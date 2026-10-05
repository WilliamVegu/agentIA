"""Export the actually verified application image; shared builders/DB kits stay separate."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import uuid
import zipfile
import yaml
from app.config import settings

PACKAGE_SCRIPT = r'''param(
 [ValidateSet('Import','Start','Stop','Cleanup')][string]$Action='Start',
 [switch]$SourcesOnly,[switch]$ConfirmDeleteData,[int]$Port=0
)
$ErrorActionPreference='Stop'
if ($SourcesOnly) { Write-Host 'Fuentes disponibles; ejecucion Docker NO EJECUTADA.'; return }
Set-Location -LiteralPath $PSScriptRoot
function Invoke-Docker { $result=& docker @args; if ($LASTEXITCODE -ne 0) { throw 'Operacion Docker fallida' }; return $result }
function Get-PackageHash([string]$Path) {
 $stream=[IO.File]::OpenRead($Path)
 try { $algorithm=[Security.Cryptography.SHA256]::Create(); try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-','').ToLowerInvariant() } finally { $algorithm.Dispose() } } finally { $stream.Dispose() }
}
__ARCHIVE_PREFLIGHT__
$manifest=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'EXECUTABLE_PACKAGE.json') -Raw | ConvertFrom-Json
if ($manifest.formatVersion -ne 1 -or $manifest.packageKind -ne 'VERIFIED_IMAGE' -or $manifest.project -notmatch '^agentia-package-[a-f0-9]{32}$') { throw 'Paquete invalido' }
foreach ($entry in $manifest.files.PSObject.Properties) {
 $file=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot $entry.Name))
 if (-not $file.StartsWith($PSScriptRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or -not (Test-Path -LiteralPath $file -PathType Leaf)) { throw 'Archivo de paquete ausente o inseguro' }
 if ((Get-Item -LiteralPath $file).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Archivo enlazado no admitido' }
 if ((Get-Item -LiteralPath $file).Length -ne $entry.Value.bytes -or (Get-PackageHash $file) -ne $entry.Value.sha256) { throw 'Integridad de paquete incorrecta' }
}
$project=$manifest.project
if ($Action -eq 'Stop' -or $Action -eq 'Cleanup') {
 if ($Action -eq 'Cleanup' -and -not $ConfirmDeleteData) { throw 'Confirme -ConfirmDeleteData para eliminar datos de este paquete' }
 $resources=@{}
 foreach ($kind in @('container','volume','network')) {
  if ($kind -eq 'container') { $ids=@(Invoke-Docker ps -a -q --filter "label=com.docker.compose.project=$project") }
  else { $ids=@(Invoke-Docker $kind ls -q --filter "label=com.docker.compose.project=$project") }
  $resources[$kind]=$ids
  foreach ($id in $ids) {
   if ($kind -eq 'container') { $info=(Invoke-Docker inspect $id | ConvertFrom-Json)[0]; $labels=$info.Config.Labels }
   else { $info=(Invoke-Docker $kind inspect $id | ConvertFrom-Json)[0]; $labels=$info.Labels }
   if ($labels.'com.docker.compose.project' -ne $project) { throw 'Recurso ajeno; operacion rechazada' }
  }
 }
 foreach ($id in $resources['container']) { Invoke-Docker stop --time 10 $id | Out-Null }
 if ($Action -eq 'Cleanup') {
  foreach ($id in $resources['container']) { Invoke-Docker rm $id | Out-Null }
  foreach ($kind in @('volume','network')) { foreach ($id in $resources[$kind]) { Invoke-Docker $kind rm $id | Out-Null } }
 }
 Write-Host 'Recursos propios detenidos. Cleanup elimina datos solo con confirmacion explicita.'; return
}
$archive=Join-Path $PSScriptRoot 'application-image.tar'
Assert-KitArchive -Archive $archive -Images @($manifest.application)
$existing=& docker image inspect $manifest.application.reference 2>$null
if ($LASTEXITCODE -eq 0 -and ($existing | ConvertFrom-Json)[0].Id -ne $manifest.application.id) { throw 'Tag existente con imagen distinta; no se sobrescribe' }
Invoke-Docker load -i $archive | Out-Null
$actual=(Invoke-Docker image inspect $manifest.application.reference | ConvertFrom-Json)[0]
if ($actual.Id -ne $manifest.application.id) { throw 'Imagen importada distinta' }
if ($Action -eq 'Import') { Write-Host 'Imagen verificada importada. No acredita ejecucion en este equipo.'; return }
foreach ($record in $manifest.sharedImages) {
 $info=(Invoke-Docker image inspect $record.reference | ConvertFrom-Json)[0]
 if ($info.Id -ne $record.id) { throw 'Importe el kit compartido compatible; no se descarga automaticamente' }
}
if ($Port -eq 0) { $Port=$manifest.hostPort }
if ($Port -lt 1024 -or $Port -gt 65535) { throw 'Puerto fuera de rango' }
for ($attempt=0;$attempt -lt 100;$attempt++) {
 $listener=New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback,$Port)
 try { $listener.Start(); $listener.Stop(); break } catch { $listener.Stop(); $Port++; if ($Port -gt 65535 -or $attempt -eq 99) { throw 'Sin puerto local disponible' } }
}
$env:HOST_PORT=[string]$Port
Invoke-Docker compose -p $project -f executable-compose.yml up -d --no-build --pull never --wait --wait-timeout 180 | Out-Null
$health=Invoke-RestMethod -Uri "http://127.0.0.1:$Port/actuator/health" -TimeoutSec 5
if ($health.status -ne 'UP') { throw 'Readiness no confirmada' }
Write-Host "Aplicacion saludable: http://localhost:$Port. No se compilo ni descargaron dependencias."
'''


def export_executable(session_id):
    from app.models.session import GenerationSessionDB, SessionLocal
    from app.services.verification_policy import require_verified_session, require_source_delivery, workspace_fingerprint
    from app.services.source_snapshot import validate_snapshot
    from app.services.session_operation_lock import SessionOperationLock
    from fastapi import HTTPException
    with SessionLocal() as db:
        row = db.get(GenerationSessionDB, session_id)
        if not row:
            raise HTTPException(404, 'Sesion inexistente')
        # Source mode returns before any Docker inspection or process.
        if row.execution_mode == 'SOURCE_ONLY':
            raise HTTPException(409, 'Modo fuentes: use el ZIP de fuentes; no hay paquete ejecutable aprobado')
        require_verified_session(row)
        require_source_delivery(row)
        metrics = json.loads(row.verification_metrics_json)
    lock = SessionOperationLock(session_id)
    if not lock.acquire(False):
        raise HTTPException(409, 'Hay una operacion activa')
    ws = Path(settings.WORKSPACE_DIR) / session_id
    output_root = Path(__file__).resolve().parents[3] / '.run' / 'executable-packages'
    output_root.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    output = output_root / (token + '.zip')
    def docker(*args):
        return subprocess.check_output(['docker', *args], text=True, encoding='utf-8', errors='replace', timeout=600)
    try:
        manifest, archive = validate_snapshot(ws, metrics.get('sourceSnapshotId'), metrics['workspaceFingerprint'])
        from app.services.docker_service import get_deployment_status
        runtime = get_deployment_status(session_id)
        if runtime.status.value != 'HEALTHY' or runtime.sourceSnapshotId != metrics['sourceSnapshotId'] or runtime.workspaceFingerprint != metrics['workspaceFingerprint']:
            raise HTTPException(409, 'Despliegue saludable del snapshot requerido antes de exportar imagen ejecutable')
        with tempfile.TemporaryDirectory(prefix='package-', dir=output_root) as temporary:
            stage = Path(temporary)
            with zipfile.ZipFile(archive) as sealed:
                # Snapshot validator already checks the entire safe catalogue.
                sealed.extractall(stage)
            profile = yaml.safe_load((stage / 'docker-compose.yml').read_text(encoding='utf-8'))
            application = next(c for c in profile['services'].values() if c.get('labels', {}).get('io.agentia.role') == 'application')
            tag = application['image'].replace('${COMPOSE_PROJECT_NAME}', session_id)
            info = json.loads(docker('image', 'inspect', tag))[0]
            labels = info['Config']['Labels']
            if info['Id'] != runtime.imageId or labels.get('io.agentia.source-snapshot') != metrics['sourceSnapshotId'] or labels.get('io.agentia.jar-sha256') != runtime.executableJarSha256:
                raise HTTPException(409, 'La imagen cambio; exportacion rechazada')
            application.pop('build', None)
            application['image'] = runtime.imageId
            shared = []
            for service in profile['services'].values():
                if service is not application:
                    metadata = json.loads(docker('image', 'inspect', service['image']))[0]
                    shared.append({'reference': service['image'], 'id': metadata['Id']})
                    service['image'] = metadata['Id']
            (stage / 'executable-compose.yml').write_text(yaml.safe_dump(profile, sort_keys=False), encoding='utf-8')
            docker('save', '-o', str(stage / 'application-image.tar'), tag)
            from app.services.kit_archive_script import ARCHIVE_PREFLIGHT
            (stage / 'executable-local.ps1').write_text(PACKAGE_SCRIPT.replace('__ARCHIVE_PREFLIGHT__', ARCHIVE_PREFLIGHT), encoding='utf-8')
            (stage / 'EXECUTABLE_PACKAGE.md').write_text(
                '# Paquete de imagen verificada\n\n'
                '`./executable-local.ps1 -Action Start` importa la imagen aprobada y arranca sin compilar. '
                'Para PostgreSQL/MySQL importe antes el kit compartido y defina .env privado. '
                'No contiene credenciales ni datos de la BD original. Usa proyecto/volumen propio y localhost; informa puerto alternativo. '
                '`-Action Stop` conserva datos; `-Action Cleanup -ConfirmDeleteData` retira solo los recursos del paquete. '
                '`-SourcesOnly` retorna sin Docker. El ZIP de fuentes sigue siendo independiente. '
                'Los hashes verifican integridad, no autentican la procedencia. La prueba original no acredita otro equipo ni firewall global.\n', encoding='utf-8')
            def file_info(path):
                digest = hashlib.sha256()
                with path.open('rb') as stream:
                    while chunk := stream.read(1024 * 1024): digest.update(chunk)
                return {'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}
            package = {'formatVersion': 1, 'packageKind': 'VERIFIED_IMAGE', 'sourceSnapshotId': metrics['sourceSnapshotId'],
                       'workspaceFingerprint': metrics['workspaceFingerprint'], 'jarSha256': runtime.executableJarSha256,
                       'verificationOutcome': 'PASSED', 'project': 'agentia-package-' + token,
                       'hostPort': runtime.hostPort, 'application': {'reference': tag, 'id': info['Id']},
                       'sharedImages': shared, 'includesDatabaseData': False,
                       'files': {p.relative_to(stage).as_posix(): file_info(p) for p in sorted(stage.rglob('*')) if p.is_file()}}
            (stage / 'EXECUTABLE_PACKAGE.json').write_text(json.dumps(package, indent=2), encoding='utf-8')
            if workspace_fingerprint(ws) != metrics['workspaceFingerprint'] or json.loads(docker('image', 'inspect', tag))[0]['Id'] != info['Id']:
                raise HTTPException(409, 'Fuentes/imagen cambiaron durante exportacion')
            with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_STORED) as result:
                for path in stage.rglob('*'):
                    if path.is_file(): result.write(path, path.relative_to(stage).as_posix())
        return output
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    finally:
        lock.release()
