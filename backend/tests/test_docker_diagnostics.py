import json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from app.config import settings
from app.models.execution import ExecutionMode
from app.services import docker_diagnostics as diagnostics
from app.services.devops_service import generate_all_devops_assets


@pytest.fixture
def environment(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'DOCKER_ENABLED', True)
    monkeypatch.setattr(diagnostics, 'execution_mode', lambda *a, **kw: ExecutionMode.DOCKER)
    monkeypatch.setattr(diagnostics.shutil, 'which', lambda name: 'docker.exe')
    generate_all_devops_assets(str(tmp_path), 'diag', db_engine='H2')
    def run(command, **kwargs):
        if command[1:3] == ['container', 'inspect']:
            return SimpleNamespace(returncode=1, stdout='', stderr='Error: No such container')
        if command[1:3] == ['buildx', 'inspect']:
            return SimpleNamespace(returncode=0, stdout='Driver: docker\nNodes:\nStatus: running\nBuildKit version: v0.32.2\n', stderr='')
        payload = json.dumps({'OSType': 'linux', 'ServerVersion': '29', 'Architecture': 'x86_64'}) if 'info' in command else json.dumps([{'Id': 'sha256:' + 'a' * 64, 'Os': 'linux', 'Architecture': 'amd64', 'RepoDigests': ['fixture@sha256:digest']}]) if 'inspect' in command else 'version 2'
        return SimpleNamespace(returncode=0, stdout=payload, stderr='')
    monkeypatch.setattr(diagnostics.subprocess, 'run', run)
    return tmp_path


def test_sources_never_probe_cli_or_paths(environment, monkeypatch):
    monkeypatch.setattr(diagnostics, 'execution_mode', lambda *a, **kw: ExecutionMode.SOURCE_ONLY)
    forbidden = Mock(side_effect=AssertionError('source mode probe'))
    monkeypatch.setattr(diagnostics.shutil, 'which', forbidden)
    monkeypatch.setattr(diagnostics.subprocess, 'run', forbidden)
    monkeypatch.setattr(diagnostics.tempfile, 'TemporaryFile', forbidden)
    report = diagnostics.diagnose('diag', environment)
    assert report['checks'][0]['status'] == 'SKIPPED_BY_CHOICE'
    forbidden.assert_not_called()


def test_prepared_images_do_not_certify_offline_verification(environment):
    report = diagnostics.diagnose('diag', environment)
    assert report['readyForPreparation'] and report['preparedImagesAvailable']
    assert not report['offlineVerified']
    assert all(c['imageId'] for c in report['checks'] if c['name'] == 'image')
    assert next(c for c in report['checks'] if c['name'] == 'prepared-cache')['status'] == 'AVAILABLE'


@pytest.mark.parametrize('failure', ['admin', 'cli', 'daemon', 'windows', 'malformed', 'permissions'])
def test_specific_unavailability_does_not_become_a_pass(environment, monkeypatch, failure):
    if failure == 'admin': monkeypatch.setattr(settings, 'DOCKER_ENABLED', False)
    if failure == 'cli': monkeypatch.setattr(diagnostics.shutil, 'which', lambda *a: None)
    original = diagnostics.subprocess.run
    def run(command, **kwargs):
        if 'info' in command:
            if failure == 'daemon': return SimpleNamespace(returncode=1, stdout='', stderr='named pipe unavailable')
            if failure == 'windows': return SimpleNamespace(returncode=0, stdout=json.dumps({'OSType': 'windows'}), stderr='')
            if failure == 'malformed': return SimpleNamespace(returncode=0, stdout='[]', stderr='')
        return original(command, **kwargs)
    monkeypatch.setattr(diagnostics.subprocess, 'run', run)
    if failure == 'permissions':
        monkeypatch.setattr(diagnostics.tempfile, 'TemporaryFile', Mock(side_effect=PermissionError('denied')))
    report = diagnostics.diagnose('diag', environment)
    assert not report['readyForPreparation'] and not report['offlineVerified']
    assert any(c['status'] == 'UNAVAILABLE' for c in report['checks'])
    assert report['availableActions'] == ['RETRY', 'CONTINUE_WITHOUT_DOCKER']


@pytest.mark.parametrize('failure', ['context', 'buildkit-stopped', 'buildkit-invalid', 'compose', 'disk-low', 'disk-unknown'])
def test_preparation_requires_operational_builder_and_disk(environment, monkeypatch, failure):
    original = diagnostics.subprocess.run
    def run(command, **kwargs):
        if failure == 'context' and command[1:3] == ['context', 'show']:
            return SimpleNamespace(returncode=1, stdout='', stderr='unavailable')
        if failure == 'compose' and command[1:3] == ['compose', 'version']:
            return SimpleNamespace(returncode=1, stdout='', stderr='unavailable')
        if failure.startswith('buildkit') and command[1:3] == ['buildx', 'inspect']:
            return SimpleNamespace(returncode=0, stdout='Status: stopped' if failure.endswith('stopped') else 'garbage', stderr='')
        return original(command, **kwargs)
    monkeypatch.setattr(diagnostics.subprocess, 'run', run)
    if failure == 'disk-low':
        monkeypatch.setattr(diagnostics.shutil, 'disk_usage', lambda _: SimpleNamespace(free=1))
    if failure == 'disk-unknown':
        monkeypatch.setattr(diagnostics.shutil, 'disk_usage', Mock(side_effect=PermissionError()))
    report = diagnostics.diagnose('diag', environment)
    assert not report['readyForPreparation'] and not report['offlineVerified']


def test_incompatible_image_is_not_launched(environment, monkeypatch):
    original = diagnostics.subprocess.run
    commands = []
    def run(command, **kwargs):
        commands.append(command)
        if command[1:3] == ['image', 'inspect']:
            return SimpleNamespace(returncode=0, stdout=json.dumps([{'Id': 'sha256:other', 'Os': 'linux', 'Architecture': 'arm64'}]), stderr='')
        return original(command, **kwargs)
    monkeypatch.setattr(diagnostics.subprocess, 'run', run)
    report = diagnostics.diagnose('diag', environment)
    assert not report['preparedImagesAvailable']
    assert next(c for c in report['checks'] if c['name'] == 'prepared-cache')['status'] == 'UNAVAILABLE'
    assert not any(c[1] == 'run' for c in commands)


def test_cache_probe_has_no_network_pull_mount_write_or_build(environment, monkeypatch):
    original = diagnostics.subprocess.run
    commands = []
    def run(command, **kwargs):
        commands.append(command)
        if command[1] == 'run':
            assert command[command.index('--network') + 1] == 'none'
            assert command[command.index('--pull') + 1] == 'never'
            assert '--read-only' in command and '--cap-drop' in command
            assert '--mount' not in command and '-v' not in command
            assert kwargs['timeout'] == settings.LOCAL_DIAGNOSTIC_CACHE_TIMEOUT
            return SimpleNamespace(returncode=1, stdout='', stderr='cache missing')
        return original(command, **kwargs)
    monkeypatch.setattr(diagnostics.subprocess, 'run', run)
    report = diagnostics.diagnose('diag', environment)
    assert report['preparedImagesAvailable'] and not report['offlineVerified']
    assert next(c for c in report['checks'] if c['name'] == 'prepared-cache')['status'] == 'UNAVAILABLE'
    assert not any('--bootstrap' in c or c[1] in ('pull', 'build') for c in commands)


@pytest.mark.parametrize('owned', [True, False])
def test_timeout_cleanup_requires_exact_diagnostic_label(environment, monkeypatch, owned):
    import subprocess
    original = diagnostics.subprocess.run
    token = None
    removed = []
    def run(command, **kwargs):
        nonlocal token
        if command[1] == 'run':
            token = command[command.index('--label') + 1].split('=', 1)[1]
            raise subprocess.TimeoutExpired(command, kwargs['timeout'])
        if command[1:3] == ['container', 'inspect']:
            assert token and command[-1] == 'agentia-diagnostic-' + token
            record = {'Id': 'container-own', 'Config': {'Labels': {'io.agentia.diagnostic': token if owned else 'foreign'}}}
            return SimpleNamespace(returncode=0, stdout=json.dumps([record]), stderr='')
        if command[1] == 'rm':
            removed.append(command[-1])
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        return original(command, **kwargs)
    monkeypatch.setattr(diagnostics.subprocess, 'run', run)
    report = diagnostics.diagnose('diag', environment)
    cache = next(c for c in report['checks'] if c['name'] == 'prepared-cache')
    assert cache['status'] == ('UNAVAILABLE' if owned else 'UNKNOWN')
    assert removed == (['container-own'] if owned else [])
    assert not report['offlineVerified']


def test_diagnostic_errors_redact_credentials(environment, monkeypatch):
    original = diagnostics.subprocess.run
    def run(command, **kwargs):
        if command[1:3] == ['compose', 'version']:
            return SimpleNamespace(returncode=1, stdout='', stderr='DB_PASSWORD=super-secret')
        return original(command, **kwargs)
    monkeypatch.setattr(diagnostics.subprocess, 'run', run)
    report = diagnostics.diagnose('diag', environment)
    assert 'super-secret' not in json.dumps(report)


def test_missing_host_cache_does_not_disable_prepared_builder(environment, monkeypatch):
    monkeypatch.setattr(settings, 'MAVEN_CACHE_DIR', str(environment / 'absent-cache'))
    report = diagnostics.diagnose('diag', environment)
    assert next(c for c in report['checks'] if c['name'] == 'host-cache')['status'] == 'UNAVAILABLE'
    assert next(c for c in report['checks'] if c['name'] == 'prepared-cache')['status'] == 'AVAILABLE'
    assert report['readyForPreparation'] and report['preparedImagesAvailable']


def test_legible_host_cache_is_advisory_not_offline_acceptance(environment, monkeypatch):
    cache = environment / 'host-cache'; cache.mkdir()
    (cache / 'file').write_text('content')
    monkeypatch.setattr(settings, 'MAVEN_CACHE_DIR', str(cache))
    report = diagnostics.diagnose('diag', environment)
    assert next(c for c in report['checks'] if c['name'] == 'host-cache')['status'] == 'AVAILABLE'
    assert not report['offlineVerified']
