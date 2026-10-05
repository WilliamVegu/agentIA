"""Integrity failures precede writes or processes; no Docker or package registry."""
import importlib.util
import json
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('native_kit', Path(__file__).resolve().parents[2] / 'scripts/native_offline_kit.py')
kit_tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kit_tool)


@pytest.fixture
def prepared(tmp_path):
    project, kit = tmp_path / 'project', tmp_path / 'kit'
    kit.mkdir()
    for name in kit_tool.BUILD_FILES:
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('fixture')
    wheel = kit / 'wheels/package.whl'
    wheel.parent.mkdir()
    wheel.write_bytes(b'wheel fixture')
    nested = kit / 'node/manifest.json'
    nested.parent.mkdir()
    nested.write_text('runtime metadata')
    manifest = {'formatVersion': 1, 'platform': kit_tool.sys.platform, 'machine': kit_tool.platform.machine(),
                'projectFiles': kit_tool.project_hashes(project),
                'files': {file.relative_to(kit).as_posix(): {'bytes': file.stat().st_size, 'sha256': kit_tool.digest(file)}
                          for file in kit_tool.files(kit)}}
    (kit / 'manifest.json').write_text(json.dumps(manifest))
    return project, kit, tmp_path / 'fresh'


@pytest.mark.parametrize('case', ['wheel', 'nested-manifest', 'extra-file', 'missing-file', 'dependency', 'architecture'])
def test_modified_kit_is_rejected_before_installation(prepared, monkeypatch, case):
    project, kit, destination = prepared
    if case == 'wheel':
        (kit / 'wheels/package.whl').write_bytes(b'changed wheel')
    elif case == 'nested-manifest':
        (kit / 'node/manifest.json').write_text('changed metadata')
    elif case == 'extra-file':
        (kit / 'extra').write_text('unexpected')
    elif case == 'missing-file':
        (kit / 'wheels/package.whl').unlink()
    elif case == 'dependency':
        (project / 'backend/requirements.txt').write_text('changed requirement')
    else:
        path = kit / 'manifest.json'
        manifest = json.loads(path.read_text())
        manifest['machine'] = 'incompatible'
        path.write_text(json.dumps(manifest))
    def forbidden(*args, **kwargs):
        raise AssertionError('No se ejecutan procesos para un kit inválido')
    monkeypatch.setattr(kit_tool.subprocess, 'run', forbidden)
    with pytest.raises(ValueError):
        kit_tool.install(project, kit, destination)
    assert not destination.exists()


def test_valid_kit_verifies_without_processes(prepared, monkeypatch):
    project, kit, _ = prepared
    monkeypatch.setattr(kit_tool.subprocess, 'run', lambda *a, **kw: pytest.fail('Proceso inesperado'))
    assert kit_tool.verify(project, kit)['formatVersion'] == 1
