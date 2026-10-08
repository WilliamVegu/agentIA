import pytest
from fastapi import HTTPException
from app.config import settings
from app.models.session import SessionLocal, GenerationSessionDB
from integration.reliability_fixtures import ledger_draft

@pytest.fixture
def session(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'WORKSPACE_DIR', str(tmp_path))
    with SessionLocal() as db:
        db.add(GenerationSessionDB(id='draft-authority', spec_id='draft-spec', spec_name='Ledger'))
        db.commit()
    yield tmp_path / 'draft-authority'
    from app.models.reliability import DraftRevision, SessionConfiguration, ArtifactProvenance, PipelineOperation, SessionEvent
    with SessionLocal() as db:
        for model in (SessionEvent, PipelineOperation, ArtifactProvenance, DraftRevision, SessionConfiguration):
            db.query(model).filter_by(session_id='draft-authority').delete()
        db.query(GenerationSessionDB).filter_by(id='draft-authority').delete()
        db.commit()

def test_save_approve_reload_pipeline_preserves_complete_draft(session):
    from app.services.draft_revision_service import save_revision, approve_revision, get_revision
    result = save_revision('draft-authority', ledger_draft())
    assert result['approvalStatus'] == 'DRAFT'
    approve_revision('draft-authority', result['revisionId'])
    restored = get_revision('draft-authority')
    assert restored['draft']['packageName'] == 'com.audit.custom'
    assert restored['draft']['basePort'] == 18088
    assert restored['draft']['entities'][0]['name'] == 'LedgerEntry'
    assert restored['draft']['entities'][0]['attributes'][1]['isUnique']
    from app.services.pipeline_runner import _get_or_create_draft
    generated = _get_or_create_draft(session, 'Other service', api_key='must-not-call')
    assert generated.model_dump() == restored['draft']

def test_concurrent_revision_and_approval_are_not_inherited(session):
    from app.services.draft_revision_service import save_revision, approve_revision, get_revision
    first = save_revision('draft-authority', ledger_draft())
    approve_revision('draft-authority', first['revisionId'])
    changed = ledger_draft(); changed['basePort'] = 18089
    second = save_revision('draft-authority', changed, expected_revision_id=first['revisionId'])
    assert second['approvalStatus'] == 'DRAFT'
    assert second['canonicalHash'] != first['canonicalHash']
    with pytest.raises(HTTPException) as error:
        save_revision('draft-authority', changed, expected_revision_id=first['revisionId'])
    assert error.value.status_code == 409
    with pytest.raises(HTTPException) as error:
        approve_revision('draft-authority', first['revisionId'])
    assert error.value.status_code == 409
    assert get_revision('draft-authority')['revisionId'] == second['revisionId']

def test_invalid_legacy_is_not_replaced_by_invented_entities(session):
    session.mkdir(); (session/'specification_draft.json').write_text('{broken')
    from app.services.draft_revision_service import get_revision
    result=get_revision('draft-authority')
    assert result['approvalStatus'] == 'NEEDS_REVIEW'
    assert result['draft'] is None

def test_real_autopilot_stops_at_stories_without_regenerating(session, monkeypatch):
    from app.services.draft_revision_service import save_revision, approve_revision
    from app.services import pipeline_runner
    from app.models.orchestrator import LifecyclePhase
    from app.services.operation_repository import get_operation
    revision=save_revision('draft-authority', ledger_draft())
    approve_revision('draft-authority', revision['revisionId'])
    def forbidden(*args, **kwargs):
        raise AssertionError('No provider call allowed for a saved draft')
    monkeypatch.setattr(pipeline_runner, 'transform_requirements', forbidden)
    assert pipeline_runner.run_pipeline('draft-authority', LifecyclePhase.STORIES, api_key='mock-key', provider='mock')
    pipeline_runner._active_threads['draft-authority'].join(timeout=10)
    operation=get_operation('draft-authority')
    assert operation['state'] == 'COMPLETED', operation
    assert operation['revisionId'] == revision['revisionId']
    assert not (session/'architecture.json').exists()
    import json
    assert json.loads((session/'specification_draft.json').read_text())['entities'][0]['name'] == 'LedgerEntry'


def test_nonfile_projection_blocks_before_revision_or_projection_writes(session):
    from app.services.draft_revision_service import save_revision
    from app.models.reliability import DraftRevision
    session.mkdir()
    (session/'spec.md').mkdir()
    with pytest.raises(HTTPException) as error:
        save_revision('draft-authority',ledger_draft())
    assert error.value.status_code==409
    assert (session/'spec.md').is_dir()
    assert not (session/'user_stories.json').exists()
    assert not (session/'specification_draft.json').exists()
    with SessionLocal() as db:
        assert db.get(GenerationSessionDB,'draft-authority').revision_id is None
        assert db.query(DraftRevision).filter_by(session_id='draft-authority').count()==0
