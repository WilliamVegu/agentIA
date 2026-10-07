$ErrorActionPreference = 'Stop'
$skillPython = 'C:\Users\willi\.codex\skills\obs-screen-recorder\.venv\Scripts\python.exe'
$helper = 'C:\Users\willi\.codex\skills\obs-screen-recorder\scripts\obs_control.py'
$capturePath = Join-Path $PSScriptRoot 'obs-live-test.png'
$reportPath = Join-Path $PSScriptRoot 'obs-live-test.json'
$results = [ordered]@{}
function Invoke-ObsTest {
    param([string[]]$CommandArgs)
    $resultLines = & $skillPython $helper @CommandArgs --json
    if ($LASTEXITCODE -ne 0) { throw "Falló OBS: $($CommandArgs[0])" }
    $value = ($resultLines -join "`n") | ConvertFrom-Json
    $value | ConvertTo-Json -Depth 8 | Write-Output | Out-Host
    return $value
}
$startedByTest = $false
try {
    $results.doctor = Invoke-ObsTest -CommandArgs @('doctor')
    if (-not $results.doctor.obs_running) {
        $results.launch = Invoke-ObsTest -CommandArgs @('launch')
    }
    $results.initial_status = Invoke-ObsTest -CommandArgs @('status')
    $results.scenes = Invoke-ObsTest -CommandArgs @('scenes')
    $results.screenshot = Invoke-ObsTest -CommandArgs @('screenshot', '--output', $capturePath)
    if ($results.initial_status.is_recording) {
        $results.recording_test = 'Omitido: ya había una grabación activa.'
    } else {
        $results.start = Invoke-ObsTest -CommandArgs @('start')
        if ($results.start.status -eq 'recording_started') {
            $startedByTest = $true
            Start-Sleep -Seconds 2
            $results.pause = Invoke-ObsTest -CommandArgs @('pause')
            Start-Sleep -Milliseconds 500
            $results.resume = Invoke-ObsTest -CommandArgs @('resume')
            Start-Sleep -Seconds 2
            $results.stop = Invoke-ObsTest -CommandArgs @('stop')
            $startedByTest = $false
        } else {
            $results.recording_test = 'Omitido: apareció otra grabación antes del inicio.'
        }
    }
    $results.final_status = Invoke-ObsTest -CommandArgs @('status')
} finally {
    if ($startedByTest) {
        $results.cleanup_stop = Invoke-ObsTest -CommandArgs @('stop')
    }
    $results | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $reportPath -Encoding utf8
}
