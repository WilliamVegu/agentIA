from integration.reliability_fixtures import ledger_draft
from app.orchestrator.stages.deterministic import domain, service, controller


def test_native_sources_preserve_constraints_uuid_and_date(tmp_path):
    state={'blueprint':ledger_draft(),'workspace_path':str(tmp_path),'generated_files':{},'logs':[]}
    for module in [domain,service,controller]:
        state.update(module.emit(state))
    generated=state['generated_files']
    request=next(code for path,code in generated.items() if path.endswith('CreateLedgerEntryRequest.java'))
    entity=next(code for path,code in generated.items() if path.endswith('/LedgerEntry.java'))
    repo=next(code for path,code in generated.items() if path.endswith('LedgerEntryRepository.java'))
    assert '@Email' in request and '@Positive' in request
    assert 'java.time.Instant bookedAt' in request
    assert 'java.util.UUID entryId' in entity
    assert 'unique = true' in entity
    assert 'java.util.UUID' in repo
    assert 'Objects.equals(entryId, that.entryId)' in entity
    assert not any('findById(Long id)' in code or 'delete(Long id)' in code for code in generated.values())
    endpoints=next(code for path,code in generated.items() if path.endswith('LedgerEntryController.java') or path.endswith('LedgerEntryResource.java'))
    assert '@Valid' in endpoints


def test_scaffolding_uses_versioned_dialects_and_original_port(tmp_path):
    from app.orchestrator.stages.deterministic import scaffolder
    for engine in ['H2','POSTGRESQL','MYSQL']:
        draft=ledger_draft();draft['databaseMode']=engine
        state={'blueprint':draft,'workspace_path':str(tmp_path/engine),'generated_files':{},'logs':[]}
        files=scaffolder.emit(state)['generated_files']
        assert 'port: 18088' in files['src/main/resources/application.yml']
        assert 'ddl-auto: validate' in files['src/main/resources/application.yml']
        assert 'liquibase-core' in files['pom.xml']
        assert any(path.endswith('/mysql/V1__initial.sql') for path in files)
        if engine=='MYSQL': assert 'com.mysql' in files['pom.xml']
        if engine!='H2': assert ('org.hibernate.dialect.PostgreSQLDialect' if engine=='POSTGRESQL' else 'org.hibernate.dialect.MySQLDialect') in files['src/main/resources/application-prod.yml']
