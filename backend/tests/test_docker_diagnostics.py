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
        payload = json.dumps({'OSType': 'linux', 'ServerVersion': '29', 'Architecture': 'x86_64'}) if 'info' in command else json.dumps([{'Id': 'sha256:fixture', 'Os': 'linux', 'RepoDigests': ['fixture@sha256:digest']}]) if 'inspect' in command else 'version 2'
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
