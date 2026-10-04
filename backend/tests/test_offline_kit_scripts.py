"""Execute the generated PowerShell; simulate only the Docker binary boundary."""
import json
import shutil
import subprocess
from pathlib import Path
import pytest
from app.services.devops_service import generate_all_devops_assets


@pytest.mark.parametrize('case', ['valid', 'corrupt', 'hash', 'fingerprint', 'modified-build', 'added-build', 'cache-manifest', 'existing-image', 'architecture'])
def test_kit_checks_integrity_before_loading_images(tmp_path, case):
    powershell = shutil.which('powershell.exe')
    if not powershell: pytest.skip('Windows PowerShell execution requires Windows')
    ws = tmp_path / 'project'
    ws.mkdir()
    (ws / 'pom.xml').write_text('<project><dependencies></dependencies></project>')
    generate_all_devops_assets(str(ws), 'kit-test', db_engine='H2')
    kit = tmp_path / 'portable-kit'
    script = tmp_path / 'validate-kit.ps1'
    def quote(path): return "'" + str(path).replace("'", "''") + "'"
    # No external command is executed: the native scripts see a controlled Docker function.
    script.write_text("""$ErrorActionPreference='Stop'
$global:loaded=$false
$global:identity='sha256:' + ('1' * 64)
function global:docker {
  $global:LASTEXITCODE=0
  if ($args[0] -eq 'info') { @{OSType='linux'; Architecture='x86_64'} | ConvertTo-Json -Compress; return }
  if ($args[0] -eq 'image') { @{Id=$global:identity; Os='linux'; Architecture='amd64'; RepoDigests=@()} | ConvertTo-Json -Compress; return }
  if ($args[0] -eq 'save') { [IO.File]::WriteAllBytes($args[2],[Text.Encoding]::UTF8.GetBytes('fixture image archive')); return }
  if ($args[0] -eq 'load') { $global:loaded=$true; return }
}
""" + f"& {quote(ws / 'export-offline-kit.ps1')} -Path {quote(kit)}\n" + {
        'valid': '',
        'corrupt': f"Add-Content -LiteralPath {quote(kit / 'images.tar')} -Value 'corruption'\n",
        'hash': f"[IO.File]::WriteAllBytes({quote(kit / 'images.tar')},[Text.Encoding]::UTF8.GetBytes('fixture image archivf'))\n",
        'fingerprint': f"$manifest=Get-Content -LiteralPath {quote(kit / 'manifest.json')} -Raw | ConvertFrom-Json; $manifest.dependencyFingerprint='wrong'; $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath {quote(kit / 'manifest.json')} -Encoding UTF8\n",
        'modified-build': f"Add-Content -LiteralPath {quote(ws / 'pom.xml')} -Value '<!-- changed -->'\n",
        'added-build': f"[IO.Directory]::CreateDirectory({quote(ws / 'module')}) | Out-Null; [IO.File]::WriteAllText({quote(ws / 'module/pom.xml')},'<project/>')\n",
        'cache-manifest': f"[IO.Directory]::CreateDirectory({quote(ws / 'build/cache')}) | Out-Null; [IO.File]::WriteAllText({quote(ws / 'build/cache/pom.xml')},'<project/>')\n",
        'existing-image': "$global:identity='sha256:' + ('2' * 64)\n",
        'architecture': f"$manifest=Get-Content -LiteralPath {quote(kit / 'manifest.json')} -Raw | ConvertFrom-Json; foreach ($image in $manifest.images) {{ $image.architecture='arm64' }}; $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath {quote(kit / 'manifest.json')} -Encoding UTF8\n",
    }[case] + f"try {{ & {quote(ws / 'import-offline-kit.ps1')} -Path {quote(kit)}; $rejected=$false }} catch {{ $rejected=$true }}\n" + "@{rejected=$rejected; loaded=$global:loaded} | ConvertTo-Json -Compress\n", encoding='utf-8-sig')
    result = subprocess.run([powershell, '-NoProfile', '-NonInteractive', '-File', str(script)], capture_output=True, text=True, timeout=25)
    assert result.returncode == 0, result.stdout + result.stderr
    outcome = json.loads(result.stdout.splitlines()[-1])
    success = case in {'valid', 'cache-manifest'}
    assert outcome == {'rejected': not success, 'loaded': success}
    assert (kit / 'manifest.json').is_file()
