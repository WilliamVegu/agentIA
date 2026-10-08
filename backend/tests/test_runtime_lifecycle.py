import json
import threading
from types import SimpleNamespace
import pytest
from app.models.devops import DeploymentStatus, LocalDeploymentSession
from app.services import docker_service as service, runtime_lifecycle as lifecycle
from app.services.local_runtime import persist
from test_local_docker_runtime import runtime


def test_restart_uses_existing_image_offline_and_survives_registry_reload(runtime):
    persist(LocalDeploymentSession(sessionId=runtime.id, containerId='old', hostPort=18080, status=DeploymentStatus.STOPPED))
    service._active_deployments.clear()
    row = lifecycle.restart_local(runtime.id, str(runtime.ws))
    assert row.status == DeploymentStatus.BUILDING
    runtime.workers[0]()
    assert row.status == DeploymentStatus.HEALTHY and row.hostPort == 18080
    commands = runtime.commands
    assert not any('build' in command or 'pull' == command[1] for command in commands)
    assert any('--no-build' in command and '--pull' in command and 'never' in command for command in commands)
    assert not service._operation_locks[runtime.id].locked()


def test_restart_failure_is_recorded_and_lock_released(runtime):
    (runtime.ws / 'docker-compose.yml').write_text('services: {}')
    row = lifecycle.restart_local(runtime.id, str(runtime.ws))
    runtime.workers[0]()
    assert row.status == DeploymentStatus.FAILED and 'imagen' in row.errorMessage
    assert not service._operation_locks[runtime.id].locked()


def test_source_only_restart_cleanup_never_query_docker(runtime, monkeypatch):
    monkeypatch.setattr(lifecycle, 'execution_mode', lambda _: SimpleNamespace(value='SOURCE_ONLY'))
    monkeypatch.setattr('app.services.execution_policy.execution_mode', lambda *_: SimpleNamespace(value='SOURCE_ONLY'))
    monkeypatch.setattr(service.subprocess, 'run', lambda *_a, **_k: pytest.fail('SOURCE_ONLY called Docker'))
    assert lifecycle.restart_local(runtime.id, str(runtime.ws)).status == DeploymentStatus.SKIPPED_BY_CHOICE
    assert lifecycle.cleanup_local(runtime.id, True).status == DeploymentStatus.SKIPPED_BY_CHOICE


def test_cleanup_requires_confirmation_before_any_mutation(runtime):
    with pytest.raises(ValueError, match='deleteData'): lifecycle.cleanup_local(runtime.id)
    assert not runtime.commands


def test_foreign_identity_prevents_stop_and_cleanup(runtime):
    runtime.started, runtime.foreign = True, True
    assert service.stop_deployment(runtime.id, str(runtime.ws)).status == DeploymentStatus.FAILED
    with pytest.raises(RuntimeError,match="Identidad ajena"):
        lifecycle.cleanup_local(runtime.id, True)
    assert not any(command[1] in ('stop', 'rm') for command in runtime.commands)


def test_cleanup_scopes_containers_volumes_networks_and_checks_absence(runtime, monkeypatch):
    state = {'container': [{'Id': 'own-container'}], 'volume': [{'Name': 'own-volume'}], 'network': [{'Id': 'own-network'}]}
    commands = []
    monkeypatch.setattr(lifecycle, 'owned_resources', lambda sid, kind='container': state[kind])
    def run(command, **kwargs):
        commands.append(command)
        if command[1] == 'rm': state['container'] = []
        else: state[command[1]] = []
    monkeypatch.setattr(lifecycle, '_command', run)
    preview=lifecycle.cleanup_preview(runtime.id)
    row = lifecycle.cleanup_local(runtime.id, True, confirmation=preview["confirmationToken"])
    assert row.status == DeploymentStatus.STOPPED and row.containerId is None
    assert commands == [['docker', 'rm', '-f', 'own-container'], ['docker', 'volume', 'rm', 'own-volume'], ['docker', 'network', 'rm', 'own-network']]


def test_cleanup_busy_does_not_mutate_resources(runtime):
    lock = threading.Lock(); lock.acquire()
    service._operation_locks[runtime.id] = lock
    preview=lifecycle.cleanup_preview(runtime.id)
    try: assert lifecycle.cleanup_local(runtime.id, True,confirmation=preview["confirmationToken"]).status == DeploymentStatus.BUILDING
    finally: lock.release()
    assert not any(command[1] in ('stop','rm') or 'rm' in command[2:] for command in runtime.commands)


def test_lifecycle_routes_validate_session_and_cleanup_confirmation(runtime, monkeypatch):
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
    from app.api import routes_devops as routes
    def resolve(identity):
        if identity != runtime.id: raise HTTPException(404, 'Missing session')
        return runtime.ws, 'probe-service'
    monkeypatch.setattr(routes, '_resolve_session_context', resolve)
    monkeypatch.setattr(lifecycle, 'restart_local', lambda sid, workspace: LocalDeploymentSession(sessionId=sid, status=DeploymentStatus.BUILDING))
    app = FastAPI(); app.include_router(routes.router)
    with TestClient(app) as client:
        assert client.post(f'/devops/{runtime.id}/restart').json()['status'] == 'BUILDING'
        assert client.post(f'/devops/{runtime.id}/cleanup', json={}).status_code == 400
        assert client.post('/devops/missing/restart').status_code == 404
        assert client.post('/devops/missing/cleanup', json={'deleteData': True}).status_code == 404
    assert not runtime.commands


def test_daemon_unavailable_preserves_identity_without_claiming_stopped(runtime, monkeypatch):
    row = LocalDeploymentSession(sessionId=runtime.id, containerId='known-own', hostPort=19111, status=DeploymentStatus.HEALTHY, healthStatus='UP', testUrl='http://localhost:19111/actuator/health')
    persist(row)
    monkeypatch.setattr(service, 'check_docker_daemon', lambda: False)
    result = service.get_deployment_status(runtime.id)
    assert result.status == DeploymentStatus.DOCKER_UNAVAILABLE and result.healthStatus == 'UNKNOWN'
    assert result.containerId == 'known-own' and result.hostPort == 19111 and result.testUrl is None


@pytest.mark.parametrize('application', [False, True])
def test_recovery_distinguishes_orphan_database_and_crashed_application(runtime, monkeypatch, application):
    def run(command, **kwargs):
        if command[1] == 'ps': return SimpleNamespace(returncode=0, stdout='own')
        container = {'Id': 'own', 'Config': {'Labels': {'com.docker.compose.project': runtime.id, 'io.agentia.owner': runtime.id, 'io.agentia.studio': 'springboot', 'io.agentia.role': 'application' if application else 'database'}},
                     'State': {'Running': not application, 'ExitCode': 2},
                     'HostConfig': {'PortBindings': {'8080/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '18080'}]}}}
        return SimpleNamespace(returncode=0, stdout=json.dumps([container]))
    monkeypatch.setattr(service.subprocess, 'run', run)
    from app.services.local_runtime import inspect_session
    row = inspect_session(runtime.id)
    assert row.status == (DeploymentStatus.FAILED if application else DeploymentStatus.DEGRADED)
    assert row.healthStatus == 'DOWN'


def test_runtime_recovers_from_sqlite_after_projection_deleted_or_tampered(runtime):
    from app.services.local_runtime import restore
    row=LocalDeploymentSession(sessionId=runtime.id,operationId='durable-runtime',status=DeploymentStatus.STOPPED,hostPort=19111)
    persist(row)
    projection=runtime.ws/'.agentia-runtime/deployment.json'
    projection.unlink()
    assert restore(runtime.id).hostPort==19111
    projection.write_text(row.model_copy(update={'hostPort':8080,'status':DeploymentStatus.HEALTHY}).model_dump_json(),encoding='utf-8')
    restored=restore(runtime.id)
    assert restored.hostPort==19111 and restored.status==DeploymentStatus.STOPPED


def test_late_runtime_callback_never_replaces_new_operation(runtime):
    from app.services.local_runtime import restore
    first=LocalDeploymentSession(sessionId=runtime.id,operationId='old-runtime',status=DeploymentStatus.STOPPED)
    persist(first)
    second=first.model_copy(update={'operationId':'new-runtime','status':DeploymentStatus.FAILED})
    persist(second)
    first.status=DeploymentStatus.HEALTHY
    assert persist(first) is False
    restored=restore(runtime.id)
    assert restored.operationId=='new-runtime' and restored.status==DeploymentStatus.FAILED


def test_legacy_project_label_alone_does_not_authorize_mutation(runtime,monkeypatch):
    original=service.subprocess.run
    def legacy(command,**kwargs):
        result=original(command,**kwargs)
        if command[:2]==['docker','inspect']:
            resources=json.loads(result.stdout)
            for item in resources:
                item['Config']['Labels'].pop('io.agentia.owner',None)
                item['Config']['Labels'].pop('io.agentia.studio',None)
            result.stdout=json.dumps(resources)
        return result
    runtime.started=True
    monkeypatch.setattr(service.subprocess,'run',legacy)
    with pytest.raises(RuntimeError,match='legacy'): lifecycle.cleanup_preview(runtime.id)
    assert service.stop_deployment(runtime.id,str(runtime.ws)).status==DeploymentStatus.FAILED
    assert not any(command[1] in {'stop','rm'} for command in runtime.commands)
