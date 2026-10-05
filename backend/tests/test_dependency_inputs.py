import hashlib
import json
from pathlib import Path
import pytest

from app.services.dependency_inputs import dependency_manifest, POWERSHELL_SELECTOR
from app.services.local_deployment_assets import project_identity, MAVEN_IMAGE, GRADLE_IMAGE, RUNTIME_IMAGE
from app.services.standalone_delivery import delivery_metadata
from test_standalone_delivery import powershell, assets
from test_local_docker_runtime import runtime

INPUTS = ['.mvn/maven.config', '.mvn/extensions.xml', 'gradle/libs.versions.toml',
          'gradle/wrapper/gradle-wrapper.properties', 'gradle.lockfile', 'gradlew.bat',
          'buildSrc/src/main/kotlin/Dependencies.kt', 'config/testing.gradle.kts']


@pytest.mark.parametrize('relative', INPUTS)
def test_added_and_changed_build_inputs_change_preparation_identity(tmp_path, relative):
    (tmp_path / 'pom.xml').write_text('<project/>')
    initial = project_identity(tmp_path)
    file = tmp_path / relative; file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text('first configuration')
    added = project_identity(tmp_path)
    assert added != initial and relative in dependency_manifest(tmp_path)
    assert relative in delivery_metadata(tmp_path, 'project', 'maven', 'H2')['buildManifests']
    file.write_text('changed configuration')
    assert project_identity(tmp_path) != added
    file.unlink()
    assert project_identity(tmp_path) == initial


def test_python_and_powershell_select_exact_same_inputs(tmp_path):
    for relative in INPUTS + ['pom.xml', 'module/pom.xml', 'buildSrc/build/cache.gradle',
        'target/gradle/cache.toml', '.agentia-runtime/pom.xml', 'node_modules/gradle/catalog.toml',
        'gradle/Thumbs.db', 'buildSrc/.idea/cache.xml', 'buildSrc/.env', 'buildSrc/__pycache__/cache.pyc',
        'src/main/java/Unrelated.java', 'README.md']:
        file = tmp_path / relative; file.parent.mkdir(parents=True, exist_ok=True); file.write_text('content')
    script = POWERSHELL_SELECTOR + "\n$names = @(Get-DependencyInputs | ForEach-Object { $_.FullName.Substring($PSScriptRoot.Length+1).Replace('\\','/') }); ConvertTo-Json -InputObject $names -Compress"
    result = powershell(tmp_path, script)
    assert result.returncode == 0, result.stderr
    assert set(json.loads(result.stdout)) == set(dependency_manifest(tmp_path))
    from app.services.source_snapshot import SourceSnapshot
    snapshot = SourceSnapshot(tmp_path)
    try:
        assert not (snapshot.working / 'buildSrc/.env').exists()
        assert (snapshot.working / 'gradle/libs.versions.toml').exists()
    finally:
        snapshot.close()


def test_basic_builder_identity_remains_compatible(tmp_path):
    content = b'<project/>'
    (tmp_path / 'pom.xml').write_bytes(content)
    digest = hashlib.sha256(b'pom.xml' + content + (MAVEN_IMAGE + GRADLE_IMAGE + RUNTIME_IMAGE).encode())
    assert project_identity(tmp_path) == digest.hexdigest()[:24]


@pytest.mark.parametrize('relative', INPUTS)
def test_standalone_rejects_new_input_before_any_docker_call(tmp_path, relative):
    assets(tmp_path)
    file = tmp_path / relative; file.parent.mkdir(parents=True, exist_ok=True); file.write_text('new dependency configuration')
    result = powershell(tmp_path, "function global:docker { throw 'Docker forbidden' }\n& (Join-Path $PSScriptRoot 'start-local.ps1')")
    assert result.returncode != 0 and 'Docker forbidden' not in result.stderr
    assert 'dependencias' in result.stderr.lower()


def test_preparation_change_stops_following_commands(runtime, monkeypatch):
    from app.services import local_preparation, docker_service
    commands = []
    def build(command, callback, **kwargs):
        commands.append(command)
        path = runtime.ws / '.mvn/maven.config'; path.parent.mkdir(exist_ok=True)
        path.write_text('-Pnew-profile')
    monkeypatch.setattr(docker_service, 'run_logged', build)
    row = local_preparation.prepare_local(runtime.id, str(runtime.ws), 'H2')
    runtime.workers[0]()
    assert len(commands) == 1 and row.status.value == 'FAILED' and row.finishedAt
    assert 'Dependencias cambiadas' in row.errorMessage


@pytest.mark.parametrize('choice', ['sources', 'changed', 'during'])
def test_standalone_preparation_guards_inputs_and_source_choice(tmp_path, choice):
    assets(tmp_path)
    if choice == 'changed': (tmp_path / 'pom.xml').write_text('new POM')
    script = r'''$global:calls=0
function global:docker {
  $global:LASTEXITCODE=0
  $global:calls++
  if ($args[0] -eq 'build') { [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'pom.xml'),'changed during build') }
}
try { & (Join-Path $PSScriptRoot 'prepare-local.ps1') __CHOICE__; $rejected=$false }
catch { Write-Host $_.Exception.Message; $rejected=$true }
@{calls=$global:calls; rejected=$rejected} | ConvertTo-Json -Compress
'''.replace('__CHOICE__', '-SourcesOnly' if choice == 'sources' else '')
    result = powershell(tmp_path, script)
    assert result.returncode == 0, result.stderr
    outcome = json.loads(result.stdout.splitlines()[-1])
    assert outcome == {'calls': 3 if choice == 'during' else 0, 'rejected': choice != 'sources'}, result.stdout + result.stderr
    if choice != 'sources': assert 'Preparación completa' not in result.stdout
