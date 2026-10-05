"""Real verify -> sealed JAR -> image -> localhost, no second compilation."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
import zipfile

import pytest
import requests

from app.config import settings
from app.models.session import SessionLocal, GenerationSessionDB, SessionStatus
from app.services import docker_service, session_execution, security_service
from app.services.export_service import create_project_zip
from app.services.runtime_lifecycle import owned_resources, cleanup_local
from app.services.source_snapshot import validate_snapshot
from scripts.local_microservice_fixture import create_fixture

pytestmark = pytest.mark.skipif(os.environ.get('AGENTIA_RUN_REAL_DOCKER') != '1', reason='Docker real opt-in')


def test_verified_jar_becomes_same_runtime_image_and_sealed_export(monkeypatch):
    identity = str(uuid.uuid4())
    root = Path('.run/real-sealed-deployment').resolve(); ws = root / identity
    create_fixture(ws, identity=identity)
    monkeypatch.setattr(settings, 'WORKSPACE_DIR', str(root))
    monkeypatch.setattr(settings, 'DOCKER_ENABLED', True)
    with SessionLocal() as db:
        db.add(GenerationSessionDB(id=identity, spec_id='test', spec_name='probe-service',
            execution_mode='DOCKER', status=SessionStatus.PAUSED)); db.commit()
    report = {'session': identity, 'result': 'RUNNING', 'offlineGlobalVerified': False}
    def docker(*args):
        return subprocess.check_output(['docker', *args], text=True, timeout=30).strip()
    target = identity + '-probe-service:local'
    try:
        # Keep the real SAST call; no gate/verification mocks in this acceptance.
        audit = security_service.audit_workspace(str(ws), identity, 'probe-service')
        assert audit.qualityGate.canExport, audit.qualityGate.summaryMessage
        response = session_execution.verify_existing_sources(identity)
        assert response['status'] == 'COMPLETED', response
        metrics = response['metrics']; snapshot_id = metrics['sourceSnapshotId']
        manifest, _ = validate_snapshot(ws, snapshot_id, metrics['workspaceFingerprint'])
        assert manifest['verification'] == 'PASSED' and manifest['reports'] and len(manifest['executableJars']) == 1
        expected_jar = next(iter(manifest['executableJars'].values()))
        row = docker_service.deploy_local(identity, str(ws))
        deadline = time.monotonic() + 180
        while row.finishedAt is None and time.monotonic() < deadline: time.sleep(.25)
        assert row.finishedAt and row.status.value == 'HEALTHY', row.model_dump()
        assert row.sourceSnapshotId == snapshot_id and row.workspaceFingerprint == metrics['workspaceFingerprint']
        assert row.executableJarSha256 == expected_jar
        actual_jar = docker('exec', row.containerId, 'sha256sum', '/app/application.jar').split()[0]
        assert actual_jar == expected_jar
        image = json.loads(docker('image', 'inspect', target))[0]
        assert image['Id'] == row.imageId and image['Config']['Labels']['io.agentia.source-snapshot'] == snapshot_id
        base = f'http://127.0.0.1:{row.hostPort}'
        created = requests.post(base + '/api/v1/items', json={'name': 'sealed'}, timeout=5)
        assert created.status_code == 201
        assert requests.get(base + '/api/v1/items/' + str(created.json()['id']), timeout=5).json()['name'] == 'sealed'
        archive = create_project_zip(str(ws))
        (ws / '.agentia-runtime/delivery.zip').write_bytes(archive)
        with zipfile.ZipFile(io.BytesIO(archive)) as exported:
            status = json.loads(exported.read('DELIVERY_STATUS.json'))
            assert status['sourceSnapshotId'] == snapshot_id and status['verificationOutcome'] == 'PASSED'
        # Restore state from disk and rediscover actual identity, rather than trusting memory.
        docker_service._active_deployments.pop(identity, None)
        recovered = docker_service.get_deployment_status(identity)
        assert recovered.imageId == row.imageId and recovered.sourceSnapshotId == snapshot_id and recovered.status.value == 'HEALTHY'
        report.update(result='PASS', snapshotId=snapshot_id, fingerprint=row.workspaceFingerprint,
            jarSha256=expected_jar, actualRuntimeJarSha256=actual_jar, imageId=row.imageId,
            tests=metrics['totalTests'], reports=len(manifest['reports']), sealedExport=True,
            recoveredIdentity=True, localhost=base, packagedWithoutRecompile=True)
        from app.services.executable_delivery import export_executable
        package = export_executable(identity)
        delivered = root / (identity + '-executable')
        delivered.mkdir()
        with zipfile.ZipFile(package) as executable:
            metadata = json.loads(executable.read('EXECUTABLE_PACKAGE.json'))
            assert metadata['application']['id'] == row.imageId
            assert metadata['sourceSnapshotId'] == snapshot_id
            assert not metadata['includesDatabaseData']
            executable.extractall(delivered)
        package.unlink()
        shell = str(Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe')
        project = metadata['project']
        def package_action(action, *options):
            result = subprocess.run([shell, '-NoProfile', '-File', str(delivered / 'executable-local.ps1'),
                                     '-Action', action, *options], capture_output=True, text=True, timeout=300)
            (delivered / (action + '.log')).write_text(result.stdout + '\n' + result.stderr, encoding='utf-8')
            assert result.returncode == 0, result.stdout + result.stderr
            return result.stdout
        try:
            package_action('Start')
            containers = docker('ps', '-q', '--filter', 'label=com.docker.compose.project=' + project).split()
            assert len(containers) == 1
            actual = json.loads(docker('inspect', containers[0]))[0]
            mapping = actual['NetworkSettings']['Ports']['8080/tcp'][0]
            assert mapping['HostIp'] == '127.0.0.1' and actual['Image'] == row.imageId
            delivered_base = 'http://127.0.0.1:' + mapping['HostPort']
            assert mapping['HostPort'] != str(row.hostPort)
            assert requests.post(delivered_base + '/api/v1/items', json={'name': 'package'}, timeout=5).status_code == 201
            package_action('Stop')
            package_action('Start')
            assert requests.get(delivered_base + '/api/v1/items', timeout=5).json()[0]['name'] == 'package'
            assert requests.get(base + '/api/v1/items/1', timeout=5).json()['name'] == 'sealed'
            report['executablePackage'] = {'result': 'PASS', 'sameImage': True, 'persistence': True,
                                            'isolatedFromOriginal': True, 'localhost': delivered_base}
        finally:
            package_action('Cleanup', '-ConfirmDeleteData')
            assert not docker('ps', '-a', '-q', '--filter', 'label=com.docker.compose.project=' + project)
    except BaseException as exc:
        report.update(result='FAILED', error=str(exc))
        raise
    finally:
        deadline = time.monotonic() + 180
        active = docker_service._active_deployments.get(identity)
        while active and active.finishedAt is None and time.monotonic() < deadline: time.sleep(.25)
        if any(owned_resources(identity, kind) for kind in ('container', 'volume', 'network')):
            cleanup_local(identity, True)
        assert all(not owned_resources(identity, kind) for kind in ('container', 'volume', 'network'))
        subprocess.run(['docker', 'image', 'rm', target], capture_output=True, timeout=30, check=False)
        report['cleanup'] = 'CONFIRMED'
        (ws / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
