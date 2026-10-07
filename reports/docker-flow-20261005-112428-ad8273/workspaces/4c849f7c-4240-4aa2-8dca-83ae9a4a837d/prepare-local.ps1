param([switch]$SourcesOnly)
if ($SourcesOnly) { Write-Host 'Preparacion Docker NO EJECUTADA por eleccion de fuentes.'; return }
# Preparación inicial online; no constituye prueba offline.
$ErrorActionPreference = 'Stop'

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

function Assert-GradleCompatibility([string]$BuildTool) {
  if ($BuildTool -ne 'gradle') { return }
  foreach ($file in @(Get-DependencyInputs | Where-Object { $_.Name -eq 'gradle-wrapper.properties' })) {
    $urls = @(Get-Content -LiteralPath $file.FullName | Where-Object { $_ -match '^\s*distributionUrl\s*=\s*\S+\s*$' })
    if ($urls.Count -ne 1 -or $urls[0] -notmatch '(?:^|/)gradle-(?<version>[0-9]+(?:\.[0-9]+){1,2})-(?:bin|all)\.zip(?:[?#].*)?\s*$' -or $Matches.version -ne '8.10.2') {
      throw 'Gradle incompatible: el perfil preparado usa 8.10.2. Ajuste explicitamente el proyecto y regenere/prepare, o continue con -SourcesOnly. No se descarga el wrapper.'
    }
  }
}

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

Set-Location -LiteralPath $PSScriptRoot
function Invoke-Docker { & docker @args; if ($LASTEXITCODE -ne 0) { throw "Docker falló: $args" } }
Invoke-Docker info
Invoke-Docker compose -p 4c849f7c-4240-4aa2-8dca-83ae9a4a837d version
Assert-PreparationInputs
Invoke-Docker build --pull -f Dockerfile.prepare -t agentia-builder:d88bfa15cfd91d25b40dd518 .
Assert-PreparationInputs
Invoke-Docker build --pull -f Dockerfile.runtime -t agentia-runtime:21-v1 .
Assert-PreparationInputs
Invoke-Docker pull postgres:16.4-alpine
Assert-PreparationInputs
Write-Host 'Preparación completa para las dependencias actuales. Para operar offline ejecute start-local.ps1.'
