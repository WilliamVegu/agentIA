param([ValidateRange(1024,65535)][int]$Port=8080,[switch]$SourcesOnly,[switch]$ReuseImage)
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

function Get-DependencyInputs {
  @(Get-ChildItem -LiteralPath $PSScriptRoot -File -Recurse | Where-Object {
    $relative = $_.FullName.Substring($PSScriptRoot.Length+1).Replace('\','/')
    $included = $relative -notmatch '(^|/)(\.git|target|build|\.gradle|\.m2|node_modules|\.agentia-runtime|\.operation-locks|\.run|\.venv|\.idea|__pycache__)(/|$)' -and
      $_.Name -notin @('.DS_Store','Thumbs.db') -and $_.Name -notmatch '\.pyc$' -and ($_.Name -notlike '.env*' -or $_.Name -eq '.env.example') -and (
      $_.Name -in @('pom.xml','build.gradle','build.gradle.kts','settings.gradle','settings.gradle.kts','gradle.properties','gradlew','gradlew.bat','mvnw','mvnw.cmd') -or
      $_.Name -match '\.(gradle|gradle\.kts|lockfile)$' -or $relative -match '(^|/)(\.mvn|gradle|buildSrc)(/|$)')
    if ($included -and ($_.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Entrada de build enlazada no admitida' }
    $included
  })
}

$current = @(Get-DependencyInputs)
if ($current.Count -ne @($delivery.buildManifests.PSObject.Properties).Count) { throw 'Cambio el conjunto de dependencias. Regenere y prepare de nuevo.' }

function Assert-GradleCompatibility([string]$BuildTool) {
  if ($BuildTool -ne 'gradle') { return }
  foreach ($file in @(Get-DependencyInputs | Where-Object { $_.Name -eq 'gradle-wrapper.properties' })) {
    $urls = @(Get-Content -LiteralPath $file.FullName | Where-Object { $_ -match '^\s*distributionUrl\s*=\s*\S+\s*$' })
    if ($urls.Count -ne 1 -or $urls[0] -notmatch '(?:^|/)gradle-(?<version>[0-9]+(?:\.[0-9]+){1,2})-(?:bin|all)\.zip(?:[?#].*)?\s*$' -or $Matches.version -ne '8.10.2') {
      throw 'Gradle incompatible: el perfil preparado usa 8.10.2. Ajuste explicitamente el proyecto y regenere/prepare, o continue con -SourcesOnly. No se descarga el wrapper.'
    }
  }
}

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
