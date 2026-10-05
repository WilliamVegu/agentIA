import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.models.session import GenerationSessionDB, SessionStatus, SessionPhase, SessionLocal

client = TestClient(app)

@pytest.fixture
def mock_export_session():
    session_id = "test-export-session-001"
    ws_path = Path(settings.WORKSPACE_DIR) / session_id
    ws_path.mkdir(parents=True, exist_ok=True)

    from scripts.local_microservice_fixture import create_fixture
    from app.services.verification_policy import workspace_fingerprint
    import json
    create_fixture(ws_path, assets=False)

    db = SessionLocal()
    try:
        sess = GenerationSessionDB(
            id=session_id,
            spec_id="dummy-spec",
            spec_name="order-service",
            status=SessionStatus.COMPLETED,
            phase=SessionPhase.TEST_SYNTHESIS,
            repair_attempts=0,
            verification_metrics_json=json.dumps({'verificationSkipped': True, 'allPassed': False,
                'workspaceFingerprint': workspace_fingerprint(ws_path)})
        )
        db.merge(sess)
        db.commit()
    finally:
        db.close()

    yield session_id

def test_export_zip(mock_export_session):
    sess_id = mock_export_session
    response = client.get(f"/api/v1/sessions/{sess_id}/export")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "order-service.zip" in response.headers["content-disposition"]
    assert len(response.content) > 0

def test_export_zip_not_found():
    response = client.get("/api/v1/sessions/non-existent-session/export")
    assert response.status_code == 404

