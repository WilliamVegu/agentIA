. (Join-Path $PSScriptRoot 'runtime-common.ps1')
$running = @(Get-LocalResources | Where-Object { $_.State.Running } | ForEach-Object { $_.Id })
if ($running.Count -gt 0) { Invoke-LocalDocker -DockerArgs (@('stop','--time','10') + $running) | Out-Null }
if (@(Get-LocalResources | Where-Object { $_.State.Running }).Count -gt 0) { throw 'Quedan contenedores propios activos' }
Write-Host 'Contenedores propios detenidos. Datos conservados.'
