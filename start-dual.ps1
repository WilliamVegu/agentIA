param([switch]$Install, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'integration/launch.py'
$launcherArgs = @($launcher)
if ($Install) { $launcherArgs += '--install' }
if ($NoBrowser) { $launcherArgs += '--no-browser' }
& python @launcherArgs
exit $LASTEXITCODE
