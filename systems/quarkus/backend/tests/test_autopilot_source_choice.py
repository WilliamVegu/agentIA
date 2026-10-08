"""Real source-only Auto-Pilot must finish without entering the Docker branch."""
import json
import pytest
from fastapi import HTTPException
from test_draft_authority import session
from integration.reliability_fixtures import ledger_draft
from app.models.session import SessionLocal, GenerationSessionDB, SessionStatus
from app.models.orchestrator import LifecyclePhase
from app.services import pipeline_runner as pipeline
from app.services.draft_revision_service import save_revision, approve_revision
from app.services.operation_repository import get_operation


def test_missing_generation_choice_does_not_begin_an_operation(session):
    session.mkdir()
    with pytest.raises(HTTPException) as observed:
        pipeline.run_pipeline('draft-authority')
    assert observed.value.status_code==422
    assert get_operation('draft-authority') is None
    with SessionLocal() as db:
        assert db.get(GenerationSessionDB,'draft-authority').status==SessionStatus.QUEUED


def test_source_only_auto_deploy_finishes_without_docker(session,monkeypatch):
    draft=ledger_draft();revision=save_revision('draft-authority',draft)
    approve_revision('draft-authority',revision['revisionId'])
    def forbidden(*args,**kwargs):raise AssertionError('SOURCE_ONLY does not deploy or probe Docker')
    monkeypatch.setattr(pipeline,'deploy_local',forbidden)
    from app.services import docker_service
    monkeypatch.setattr(docker_service,'check_docker_daemon',forbidden)
    assert pipeline.run_pipeline('draft-authority',target_phase=LifecyclePhase.COMPLETED,auto_deploy=True,provider='mock')
    worker=pipeline._active_threads['draft-authority'];worker.join(30)
    assert not worker.is_alive()
    operation=get_operation('draft-authority')
    with SessionLocal() as db:
        row=db.get(GenerationSessionDB,'draft-authority')
        assert operation['state']=='COMPLETED' and row.status==SessionStatus.COMPLETED,(operation,row.error_message)
        metrics=json.loads(row.verification_metrics_json)
        assert metrics['verificationSkipped'] and metrics['totalTests']==0 and not metrics['allPassed']
