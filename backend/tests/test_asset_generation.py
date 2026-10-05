import json
import threading
from pathlib import Path
import pytest
from app.services import asset_generation, docker_service
from app.services.devops_service import generate_all_devops_assets, _write_devops_assets
from test_local_docker_runtime import runtime


def project(tmp_path):
    (tmp_path / 'pom.xml').write_text('<project><dependencies></dependencies></project>')
    return tmp_path


def test_new_assets_versioned_idempotent_and_configuration_can_change(tmp_path):
    ws = project(tmp_path)
    generate_all_devops_assets(str(ws), 'new', db_engine='H2')
    first = asset_generation.inventory(ws)
    generate_all_devops_assets(str(ws), 'new', db_engine='H2')
    assert asset_generation.inventory(ws) == first
    generate_all_devops_assets(str(ws), 'new', db_engine='H2', host_port=18081)
    assert '18081' in (ws / 'docker-compose.yml').read_text()
    configuration = json.loads((ws / 'ASSET_CONFIGURATION.json').read_text())
    assert configuration['templateVersion'] == asset_generation.TEMPLATE_VERSION and configuration['hostPort'] == 18081
    ledger = json.loads((ws / '.agentia-runtime/generated-assets.json').read_text())
    assert ledger['files']['docker-compose.yml'] == asset_generation.inventory(ws)['docker-compose.yml']


@pytest.mark.parametrize('name', ['Dockerfile', 'start-local.ps1', 'docker-compose.yml', '.github/workflows/ci-cd.yml'])
def test_user_edits_rejected_before_any_mutation(tmp_path, name):
    ws = project(tmp_path)
    generate_all_devops_assets(str(ws), 'new', db_engine='H2')
    path = ws / name
    path.write_text(path.read_text() + '\n# user change')
    before = asset_generation.inventory(ws)
    with pytest.raises(asset_generation.AssetConflict, match='editados'):
        generate_all_devops_assets(str(ws), 'new', db_engine='H2', host_port=18081)
    assert asset_generation.inventory(ws) == before


def test_unowned_existing_assets_are_not_migrated_or_overwritten(tmp_path):
    ws = project(tmp_path)
    (ws / 'Dockerfile').write_text('old or user-owned Dockerfile')
    before = asset_generation.inventory(ws)
    with pytest.raises(asset_generation.AssetConflict, match='propiedad'):
        generate_all_devops_assets(str(ws), 'old', db_engine='H2')
    assert asset_generation.inventory(ws) == before
    assert not (ws / '.agentia-runtime/generated-assets.json').exists()


def test_generation_failure_does_not_leave_partial_source_mutations(tmp_path):
    ws = project(tmp_path)
    before = asset_generation.inventory(ws)
    existing_stages = set(asset_generation.STAGING_ROOT.glob('*'))
    def broken(stage, *args, **kwargs):
        (Path(stage) / 'pom.xml').write_text('changed in stage')
        raise RuntimeError('failed generator')
    with pytest.raises(RuntimeError, match='failed generator'):
        asset_generation.generate_safely(ws, 'failure', broken)
    assert asset_generation.inventory(ws) == before
    assert set(asset_generation.STAGING_ROOT.glob('*')) == existing_stages
    assert not docker_service._operation_locks['failure'].locked()


def test_commit_failure_rolls_back_sources(tmp_path, monkeypatch):
    ws = project(tmp_path)
    before = asset_generation.inventory(ws)
    native_copy = asset_generation.shutil.copyfile
    count = 0
    def fail_second_commit(source, destination, *args, **kwargs):
        nonlocal count
        if str(destination).endswith('.tmp'):
            count += 1
            if count == 2: raise OSError('disk unavailable')
        return native_copy(source, destination, *args, **kwargs)
    monkeypatch.setattr(asset_generation.shutil, 'copyfile', fail_second_commit)
    with pytest.raises(OSError, match='disk unavailable'):
        generate_all_devops_assets(str(ws), 'disk-failure', db_engine='H2')
    assert asset_generation.inventory(ws) == before
    assert not (ws / '.agentia-runtime/generated-assets.json').exists()


def test_concurrent_source_edit_rejected_at_publish_boundary(tmp_path):
    ws = project(tmp_path)
    def changing(stage, *args, **kwargs):
        result = _write_devops_assets(stage, *args, **kwargs)
        (ws / 'pom.xml').write_text('user edit while generating')
        return result
    with pytest.raises(asset_generation.AssetConflict, match='cambio'):
        asset_generation.generate_safely(ws, 'concurrent', changing, db_engine='H2')
    assert (ws / 'pom.xml').read_text() == 'user edit while generating'
    assert not (ws / 'docker-compose.yml').exists()


def test_active_deployment_prevents_generation_without_modifications(runtime):
    before = asset_generation.inventory(runtime.ws)
    lock = threading.Lock(); lock.acquire()
    docker_service._operation_locks[runtime.id] = lock
    try:
        with pytest.raises(asset_generation.AssetConflict, match='activa'):
            generate_all_devops_assets(str(runtime.ws), runtime.id, db_engine='H2')
        assert asset_generation.inventory(runtime.ws) == before
    finally:
        lock.release()


def test_sources_generation_has_no_docker_calls(tmp_path, monkeypatch):
    ws = project(tmp_path)
    def forbidden(*args, **kwargs): raise AssertionError('Docker called during generation')
    monkeypatch.setattr(docker_service.subprocess, 'run', forbidden)
    generate_all_devops_assets(str(ws), 'sources', db_engine='H2')
    assert (ws / 'docker-compose.yml').exists()


@pytest.mark.parametrize('invalid', ['future', 'identity', 'json'])
def test_invalid_registry_rejected_without_mutation(tmp_path, invalid):
    ws = project(tmp_path)
    generate_all_devops_assets(str(ws), 'new', db_engine='H2')
    path = ws / '.agentia-runtime/generated-assets.json'
    ledger = json.loads(path.read_text())
    if invalid == 'future': ledger['templateVersion'] = 999
    if invalid == 'identity': ledger['sessionId'] = 'foreign'
    path.write_text('invalid json' if invalid == 'json' else json.dumps(ledger))
    before = asset_generation.inventory(ws)
    with pytest.raises(asset_generation.AssetConflict, match='invalido'):
        generate_all_devops_assets(str(ws), 'new', db_engine='H2', host_port=18081)
    assert asset_generation.inventory(ws) == before


def test_registry_commit_failure_rolls_back_update(tmp_path, monkeypatch):
    ws = project(tmp_path)
    generate_all_devops_assets(str(ws), 'new', db_engine='H2')
    before = asset_generation.inventory(ws)
    registry = (ws / '.agentia-runtime/generated-assets.json').read_bytes()
    native_replace = Path.replace
    def fail_registry(path, destination):
        if Path(destination).name == 'generated-assets.json': raise OSError('registry unavailable')
        return native_replace(path, destination)
    monkeypatch.setattr(Path, 'replace', fail_registry)
    with pytest.raises(OSError, match='registry unavailable'):
        generate_all_devops_assets(str(ws), 'new', db_engine='H2', host_port=18081)
    assert asset_generation.inventory(ws) == before
    assert (ws / '.agentia-runtime/generated-assets.json').read_bytes() == registry
    assert not list((ws / '.agentia-runtime').glob('*.tmp'))


@pytest.mark.asyncio
async def test_api_returns_conflict_preserving_custom_asset(runtime, monkeypatch):
    from types import SimpleNamespace
    from fastapi import HTTPException
    from app.api import routes_devops
    from app.models.devops import DatabaseEngine
    monkeypatch.setattr(routes_devops, 'audit_workspace', lambda *a: SimpleNamespace(qualityGate=SimpleNamespace(canExport=True)))
    path = runtime.ws / 'Dockerfile'
    path.write_text('user custom asset')
    with pytest.raises(HTTPException) as failure:
        await routes_devops.generate_manifests(runtime.id, DatabaseEngine.H2, 18081)
    assert failure.value.status_code == 409
    assert path.read_text() == 'user custom asset'
