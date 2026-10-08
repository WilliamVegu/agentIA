import json
from types import SimpleNamespace
import pytest
from app.services import runtime_lifecycle as lifecycle


def test_stop_only_owned_containers_never_deletes_data(monkeypatch):
    project = lifecycle.compose_project('test-session')
    identifier = 'a' * 64
    running = True
    commands = []
    def run(args, **kwargs):
        nonlocal running
        commands.append(args)
        if args[1] == 'ps':
            output = identifier
        elif args[1] == 'inspect':
            output = json.dumps([{'Id': identifier, 'State': {'Running': running}, 'Config': {'Labels': {
                'com.docker.compose.project': project, 'io.agentia.owner': project, 'io.agentia.studio': 'quarkus'}}}])
        elif args[1] == 'stop':
            running = False
            output = ''
        else:
            raise AssertionError('Unexpected mutation')
        return SimpleNamespace(returncode=0, stdout=output, stderr='')
    monkeypatch.setattr(lifecycle.subprocess, 'run', run)
    lifecycle.stop_owned('test-session')
    assert not running
    assert all('down' not in args and '-v' not in args and 'rm' not in args for args in commands)


def test_foreign_resource_and_error_are_not_success(monkeypatch):
    identifier = 'a' * 64
    def run(args, **kwargs):
        output = identifier if args[1] == 'ps' else json.dumps([{'Id': identifier, 'Config': {'Labels': {}}}])
        return SimpleNamespace(returncode=0, stdout=output, stderr='')
    monkeypatch.setattr(lifecycle.subprocess, 'run', run)
    with pytest.raises(RuntimeError, match='unowned'):
        lifecycle.stop_owned('test-session')
    monkeypatch.setattr(lifecycle.subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=1, stderr='failure', stdout=''))
    with pytest.raises(RuntimeError, match='failure'):
        lifecycle.stop_owned('test-session')


def test_cleanup_requires_current_preview_and_explicit_opt_in(monkeypatch):
    monkeypatch.setattr(lifecycle, 'owned_resources', lambda *args: [])
    with pytest.raises(ValueError, match='deleteData'):
        lifecycle.cleanup_owned('test-session')
    with pytest.raises(ValueError, match='confirmation'):
        lifecycle.cleanup_owned('test-session', delete_data=True)
    preview = lifecycle.cleanup_preview('test-session')
    assert lifecycle.cleanup_owned('test-session', delete_data=True, confirmation=preview['confirmationToken']) == preview


def test_public_stop_does_not_hide_docker_failure(monkeypatch, tmp_path):
    from app.services import docker_service
    from app.config import settings
    monkeypatch.setattr(settings, 'WORKSPACE_DIR', str(tmp_path / 'workspaces'))
    from app.models.session import SessionLocal,GenerationSessionDB
    from app.models.execution import ExecutionMode
    with SessionLocal() as db:
        db.add(GenerationSessionDB(id='stop-failure-test',spec_id='stop-failure',spec_name='Stop',execution_mode=ExecutionMode.DOCKER))
        db.commit()
    calls = []
    def fail(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=1, stdout='', stderr='daemon unavailable')
    monkeypatch.setattr(docker_service.subprocess, 'run', fail)
    result = docker_service.stop_deployment('stop-failure-test', str(tmp_path))
    assert result.status.value == 'FAILED'
    assert result.errorMessage
    assert all('-v' not in args for args in calls)


from integration.runtime_data_safety_cases import run_db_conservation

@pytest.mark.parametrize("engine_name", ["POSTGRESQL", "MYSQL"])
def test_real_stop_restart_preserves_records(engine_name, tmp_path, monkeypatch):
    run_db_conservation(engine_name, tmp_path, monkeypatch)
