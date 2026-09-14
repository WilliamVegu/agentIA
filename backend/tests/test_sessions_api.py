import uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.config import settings
from app.models.session import GenerationSessionDB, SessionLocal, SessionStatus, SessionPhase

client = TestClient(app)


def test_list_sessions_endpoint():
    db = SessionLocal()
    sess_id1 = str(uuid.uuid4())
    sess_id2 = str(uuid.uuid4())
    try:
        s1 = GenerationSessionDB(
            id=sess_id1,
            spec_id=str(uuid.uuid4()),
            spec_name="order-service",
            status=SessionStatus.QUEUED,
            phase=SessionPhase.INITIALIZATION,
            current_lifecycle_phase="REQUIREMENTS",
            lifecycle_mode="GUIDED_STEP",
            created_at=datetime.now(timezone.utc),
        )
        s2 = GenerationSessionDB(
            id=sess_id2,
            spec_id=str(uuid.uuid4()),
            spec_name="payment-service",
            status=SessionStatus.COMPLETED,
            phase=SessionPhase.VERIFIED,
            current_lifecycle_phase="COMPLETED",
            lifecycle_mode="AUTO_PILOT",
            created_at=datetime.now(timezone.utc),
        )
        db.add_all([s1, s2])
        db.commit()

        resp = client.get("/api/v1/sessions?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2
        
        found_ids = [s["sessionId"] for s in data]
        assert sess_id1 in found_ids
        assert sess_id2 in found_ids
    finally:
        db.query(GenerationSessionDB).filter(GenerationSessionDB.id.in_([sess_id1, sess_id2])).delete()
        db.commit()
        db.close()


def test_quick_start_session_endpoint():
    payload = {
        "serviceName": "inventory-service",
        "rawText": "Manage stock levels, warehouse items, and low-inventory reorder alerts.",
        "databaseEngine": "POSTGRESQL",
    }
    resp = client.post("/api/v1/sessions/quick-start", json=payload)
    assert resp.status_code == 201
    data = resp.json()

    assert "sessionId" in data
    assert data["specName"] == "inventory-service"
    assert data["status"] == "QUEUED"
    assert data["currentLifecyclePhase"] == "REQUIREMENTS"
    assert data["lifecycleMode"] == "GUIDED_STEP"

    sess_id = data["sessionId"]
    ws_path = Path(settings.WORKSPACE_DIR) / sess_id
    assert ws_path.exists()
    spec_file = ws_path / "spec.md"
    assert spec_file.exists()
    content = spec_file.read_text(encoding="utf-8")
    assert "inventory-service" in content
    assert "Manage stock levels" in content

    # Cleanup DB
    db = SessionLocal()
    try:
        db.query(GenerationSessionDB).filter(GenerationSessionDB.id == sess_id).delete()
        db.commit()
    finally:
        db.close()


def test_quick_start_session_default_name():
    resp = client.post("/api/v1/sessions/quick-start", json={})
    assert resp.status_code == 201
    data = resp.json()
    assert data["specName"] == "app-service"

    sess_id = data["sessionId"]
    db = SessionLocal()
    try:
        db.query(GenerationSessionDB).filter(GenerationSessionDB.id == sess_id).delete()
        db.commit()
    finally:
        db.close()


def test_quick_start_session_with_auto_run():
    payload = {
        "specName": "order-service",
        "prompt": "Order management service with payments",
        "databaseEngine": "MYSQL",
        "autoRun": True,
        "apiKey": "mock-key",
        "llmProvider": "mock",
    }
    resp = client.post("/api/v1/sessions/quick-start", json=payload)
    assert resp.status_code == 201
    data = resp.json()

    assert "sessionId" in data
    assert data["specName"] == "order-service"
    assert data["status"] == "QUEUED"
    assert data["lifecycleMode"] == "AUTO_PILOT"
    assert data["pipelineStarted"] is True

    sess_id = data["sessionId"]
    db = SessionLocal()
    try:
        db.query(GenerationSessionDB).filter(GenerationSessionDB.id == sess_id).delete()
        db.commit()
    finally:
        db.close()
