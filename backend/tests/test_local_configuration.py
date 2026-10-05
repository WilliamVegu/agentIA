from scripts.local_microservice_fixture import create_fixture
import json
import os
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace
import pytest
from app.services.local_configuration import resolve_configuration
from app.services.devops_service import generate_all_devops_assets
from app.sandbox.docker_runner import build_docker_cmd
from app.models.session import SessionLocal, GenerationSessionDB, SessionStatus
from test_local_docker_runtime import runtime
from test_local_execution_mode import session_workspace, forbid_docker


def test_regeneration_keeps_project_database_and_port(runtime):
    generate_all_devops_assets(str(runtime.ws), runtime.id, db_engine='H2', host_port=18081)
    # Session defaults differ from the explicit project settings.
    with SessionLocal() as db:
        db.get(GenerationSessionDB, runtime.id).database_engine = 'POSTGRESQL'
        db.commit()
    generate_all_devops_assets(str(runtime.ws), runtime.id)
    config = resolve_configuration(runtime.ws, runtime.id)
    assert (config['databaseEngine'], config['hostPort']) == ('H2', 18081)
    assert '18081' in (runtime.ws / 'docker-compose.yml').read_text()
    assert resolve_configuration(runtime.ws, runtime.id, database='MYSQL', port=18082)['databaseEngine'] == 'MYSQL'


def test_configuration_endpoint_reads_sources_without_docker(session_workspace, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    identity, ws = session_workspace
    generate_all_devops_assets(str(ws), identity, db_engine='H2', host_port=18081)
    forbidden = forbid_docker(monkeypatch)
    monkeypatch.setenv('STUDIO_USER_EMAIL', 'configuration@test.local')
    monkeypatch.setenv('STUDIO_ACCESS_TOKEN', 'test-local-password-01')
    with TestClient(app) as client:
        assert client.get(f'/api/v1/devops/{identity}/configuration').status_code == 401
        assert client.post('/api/v1/auth/login', json={'email': 'configuration@test.local', 'password': 'test-local-password-01'}).status_code == 200
        result = client.get(f'/api/v1/devops/{identity}/configuration')
        client.post('/api/v1/auth/logout')
    assert result.status_code == 200
    assert result.json() == {'databaseEngine': 'H2', 'hostPort': 18081, 'buildTool': 'maven', 'buildDirectory': '.'}
    forbidden.assert_not_called()


def test_deploy_without_port_uses_saved_port(runtime):
    from app.services import docker_service
    generate_all_devops_assets(str(runtime.ws), runtime.id, db_engine='H2', host_port=18083)
    result = docker_service.deploy_local(runtime.id, str(runtime.ws))
    runtime.workers[0]()
    assert result.hostPort >= 18083 and result.status.value == 'HEALTHY'


@pytest.mark.parametrize('manifest,tool', [('pom.xml', 'maven'), ('build.gradle', 'gradle'), ('build.gradle.kts', 'gradle')])
@pytest.mark.parametrize('prepared', [True, False])
def test_sandbox_uses_module_build_entry(tmp_path, manifest, tool, prepared):
    (tmp_path / 'bootstrap').mkdir()
    (tmp_path / 'bootstrap' / manifest).write_text('<project/>' if tool == 'maven' else 'plugins {}')
    command = build_docker_cmd(str(tmp_path), str(tmp_path / 'cache'), 'agentia-builder:test', prepared)
    assert command[command.index('-w') + 1] == '/workspace/bootstrap'
    assert ('gradle' in ' '.join(command)) == (tool == 'gradle')
    assert command[command.index('--pull') + 1] == 'never'
    assert command[command.index('--network') + 1] == 'none'


@pytest.mark.parametrize('invalid', ['foreign', 'json', 'port', 'engine', 'missing'])
def test_invalid_saved_config_does_not_fall_back_to_defaults(runtime, invalid):
    path = runtime.ws / 'ASSET_CONFIGURATION.json'
    config = json.loads(path.read_text())
    if invalid == 'foreign': config['sessionId'] = 'foreign'
    if invalid == 'port': config['hostPort'] = True
    if invalid == 'engine': config['databaseEngine'] = 'INVALID'
    if invalid == 'missing': config.pop('databaseEngine')
    path.write_text('invalid json' if invalid == 'json' else json.dumps(config))
    with pytest.raises(ValueError, match='inválida'):
        resolve_configuration(runtime.ws, runtime.id)


@pytest.mark.parametrize('manifest', ['pom.xml', 'build.gradle', 'build.gradle.kts'])
def test_source_delivery_verification_accepts_bootstrap_without_docker(session_workspace, monkeypatch, manifest):
    from app.services.session_execution import verify_existing_sources
    from app.services.verification_policy import session_allows_source_delivery, session_is_verified
    identity, ws = session_workspace
    (ws / 'pom.xml').unlink()
    (ws / 'bootstrap/src/main/java').mkdir(parents=True)
    (ws / 'bootstrap' / manifest).write_text('<project><dependencies></dependencies></project>' if manifest == 'pom.xml' else 'plugins {}')
    (ws / 'bootstrap/src/main/java/App.java').write_text('class App {}')
    monkeypatch.setattr('app.services.security_service.audit_workspace', lambda *a: SimpleNamespace(qualityGate=SimpleNamespace(canExport=True)))
    with SessionLocal() as db:
        db.get(GenerationSessionDB, identity).status = SessionStatus.PAUSED
        db.commit()
    forbidden = forbid_docker(monkeypatch)
    assert verify_existing_sources(identity)['status'] == 'COMPLETED'
    with SessionLocal() as db:
        row = db.get(GenerationSessionDB, identity)
        assert session_allows_source_delivery(row) and not session_is_verified(row)
    forbidden.assert_not_called()


@pytest.mark.asyncio
async def test_preparation_uses_project_database_and_preserves_port(runtime, monkeypatch):
    from app.api import routes_devops
    generate_all_devops_assets(str(runtime.ws), runtime.id, db_engine='H2', host_port=18084)
    monkeypatch.setattr(routes_devops, 'audit_workspace', lambda *a: SimpleNamespace(qualityGate=SimpleNamespace(canExport=True)))
    monkeypatch.setattr('app.services.local_preparation.prepare_local', lambda identity, workspace, database: database)
    assert await routes_devops.prepare_environment(runtime.id) == 'H2'
    assert resolve_configuration(runtime.ws, runtime.id)['hostPort'] == 18084


@pytest.mark.skipif(os.environ.get('AGENTIA_RUN_REAL_DOCKER') != '1', reason='Docker real opt-in')
def test_real_prepared_sandbox_builds_maven_bootstrap():
    ws = Path('.run/real-bootstrap-sandbox', uuid.uuid4().hex).resolve()
    create_fixture(ws, layout='bootstrap', assets=False)
    command = build_docker_cmd(str(ws), 'unused-cache', 'agentia-builder:f3a47171af85acdfddd092dd', prepared=True)
    name = 'agentia-bootstrap-' + ws.name
    command[2:2] = ['--name', name, '--label', 'io.agentia.test=' + ws.name]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=90)
        (ws / 'sandbox.log').write_text(result.stdout + result.stderr, encoding='utf-8')
        assert result.returncode == 0, result.stdout[-3000:] + result.stderr
        assert 'Tests run: 8, Failures: 0, Errors: 0, Skipped: 0' in result.stdout
        assert 'BUILD SUCCESS' in result.stdout
        (ws / 'result.json').write_text(json.dumps({'result': 'PASS', 'buildDirectory': 'bootstrap', 'tests': 8,
            'offline': True, 'preparedDependencies': True}, indent=2))
    finally:
        inspected = subprocess.run(['docker', 'inspect', name], capture_output=True, text=True, timeout=10)
        if inspected.returncode == 0:
            metadata = json.loads(inspected.stdout)[0]
            assert metadata['Config']['Labels'].get('io.agentia.test') == ws.name
            subprocess.run(['docker', 'rm', '-f', metadata['Id']], capture_output=True, timeout=10, check=True)
