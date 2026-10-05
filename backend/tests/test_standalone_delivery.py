import io
import json
import shutil
import subprocess
import zipfile
from pathlib import Path
import pytest
from app.services.local_deployment_assets import write_windows_scripts
from app.services.export_service import create_project_zip
from test_local_docker_runtime import runtime


def assets(ws):
    (ws / 'pom.xml').write_text('<project/>')
    write_windows_scripts(ws, 'maven', 'H2')


def powershell(ws, script):
    shell = shutil.which('powershell.exe')
    if not shell: pytest.skip('Windows PowerShell required')
    probe = ws / 'probe.ps1'; probe.write_text(script, encoding='utf-8-sig')
    return subprocess.run([shell, '-NoProfile', '-NonInteractive', '-File', str(probe)],
                          capture_output=True, text=True, timeout=30)


def test_sources_only_start_returns_without_docker(tmp_path):
    assets(tmp_path)
    result = powershell(tmp_path, "function global:docker { throw 'Docker forbidden' }\n& (Join-Path $PSScriptRoot 'start-local.ps1') -SourcesOnly")
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'NO EJECUTADOS' in result.stdout


def test_dependency_change_rejected_before_docker(tmp_path):
    assets(tmp_path)
    (tmp_path / 'pom.xml').write_text('<project>changed</project>')
    result = powershell(tmp_path, "function global:docker { throw 'Docker forbidden' }\n& (Join-Path $PSScriptRoot 'start-local.ps1')")
    assert result.returncode != 0 and 'Dependencias cambiadas' in result.stderr
    assert 'Docker forbidden' not in result.stderr


def test_saved_port_is_used_when_omitted_and_explicit_port_wins(tmp_path):
    assets(tmp_path)
    write_windows_scripts(tmp_path, 'maven', 'H2', host_port=18081)
    metadata = json.loads((tmp_path / 'LOCAL_DELIVERY.json').read_text())
    assert metadata['hostPort'] == 18081
    project = metadata['composeProject']
    config = {'services': {'app': {'image': project + '-app:local', 'labels': {'io.agentia.role': 'application'},
        'ports': [{'host_ip': '127.0.0.1'}]}}, 'volumes': {}, 'networks': {}}
    (tmp_path / 'restart-local.ps1').write_text('param([int]$Port)\nWrite-Host "PORT=$Port"')
    prefix = '''function global:docker {
 $global:LASTEXITCODE=0
 if ($args[0] -eq 'info') { '{"OSType":"linux","Architecture":"x86_64"}'; return }
 if ($args[0] -eq 'image') { '[{"Os":"linux","Architecture":"amd64"}]'; return }
 if ($args -contains 'config') { '@CONFIG@'; return }
}
'''.replace('@CONFIG@', json.dumps(config))
    implicit = powershell(tmp_path, prefix + "& (Join-Path $PSScriptRoot 'start-local.ps1')")
    explicit = powershell(tmp_path, prefix + "& (Join-Path $PSScriptRoot 'start-local.ps1') -Port 18082")
    assert implicit.returncode == explicit.returncode == 0, implicit.stderr + explicit.stderr
    assert 'PORT=18081' in implicit.stdout and 'PORT=18082' in explicit.stdout


@pytest.mark.parametrize('fault', ['foreign', 'build', 'readiness', 'missing-image', 'success'])
def test_start_checks_config_and_does_not_report_success_after_failure(tmp_path, fault):
    assets(tmp_path)
    metadata = json.loads((tmp_path / 'LOCAL_DELIVERY.json').read_text())
    project = metadata['composeProject']
    (tmp_path / 'restart-local.ps1').write_text("param([int]$Port)\n" + ("throw 'readiness failure'" if fault == 'readiness' else "Write-Host 'READY_FROM_LIFECYCLE'"))
    config = {'services': {'app': {'image': ('foreign' if fault == 'foreign' else project) + '-app:local',
              'labels': {'io.agentia.role': 'application'}, 'ports': [{'host_ip': '127.0.0.1'}]}},
              'volumes': {'appdata': {'name': project + '_appdata'}}, 'networks': {}}
    probe = r'''$global:builds=0
function global:docker {
 $global:LASTEXITCODE=0
 if ($args[0] -eq 'info') { '{"OSType":"linux","Architecture":"x86_64"}'; return }
 if ($args[0] -eq 'image') { if ('@FAULT@' -eq 'missing-image') { $global:LASTEXITCODE=1; return }; '[{"Os":"linux","Architecture":"amd64"}]'; return }
 if ($args -contains 'config') { '@CONFIG@'; return }
 if ($args -contains 'build') { $global:builds++; if ('@FAULT@' -eq 'build') { $global:LASTEXITCODE=1 }; return }
}
try { & (Join-Path $PSScriptRoot 'start-local.ps1'); $failed=$false } catch { Write-Host $_.Exception.Message; $failed=$true }
@{failed=$failed; builds=$global:builds} | ConvertTo-Json -Compress
'''.replace('@CONFIG@', json.dumps(config)).replace('@FAULT@', fault)
    result = powershell(tmp_path, probe)
    assert result.returncode == 0, result.stdout + result.stderr
    status = json.loads(result.stdout.splitlines()[-1])
    assert status == {'failed': fault != 'success', 'builds': 0 if fault in {'foreign', 'missing-image'} else 1}, result.stdout + result.stderr
    if fault == 'missing-image':
        assert 'prepare-local.ps1' in result.stdout and '-SourcesOnly' in result.stdout
    assert ('Readiness confirmada' in result.stdout) is (fault == 'success')


def test_source_zip_has_honest_delivery_status_without_secret_or_heavy_kit(tmp_path):
    assets(tmp_path)
    (tmp_path / '.env').write_text('SECRET=must-not-export')
    (tmp_path / 'images.tar').write_bytes(b'heavy kit')
    with zipfile.ZipFile(io.BytesIO(create_project_zip(str(tmp_path)))) as archive:
        assert '.env' not in archive.namelist() and 'images.tar' not in archive.namelist()
        status = json.loads(archive.read('DELIVERY_STATUS.json'))
        assert status['packageKind'] == 'SOURCES' and not status['includesImages']
        assert status['verificationOutcome'] == 'NOT_EXECUTED'
        metadata = json.loads(archive.read('LOCAL_DELIVERY.json'))
        assert metadata['persistentResources']['stopPreservesData']
        assert metadata['verification']['outcome'] == 'NOT_EXECUTED'


def test_source_change_during_packaging_rejected(tmp_path, monkeypatch):
    assets(tmp_path)
    original = zipfile.ZipFile.write
    def changing(archive, filename, *args, **kwargs):
        original(archive, filename, *args, **kwargs)
        if Path(filename).name == 'pom.xml':
            (tmp_path / 'pom.xml').write_text('<project>changed during ZIP</project>')
    monkeypatch.setattr(zipfile.ZipFile, 'write', changing)
    with pytest.raises(RuntimeError, match='cambiaron'):
        create_project_zip(str(tmp_path))


@pytest.mark.parametrize('outcome', ['PASSED', 'OUTDATED', 'INTERRUPTED', 'SKIPPED_BY_CHOICE'])
def test_zip_records_current_session_evidence_without_docker(runtime, monkeypatch, outcome):
    from app.models.session import SessionLocal, GenerationSessionDB
    from app.services.verification_policy import workspace_fingerprint
    from app.services import docker_service
    def forbidden(*args, **kwargs):
        raise AssertionError('Docker must not be called by source packaging')
    monkeypatch.setattr(docker_service.subprocess, 'run', forbidden)
    metrics = {'workspaceFingerprint': 'old' if outcome == 'OUTDATED' else workspace_fingerprint(runtime.ws),
               'totalTests': 3, 'passedTests': 3, 'failedTests': 0, 'allPassed': True, 'fallback_used': False}
    if outcome == 'INTERRUPTED':
        metrics.update(verificationInterrupted=True, fallback_used=True, allPassed=False)
    if outcome == 'SKIPPED_BY_CHOICE':
        metrics.update(verificationSkipped=True, fallback_used=True, allPassed=False)
    with SessionLocal() as db:
        row = db.get(GenerationSessionDB, runtime.id)
        row.verification_metrics_json = json.dumps(metrics)
        row.execution_mode = 'SOURCE_ONLY' if outcome == 'SKIPPED_BY_CHOICE' else 'DOCKER'
        db.commit()
    with zipfile.ZipFile(io.BytesIO(create_project_zip(str(runtime.ws)))) as archive:
        status = json.loads(archive.read('DELIVERY_STATUS.json'))
        assert status['verificationOutcome'] == outcome
        assert status['packageKind'] == 'SOURCES' and not status['includesImages']
