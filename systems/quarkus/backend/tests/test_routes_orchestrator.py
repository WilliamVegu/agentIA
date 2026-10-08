import json
import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from app.main import app
from app.config import settings
from app.models.session import GenerationSessionDB, SessionLocal, SessionPhase, SessionStatus
from app.models.orchestrator import LifecyclePhase


@pytest.fixture
def client_with_session(tmp_path, monkeypatch):
    client = TestClient(app)
    session_id = "test-orch-route-sess"
    ws_path = tmp_path / session_id
    ws_path.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(settings, "WORKSPACE_DIR", str(tmp_path))

    db = SessionLocal()
    db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).delete()
    sess = GenerationSessionDB(
        id=session_id,
        spec_id="spec-test",
        spec_name="PaymentService",
        status=SessionStatus.QUEUED,
        phase=SessionPhase.INITIALIZATION,
        current_lifecycle_phase="INITIAL",
        lifecycle_mode="GUIDED_STEP",
    )
    db.add(sess)
    db.commit()
    db.close()

    yield client, session_id, ws_path

    from app.services.pipeline_runner import _active_threads
    thread=_active_threads.get(session_id)
    if thread: thread.join(timeout=10)
    assert not thread or not thread.is_alive()
    db = SessionLocal()
    db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).delete()
    db.commit()
    db.close()


def test_get_lifecycle_endpoint(client_with_session):
    client, session_id, ws_path = client_with_session
    resp = client.get(f"/api/v1/orchestrator/sessions/{session_id}/lifecycle")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sessionId"] == session_id
    assert "completionPercentage" in data
    assert len(data["phases"]) == 7


def test_transition_phase_endpoint(client_with_session):
    client, session_id, ws_path = client_with_session

    # Creating spec.md to satisfy phase 1
    (ws_path / "spec.md").write_text("# Payment Service Spec", encoding="utf-8")

    # Transitioning to STORIES should succeed
    resp = client.post(
        f"/api/v1/orchestrator/sessions/{session_id}/transition",
        json={"targetPhase": "STORIES", "force": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["currentPhase"] == "STORIES"

    # Transitioning prematurely to DEVOPS_DEPLOY should return 400
    fail_resp = client.post(
        f"/api/v1/orchestrator/sessions/{session_id}/transition",
        json={"targetPhase": "DEVOPS_DEPLOY", "force": False},
    )
    assert fail_resp.status_code == 400


def test_get_overview_endpoint(client_with_session):
    client, session_id, ws_path = client_with_session
    (ws_path / "spec.md").write_text("# Spec", encoding="utf-8")
    (ws_path / "user_stories.json").write_text(json.dumps([{"id": "US1"}]), encoding="utf-8")

    resp = client.get(f"/api/v1/orchestrator/sessions/{session_id}/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sessionId"] == session_id
    assert data["specName"] == "PaymentService"
    assert data["userStoriesCount"] == 1


def test_pipeline_run_and_pause_endpoints(client_with_session,monkeypatch):
    import threading
    from app.services import pipeline_runner
    from app.services.operation_repository import get_operation
    client,session_id,ws_path=client_with_session
    reached=threading.Event()
    def controlled_steps(sid,*args):
        reached.set()
        assert pipeline_runner._pause_events[sid].wait(timeout=5)
    monkeypatch.setattr(pipeline_runner,'_execute_pipeline_steps',controlled_steps)
    resp=client.post('/api/v1/orchestrator/pipeline/run',json={'sessionId':session_id,'provider':'mock','targetPhase':'CODE_TESTS','stopOnGate':True})
    assert resp.status_code==202
    assert reached.wait(timeout=5)
    pause=client.post(f'/api/v1/orchestrator/pipeline/{session_id}/pause')
    assert pause.status_code==200
    assert pause.json()['status']=='PAUSE_REQUESTED'
    pipeline_runner._active_threads[session_id].join(timeout=5)
    assert get_operation(session_id)['state']=='PAUSED'
    assert get_operation(session_id)['targetPhase']=='CODE_TESTS'


def test_export_bundle_endpoint(client_with_session):
    client, session_id, ws_path = client_with_session
    (ws_path / "spec.md").write_text("# Spec Content", encoding="utf-8")
    (ws_path / "docker-compose.yml").write_text("version: '3.8'", encoding="utf-8")

    resp = client.get(f"/api/v1/orchestrator/sessions/{session_id}/export-bundle")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert len(resp.content) > 0


def test_pipeline_run_with_new_session():
    client = TestClient(app)
    resp = client.post(
        "/api/v1/orchestrator/pipeline/run",
        json={"sessionId": "new", "provider": "mock", "targetPhase": "DEVOPS_DEPLOY", "stopOnGate": True},
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["sessionId"] != "new"
    assert len(data["sessionId"]) > 10
    assert data["status"] == "RUNNING"

    from app.services.pipeline_runner import _active_threads
    _active_threads[data['sessionId']].join(timeout=10)
    assert not _active_threads[data['sessionId']].is_alive()
    # Cleanup created session
    db = SessionLocal()
    try:
        db.query(GenerationSessionDB).filter(GenerationSessionDB.id == data["sessionId"]).delete()
        db.commit()
    finally:
        db.close()


def test_invalidation_without_built_artifacts_does_not_invent_stale_phases(client_with_session):
    client,session_id,ws_path=client_with_session
    response=client.post(f'/api/v1/orchestrator/sessions/{session_id}/invalidate',json={'modifiedPhase':'STORIES'})
    assert response.status_code==200
    assert response.json()['outdatedPhases']==[]
    assert client.get(f'/api/v1/orchestrator/sessions/{session_id}/lifecycle').json()['isOutdated'] is False


def test_pipeline_cancel_endpoints(client_with_session):
    from app.services.operation_repository import begin_operation,transition_operation,get_operation
    client,session_id,ws_path=client_with_session
    assert client.post(f'/api/v1/orchestrator/pipeline/{session_id}/cancel').status_code==409
    operation=begin_operation(session_id,'CODE_TESTS')
    response=client.post(f'/api/v1/orchestrator/pipeline/{session_id}/cancel')
    assert response.status_code==200
    assert response.json()['status']=='CANCEL_REQUESTED'
    requested=get_operation(session_id)
    assert requested['state']=='CANCEL_REQUESTED'
    transition_operation(operation['operationId'],requested['version'],'CANCELLED')
    repeat=client.post('/api/v1/orchestrator/pipeline/cancel',json={'sessionId':session_id})
    assert repeat.status_code==409
    assert get_operation(session_id)['state']=='CANCELLED'
