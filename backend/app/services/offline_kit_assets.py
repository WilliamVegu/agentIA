"""Standalone PowerShell kit transfer; integrity is distinct from runtime verification."""
import json
import base64
import hashlib
from pathlib import Path
from app.services.local_deployment_assets import builder_image, project_identity, DATABASE_IMAGES


def write_kit_scripts(workspace, database):
    ws = Path(workspace)
    references = [builder_image(ws), 'agentia-runtime:21-v1']
    if DATABASE_IMAGES[database]: references.append(DATABASE_IMAGES[database])
    fingerprint = project_identity(ws)
    manifests = {file.relative_to(ws).as_posix(): hashlib.sha256(file.read_bytes()).hexdigest() for file in ws.rglob('*') if file.is_file() and file.name in {'pom.xml', 'build.gradle', 'build.gradle.kts', 'settings.gradle', 'settings.gradle.kts', 'gradle.properties'} and not any(p in {'target', 'build', '.gradle', '.agentia-runtime'} for p in file.relative_to(ws).parts)}
    config = base64.b64encode(json.dumps({'dependencyFingerprint': fingerprint, 'requiredImages': references, 'buildManifests': manifests}).encode()).decode()
    common = """
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
function Invoke-Docker { & docker @args; if ($LASTEXITCODE -ne 0) { throw "Docker falló: $args" } }
function Get-KitHash([string]$LiteralPath) {
  $stream=[IO.File]::OpenRead($LiteralPath)
  try {
    $algorithm=[Security.Cryptography.SHA256]::Create()
    try { return @{Hash=[BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-','').ToLowerInvariant()} }
    finally { $algorithm.Dispose() }
  } finally { $stream.Dispose() }
}
$expected = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('__CONFIG__')) | ConvertFrom-Json
foreach ($entry in $expected.buildManifests.PSObject.Properties) {
  $file = Join-Path $PSScriptRoot $entry.Name
  if (-not (Test-Path -LiteralPath $file) -or (Get-KitHash -LiteralPath $file).Hash -ne $entry.Value) { throw 'Los manifiestos de build cambiaron. Regenere los scripts y repita la preparación.' }
}
$currentManifests = @(Get-ChildItem -LiteralPath $PSScriptRoot -File -Recurse | Where-Object { $_.Name -in @('pom.xml','build.gradle','build.gradle.kts','settings.gradle','settings.gradle.kts','gradle.properties') -and $_.FullName.Substring($PSScriptRoot.Length+1).Replace('\\','/') -notmatch '(^|/)(target|build|\\.gradle|\\.agentia-runtime)(/|$)' })
if ($currentManifests.Count -ne @($expected.buildManifests.PSObject.Properties).Count) { throw 'Cambió el conjunto de manifiestos. Repita la preparación.' }
$engineOutput = & docker info --format '{{json .}}'
if ($LASTEXITCODE -ne 0) { throw 'Motor Docker inaccesible.' }
$engine = $engineOutput | ConvertFrom-Json
if ($engine.OSType -ne 'linux') { throw 'Seleccione un motor Docker Linux.' }
$engineArchitecture = switch ($engine.Architecture) { 'x86_64' {'amd64'}; 'aarch64' {'arm64'}; default {$engine.Architecture} }
if (-not $engineArchitecture) { throw 'No se pudo verificar la arquitectura del motor.' }
""".replace('__CONFIG__', config)
    export = """param([Parameter(Mandatory=$true)][string]$Path)
""" + common + """
$destination = [System.IO.Path]::GetFullPath($Path)
if ($destination -eq $PSScriptRoot -or $destination.StartsWith($PSScriptRoot+[System.IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Guarde el kit fuera del proyecto de fuentes.' }
if (Test-Path -LiteralPath $destination) { throw 'Use una carpeta nueva para el kit; no se sobrescribe un kit anterior.' }
$metadata = @()
foreach ($image in $expected.requiredImages) {
  $inspection = & docker image inspect $image
  if ($LASTEXITCODE -ne 0) { throw "Falta $image. Ejecute prepare-local.ps1 con conexión." }
  $record = @($inspection | ConvertFrom-Json)[0]
  if ($record.Os -ne 'linux' -or $record.Architecture -ne $engineArchitecture) { throw 'El kit requiere imágenes Linux compatibles con la arquitectura del motor.' }
  $metadata += @{ reference=$image; id=$record.Id; os=$record.Os; architecture=$record.Architecture; repoDigests=@($record.RepoDigests) }
}
New-Item -ItemType Directory -Path $destination | Out-Null
$archive = Join-Path $destination 'images.tar'
Invoke-Docker save -o $archive @($expected.requiredImages)
$manifest = @{ formatVersion=1; dependencyFingerprint=$expected.dependencyFingerprint; createdAt=[DateTime]::UtcNow.ToString('o'); images=$metadata; archive=@{ file='images.tar'; bytes=(Get-Item -LiteralPath $archive).Length; sha256=(Get-KitHash -LiteralPath $archive).Hash }; offlineVerified=$false }
$manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $destination 'manifest.json') -Encoding UTF8
Write-Host "Kit exportado: $destination. Transferir imágenes no acredita un build offline aprobado."
"""
    importer = """param([Parameter(Mandatory=$true)][string]$Path)
""" + common + """
$source = [System.IO.Path]::GetFullPath($Path)
$manifest = Get-Content -LiteralPath (Join-Path $source 'manifest.json') -Raw | ConvertFrom-Json
if ($manifest.formatVersion -ne 1 -or $manifest.dependencyFingerprint -ne $expected.dependencyFingerprint) { throw 'Kit incompatible con las dependencias de este proyecto.' }
if ($manifest.archive.file -ne 'images.tar') { throw 'Nombre de archivo de kit inválido.' }
$archive = Join-Path $source 'images.tar'
if ((Get-Item -LiteralPath $archive).Length -ne $manifest.archive.bytes) { throw 'Tamaño del archivo de imágenes incorrecto.' }
if ((Get-KitHash -LiteralPath $archive).Hash -ne $manifest.archive.sha256) { throw 'Integridad SHA256 incorrecta. No se importó ninguna imagen.' }
if (@($manifest.images).Count -ne @($expected.requiredImages).Count) { throw 'Catálogo de imágenes incorrecto.' }
$seen = @{}
foreach ($record in $manifest.images) {
  if ($record.reference -notin $expected.requiredImages -or $seen.ContainsKey($record.reference) -or $record.os -ne 'linux' -or $record.architecture -ne $engineArchitecture -or $record.id -notmatch '^sha256:[a-f0-9]{64}$') { throw 'Identidad o arquitectura de imagen inválida en el kit.' }
  $seen[$record.reference]=$true
  $existing = & docker image inspect $record.reference 2>$null
  if ($LASTEXITCODE -eq 0) {
    $existingRecord = @($existing | ConvertFrom-Json)[0]
    if ($existingRecord.Id -ne $record.id) { throw "Existe otra imagen bajo $($record.reference). No se sobrescribe automáticamente." }
  }
}
Invoke-Docker load -i $archive
foreach ($record in $manifest.images) {
  $inspection = & docker image inspect $record.reference
  if ($LASTEXITCODE -ne 0) { throw "No se importó $($record.reference)." }
  $actual = @($inspection | ConvertFrom-Json)[0]
  if ($actual.Id -ne $record.id -or $actual.Os -ne $record.os -or $actual.Architecture -ne $record.architecture) { throw 'Identidad importada no coincide con el manifiesto.' }
}
Write-Host 'Imágenes importadas y comprobadas. Ejecute start-local.ps1 para verificar y arrancar offline.'
"""
    (ws / 'export-offline-kit.ps1').write_text(export, encoding='utf-8')
    (ws / 'import-offline-kit.ps1').write_text(importer, encoding='utf-8')
    (ws / 'OFFLINE_KIT.md').write_text(
        '# Kit de imágenes para este proyecto\n\n'
        'Después de `prepare-local.ps1`, ejecute `./export-offline-kit.ps1 -Path C:\\kits\\proyecto` usando una carpeta nueva. '
        'Transfiera la carpeta a otro equipo con Docker Linux y use `./import-offline-kit.ps1 -Path C:\\kits\\proyecto`. '
        'No requiere Java, Maven/Gradle ni AgentIA en el equipo destino. El fingerprint debe coincidir con los manifiestos de build. '
        'El import comprueba tamaño y SHA256 antes de cargar, rechaza tags existentes con identidad distinta y comprueba IDs/arquitectura después.\n\n'
        'Use kits de procedencia confiable: el hash detecta corrupción; no es una firma de autenticidad. '
        'El kit contiene builder/dependencias actuales, runtime y BD; no incluye Python/Node de AgentIA, scanners, herramientas Kubernetes ni la imagen de aplicación. '
        'Ejecute el build offline para demostrar pruebas y arranque; la transferencia por sí sola no acredita esa evidencia. '
        'La carpeta pesada se conserva separada del ZIP de fuentes. Importación en un motor real y prueba de caché fría siguen pendientes.\n', encoding='utf-8')
