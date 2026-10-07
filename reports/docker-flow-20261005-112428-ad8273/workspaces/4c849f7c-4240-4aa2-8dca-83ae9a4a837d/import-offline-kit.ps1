param([Parameter(Mandatory=$true)][string]$Path)

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
$expected = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('eyJkZXBlbmRlbmN5RmluZ2VycHJpbnQiOiAiZDg4YmZhMTVjZmQ5MWQyNWI0MGRkNTE4IiwgInJlcXVpcmVkSW1hZ2VzIjogWyJhZ2VudGlhLWJ1aWxkZXI6ZDg4YmZhMTVjZmQ5MWQyNWI0MGRkNTE4IiwgImFnZW50aWEtcnVudGltZToyMS12MSIsICJwb3N0Z3JlczoxNi40LWFscGluZSJdLCAiYnVpbGRNYW5pZmVzdHMiOiB7InBvbS54bWwiOiAiYjIxYzQxZmViOTFiMjM1ODA0NDg5YTc3OWM3M2Y4ZmVkYTk5MTk0MmE0NzcyYWFiNjQ1M2VkZWY1NTIxNDkzZiJ9fQ==')) | ConvertFrom-Json
foreach ($entry in $expected.buildManifests.PSObject.Properties) {
  $file = Join-Path $PSScriptRoot $entry.Name
  if (-not (Test-Path -LiteralPath $file) -or (Get-KitHash -LiteralPath $file).Hash -ne $entry.Value) { throw 'Los manifiestos de build cambiaron. Regenere los scripts y repita la preparación.' }
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

$currentManifests = @(Get-DependencyInputs)
if ($currentManifests.Count -ne @($expected.buildManifests.PSObject.Properties).Count) { throw 'Cambió el conjunto de manifiestos. Repita la preparación.' }
$engineOutput = & docker info --format '{{json .}}'
if ($LASTEXITCODE -ne 0) { throw 'Motor Docker inaccesible.' }
$engine = $engineOutput | ConvertFrom-Json
if ($engine.OSType -ne 'linux') { throw 'Seleccione un motor Docker Linux.' }
$engineArchitecture = switch ($engine.Architecture) { 'x86_64' {'amd64'}; 'aarch64' {'arm64'}; default {$engine.Architecture} }
if (-not $engineArchitecture) { throw 'No se pudo verificar la arquitectura del motor.' }

function Assert-KitArchive([string]$Archive, $Images) {
  $stream=[IO.File]::OpenRead($Archive)
  $configs=@{}
  $documents=@{}
  $catalog=$null
  $ociIndex=$null
  try {
    while ($stream.Position -lt $stream.Length) {
      $header=New-Object byte[] 512
      if ($stream.Read($header,0,512) -ne 512) { throw 'Cabecera TAR incompleta' }
      $nonzero=$false
      foreach ($value in $header) { if ($value -ne 0) { $nonzero=$true; break } }
      if (-not $nonzero) { break }
      $checksumText=[Text.Encoding]::ASCII.GetString($header,148,8).Trim([char[]]@([char]0,[char]32))
      $checksum=[Convert]::ToInt64($checksumText,8)
      $sum=0
      for ($index=0;$index -lt 512;$index++) { if ($index -ge 148 -and $index -lt 156) { $sum+=32 } else { $sum+=$header[$index] } }
      if ($sum -ne $checksum) { throw 'Checksum de cabecera TAR incorrecto' }
      $name=[Text.Encoding]::ASCII.GetString($header,0,100).Trim([char]0)
      $prefix=[Text.Encoding]::ASCII.GetString($header,345,155).Trim([char]0)
      if ($prefix) { $name="$prefix/$name" }
      $sizeText=[Text.Encoding]::ASCII.GetString($header,124,12).Trim([char[]]@([char]0,[char]32))
      $size=[Convert]::ToInt64($sizeText,8)
      if ($size -lt 0 -or $size -gt ($stream.Length-$stream.Position)) { throw 'TAR truncado o tamano invalido' }
      $regular=$header[156] -eq 0 -or $header[156] -eq 48
      if ($name -eq 'manifest.json' -or $name -eq 'index.json') {
        if (($name -eq 'manifest.json' -and $null -ne $catalog) -or ($name -eq 'index.json' -and $null -ne $ociIndex) -or -not $regular -or $size -gt 8388608) { throw 'Catalogo Docker duplicado o invalido' }
        $bytes=New-Object byte[] ([int]$size)
        if ($stream.Read($bytes,0,$bytes.Length) -ne $bytes.Length) { throw 'Catalogo truncado' }
        $document=[Text.Encoding]::UTF8.GetString($bytes) | ConvertFrom-Json
        if ($name -eq 'manifest.json') { $catalog=$document } else { $ociIndex=$document }
      } elseif ($regular -and $size -le 4194304 -and ($name -match '^blobs/sha256/[a-f0-9]{64}$' -or $name -match '^[a-f0-9]{64}\.json$')) {
        if ($configs.ContainsKey($name)) { throw 'Contenido de imagen duplicado' }
        $bytes=New-Object byte[] ([int]$size)
        if ($stream.Read($bytes,0,$bytes.Length) -ne $bytes.Length) { throw 'Contenido truncado' }
        $algorithm=[Security.Cryptography.SHA256]::Create()
        try { $configs[$name]='sha256:'+([BitConverter]::ToString($algorithm.ComputeHash($bytes)).Replace('-','').ToLowerInvariant()) }
        finally { $algorithm.Dispose() }
        if ($bytes.Length -gt 0 -and $bytes[0] -eq 123 -and $size -le 262144) {
          try { $documents[$name]=[Text.Encoding]::UTF8.GetString($bytes) | ConvertFrom-Json } catch { }
        }
      } else { $stream.Seek($size,[IO.SeekOrigin]::Current) | Out-Null }
      $padding=(512-($size % 512)) % 512
      if ($padding -gt ($stream.Length-$stream.Position)) { throw 'Padding TAR truncado' }
      $stream.Seek($padding,[IO.SeekOrigin]::Current) | Out-Null
    }
  } finally { $stream.Dispose() }
  if ($null -eq $catalog) { throw 'Archivo Docker save sin manifest.json compatible' }
  $expectedTags=@{}
  foreach ($record in $Images) { $expectedTags[$record.reference]=$record.id }
  function Get-ArchiveConfigs([string]$Digest,[int]$Depth=0) {
    if ($Depth -gt 4 -or $Digest -notmatch '^sha256:[a-f0-9]{64}$') { throw 'Grafo OCI invalido' }
    $key='blobs/sha256/'+$Digest.Substring(7)
    if ($configs[$key] -ne $Digest -or -not $documents.ContainsKey($key)) { throw 'Identidad OCI no comprobable' }
    $document=$documents[$key]
    if ($document.config.digest) { return $document.config.digest }
    if (-not $document.manifests) { throw 'Manifiesto OCI sin configuracion' }
    foreach ($child in $document.manifests) { Get-ArchiveConfigs -Digest $child.digest -Depth ($Depth+1) }
  }
  $ociTags=@{}
  if ($null -ne $ociIndex) {
    foreach ($entry in $ociIndex.manifests) {
      $tag=$entry.annotations.'io.containerd.image.name'
      if (-not $tag) {
        if ($entry.annotations.'org.opencontainers.image.ref.name') { throw 'Tag OCI sin nombre completo' }
        continue
      }
      $tag=$tag -replace '^docker.io/library/','' -replace '^docker.io/',''
      if (-not $expectedTags.ContainsKey($tag) -or $ociTags.ContainsKey($tag)) { throw 'Tag OCI ajeno o duplicado' }
      $linkedConfigs=@(Get-ArchiveConfigs -Digest $entry.digest)
      $ociTags[$tag]=@{id=$entry.digest; configs=$linkedConfigs}
    }
    if ($ociTags.Count -ne $expectedTags.Count) { throw 'Catalogo OCI incompleto' }
  }
  $seenTags=@{}
  foreach ($record in $catalog) {
    if (-not $configs.ContainsKey($record.Config) -or @($record.RepoTags).Count -eq 0) { throw 'Configuracion o tags ausentes en el archivo Docker' }
    $configId=$configs[$record.Config]
    if ($record.Config -ne ('blobs/sha256/'+$configId.Substring(7)) -and $record.Config -ne ($configId.Substring(7)+'.json')) { throw 'Nombre de config y digest no coinciden' }
    foreach ($tag in $record.RepoTags) {
      if (-not $expectedTags.ContainsKey($tag) -or $seenTags.ContainsKey($tag)) { throw 'El archivo contiene tags ajenos o duplicados; no se carga' }
      if ($ociTags.ContainsKey($tag) -and $configId -notin $ociTags[$tag].configs) { throw 'Config no vinculada a su imagen OCI' }
      if ($configId -ne $expectedTags[$tag] -and (-not $ociTags.ContainsKey($tag) -or $ociTags[$tag].id -ne $expectedTags[$tag])) { throw 'Identidad del contenido no coincide con el manifiesto del kit' }
      $seenTags[$tag]=$true
    }
  }
  if ($seenTags.Count -ne $expectedTags.Count) { throw 'Catalogo de tags incompleto' }
}

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
}
# Verify every archive tag and config digest before load can overwrite anything.
Assert-KitArchive -Archive $archive -Images $manifest.images
foreach ($record in $manifest.images) {
  $existing = & docker image inspect $record.reference 2>$null
  if ($LASTEXITCODE -eq 0) {
    $existingRecord = ($existing | ConvertFrom-Json)[0]
    if ($existingRecord.Id -ne $record.id) { throw "Existe otra imagen bajo $($record.reference). No se sobrescribe automáticamente." }
  }
}
Invoke-Docker load -i $archive
foreach ($record in $manifest.images) {
  $inspection = & docker image inspect $record.reference
  if ($LASTEXITCODE -ne 0) { throw "No se importó $($record.reference)." }
  $actual = ($inspection | ConvertFrom-Json)[0]
  if ($actual.Id -ne $record.id -or $actual.Os -ne $record.os -or $actual.Architecture -ne $record.architecture) { throw 'Identidad importada no coincide con el manifiesto.' }
}
Write-Host 'Imágenes importadas y comprobadas. Ejecute start-local.ps1 para verificar y arrancar offline.'
