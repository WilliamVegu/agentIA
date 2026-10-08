"""Standalone Windows lifecycle commands; never require the AgentIA process."""
from pathlib import Path


def write_lifecycle_scripts(workspace, project):
    workspace = Path(workspace)
    common = r'''$ErrorActionPreference = 'Stop'
$LocalProject = '@PROJECT@'
function Invoke-LocalDocker {
  param([string[]]$DockerArgs)
  $result = & docker @DockerArgs
  if ($LASTEXITCODE -ne 0) { throw "Docker fallo con codigo $LASTEXITCODE" }
  return $result
}
function Get-LocalResources {
  param([ValidateSet('container','volume','network')][string]$Kind = 'container')
  $filter = "label=com.docker.compose.project=$LocalProject"
  if ($Kind -eq 'container') {
    $ids = @(Invoke-LocalDocker -DockerArgs @('ps','-a','--filter',$filter,'--format','{{.ID}}'))
  } else { $ids = @(Invoke-LocalDocker -DockerArgs @($Kind,'ls','-q','--filter',$filter)) }
  if ($ids.Count -eq 0) { return @() }
  if ($Kind -eq 'container') { $argsList = @('inspect') + $ids }
  else { $argsList = @($Kind,'inspect') + $ids }
  $records = ((Invoke-LocalDocker -DockerArgs $argsList) -join "`n") | ConvertFrom-Json
  if (@($records).Count -ne $ids.Count) { throw 'Inspeccion incompleta; no se modifican recursos' }
  foreach ($record in $records) {
    if ($Kind -eq 'container') { $labels = $record.Config.Labels } else { $labels = $record.Labels }
    if ($labels.'com.docker.compose.project' -ne $LocalProject -or $labels.'io.agentia.owner' -ne $LocalProject -or $labels.'io.agentia.studio' -ne 'springboot') { throw 'Recurso ajeno; operacion rechazada' }
  }
  return $records
}
Set-Location -LiteralPath $PSScriptRoot
'''.replace('@PROJECT@', project)
    (workspace / 'runtime-common.ps1').write_text(common, encoding='utf-8')
    (workspace / 'stop-local.ps1').write_text(r'''. (Join-Path $PSScriptRoot 'runtime-common.ps1')
$running = @(Get-LocalResources | Where-Object { $_.State.Running } | ForEach-Object { $_.Id })
if ($running.Count -gt 0) { Invoke-LocalDocker -DockerArgs (@('stop','--time','10') + $running) | Out-Null }
if (@(Get-LocalResources | Where-Object { $_.State.Running }).Count -gt 0) { throw 'Quedan contenedores propios activos' }
Write-Host 'Contenedores propios detenidos. Datos conservados.'
''', encoding='utf-8')
    (workspace / 'cleanup-local.ps1').write_text(r'''param([switch]$DeleteData)
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
''', encoding='utf-8')
    (workspace / 'restart-local.ps1').write_text(r'''param([int]$Port = 0)
. (Join-Path $PSScriptRoot 'runtime-common.ps1')
$config = ((Invoke-LocalDocker -DockerArgs @('compose','-p',$LocalProject,'config','--format','json')) -join "`n") | ConvertFrom-Json
$apps = @($config.services.PSObject.Properties.Value | Where-Object { $_.labels.'io.agentia.role' -eq 'application' })
if ($apps.Count -ne 1 -or -not $apps[0].image.StartsWith("$LocalProject-")) { throw 'Imagen ajena o no identificada por sesion' }
foreach ($service in $config.services.PSObject.Properties.Value) {
  if ($service.container_name) { throw 'No se admiten nombres globales de contenedor' }
}
foreach ($kind in @('volumes','networks')) {
  foreach ($resource in $config.$kind.PSObject.Properties.Value) {
    if ($resource.external -or -not $resource.name.StartsWith("${LocalProject}_")) { throw 'No se admiten recursos globales o externos' }
  }
}
if (@($apps[0].ports).Count -eq 0 -or @($apps[0].ports | Where-Object { $_.host_ip -ne '127.0.0.1' }).Count -gt 0) { throw 'Solo se admite localhost' }
foreach ($kind in @('container','volume','network')) { Get-LocalResources -Kind $kind | Out-Null }
$previous = @(Get-LocalResources | Where-Object { $_.Config.Labels.'io.agentia.role' -eq 'application' })
if ($Port -eq 0) {
  if ($previous.Count -gt 0) { $Port = [int]$previous[0].HostConfig.PortBindings.'8080/tcp'[0].HostPort }
  else { $Port = [int]$apps[0].ports[0].published }
}
if ($Port -lt 1024 -or $Port -gt 65535) { throw 'Puerto fuera del rango permitido' }
for ($attempt=0; $attempt -lt 3; $attempt++) {
  $env:HOST_PORT = "$Port"
  & docker compose -p $LocalProject up -d --force-recreate --no-build --pull never --wait --wait-timeout 180
  if ($LASTEXITCODE -eq 0) { break }
  if ($attempt -eq 2) { throw 'Reinicio no confirmado; consulte logs y estado' }
  # Only retry if the requested port is now occupied; never retry arbitrary build/BD errors.
  $probe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback,$Port)
  $occupied = $false
  try { $probe.Start() } catch [System.Net.Sockets.SocketException] { $occupied = $true } finally { $probe.Stop() }
  if (-not $occupied) { throw 'Docker no pudo iniciar; no se cambia el puerto por este error' }
  $found = $false
  for ($candidate=$Port+1; $candidate -lt [Math]::Min($Port+100,65536); $candidate++) {
    $probe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback,$candidate)
    try { $probe.Start(); $Port=$candidate; $found=$true; break } catch [System.Net.Sockets.SocketException] { } finally { $probe.Stop() }
  }
  if (-not $found) { throw 'No hay puerto alternativo disponible' }
  Write-Host "Puerto ocupado; se usara $Port. Datos conservados."
}
$actual = @(Get-LocalResources | Where-Object { $_.Config.Labels.'io.agentia.role' -eq 'application' -and $_.State.Running })
if ($actual.Count -ne 1) { throw 'Reinicio sin aplicacion propia activa' }
$effectivePort = [int]$actual[0].HostConfig.PortBindings.'8080/tcp'[0].HostPort
$health = Invoke-RestMethod -Uri "http://127.0.0.1:$effectivePort/actuator/health" -TimeoutSec 5 -MaximumRedirection 0
if ($health.status -ne 'UP') { throw 'Readiness HTTP no aprobada' }
Write-Host "Servicio listo en http://localhost:$effectivePort. Imagen reutilizada y datos conservados."
''', encoding='utf-8')
    with (workspace / 'LOCAL_DEPLOYMENT.md').open('a', encoding='utf-8') as guide:
        guide.write('\n`restart-local.ps1` reinicia sin build/pull, conserva datos y usa el puerto anterior o uno alternativo si está ocupado. `runtime-common.ps1` debe acompañar a los scripts: inspecciona propiedad antes de operar. La limpieza requiere `-DeleteData`, elimina solo contenedores/volúmenes/redes propios y conserva fuentes, historial e imágenes. Un error no se registra como parada/reinicio/limpieza aprobados.\n')
