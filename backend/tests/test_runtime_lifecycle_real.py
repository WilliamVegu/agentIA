"""Opt-in real Spring/H2 restart using an existing local fixture image; no builds/pulls."""
import json
import os
import socket
import subprocess
import threading
import uuid
from pathlib import Path
import pytest
import requests
from app.config import settings
from app.models.devops import DeploymentStatus
from app.models.session import SessionLocal, GenerationSessionDB, SessionStatus
from app.services import docker_service as service, runtime_lifecycle as lifecycle
from app.services.local_deployment_assets import compose
from app.services.lifecycle_scripts import write_lifecycle_scripts

pytestmark = pytest.mark.skipif(os.environ.get('AGENTIA_RUN_REAL_DOCKER') != '1', reason='Docker real opt-in')


def test_restart_preserves_h2_identity_and_resolves_port_then_explicit_cleanup(monkeypatch):
    identity = str(uuid.uuid4())
    root = Path('.run/real-lifecycle').resolve()
    ws = root / identity
    ws.mkdir(parents=True)
    image = os.environ.get('AGENTIA_LIFECYCLE_FIXTURE_IMAGE', 'agentia-isolation-6bc4bff2ad-a-probe-service:local')
    target = identity + '-probe-service:local'
    report = {'result': 'RUNNING', 'session': identity, 'sourceImage': image, 'checks': []}
    monkeypatch.setattr(settings, 'WORKSPACE_DIR', str(root))
    monkeypatch.setattr(service, '_active_deployments', {})
    monkeypatch.setattr(service, '_raw_log_history', {})
    monkeypatch.setattr('app.services.runtime_log_capture.ensure_capture', lambda _: None)
    def docker(*command, cwd=ws, env=None):
        return subprocess.check_output(['docker', *command], cwd=cwd, env=env, text=True, stderr=subprocess.STDOUT, timeout=200).strip()
    with SessionLocal() as db:
        db.add(GenerationSessionDB(id=identity, spec_id='probe', spec_name='probe-service', execution_mode='DOCKER', status=SessionStatus.PAUSED)); db.commit()
    occupied = socket.socket()
    try:
        report['imageId'] = docker('image', 'inspect', image, '--format', '{{.Id}}')
        docker('image', 'tag', image, target)
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0)); port = probe.getsockname()[1]
        if port > 65400: pytest.skip('Port too close to upper range')
        (ws / 'docker-compose.yml').write_text(compose('probe-service', 'H2', port), encoding='utf-8')
        docker('compose', '-p', identity, 'up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '180')
        initial = service.get_deployment_status(identity)
        assert initial.status == DeploymentStatus.HEALTHY and initial.dbEngine == 'H2'
        created = requests.post(f'http://localhost:{port}/api/v1/items', json={'name': 'restart-marker'}, timeout=5)
        assert created.status_code == 201
        record_id = created.json()['id']
        assert service.stop_deployment(identity, str(ws)).status == DeploymentStatus.STOPPED
        service._active_deployments.clear()
        assert service.get_deployment_status(identity).status == DeploymentStatus.STOPPED
        # Occupy the previous port without altering any unrelated service.
        occupied.bind(('127.0.0.1', port)); occupied.listen()
        restarted = lifecycle.restart_local(identity, str(ws))
        restarted = service.wait_for_deployment(identity, timeout=90)
        assert restarted.status == DeploymentStatus.HEALTHY, restarted.errorMessage
        assert restarted.containerId != initial.containerId and restarted.hostPort != port
        assert restarted.dbEngine == 'H2' and 'Puerto ocupado' in restarted.message
        metadata = json.loads(docker('inspect', restarted.containerId))[0]
        assert metadata['Image'] == report['imageId']
        record = requests.get(f'http://localhost:{restarted.hostPort}/api/v1/items/{record_id}', timeout=5)
        assert record.status_code == 200 and record.json()['name'] == 'restart-marker'
        from app.services.playground_proxy import forward
        forwarded = forward(identity, 'GET', f'/api/v1/items/{record_id}')
        assert forwarded['statusCode'] == 200 and forwarded['body']['name'] == 'restart-marker'
        assert forwarded['url'].startswith(f'http://127.0.0.1:{restarted.hostPort}/')
        assert service.run_smoke_test(identity, host_port=port, max_retries=1, interval=0).passed
        report['checks'] = ['STOPPED after registry reload', 'new container/same image', 'occupied port informed',
                            'H2 record preserved', 'health and effective engine/port', 'no build/pull',
                            'operation wait completed after readiness', 'playground and smoke use effective inspected port']
        # Standalone Windows scripts operate on the same exact project/data without AgentIA.
        write_lifecycle_scripts(ws, identity)
        shell = r'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe'
        def script(name, *args):
            result = subprocess.run([shell, '-NoProfile', '-NonInteractive', '-File', str(ws / name), *args],
                cwd=ws, text=True, capture_output=True, timeout=200)
            (ws / (name + '.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
            assert result.returncode == 0, result.stdout + result.stderr
            return result.stdout
        script('stop-local.ps1')
        script('restart-local.ps1')
        current = service.get_deployment_status(identity)
        assert current.status == DeploymentStatus.HEALTHY
        assert requests.get(f'http://localhost:{current.hostPort}/api/v1/items/{record_id}', timeout=5).json()['name'] == 'restart-marker'
        report['checks'].append('standalone PowerShell stop/restart/readiness and data preserved')
        script('cleanup-local.ps1', '-DeleteData')
        result = lifecycle.cleanup_local(identity, True)  # API cleanup is idempotent after script cleanup.
        assert result.status == DeploymentStatus.STOPPED, result.errorMessage
        assert all(not lifecycle.owned_resources(identity, kind) for kind in ('container', 'volume', 'network'))
        assert docker('image', 'inspect', image, '--format', '{{.Id}}') == report['imageId']
        report['checks'].append('explicit scoped cleanup; source image untouched')
        report['result'] = 'PASS'
    except Exception as exc:
        report['result'], report['error'] = 'FAILED', str(exc)
        raise
    finally:
        occupied.close()
        # Never let fixture teardown restore settings while its worker is still using them.
        lock = service._operation_locks.get(identity)
        if lock and lock.locked():
            released = lock.acquire(timeout=60)
            if released: lock.release()
            else: report['workerError'] = 'Operation did not finish before cleanup'
        try:
            cleanup = lifecycle.cleanup_local(identity, True)
            report['cleanup'] = cleanup.status.value
            if cleanup.status != DeploymentStatus.STOPPED: report['cleanupError'] = cleanup.errorMessage
        except Exception as exc: report['cleanupError'] = str(exc)
        subprocess.run(['docker', 'image', 'rm', target], capture_output=True, timeout=15, check=False)
        with SessionLocal() as db:
            db.query(GenerationSessionDB).filter_by(id=identity).delete(); db.commit()
        (ws / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
