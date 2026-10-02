import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.models.session import GenerationSessionDB, SessionLocal, SessionPhase, SessionStatus

client = TestClient(app)


@pytest.fixture
def clean_devops_session():
    session_id = "test-devops-clean-session"
    ws_path = Path(settings.WORKSPACE_DIR) / session_id
    ws_path.mkdir(parents=True, exist_ok=True)

    # Valid, clean files. "Clean" now has to mean auditable: a workspace with no Java
    # source at all is BLOCKED with "No source code was audited", so the gate can only
    # be observed to pass on a project that actually has compliant code. The advice
    # class is what satisfies Principle III structurally.
    (ws_path / "pom.xml").write_text("<project></project>", encoding="utf-8")
    (ws_path / "schema.sql").write_text("CREATE TABLE orders (id BIGINT PRIMARY KEY);", encoding="utf-8")
    dto = ws_path / "src" / "main" / "java" / "com" / "corp" / "order" / "dto"
    dto.mkdir(parents=True, exist_ok=True)
    (dto / "OrderRequest.java").write_text(
        "package com.corp.order.dto;\n"
        "import jakarta.validation.constraints.NotNull;\n"
        "import java.math.BigDecimal;\n\n"
        "public record OrderRequest(@NotNull BigDecimal amount) {}\n",
        encoding="utf-8",
    )
    advice = ws_path / "src" / "main" / "java" / "com" / "corp" / "order" / "advice"
    advice.mkdir(parents=True, exist_ok=True)
    (advice / "GlobalExceptionHandler.java").write_text(
        "package com.corp.order.advice;\n"
        "import org.springframework.web.bind.annotation.RestControllerAdvice;\n\n"
        "@RestControllerAdvice\n"
        "public class GlobalExceptionHandler {}\n",
        encoding="utf-8",
    )

    db = SessionLocal()
    try:
        sess = GenerationSessionDB(
            id=session_id,
            spec_id="dummy-spec",
            spec_name="order-service",
            status=SessionStatus.COMPLETED,
            phase=SessionPhase.VERIFIED,
            repair_attempts=0,
        )
        db.merge(sess)
        db.commit()
    finally:
        db.close()

    yield session_id


@pytest.fixture
def blocked_devops_session():
    session_id = "test-devops-blocked-session"
    ws_path = Path(settings.WORKSPACE_DIR) / session_id
    ws_path.mkdir(parents=True, exist_ok=True)

    # Insecure file with hardcoded API key
    (ws_path / "application.yml").write_text("openai: sk-proj-12345678901234567890abcdef", encoding="utf-8")
    (ws_path / "pom.xml").write_text("<project></project>", encoding="utf-8")

    db = SessionLocal()
    try:
        sess = GenerationSessionDB(
            id=session_id,
            spec_id="dummy-spec",
            spec_name="blocked-service",
            status=SessionStatus.COMPLETED,
            phase=SessionPhase.VERIFIED,
            repair_attempts=0,
        )
        db.merge(sess)
        db.commit()
    finally:
        db.close()

    yield session_id


def test_generate_devops_manifests_success(clean_devops_session):
    sess_id = clean_devops_session
    response = client.post(f"/api/v1/devops/{sess_id}/generate?db_engine=POSTGRESQL&host_port=8080")
    assert response.status_code == 200
    data = response.json()
    assert data["sessionId"] == sess_id
    assert data["serviceName"] == "order-service"
    assert data["databaseEngine"] == "POSTGRESQL"
    assert "eclipse-temurin:21-jre-alpine" in data["dockerfileContent"]
    assert "postgres:16-alpine" in data["dockerComposeContent"]
    assert "deployment.yaml" in data["kubernetesManifests"]

    # Verify physical file existence
    ws_path = Path(settings.WORKSPACE_DIR) / sess_id
    assert (ws_path / "Dockerfile").exists()
    assert (ws_path / "docker-compose.yml").exists()
    assert (ws_path / ".github" / "workflows" / "ci-cd.yml").exists()
    assert (ws_path / "k8s" / "deployment.yaml").exists()


def test_generate_devops_manifests_blocked_by_quality_gate(blocked_devops_session):
    sess_id = blocked_devops_session
    response = client.post(f"/api/v1/devops/{sess_id}/generate")
    assert response.status_code == 403
    assert "Quality Gate is BLOCKED" in response.json()["detail"]


def test_deploy_devops_blocked_by_quality_gate(blocked_devops_session):
    sess_id = blocked_devops_session
    response = client.post(f"/api/v1/devops/{sess_id}/deploy")
    assert response.status_code == 403
    assert "Quality Gate is BLOCKED" in response.json()["detail"]


def test_deploy_devops_clean_session_behavior(clean_devops_session, monkeypatch):
    sess_id = clean_devops_session
    # The deploy path now refuses to create a container when the requested port is
    # already published by *another* project (it reports FAILED with the holder
    # named), which is correct on a shared host. This test is about a clean session's
    # deploy result -- building when the daemon is reachable, DOCKER_UNAVAILABLE when
    # it is not -- so the host's port occupancy must not decide its outcome. The
    # conflict rule itself is covered by test_qe_deployment_identity.py.
    import app.services.docker_service as docker_service

    monkeypatch.setattr(docker_service, "_port_holder", lambda host_port: None)

    # Deploy will either start building (if Docker is present) or return DOCKER_UNAVAILABLE (if Docker is absent)
    response = client.post(f"/api/v1/devops/{sess_id}/deploy", json={"hostPort": 8080})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["sessionId"] == sess_id
    assert data["status"] in ["BUILDING", "RUNNING", "HEALTHY", "DOCKER_UNAVAILABLE"]


def test_devops_status_endpoint(clean_devops_session):
    sess_id = clean_devops_session
    response = client.get(f"/api/v1/devops/{sess_id}/status")
    assert response.status_code == 200
    data = response.json()
    assert data["sessionId"] == sess_id


def test_devops_logs_stream_endpoint(clean_devops_session):
    sess_id = clean_devops_session
    response = client.get(f"/api/v1/devops/{sess_id}/logs/stream")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
