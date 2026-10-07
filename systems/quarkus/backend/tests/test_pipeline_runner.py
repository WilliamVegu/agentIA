import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.models.orchestrator import LifecyclePhase, PhaseStatus, PipelineRunStatus
from app.models.session import GenerationSessionDB, SessionLocal, SessionPhase, SessionStatus
from app.services.pipeline_runner import (
    _execute_pipeline_steps,
    _pause_events,
    _pipeline_statuses,
    _stop_events,
    get_pipeline_status,
    pause_pipeline,
    run_pipeline,
)


@pytest.fixture
def runner_session(tmp_path, monkeypatch):
    session_id = "test-runner-sess"
    ws_path = tmp_path / session_id
    ws_path.mkdir(parents=True, exist_ok=True)

    from app.config import settings
    monkeypatch.setattr(settings, "WORKSPACE_DIR", str(tmp_path))

    db = SessionLocal()
    db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).delete()
    sess = GenerationSessionDB(
        id=session_id,
        spec_id="spec-runner",
        spec_name="InventoryService",
        status=SessionStatus.QUEUED,
        phase=SessionPhase.INITIALIZATION,
        current_lifecycle_phase="INITIAL",
        lifecycle_mode="AUTO_PILOT",
    )
    db.add(sess)
    db.commit()
    db.close()

    yield session_id, ws_path

    db = SessionLocal()
    db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).delete()
    db.commit()
    db.close()


def test_pipeline_runner_full_run(runner_session):
    session_id, ws_path = runner_session
    import threading
    _pause_events[session_id] = threading.Event()
    _stop_events[session_id] = threading.Event()

    # Execute all steps
    _execute_pipeline_steps(session_id, LifecyclePhase.DEVOPS_DEPLOY, stop_on_gate=True, auto_deploy=False)

    assert (ws_path / "spec.md").exists()
    assert (ws_path / "user_stories.json").exists()
    assert (ws_path / "architecture.json").exists()
    assert (ws_path / "architecture.md").exists()
    assert (ws_path / "schema.sql").exists()
    assert (ws_path / "pom.xml").exists()
    assert (ws_path / "src" / "main" / "java").exists()
    assert (ws_path / "src" / "test" / "java").exists()
    assert len(list((ws_path / "src").glob("**/*.java"))) >= 4
    assert (ws_path / "docker-compose.yml").exists()
    assert (ws_path / "Dockerfile").exists()
    assert _pipeline_statuses.get(session_id) == PipelineRunStatus.COMPLETED


def test_pipeline_runner_hot_pause(runner_session):
    session_id, ws_path = runner_session
    import threading
    _pause_events[session_id] = threading.Event()
    _stop_events[session_id] = threading.Event()

    # Signal pause immediately before start
    _pause_events[session_id].set()

    _execute_pipeline_steps(session_id, LifecyclePhase.DEVOPS_DEPLOY, stop_on_gate=True, auto_deploy=False)

    assert _pipeline_statuses.get(session_id) == PipelineRunStatus.PAUSED
    # Step 3 and later should not be created
    assert not (ws_path / "docker-compose.yml").exists()


def test_pipeline_runner_quality_gate_block(runner_session, monkeypatch):
    session_id, ws_path = runner_session
    import threading
    _pause_events[session_id] = threading.Event()
    _stop_events[session_id] = threading.Event()

    # Mock audit_workspace to return a BLOCKED quality gate
    mock_audit = MagicMock()
    mock_audit.qualityGate.status = "BLOCKED"
    mock_audit.qualityGate.summaryMessage = "Hardcoded password found in configuration"

    import app.services.pipeline_runner as pr
    monkeypatch.setattr(pr, "audit_workspace", lambda *args, **kwargs: mock_audit)

    _execute_pipeline_steps(session_id, LifecyclePhase.DEVOPS_DEPLOY, stop_on_gate=True, auto_deploy=False)

    assert _pipeline_statuses.get(session_id) == PipelineRunStatus.AWAITING_INTERVENTION
    # DevOps assets should NOT be created due to block
    assert not (ws_path / "docker-compose.yml").exists()

