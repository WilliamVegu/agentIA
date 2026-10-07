param([int]$Port = 0)
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
