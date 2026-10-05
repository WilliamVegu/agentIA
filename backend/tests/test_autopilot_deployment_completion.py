"""Real pipeline control flow with infrastructure/model boundaries simulated."""
import pytest
from types import SimpleNamespace
from app.models.devops import LocalDeploymentSession, DeploymentStatus
from app.models.execution import ExecutionMode
from app.models.orchestrator import LifecyclePhase, PipelineRunStatus
from app.models.session import GenerationSessionDB, SessionLocal, SessionStatus
from app.services import pipeline_runner as pr, docker_service
from test_qe_pipeline_autopilot import session, isolated_runner_state, _prepare_events, _stub_heavy_steps, _row


@pytest.fixture
def deploy_pipeline(session, monkeypatch):
    sid, ws = session
    _prepare_events(sid)
    _stub_heavy_steps(monkeypatch)
    monkeypatch.setattr(pr, 'execution_mode', lambda _: ExecutionMode.DOCKER)
    # Drive step 7 without model calls, Docker verification or earlier artifacts.
    monkeypatch.setattr(pr, 'generate_all_devops_assets', lambda *a, **k: None)
    monkeypatch.setattr(pr.time, 'sleep', lambda _: None)
    from app.services.workspace_verification import WorkspaceVerification
    from app.sandbox.docker_runner import DockerExecutionResult
    def verify(*args, **kwargs):
        sources = pr.execution_mode(sid) == ExecutionMode.SOURCE_ONLY
        return WorkspaceVerification(result=DockerExecutionResult(exit_code=0,
            stdout='' if sources else 'Tests run: 3, Failures: 0, Errors: 0, Skipped: 0\nBUILD SUCCESS',
            fallback_used=sources, verification_skipped=sources,
            fallback_reason='fuentes elegidas' if sources else None), platform_test_path=None)
    monkeypatch.setattr(pr, 'run_workspace_verification', verify)
    return sid


@pytest.mark.parametrize('initial', [DeploymentStatus.BUILDING, DeploymentStatus.RUNNING])
@pytest.mark.parametrize('final', [DeploymentStatus.HEALTHY, DeploymentStatus.FAILED, DeploymentStatus.DOCKER_UNAVAILABLE])
def test_autopilot_waits_before_completing_or_asking_for_decision(deploy_pipeline, monkeypatch, initial, final):
    sid = deploy_pipeline
    monkeypatch.setattr(pr, 'deploy_local', lambda *a, **k: LocalDeploymentSession(sessionId=sid, status=initial))
    waited = []
    def wait(identity, stop_event=None):
        assert _row(sid).status != SessionStatus.COMPLETED
        waited.append((identity, stop_event))
        return LocalDeploymentSession(sessionId=sid, status=final, errorMessage='real cause' if final != DeploymentStatus.HEALTHY else None)
    monkeypatch.setattr(docker_service, 'wait_for_deployment', wait)
    pr._execute_pipeline_steps(sid, LifecyclePhase.DEVOPS_DEPLOY, stop_on_gate=True, auto_deploy=True)
    assert waited == [(sid, pr._stop_events[sid])]
    if final == DeploymentStatus.HEALTHY:
        assert pr._pipeline_statuses[sid] == PipelineRunStatus.COMPLETED
    else:
        assert pr._pipeline_statuses[sid] == PipelineRunStatus.AWAITING_INTERVENTION
        assert _row(sid).status == SessionStatus.PAUSED and _row(sid).error_message == 'real cause'
        events = list(pr._event_queues[sid].queue)
        decision = [event for event in events if event.step == 'Despliegue pendiente de decisión']
        assert decision and decision[-1].error == 'real cause'
        if final == DeploymentStatus.DOCKER_UNAVAILABLE:
            assert 'continuar sin Docker' in decision[-1].message


def test_cancel_during_deploy_wait_does_not_become_completed_or_paused(deploy_pipeline, monkeypatch):
    sid = deploy_pipeline
    monkeypatch.setattr(pr, 'deploy_local', lambda *a, **k: LocalDeploymentSession(sessionId=sid, status=DeploymentStatus.BUILDING))
    def wait(identity, stop_event=None):
        stop_event.set()
        return LocalDeploymentSession(sessionId=sid, status=DeploymentStatus.FAILED)
    monkeypatch.setattr(docker_service, 'wait_for_deployment', wait)
    pr._execute_pipeline_steps(sid, LifecyclePhase.DEVOPS_DEPLOY, stop_on_gate=True, auto_deploy=True)
    assert pr._pipeline_statuses[sid] == PipelineRunStatus.CANCELLED
    assert _row(sid).status == SessionStatus.CANCELLED


def test_source_only_autopilot_never_deploys_or_waits(deploy_pipeline, monkeypatch):
    sid = deploy_pipeline
    monkeypatch.setattr(pr, 'execution_mode', lambda _: ExecutionMode.SOURCE_ONLY)
    monkeypatch.setattr(pr, 'deploy_local', lambda *a, **k: pytest.fail('Docker deploy in sources'))
    monkeypatch.setattr(docker_service, 'wait_for_deployment', lambda *a, **k: pytest.fail('Docker wait in sources'))
    pr._execute_pipeline_steps(sid, LifecyclePhase.DEVOPS_DEPLOY, stop_on_gate=True, auto_deploy=True)
    assert pr._pipeline_statuses[sid] == PipelineRunStatus.COMPLETED


def test_pause_during_deploy_wait_does_not_become_completed(deploy_pipeline, monkeypatch):
    sid = deploy_pipeline
    pr._active_threads[sid] = SimpleNamespace(is_alive=lambda: True)
    monkeypatch.setattr(pr, 'deploy_local', lambda *a, **k: LocalDeploymentSession(sessionId=sid, status=DeploymentStatus.BUILDING))
    def wait(identity, stop_event=None):
        pr.pause_pipeline(sid)
        return LocalDeploymentSession(sessionId=sid, status=DeploymentStatus.HEALTHY)
    monkeypatch.setattr(docker_service, 'wait_for_deployment', wait)
    pr._execute_pipeline_steps(sid, LifecyclePhase.DEVOPS_DEPLOY, stop_on_gate=True, auto_deploy=True)
    assert pr._pipeline_statuses[sid] == PipelineRunStatus.PAUSED
    assert _row(sid).status == SessionStatus.PAUSED


def test_passing_test_summary_does_not_override_failed_build(deploy_pipeline, monkeypatch):
    import json
    from app.services.workspace_verification import WorkspaceVerification
    from app.sandbox.docker_runner import DockerExecutionResult
    monkeypatch.setattr(pr, 'run_workspace_verification', lambda *a, **k: WorkspaceVerification(
        result=DockerExecutionResult(exit_code=1, stdout='Tests run: 3, Failures: 0, Errors: 0, Skipped: 0'),
        platform_test_path=None))
    monkeypatch.setattr(pr, 'deploy_local', lambda *a, **k: pytest.fail('Failed build must not deploy'))
    pr._execute_pipeline_steps(deploy_pipeline, LifecyclePhase.DEVOPS_DEPLOY, stop_on_gate=True, auto_deploy=True)
    row = _row(deploy_pipeline)
    assert row.status == SessionStatus.BLOCKED
    metrics = json.loads(row.verification_metrics_json)
    assert metrics['passedTests'] == 3 and not metrics['allPassed']
