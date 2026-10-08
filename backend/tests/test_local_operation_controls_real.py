"""Real local CLI interruption and scoped stop; explicitly not BuildKit cancellation proof."""
import json
import os
import subprocess
import uuid
from pathlib import Path
import pytest
from app.config import settings
from app.models.devops import LocalDeploymentSession, DeploymentStatus
from app.models.session import GenerationSessionDB, SessionLocal, SessionStatus
from app.services import docker_service, local_operations, logged_process, runtime_lifecycle

pytestmark = pytest.mark.skipif(os.environ.get('AGENTIA_RUN_REAL_DOCKER') != '1', reason='Docker real opt-in')


def test_cli_cancel_is_honest_and_scoped_stop_preserves_volume_and_other_project(monkeypatch):
    identity, other = str(uuid.uuid4()), str(uuid.uuid4())
    root = Path('.run/real-operation-controls').resolve()
    ws = root / identity; ws.mkdir(parents=True)
    monkeypatch.setattr(settings, 'WORKSPACE_DIR', str(root))
    monkeypatch.setattr(settings, 'DOCKER_ENABLED', True)
    image = 'agentia-runtime:21-v1'
    volume = identity + '-probe-data'
    report = {'session': identity, 'otherTestProject': other, 'result': 'RUNNING'}
    def docker(*args):
        result = subprocess.run(['docker', *args], capture_output=True, text=True, timeout=30, check=False)
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()
    with SessionLocal() as db:
        db.add(GenerationSessionDB(id=identity, spec_id='test', spec_name='operation-probe',
                                   execution_mode='DOCKER', status=SessionStatus.PAUSED)); db.commit()
    row = LocalDeploymentSession(sessionId=identity, status=DeploymentStatus.BUILDING, operationId=str(uuid.uuid4()))
    control = local_operations.register(row, 'DEPLOY')
    docker_service._active_deployments[identity] = row
    try:
        report['imageId'] = docker('image', 'inspect', image, '--format', '{{.Id}}')
        docker('volume', 'create', '--label', f'com.docker.compose.project={identity}','--label',f'io.agentia.owner={identity}','--label','io.agentia.studio=springboot', volume)
        main = docker('run', '-d', '--pull', 'never', '--network', 'none',
            '--label', f'com.docker.compose.project={identity}','--label',f'io.agentia.owner={identity}','--label','io.agentia.studio=springboot', '--label', 'io.agentia.role=application',
            '-v', f'{volume}:/probe-data', image, 'sh', '-c', 'sleep 300')
        foreign = docker('run', '-d', '--pull', 'never', '--network', 'none',
            '--label', f'com.docker.compose.project={other}', '--label', 'io.agentia.role=application',
            image, 'sh', '-c', 'sleep 300')
        native_spawn = subprocess.Popen
        def spawn(command, **kwargs):
            process = native_spawn(command, **kwargs)
            if command[:2] == ['docker', 'wait']:
                local_operations.request_cancel(identity, row.operationId)
            return process
        with monkeypatch.context() as scoped:
            scoped.setattr(logged_process.subprocess, 'Popen', spawn)
            with pytest.raises(logged_process.CommandCancelled):
                logged_process.run_logged(['docker', 'wait', main], lambda _: None, cancel_event=control, timeout=10)
        # Killing the client does not imply the daemon stopped its container.
        assert docker('inspect', main, '--format', '{{.State.Running}}') == 'true'
        runtime_lifecycle.stop_interrupted_runtime(identity)
        assert docker('inspect', main, '--format', '{{.State.Running}}') == 'false'
        assert docker('inspect', foreign, '--format', '{{.State.Running}}') == 'true'
        assert docker('volume', 'inspect', volume, '--format', '{{.Name}}') == volume
        assert docker('image', 'inspect', image, '--format', '{{.Id}}') == report['imageId']
        report.update(result='PASS', cliInterrupted=True, daemonStopNotAssumed=True,
                      ownedStopConfirmed=True, otherProjectUnaffected=True, volumePreserved=True)
    finally:
        local_operations.finish(row)
        # Both UUIDs belong to this test, and every resource is inspected before removal.
        for project in (identity, other):
            containers = runtime_lifecycle.owned_resources(project)
            if containers: docker('rm', '-f', *[item['Id'] for item in containers])
            volumes = runtime_lifecycle.owned_resources(project, 'volume')
            if volumes: docker('volume', 'rm', *[item['Name'] for item in volumes])
            assert not runtime_lifecycle.owned_resources(project)
            assert not runtime_lifecycle.owned_resources(project, 'volume')
        report['cleanup'] = 'CONFIRMED'
        docker_service._active_deployments.pop(identity, None)
        with SessionLocal() as db:
            db.query(GenerationSessionDB).filter_by(id=identity).delete(); db.commit()
        (ws / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
