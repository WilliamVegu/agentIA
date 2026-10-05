"""Honest source delivery metadata and standalone Windows entry point."""
import json
from app.services.dependency_inputs import dependency_manifest, POWERSHELL_SELECTOR
from app.services.gradle_compatibility import POWERSHELL_COMPATIBILITY
from pathlib import Path
from app.services.local_deployment_assets import builder_image, DATABASE_IMAGES, MAVEN_IMAGE, GRADLE_IMAGE, RUNTIME_IMAGE


def delivery_metadata(workspace, project, build_tool, database, host_port=8080):
    ws = Path(workspace).resolve()
    manifests = dependency_manifest(ws)
    images = [builder_image(ws), 'agentia-runtime:21-v1']
    if DATABASE_IMAGES[database]: images.append(DATABASE_IMAGES[database])
    return {'formatVersion': 1, 'packageKind': 'SOURCES', 'composeProject': project,
            'buildTool': build_tool, 'databaseEngine': database, 'javaVersion': 21, 'hostPort': host_port,
            'baseImages': {'builder': GRADLE_IMAGE if build_tool == 'gradle' else MAVEN_IMAGE, 'runtime': RUNTIME_IMAGE},
            'requiredImages': images, 'buildManifests': manifests,
            'verification': {'outcome': 'NOT_EXECUTED', 'note': 'Generating scripts is not execution evidence.'},
            'persistentResources': {'volumes': ['appdata'] + ([] if database == 'H2' else ['dbdata']),
                                    'stopPreservesData': True, 'cleanupRequiresDeleteData': True},
            'offlineKit': {'separateFromSourceZip': True, 'importCommand': './import-offline-kit.ps1 -Path <kit>',
                           'includesApplicationImage': False}}


def write_standalone_delivery(workspace, project, build_tool, database, host_port=8080):
    ws = Path(workspace)
    (ws / 'LOCAL_DELIVERY.json').write_text(json.dumps(delivery_metadata(ws, project, build_tool, database, host_port), indent=2), encoding='utf-8')
    prepare_path = ws / 'prepare-local.ps1'
    prepare = prepare_path.read_text(encoding='utf-8')
    guard = POWERSHELL_SELECTOR + POWERSHELL_COMPATIBILITY + r'''
function Get-PreparationHash([string]$Path) {
  $stream = [IO.File]::OpenRead($Path)
  try {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-','').ToLowerInvariant() }
    finally { $algorithm.Dispose() }
  } finally { $stream.Dispose() }
}
function Assert-PreparationInputs {
  $expected = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'LOCAL_DELIVERY.json') -Raw | ConvertFrom-Json
  Assert-GradleCompatibility $expected.buildTool
  foreach ($entry in $expected.buildManifests.PSObject.Properties) {
    $file = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot $entry.Name))
    if (-not $file.StartsWith($PSScriptRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Entrada de dependencias fuera del proyecto' }
    if (-not (Test-Path -LiteralPath $file -PathType Leaf) -or (Get-PreparationHash $file) -ne $entry.Value) { throw 'Dependencias cambiadas: regenere activos y repita la preparacion explicita.' }
  }
  if (@(Get-DependencyInputs).Count -ne @($expected.buildManifests.PSObject.Properties).Count) { throw 'Cambio el conjunto de dependencias; regenere activos antes de preparar.' }
}
Assert-PreparationInputs
'''
    prepare = prepare.replace('Invoke-Docker build', 'Assert-PreparationInputs\nInvoke-Docker build')
    prepare = prepare.replace('Invoke-Docker pull', 'Assert-PreparationInputs\nInvoke-Docker pull')
    prepare = prepare.replace("$ErrorActionPreference = 'Stop'", "$ErrorActionPreference = 'Stop'\n" + guard, 1)
    prepare = prepare.replace("Write-Host 'Preparación completa", "Assert-PreparationInputs\nWrite-Host 'Preparación completa")
    prepare_path.write_text("param([switch]$SourcesOnly)\nif ($SourcesOnly) { Write-Host 'Preparacion Docker NO EJECUTADA por eleccion de fuentes.'; return }\n" + prepare, encoding='utf-8')
    (ws / 'start-local.ps1').write_text(r'''param([ValidateRange(1024,65535)][int]$Port=8080,[switch]$SourcesOnly,[switch]$ReuseImage)
$ErrorActionPreference='Stop'
# Laboratory choice returns before any Docker discovery or call.
if ($SourcesOnly) {
  Write-Host 'Entrega de fuentes: compilacion, pruebas y despliegue Docker NO EJECUTADOS. Docker no es necesario.'
  return
}
. (Join-Path $PSScriptRoot 'runtime-common.ps1')
function Get-DeliveryHash([string]$Path) {
  $stream=[IO.File]::OpenRead($Path)
  try {
    $algorithm=[Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-','').ToLowerInvariant() }
    finally { $algorithm.Dispose() }
  } finally { $stream.Dispose() }
}
$delivery = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'LOCAL_DELIVERY.json') -Raw | ConvertFrom-Json
if (-not $PSBoundParameters.ContainsKey('Port')) {
  if (($delivery.hostPort -isnot [int] -and $delivery.hostPort -isnot [long]) -or $delivery.hostPort -lt 1024 -or $delivery.hostPort -gt 65535) { throw 'Puerto guardado invalido; regenere los activos.' }
  $Port = [int]$delivery.hostPort
}
if ($delivery.formatVersion -ne 1 -or $delivery.composeProject -ne $LocalProject) { throw 'Paquete incompatible; regenere los archivos de despliegue' }
foreach ($entry in $delivery.buildManifests.PSObject.Properties) {
  $file = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot $entry.Name))
  if (-not $file.StartsWith($PSScriptRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Manifiesto fuera del proyecto' }
  if (-not (Test-Path -LiteralPath $file -PathType Leaf) -or (Get-DeliveryHash $file) -ne $entry.Value) { throw 'Dependencias cambiadas. Regenere los activos y repita prepare-local.ps1 antes de operar offline.' }
}
__DEPENDENCY_SELECTOR__
$current = @(Get-DependencyInputs)
if ($current.Count -ne @($delivery.buildManifests.PSObject.Properties).Count) { throw 'Cambio el conjunto de dependencias. Regenere y prepare de nuevo.' }
__GRADLE_COMPATIBILITY__
Assert-GradleCompatibility $delivery.buildTool
$engine = ((Invoke-LocalDocker -DockerArgs @('info','--format','{{json .}}')) -join "`n") | ConvertFrom-Json
if ($engine.OSType -ne 'linux') { throw 'Se requiere Docker Linux. Puede continuar con -SourcesOnly.' }
$architecture = switch ($engine.Architecture) { 'x86_64' {'amd64'}; 'aarch64' {'arm64'}; default {$engine.Architecture} }
Invoke-LocalDocker -DockerArgs @('compose','version') | Out-Null
$env:HOST_PORT="$Port"
$config = ((Invoke-LocalDocker -DockerArgs @('compose','-p',$LocalProject,'config','--format','json')) -join "`n") | ConvertFrom-Json
$apps = @($config.services.PSObject.Properties.Value | Where-Object { $_.labels.'io.agentia.role' -eq 'application' })
if ($apps.Count -ne 1 -or -not $apps[0].image.StartsWith("$LocalProject-")) { throw 'Aplicacion no identificada por proyecto' }
foreach ($service in $config.services.PSObject.Properties.Value) {
  if ($service.container_name) { throw 'Nombre de contenedor global rechazado' }
  foreach ($portBinding in $service.ports) { if ($portBinding.host_ip -ne '127.0.0.1' -or $service.labels.'io.agentia.role' -ne 'application') { throw 'Solo la aplicacion puede publicarse en localhost' } }
}
foreach ($kind in @('volumes','networks')) {
  foreach ($resource in $config.$kind.PSObject.Properties.Value) { if ($resource.external -or -not $resource.name.StartsWith("${LocalProject}_")) { throw 'Recurso global o externo rechazado' } }
}
$required = @($delivery.requiredImages | Where-Object { -not $ReuseImage -or -not $_.StartsWith('agentia-builder:') })
if ($ReuseImage) { $required += $apps[0].image }
foreach ($image in $required) {
  try { $record = (((Invoke-LocalDocker -DockerArgs @('image','inspect',$image)) -join "`n") | ConvertFrom-Json)[0] }
  catch { throw "Falta la imagen $image. Importe el kit o ejecute prepare-local.ps1 con conexion; puede continuar con -SourcesOnly." }
  if ($record.Os -ne 'linux' -or $record.Architecture -ne $architecture) { throw "Imagen incompatible: $image. Importe el kit o ejecute prepare-local.ps1 con conexion." }
}
if (-not $ReuseImage) {
  Write-Host 'Construccion y pruebas offline; errores impiden el arranque.'
  Invoke-LocalDocker -DockerArgs @('compose','-p',$LocalProject,'build','--pull=false','--no-cache') | Out-Host
} else { Write-Host 'Imagen existente reutilizada. No se ejecutaron nuevas pruebas.' }
# Reuse the inspected lifecycle path: bounded port retries, readiness and data preservation.
& (Join-Path $PSScriptRoot 'restart-local.ps1') -Port $Port
Write-Host 'Readiness confirmada. Consulte la evidencia de pruebas; arrancar no acredita un nuevo PASS.'
'''.replace('__DEPENDENCY_SELECTOR__', POWERSHELL_SELECTOR).replace('__GRADLE_COMPATIBILITY__', POWERSHELL_COMPATIBILITY), encoding='utf-8')
    with (ws / 'LOCAL_DEPLOYMENT.md').open('a', encoding='utf-8') as guide:
        guide.write('\n## Entrega y arranque independiente\n\n'
            '`start-local.ps1 -SourcesOnly` finaliza sin consultar Docker: las fuentes se entregan con ejecución omitida. '
            '`start-local.ps1 -Port 8080` comprueba dependencias, motor Linux, imágenes preparadas y aislamiento de Compose, '
            'construye offline y utiliza el reinicio inspeccionado para readiness/puerto alternativo. '
            '`-ReuseImage` omite construcción y nuevas pruebas: requiere la imagen de aplicación existente. '
            'Un error detiene el script; no se descarga ni prepara automáticamente. No necesita AgentIA, IA, Java/Maven/Gradle en Windows.\n\n'
            '`LOCAL_DELIVERY.json` indica versiones previstas, dependencias y volúmenes propios. '
            'El ZIP es de fuentes y scripts: las imágenes pesadas se transfieren por el kit separado; no es un ejecutable autocontenido. '
            'La metadata generada comienza con NOT_EXECUTED. En el ZIP, DELIVERY_STATUS.json registra la evidencia actual de la sesión, '
            'incluyendo omisiones o resultados obsoletos. La presencia de scripts, un build exitoso o readiness no inventa un resumen de pruebas. '
            'Stop/restart conservan appdata y, para PostgreSQL/MySQL, dbdata; cleanup requiere -DeleteData.\n')
