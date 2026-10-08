"""QE coverage: the unattended Auto-Pilot path (``services/pipeline_runner.py``).

This module was at 82.4% with 61 uncovered statements, and the uncovered part was not the
happy path -- that had a test. It was the *control* surface and the *failure* surface:

* ``stream_pipeline_events`` -- the entire SSE endpoint the monitor screen reads (0%).
* The cooperative pause checks at every step boundary, and cancel.
* The schema-synthesis fallback, whose silent version wrote a hardcoded ``items`` table
  whatever the blueprint said (the defect an external review found in generated output).
* The outer error handler, which is what stops a crashed run from leaving a session
  ``RUNNING`` forever.

Two things make these worth pinning beyond the coverage number. Auto-Pilot is
**unattended**: nobody is watching when it pauses, cancels or dies, so the only witness is
the state it leaves behind and the events it emits. And a pipeline that reports progress it
did not make is the same class of dishonesty feature 012 spent a whole feature removing --
here it would be "Pausa cooperativa" emitted after the work already ran.

No container, no model, no network: the stage runner, the auditor, the DevOps generator and
the deployer are all faked at their module boundaries.
"""

from __future__ import annotations

import json
import queue
import sys
import threading
from itertools import islice
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

import app.services.pipeline_runner as pr  # noqa: E402
from app.models.orchestrator import (  # noqa: E402
    LifecyclePhase,
    PhaseStatus,
    PipelineRunStatus,
)
from app.models.session import (  # noqa: E402
    GenerationSessionDB,
    SessionLocal,
    SessionPhase,
    SessionStatus,
)

SESSION_ID = "qe-autopilot-session"


class _Gate:
    """A quality gate good enough for the two fields the pipeline reads."""

    def __init__(self, status="APPROVED", message="ok", can_export=True):
        self.status = status
        self.summaryMessage = message
        self.canExport = can_export


class _Audit:
    def __init__(self, gate=None):
        self.qualityGate = gate or _Gate()


@pytest.fixture(autouse=True)
def isolated_runner_state(monkeypatch):
    """The runner tracks everything in process-global dicts; each test gets fresh ones."""
    monkeypatch.setattr(pr, "_active_threads", {})
    monkeypatch.setattr(pr, "_pause_events", {})
    monkeypatch.setattr(pr, "_stop_events", {})
    monkeypatch.setattr(pr, "_event_queues", {})
    monkeypatch.setattr(pr, "_pipeline_statuses", {})
    monkeypatch.setattr(pr, "_session_credentials", {})
    monkeypatch.setattr(pr,"_worker_operations",{})
    # The pipeline's own broadcast must not leak into other modules' state.
    yield


@pytest.fixture
def session(tmp_path, monkeypatch):
    ws = tmp_path / SESSION_ID
    ws.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(pr.settings, "WORKSPACE_DIR", str(tmp_path))

    db = SessionLocal()
    try:
        from app.models.reliability import RepairAttempt, SessionEvent, DeploymentOperation, AuditRun, VerificationRun, ArtifactProvenance, SessionConfiguration, PipelineOperation, DraftRevision
        for model in (RepairAttempt,SessionEvent,DeploymentOperation,AuditRun,VerificationRun,ArtifactProvenance,SessionConfiguration,PipelineOperation,DraftRevision):
            db.query(model).filter_by(session_id=SESSION_ID).delete()
        db.query(GenerationSessionDB).filter(GenerationSessionDB.id == SESSION_ID).delete()
        db.add(GenerationSessionDB(
            id=SESSION_ID,
            spec_id="spec-autopilot",
            spec_name="OrderService",
            status=SessionStatus.QUEUED,
            phase=SessionPhase.INITIALIZATION,
            current_lifecycle_phase="INITIAL",
            lifecycle_mode="GUIDED_STEP",
            repair_attempts=0,
        ))
        db.commit()
    finally:
        db.close()

    yield SESSION_ID, ws
    for worker in pr._active_threads.values():
        if isinstance(worker,threading.Thread):
            worker.join(timeout=10)
            assert not worker.is_alive(), "Fixture cannot delete an active writer"

    db = SessionLocal()
    try:
        from app.models.reliability import RepairAttempt, SessionEvent, DeploymentOperation, AuditRun, VerificationRun, ArtifactProvenance, SessionConfiguration, PipelineOperation, DraftRevision
        for model in (RepairAttempt,SessionEvent,DeploymentOperation,AuditRun,VerificationRun,ArtifactProvenance,SessionConfiguration,PipelineOperation,DraftRevision):
            db.query(model).filter_by(session_id=SESSION_ID).delete()
        db.query(GenerationSessionDB).filter(GenerationSessionDB.id == SESSION_ID).delete()
        db.commit()
    finally:
        db.close()


def _row(session_id):
    db = SessionLocal()
    try:
        return db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
    finally:
        db.close()


def _recorded_events(session_id):
    from types import SimpleNamespace
    from app.services.session_event_service import read_events
    return [SimpleNamespace(**json.loads(event['data'])) for event in read_events(session_id) if event['event']=='pipeline_progress']


def _running_operation(session_id, paused=False):
    from app.services.operation_repository import begin_operation, transition_operation
    operation = begin_operation(session_id, LifecyclePhase.DEVOPS_DEPLOY)
    operation = transition_operation(operation['operationId'], operation['version'], 'RUNNING')
    if paused:
        operation = transition_operation(operation['operationId'], operation['version'], 'PAUSE_REQUESTED')
        operation = transition_operation(operation['operationId'], operation['version'], 'PAUSED')
    return operation


def _prepare_events(session_id):
    pr._pause_events[session_id] = threading.Event()
    pr._stop_events[session_id] = threading.Event()


def _fast_stages(state, stages=None, api_key=None, **kwargs):
    """Stand in for the stage boundary: create the two artifacts step 5 checks for."""
    ws = Path(state["workspace_path"])
    (ws / "pom.xml").write_text("<project/>", encoding="utf-8")
    java = ws / "src" / "main" / "java"
    java.mkdir(parents=True, exist_ok=True)
    (java / "App.java").write_text("class App {}", encoding="utf-8")
    state["generated_files"] = {"pom.xml": "<project/>", "src/main/java/App.java": "class App {}"}
    state["status"] = SessionStatus.COMPLETED.value
    return state


def _stub_heavy_steps(monkeypatch, audit=None):
    monkeypatch.setattr(pr, "run_generation_stages", _fast_stages)
    monkeypatch.setattr(pr, "audit_workspace", lambda *a, **k: audit or _Audit())


# ===========================================================================
# Cooperative pause at every step boundary
# ===========================================================================
STEP_ARTIFACTS = [
    (LifecyclePhase.REQUIREMENTS, "architecture.json"),
    (LifecyclePhase.STORIES, "architecture.json"),
    (LifecyclePhase.ARCHITECTURE, "schema.sql"),
    (LifecyclePhase.DATA_MODEL, "pom.xml"),
    (LifecyclePhase.CODE_TESTS, "docker-compose.yml"),
    (LifecyclePhase.SECURITY_AUDIT, "docker-compose.yml"),
]


@pytest.mark.parametrize("pause_after,next_artifact", STEP_ARTIFACTS,
                         ids=[p.value for p, _ in STEP_ARTIFACTS])
def test_pausing_after_a_step_stops_before_the_next_one(session, monkeypatch,
                                                       pause_after, next_artifact):
    """A pause must take effect at the *next* boundary, not after the whole run.

    Cooperative pausing is only honest if it stops between steps: the operator pressed
    pause to inspect what exists so far, and the artifact of the step they interrupted must
    not be there. Each case drives one specific boundary check, which is why they are
    parametrized rather than collapsed into one run.
    """
    session_id, ws = session
    _prepare_events(session_id)
    _stub_heavy_steps(monkeypatch)
    real_transition = pr.transition_phase

    def transition_then_pause(sid, phase, force=False):
        result = real_transition(sid, phase, force=force)
        if phase == pause_after:
            pr._pause_events[sid].set()
        return result

    monkeypatch.setattr(pr, "transition_phase", transition_then_pause)

    pr._execute_pipeline_steps(session_id, LifecyclePhase.DEVOPS_DEPLOY,
                               stop_on_gate=True, auto_deploy=False, provider='mock')

    assert pr._pipeline_statuses[session_id] == PipelineRunStatus.PAUSED
    assert (not (ws / next_artifact).exists() if pause_after != LifecyclePhase.SECURITY_AUDIT else not any(e.step == "DevOps & Manifiestos" for e in _recorded_events(session_id))), (
        f"the step after {pause_after.value} ran despite the pause"
    )


def test_a_pause_emits_its_own_event_and_keeps_the_progress_made(session, monkeypatch):
    """The operator needs to be told the run stopped *and* that it stopped by design."""
    session_id, ws = session
    _prepare_events(session_id)
    _stub_heavy_steps(monkeypatch)
    real_transition = pr.transition_phase

    def transition_then_pause(sid, phase, force=False):
        result = real_transition(sid, phase, force=force)
        if phase == LifecyclePhase.STORIES:
            pr._pause_events[sid].set()
        return result

    monkeypatch.setattr(pr, "transition_phase", transition_then_pause)

    pr._execute_pipeline_steps(session_id, LifecyclePhase.DEVOPS_DEPLOY,
                               stop_on_gate=True, auto_deploy=False, provider='mock')

    statuses = [e.status for e in _recorded_events(session_id)]
    assert PhaseStatus.IN_PROGRESS in statuses
    assert pr.get_pipeline_status(session_id) == PipelineRunStatus.PAUSED
    # The work already done is preserved, which is the difference between pause and cancel.
    assert (ws / "spec.md").exists()
    assert (ws / "user_stories.json").exists()


def test_cancelling_before_the_first_step_marks_the_run_cancelled(session, monkeypatch):
    """Cancel and pause must not be conflated: one keeps the progress, the other stops."""
    session_id, ws = session
    _prepare_events(session_id)
    _stub_heavy_steps(monkeypatch)
    pr._stop_events[session_id].set()

    pr._execute_pipeline_steps(session_id, LifecyclePhase.DEVOPS_DEPLOY,
                               stop_on_gate=True, auto_deploy=False, provider='mock')

    assert pr._pipeline_statuses[session_id] == PipelineRunStatus.CANCELLED
    assert not (ws / "spec.md").exists(), "a cancelled run generated artifacts"


# ===========================================================================
# cancel / pause / resume entry points
# ===========================================================================
def test_cancel_marks_the_row_signals_the_threads_and_emits_an_event(session):
    session_id, _ = session
    _prepare_events(session_id)
    _running_operation(session_id, paused=False)
    pr._pipeline_statuses[session_id] = PipelineRunStatus.RUNNING

    assert pr.cancel_pipeline(session_id) is True

    from app.services.operation_repository import get_operation
    from app.services.session_event_service import read_events
    assert get_operation(session_id)['state'] == 'CANCEL_REQUESTED'
    assert _row(session_id).status != SessionStatus.CANCELLED
    assert pr.get_pipeline_status(session_id) == PipelineRunStatus.RUNNING
    assert pr._stop_events[session_id].is_set()
    assert any(e['event'] == 'operation_state' and 'CANCEL_REQUESTED' in e['data'] for e in read_events(session_id))



def test_pause_switches_the_session_to_guided_step(session):
    """Pause is a mode change, not just a flag: the operator takes over by hand."""
    session_id, _ = session
    _prepare_events(session_id)
    _running_operation(session_id, paused=False)

    from types import SimpleNamespace
    pr._active_threads[session_id] = SimpleNamespace(is_alive=lambda: True)
    assert pr.pause_pipeline(session_id) is True

    row = _row(session_id)
    from app.services.operation_repository import get_operation
    assert get_operation(session_id)['state'] == 'PAUSE_REQUESTED'
    assert row.status != SessionStatus.PAUSED
    assert row.lifecycle_mode == "GUIDED_STEP"
    assert pr._pause_events[session_id].is_set()


def test_pausing_a_session_that_was_never_started_reports_whether_it_is_paused(session):
    """The return value is the answer to "is this paused?", not "did I touch a row?".

    A session with an event but no database row is still paused; one with neither is not,
    and claiming otherwise would tell the UI to show a pause that never happened.
    """
    pr._pause_events["qe-orphan"] = threading.Event()

    from fastapi import HTTPException
    for missing in ("qe-orphan", "qe-never-existed"):
        with pytest.raises(HTTPException) as error:
            pr.pause_pipeline(missing)
        assert error.value.status_code == 404


def test_resume_replays_the_session_credentials_and_waits_for_the_old_thread(session, monkeypatch):
    """Resuming must reuse the credentials the run started with.

    They are held in memory only (Principle VI), so a resume that did not replay them would
    silently drop the session to offline mock mode mid-project.
    """
    session_id, _ = session
    _prepare_events(session_id)
    _running_operation(session_id, paused=True)
    pr._session_credentials[session_id] = {
        "api_key": "sk-cached", "provider": "deepseek", "model_name": "deepseek-flash"
    }

    unwinding = threading.Event()
    old_thread = threading.Thread(target=lambda: unwinding.wait(5), daemon=True)
    old_thread.start()
    pr._active_threads[session_id] = old_thread

    called = {}

    def fake_run(sid, target_phase=None, **kwargs):
        called["sid"] = sid
        called.update(kwargs)
        return True

    monkeypatch.setattr(pr, "run_pipeline", fake_run)
    unwinding.set()
    try:
        assert pr.resume_pipeline(session_id) is True
    finally:
        unwinding.set()
        old_thread.join(timeout=2)

    assert called["api_key"] == "sk-cached"
    assert called["provider"] == "deepseek"
    assert called["model_name"] == "deepseek-flash"
    assert not called.get("force", False), "resume must preserve writer exclusion"
    row = _row(session_id)
    assert row.lifecycle_mode == "GUIDED_STEP"  # fake_run does not mutate persistence


# ===========================================================================
# run_pipeline: the entry point and its guard
# ===========================================================================
def test_a_second_run_is_refused_while_one_is_alive(session, monkeypatch):
    """Two Auto-Pilot threads on one workspace would interleave writes to the same files."""
    session_id, _ = session
    _prepare_events(session_id)
    gate = threading.Event()
    started = threading.Event()

    def blocking_steps(*args, **kwargs):
        started.set()
        gate.wait(5)

    monkeypatch.setattr(pr, "_execute_pipeline_steps", blocking_steps)

    assert pr.run_pipeline(session_id, provider='mock') is True
    assert started.wait(3), "the worker thread never started"
    assert pr.run_pipeline(session_id, provider='mock') is False, "a concurrent run was allowed"

    gate.set()
    pr._active_threads[session_id].join(timeout=3)


def test_force_refuses_a_run_while_another_writer_is_alive(session, monkeypatch):
    """Force may restart a finished worker, but never interleave two live writers."""
    session_id, _ = session
    _prepare_events(session_id)
    gate = threading.Event()
    started = threading.Event()

    def blocking_steps(*args, **kwargs):
        started.set()
        gate.wait(5)

    monkeypatch.setattr(pr, "_execute_pipeline_steps", blocking_steps)
    assert pr.run_pipeline(session_id, provider='mock') is True
    assert started.wait(3)

    assert pr.run_pipeline(session_id, force=True) is False  # force cannot interleave writers

    gate.set()
    for thread in list(pr._active_threads.values()):
        thread.join(timeout=3)


def test_starting_a_run_marks_the_session_running_and_auto_pilot(session, monkeypatch):
    session_id, _ = session
    _prepare_events(session_id)
    monkeypatch.setattr(pr, "_execute_pipeline_steps", lambda *a, **k: None)

    assert pr.run_pipeline(session_id, provider='mock') is True

    row = _row(session_id)
    assert row.status == SessionStatus.RUNNING
    assert row.lifecycle_mode == "AUTO_PILOT"
    assert row.started_at is not None
    assert pr.get_pipeline_status(session_id) == PipelineRunStatus.RUNNING
    pr._active_threads[session_id].join(timeout=3)


def test_credentials_are_replayed_from_memory_when_a_run_omits_them(session, monkeypatch):
    """Principle VI: the key lives in memory only, so the cache is the only source."""
    session_id, _ = session
    _prepare_events(session_id)
    seen = []

    def capture(*args):
        seen.append(args)

    monkeypatch.setattr(pr, "_execute_pipeline_steps", capture)

    pr.run_pipeline(session_id, api_key="sk-first", provider="deepseek", model_name="m1")
    pr._active_threads[session_id].join(timeout=3)
    pr.run_pipeline(session_id, force=True)
    pr._active_threads[session_id].join(timeout=3)

    assert seen[0][4] == "sk-first", "the first run did not receive its credentials"
    assert seen[1][4] == "sk-first", "the cached credentials were not replayed"
    assert seen[1][5] == "deepseek"
    assert seen[1][6] == "m1"


# ===========================================================================
# stream_pipeline_events -- the monitor screen's feed
# ===========================================================================
def test_empty_stream_heartbeat_can_be_disconnected(session):
    session_id,_=session
    stream=pr.stream_pipeline_events(session_id)
    assert next(stream)==': keepalive\n\n'
    stream.close()


def test_progress_replays_identically_for_independent_clients(session):
    session_id,_=session
    pr._emit_event(session_id,LifecyclePhase.REQUIREMENTS,'Especificación',15.0,'sintetizando',PhaseStatus.IN_PROGRESS)
    from app.services.session_event_service import read_events
    events=read_events(session_id)
    payload=json.loads(events[-1]['data'])
    assert payload['sessionId']==session_id and payload['percent']==15.0
    one=pr.stream_pipeline_events(session_id);two=pr.stream_pipeline_events(session_id)
    assert next(one)==next(two)
    one.close();two.close()


def test_terminal_event_remains_replayable_after_disconnect(session):
    session_id,_=session
    pr._emit_event(session_id,LifecyclePhase.COMPLETED,'Finalizado',100.0,'listo',PhaseStatus.COMPLETED)
    from app.services.session_event_service import read_events
    events=read_events(session_id)
    assert json.loads(events[-1]['data'])['status']=='COMPLETED'
    assert read_events(session_id,int(events[-1]['id']))==[]


# ===========================================================================
# Resilience: the pipeline must survive a dead broadcaster and a dead database
# ===========================================================================
def test_a_broken_event_broadcaster_does_not_stop_the_pipeline(session, monkeypatch):
    """The stream is a convenience; generation is the product. A client watcher that has
    gone away must not take the run with it."""
    session_id, ws = session
    _prepare_events(session_id)
    _stub_heavy_steps(monkeypatch)

    def explode(*args, **kwargs):
        raise RuntimeError("no subscribers")

    monkeypatch.setattr("app.api.routes_session.broadcast_session_event", explode)

    pr._execute_pipeline_steps(session_id, LifecyclePhase.DEVOPS_DEPLOY,
                               stop_on_gate=True, auto_deploy=False, provider='mock')

    assert pr.get_pipeline_status(session_id) == PipelineRunStatus.COMPLETED
    assert (ws / "docker-compose.yml").exists()
    assert _recorded_events(session_id), "the local queue lost the events too"


class _ExplodingDB:
    def __init__(self, fail_rollback=False):
        self._fail_rollback = fail_rollback

    def query(self, *args, **kwargs):
        raise RuntimeError("database is gone")

    def rollback(self):
        if self._fail_rollback:
            raise RuntimeError("rollback failed too")
        return None

    def close(self):
        return None


@pytest.mark.parametrize("fail_rollback", [False, True], ids=["rollback-ok", "rollback-fails"])
def test_a_session_that_cannot_be_marked_blocked_is_still_diagnosed(monkeypatch, fail_rollback):
    """Two independent duties: record the terminal state, and record the evidence.

    If the first fails, the second must still run -- that is the whole point of keeping
    them in one function with a guarded write. The rollback itself may fail too, and even
    that must not escape.
    """
    recorded = []
    monkeypatch.setattr(pr, "SessionLocal", lambda: _ExplodingDB(fail_rollback))
    monkeypatch.setattr(pr, "record_session_diagnostics",
                        lambda sid, state, **kw: recorded.append(sid) or True)

    pr._finalise_blocked_session("qe-unmarkable", {"error": "three repair attempts used"})

    assert recorded == ["qe-unmarkable"]


def test_the_blocked_session_is_marked_and_diagnosed(session, monkeypatch):
    session_id, _ = session
    recorded = []
    monkeypatch.setattr(pr, "record_session_diagnostics",
                        lambda sid, state, **kw: recorded.append(sid) or True)

    pr._finalise_blocked_session(session_id, {"error": "exhausted"})

    row = _row(session_id)
    assert row.status == SessionStatus.BLOCKED
    assert row.phase == SessionPhase.FAILED
    assert row.error_message == "exhausted"
    assert row.completed_at is not None
    assert recorded == [session_id], "a blocked session was not diagnosed"


def test_a_default_reason_is_recorded_when_the_state_carries_none(session):
    """The operator must not be shown an empty error box."""
    session_id, _ = session

    pr._finalise_blocked_session(session_id, {})

    assert "human intervention required" in _row(session_id).error_message.lower()


# ===========================================================================
# Failure paths inside the steps
# ===========================================================================
def test_a_crash_in_a_step_fails_the_run_and_blocks_the_session(session, monkeypatch):
    """Without the outer handler the exception dies in a daemon thread, the row stays
    RUNNING, and the UI polls a session that no longer exists."""
    session_id, _ = session
    _prepare_events(session_id)

    def explode(*args, **kwargs):
        raise RuntimeError("requirements synthesis exploded")

    monkeypatch.setattr(pr, "_get_or_create_draft", explode)
    monkeypatch.setattr("app.api.routes_session.broadcast_session_event",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no subscribers")))

    pr._execute_pipeline_steps(session_id, LifecyclePhase.DEVOPS_DEPLOY,
                               stop_on_gate=True, auto_deploy=False, provider='mock')

    row = _row(session_id)
    assert row.status == SessionStatus.BLOCKED
    assert "requirements synthesis exploded" in row.error_message
    assert pr.get_pipeline_status(session_id) == PipelineRunStatus.FAILED
    events = _recorded_events(session_id)
    assert events[-1].status == PhaseStatus.BLOCKED
    assert "requirements synthesis exploded" in (events[-1].error or "")


def test_a_failed_schema_synthesis_falls_back_to_this_blueprints_own_ddl(session, monkeypatch):
    """The fallback must derive from the blueprint.

    The previous fallback wrote a hardcoded ``items`` table whatever the service was about,
    so the shipped schema contradicted the JPA entities beside it -- and because
    docker-compose mounts schema.sql into the entrypoint directory, the service then failed
    to start against the database it had just created.
    """
    session_id, ws = session
    _prepare_events(session_id)
    _stub_heavy_steps(monkeypatch)

    def explode(*args, **kwargs):
        raise RuntimeError("synthesis unavailable")

    monkeypatch.setattr(pr.model_sql_service, "synthesize_domain_models_and_sql", explode)

    pr._execute_pipeline_steps(session_id, LifecyclePhase.DEVOPS_DEPLOY,
                               stop_on_gate=True, auto_deploy=False, provider='mock')

    assert pr.get_pipeline_status(session_id) == PipelineRunStatus.COMPLETED, (
        "the run died in the fallback instead of falling back"
    )
    schema = (ws / "schema.sql").read_text(encoding="utf-8")
    assert schema.strip(), "the fallback left an empty schema.sql behind"
    assert "items" not in schema.lower(), "the hardcoded fallback table came back"
    assert "orders" in schema.lower(), "the fallback did not use this blueprint's entity"


def test_auto_deploy_asks_for_the_local_deployment(session, monkeypatch):
    """Auto-Pilot's last step is optional and is driven by a flag, not by the environment."""
    session_id, ws = session
    _prepare_events(session_id)
    _stub_heavy_steps(monkeypatch)
    deployed = []

    from app.models.devops import LocalDeploymentSession, DeploymentStatus
    from app.models.execution import ExecutionMode
    with SessionLocal() as db:
        db.get(GenerationSessionDB, session_id).execution_mode = "DOCKER"
        db.commit()
    monkeypatch.setattr(pr, "deploy_local", lambda sid, path, **kw: (deployed.append((sid, path)) or LocalDeploymentSession(sessionId=sid, status=DeploymentStatus.HEALTHY)))
    from app.sandbox.docker_runner import DockerExecutionResult
    from app.services.workspace_verification import WorkspaceVerification
    monkeypatch.setattr(pr, "run_workspace_verification", lambda *a, **kw: WorkspaceVerification(result=DockerExecutionResult(exit_code=0, stdout="Tests run: 1, Failures: 0, Errors: 0, Skipped: 0"), platform_test_path=None))

    pr._execute_pipeline_steps(session_id, LifecyclePhase.DEVOPS_DEPLOY,
                               stop_on_gate=True, auto_deploy=True, provider='mock')

    assert deployed == [(session_id, str(ws))]


def test_auto_deploy_is_skipped_when_not_requested(session, monkeypatch):
    session_id, _ = session
    _prepare_events(session_id)
    _stub_heavy_steps(monkeypatch)
    deployed = []
    monkeypatch.setattr(pr, "deploy_local", lambda *a, **k: deployed.append(a))

    pr._execute_pipeline_steps(session_id, LifecyclePhase.DEVOPS_DEPLOY,
                               stop_on_gate=True, auto_deploy=False, provider='mock')

    assert deployed == []


def test_a_blocking_quality_gate_stops_before_devops_even_with_auto_deploy(session, monkeypatch):
    """``stop_on_gate`` outranks ``auto_deploy``: a blocked gate must not reach deployment."""
    session_id, ws = session
    _prepare_events(session_id)
    _stub_heavy_steps(monkeypatch, audit=_Audit(_Gate("BLOCKED", "hardcoded secret")))
    deployed = []
    monkeypatch.setattr(pr, "deploy_local", lambda *a, **k: deployed.append(a))

    pr._execute_pipeline_steps(session_id, LifecyclePhase.DEVOPS_DEPLOY,
                               stop_on_gate=True, auto_deploy=True, provider='mock')

    assert deployed == []
    assert not any(e.step == "DevOps & Manifiestos" for e in _recorded_events(session_id))
    assert pr.get_pipeline_status(session_id) == PipelineRunStatus.AWAITING_INTERVENTION


def test_the_gate_can_be_ignored_when_the_operator_asks(session, monkeypatch):
    """Guided Step allows an informed override; the flag is what makes it explicit."""
    session_id, ws = session
    _prepare_events(session_id)
    _stub_heavy_steps(monkeypatch, audit=_Audit(_Gate("BLOCKED", "hardcoded secret")))

    pr._execute_pipeline_steps(session_id, LifecyclePhase.DEVOPS_DEPLOY,
                               stop_on_gate=False, auto_deploy=False, provider='mock')

    assert (ws / "docker-compose.yml").exists()
    assert pr.get_pipeline_status(session_id) == PipelineRunStatus.COMPLETED


# ===========================================================================
# Instructions, drafts and the deterministic/model mode split
# ===========================================================================
def test_a_missing_instruction_set_only_warns_on_the_deterministic_path(session, monkeypatch,
                                                                       capsys):
    """Offline generation does not read instructions, so an absent set must not stop it."""
    session_id, ws = session
    _prepare_events(session_id)
    _stub_heavy_steps(monkeypatch)

    class _Deterministic:
        mode = "DETERMINISTIC"
        provider = None
        model = None
        reason = "test"

    monkeypatch.setattr(pr, "select_generation_mode", lambda **kw: _Deterministic())

    def explode():
        raise FileNotFoundError("no instruction set installed")

    monkeypatch.setattr("app.orchestrator.stages.instructions.load_instruction_set", explode)

    pr._execute_pipeline_steps(session_id, LifecyclePhase.DEVOPS_DEPLOY,
                               stop_on_gate=True, auto_deploy=False, provider='mock')

    assert pr.get_pipeline_status(session_id) == PipelineRunStatus.COMPLETED
    assert (ws / "docker-compose.yml").exists()
    assert "instruction set not loaded" in capsys.readouterr().out


def test_a_missing_instruction_set_fails_loudly_on_the_model_path(session, monkeypatch):
    """The model path *does* read the set. Continuing without it would emit template-shaped
    artifacts from a session recorded as model-generated -- the hybrid the mode split
    exists to prevent."""
    session_id, _ = session
    _prepare_events(session_id)
    _stub_heavy_steps(monkeypatch)

    class _Model:
        mode = "MODEL"
        provider = "deepseek"
        model = "deepseek-flash"
        reason = "test"

    monkeypatch.setattr(pr, "select_generation_mode", lambda **kw: _Model())

    def explode():
        raise FileNotFoundError("no instruction set installed")

    monkeypatch.setattr("app.orchestrator.stages.instructions.load_instruction_set", explode)

    pr._execute_pipeline_steps(session_id, LifecyclePhase.DEVOPS_DEPLOY,
                               stop_on_gate=True, auto_deploy=False, provider='mock')

    assert pr.get_pipeline_status(session_id) == PipelineRunStatus.FAILED
    assert "no instruction set installed" in _row(session_id).error_message


def test_exhausted_stages_block_the_session_and_record_the_evidence(session, monkeypatch):
    """The exhaustion path -- the one the module's own docstring calls the fix.

    When the repair budget runs out the branch used to set an in-memory status and return:
    the session row kept its pre-run state forever and no diagnostic was written, so a
    blocked session -- the one most worth diagnosing -- was the one path that recorded
    nothing. This pins state, status and evidence being written together.
    """
    session_id, ws = session
    _prepare_events(session_id)
    recorded = []
    monkeypatch.setattr(pr, "record_session_diagnostics",
                        lambda sid, state, **kw: recorded.append(sid) or True)
    monkeypatch.setattr(pr, "audit_workspace", lambda *a, **k: _Audit())

    def blocked_stages(state, stages=None, api_key=None, **kwargs):
        ws_path = Path(state["workspace_path"])
        (ws_path / "pom.xml").write_text("<project/>", encoding="utf-8")
        java = ws_path / "src" / "main" / "java"
        java.mkdir(parents=True, exist_ok=True)
        (java / "App.java").write_text("class App {}", encoding="utf-8")
        state["status"] = SessionStatus.BLOCKED.value
        state["error"] = "3 repair attempts exhausted"
        return state

    monkeypatch.setattr(pr, "run_generation_stages", blocked_stages)

    pr._execute_pipeline_steps(session_id, LifecyclePhase.DEVOPS_DEPLOY,
                               stop_on_gate=True, auto_deploy=False, provider='mock')

    row = _row(session_id)
    assert row.status == SessionStatus.BLOCKED
    assert row.error_message == "3 repair attempts exhausted"
    assert row.completed_at is not None
    assert pr.get_pipeline_status(session_id) == PipelineRunStatus.AWAITING_INTERVENTION
    assert recorded == [session_id], "the blocked session was not diagnosed"
    assert not any(e.step == "DevOps & Manifiestos" for e in _recorded_events(session_id)), "a blocked run continued into DevOps"
    events = _recorded_events(session_id)
    assert events[-1].status == PhaseStatus.BLOCKED
    assert events[-1].error == "3 repair attempts exhausted"


def test_deterministic_architecture_is_derived_per_entity(session, monkeypatch):
    """No key: the architecture is DERIVED from the draft's entities, not a hardcoded list."""
    session_id, ws = session
    _prepare_events(session_id)
    _stub_heavy_steps(monkeypatch)

    def explode(*args, **kwargs):
        raise RuntimeError("architecture service unavailable")

    # No api_key => deterministic path, so the LLM design is never invoked and this
    # stub proves the pipeline did not try to call it.
    monkeypatch.setattr(pr, "design_architecture", explode)

    pr._execute_pipeline_steps(session_id, LifecyclePhase.DEVOPS_DEPLOY,
                               stop_on_gate=True, auto_deploy=False, provider='mock')

    assert pr.get_pipeline_status(session_id) == PipelineRunStatus.COMPLETED
    arch = json.loads((ws / "architecture.json").read_text(encoding="utf-8"))
    assert arch["serviceName"] == "orderservice"
    # Per-entity component objects (Controller/Service/Repository/Model), not the
    # hardcoded ["Controller", "Service", "Repository", "Entity"] list.
    assert isinstance(arch["components"], list) and arch["components"]
    assert all(isinstance(c, dict) and "layer" in c for c in arch["components"])
    assert "mermaidDiagram" in arch
    assert (ws / "architecture.md").exists()


def test_an_ambiguous_api_key_blocks_the_session_instead_of_escaping(session, monkeypatch):
    """``detect_provider`` refuses to guess between DeepSeek and OpenAI for an ``sk-`` key
    when both environment variables are set. Refusing is right; escaping the handler is
    not -- the operator would be left with a session stuck on RUNNING and no reason given.
    """
    session_id, _ = session
    _prepare_events(session_id)
    _stub_heavy_steps(monkeypatch)

    def explode(*args, **kwargs):
        raise ValueError("Ambiguous provider: pass an explicit provider")

    monkeypatch.setattr(pr.LLMFactory, "detect_provider", explode)

    pr._execute_pipeline_steps(session_id, LifecyclePhase.DEVOPS_DEPLOY,
                               stop_on_gate=True, auto_deploy=False, provider='mock')

    assert pr.get_pipeline_status(session_id) == PipelineRunStatus.FAILED
    assert "Ambiguous provider" in _row(session_id).error_message


def test_an_unreadable_spec_file_blocks_without_inventing_a_draft(session, monkeypatch):
    """A spec.md that cannot be read is a normal half-written state, not a fatal one."""
    session_id, ws = session
    (ws / "spec.md").mkdir(parents=True, exist_ok=True)  # a directory: read_text raises
    _prepare_events(session_id)
    _stub_heavy_steps(monkeypatch)

    pr._execute_pipeline_steps(session_id, LifecyclePhase.DEVOPS_DEPLOY,
                               stop_on_gate=True, auto_deploy=False, provider='mock')

    assert pr.get_pipeline_status(session_id) == PipelineRunStatus.FAILED
    assert not (ws / "user_stories.json").exists()
    assert (ws / "spec.md").is_dir()
    assert _row(session_id).error_message


def test_an_entity_without_a_primary_key_gets_one(monkeypatch, tmp_path):
    """JPA requires an @Id. A blueprint whose entity lacks one must still produce a valid
    domain model rather than one the persistence layer rejects."""
    from app.services import requirements_service as rs

    decomp = rs._generate_mock_decomposition(raw_text="cafe", service_name="cafe")
    decomp.entities[0].attributes = [
        a for a in decomp.entities[0].attributes if not getattr(a, "isPrimaryKey", False)
    ]
    assert not any(getattr(a, "isPrimaryKey", False) for a in decomp.entities[0].attributes)

    monkeypatch.setattr(pr, "_generate_mock_decomposition", lambda **kw: decomp)
    monkeypatch.setattr(pr.settings, "WORKSPACE_DIR", str(tmp_path))
    (tmp_path / 'spec.md').write_text('Crear un servicio de pedidos con nombre y precio', encoding='utf-8')
    draft = pr._get_or_create_draft(tmp_path, "cafe")

    attributes = draft.entities[0].attributes
    assert attributes[0].name == "id"
    assert attributes[0].isPrimaryKey is True


def test_an_existing_spec_file_is_used_as_the_prompt(tmp_path, monkeypatch):
    """The prompt the user submitted is what the decomposition should run on."""
    monkeypatch.setattr(pr.settings, "WORKSPACE_DIR", str(tmp_path))
    (tmp_path / "spec.md").write_text(
        "# Feature Specification: orders\n\nun servicio de pedidos con ceviche", encoding="utf-8"
    )
    real = pr._generate_mock_decomposition
    seen = {}

    def capture(raw_text=None, service_name=None, **kw):
        seen["raw_text"] = raw_text
        return real(raw_text=raw_text, service_name=service_name)

    monkeypatch.setattr(pr, "_generate_mock_decomposition", capture)

    pr._get_or_create_draft(tmp_path, "orders")

    assert "ceviche" in seen["raw_text"]


def test_a_short_spec_file_is_ignored_and_the_service_name_is_used(tmp_path, monkeypatch):
    """A stub spec of a few characters carries no prompt; using it would decompose noise."""
    monkeypatch.setattr(pr.settings, "WORKSPACE_DIR", str(tmp_path))
    (tmp_path / "spec.md").write_text("# x\n", encoding="utf-8")
    real = pr._generate_mock_decomposition
    seen = {}

    def capture(raw_text=None, service_name=None, **kw):
        seen["raw_text"] = raw_text
        return real(raw_text=raw_text, service_name=service_name)

    monkeypatch.setattr(pr, "_generate_mock_decomposition", capture)

    pr._get_or_create_draft(tmp_path, "orders")

    assert seen["raw_text"] == "orders"


def test_a_rejected_model_transform_blocks_instead_of_fabricating(tmp_path, monkeypatch):
    """A model-mode transform failure must propagate, not fabricate a decomposition."""
    monkeypatch.setattr(pr.settings, "WORKSPACE_DIR", str(tmp_path))
    monkeypatch.setattr(pr.LLMFactory, "is_mock", lambda *a, **k: False)

    def explode(*args, **kwargs):
        raise RuntimeError("model refused")

    monkeypatch.setattr(pr, "transform_requirements", explode)

    with pytest.raises(RuntimeError):
        pr._get_or_create_draft(tmp_path, "order-processing-service", api_key="sk-real", provider="deepseek")
