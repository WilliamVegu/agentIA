"""Operation completion and HTTP attribution, including port-bind races."""
import threading
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from app.models.devops import DeploymentStatus as Status, LocalDeploymentSession
from app.services import docker_service as service, playground_proxy as proxy
from app.services import local_runtime
from test_local_docker_runtime import runtime


@pytest.mark.parametrize('final', [Status.HEALTHY, Status.FAILED])
def test_wait_ignores_running_until_worker_releases_operation(runtime, monkeypatch, final):
    row = LocalDeploymentSession(sessionId=runtime.id, status=Status.RUNNING, containerId='owned')
    lock = threading.Lock(); lock.acquire()
    service._operation_locks[runtime.id] = lock
    service._active_deployments[runtime.id] = row
    query = Mock(side_effect=AssertionError('Health queried before worker completion'))
    monkeypatch.setattr(service, 'get_deployment_status', query)
    def finish(_):
        row.status = final
        row.errorMessage = 'smoke failed' if final == Status.FAILED else None
        lock.release()
    monkeypatch.setattr(service.time, 'sleep', finish)
    result = service.wait_for_deployment(runtime.id, timeout=10)
    assert result.status == final
    query.assert_not_called()


def test_wait_timeout_does_not_overwrite_or_claim_to_stop_worker(runtime):
    row = LocalDeploymentSession(sessionId=runtime.id, status=Status.BUILDING)
    service._active_deployments[runtime.id] = row
    lock = threading.Lock(); lock.acquire()
    service._operation_locks[runtime.id] = lock
    result = service.wait_for_deployment(runtime.id, timeout=0)
    assert result.status == Status.FAILED and 'puede seguir activa' in result.errorMessage
    assert row.status == Status.BUILDING and lock.locked()
    lock.release()


def test_pipeline_wait_interruption_is_immediate_and_honest(runtime):
    event = threading.Event(); event.set()
    result = service.wait_for_deployment(runtime.id, stop_event=event)
    assert result.status == Status.FAILED and 'no se confirma cancelación' in result.errorMessage
    assert not runtime.commands


def test_source_only_smoke_and_playground_do_not_call_docker_or_http(runtime, monkeypatch):
    from app.models.execution import ExecutionMode
    monkeypatch.setattr('app.services.execution_policy.execution_mode', lambda _: ExecutionMode.SOURCE_ONLY)
    monkeypatch.setattr(service.subprocess, 'run', lambda *a, **k: pytest.fail('Docker in sources'))
    monkeypatch.setattr(service.requests, 'get', lambda *a, **k: pytest.fail('HTTP in sources'))
    monkeypatch.setattr(proxy.requests, 'request', lambda *a, **k: pytest.fail('Proxy in sources'))
    assert not service.run_smoke_test(runtime.id).passed
    with pytest.raises(proxy.PlaygroundProxyError):
        proxy.forward(runtime.id, 'GET', '/api/v1/items')


def test_status_does_not_certify_health_after_container_replacement(runtime, monkeypatch):
    runtime.started = True
    original = local_runtime.inspect_session(runtime.id)
    replacement = original.model_copy(update={'containerId': 'replacement'})
    inspections = iter([original, replacement])
    monkeypatch.setattr(local_runtime, 'inspect_session', lambda _: next(inspections))
    row = service.get_deployment_status(runtime.id)
    assert row.status == Status.DEGRADED and row.testUrl is None
    assert 'durante' in row.errorMessage


def test_smoke_never_follows_health_redirect_to_a_different_service(runtime, monkeypatch):
    runtime.started = True
    original = local_runtime.inspect_session(runtime.id)
    monkeypatch.setattr(service, 'get_deployment_status', lambda _: original)
    calls = []
    def redirected(url, **kwargs):
        assert url.startswith('http://127.0.0.1:')
        calls.append(kwargs)
        return SimpleNamespace(status_code=302, json=lambda: {'status': 'UP'})
    monkeypatch.setattr(service.requests, 'get', redirected)
    assert not service.run_smoke_test(runtime.id, max_retries=1, interval=0).passed
    assert calls[0]['allow_redirects'] is False


@pytest.mark.parametrize('change', ['container', 'port', 'database', 'stopped'])
def test_smoke_does_not_certify_http_response_after_runtime_change(runtime, monkeypatch, change):
    runtime.started = True
    original = local_runtime.inspect_session(runtime.id)
    changed = original.model_copy(deep=True)
    if change == 'container': changed.containerId = 'replacement'
    if change == 'port': changed.hostPort += 1
    if change == 'database': changed.databaseContainerId = 'replacement-db'
    if change == 'stopped': changed.status = Status.STOPPED
    monkeypatch.setattr(service, 'get_deployment_status', lambda _: original)
    inspections = iter([original, changed])
    monkeypatch.setattr(local_runtime, 'inspect_session', lambda _: next(inspections))
    result = service.run_smoke_test(runtime.id, max_retries=1, interval=0)
    assert not result.passed and 'durante' in result.details


@pytest.mark.parametrize('change', ['container', 'port', 'database', 'stopped'])
def test_playground_discards_response_after_runtime_change(monkeypatch, change):
    original = LocalDeploymentSession(sessionId='s', containerId='a', status=Status.HEALTHY, hostPort=18321)
    changed = original.model_copy(deep=True)
    if change == 'container': changed.containerId = 'b'
    if change == 'port': changed.hostPort += 1
    if change == 'database': changed.databaseContainerId = 'b'
    if change == 'stopped': changed.status = Status.STOPPED
    states = iter([original, changed])
    monkeypatch.setattr(proxy, 'get_deployment_status', lambda _: next(states))
    request = Mock(return_value=SimpleNamespace(content=b'{"name":"foreign"}', status_code=200, headers={}))
    monkeypatch.setattr(proxy.requests, 'request', request)
    result = proxy.forward('s', 'POST', '/api/v1/items', {'name': 'new'})
    assert result['statusCode'] is None and result['body'] is None
    assert 'pudo ejecutarse' in result['error']
    assert request.call_args.args[1] == 'http://127.0.0.1:18321/api/v1/items'


def test_port_bind_race_retries_with_override_and_informs(runtime, monkeypatch):
    execute = service.run_logged
    starts = []
    def race(command, on_line, **kwargs):
        if 'up' in command:
            starts.append(kwargs['env']['HOST_PORT'])
            if len(starts) == 1:
                raise RuntimeError('port is already allocated')
        return execute(command,on_line,**kwargs)
    monkeypatch.setattr(service,'run_logged',race)
    monkeypatch.setattr(local_runtime, 'available_port', lambda preferred: preferred)
    row = service.deploy_local(runtime.id, str(runtime.ws), host_port=18080)
    runtime.workers[0]()
    assert row.status == Status.HEALTHY and row.hostPort == 18081
    assert starts == ['18080', '18081'] and '18081' in row.message


def test_port_conflicts_are_bounded_and_do_not_start_unrelated_service(runtime, monkeypatch):
    execute = service.run_logged
    starts = []
    def occupied(command, on_line, **kwargs):
        if 'up' in command:
            starts.append(kwargs['env']['HOST_PORT'])
            raise RuntimeError('ports are not available')
        return execute(command,on_line,**kwargs)
    monkeypatch.setattr(service,'run_logged',occupied)
    monkeypatch.setattr(local_runtime, 'available_port', lambda preferred: preferred)
    row = service.deploy_local(runtime.id, str(runtime.ws), host_port=18080)
    runtime.workers[0]()
    assert row.status == Status.FAILED and starts == ['18080', '18081', '18082']
    assert not runtime.started and not service._operation_locks[runtime.id].locked()
    assert not any('stop' in command or 'rm' in command for command in runtime.commands)
