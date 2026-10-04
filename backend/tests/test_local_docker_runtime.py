"""Exercise Docker outcomes with inspected container identities and real port sockets."""
import json
import socket
import uuid
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from app.config import settings
from app.models.session import SessionLocal, GenerationSessionDB, SessionStatus
from app.models.devops import DeploymentStatus, LocalDeploymentSession
from app.services import docker_service as service
from app.services.local_runtime import inspect_session, available_port, restore
from app.services.devops_service import generate_all_devops_assets
from app.sandbox.docker_runner import build_docker_cmd


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    identity = str(uuid.uuid4())
    ws = tmp_path / identity
    (ws / 'src/main/java').mkdir(parents=True)
    (ws / 'pom.xml').write_text('<project><dependencies></dependencies></project>')
    monkeypatch.setattr(settings, 'WORKSPACE_DIR', str(tmp_path))
    monkeypatch.setattr(settings, 'DOCKER_ENABLED', True)
    monkeypatch.setattr(service, '_active_deployments', {})
    monkeypatch.setattr(service, '_raw_log_history', {})
    monkeypatch.setattr(service, '_operation_locks', {})
    with SessionLocal() as db:
        db.add(GenerationSessionDB(id=identity, spec_id='test', spec_name='runtime-service', execution_mode='DOCKER', status=SessionStatus.PAUSED))
        db.commit()
    generate_all_devops_assets(str(ws), identity, 'runtime-service', db_engine='H2')
    data = SimpleNamespace(id=identity, ws=ws, started=False, port=18080, foreign=False, healthy=True, stop_failure=False, build_failure=False, commands=[], workers=[])
    class DeferredThread:
        def __init__(self, target, **kwargs): data.workers.append(target)
        def start(self): pass
    monkeypatch.setattr(service.threading, 'Thread', DeferredThread)
    def execute(cmd, **kwargs):
        data.commands.append(cmd)
        rc, output, error = 0, '', ''
        if cmd[:2] == ['docker', 'ps']:
            output = 'container-id' if data.started else ''
        elif cmd[:2] == ['docker', 'inspect']:
            output = json.dumps([{'Id': 'container-id', 'Config': {'Labels': {'com.docker.compose.project': 'foreign-session' if data.foreign else identity, 'io.agentia.role': 'application'}}, 'HostConfig': {'PortBindings': {'8080/tcp': [{'HostIp': '127.0.0.1', 'HostPort': str(data.port)}]}}, 'State': {'Running': data.started}}])
        elif 'build' in cmd and data.build_failure:
            rc, error = 1, 'BUILD FAILURE: actual failing test'
        elif 'up' in cmd:
            data.started = True
            data.port = int(kwargs['env']['HOST_PORT'])
        elif 'down' in cmd:
            if data.stop_failure: rc, error = 1, 'daemon disconnected'
            else: data.started = False
        return SimpleNamespace(returncode=rc, stdout=output, stderr=error)
    monkeypatch.setattr(service.subprocess, 'run', execute)
    monkeypatch.setattr(service.requests, 'get', lambda *a, **kw: SimpleNamespace(status_code=200, json=lambda: {'status': 'UP' if data.healthy else 'DOWN'}))
    yield data
    with SessionLocal() as db:
        db.query(GenerationSessionDB).filter_by(id=identity).delete()
        db.commit()


def test_duplicate_deploy_is_one_operation_and_only_healthy_after_identity(runtime):
    first = service.deploy_local(runtime.id, str(runtime.ws), host_port=18080)
    duplicate = service.deploy_local(runtime.id, str(runtime.ws), host_port=18080)
    assert first.status == DeploymentStatus.BUILDING
    assert first.operationId == duplicate.operationId
    assert len(runtime.workers) == 1
    runtime.workers[0]()
    assert service.get_deployment_status(runtime.id).status == DeploymentStatus.HEALTHY
    assert any('build' in command and '--pull=false' in command for command in runtime.commands)
    assert any('up' in command and '--no-build' in command and 'never' in command for command in runtime.commands)


def test_build_failure_is_not_healthy(runtime):
    runtime.build_failure = True
    service.deploy_local(runtime.id, str(runtime.ws))
    runtime.workers[0]()
    row = service.get_deployment_status(runtime.id)
    assert row.status == DeploymentStatus.FAILED
    assert 'BUILD FAILURE' in row.errorMessage
    assert not runtime.started


def test_foreign_container_never_satisfies_smoke_test(runtime, monkeypatch):
    runtime.started, runtime.foreign = True, True
    probe = Mock(side_effect=AssertionError('probed foreign endpoint'))
    monkeypatch.setattr(service.requests, 'get', probe)
    assert inspect_session(runtime.id) is None
    assert not service.run_smoke_test(runtime.id).passed
    probe.assert_not_called()


def test_restart_and_health_downgrade_are_truthful(runtime, monkeypatch):
    service.deploy_local(runtime.id, str(runtime.ws))
    runtime.workers[0]()
    assert restore(runtime.id).status == DeploymentStatus.HEALTHY
    service._active_deployments.clear()
    runtime.healthy = False
    assert service.get_deployment_status(runtime.id).status == DeploymentStatus.DEGRADED
    runtime.started = False
    assert service.get_deployment_status(runtime.id).status == DeploymentStatus.STOPPED


def test_stop_failure_is_not_reported_as_stopped_and_does_not_delete_data(runtime):
    service.deploy_local(runtime.id, str(runtime.ws))
    runtime.workers[0]()
    runtime.stop_failure = True
    assert service.stop_deployment(runtime.id, str(runtime.ws)).status == DeploymentStatus.FAILED
    runtime.stop_failure = False
    assert service.stop_deployment(runtime.id, str(runtime.ws)).status == DeploymentStatus.STOPPED
    assert all('--volumes' not in command and '-v' not in command for command in runtime.commands if 'down' in command)


def test_port_conflict_selects_another_localhost_port():
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1', 0))
        port = occupied.getsockname()[1]
        if port == 65535: pytest.skip('No alternate port at end of range')
        assert available_port(port) > port


def test_prepared_sandbox_never_pulls_and_uses_private_writable_cache(runtime):
    command = build_docker_cmd(str(runtime.ws), 'unused-host-cache', 'agentia-builder:test', prepared=True)
    assert command[command.index('--pull') + 1] == 'never'
    assert command[command.index('--network') + 1] == 'none'
    assert '/opt/agentia-cache' in command[-1] and '/tmp/m2' in command[-1]
    assert 'verify' in command[-1]


def test_logs_are_durable_redacted_and_bounded(runtime):
    service._log_message(runtime.id, 'password=do-not-disclose token=private-value')
    service._raw_log_history.clear()
    logs = service.get_deployment_logs(runtime.id)
    assert '[REDACTED]' in logs[0] and 'private-value' not in logs[0]


@pytest.mark.parametrize('failure', [FileNotFoundError('docker missing'), OSError('permission denied')])
def test_daemon_errors_are_unavailable(runtime, monkeypatch, failure):
    def fail(*args, **kwargs): raise failure
    monkeypatch.setattr(service.subprocess, 'run', fail)
    assert service.get_deployment_status(runtime.id).status == DeploymentStatus.DOCKER_UNAVAILABLE


def test_non_json_health_is_not_a_pass(runtime, monkeypatch):
    runtime.started = True
    def response(*args, **kwargs):
        def invalid(): raise ValueError('not JSON')
        return SimpleNamespace(status_code=200, json=invalid)
    monkeypatch.setattr(service.requests, 'get', response)
    assert service.get_deployment_status(runtime.id).status == DeploymentStatus.DEGRADED
    assert not service.run_smoke_test(runtime.id, max_retries=1, interval=0).passed


def test_thread_start_error_releases_operation_and_records_failure(runtime, monkeypatch):
    class BrokenThread:
        def __init__(self, **kwargs): pass
        def start(self): raise RuntimeError('cannot start worker')
    monkeypatch.setattr(service.threading, 'Thread', BrokenThread)
    with pytest.raises(RuntimeError, match='cannot start worker'):
        service.deploy_local(runtime.id, str(runtime.ws))
    assert not service._operation_locks[runtime.id].locked()
    assert restore(runtime.id).status == DeploymentStatus.FAILED


def test_initial_write_failure_does_not_leave_building_or_lock(runtime, monkeypatch):
    from app.services import local_runtime
    monkeypatch.setattr(local_runtime, 'persist', Mock(side_effect=PermissionError('workspace read-only')))
    with pytest.raises(PermissionError):
        service.deploy_local(runtime.id, str(runtime.ws))
    assert not service._operation_locks[runtime.id].locked()
    assert service._active_deployments[runtime.id].status == DeploymentStatus.FAILED


def test_verification_conflicts_with_an_active_deployment(runtime):
    from fastapi import HTTPException
    from app.services.session_execution import verify_existing_sources
    service.deploy_local(runtime.id, str(runtime.ws))
    with pytest.raises(HTTPException) as blocked:
        verify_existing_sources(runtime.id)
    assert blocked.value.status_code == 409
    runtime.workers[0]()


def test_stopped_container_cannot_forward_playground_to_another_process(runtime, monkeypatch):
    from app.services import playground_proxy
    stopped = LocalDeploymentSession(sessionId=runtime.id, containerId='old-container', status=DeploymentStatus.STOPPED, hostPort=18080)
    monkeypatch.setattr(playground_proxy, 'get_deployment_status', lambda *a: stopped)
    with pytest.raises(playground_proxy.PlaygroundProxyError):
        playground_proxy.build_target_url(runtime.id, '/api/products')
