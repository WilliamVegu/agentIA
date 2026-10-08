"""Model/SQL projection preserves the draft instead of adding heuristics."""
from app.models.requirements import SpecificationDraft
from app.services.model_sql_service import _mock_domain_model_response
from integration.reliability_fixtures import ledger_draft


def test_domain_projection_preserves_explicit_columns_and_non_unique_email():
    payload=ledger_draft()
    payload['entities'][0]['attributes'][1].update(isUnique=False,columnName='account_email')
    response=_mock_domain_model_response(SpecificationDraft.model_validate(payload),'H2')
    entity=response.entities[0]
    assert {attribute.name for attribute in entity.attributes}=={attribute['name'] for attribute in payload['entities'][0]['attributes']}
    email=next(attribute for attribute in entity.attributes if attribute.name=='email')
    assert email.columnName=='account_email'
    assert email.isUnique is False
    assert not entity.hasAuditFields


def test_related_names_do_not_invent_foreign_keys_or_relationships():
    payload=ledger_draft()
    payload['entities'].append({'name':'LedgerEntryDetail','tableName':'ledger_entry_details','attributes':[{'name':'detailId','type':'UUID','isPrimaryKey':True},{'name':'description','type':'String','nullable':False}]})
    response=_mock_domain_model_response(SpecificationDraft.model_validate(payload),'POSTGRESQL')
    child=next(entity for entity in response.entities if entity.name=='LedgerEntryDetail')
    assert {attribute.name for attribute in child.attributes}=={'detailId','description'}
    assert child.relationships==[]
    assert all(not entity.relationships for entity in response.entities)


import pytest
from integration.reliability_fixtures import relational_ledger_draft
from app.services.domain_descriptor import normalize_blueprint


def test_explicit_foreign_key_preserves_custom_columns_and_primary_key(tmp_path):
    payload=relational_ledger_draft()
    typed=SpecificationDraft.model_validate(payload)
    response=_mock_domain_model_response(typed,'POSTGRESQL')
    assert 'FOREIGN KEY (owner_account) REFERENCES ledger_accounts(account_key)' in response.sqlSchema.schemaDdl
    assert 'ON DELETE CASCADE' not in response.sqlSchema.schemaDdl
    from app.orchestrator.stages.deterministic import domain
    files=domain.emit({'blueprint':typed.model_dump(),'workspace_path':str(tmp_path),'generated_files':{},'logs':[]})['generated_files']
    entity=next(code for path,code in files.items() if path.endswith('/LedgerEntry.java'))
    assert '@ManyToOne(fetch = FetchType.LAZY)' in entity
    assert 'name = "owner_account", referencedColumnName = "account_key", insertable = false, updatable = false' in entity
    assert 'java.util.UUID accountKey' in entity
    assert 'java.time.LocalDate effectiveDate' in entity
    assert 'java.time.LocalDateTime recordedAt' in entity


@pytest.mark.parametrize('change',[
    {'referencesEntity':'MissingAccount'},
    {'referencesAttribute':'name'},
    {'type':'Long'},
    {'referencesEntity':None},
])
def test_invalid_foreign_key_is_rejected_before_generation(change):
    payload=relational_ledger_draft()
    payload['entities'][1]['attributes'][4].update(change)
    with pytest.raises(ValueError):
        normalize_blueprint(payload)


@pytest.mark.parametrize('engine',['H2','POSTGRESQL','MYSQL'])
def test_initial_migration_enforces_the_same_foreign_key_as_model_projection(tmp_path,engine):
    from app.orchestrator.stages.deterministic import scaffolder
    payload=relational_ledger_draft();payload['databaseMode']=engine
    files=scaffolder.emit({'blueprint':payload,'workspace_path':str(tmp_path),'generated_files':{},'logs':[]})['generated_files']
    migration=next(code for path,code in files.items() if path.endswith('/'+engine.lower()+'/V1__initial.sql'))
    assert 'FOREIGN KEY (owner_account) REFERENCES ledger_accounts(account_key)' in migration
    assert 'ON DELETE CASCADE' not in migration
