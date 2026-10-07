param([switch]$DeleteData)
if (-not $DeleteData) { throw 'Confirme -DeleteData para eliminar datos de esta sesion' }
. (Join-Path $PSScriptRoot 'runtime-common.ps1')
$containers = @(Get-LocalResources)
$volumes = @(Get-LocalResources -Kind volume)
$networks = @(Get-LocalResources -Kind network)
if ($containers.Count -gt 0) { Invoke-LocalDocker -DockerArgs (@('rm','-f') + @($containers | ForEach-Object { $_.Id })) | Out-Null }
if ($volumes.Count -gt 0) { Invoke-LocalDocker -DockerArgs (@('volume','rm') + @($volumes | ForEach-Object { $_.Name })) | Out-Null }
if ($networks.Count -gt 0) { Invoke-LocalDocker -DockerArgs (@('network','rm') + @($networks | ForEach-Object { $_.Id })) | Out-Null }
foreach ($kind in @('container','volume','network')) {
  if (@(Get-LocalResources -Kind $kind).Count -gt 0) { throw 'Limpieza incompleta; quedan recursos propios' }
}
Write-Host 'Recursos y datos propios eliminados. Fuentes e imagenes conservadas.'
