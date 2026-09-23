import io
import json
import zipfile
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.orchestrator.graph import generation_graph
from app.orchestrator.nodes.validator_node import validator_node
from app.orchestrator.nodes.scaffolder_node import scaffolder_node
from app.orchestrator.nodes.domain_node import domain_node
from app.orchestrator.nodes.service_node import service_node
from app.orchestrator.nodes.controller_node import controller_node
from app.orchestrator.nodes.test_node import test_node as execute_test_node
from app.orchestrator.nodes.sandbox_node import sandbox_node
from app.orchestrator.nodes.repair_node import repair_node
from app.orchestrator.state import GenerationAgentState
from app.models.session import (
    GenerationSessionDB,
    SessionLocal,
    SessionPhase,
    SessionStatus,
)

client = TestClient(app)

SAMPLE_BLUEPRINT = {
    "serviceName": "order-billing-service",
    "packageName": "com.tcs.billing",
    "basePort": 8080,
    "databaseMode": "PostgreSQL",
    "entities": [
        {
            "name": "Invoice",
            "tableName": "invoices",
            "attributes": [
                {"name": "id", "type": "Long", "isPrimaryKey": True, "nullable": False},
                {"name": "customerEmail", "type": "String", "nullable": False, "validationRules": ["@NotBlank"]},
                {"name": "totalAmount", "type": "BigDecimal", "nullable": False, "validationRules": ["@NotNull"]},
                {"name": "status", "type": "String", "nullable": False, "validationRules": ["@NotBlank"]},
            ],
        },
        {
            "name": "Payment",
            "tableName": "payments",
            "attributes": [
                {"name": "id", "type": "Long", "isPrimaryKey": True, "nullable": False},
                {"name": "invoiceId", "type": "Long", "nullable": False},
                {"name": "paymentMethod", "type": "String", "nullable": False},
                {"name": "amountPaid", "type": "BigDecimal", "nullable": False},
            ],
        },
    ],
    "userStories": [
        {
            "id": "US-1",
            "priority": "P1",
            "role": "BillingManager",
            "intent": "Emit invoice and record payment",
            "benefit": "Collect revenue accurately",
            "scenarios": [
                {
                    "scenarioId": "AC-1.1",
                    "given": "Valid invoice details",
                    "when": "POST /api/v1/invoices is called",
                    "then": "Invoice is persisted and 201 Created is returned",
                }
            ],
        }
    ],
}


@pytest.fixture
def clean_workspace(tmp_path, monkeypatch):
    """Provides a sterile, isolated workspace directory for test execution."""
    ws = tmp_path / "codegen_test_ws"
    ws.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "WORKSPACE_DIR", str(ws))
    return ws


# =========================================================================
# 1. Scaffolding Node Tests
# =========================================================================
def test_scaffolder_node_generates_maven_archetype(clean_workspace):
    session_ws = clean_workspace / "sess_scaffold"
    session_ws.mkdir()

    state: GenerationAgentState = {
        "session_id": "sess_scaffold",
        "blueprint": SAMPLE_BLUEPRINT,
        "workspace_path": str(session_ws),
        "generated_files": {},
        "logs": [],
    }

    result = scaffolder_node(state)

    pom_path = session_ws / "pom.xml"
    app_yml_path = session_ws / "src" / "main" / "resources" / "application.yml"
    app_java_path = (
        session_ws
        / "src"
        / "main"
        / "java"
        / "com"
        / "tcs"
        / "billing"
        / "OrderBillingServiceApplication.java"
    )

    assert pom_path.exists(), "pom.xml must be generated"
    assert app_yml_path.exists(), "application.yml must be generated"
    assert app_java_path.exists(), "Main Application.java must be generated"

    # Verify pom.xml contents
    pom_content = pom_path.read_text(encoding="utf-8")
    assert "<java.version>21</java.version>" in pom_content
    assert "spring-boot-starter-web" in pom_content
    assert "spring-boot-starter-data-jpa" in pom_content
    assert "spring-boot-starter-validation" in pom_content
    assert "spring-boot-starter-test" in pom_content
    assert "h2" in pom_content

    # Verify Application.java
    app_code = app_java_path.read_text(encoding="utf-8")
    assert "@SpringBootApplication" in app_code
    assert "public class OrderBillingServiceApplication" in app_code
    assert "package com.tcs.billing;" in app_code


# =========================================================================
# 2. Domain Node Tests (JPA Entities + Immutable Records DTOs)
# =========================================================================
def test_domain_node_generates_jpa_entities_and_record_dtos(clean_workspace):
    session_ws = clean_workspace / "sess_domain"
    session_ws.mkdir()

    state: GenerationAgentState = {
        "session_id": "sess_domain",
        "blueprint": SAMPLE_BLUEPRINT,
        "workspace_path": str(session_ws),
        "generated_files": {},
        "logs": [],
    }

    result = domain_node(state)

    # Check Invoice Entity
    invoice_entity_path = (
        session_ws
        / "src"
        / "main"
        / "java"
        / "com"
        / "tcs"
        / "billing"
        / "model"
        / "entity"
        / "Invoice.java"
    )
    assert invoice_entity_path.exists()
    invoice_src = invoice_entity_path.read_text(encoding="utf-8")
    assert "@Entity" in invoice_src
    assert '@Table(name = "invoices")' in invoice_src
    assert "@Id" in invoice_src
    assert "@GeneratedValue(strategy = GenerationType.IDENTITY)" in invoice_src
    assert "private java.math.BigDecimal totalAmount;" in invoice_src
    assert "public java.math.BigDecimal getTotalAmount()" in invoice_src

    # Check Payment Entity
    payment_entity_path = (
        session_ws
        / "src"
        / "main"
        / "java"
        / "com"
        / "tcs"
        / "billing"
        / "model"
        / "entity"
        / "Payment.java"
    )
    assert payment_entity_path.exists()

    # Check Immutable Records DTOs (Principle II)
    invoice_req_dto = (
        session_ws
        / "src"
        / "main"
        / "java"
        / "com"
        / "tcs"
        / "billing"
        / "model"
        / "dto"
        / "CreateInvoiceRequest.java"
    )
    assert invoice_req_dto.exists()
    req_dto_src = invoice_req_dto.read_text(encoding="utf-8")
    assert "public record CreateInvoiceRequest(" in req_dto_src, "DTOs must be Java Records"

    invoice_resp_dto = (
        session_ws
        / "src"
        / "main"
        / "java"
        / "com"
        / "tcs"
        / "billing"
        / "model"
        / "dto"
        / "InvoiceResponse.java"
    )
    assert invoice_resp_dto.exists()
    resp_dto_src = invoice_resp_dto.read_text(encoding="utf-8")
    assert "public record InvoiceResponse(" in resp_dto_src, "Response DTO must be Java Record"


# =========================================================================
# 3. Service Node Tests
# =========================================================================
def test_service_node_generates_repositories_and_services(clean_workspace):
    session_ws = clean_workspace / "sess_service"
    session_ws.mkdir()

    state: GenerationAgentState = {
        "session_id": "sess_service",
        "blueprint": SAMPLE_BLUEPRINT,
        "workspace_path": str(session_ws),
        "generated_files": {},
        "logs": [],
    }

    result = service_node(state)

    # 1. Custom Exception
    ex_path = (
        session_ws
        / "src"
        / "main"
        / "java"
        / "com"
        / "tcs"
        / "billing"
        / "exception"
        / "ResourceNotFoundException.java"
    )
    assert ex_path.exists()
    assert "public class ResourceNotFoundException extends RuntimeException" in ex_path.read_text(encoding="utf-8")

    # 2. Repository interface
    repo_path = (
        session_ws
        / "src"
        / "main"
        / "java"
        / "com"
        / "tcs"
        / "billing"
        / "repository"
        / "InvoiceRepository.java"
    )
    assert repo_path.exists()
    repo_src = repo_path.read_text(encoding="utf-8")
    assert "public interface InvoiceRepository extends JpaRepository<Invoice, Long>" in repo_src

    # 3. Service Interface & Implementation
    svc_iface_path = (
        session_ws
        / "src"
        / "main"
        / "java"
        / "com"
        / "tcs"
        / "billing"
        / "service"
        / "InvoiceService.java"
    )
    assert svc_iface_path.exists()

    svc_impl_path = (
        session_ws
        / "src"
        / "main"
        / "java"
        / "com"
        / "tcs"
        / "billing"
        / "service"
        / "impl"
        / "InvoiceServiceImpl.java"
    )
    assert svc_impl_path.exists()
    impl_src = svc_impl_path.read_text(encoding="utf-8")
    assert "@Service" in impl_src
    assert "public class InvoiceServiceImpl implements InvoiceService" in impl_src
    assert "private final InvoiceRepository repository;" in impl_src


# =========================================================================
# 4. Controller Node Tests (Principle III: Centralized Error Handling)
# =========================================================================
def test_controller_node_generates_controllers_and_advice(clean_workspace):
    session_ws = clean_workspace / "sess_controller"
    session_ws.mkdir()

    state: GenerationAgentState = {
        "session_id": "sess_controller",
        "blueprint": SAMPLE_BLUEPRINT,
        "workspace_path": str(session_ws),
        "generated_files": {},
        "logs": [],
    }

    result = controller_node(state)

    # 1. GlobalExceptionHandler
    handler_path = (
        session_ws
        / "src"
        / "main"
        / "java"
        / "com"
        / "tcs"
        / "billing"
        / "controller"
        / "GlobalExceptionHandler.java"
    )
    assert handler_path.exists()
    handler_src = handler_path.read_text(encoding="utf-8")
    assert "@RestControllerAdvice" in handler_src
    assert "@ExceptionHandler(ResourceNotFoundException.class)" in handler_src
    assert "@ExceptionHandler(MethodArgumentNotValidException.class)" in handler_src

    # 2. RestController
    ctrl_path = (
        session_ws
        / "src"
        / "main"
        / "java"
        / "com"
        / "tcs"
        / "billing"
        / "controller"
        / "InvoiceController.java"
    )
    assert ctrl_path.exists()
    ctrl_src = ctrl_path.read_text(encoding="utf-8")
    assert "@RestController" in ctrl_src
    assert '@RequestMapping("/api/v1/invoices")' in ctrl_src
    assert "@PostMapping" in ctrl_src
    assert "@Valid @RequestBody CreateInvoiceRequest" in ctrl_src
    assert "public ResponseEntity<InvoiceResponse>" in ctrl_src


# =========================================================================
# 5. Test Node Tests (Mockito Unit Tests + WebMvcTest Integration)
# =========================================================================
def test_test_node_generates_mockito_and_web_tests(clean_workspace):
    session_ws = clean_workspace / "sess_test"
    session_ws.mkdir()

    state: GenerationAgentState = {
        "session_id": "sess_test",
        "blueprint": SAMPLE_BLUEPRINT,
        "workspace_path": str(session_ws),
        "generated_files": {},
        "logs": [],
    }

    result = execute_test_node(state)

    # Main context sanity test
    app_test = (
        session_ws
        / "src"
        / "test"
        / "java"
        / "com"
        / "tcs"
        / "billing"
        / "OrderBillingServiceApplicationTests.java"
    )
    assert app_test.exists()

    # Invoice Service Mockito Unit Test
    invoice_svc_test = (
        session_ws
        / "src"
        / "test"
        / "java"
        / "com"
        / "tcs"
        / "billing"
        / "service"
        / "InvoiceServiceTest.java"
    )
    assert invoice_svc_test.exists()
    invoice_test_src = invoice_svc_test.read_text(encoding="utf-8")
    assert "@ExtendWith(MockitoExtension.class)" in invoice_test_src
    assert "@Mock" in invoice_test_src
    assert "@InjectMocks" in invoice_test_src
    assert "shouldCreateInvoiceSuccessfully" in invoice_test_src

    # Payment Service Mockito Unit Test
    payment_svc_test = (
        session_ws
        / "src"
        / "test"
        / "java"
        / "com"
        / "tcs"
        / "billing"
        / "service"
        / "PaymentServiceTest.java"
    )
    assert payment_svc_test.exists()
    payment_test_src = payment_svc_test.read_text(encoding="utf-8")
    assert "@ExtendWith(MockitoExtension.class)" in payment_test_src
    assert "shouldCreatePaymentSuccessfully" in payment_test_src


# =========================================================================
# 6. Complete LangGraph State Graph Workflow Execution
# =========================================================================
def test_complete_langgraph_generation_graph(clean_workspace):
    session_ws = clean_workspace / "sess_graph_full"
    session_ws.mkdir()

    initial_state = {
        "session_id": "sess_graph_full",
        "blueprint": SAMPLE_BLUEPRINT,
        "workspace_path": str(session_ws),
        "generated_files": {},
        "logs": [],
    }

    final_state = generation_graph.invoke(initial_state)

    assert final_state["build_success"] is True
    assert final_state["status"] == SessionStatus.COMPLETED.value
    assert final_state["current_phase"] == SessionPhase.VERIFIED.value

    # Verify that all 4 layers and tests are generated in the file system
    all_java_files = list(session_ws.glob("**/*.java"))
    assert len(all_java_files) >= 10, f"Expected at least 10 Java files, found {len(all_java_files)}"

    # Verify POM exists
    assert (session_ws / "pom.xml").exists()
    assert (session_ws / "src" / "main" / "resources" / "application.yml").exists()


# =========================================================================
# 7. Validator Failure Edge Case
# =========================================================================
def test_validator_fails_gracefully_when_no_entities(clean_workspace):
    session_ws = clean_workspace / "sess_invalid"
    session_ws.mkdir()

    invalid_blueprint = {
        "serviceName": "empty-service",
        "packageName": "com.empty",
        "entities": [],
    }

    initial_state = {
        "session_id": "sess_invalid",
        "blueprint": invalid_blueprint,
        "workspace_path": str(session_ws),
        "generated_files": {},
        "logs": [],
    }

    final_state = generation_graph.invoke(initial_state)
    assert final_state.get("status") == "FAILED"
    assert "at least one domain entity" in final_state.get("error", "")


# =========================================================================
# 8. Self-Repair Bounded Iteration Tests (Principle V: Max 3 Attempts)
# =========================================================================
def test_repair_node_stops_after_3_attempts(clean_workspace):
    session_ws = clean_workspace / "sess_repair"
    session_ws.mkdir()

    state = {
        "session_id": "sess_repair",
        "blueprint": SAMPLE_BLUEPRINT,
        "workspace_path": str(session_ws),
        "repair_attempts": 3,
        "max_repair_attempts": 3,
        "last_diagnostic": {
            "failed_file": "Invoice.java",
            "summary": "Compilation syntax error",
            "line_number": 20,
        },
        "logs": [],
    }

    result = repair_node(state)
    assert result["status"] == SessionStatus.BLOCKED.value
    assert "Maximum repair attempts (3) exhausted" in result["error"]


# =========================================================================
# 9. End-to-End Artifact Retrieval and ZIP Export API Verification
# =========================================================================
def test_api_artifact_listing_and_export_zip(clean_workspace):
    session_id = "sess_api_verify"
    session_ws = clean_workspace / session_id
    session_ws.mkdir()

    # Pre-populate session in DB
    db = SessionLocal()
    db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).delete()
    sess = GenerationSessionDB(
        id=session_id,
        spec_id="spec-api-test",
        spec_name="order-billing-service",
        status=SessionStatus.COMPLETED,
        phase=SessionPhase.VERIFIED,
        current_lifecycle_phase="COMPLETED",
        lifecycle_mode="AUTO_PILOT",
    )
    db.add(sess)
    db.commit()
    db.close()

    try:
        # Run generation graph to populate workspace
        state = {
            "session_id": session_id,
            "blueprint": SAMPLE_BLUEPRINT,
            "workspace_path": str(session_ws),
            "generated_files": {},
            "logs": [],
        }
        generation_graph.invoke(state)

        # 1. Test listing artifacts via API
        resp = client.get(f"/api/v1/sessions/{session_id}/artifacts")
        assert resp.status_code == 200
        artifacts = resp.json()
        assert isinstance(artifacts, list)
        assert len(artifacts) >= 8

        # 2. Test fetching single artifact content
        pom_item = next((a for a in artifacts if a["relativePath"] == "pom.xml"), None)
        assert pom_item is not None

        content_resp = client.get(
            f"/api/v1/sessions/{session_id}/artifacts/content",
            params={"path": "pom.xml"},
        )
        assert content_resp.status_code == 200
        assert "<artifactId>order-billing-service</artifactId>" in content_resp.text

        # 3. Test ZIP Export
        export_resp = client.get(f"/api/v1/sessions/{session_id}/export")
        assert export_resp.status_code == 200
        assert export_resp.headers["content-type"] in (
            "application/zip",
            "application/x-zip-compressed",
            "application/octet-stream",
        )

        # Decompress and verify ZIP contents
        zip_buf = io.BytesIO(export_resp.content)
        with zipfile.ZipFile(zip_buf, "r") as zf:
            namelist = zf.namelist()
            assert any(f.endswith("pom.xml") for f in namelist), "ZIP must contain pom.xml"
            assert any(f.endswith("Invoice.java") for f in namelist), "ZIP must contain JPA Entity"
            assert any(f.endswith("InvoiceController.java") for f in namelist), "ZIP must contain RestController"
            assert any(f.endswith("InvoiceServiceTest.java") for f in namelist), "ZIP must contain Mockito test"

    finally:
        db = SessionLocal()
        db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).delete()
        db.commit()
        db.close()
