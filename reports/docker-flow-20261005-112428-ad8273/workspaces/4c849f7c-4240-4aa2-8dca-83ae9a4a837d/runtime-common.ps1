$ErrorActionPreference = 'Stop'
$LocalProject = '4c849f7c-4240-4aa2-8dca-83ae9a4a837d'
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
    if ($labels.'com.docker.compose.project' -ne $LocalProject) { throw 'Recurso ajeno; operacion rechazada' }
  }
  return $records
}
Set-Location -LiteralPath $PSScriptRoot
