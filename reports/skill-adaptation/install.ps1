$ErrorActionPreference = 'Stop'
$sourceSkill = Join-Path $PSScriptRoot 'obs-screen-recorder'
$targetSkill = 'C:\Users\willi\.codex\skills\obs-screen-recorder'
$runtimePython = 'C:\Users\willi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (Test-Path -LiteralPath $targetSkill) {
    throw "La carpeta destino ya existe: $targetSkill. No se sobrescribirá."
}
New-Item -ItemType Directory -Path (Join-Path $targetSkill 'scripts') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $targetSkill 'agents') -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $sourceSkill 'SKILL.md') -Destination $targetSkill
Copy-Item -LiteralPath (Join-Path $sourceSkill 'agents/openai.yaml') -Destination (Join-Path $targetSkill 'agents/openai.yaml')
Copy-Item -LiteralPath (Join-Path $sourceSkill 'scripts/obs_control.py') -Destination (Join-Path $targetSkill 'scripts/obs_control.py')
Copy-Item -LiteralPath (Join-Path $sourceSkill 'scripts/requirements.txt') -Destination (Join-Path $targetSkill 'scripts/requirements.txt')
& $runtimePython -m venv (Join-Path $targetSkill '.venv')
if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno virtual.' }
$skillPython = Join-Path $targetSkill '.venv/Scripts/python.exe'
& $skillPython -m pip install --disable-pip-version-check -r (Join-Path $targetSkill 'scripts/requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias.' }
& $skillPython (Join-Path $targetSkill 'scripts/obs_control.py') doctor --json
if ($LASTEXITCODE -ne 0) { throw 'Falló el diagnóstico de la skill instalada.' }
