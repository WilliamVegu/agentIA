"""Execute the generated PowerShell; simulate only the Docker binary boundary."""
import json
import hashlib
import io
import tarfile
import shutil
import subprocess
from pathlib import Path
import pytest
from app.services.devops_service import generate_all_devops_assets
from app.services.local_deployment_assets import builder_image


@pytest.mark.parametrize('case', ['valid', 'corrupt', 'hash', 'fingerprint', 'modified-build', 'added-build', 'cache-manifest', 'existing-image', 'architecture',
                                 'archive-tags', 'archive-id', 'archive-duplicate', 'archive-format',
                                 'added-gradle-catalog', 'modified-maven-config'])
def test_kit_checks_integrity_before_loading_images(tmp_path, case):
    powershell = shutil.which('powershell.exe')
    if not powershell: pytest.skip('Windows PowerShell execution requires Windows')
    ws = tmp_path / 'project'
    ws.mkdir()
    (ws / 'pom.xml').write_text('<project><dependencies></dependencies></project>')
    if case == 'modified-maven-config':
        (ws / '.mvn').mkdir()
        (ws / '.mvn/maven.config').write_text('-Pinitial-profile')
    generate_all_devops_assets(str(ws), 'kit-test', db_engine='H2')
    config_bytes = b'{"os":"linux","architecture":"amd64","rootfs":{"type":"layers","diff_ids":[]}}'
    image_id = hashlib.sha256(config_bytes).hexdigest()
    references = [builder_image(ws), 'agentia-runtime:21-v1']
    def archive_bytes(tags, digest=image_id, duplicate=False):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w', format=tarfile.USTAR_FORMAT) as archive:
            catalog = [{'Config': digest + '.json', 'RepoTags': tags, 'Layers': []}]
            if duplicate: catalog += catalog
            for name, data in ((digest + '.json', config_bytes), ('manifest.json', json.dumps(catalog).encode())):
                record = tarfile.TarInfo(name); record.size = len(data)
                archive.addfile(record, io.BytesIO(data))
        return buffer.getvalue()
    fixture = tmp_path / 'fixture.tar'
    fixture.write_bytes(archive_bytes(references))
    kit = tmp_path / 'portable-kit'
    script = tmp_path / 'validate-kit.ps1'
    def quote(path): return "'" + str(path).replace("'", "''") + "'"
    # No external command is executed: the native scripts see a controlled Docker function.
    script.write_text("""$ErrorActionPreference='Stop'
$global:loaded=$false
$global:identity='sha256:__IMAGE_ID__'
function global:docker {
  $global:LASTEXITCODE=0
  if ($args[0] -eq 'info') { @{OSType='linux'; Architecture='x86_64'} | ConvertTo-Json -Compress; return }
  if ($args[0] -eq 'image') { @{Id=$global:identity; Os='linux'; Architecture='amd64'; RepoDigests=@()} | ConvertTo-Json -Compress; return }
  if ($args[0] -eq 'save') { [IO.File]::Copy('__FIXTURE__',$args[2]); return }
  if ($args[0] -eq 'load') { $global:loaded=$true; return }
}
""".replace('__IMAGE_ID__', image_id).replace('__FIXTURE__', str(fixture).replace("'", "''")) + f"& {quote(ws / 'export-offline-kit.ps1')} -Path {quote(kit)}\n" + {
        'valid': '',
        'corrupt': f"Add-Content -LiteralPath {quote(kit / 'images.tar')} -Value 'corruption'\n",
        'hash': f"$bytes=[IO.File]::ReadAllBytes({quote(kit / 'images.tar')}); $bytes[0]=($bytes[0] -bxor 1); [IO.File]::WriteAllBytes({quote(kit / 'images.tar')},$bytes)\n",
        'fingerprint': f"$manifest=Get-Content -LiteralPath {quote(kit / 'manifest.json')} -Raw | ConvertFrom-Json; $manifest.dependencyFingerprint='wrong'; $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath {quote(kit / 'manifest.json')} -Encoding UTF8\n",
        'modified-build': f"Add-Content -LiteralPath {quote(ws / 'pom.xml')} -Value '<!-- changed -->'\n",
        'added-build': f"[IO.Directory]::CreateDirectory({quote(ws / 'module')}) | Out-Null; [IO.File]::WriteAllText({quote(ws / 'module/pom.xml')},'<project/>')\n",
        'added-gradle-catalog': f"[IO.Directory]::CreateDirectory({quote(ws / 'gradle')}) | Out-Null; [IO.File]::WriteAllText({quote(ws / 'gradle/libs.versions.toml')},'[versions]')\n",
        'modified-maven-config': f"[IO.File]::WriteAllText({quote(ws / '.mvn/maven.config')},'-Pchanged-profile')\n",
        'cache-manifest': f"[IO.Directory]::CreateDirectory({quote(ws / 'build/cache')}) | Out-Null; [IO.File]::WriteAllText({quote(ws / 'build/cache/pom.xml')},'<project/>')\n",
        'existing-image': "$global:identity='sha256:' + ('2' * 64)\n",
        'architecture': f"$manifest=Get-Content -LiteralPath {quote(kit / 'manifest.json')} -Raw | ConvertFrom-Json; foreach ($image in $manifest.images) {{ $image.architecture='arm64' }}; $manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath {quote(kit / 'manifest.json')} -Encoding UTF8\n",
    }.get(case, '') + '__REPLACE_ARCHIVE__' + f"try {{ & {quote(ws / 'import-offline-kit.ps1')} -Path {quote(kit)}; $rejected=$false }} catch {{ Write-Host $_.Exception.Message; $rejected=$true }}\n" + "@{rejected=$rejected; loaded=$global:loaded} | ConvertTo-Json -Compress\n", encoding='utf-8-sig')
    replacement = ''
    if case.startswith('archive-'):
        mutated = {
            'archive-tags': lambda: archive_bytes(references + ['unrelated:latest']),
            'archive-id': lambda: archive_bytes(references, digest='2' * 64),
            'archive-duplicate': lambda: archive_bytes(references, duplicate=True),
            'archive-format': lambda: b'not a Docker save TAR',
        }[case]()
        alternate = tmp_path / 'alternate.tar'; alternate.write_bytes(mutated)
        replacement = (f"[IO.File]::Copy({quote(alternate)},{quote(kit / 'images.tar')},$true)\n"
                       f"$manifest=Get-Content -LiteralPath {quote(kit / 'manifest.json')} -Raw | ConvertFrom-Json; "
                       f"$manifest.archive.sha256='{hashlib.sha256(mutated).hexdigest()}'; $manifest.archive.bytes={len(mutated)}; "
                       f"$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath {quote(kit / 'manifest.json')} -Encoding UTF8\n")
    script.write_text(script.read_text(encoding='utf-8-sig').replace('__REPLACE_ARCHIVE__', replacement), encoding='utf-8-sig')
    result = subprocess.run([powershell, '-NoProfile', '-NonInteractive', '-File', str(script)], capture_output=True, text=True, timeout=25)
    assert result.returncode == 0, result.stdout + result.stderr
    outcome = json.loads(result.stdout.splitlines()[-1])
    success = case in {'valid', 'cache-manifest'}
    assert outcome == {'rejected': not success, 'loaded': success}, result.stdout + result.stderr
    assert (kit / 'manifest.json').is_file()
    catalog = json.loads((kit / 'manifest.json').read_text(encoding='utf-8-sig'))
    assert catalog['included']['buildDependencies'] is True
    assert catalog['included']['externalScanners'] is False
    assert catalog['included']['applicationImage'] is False
    assert catalog['offlineVerified'] is False


@pytest.mark.parametrize('case', ['valid-oci', 'foreign-oci', 'forged-index', 'wrong-link'])
def test_oci_index_links_image_identity_and_rejects_undeclared_tags(tmp_path, case):
    from app.services.kit_archive_script import ARCHIVE_PREFLIGHT
    shell = shutil.which('powershell.exe')
    if not shell: pytest.skip('Windows PowerShell required')
    config = b'{"os":"linux","architecture":"amd64"}'
    config_digest = hashlib.sha256(config).hexdigest()
    root = json.dumps({'config': {'digest': 'sha256:' + (('2' * 64) if case == 'wrong-link' else config_digest)}}).encode()
    root_digest = hashlib.sha256(root).hexdigest()
    entry = {'digest': 'sha256:' + root_digest, 'annotations': {'io.containerd.image.name': 'docker.io/library/own:local'}}
    index = {'manifests': [entry]}
    if case == 'foreign-oci':
        index['manifests'].append({'digest': 'sha256:' + root_digest, 'annotations': {'io.containerd.image.name': 'docker.io/library/foreign:local'}})
    payload = tmp_path / 'images.tar'
    with tarfile.open(payload, 'w', format=tarfile.USTAR_FORMAT) as archive:
        contents = {
            'blobs/sha256/' + config_digest: config,
            'blobs/sha256/' + root_digest: b'{"forged":true}' if case == 'forged-index' else root,
            'index.json': json.dumps(index).encode(),
            'manifest.json': json.dumps([{'Config': 'blobs/sha256/' + config_digest, 'RepoTags': ['own:local'], 'Layers': []}]).encode(),
        }
        for name, data in contents.items():
            record = tarfile.TarInfo(name); record.size = len(data)
            archive.addfile(record, io.BytesIO(data))
    probe = tmp_path / 'probe.ps1'
    probe.write_text(ARCHIVE_PREFLIGHT + "\n$images=@(@{reference='own:local';id='sha256:" + root_digest + "'})\n"
                     + "try { Assert-KitArchive -Archive '" + str(payload).replace("'", "''") + "' -Images $images; $rejected=$false } catch { $rejected=$true }\n"
                     + "@{rejected=$rejected} | ConvertTo-Json -Compress", encoding='utf-8-sig')
    result = subprocess.run([shell, '-NoProfile', '-NonInteractive', '-File', str(probe)], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout.strip()) == {'rejected': case != 'valid-oci'}
