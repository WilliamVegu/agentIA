"""Sealed inputs, execution isolation, artifact integrity and honest export."""
import hashlib
import io
import json
from pathlib import Path
import zipfile

import pytest

from app.services.source_snapshot import SourceSnapshot, validate_snapshot, materialize_snapshot
from app.services.verification_policy import workspace_fingerprint, session_has_current_evidence
from app.services.export_service import create_project_zip
from app.models.session import SessionLocal, GenerationSessionDB, SessionStatus, SessionPhase
from app.sandbox.docker_runner import DockerExecutionResult
from app.services import workspace_verification, docker_service
from test_local_docker_runtime import runtime


def sealed(runtime):
    snapshot = SourceSnapshot(runtime.ws)
    reports = snapshot.working / 'target/surefire-reports'; reports.mkdir(parents=True)
    (reports / 'suite.xml').write_text('<testsuite tests="3" failures="0" errors="0" skipped="0"/>')
    jar = snapshot.working / 'target/application.jar'
    with zipfile.ZipFile(jar, 'w') as output:
        output.writestr('META-INF/MANIFEST.MF', 'Main-Class: org.springframework.boot.loader.launch.JarLauncher\n')
        output.writestr('BOOT-INF/classes/test.txt', 'fixture artifact')
    snapshot.finish(DockerExecutionResult(exit_code=0, stdout='Tests run: 3, Failures: 0, Errors: 0, Skipped: 0'), False)
    snapshot.close()
    return snapshot


def bind_evidence(runtime, snapshot):
    with SessionLocal() as db:
        row = db.get(GenerationSessionDB, runtime.id)
        row.status, row.phase = SessionStatus.COMPLETED, SessionPhase.VERIFIED
        row.verification_metrics_json = json.dumps({'totalTests': 3, 'passedTests': 3, 'failedTests': 0,
            'allPassed': True, 'fallback_used': False, 'workspaceFingerprint': snapshot.manifest['workspaceFingerprint'],
            'sourceSnapshotId': snapshot.id})
        db.commit()


def test_seal_excludes_credentials_and_old_outputs(runtime):
    (runtime.ws / '.env').write_text('DB_PASSWORD=private-password')
    target = runtime.ws / 'target'; target.mkdir()
    (target / 'old.jar').write_bytes(b'old')
    snapshot = SourceSnapshot(runtime.ws)
    try:
        with zipfile.ZipFile(snapshot.directory / 'sources.zip') as archive:
            assert '.env' not in archive.namelist()
            assert not any(n.startswith(('target/', '.agentia-runtime/')) for n in archive.namelist())
        old = (snapshot.working / 'pom.xml').read_bytes()
        (runtime.ws / 'pom.xml').write_text('changed originals')
        assert (snapshot.working / 'pom.xml').read_bytes() == old
    finally: snapshot.close()
    assert not snapshot.stage.exists()


@pytest.mark.parametrize('kind', ['source', 'report', 'jar', 'manifest'])
def test_corruption_invalidates_evidence_and_delivery(runtime, kind):
    snapshot = sealed(runtime)
    bind_evidence(runtime, snapshot)
    if kind == 'source':
        (snapshot.directory / 'sources.zip').write_bytes(b'corrupt')
    elif kind == 'report':
        (snapshot.directory / 'reports/target/surefire-reports/suite.xml').write_text('changed')
    elif kind == 'jar':
        (snapshot.directory / 'artifacts/target/application.jar').write_bytes(b'changed')
    else:
        (snapshot.directory / 'manifest.json').write_text('[]')
    with pytest.raises((ValueError, OSError)):
        validate_snapshot(runtime.ws, snapshot.id, snapshot.manifest['workspaceFingerprint'])
    with SessionLocal() as db:
        assert not session_has_current_evidence(db.get(GenerationSessionDB, runtime.id))


def test_source_export_uses_sealed_bytes_not_new_unverified_extras(runtime):
    snapshot = sealed(runtime); bind_evidence(runtime, snapshot)
    (runtime.ws / 'unverified-extra.txt').write_text('added after tests')
    with zipfile.ZipFile(io.BytesIO(create_project_zip(str(runtime.ws)))) as archive:
        assert 'unverified-extra.txt' not in archive.namelist()
        status = json.loads(archive.read('DELIVERY_STATUS.json'))
        assert status['sourceSnapshotId'] == snapshot.id and status['verificationOutcome'] == 'PASSED'
        assert archive.read('pom.xml') == (runtime.ws / 'pom.xml').read_bytes()
    with materialize_snapshot(runtime.ws, snapshot.id, snapshot.manifest['workspaceFingerprint']) as (ws, jar_hash):
        assert workspace_fingerprint(ws) == snapshot.manifest['workspaceFingerprint']
        assert hashlib.sha256((ws / '.verified-artifact/application.jar').read_bytes()).hexdigest() == jar_hash
        assert not (ws / 'unverified-extra.txt').exists()
    assert not ws.exists()


def test_original_edit_restored_during_run_cannot_change_execution_inputs(runtime, monkeypatch):
    old = (runtime.ws / 'pom.xml').read_bytes()
    def run(path, callback):
        execution = Path(path)
        assert execution != runtime.ws and execution.name == runtime.id
        (runtime.ws / 'pom.xml').write_text('transient invalid input')
        assert (execution / 'pom.xml').read_bytes() == old
        (runtime.ws / 'pom.xml').write_bytes(old)
        return DockerExecutionResult(exit_code=0, stdout='Tests run: 3, Failures: 0, Errors: 0, Skipped: 0')
    monkeypatch.setattr(workspace_verification, '_run_sandbox_blocking', run)
    outcome = workspace_verification.run_workspace_verification(str(runtime.ws))
    assert outcome.result.is_success and not outcome.source_changed and outcome.snapshot_id
    manifest, _ = validate_snapshot(runtime.ws, outcome.snapshot_id, outcome.workspace_fingerprint)
    assert manifest['verification'] == 'PASSED'


@pytest.mark.parametrize('mismatch', [None, 'image', 'container'])
def test_snapshot_packaging_inspects_image_and_runtime_chain(runtime, monkeypatch, mismatch):
    snapshot = sealed(runtime); bind_evidence(runtime, snapshot)
    jar_hash = next(iter(snapshot.manifest['executableJars'].values()))
    image_id = 'sha256:' + 'b' * 64
    labels = {'io.agentia.source-snapshot': snapshot.id, 'io.agentia.source-fingerprint': snapshot.manifest['workspaceFingerprint'],
              'io.agentia.jar-sha256': jar_hash}
    original = docker_service.subprocess.run
    def execute(command, **kwargs):
        result = original(command, **kwargs)
        if command[:3] == ['docker', 'image', 'inspect'] and command[-1].endswith('-runtime-service:local'):
            image_labels = dict(labels)
            if mismatch == 'image': image_labels['io.agentia.source-snapshot'] = 'unexpected'
            result.stdout = json.dumps([{'Id': image_id, 'Config': {'Labels': image_labels}}])
        if command[:2] == ['docker', 'inspect']:
            payload = json.loads(result.stdout)
            for item in payload:
                item['Image'] = 'wrong-image' if mismatch == 'container' else image_id
                item['Config']['Labels'].update(labels)
            result.stdout = json.dumps(payload)
        if 'build' in command:
            cwd = Path(kwargs['cwd'])
            assert cwd != runtime.ws
            assert (cwd / '.verified-artifact/application.jar').exists()
            assert 'COPY --chown=10001:10001' in (cwd / 'Dockerfile.verified').read_text()
        return result
    monkeypatch.setattr(docker_service.subprocess, 'run', execute)
    row = docker_service.deploy_local(runtime.id, str(runtime.ws))
    runtime.workers[0]()
    if mismatch:
        assert row.status.value == 'FAILED' and row.errorMessage
        return
    assert row.status.value == 'HEALTHY', row.errorMessage
    assert (row.imageId, row.sourceSnapshotId, row.executableJarSha256) == (image_id, snapshot.id, jar_hash)


def test_readiness_rejects_changed_image_identity():
    from types import SimpleNamespace
    from app.models.devops import DeploymentStatus
    expected = SimpleNamespace(containerId='owned', hostPort=19080, databaseContainerId=None,
        imageId='verified-image', sourceSnapshotId='seal', workspaceFingerprint='fingerprint', executableJarSha256='jar')
    actual = SimpleNamespace(**vars(expected), status=DeploymentStatus.RUNNING)
    assert docker_service.same_runtime(expected, actual)
    for field in ('imageId', 'sourceSnapshotId', 'workspaceFingerprint', 'executableJarSha256'):
        previous = getattr(actual, field)
        setattr(actual, field, 'different')
        assert not docker_service.same_runtime(expected, actual)
        setattr(actual, field, previous)


@pytest.mark.parametrize('relative', ['.mvn/maven.config', 'gradle/libs.versions.toml', 'gradle.lockfile', 'gradlew.bat'])
def test_build_configuration_changes_invalidate_fingerprint(runtime, relative):
    file = runtime.ws / relative
    file.parent.mkdir(parents=True, exist_ok=True)
    before = workspace_fingerprint(runtime.ws)
    file.write_text('new build input')
    assert workspace_fingerprint(runtime.ws) != before
