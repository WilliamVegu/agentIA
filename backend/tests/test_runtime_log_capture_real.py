"""Opt-in: real Docker log transport using only local images and own containers."""
import json
import os
import subprocess
import threading
import uuid
from pathlib import Path
from types import SimpleNamespace
import pytest
from app.config import settings
from app.services import docker_service as service, runtime_log_capture as capture

pytestmark = pytest.mark.skipif(os.environ.get('AGENTIA_RUN_REAL_DOCKER') != '1',
                              reason='Docker real opt-in; laboratorio no requiere Docker')


def test_real_container_logs_reconnect_restart_identity_and_source_mode(monkeypatch):
    identity = 'agentia-log-probe-' + uuid.uuid4().hex[:10]
    root = Path('.run/real-runtime-logs').resolve() / identity
    root.mkdir(parents=True)
    monkeypatch.setattr(settings, 'WORKSPACE_DIR', str(root))
    monkeypatch.setattr(service, '_raw_log_history', {})
    monkeypatch.setattr(capture, 'execution_mode', lambda _: SimpleNamespace(value='DOCKER'))
    containers = []
    report = {'result': 'RUNNING', 'session': identity, 'image': 'agentia-runtime:21-v1', 'checks': []}
    def docker(*args):
        return subprocess.check_output(['docker', *args], text=True, timeout=15).strip()
    try:
        docker('image', 'inspect', report['image'])
        for role in ('application', 'database'):
            name = identity + '-' + role
            docker('create', '--pull=never', '--name', name, '--network', 'none',
                '--label', f'com.docker.compose.project={identity}', '--label', f'io.agentia.role={role}',
                '--entrypoint', 'sh', report['image'], '-c',
                f'printf "{role}-first token=probe-secret\\n"; sleep 1; printf "{role}-second\\n"; sleep 60')
            containers.append(name)
            docker('start', name)
        deadline = threading.Event()
        for _ in range(20):
            capture.capture_once(identity)
            snapshot = service._deployment_log_snapshot(identity)
            if len(snapshot['entries']) >= 4: break
            deadline.wait(0.25)
        assert len(snapshot['entries']) == 4
        assert {e['source'] for e in snapshot['entries']} == {'application', 'database'}
        assert 'probe-secret' not in json.dumps(snapshot)
        service._raw_log_history.clear()
        capture.capture_once(identity)
        assert service._deployment_log_snapshot(identity)['nextId'] == 5
        a, b = service.stream_logs(identity), service.stream_logs(identity)
        try:
            assert next(a) == next(b)
        finally:
            a.close(); b.close()
        docker('exec', containers[0], 'sh', '-c', 'echo application-third > /proc/1/fd/1')
        capture.capture_once(identity)
        assert service._deployment_log_snapshot(identity)['nextId'] == 6
        # Disabled mode cannot even query Docker, despite these running containers.
        monkeypatch.setattr(capture, 'execution_mode', lambda _: SimpleNamespace(value='SOURCE_ONLY'))
        with monkeypatch.context() as patch:
            patch.setattr(capture.subprocess, 'run', lambda *_a, **_k: pytest.fail('SOURCE_ONLY invoked Docker'))
            assert not capture.capture_once(identity)
            capture.ensure_capture(identity)
        report['checks'] = ['application/database transport', 'redaction', 'durable cursor/no duplicates',
                            'independent SSE consumers', 'new stdout captured', 'SOURCE_ONLY zero Docker calls']
        report['result'] = 'PASS'
    except Exception as exc:
        report['result'], report['error'] = 'FAILED', str(exc)
        raise
    finally:
        report['cleanup'] = []
        for name in containers:
            try:
                docker('rm', '-f', name)
                report['cleanup'].append({'container': name, 'removed': True})
            except Exception as exc:
                report['cleanup'].append({'container': name, 'removed': False, 'error': str(exc)})
        (root / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
