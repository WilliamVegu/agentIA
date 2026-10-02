"""Runnable, copy-pasteable test examples for Microservice Code Studio.

This module is intentionally illustrative: it shows one example per test level
and per supported technique, rather than trying to cover the domain. It is
safe to delete or to copy individual functions into a feature test file.

Run just these examples:

    python -m pytest backend/tests/test_app_examples.py -v

Conventions used here (same as the rest of the suite):
  * ``backend/tests/conftest.py`` isolates the SQLAlchemy database to a
    temporary SQLite file for the whole session, so tests never touch
    ``backend/studio.db``.
  * Anything that writes generated code must redirect ``settings.WORKSPACE_DIR``
    to ``tmp_path`` so ``backend/workspaces/`` stays clean.
  * LLM-backed endpoints are exercised with ``provider="mock"`` (the offline
    mock engine), so no API key and no network are required.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.models.session import (
    GenerationSessionDB,
    SessionLocal,
    SessionPhase,
    SessionStatus,
)
from app.orchestrator.repair import can_retry, parse_maven_errors
from app.services.security_service import scan_secrets

client = TestClient(app)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _delete_session(session_id: str) -> None:
    """Removes a session row created by a test (the DB itself is a temp file)."""
    db = SessionLocal()
    try:
        db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).delete()
        db.commit()
    finally:
        db.close()


def _create_session_row(session_id: str, **overrides) -> None:
    """Inserts a session row directly, bypassing the HTTP layer."""
    values = dict(
        id=session_id,
        spec_id="spec-example",
        spec_name="order-service",
        status=SessionStatus.QUEUED,
        phase=SessionPhase.INITIALIZATION,
        current_lifecycle_phase="INITIAL",
        lifecycle_mode="GUIDED_STEP",
        repair_attempts=0,
    )
    values.update(overrides)

    db = SessionLocal()
    try:
        db.merge(GenerationSessionDB(**values))
        db.commit()
    finally:
        db.close()


#: Compliant sources: a validation-annotated record and the advice that satisfies
#: Principle III structurally. The Quality Gate now BLOCKS a workspace with no
#: audited source ("No source code was audited"), so "the gate passes" needs a
#: workspace that actually contains auditable, compliant code.
_CLEAN_SOURCES = {
    "src/main/java/com/corp/order/dto/OrderRequest.java": (
        "package com.corp.order.dto;\n"
        "import jakarta.validation.constraints.NotNull;\n"
        "import java.math.BigDecimal;\n\n"
        "public record OrderRequest(@NotNull BigDecimal amount) {}\n"
    ),
    "src/main/java/com/corp/order/advice/GlobalExceptionHandler.java": (
        "package com.corp.order.advice;\n"
        "import org.springframework.web.bind.annotation.RestControllerAdvice;\n\n"
        "@RestControllerAdvice\n"
        "public class GlobalExceptionHandler {}\n"
    ),
}


def _write_clean_sources(workspace: Path) -> None:
    for relative, content in _CLEAN_SOURCES.items():
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def _mark_session_verified(session_id: str) -> None:
    """Persist the verification evidence export/publish now require.

    ``require_verified_session`` accepts a session only when it is COMPLETED/VERIFIED,
    carries no error, and its metrics' ``workspaceFingerprint`` still matches the files
    on disk. These examples are about the export/publish contract, so the evidence the
    pipeline would normally write is seeded after the workspace is in its final state.
    """
    from app.services.verification_policy import workspace_fingerprint

    workspace = Path(settings.WORKSPACE_DIR) / session_id
    metrics = {
        "totalTests": 4,
        "passedTests": 4,
        "failedTests": 0,
        "allPassed": True,
        "fallback_used": False,
        "workspaceFingerprint": workspace_fingerprint(workspace),
    }
    db = SessionLocal()
    try:
        row = (
            db.query(GenerationSessionDB)
            .filter(GenerationSessionDB.id == session_id)
            .first()
        )
        row.status = SessionStatus.COMPLETED
        row.phase = SessionPhase.VERIFIED
        row.error_message = None
        row.verification_metrics_json = json.dumps(metrics)
        db.commit()
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# Level 1 - Smoke test: the process boots and answers
# --------------------------------------------------------------------------- #
def test_example_smoke_health_endpoint():
    """Cheapest possible check: the FastAPI app is importable and serving."""
    response = client.get("/healthz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "UP"
    assert body["app"] == settings.APP_NAME


# --------------------------------------------------------------------------- #
# Level 2 - API test with an isolated workspace
# --------------------------------------------------------------------------- #
def test_example_quick_start_creates_session_and_spec(tmp_path, monkeypatch):
    """POST /sessions/quick-start creates the DB row and writes spec.md."""
    monkeypatch.setattr(settings, "WORKSPACE_DIR", str(tmp_path))

    payload = {
        "serviceName": "inventory-service",
        "rawText": "Manage stock levels, warehouse items, and low-inventory alerts.",
        "databaseEngine": "POSTGRESQL",
    }
    response = client.post("/api/v1/sessions/quick-start", json=payload)
    assert response.status_code == 201

    body = response.json()
    session_id = body["sessionId"]
    try:
        assert body["specName"] == "inventory-service"
        assert body["status"] == "QUEUED"
        assert body["lifecycleMode"] == "GUIDED_STEP"

        spec_file: Path = tmp_path / session_id / "spec.md"
        assert spec_file.exists()
        assert "inventory-service" in spec_file.read_text(encoding="utf-8")
    finally:
        _delete_session(session_id)


def test_example_quick_start_defaults_are_applied(tmp_path, monkeypatch):
    """Empty payload is valid: the endpoint falls back to 'app-service'."""
    monkeypatch.setattr(settings, "WORKSPACE_DIR", str(tmp_path))

    response = client.post("/api/v1/sessions/quick-start", json={})
    assert response.status_code == 201

    session_id = response.json()["sessionId"]
    try:
        assert response.json()["specName"] == "app-service"
    finally:
        _delete_session(session_id)


# --------------------------------------------------------------------------- #
# Level 3 - Contract tests for the ingestion API
# --------------------------------------------------------------------------- #
def test_example_upload_spec_markdown():
    """Multipart upload of a Spec Kit markdown file returns a parsed summary."""
    spec_content = "\n".join(
        [
            "# Feature Specification: Payment Service",
            "**Feature Branch**: `002-payment-service`",
            "### Key Entities",
            "- **Payment**: id (UUID, PK), amount (BigDecimal, @Positive)",
            "### User Story 1 - Process Payment (Priority: P1)",
            "As a user I want to pay so that my account is credited.",
            "1. **Given** valid funds, **When** payment is submitted, **Then** 201 is returned.",
        ]
    )
    files = {"file": ("spec.md", spec_content.encode("utf-8"), "text/markdown")}

    response = client.post("/api/v1/specifications/upload", files=files)

    assert response.status_code == 201
    body = response.json()
    assert body["serviceName"] == "payment-service"
    assert body["isValid"] is True


def test_example_submit_blueprint_json():
    """Structured JSON blueprint ingestion (no LLM involved)."""
    payload = {
        "serviceName": "inventory-service",
        "packageName": "com.corp.inventory",
        "basePort": 8082,
        "entities": [
            {
                "name": "Item",
                "tableName": "items",
                "attributes": [
                    {"name": "id", "type": "UUID", "isPrimaryKey": True},
                    {"name": "sku", "type": "String", "validationRules": ["@NotBlank"]},
                ],
            }
        ],
        "userStories": [
            {
                "id": "US-1",
                "priority": "P1",
                "role": "Warehouse Manager",
                "intent": "track inventory",
                "benefit": "know stock levels",
                "scenarios": [
                    {
                        "scenarioId": "AC-1.1",
                        "given": "sku exists",
                        "when": "query item",
                        "then": "return current quantity",
                    }
                ],
            }
        ],
    }

    response = client.post("/api/v1/specifications", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["serviceName"] == "inventory-service"
    assert body["entityCount"] == 1
    assert body["isValid"] is True


def test_example_invalid_blueprint_uses_error_envelope():
    """Validation failures return the centralized RFC-style 400 envelope."""
    response = client.post("/api/v1/specifications", json={"serviceName": "Bad Service Name"})

    assert response.status_code == 400
    body = response.json()
    assert body["status"] == 400
    assert "message" in body and "details" in body


def test_example_unknown_specification_returns_404():
    response = client.get("/api/v1/specifications/does-not-exist")
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Level 4 - LLM-backed endpoints without an API key (mock provider)
# --------------------------------------------------------------------------- #
def test_example_requirements_transform_offline_mock(monkeypatch):
    """provider='mock' no longer routes to a mock engine: it is rejected (no key)."""
    for var in ("OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    payload = {
        "rawText": (
            "Microservicio para gestionar órdenes de compra con email de cliente "
            "y monto total, incluyendo validación de stock."
        ),
        "serviceName": "order-service",
        "provider": "mock",
    }

    response = client.post("/api/v1/requirements/transform", json=payload)

    assert response.status_code == 401


def test_example_llm_verify_mock_provider():
    """Credential verification no longer short-circuits to READY for the mock provider."""
    response = client.post("/api/v1/llm/verify", json={"provider": "mock"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ERROR"


def test_example_missing_api_key_is_rejected(monkeypatch):
    """Constitution Principle VI: no ephemeral key -> 401, never a silent fallback."""
    for var in ("OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(settings, "ALLOW_OFFLINE_MOCK", False)

    response = client.post(
        "/api/v1/requirements/transform",
        json={"rawText": "Requisitos válidos con longitud suficiente sin clave de API."},
    )

    assert response.status_code == 401
    assert "LLM API key is required" in response.text


# --------------------------------------------------------------------------- #
# Level 5 - Deterministic security / quality auditing
# --------------------------------------------------------------------------- #
def test_example_security_audit_passes_clean_code():
    """A compliant DTO record plus a @RestControllerAdvice passes the gate.

    Note: omitting the advice would BLOCK the gate even with no secrets or
    CVEs, because Principle III is enforced structurally -- as the next test
    for a non-compliant workspace shows.
    """
    payload = {
        "serviceName": "payment-service",
        "files": {
            "src/main/java/com/corp/payment/dto/PaymentRequest.java": (
                "package com.corp.payment.dto;\n"
                "import jakarta.validation.constraints.NotNull;\n"
                "import java.math.BigDecimal;\n\n"
                "public record PaymentRequest(@NotNull BigDecimal amount) {}\n"
            ),
            "src/main/java/com/corp/payment/advice/GlobalExceptionHandler.java": (
                "package com.corp.payment.advice;\n"
                "import org.springframework.web.bind.annotation.RestControllerAdvice;\n\n"
                "@RestControllerAdvice\n"
                "public class GlobalExceptionHandler {}\n"
            ),
        },
        "pomXml": "<project><dependencies></dependencies></project>",
    }

    response = client.post("/api/v1/security/audit", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["qualityGate"]["status"] == "PASS"
    assert body["qualityGate"]["canExport"] is True
    assert body["vulnerabilities"] == []
    assert body["violations"] == []


def test_example_security_audit_blocks_secret_and_injection():
    payload = {
        "serviceName": "vulnerable-service",
        "files": {
            "src/main/resources/application.yml": "openai: sk-proj-12345678901234567890abcdef",
            "src/main/java/com/corp/repository/OrderRepository.java": (
                "package com.corp.repository;\n"
                'public interface OrderRepository {\n'
                '    @Query("SELECT o FROM Order o WHERE o.name = \'" + name + "\'")\n'
                "    List<Order> findByName(String name);\n"
                "}\n"
            ),
        },
        "pomXml": "<project></project>",
    }

    response = client.post("/api/v1/security/audit", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["qualityGate"]["status"] == "BLOCKED"
    assert body["qualityGate"]["canExport"] is False
    assert body["qualityGate"]["criticalCount"] >= 1
    assert len(body["vulnerabilities"]) >= 2


def test_example_surgical_remediation_returns_a_diff():
    payload = {
        "findingId": "CONST-VIOL-001",
        "filePath": "src/main/java/com/corp/dto/ItemRequest.java",
        "sourceCode": (
            "package com.corp.dto;\n\n"
            "public class ItemRequest {\n"
            "    private String name;\n"
            "    private int quantity;\n"
            "}\n"
        ),
    }

    response = client.post("/api/v1/security/remediate", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    assert "public record ItemRequest(String name, int quantity)" in body["remediatedCode"]
    assert "--- a/src/main/java/com/corp/dto/ItemRequest.java" in body["diff"]


# --------------------------------------------------------------------------- #
# Level 6 - Orchestrator lifecycle state machine
# --------------------------------------------------------------------------- #
def test_example_lifecycle_and_phase_transition(tmp_path, monkeypatch):
    """Guided mode: a phase only advances once its prerequisite files exist."""
    session_id = "example-lifecycle-session"
    monkeypatch.setattr(settings, "WORKSPACE_DIR", str(tmp_path))
    workspace = tmp_path / session_id
    workspace.mkdir(parents=True, exist_ok=True)
    _create_session_row(session_id)

    try:
        # 1. Fresh session reports the full 7-phase plan at 0% completion.
        lifecycle = client.get(f"/api/v1/orchestrator/sessions/{session_id}/lifecycle")
        assert lifecycle.status_code == 200
        assert len(lifecycle.json()["phases"]) == 7

        # 2. Jumping ahead is refused while spec.md is missing.
        premature = client.post(
            f"/api/v1/orchestrator/sessions/{session_id}/transition",
            json={"targetPhase": "DEVOPS_DEPLOY", "force": False},
        )
        assert premature.status_code == 400

        # 3. Satisfy the requirement, then advance one step.
        (workspace / "spec.md").write_text("# Order Service Spec", encoding="utf-8")
        advanced = client.post(
            f"/api/v1/orchestrator/sessions/{session_id}/transition",
            json={"targetPhase": "STORIES", "force": False},
        )
        assert advanced.status_code == 200
        assert advanced.json()["currentPhase"] == "STORIES"
    finally:
        _delete_session(session_id)


# --------------------------------------------------------------------------- #
# Level 7 - Mocking an external boundary (no real Git server contacted)
# --------------------------------------------------------------------------- #
def test_example_publish_to_git_with_mocked_boundary(tmp_path, monkeypatch):
    """Replace the outbound Git call; assert the route's own behaviour."""
    from app.api import routes_publish

    session_id = "example-publish-session"
    monkeypatch.setattr(settings, "WORKSPACE_DIR", str(tmp_path))
    workspace = tmp_path / session_id
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "pom.xml").write_text("<project></project>", encoding="utf-8")
    # Publishing is gated on a verified session *and* a passing Quality Gate. The
    # workspace therefore has to hold auditable, compliant code, and the session has
    # to carry the verification evidence; the route's Git behaviour is unchanged.
    _write_clean_sources(workspace)
    _create_session_row(session_id, status=SessionStatus.COMPLETED, phase=SessionPhase.VERIFIED)
    _mark_session_verified(session_id)

    captured = {}

    def fake_publish_to_git(**kwargs):
        captured.update(kwargs)
        return {
            "branchUrl": "https://github.com/corp/orders/tree/feature/001-order-service",
            "commitHash": "abc1234",
            "pullRequestUrl": "https://github.com/corp/orders/pull/1",
            "branchName": kwargs["branch_name"],
        }

    monkeypatch.setattr(routes_publish, "publish_to_git", fake_publish_to_git)

    try:
        response = client.post(
            f"/api/v1/sessions/{session_id}/publish",
            json={
                "repositoryUrl": "https://github.com/corp/orders.git",
                "branchName": "feature/001-order-service",
                "gitToken": "ghp_ephemeral_token",
            },
        )

        assert response.status_code == 200
        assert response.json()["commitHash"] == "abc1234"
        # The ephemeral token is forwarded in memory and never persisted.
        assert captured["git_token"] == "ghp_ephemeral_token"
        assert captured["repository_url"] == "https://github.com/corp/orders.git"
    finally:
        _delete_session(session_id)


# --------------------------------------------------------------------------- #
# Level 8 - Pure unit tests: no HTTP, no DB, no I/O
# --------------------------------------------------------------------------- #
def test_example_unit_parse_maven_compilation_error():
    log = (
        "[ERROR] COMPILATION ERROR :\n"
        "[ERROR] /workspace/src/main/java/com/corp/order/service/OrderServiceImpl.java:[28,15]"
        " cannot find symbol\n"
        "[INFO] 1 error\n"
    )

    diagnostic = parse_maven_errors(log)

    assert diagnostic["error_type"] == "COMPILATION"
    assert "OrderServiceImpl.java" in diagnostic["failed_file"]
    assert "cannot find symbol" in diagnostic["summary"]


def test_example_unit_repair_boundary_is_three_attempts():
    assert can_retry(current_attempt=1, max_attempts=3) is True
    assert can_retry(current_attempt=2, max_attempts=3) is True
    assert can_retry(current_attempt=3, max_attempts=3) is False


def test_example_unit_secret_scanner_flags_hardcoded_key():
    findings = scan_secrets(
        {"src/main/resources/application.properties": "api.key=sk-proj-999988887777666655554444"}
    )

    assert findings, "a hardcoded provider key must be reported"
    assert any(f.severity.value in ("CRITICAL", "HIGH") for f in findings)
    assert any("key" in f.title.lower() or "secret" in f.title.lower() for f in findings)


# --------------------------------------------------------------------------- #
# Level 9 - Parametrized contract test (one rule, many cases)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "service_name, expected",
    [
        ("order-service", "order-service"),
        ("inventory-service", "inventory-service"),
        ("", "app-service"),
    ],
)
def test_example_parametrized_service_names(tmp_path, monkeypatch, service_name, expected):
    monkeypatch.setattr(settings, "WORKSPACE_DIR", str(tmp_path))

    payload = {"serviceName": service_name} if service_name else {}
    response = client.post("/api/v1/sessions/quick-start", json=payload)
    assert response.status_code == 201

    session_id = response.json()["sessionId"]
    try:
        assert response.json()["specName"] == expected
    finally:
        _delete_session(session_id)


# --------------------------------------------------------------------------- #
# Level 10 - Export guard: the Quality Gate blocks unsafe artifacts
# --------------------------------------------------------------------------- #
def test_example_export_blocked_when_quality_gate_fails(tmp_path, monkeypatch):
    session_id = "example-blocked-export-session"
    monkeypatch.setattr(settings, "WORKSPACE_DIR", str(tmp_path))
    workspace = tmp_path / session_id
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "application.properties").write_text(
        "api.secret=sk-proj-99998888777766665555444433332222", encoding="utf-8"
    )
    (workspace / "pom.xml").write_text("<project></project>", encoding="utf-8")
    _create_session_row(session_id, status=SessionStatus.COMPLETED, phase=SessionPhase.VERIFIED)
    # The session is verified; the secret in the workspace is what must block export.
    _mark_session_verified(session_id)

    try:
        audit = client.get(f"/api/v1/sessions/{session_id}/audit")
        assert audit.status_code == 200
        assert audit.json()["qualityGate"]["status"] == "BLOCKED"

        export = client.get(f"/api/v1/sessions/{session_id}/export")
        assert export.status_code == 403
        assert "Quality Gate is BLOCKED" in export.json()["detail"]
    finally:
        _delete_session(session_id)


def test_example_export_returns_a_zip_when_gate_passes(tmp_path, monkeypatch):
    session_id = "example-clean-export-session"
    monkeypatch.setattr(settings, "WORKSPACE_DIR", str(tmp_path))
    workspace = tmp_path / session_id
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "pom.xml").write_text("<project></project>", encoding="utf-8")
    # A gate that passes requires audited code, not just a build file.
    _write_clean_sources(workspace)
    _create_session_row(session_id, status=SessionStatus.COMPLETED, phase=SessionPhase.VERIFIED)
    _mark_session_verified(session_id)

    try:
        response = client.get(f"/api/v1/sessions/{session_id}/export")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        assert "order-service.zip" in response.headers["content-disposition"]
        assert len(response.content) > 0
    finally:
        _delete_session(session_id)


# --------------------------------------------------------------------------- #
# Level 11 - Pipeline execution internals, with the gate mocked
# --------------------------------------------------------------------------- #
def test_example_pipeline_stops_at_blocked_quality_gate(tmp_path, monkeypatch):
    """Pipeline runner example: one mocked dependency, no Docker, no network."""
    import threading
    from unittest.mock import MagicMock

    import app.services.pipeline_runner as pipeline_runner
    from app.models.orchestrator import LifecyclePhase, PipelineRunStatus

    session_id = "example-runner-session"
    monkeypatch.setattr(settings, "WORKSPACE_DIR", str(tmp_path))
    (tmp_path / session_id).mkdir(parents=True, exist_ok=True)
    _create_session_row(session_id, lifecycle_mode="AUTO_PILOT")
    pipeline_runner._pause_events[session_id] = threading.Event()
    pipeline_runner._stop_events[session_id] = threading.Event()

    blocked_audit = MagicMock()
    blocked_audit.qualityGate.status = "BLOCKED"
    blocked_audit.qualityGate.summaryMessage = "Hardcoded password found in configuration"
    monkeypatch.setattr(pipeline_runner, "audit_workspace", lambda *a, **kw: blocked_audit)

    # The security audit is reached only after hermetic verification. Without this
    # stub the sandbox result decides the run (fallback => AWAITING_INTERVENTION as
    # well), and the mocked gate below is never consulted -- which would make this
    # test pass without exercising its own subject. A passing verification lets the
    # run reach the gate.
    from app.sandbox.docker_runner import DockerExecutionResult
    from app.services.workspace_verification import WorkspaceVerification

    passed_verification = WorkspaceVerification(
        result=DockerExecutionResult(
            exit_code=0,
            stdout="[INFO] Tests run: 5, Failures: 0, Errors: 0, Skipped: 0\n",
        ),
        platform_test_path="src/test/java/x/PlatformPersistenceContractTest.java",
    )
    monkeypatch.setattr(
        pipeline_runner,
        "run_workspace_verification",
        lambda path, log_callback=None: passed_verification,
    )

    try:
        pipeline_runner._execute_pipeline_steps(
            session_id,
            LifecyclePhase.DEVOPS_DEPLOY,
            stop_on_gate=True,
            auto_deploy=False,
        )

        assert pipeline_runner._pipeline_statuses.get(session_id) == PipelineRunStatus.AWAITING_INTERVENTION
        # The gate halts the run and names the reason. It cannot prevent the DevOps
        # assets from existing any more: `generate_all_devops_assets` runs before
        # verification, because the hermetic container build needs the workspace's
        # Dockerfile. The terminal state, not a file's absence, is the evidence that
        # the pipeline stopped at the gate.
        db = SessionLocal()
        try:
            row = (
                db.query(GenerationSessionDB)
                .filter(GenerationSessionDB.id == session_id)
                .first()
            )
            assert row.status == SessionStatus.BLOCKED
            assert row.error_message == "Hardcoded password found in configuration"
        finally:
            db.close()
    finally:
        _delete_session(session_id)
        pipeline_runner._pause_events.pop(session_id, None)
        pipeline_runner._stop_events.pop(session_id, None)
        pipeline_runner._pipeline_statuses.pop(session_id, None)


# --------------------------------------------------------------------------- #
# Level 12 - SSE stream shape
# --------------------------------------------------------------------------- #
def test_example_unknown_session_stream_returns_404():
    """Streaming endpoint contract: an unknown session is rejected up front."""
    response = client.get("/api/v1/sessions/example-unknown-session/stream")
    assert response.status_code == 404


def test_example_sse_event_history_is_recorded():
    """The SSE feed replays recorded events.

    Deliberately tested through the in-process recorder rather than by
    consuming the live stream: a real SSE response keeps emitting keepalives,
    so reading it with TestClient blocks. Use ``curl -N`` against a running
    server for the live end-to-end check (see TESTING_EXAMPLES.md).
    """
    from app.api import routes_session

    session_id = "example-sse-session"
    routes_session.broadcast_session_event(
        session_id, "phase_transition", {"sessionId": session_id, "phase": "STORIES"}
    )

    try:
        history = routes_session.SESSION_EVENT_HISTORY[session_id]
        assert len(history) == 1
        assert history[0]["event"] == "phase_transition"
        assert json.loads(history[0]["data"])["phase"] == "STORIES"
    finally:
        routes_session.SESSION_EVENT_HISTORY.pop(session_id, None)


def test_example_session_detail_is_json_serializable(tmp_path, monkeypatch):
    session_id = "example-detail-session"
    monkeypatch.setattr(settings, "WORKSPACE_DIR", str(tmp_path))
    _create_session_row(session_id, spec_name="detail-service")

    try:
        response = client.get(f"/api/v1/sessions/{session_id}")
        assert response.status_code == 200

        body = response.json()
        assert body["specName"] == "detail-service"
        json.dumps(body)  # must round-trip
    finally:
        _delete_session(session_id)


def test_example_delete_cancels_the_session():
    """DELETE /sessions/{id} cancels (204); an unknown id is a 404."""
    session_id = "example-delete-session"
    _create_session_row(session_id)

    try:
        response = client.delete(f"/api/v1/sessions/{session_id}")
        assert response.status_code == 204

        detail = client.get(f"/api/v1/sessions/{session_id}")
        assert detail.json()["status"] == "CANCELLED"

        missing = client.delete("/api/v1/sessions/example-missing-session")
        assert missing.status_code == 404
    finally:
        _delete_session(session_id)


def test_example_list_sessions_returns_array():
    response = client.get("/api/v1/sessions?limit=5")

    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) <= 5
