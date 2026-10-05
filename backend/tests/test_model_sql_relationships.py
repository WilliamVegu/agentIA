import pytest
from app.models.domain_model import DomainEntityDefinition as Entity, EntityAttributeDefinition as Attr, EntityRelationshipDefinition as Rel, RelationshipType as Kind, JavaPropertyType as Java, SqlDataType as SQL
from app.services.model_sql_service import generate_schema_sql, generate_seed_data_sql, generate_java_entity_source, model_sql_service
from app.models.requirements import SpecificationDraft
from app.models.blueprint import DomainEntity, EntityAttribute


def entity(name, pk=SQL.UUID):
    return Entity(name=name, tableName='custom_' + name.lower(), packageName='com.example.model', attributes=[
        Attr(name='key', columnName='entity_key', javaType=Java.UUID if pk == SQL.UUID else Java.LONG,
             sqlType=pk, isPrimaryKey=True)])


@pytest.mark.parametrize('engine', ['H2', 'POSTGRESQL', 'MYSQL'])
def test_uuid_owning_relations_seed_types_default_column_and_one_to_one(engine):
    parent, child = entity('Parent'), entity('Child', SQL.BIGINT)
    child.relationships = [Rel(sourceEntity='Child', targetEntity='Parent', relationshipType=Kind.ONE_TO_ONE)]
    schema = generate_schema_sql([child, parent], engine)
    assert 'parent_id ' + ('BINARY(16)' if engine == 'MYSQL' else 'UUID') + ' NOT NULL UNIQUE' in schema
    assert 'REFERENCES custom_parent(entity_key)' in schema
    seed = generate_seed_data_sql([child, parent], db_engine=engine)
    assert seed.index('INSERT INTO custom_parent') < seed.index('INSERT INTO custom_child')
    assert 'parent_id' in seed
    assert ('UNHEX(' in seed) == (engine == 'MYSQL')


@pytest.mark.parametrize('engine', ['H2', 'POSTGRESQL', 'MYSQL'])
def test_many_to_many_sql_java_and_seed_agree_on_custom_tables(engine):
    left, right = entity('Account'), entity('Role', SQL.BIGINT)
    for source, target in [(left, right), (right, left)]:
        source.relationships = [Rel(sourceEntity=source.name, targetEntity=target.name, relationshipType=Kind.MANY_TO_MANY)]
    schema = generate_schema_sql([right, left], engine)
    assert schema.count('CREATE TABLE IF NOT EXISTS custom_account_custom_role') == 1
    assert 'PRIMARY KEY (account_id, role_id)' in schema
    seed = generate_seed_data_sql([right, left], db_engine=engine)
    assert seed.index('INSERT INTO custom_account_custom_role') > seed.index('INSERT INTO custom_role')
    java = generate_java_entity_source(left, [left, right])
    assert '@JoinTable(name = "custom_account_custom_role"' in java
    assert 'package com.example.model;' in java and '.model.model' not in java
    assert '@ManyToMany(mappedBy = "roles"' in generate_java_entity_source(right, [left, right])


def test_incompatible_fk_and_mandatory_cycle_fail_before_publishing_sql():
    parent, child = entity('Parent'), entity('Child', SQL.BIGINT)
    child.attributes.append(Attr(name='parentId', columnName='parent_id', sqlType=SQL.BIGINT, javaType=Java.LONG))
    child.relationships = [Rel(sourceEntity='Child', targetEntity='Parent', relationshipType=Kind.MANY_TO_ONE, joinColumnName='parent_id')]
    with pytest.raises(ValueError, match='Tipo FK incompatible'):
        generate_schema_sql([parent, child])
    child.attributes.pop()
    parent.relationships = [Rel(sourceEntity='Parent', targetEntity='Child', relationshipType=Kind.MANY_TO_ONE)]
    with pytest.raises(ValueError, match='ciclo obligatorio'):
        generate_seed_data_sql([parent, child])


@pytest.mark.parametrize('engine', ['H2', 'POSTGRESQL', 'MYSQL'])
def test_inferred_uuid_fk_and_audit_lifecycle_are_coherent(engine):
    draft = SpecificationDraft(serviceName='orders', packageName='com.example', entities=[
        DomainEntity(name='Order', tableName='orders', attributes=[EntityAttribute(name='id', type='UUID', isPrimaryKey=True)]),
        DomainEntity(name='OrderItem', tableName='order_items', attributes=[EntityAttribute(name='id', type='Long', isPrimaryKey=True)])], userStories=[])
    result = model_sql_service.synthesize_domain_models_and_sql(draft, provider='mock', db_engine=engine)
    child = next(e for e in result.entities if e.name == 'OrderItem')
    assert next(a for a in child.attributes if a.columnName == 'order_id').sqlType == SQL.UUID
    assert '@PrePersist' in result.javaEntityClasses['OrderItem'] and '@PreUpdate' in result.javaEntityClasses['OrderItem']
    assert 'insertable = false, updatable = false' in result.javaEntityClasses['OrderItem']
