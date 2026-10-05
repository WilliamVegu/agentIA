"""Windows .NET TAR preflight: inspect Docker save metadata without extracting files."""

ARCHIVE_PREFLIGHT = r'''
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
'''
