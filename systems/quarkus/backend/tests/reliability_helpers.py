"""Build real deterministic sources for source-delivery API fixtures, without Docker/IA."""
import json
from app.models.session import SessionLocal,GenerationSessionDB,SessionStatus,SessionPhase
from app.services.draft_revision_service import save_revision
from app.services.verification_policy import workspace_fingerprint
from app.orchestrator.stages.runner import run_stages
from integration.reliability_fixtures import ledger_draft


def prepare_source_delivery(session_id,workspace,*,service_name='order-service',database='H2',port=18088):
    draft=ledger_draft();draft.update(serviceName=service_name,databaseMode=database,basePort=port)
    save_revision(session_id,draft,source='MANUAL')
    result=run_stages({'session_id':session_id,'workspace_path':str(workspace),'blueprint':draft,
        'generation_mode':'DETERMINISTIC','generated_files':{},'logs':[]})
    assert result.get('status')!='BLOCKED'
    fingerprint=workspace_fingerprint(workspace)
    with SessionLocal() as db:
        session=db.get(GenerationSessionDB,session_id)
        session.status=SessionStatus.COMPLETED;session.phase=SessionPhase.CODE_GENERATION
        session.error_message=None;session.execution_mode='SOURCE_ONLY'
        session.verification_metrics_json=json.dumps({'verificationSkipped':True,'fallback_used':True,
            'verificationOutcome':'SKIPPED_BY_CHOICE','allPassed':False,'totalTests':0,
            'passedTests':0,'failedTests':0,'workspaceFingerprint':fingerprint,
            'sourceDeliveryReady':True,'sourceDeliveryFingerprint':fingerprint})
        db.commit()
    return result


def mark_source_delivery_current(session_id, workspace):
    with SessionLocal() as db:
        row=db.get(GenerationSessionDB,session_id)
        row.status=SessionStatus.COMPLETED
        row.phase=SessionPhase.CODE_GENERATION
        row.error_message=None
        row.execution_mode='SOURCE_ONLY'
        fingerprint=workspace_fingerprint(workspace)
        row.verification_metrics_json=json.dumps({'verificationSkipped':True,'allPassed':False,
            'fallback_used':False,'workspaceFingerprint':fingerprint,'sourceDeliveryReady':True,
            'sourceDeliveryFingerprint':fingerprint})
        db.commit()
