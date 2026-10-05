import sys
import threading
import subprocess
from unittest.mock import Mock
import pytest
from app.models.devops import DeploymentStatus as Status
from app.services import docker_service as service, local_operations as operations
from app.services.logged_process import run_logged, CommandCancelled
from app.services.local_runtime import restore
from test_local_docker_runtime import runtime


def test_cancel_exact_operation_prevents_any_build_or_start(runtime):
    row = service.deploy_local(runtime.id, str(runtime.ws))
    assert row.operationKind == 'DEPLOY' and row.startedAt and not row.finishedAt
    commands_before = len(runtime.commands)
    operations.request_cancel(runtime.id, row.operationId)
    operations.request_cancel(runtime.id, row.operationId)
    runtime.workers[0]()
    assert len(runtime.commands) == commands_before
    assert row.status == Status.FAILED and row.finishedAt and row.cancelRequested
    assert row.operationPhase == 'INTERRUPTED' and 'daemon' in row.errorMessage
    assert not service._operation_locks[runtime.id].locked()
    assert restore(runtime.id).cancelRequested


def test_old_cancel_cannot_cancel_new_retry(runtime):
    first = service.deploy_local(runtime.id, str(runtime.ws))
    operations.request_cancel(runtime.id, first.operationId)
    runtime.workers[0]()
    second = service.deploy_local(runtime.id, str(runtime.ws))
    with pytest.raises(ValueError, match='cambió'):
        operations.request_cancel(runtime.id, first.operationId)
    assert not second.cancelRequested
    runtime.workers[1]()
    assert second.status == Status.HEALTHY and second.finishedAt


def test_build_cancellation_never_starts_runtime(runtime, monkeypatch):
    def cancelled_build(command, on_line, **kwargs):
        assert kwargs['timeout'] == service.settings.LOCAL_BUILD_TIMEOUT
        assert service._active_deployments[runtime.id].operationPhase == 'BUILD'
        kwargs['cancel_event'].set()
        raise CommandCancelled('CLI cancelado; daemon no confirmado')
    monkeypatch.setattr(service, 'run_logged', cancelled_build)
    row = service.deploy_local(runtime.id, str(runtime.ws))
    runtime.workers[0]()
    assert row.cancelRequested and row.finishedAt and row.status == Status.FAILED
    assert not any('up' in command for command in runtime.commands)


def test_autopilot_cancel_signals_exact_active_deployment(runtime, monkeypatch):
    from app.services import pipeline_runner
    monkeypatch.setattr(pipeline_runner, '_record_pipeline_cost', lambda *a, **k: None)
    monkeypatch.setattr(pipeline_runner, '_stop_events', {runtime.id: threading.Event()})
    row = service.deploy_local(runtime.id, str(runtime.ws))
    pipeline_runner.cancel_pipeline(runtime.id)
    assert row.cancelRequested and pipeline_runner._stop_events[runtime.id].is_set()
    runtime.workers[0]()
    assert row.finishedAt and not any('up' in command for command in runtime.commands)


def test_start_timeout_stops_only_owned_runtime_preserving_data(runtime, monkeypatch):
    original = service.subprocess.run
    def timeout(command, **kwargs):
        if 'up' in command:
            runtime.started = True
            raise subprocess.TimeoutExpired(command, 0.01)
        return original(command, **kwargs)
    monkeypatch.setattr(service.subprocess, 'run', timeout)
    row = service.deploy_local(runtime.id, str(runtime.ws))
    runtime.workers[0]()
    assert row.status == Status.FAILED and row.operationPhase == 'INTERRUPTED'
    assert not runtime.started and row.finishedAt
    assert any(command[:2] == ['docker', 'stop'] and command[-1] == 'container-id' for command in runtime.commands)
    assert not any('rm' in command or '--volumes' in command for command in runtime.commands)


def test_source_cancel_does_not_invoke_docker(runtime, monkeypatch):
    from app.models.execution import ExecutionMode
    monkeypatch.setattr('app.services.execution_policy.execution_mode', lambda _: ExecutionMode.SOURCE_ONLY)
    monkeypatch.setattr(service.subprocess, 'run', lambda *a, **k: pytest.fail('Docker in sources'))
    assert operations.request_cancel(runtime.id, 'unused').status == Status.SKIPPED_BY_CHOICE


def test_restart_and_prepare_share_control_and_finish_metadata(runtime):
    from app.services import runtime_lifecycle, local_preparation
    first = runtime_lifecycle.restart_local(runtime.id, str(runtime.ws))
    operations.request_cancel(runtime.id, first.operationId)
    runtime.workers[0]()
    assert first.finishedAt and first.cancelRequested and first.operationKind == 'RESTART'
    runtime.commands.clear()
    prepared = local_preparation.prepare_local(runtime.id, str(runtime.ws), 'H2')
    operations.request_cancel(runtime.id, prepared.operationId)
    before = len(runtime.commands)
    runtime.workers[1]()
    assert len(runtime.commands) == before
    assert prepared.finishedAt and prepared.cancelRequested and prepared.operationKind == 'PREPARE'
    assert not service._operation_locks[runtime.id].locked()


def test_cancel_route_checks_operation_identity_and_session(runtime, monkeypatch):
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
    from app.api import routes_devops as routes
    row = service.deploy_local(runtime.id, str(runtime.ws))
    def resolve(identity):
        if identity != runtime.id: raise HTTPException(404, 'Missing session')
        return runtime.ws, 'probe-service'
    monkeypatch.setattr(routes, '_resolve_session_context', resolve)
    app = FastAPI(); app.include_router(routes.router)
    with TestClient(app) as client:
        assert client.post(f'/devops/{runtime.id}/cancel', json={}).status_code == 422
        assert client.post(f'/devops/{runtime.id}/cancel', json={'operationId': 'old'}).status_code == 409
        assert client.post('/devops/missing/cancel', json={'operationId': row.operationId}).status_code == 404
        result = client.post(f'/devops/{runtime.id}/cancel', json={'operationId': row.operationId})
        assert result.status_code == 200 and result.json()['cancelRequested']
        assert not result.json()['finishedAt']
    runtime.workers[0]()


def test_real_owned_process_is_reaped_on_cancel():
    control = threading.Event()
    seen = []
    def output(line):
        seen.append(line)
        control.set()
    with pytest.raises(CommandCancelled):
        run_logged([sys.executable, '-u', '-c', 'import time;print("ready", flush=True);time.sleep(30)'],
                   output, cancel_event=control, timeout=5)
    assert 'ready' in seen


def test_pre_cancel_does_not_spawn_process(monkeypatch):
    control = threading.Event(); control.set()
    spawn = Mock(side_effect=AssertionError('spawned cancelled command'))
    monkeypatch.setattr(subprocess, 'Popen', spawn)
    with pytest.raises(CommandCancelled):
        run_logged(['unused'], lambda _: None, cancel_event=control)
    spawn.assert_not_called()


def test_recovered_operation_without_worker_does_not_keep_ui_busy(runtime):
    from app.models.devops import LocalDeploymentSession
    from app.services.local_runtime import persist
    row = LocalDeploymentSession(sessionId=runtime.id, operationId='lost-worker', operationKind='DEPLOY',
        operationPhase='READINESS', status=Status.RUNNING)
    persist(row)
    recovered = restore(runtime.id)
    assert recovered.finishedAt and recovered.operationPhase == 'INTERRUPTED'
    assert 'no se confirma' in recovered.message
