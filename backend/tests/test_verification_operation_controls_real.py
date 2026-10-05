"""Real sandbox transport/cleanup; shell fixture, not a Maven or BuildKit build."""
import json
import os
import subprocess
import uuid
from pathlib import Path
import pytest
from app.config import settings
from app.models.session import GenerationSessionDB, SessionLocal, SessionStatus
from app.sandbox import docker_runner
from app.services import docker_service, local_operations, runtime_lifecycle, workspace_verification

pytestmark = pytest.mark.skipif(os.environ.get('AGENTIA_RUN_REAL_DOCKER') != '1', reason='Docker real opt-in')


def test_real_verification_cancel_and_timeout_remove_only_temporary_container(monkeypatch):
    identity, other = str(uuid.uuid4()), str(uuid.uuid4())
    root = Path('.run/real-verification-controls').resolve()
    ws = root / identity; ws.mkdir(parents=True)
    sentinel = ws / 'source.txt'; sentinel.write_text('preserve sources', encoding='utf-8')
    (ws / 'pom.xml').write_text('<project/>', encoding='utf-8')
    monkeypatch.setattr(settings, 'WORKSPACE_DIR', str(root))
    monkeypatch.setattr(settings, 'DOCKER_ENABLED', True)
    image = 'agentia-runtime:21-v1'
    report = {'session': identity, 'otherTestProject': other, 'fixture': 'shell, no build/pull', 'result': 'RUNNING'}
    def docker(*args):
        result = subprocess.run(['docker', *args], capture_output=True, text=True, timeout=30, check=False)
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()
    with SessionLocal() as db:
        db.add(GenerationSessionDB(id=identity, spec_id='test', spec_name='verification-probe',
            execution_mode='DOCKER', status=SessionStatus.PAUSED)); db.commit()
    monkeypatch.setattr('app.services.local_deployment_assets.builder_image', lambda _: image)
    monkeypatch.setattr(docker_runner, 'build_docker_cmd', lambda *args, **kwargs:
        ['docker', 'run', '--rm', '--pull', 'never', '--network', 'none', image,
         'sh', '-c', 'echo SANDBOX_READY; sleep 300'])
    try:
        report['imageId'] = docker('image', 'inspect', image, '--format', '{{.Id}}')
        foreign = docker('run', '-d', '--pull', 'never', '--network', 'none',
            '--label', f'com.docker.compose.project={other}', '--label', 'io.agentia.role=application',
            image, 'sh', '-c', 'sleep 300')
        def cancel_when_running(line):
            if line.strip() == 'SANDBOX_READY':
                row = docker_service._active_deployments[identity]
                assert runtime_lifecycle.owned_resources(identity)
                local_operations.request_cancel(identity, row.operationId)
        attempts = []
        for cause in ('cancel', 'timeout'):
            monkeypatch.setattr(settings, 'LOCAL_BUILD_TIMEOUT', 10 if cause == 'cancel' else 2)
            outcome = workspace_verification.run_workspace_verification(str(ws),
                log_callback=cancel_when_running if cause == 'cancel' else None)
            row = docker_service._active_deployments[identity]
            report['lastOutcome'] = outcome.result.model_dump()
            assert outcome.result.verification_interrupted and outcome.result.cleanup_confirmed, outcome.result.model_dump()
            assert not outcome.result.is_success
            assert row.finishedAt and row.operationPhase == 'INTERRUPTED'
            assert not docker_service._operation_locks[identity].locked()
            assert not runtime_lifecycle.owned_resources(identity)
            assert docker('inspect', foreign, '--format', '{{.State.Running}}') == 'true'
            assert sentinel.read_text(encoding='utf-8') == 'preserve sources'
            assert docker('image', 'inspect', image, '--format', '{{.Id}}') == report['imageId']
            attempts.append({'cause': cause, 'operationId': row.operationId, 'cleanupConfirmed': True,
                             'phase': row.operationPhase, 'notPassed': True})
        assert attempts[0]['operationId'] != attempts[1]['operationId']
        report.update(result='PASS', attempts=attempts, otherProjectUnaffected=True, sourcesAndImagePreserved=True)
    finally:
        for project in (identity, other):
            containers = runtime_lifecycle.owned_resources(project)
            if containers: docker('rm', '-f', *[item['Id'] for item in containers])
            assert not runtime_lifecycle.owned_resources(project)
        report['cleanup'] = 'CONFIRMED'
        docker_service._active_deployments.pop(identity, None)
        docker_service._operation_locks.pop(identity, None)
        with SessionLocal() as db:
            db.query(GenerationSessionDB).filter_by(id=identity).delete(); db.commit()
        (ws / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
