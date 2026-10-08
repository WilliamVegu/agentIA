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
