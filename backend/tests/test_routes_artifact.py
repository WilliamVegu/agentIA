import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.models.session import GenerationSessionDB, SessionStatus, SessionPhase, SessionLocal

client = TestClient(app)

@pytest.fixture
def mock_session_with_artifacts():
    session_id = "test-artifact-session-001"
    ws_path = Path(settings.WORKSPACE_DIR) / session_id
    ws_path.mkdir(parents=True, exist_ok=True)

    # Create dummy files
    pom_file = ws_path / "pom.xml"
    pom_file.write_text("<project></project>", encoding="utf-8")

    java_file = ws_path / "src" / "main" / "java" / "com" / "corp" / "Order.java"
    java_file.parent.mkdir(parents=True, exist_ok=True)
    java_file.write_text("public class Order {}", encoding="utf-8")

    test_file = ws_path / "src" / "test" / "java" / "com" / "corp" / "OrderTest.java"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("public class OrderTest {}", encoding="utf-8")

    # Insert DB record
    db = SessionLocal()
    try:
        sess = GenerationSessionDB(
            id=session_id,
            spec_id="dummy-spec",
            spec_name="order-service",
            status=SessionStatus.COMPLETED,
            phase=SessionPhase.VERIFIED,
            repair_attempts=0
        )
        db.merge(sess)
        db.commit()
    finally:
        db.close()

    yield session_id

def test_list_artifacts(mock_session_with_artifacts):
    sess_id = mock_session_with_artifacts
    response = client.get(f"/api/v1/sessions/{sess_id}/artifacts")
    assert response.status_code == 200
    artifacts = response.json()
    assert len(artifacts) >= 3
    rel_paths = [a["relativePath"] for a in artifacts]
    assert "pom.xml" in rel_paths
    assert any("Order.java" in p for p in rel_paths)
    assert any("OrderTest.java" in p for p in rel_paths)

def test_get_artifact_content(mock_session_with_artifacts):
    sess_id = mock_session_with_artifacts
    response = client.get(
        f"/api/v1/sessions/{sess_id}/artifacts/content",
        params={"path": "pom.xml"}
    )
    assert response.status_code == 200
    assert "<project></project>" in response.text

def test_get_artifact_content_not_found(mock_session_with_artifacts):
    sess_id = mock_session_with_artifacts
    response = client.get(
        f"/api/v1/sessions/{sess_id}/artifacts/content",
        params={"path": "non_existent.java"}
    )
    assert response.status_code == 404

