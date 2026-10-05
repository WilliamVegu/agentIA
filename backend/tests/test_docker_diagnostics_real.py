"""Opt-in diagnostic with prepared images; no pulls, builds or service startup."""
import json
import os
from pathlib import Path
import subprocess
import uuid

import pytest

from app.config import settings
from app.models.execution import ExecutionMode
from app.services import docker_diagnostics as diagnostics
from app.services.local_deployment_assets import builder_image
from scripts.local_microservice_fixture import create_fixture

pytestmark = pytest.mark.skipif(os.environ.get('AGENTIA_RUN_REAL_DOCKER') != '1', reason='Docker real opt-in')


def test_real_cache_diagnostic_does_not_modify_prepared_builder(monkeypatch):
    identity = str(uuid.uuid4())
    ws = Path('.run/real-diagnostics', identity).resolve()
    create_fixture(ws, identity=identity)
    monkeypatch.setattr(settings, 'DOCKER_ENABLED', True)
    monkeypatch.setattr(diagnostics, 'execution_mode', lambda _: ExecutionMode.DOCKER)
    def docker(*args):
        return subprocess.check_output(['docker', *args], text=True, timeout=20).strip()
    image = builder_image(ws)
    original = docker('image', 'inspect', image, '--format', '{{.Id}}')
    before = set(docker('ps', '-aq', '--filter', 'label=io.agentia.diagnostic').splitlines())
    report = diagnostics.diagnose(identity, ws)
    (ws / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    assert report['readyForPreparation'] and report['preparedImagesAvailable'], report
    assert not report['offlineVerified']
    assert next(c for c in report['checks'] if c['name'] == 'prepared-cache')['status'] == 'AVAILABLE', report
    assert next(c for c in report['checks'] if c['name'] == 'buildkit')['status'] == 'AVAILABLE', report
    assert docker('image', 'inspect', image, '--format', '{{.Id}}') == original
    assert set(docker('ps', '-aq', '--filter', 'label=io.agentia.diagnostic').splitlines()) == before
