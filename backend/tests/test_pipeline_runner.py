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


@pytest.fixture(autouse=True)
def hermetic_verification(monkeypatch):
    """Keep the suite hermetic: no test may run a real container build.

    The sequential path now verifies the workspace, which is correct in production
    and unacceptable in a unit suite -- a Docker build makes tests slow and makes
    their result depend on the host. Tests that need to observe verification
    monkeypatch `run_workspace_verification` themselves, which overrides this.
    """
    from app.sandbox.docker_runner import DockerExecutionResult
    from app.services.workspace_verification import WorkspaceVerification
    import app.services.pipeline_runner as pr

    fake = WorkspaceVerification(
        result=DockerExecutionResult(exit_code=0, stdout="", fallback_used=True,
                                     fallback_reason="stubbed for the hermetic suite"),
        platform_test_path=None,
    )
    monkeypatch.setattr(
        pr, "run_workspace_verification", lambda path, log_callback=None: fake
    )
    yield


def _stub_passing_verification(monkeypatch) -> None:
    """Override the suite-wide hermetic stub with a verification that actually passed.

    The autouse fixture deliberately substitutes a *fallback* result so no test runs a
    real container build; by the product's rule that is not a pass, so a test that
    needs the pipeline to proceed past verification (to COMPLETED, or to the security
    audit) must install its own passing result.
    """
    from app.sandbox.docker_runner import DockerExecutionResult
    from app.services.workspace_verification import WorkspaceVerification
    import app.services.pipeline_runner as pr

    passing = WorkspaceVerification(
        result=DockerExecutionResult(
            exit_code=0,
            stdout="[INFO] Tests run: 6, Failures: 0, Errors: 0, Skipped: 0\n",
        ),
        platform_test_path="src/test/java/x/PlatformPersistenceContractTest.java",
    )
    monkeypatch.setattr(
        pr, "run_workspace_verification", lambda path, log_callback=None: passing
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


def test_pipeline_runner_full_run(runner_session, monkeypatch):
    session_id, ws_path = runner_session
    import threading
    _pause_events[session_id] = threading.Event()
    _stop_events[session_id] = threading.Event()

    # A run may only reach COMPLETED when verification actually passed; the
    # suite-wide hermetic stub substitutes a fallback result, which is correctly
    # not a pass. Supply a passing verification for this test, which is about the
    # steps and artifacts of a full run.
    _stub_passing_verification(monkeypatch)

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

    # The audit is only reached once hermetic verification has passed. The suite-wide
    # hermetic stub substitutes a fallback result, which stops the run before the gate
    # and would make the mocked gate unreachable.
    _stub_passing_verification(monkeypatch)

    _execute_pipeline_steps(session_id, LifecyclePhase.DEVOPS_DEPLOY, stop_on_gate=True, auto_deploy=False)

    assert _pipeline_statuses.get(session_id) == PipelineRunStatus.AWAITING_INTERVENTION

    # The gate halts the run and names the reason on the session row. DevOps assets
    # now exist by then: `generate_all_devops_assets` runs before verification because
    # the hermetic container build consumes the workspace's Dockerfile, so their
    # absence can no longer express "the gate blocked the run".
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



def test_the_sequential_path_verifies_the_workspace(runner_session, monkeypatch):
    """The product path used to generate code and never compile it.

    `POST /sessions/quick-start` with autoRun, and /orchestrator/pipeline/run, are the
    routes the readiness report tells clients to use -- and they ran the generation
    stages and a static SAST audit with no build or test step anywhere. So on the
    primary product path the acceptance signal was not merely generator-authored: it
    did not exist. This pins that the sequential path now verifies.
    """
    import threading

    from app.sandbox.docker_runner import DockerExecutionResult
    from app.services.workspace_verification import WorkspaceVerification
    import app.services.pipeline_runner as pr

    calls = []
    fake = WorkspaceVerification(
        result=DockerExecutionResult(
            exit_code=0,
            stdout="[INFO] Tests run: 7, Failures: 0, Errors: 0, Skipped: 0\n",
        ),
        platform_test_path="src/test/java/x/PlatformPersistenceContractTest.java",
    )

    def fake_verify(path, log_callback=None):
        calls.append(path)
        return fake

    monkeypatch.setattr(pr, "run_workspace_verification", fake_verify)

    session_id, ws_path = runner_session
    _pause_events[session_id] = threading.Event()
    _stop_events[session_id] = threading.Event()
    _execute_pipeline_steps(
        session_id, LifecyclePhase.CODE_TESTS, stop_on_gate=True, auto_deploy=False
    )

    assert calls, "the sequential path did not verify the workspace"

    db = SessionLocal()
    try:
        row = (
            db.query(GenerationSessionDB)
            .filter(GenerationSessionDB.id == session_id)
            .first()
        )
        metrics = json.loads(row.verification_metrics_json)
    finally:
        db.close()

    assert metrics["totalTests"] == 7
    assert metrics["passedTests"] == 7
    assert metrics["allPassed"] is True
    assert metrics["platformContractTestInjected"] is True


def test_a_substituted_verification_is_not_reported_as_a_pass(runner_session, monkeypatch):
    """Feature 012's rule, applied to the path that never had it.

    A fallback result means verification did not happen, so the session must not be
    recorded as verified however the exit code reads.
    """
    import threading

    from app.sandbox.docker_runner import DockerExecutionResult
    from app.services.workspace_verification import WorkspaceVerification
    import app.services.pipeline_runner as pr

    fake = WorkspaceVerification(
        result=DockerExecutionResult(
            exit_code=0,
            stdout="",
            fallback_used=True,
            fallback_reason="container runtime unreachable",
        ),
        platform_test_path=None,
    )
    monkeypatch.setattr(
        pr, "run_workspace_verification", lambda path, log_callback=None: fake
    )

    session_id, ws_path = runner_session
    _pause_events[session_id] = threading.Event()
    _stop_events[session_id] = threading.Event()
    _execute_pipeline_steps(
        session_id, LifecyclePhase.CODE_TESTS, stop_on_gate=True, auto_deploy=False
    )

    db = SessionLocal()
    try:
        row = (
            db.query(GenerationSessionDB)
            .filter(GenerationSessionDB.id == session_id)
            .first()
        )
        metrics = json.loads(row.verification_metrics_json)
    finally:
        db.close()

    assert metrics["fallback_used"] is True
    assert metrics["allPassed"] is False, "a substituted verification is not a pass"


def test_a_verifier_that_raises_is_recorded_as_unverified(runner_session, monkeypatch):
    """An exception has verified nothing, and must not become a pass."""
    import threading

    import app.services.pipeline_runner as pr

    def explode(path, log_callback=None):
        raise RuntimeError("sandbox unavailable")

    monkeypatch.setattr(pr, "run_workspace_verification", explode)

    session_id, ws_path = runner_session
    _pause_events[session_id] = threading.Event()
    _stop_events[session_id] = threading.Event()
    _execute_pipeline_steps(
        session_id, LifecyclePhase.CODE_TESTS, stop_on_gate=True, auto_deploy=False
    )

    db = SessionLocal()
    try:
        row = (
            db.query(GenerationSessionDB)
            .filter(GenerationSessionDB.id == session_id)
            .first()
        )
        metrics = json.loads(row.verification_metrics_json)
    finally:
        db.close()

    assert metrics["fallback_used"] is True
    assert metrics["allPassed"] is False
    assert "RuntimeError" in metrics["fallback_reason"]
