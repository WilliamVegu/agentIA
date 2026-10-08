import json
import shutil
import subprocess
import pytest
from app.services.lifecycle_scripts import write_lifecycle_scripts


@pytest.mark.parametrize('foreign', [False, 'project', 'owner', 'studio'])
def test_windows_owned_resource_arrays_and_foreign_rejection(tmp_path, foreign):
    shell = shutil.which('powershell.exe')
    if not shell: pytest.skip('Windows PowerShell required')
    write_lifecycle_scripts(tmp_path, 'own-project')
    runner = tmp_path / 'probe.ps1'
    runner.write_text(r'''$global:running=$true
$global:mutations=0
function global:docker {
 $global:LASTEXITCODE=0
 if ($args[0] -eq 'ps') { 'app'; 'init'; return }
 if ($args[0] -eq 'stop') { $global:mutations++; $global:running=$false; return }
 if ($args[0] -eq 'inspect') {
   @(@{Id='app';Config=@{Labels=@{'com.docker.compose.project'='@PROJECT@';'io.agentia.owner'='@OWNER@';'io.agentia.studio'='@STUDIO@'}};State=@{Running=$global:running}},
     @{Id='init';Config=@{Labels=@{'com.docker.compose.project'='own-project';'io.agentia.owner'='own-project';'io.agentia.studio'='springboot'}};State=@{Running=$false}}) | ConvertTo-Json -Depth 8
 }
}
try { & (Join-Path $PSScriptRoot 'stop-local.ps1'); $rejected=$false } catch { $rejected=$true }
@{rejected=$rejected; mutations=$global:mutations; running=$global:running} | ConvertTo-Json -Compress
'''.replace('@PROJECT@', 'foreign' if foreign=='project' else 'own-project').replace('@OWNER@', 'foreign' if foreign=='owner' else 'own-project').replace('@STUDIO@', 'quarkus' if foreign=='studio' else 'springboot'), encoding='utf-8-sig')
    result = subprocess.run([shell, '-NoProfile', '-NonInteractive', '-File', str(runner)], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout.splitlines()[-1]) == {'rejected': bool(foreign), 'mutations': 0 if foreign else 1, 'running': bool(foreign)}
