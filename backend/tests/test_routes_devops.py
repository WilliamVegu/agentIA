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

    from scripts.local_microservice_fixture import create_fixture
    create_fixture(ws_path, database='POSTGRESQL', identity=session_id)

    db = SessionLocal()
    try:
        sess = GenerationSessionDB(
            id=session_id,
            spec_id="dummy-spec",
            spec_name="order-service",
            database_engine="POSTGRESQL",
            execution_mode="DOCKER",
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
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["sessionId"] == sess_id
    assert data["serviceName"] == "order-service"
    assert data["databaseEngine"] == "POSTGRESQL"
    assert "agentia-runtime:21-v1" in data["dockerfileContent"]
    assert "postgres:16.4-alpine" in data["dockerComposeContent"]
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


def test_source_mode_skips_deploy_even_when_source_audit_would_block(blocked_devops_session):
    sess_id = blocked_devops_session
    response = client.post(f"/api/v1/devops/{sess_id}/deploy")
    assert response.status_code == 200
    assert response.json()['status'] == 'SKIPPED_BY_CHOICE'


def test_deploy_devops_clean_session_behavior(clean_devops_session):
    sess_id = clean_devops_session
    from app.models.execution import ExecutionMode
    with SessionLocal() as db:
        db.get(GenerationSessionDB, sess_id).execution_mode = ExecutionMode.SOURCE_ONLY
        db.commit()
    # Default source mode never starts Docker, regardless of this host's daemon.
    response = client.post(f"/api/v1/devops/{sess_id}/deploy", json={"hostPort": 8080})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["sessionId"] == sess_id
    assert data["status"] == "SKIPPED_BY_CHOICE"


def test_devops_status_endpoint(clean_devops_session):
    sess_id = clean_devops_session
    response = client.get(f"/api/v1/devops/{sess_id}/status")
    assert response.status_code == 200
    data = response.json()
    assert data["sessionId"] == sess_id


def test_devops_logs_stream_endpoint(clean_devops_session, monkeypatch):
    # Bound the streaming transport; unbounded TestClient.get cannot return.
    from app.api import routes_devops
    monkeypatch.setattr(routes_devops, 'stream_logs', lambda *args, **kwargs: iter([': keep-alive\n\n']))
    sess_id = clean_devops_session
    response = client.get(f"/api/v1/devops/{sess_id}/logs/stream")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
