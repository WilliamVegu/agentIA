$ErrorActionPreference = 'Stop'
$skillPython = 'C:\Users\willi\.codex\skills\obs-screen-recorder\.venv\Scripts\python.exe'
$helper = 'C:\Users\willi\.codex\skills\obs-screen-recorder\scripts\obs_control.py'
$reportPath = Join-Path $PSScriptRoot 'obs-visible-test.json'
$results = [ordered]@{}
function Invoke-ObsVisible {
    param([string[]]$CommandArgs)
    $lines = & $skillPython $helper @CommandArgs --json
    if ($LASTEXITCODE -ne 0) { throw "Falló OBS: $($CommandArgs[0])" }
    $data = ($lines -join "`n") | ConvertFrom-Json
    $data | ConvertTo-Json -Depth 8 | Out-Host
    return $data
}
$ownedRecording = $false
$originalScene = $null
try {
    $results.initial = Invoke-ObsVisible -CommandArgs @('status')
    if ($results.initial.is_recording) { throw 'Hay una grabación activa; no se modificará.' }
    $originalScene = $results.initial.current_scene
    $otherScene = @($results.initial.scenes | Where-Object { $_ -ne $originalScene })[0]
    if (-not $otherScene) { throw 'No hay una segunda escena para mostrar el cambio.' }
    $results.before = Invoke-ObsVisible -CommandArgs @('screenshot', '--output', (Join-Path $PSScriptRoot 'obs-visible-before.png'))
    $results.start = Invoke-ObsVisible -CommandArgs @('start')
    if ($results.start.status -ne 'recording_started') { throw 'La grabación no fue iniciada por esta prueba.' }
    $ownedRecording = $true
    Start-Sleep -Seconds 3
    $results.change = Invoke-ObsVisible -CommandArgs @('set-scene', '--name', $otherScene)
    $results.changed = Invoke-ObsVisible -CommandArgs @('screenshot', '--output', (Join-Path $PSScriptRoot 'obs-visible-changed.png'))
    Start-Sleep -Seconds 3
    $results.restore = Invoke-ObsVisible -CommandArgs @('set-scene', '--name', $originalScene)
    Start-Sleep -Seconds 3
    $results.stop = Invoke-ObsVisible -CommandArgs @('stop')
    $ownedRecording = $false
} finally {
    if ($ownedRecording) {
        try { $results.cleanup_restore = Invoke-ObsVisible -CommandArgs @('set-scene', '--name', $originalScene) }
        finally { $results.cleanup_stop = Invoke-ObsVisible -CommandArgs @('stop') }
    }
    $results | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $reportPath -Encoding utf8
}
