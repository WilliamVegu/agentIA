"""Regression checks for the native generators restored into the complete Studio."""
import xml.etree.ElementTree as ET
import pytest
from app.orchestrator.stages.deterministic import scaffolder, domain, service, controller, test_synthesis
from app.services.devops_service import generate_all_devops_assets
from app.services import spec_service
from app.models.blueprint import ArchitectureBlueprint


def blueprint(kind='UUID', database='H2'):
    return {'serviceName': 'native-inventory', 'packageName': 'com.example.inventory',
        'basePort': 8082, 'databaseMode': database,
        'entities': [{'name': 'Item', 'tableName': 'inventory_items', 'attributes': [
            {'name': 'itemKey', 'type': kind, 'isPrimaryKey': True},
            {'name': 'sku', 'type': 'String', 'validationRules': ['@NotBlank']}]}],
        'userStories': [{'id': 'US-1', 'priority': 'P1', 'role': 'Operator',
            'intent': 'track items', 'benefit': 'see inventory', 'scenarios': [
                {'scenarioId': 'AC-1', 'given': 'an item', 'when': 'read it', 'then': 'return its details'}]}]}


@pytest.mark.parametrize('kind,java_type', [('UUID', 'java.util.UUID'), ('String', 'String'), ('Long', 'Long'), ('Integer', 'Integer')])
def test_identifier_type_and_custom_name_survive_every_stage(tmp_path, kind, java_type):
    state = {'blueprint': blueprint(kind), 'workspace_path': str(tmp_path), 'generated_files': {}, 'logs': []}
    for stage in (scaffolder, domain, service, controller, test_synthesis):
        state.update(stage.emit(state))
    entity = (tmp_path / 'src/main/java/com/example/inventory/model/entity/Item.java').read_text()
    assert f'{java_type} itemKey' in entity
    assert '@Table(name = "inventory_items")' in entity
    for folder, suffix in [('repository', 'Repository'), ('service', 'Service'), ('controller', 'Controller')]:
        code = (tmp_path / f'src/main/java/com/example/inventory/{folder}/Item{suffix}.java').read_text()
        assert f'{java_type} id' in code
    java = '\n'.join(p.read_text() for p in tmp_path.rglob('*.java'))
    assert 'org.springframework' not in java
    assert '@QuarkusTest' in java


@pytest.mark.parametrize('database,driver', [('H2', 'h2'), ('POSTGRESQL', 'postgresql'), ('MYSQL', 'mysql')])
def test_selected_database_extension_is_a_runtime_dependency(tmp_path, database, driver):
    scaffolder.emit({'blueprint': blueprint(database=database), 'workspace_path': str(tmp_path)})
    ns = {'m': 'http://maven.apache.org/POM/4.0.0'}
    pom = ET.parse(tmp_path / 'pom.xml').getroot()
    ids = [node.text for node in pom.findall('m:dependencies/m:dependency/m:artifactId', ns)]
    assert 'quarkus-jdbc-' + driver in ids
    assert pom.find('m:dependencyManagement/m:dependencies/m:dependency/m:artifactId', ns).text == '${quarkus.platform.artifact-id}'


def test_devops_injects_driver_outside_bom_management(tmp_path):
    scaffolder.emit({'blueprint': blueprint(), 'workspace_path': str(tmp_path)})
    generate_all_devops_assets(str(tmp_path), 'native-session', 'native-inventory', db_engine='MYSQL')
    ns = {'m': 'http://maven.apache.org/POM/4.0.0'}
    pom = ET.parse(tmp_path / 'pom.xml').getroot()
    assert pom.find("m:dependencies/m:dependency[m:artifactId='quarkus-jdbc-mysql']", ns) is not None
    assert pom.find("m:dependencyManagement/m:dependencies/m:dependency[m:artifactId='quarkus-jdbc-mysql']", ns) is None


def test_specification_can_be_read_after_memory_cache_is_lost(tmp_path, monkeypatch):
    monkeypatch.setattr(spec_service.settings, 'SPECIFICATION_DIR', str(tmp_path))
    monkeypatch.setattr(spec_service, 'SPECIFICATIONS_STORE', {})
    expected = ArchitectureBlueprint.model_validate(blueprint())
    saved = spec_service.save_specification(expected)
    spec_service.SPECIFICATIONS_STORE.clear()
    assert spec_service.get_specification(saved.specId) == expected
    with pytest.raises(KeyError):
        spec_service.get_specification('../outside')


def test_declared_primary_key_wins_over_an_ordinary_id_field(tmp_path):
    spec = blueprint()
    spec['entities'][0]['attributes'].insert(0, {'name': 'id', 'type': 'String'})
    state = {'blueprint': spec, 'workspace_path': str(tmp_path), 'generated_files': {}}
    for stage in (domain, service, test_synthesis):
        state.update(stage.emit(state))
    java = state['generated_files']['src/main/java/com/example/inventory/model/entity/Item.java']
    assert java.count('@Id') == 1
    assert 'private java.util.UUID itemKey;' in java
    assert 'private String id;' in java
    dto = state['generated_files']['src/main/java/com/example/inventory/model/dto/CreateItemRequest.java']
    assert 'String id' in dto
