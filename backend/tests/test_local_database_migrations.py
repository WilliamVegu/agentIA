import xml.etree.ElementTree as ET
from types import SimpleNamespace
import pytest
from app.orchestrator.stages.deterministic import domain
from app.services.lifecycle_artifacts import blueprint_from_generated_code
from app.services.local_database_migrations import write_migrations
from app.services.model_sql_service import schema_sql_from_draft


def blueprint():
    return {'packageName': 'com.example.inventory', 'entities': [{'name': 'Item', 'tableName': 'inventory_records', 'attributes': [
        {'name': 'id', 'type': 'Long', 'isPrimaryKey': True, 'nullable': False},
        {'name': 'name', 'type': 'String', 'nullable': False, 'isUnique': True},
        {'name': 'amount', 'type': 'BigDecimal', 'nullable': False},
        {'name': 'requestedAt', 'type': 'LocalDateTime', 'nullable': False}]}]}


@pytest.mark.parametrize('database', ['H2', 'POSTGRESQL', 'MYSQL'])
def test_schema_migration_uses_actual_names_types_and_identity(tmp_path, database):
    draft = blueprint()
    domain.emit({'blueprint': draft, 'workspace_path': str(tmp_path)})
    write_migrations(tmp_path, database)
    sql = (tmp_path / 'schema.sql').read_text()
    java = next(tmp_path.glob('src/main/java/**/Item.java')).read_text()
    assert '@Table(name = "inventory_records")' in java
    assert 'java.time.LocalDateTime requestedAt' in java
    assert 'inventory_records' in sql and 'requested_at TIMESTAMP NOT NULL' in sql
    assert 'amount NUMERIC(19, 2) NOT NULL' in sql
    assert 'name VARCHAR(255) NOT NULL UNIQUE' in sql
    assert ('AUTO_INCREMENT' in sql) == (database == 'MYSQL')
    xml = tmp_path / 'src/main/resources/db/changelog/db.changelog-master.xml'
    ET.parse(xml)
    assert (xml.parent / '001-schema.sql').read_text() == sql
    before = xml.read_bytes()
    write_migrations(tmp_path, database)
    assert xml.read_bytes() == before


def test_authored_sql_and_seeds_are_preserved_and_versioned(tmp_path):
    schema = 'CREATE TABLE authored (id BIGINT PRIMARY KEY);\n'
    seed = 'INSERT INTO authored(id) VALUES (1);\n'
    (tmp_path / 'schema.sql').write_text(schema)
    (tmp_path / 'data.sql').write_text(seed)
    write_migrations(tmp_path, 'H2')
    path = tmp_path / 'src/main/resources/db/changelog'
    assert (path / '001-schema.sql').read_text() == schema
    assert (path / '002-seed.sql').read_text() == seed
    assert (tmp_path / 'schema.sql').read_text() == schema
    assert (tmp_path / 'data.sql').read_text() == seed
    assert '002-seed' in (path / 'db.changelog-master.xml').read_text()
    (tmp_path / 'data.sql').write_text('INSERT INTO authored(id) VALUES (2);')
    with pytest.raises(ValueError, match='nueva versión'):
        write_migrations(tmp_path, 'H2')
    assert (path / '002-seed.sql').read_text() == seed


def test_nested_entities_and_bootstrap_classpath(tmp_path):
    draft = blueprint()
    model = tmp_path / 'model'
    model.mkdir()
    domain.emit({'blueprint': draft, 'workspace_path': str(model)})
    boot = tmp_path / 'bootstrap'
    boot.mkdir()
    (boot / 'pom.xml').write_text('<project/>')
    recovered = blueprint_from_generated_code(tmp_path)
    assert recovered['entities'][0]['tableName'] == 'inventory_records'
    assert recovered['entities'][0]['attributes'][1]['isUnique']
    write_migrations(tmp_path, 'POSTGRESQL')
    assert (boot / 'src/main/resources/db/changelog/001-schema.sql').is_file()
    assert not (tmp_path / 'src/main/resources/db/changelog').exists()


def test_regeneration_preserves_appended_migration_versions(tmp_path):
    write_migrations(tmp_path, 'H2')
    path = tmp_path / 'src/main/resources/db/changelog'
    master = path / 'db.changelog-master.xml'
    extension = '  <changeSet id="003-extra" author="user"><sqlFile path="003-extra.sql" relativeToChangelogFile="true"/></changeSet>\n'
    content = master.read_text().replace('</databaseChangeLog>', extension + '</databaseChangeLog>')
    master.write_text(content)
    extra = path / '003-extra.sql'
    extra.write_text('CREATE TABLE extra(id BIGINT);')
    write_migrations(tmp_path, 'H2')
    assert master.read_text() == content
    assert extra.read_text() == 'CREATE TABLE extra(id BIGINT);'


def test_conflicting_properties_do_not_copy_partial_migrations(tmp_path):
    resources = tmp_path / 'src/main/resources'
    resources.mkdir(parents=True)
    props = resources / 'application.properties'
    props.write_text('spring.application.name=authored\n')
    with pytest.raises(ValueError, match='configure explícitamente'):
        write_migrations(tmp_path, 'H2')
    assert not (resources / 'db/changelog/001-schema.sql').exists()
    assert props.read_text() == 'spring.application.name=authored\n'
    assert not (tmp_path / 'schema.sql').exists()


@pytest.mark.parametrize('change', ['delete', 'empty'])
def test_published_seed_cannot_disappear_silently(tmp_path, change):
    (tmp_path / 'data.sql').write_text('INSERT INTO items(name) VALUES (\'seed\');')
    write_migrations(tmp_path, 'H2')
    if change == 'delete':
        (tmp_path / 'data.sql').unlink()
    else:
        (tmp_path / 'data.sql').write_text('')
    with pytest.raises(ValueError, match='retirada'):
        write_migrations(tmp_path, 'H2')
    assert (tmp_path / 'src/main/resources/db/changelog/002-seed.sql').read_text() == "INSERT INTO items(name) VALUES ('seed');"


def test_migration_seal_rejects_database_change(tmp_path):
    import json
    write_migrations(tmp_path, 'H2')
    seal = tmp_path / 'src/main/resources/db/changelog/LOCAL_MIGRATIONS.json'
    before = seal.read_bytes()
    assert json.loads(before)['seedPolicy'] == 'ONCE_PER_DATABASE'
    with pytest.raises(ValueError, match='Motor o contenido'):
        write_migrations(tmp_path, 'MYSQL')
    assert seal.read_bytes() == before


@pytest.mark.parametrize('override', ['spring.sql.init.mode=always', 'spring.jpa.hibernate.ddl-auto=create-drop',
                                     'spring.liquibase.change-log=classpath:other.xml'])
def test_conflicting_effective_property_is_rejected(tmp_path, override):
    write_migrations(tmp_path, 'H2')
    props = tmp_path / 'src/main/resources/application.properties'
    props.write_text(props.read_text() + override + '\n')
    with pytest.raises(ValueError, match='configure explícitamente'):
        write_migrations(tmp_path, 'H2')


@pytest.mark.parametrize('database', ['H2', 'POSTGRESQL', 'MYSQL'])
def test_uuid_primary_key_keeps_dialect_and_seed_type(database):
    from app.models.domain_model import DomainEntityDefinition, EntityAttributeDefinition
    from app.services.model_sql_service import generate_seed_data_sql
    draft = SimpleNamespace(entities=[SimpleNamespace(name='Record', tableName='records', attributes=[
        SimpleNamespace(name='id', type='UUID', isPrimaryKey=True)])])
    sql = schema_sql_from_draft(draft, database)
    expected = 'BINARY(16)' if database == 'MYSQL' else 'UUID'
    assert f'id {expected} PRIMARY KEY' in sql and 'IDENTITY' not in sql and 'AUTO_INCREMENT' not in sql
    entity = DomainEntityDefinition(name='Record', tableName='records', packageName='com.example',
        attributes=[EntityAttributeDefinition(name='id', columnName='id', javaType='UUID', sqlType='UUID', isPrimaryKey=True)])
    seed = generate_seed_data_sql([entity], db_engine=database)
    assert ('UNHEX(' in seed) == (database == 'MYSQL')
    assert 'a0000000' in seed and 'VALUES (1)' not in seed
