import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.models.orchestrator import (
    LifecyclePhase,
    PhaseStatus,
    PipelineExecutionMode,
)
from app.models.session import GenerationSessionDB, SessionLocal, SessionPhase, SessionStatus
from app.services.lifecycle_service import (
    PHASE_ORDER,
    clear_outdated_phases,
    get_project_overview,
    get_session_lifecycle,
    mark_downstream_outdated,
    transition_phase,
)


@pytest.fixture
def mock_session(tmp_path, monkeypatch):
    session_id = "test-fsm-session"
    ws_path = tmp_path / session_id
    ws_path.mkdir(parents=True, exist_ok=True)

    from app.config import settings
    monkeypatch.setattr(settings, "WORKSPACE_DIR", str(tmp_path))

    db = SessionLocal()
    # Clean up existing
    db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).delete()
    sess = GenerationSessionDB(
        id=session_id,
        spec_id="spec-fsm",
        spec_name="OrderService",
        status=SessionStatus.QUEUED,
        phase=SessionPhase.INITIALIZATION,
        current_lifecycle_phase="INITIAL",
        lifecycle_mode="GUIDED_STEP",
    )
    db.add(sess)
    db.commit()
    db.close()

    yield session_id, ws_path

    db = SessionLocal()
    db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).delete()
    db.commit()
    db.close()


def test_initial_session_lifecycle(mock_session):
    session_id, ws_path = mock_session
    lifecycle = get_session_lifecycle(session_id)

    assert lifecycle.session_id == session_id
    assert lifecycle.completion_percentage == 0.0
    assert len(lifecycle.phases) == len(PHASE_ORDER)
    assert lifecycle.phases[0].phase == LifecyclePhase.REQUIREMENTS
    assert lifecycle.phases[0].can_enter is True
    # Phase 2 cannot be entered before Phase 1 is done
    assert lifecycle.phases[1].can_enter is False
    assert lifecycle.can_advance is True


def test_prerequisite_guards_prevent_premature_transition(mock_session):
    session_id, _ = mock_session
    with pytest.raises(ValueError) as excinfo:
        transition_phase(session_id, LifecyclePhase.ARCHITECTURE, force=False)
    assert "requiere" in str(excinfo.value).lower()


def test_sequential_transitions_with_artifacts(mock_session):
    session_id, ws_path = mock_session

    # Complete phase 1: spec.md
    (ws_path / "spec.md").write_text("# Spec", encoding="utf-8")
    lifecycle = get_session_lifecycle(session_id)
    assert lifecycle.phases[0].status == PhaseStatus.COMPLETED
    assert lifecycle.phases[1].can_enter is True

    # Advance to Phase 2
    transition_phase(session_id, LifecyclePhase.STORIES)
    lifecycle = get_session_lifecycle(session_id)
    assert lifecycle.current_phase == LifecyclePhase.STORIES

    # Complete phase 2: user_stories.json
    (ws_path / "user_stories.json").write_text(json.dumps([{"id": "US1"}]), encoding="utf-8")
    lifecycle = get_session_lifecycle(session_id)
    assert lifecycle.phases[1].status == PhaseStatus.COMPLETED
    assert lifecycle.phases[2].can_enter is True

    # Complete phase 3: architecture.json
    (ws_path / "architecture.json").write_text(json.dumps({"service": "OrderService"}), encoding="utf-8")
    lifecycle = get_session_lifecycle(session_id)
    assert lifecycle.phases[2].status == PhaseStatus.COMPLETED

    # Complete phase 4: schema.sql
    (ws_path / "schema.sql").write_text("CREATE TABLE orders (id SERIAL PRIMARY KEY);", encoding="utf-8")
    lifecycle = get_session_lifecycle(session_id)
    assert lifecycle.phases[3].status == PhaseStatus.COMPLETED


def test_mark_downstream_outdated(mock_session):
    session_id, ws_path = mock_session

    # Create artifacts for all phases
    (ws_path / "spec.md").write_text("# Spec", encoding="utf-8")
    (ws_path / "user_stories.json").write_text("[]", encoding="utf-8")
    (ws_path / "architecture.json").write_text("{}", encoding="utf-8")
    (ws_path / "schema.sql").write_text("CREATE TABLE t (id INT);", encoding="utf-8")

    lifecycle = get_session_lifecycle(session_id)
    assert lifecycle.phases[0].status == PhaseStatus.COMPLETED
    assert lifecycle.phases[1].status == PhaseStatus.COMPLETED
    assert lifecycle.phases[2].status == PhaseStatus.COMPLETED
    assert lifecycle.phases[3].status == PhaseStatus.COMPLETED

    # Modify Phase 2: Stories
    mark_downstream_outdated(session_id, LifecyclePhase.STORIES)
    lifecycle = get_session_lifecycle(session_id)

    assert lifecycle.is_outdated is True
    # Stories should still be completed
    assert lifecycle.phases[1].status == PhaseStatus.COMPLETED
    # Downstream phases (Architecture, Data Model) should now be OUTDATED
    assert lifecycle.phases[2].status == PhaseStatus.OUTDATED
    assert lifecycle.phases[3].status == PhaseStatus.OUTDATED

    # Clear outdated
    clear_outdated_phases(session_id)
    lifecycle_cleared = get_session_lifecycle(session_id)
    assert lifecycle_cleared.is_outdated is False
    assert lifecycle_cleared.phases[2].status == PhaseStatus.COMPLETED


def test_project_overview_summary(mock_session):
    session_id, ws_path = mock_session
    (ws_path / "spec.md").write_text("# Spec", encoding="utf-8")
    (ws_path / "user_stories.json").write_text(json.dumps([{"id": "US1"}, {"id": "US2"}]), encoding="utf-8")
    (ws_path / "schema.sql").write_text("CREATE TABLE orders (id SERIAL PRIMARY KEY);\nCREATE TABLE items (id SERIAL);", encoding="utf-8")

    overview = get_project_overview(session_id)
    assert overview.session_id == session_id
    assert overview.spec_name == "OrderService"
    assert overview.user_stories_count == 2
    assert overview.entities_count == 2
    assert overview.database_engine == "POSTGRESQL"


def test_lifecycle_security_audit_completed_and_100_percent(mock_session):
    session_id, ws_path = mock_session
    (ws_path / "spec.md").write_text("# Spec", encoding="utf-8")
    (ws_path / "user_stories.json").write_text(json.dumps([{"id": "US1"}]), encoding="utf-8")
    (ws_path / "architecture.json").write_text("{}", encoding="utf-8")
    (ws_path / "schema.sql").write_text("CREATE TABLE test (id SERIAL);", encoding="utf-8")
    (ws_path / "pom.xml").write_text("<project></project>", encoding="utf-8")
    (ws_path / "src" / "main" / "java").mkdir(parents=True, exist_ok=True)
    (ws_path / "src" / "main" / "java" / "App.java").write_text("public class App {}", encoding="utf-8")
    (ws_path / "src" / "main" / "java" / "GlobalExceptionHandler.java").write_text("@RestControllerAdvice\npublic class GlobalExceptionHandler {}", encoding="utf-8")
    (ws_path / "docker-compose.yml").write_text("version: '3'", encoding="utf-8")

    lifecycle = get_session_lifecycle(session_id)
    # Check that security audit (Phase 6, index 5) is COMPLETED
    assert lifecycle.phases[5].status == PhaseStatus.COMPLETED
    assert lifecycle.phases[6].status == PhaseStatus.COMPLETED
    assert lifecycle.completion_percentage == 100.0
    assert "completamente sintetizado" in lifecycle.next_recommended_action
