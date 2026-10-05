from scripts.local_microservice_fixture import create_fixture
"""Real Windows save/load with existing prepared images; not a clean-engine claim."""
import json
import os
import subprocess
import uuid
from pathlib import Path
import pytest
from app.services.local_deployment_assets import builder_image

pytestmark = pytest.mark.skipif(os.environ.get('AGENTIA_RUN_REAL_DOCKER') != '1', reason='Docker real opt-in')


def test_real_windows_kit_roundtrip_preserves_image_ids_and_rejects_corruption():
    identity = str(uuid.uuid4())
    root = Path('.run/real-kit-transfer', identity).resolve()
    ws = root / 'project'; ws.mkdir(parents=True)
    create_fixture(ws, identity=identity)
    kit = root / 'kit'
    report = {'test': identity, 'result': 'RUNNING', 'cleanEngine': False, 'externalInternetBlocked': False}
    references = [builder_image(ws), 'agentia-runtime:21-v1']
    def docker_ids():
        return {ref: subprocess.check_output(['docker', 'image', 'inspect', ref, '--format', '{{.Id}}'],
                                             text=True, timeout=15).strip() for ref in references}
    def script(name, success=True):
        shell = r'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe'
        result = subprocess.run([shell, '-NoProfile', '-NonInteractive', '-File', str(ws / name), '-Path', str(kit)],
                                cwd=ws, capture_output=True, text=True, timeout=300)
        (root / (name + ('-rejected' if not success else '') + '.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
        assert (result.returncode == 0) is success, (result.stdout + result.stderr)[-5000:]
        return result
    try:
        initial = docker_ids()
        script('export-offline-kit.ps1')
        manifest = json.loads((kit / 'manifest.json').read_text(encoding='utf-8-sig'))
        assert {r['reference']: r['id'] for r in manifest['images']} == initial
        assert manifest['offlineVerified'] is False
        script('import-offline-kit.ps1')
        assert docker_ids() == initial
        # Corrupt the catalog hash, not the large file; import must fail before load.
        original = (kit / 'manifest.json').read_bytes()
        manifest['archive']['sha256'] = '0' * 64
        (kit / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        rejected = script('import-offline-kit.ps1', success=False)
        assert 'SHA256' in rejected.stderr
        assert docker_ids() == initial
        (kit / 'manifest.json').write_bytes(original)
        report.update(result='PASS', imageIds=initial, archiveBytes=manifest['archive']['bytes'],
                      transferAndIdentityConfirmed=True, corruptManifestRejected=True, imagesPreserved=True)
    except Exception as exc:
        report.update(result='FAILED', error=str(exc))
        raise
    finally:
        # Keep the requested portable artifact for review; no engine resources were created/removed.
        report['kitRetained'] = str(kit)
        (root / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
