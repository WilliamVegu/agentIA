import pytest
import asyncio
from app.services.gradle_compatibility import validate_gradle_version
from app.services.local_deployment_assets import write_windows_scripts
from app.sandbox.docker_runner import run_docker_sandbox
from test_standalone_delivery import powershell


def project(root, version):
    (root / 'build.gradle').write_text('plugins {}')
    wrapper = root / 'gradle/wrapper/gradle-wrapper.properties'
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text(f'distributionUrl=https\\://services.gradle.org/distributions/gradle-{version}-bin.zip\n')


@pytest.mark.parametrize('version', ['8.10.2', '8.9', '9.0', 'unknown'])
def test_prepared_profile_requires_exact_declared_version(tmp_path, version):
    project(tmp_path, version)
    if version == '8.10.2': validate_gradle_version(tmp_path)
    else:
        with pytest.raises(ValueError, match='incompatible'): validate_gradle_version(tmp_path)


@pytest.mark.parametrize('script', ['start-local.ps1', 'prepare-local.ps1'])
@pytest.mark.parametrize('sources', [False, True])
def test_generated_scripts_reject_version_before_docker_but_allow_sources(tmp_path, script, sources):
    project(tmp_path, '9.0')
    write_windows_scripts(tmp_path, 'gradle', 'H2')
    result = powershell(tmp_path, "function global:docker { throw 'Docker forbidden' }\n& (Join-Path $PSScriptRoot '" + script + "')" + (' -SourcesOnly' if sources else ''))
    assert 'Docker forbidden' not in result.stderr
    if sources: assert result.returncode == 0
    else: assert result.returncode != 0 and 'Gradle incompatible' in result.stderr


def test_sandbox_rejects_incompatible_version_even_with_legacy_fallback(tmp_path, monkeypatch):
    from app.config import settings
    project(tmp_path, '9.0')
    monkeypatch.setattr(settings, 'ALLOW_HERMETIC_FALLBACK', True)
    monkeypatch.setattr('app.sandbox.docker_runner.subprocess.run', lambda *a, **k: pytest.fail('Docker must not be called'))
    result = asyncio.run(run_docker_sandbox(str(tmp_path), mode='DOCKER'))
    assert not result.is_success and result.exit_code == 1 and 'incompatible' in result.fallback_reason
