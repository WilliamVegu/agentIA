"""Six reproducible source fixtures, without Docker/Java or providers."""
import hashlib
import json
import subprocess
from pathlib import Path
from xml.etree import ElementTree

import pytest
import yaml

from scripts.local_microservice_fixture import create_fixture
from app.services.build_layout import build_layout


@pytest.fixture(autouse=True)
def no_external_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Fixture creation must not execute Docker, Java or download tools')
    monkeypatch.setattr(subprocess, 'run', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)


@pytest.mark.parametrize('build', ['maven', 'gradle'])
@pytest.mark.parametrize('database', ['H2', 'POSTGRESQL', 'MYSQL'])
@pytest.mark.parametrize('seed', [False, True])
def test_fixture_reproducibility_and_delivery(tmp_path, build, database, seed):
    first, second = tmp_path / 'one', tmp_path / 'two'
    a = create_fixture(first, build, database, seed=seed)
    b = create_fixture(second, build, database, seed=seed)
    assert a == b
    assert a['files'] and a['execution'] == 'NOT_EXECUTED' and not a['offlineVerified']
    assert json.loads((first / 'FIXTURE_MANIFEST.json').read_text()) == a
    for relative, digest in a['files'].items():
        assert hashlib.sha256((first / relative).read_bytes()).hexdigest() == digest
    config = json.loads((first / 'ASSET_CONFIGURATION.json').read_text())
    assert config['databaseEngine'] == database
    assert build_layout(first)[0] == build
    dto = next(first.rglob('CreateItemRequest.java')).read_text()
    assert '@NotBlank' in dto
    entity = next(first.rglob('Item.java')).read_text()
    assert '@Entity' in entity and '@GeneratedValue' in entity
    controller = next(first.rglob('ItemController.java')).read_text()
    for mapping in ('@PostMapping', '@GetMapping', '@DeleteMapping', '@Valid'):
        assert mapping in controller
    assert '@PutMapping' in next(first.rglob('FixtureUpdateController.java')).read_text()
    tests = list(first.rglob('*Test*.java'))
    assert any('MockMvc' in p.read_text() for p in tests)
    assert any('Mockito' in p.read_text() for p in tests)
    schema = (first / 'schema.sql').read_text()
    assert ('inventory_records' if seed else 'items') in schema
    assert (first / 'data.sql').exists() == seed
    if build == 'maven':
        ElementTree.parse(first / 'pom.xml')
    compose = yaml.safe_load((first / 'docker-compose.yml').read_text())
    assert 'probe-service' in compose['services']
    database_services = [s for s in compose['services'].values()
                         if s.get('labels', {}).get('io.agentia.role') == 'database']
    assert len(database_services) == (0 if database == 'H2' else 1)
    assert (first / 'start-local.ps1').is_file()


@pytest.mark.parametrize('build', ['maven', 'gradle'])
def test_bootstrap_sources_need_no_assets_or_docker(tmp_path, build):
    ws = tmp_path / build
    manifest = create_fixture(ws, build, layout='bootstrap', assets=False)
    assert build_layout(ws)[:2] == (build, 'bootstrap')
    assert manifest['buildDirectory'] == 'bootstrap'
    assert all(p.startswith('bootstrap/') or p == 'schema.sql' for p in manifest['files'])
    assert not (ws / 'docker-compose.yml').exists()


def test_fixture_never_overwrites_existing_project(tmp_path):
    ws = tmp_path / 'existing'; ws.mkdir()
    sentinel = ws / 'pom.xml'; sentinel.write_text('user data')
    with pytest.raises(ValueError, match='new or empty'):
        create_fixture(ws)
    assert sentinel.read_text() == 'user data'
    assert list(ws.iterdir()) == [sentinel]


@pytest.mark.parametrize('kwargs', [{'build': 'unknown'}, {'database': 'unknown'}, {'layout': '../escape'}])
def test_invalid_catalog_option_does_not_create_destination(tmp_path, kwargs):
    ws = tmp_path / 'new'
    with pytest.raises(ValueError, match='Unsupported'):
        create_fixture(ws, **kwargs)
    assert not ws.exists()
