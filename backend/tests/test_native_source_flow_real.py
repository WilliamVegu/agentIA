"""Actual native backend acceptance with Docker forbidden, isolated data and no AI."""
import importlib.util
import os
from pathlib import Path
import uuid
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('native_source_probe', ROOT / 'scripts/verify_native_source_flow.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

pytestmark = pytest.mark.skipif(os.environ.get('AGENTIA_RUN_REAL_NATIVE') != '1', reason='Native Windows opt-in')


@pytest.mark.parametrize('docker_enabled', [True, False])
def test_generation_verification_export_and_recovery_without_docker(docker_enabled):
    installation = ROOT / '.run/native-offline-install-v4'
    if not installation.exists(): pytest.skip('Prepare native installation first')
    destination = ROOT / '.run/native-source-flow-real' / str(uuid.uuid4())
    report = probe.run(ROOT, installation, destination, docker_enabled)
    assert report['result'] == 'PASS', report
    assert report['processesStopped'] and report['forbiddenAttempts'] == 0
    assert report['guardActiveForBothStarts'] and report['restartRecovered']
