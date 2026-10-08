import pytest
from fastapi import HTTPException
from test_draft_authority import session
from integration.reliability_fixtures import ledger_draft

def test_configuration_version_prevents_stale_save_and_approval(session):
    from app.services.draft_revision_service import save_revision,approve_revision,get_revision
    first=save_revision('draft-authority',ledger_draft(),expected_version=0)
    with pytest.raises(HTTPException) as error:
        save_revision('draft-authority',ledger_draft(),expected_version=0)
    assert error.value.status_code==409
    with pytest.raises(HTTPException) as error:
        approve_revision('draft-authority',first['revisionId'],expected_version=0)
    assert error.value.status_code==409
    assert approve_revision('draft-authority',first['revisionId'],expected_version=first['configurationVersion'])['approvalStatus']=='APPROVED'
    with pytest.raises(HTTPException) as error:
        get_revision('draft-authority','nonexistent')
    assert error.value.status_code==404

def test_changed_revision_invalidates_descendants_and_keeps_content(session):
    from app.services.draft_revision_service import save_revision,record_artifact,get_revision
    from app.models.session import SessionLocal
    from app.models.reliability import ArtifactProvenance,DraftRevision
    first=save_revision('draft-authority',ledger_draft())
    (session/'schema.sql').write_text('CREATE TABLE test (id BIGINT);')
    record_artifact('draft-authority','schema.sql','DATA_MODEL',first['revisionId'])
    changed=ledger_draft();changed['basePort']=18089
    second=save_revision('draft-authority',changed,expected_revision_id=first['revisionId'])
    with SessionLocal() as db:
        item=db.query(ArtifactProvenance).filter_by(session_id='draft-authority').one()
        assert item.status=='OUTDATED'
        row=db.get(DraftRevision,first['revisionId'])
        row.payload_json='{}'
        with pytest.raises(ValueError): db.commit()
    assert get_revision('draft-authority',first['revisionId'])['draft']['basePort']==18088
    assert get_revision('draft-authority')['revisionId']==second['revisionId']


def test_explicit_regeneration_keeps_backup_before_replacing_sources(session):
    from app.services.draft_revision_service import save_revision,record_artifact,prepare_regeneration
    from app.models.session import SessionLocal
    from app.models.reliability import ArtifactProvenance
    import zipfile
    first=save_revision('draft-authority',ledger_draft())
    source=session/'src/main/java/Previous.java';source.parent.mkdir(parents=True);source.write_text('original source')
    record_artifact('draft-authority','src/main/java/Previous.java','CODE_TESTS',first['revisionId'])
    changed=ledger_draft();changed['basePort']=18089
    second=save_revision('draft-authority',changed,expected_revision_id=first['revisionId'])
    with pytest.raises(HTTPException): prepare_regeneration('draft-authority',first['revisionId'])
    assert source.read_text()=='original source'
    backup=prepare_regeneration('draft-authority',second['revisionId'])
    with zipfile.ZipFile(backup) as archive:
        assert archive.read('src/main/java/Previous.java')==b'original source'
    assert not source.exists()
    with SessionLocal() as db:
        assert not db.query(ArtifactProvenance).filter_by(session_id='draft-authority').first()
