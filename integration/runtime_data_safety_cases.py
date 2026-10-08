"""Real DB conservation; every Docker resource is created and labelled by this test."""
import json
import os
import subprocess
import time
import uuid
from pathlib import Path
import pytest


def docker(*args, check=True):
    result = subprocess.run(['docker', *args], capture_output=True, text=True, timeout=90)
    if check and result.returncode:
        raise AssertionError(result.stderr or result.stdout)
    return result.stdout.strip()


def assert_owned(identifier, run_id, kind='container'):
    args = ['inspect', identifier] if kind == 'container' else [kind, 'inspect', identifier]
    items = json.loads(docker(*args))
    labels = items[0].get('Config', {}).get('Labels', {}) if kind == 'container' else items[0].get('Labels', {})
    assert labels.get('agentia.reliability-test') == run_id, 'Never mutate unowned resources'


def run_db_conservation(engine_name, tmp_path, monkeypatch):
    from app.config import settings
    from app.models.session import SessionLocal, GenerationSessionDB, SessionStatus
    from app.services import docker_service
    from app.services import runtime_lifecycle
    if os.environ.get('RUN_RELIABILITY_DOCKER') != '1':
        pytest.skip('Real Docker fixture requires RUN_RELIABILITY_DOCKER=1')
    run_id = uuid.uuid4().hex
    session_id = 'reliability-' + run_id
    quarkus = 'quarkus' in str(Path(docker_service.__file__).resolve()).lower()
    project = runtime_lifecycle.compose_project(session_id) if quarkus else session_id
    container_name, volume_name = 'reliability-' + run_id, 'reliability-' + run_id + '-data'
    monkeypatch.setattr(settings, 'WORKSPACE_DIR', str(tmp_path / 'workspaces'))
    workspace = tmp_path / 'workspaces' / session_id
    workspace.mkdir(parents=True)
    with SessionLocal() as db:
        db.add(GenerationSessionDB(id=session_id, spec_id=run_id, spec_name='Conservation fixture',
                                 status=SessionStatus.COMPLETED, execution_mode='DOCKER'))
        db.commit()
    labels = ['--label', 'agentia.reliability-test=' + run_id,
              '--label', 'com.docker.compose.project=' + project,
              '--label', 'io.agentia.owner=' + project,
              '--label', 'io.agentia.studio=' + ('quarkus' if quarkus else 'springboot'),
              '--label', 'io.agentia.role=database']
    container = None
    volume_created = False
    try:
        docker('volume', 'create', *labels, volume_name)
        volume_created = True
        if engine_name == 'POSTGRESQL':
            args = ['-e', 'POSTGRES_USER=fixture', '-e', 'POSTGRES_PASSWORD=fixture-password', '-e', 'POSTGRES_DB=fixture']
            mount, image = '/var/lib/postgresql/data', 'postgres:16.4-alpine'
            def sql(statement):
                return docker('exec', container, 'psql', '-U', 'fixture', '-d', 'fixture', '-At', '-c', statement)
        else:
            args = ['-e', 'MYSQL_ROOT_PASSWORD=fixture-password', '-e', 'MYSQL_DATABASE=fixture']
            mount, image = '/var/lib/mysql', 'mysql:8.0.40'
            def sql(statement):
                return docker('exec', container, 'mysql', '-uroot', '-pfixture-password', '-Dfixture', '-Nse', statement)
        container = docker('run', '-d', '--name', container_name, *labels, *args, '-v', volume_name + ':' + mount, image)
        assert_owned(container, run_id)
        def ready():
            deadline = time.monotonic() + 90
            while True:
                try:
                    sql('SELECT 1')
                    return
                except AssertionError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(1)
        ready()
        sql("CREATE TABLE reliability_record (value VARCHAR(100)); INSERT INTO reliability_record VALUES ('preserved')")
        stopped = docker_service.stop_deployment(session_id, str(workspace))
        assert stopped.status.value == 'STOPPED', stopped.errorMessage
        assert_owned(volume_name, run_id, 'volume')
        assert_owned(container, run_id)
        docker('start', container)
        ready()
        assert sql('SELECT value FROM reliability_record') == 'preserved'
    finally:
        if container:
            assert_owned(container, run_id)
            docker('rm', '-f', container)
        if volume_created:
            assert_owned(volume_name, run_id, 'volume')
            docker('volume', 'rm', volume_name)
        with SessionLocal() as db:
            db.query(GenerationSessionDB).filter_by(id=session_id).delete()
            db.commit()
