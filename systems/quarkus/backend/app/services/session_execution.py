"""Explicit verification of existing Quarkus sources with a durable writer operation."""
import json
from fastapi import HTTPException
from app.models.session import SessionLocal,GenerationSessionDB,SessionStatus,SessionPhase
from app.models.execution import ExecutionMode
from app.services.session_operation_lock import SessionOperationLock
from app.services.workspace_guard import get_validated_workspace_path
from app.services.operation_repository import begin_operation,transition_operation,get_operation


def verify_existing_sources(session_id):
    workspace=get_validated_workspace_path(session_id,require_exists=True)
    lock=SessionOperationLock(session_id)
    if not lock.acquire(False): raise HTTPException(409,'Existe una operación activa')
    operation=None
    try:
        from app.services.build_layout import build_layout
        from app.services.security_service import audit_workspace
        from app.services.graph_completion_policy import previous_failed
        from app.services.verification_policy import workspace_fingerprint,tests_really_passed
        from app.services.workspace_verification import run_workspace_verification
        from app.services.verification_evidence import verification_metrics
        if not any((workspace/'src').rglob('*.java')): raise HTTPException(409,'Genere primero el código fuente')
        build_layout(workspace)
        with SessionLocal() as db:
            session=db.get(GenerationSessionDB,session_id)
            mode=session.execution_mode;name=session.spec_name
            prior=json.loads(session.verification_metrics_json or '{}');failed=previous_failed(session)
        if mode==ExecutionMode.DOCKER:
            from app.services.local_runtime import configuration
            config=configuration(session_id)
            if not config['databaseEngine'] or not config['hostPort']: raise HTTPException(409,'Guarde y apruebe la configuración del proyecto')
            if not (workspace/'docker-compose.yml').is_file():
                from app.services.devops_service import generate_all_devops_assets
                generate_all_devops_assets(str(workspace),session_id,config['serviceName'] or name,config['databaseEngine'],config['hostPort'])
        audit=audit_workspace(str(workspace),session_id,name)
        if not audit.qualityGate.canExport: raise HTTPException(403,audit.qualityGate.summaryMessage)
        operation=begin_operation(session_id,'CODE_TESTS',{'entryPoint':'VERIFY_EXISTING'})
        operation=transition_operation(operation['operationId'],operation['version'],'RUNNING')
        verification=run_workspace_verification(workspace,mode=mode)
        metrics=verification_metrics(verification)
        completed=tests_really_passed(metrics) and bool(metrics.get('sourceSnapshotId'))
        if verification.result.verification_skipped:
            completed=not failed
            if failed: metrics={**prior,'verificationOutdated':True,'sourceDeliveryReady':False}
            else: metrics.update(sourceDeliveryReady=True,sourceDeliveryFingerprint=workspace_fingerprint(workspace))
        unavailable=verification.result.fallback_used and not verification.result.verification_skipped
        terminal='COMPLETED' if completed else 'BLOCKED'
        current=get_operation(session_id,operation['operationId'])
        transition_operation(current['operationId'],current['version'],terminal)
        with SessionLocal() as db:
            session=db.get(GenerationSessionDB,session_id)
            session.verification_metrics_json=json.dumps(metrics)
            session.status=SessionStatus.COMPLETED if completed else SessionStatus.PAUSED if unavailable else SessionStatus.BLOCKED
            session.phase=SessionPhase.CODE_GENERATION if completed and verification.result.verification_skipped else SessionPhase.VERIFIED if completed else SessionPhase.FAILED
            session.error_message=None if completed else verification.result.evidence_error or verification.result.fallback_reason or 'La verificación no fue aprobada'
            db.commit()
        return {'sessionId':session_id,'metrics':metrics,'status':'COMPLETED' if completed else 'PAUSED' if unavailable else 'BLOCKED'}
    except Exception as error:
        if operation:
            current=get_operation(session_id,operation['operationId'])
            if current['state'] in {'QUEUED','RUNNING'}: transition_operation(current['operationId'],current['version'],'BLOCKED',error_code=type(error).__name__)
        raise
    finally: lock.release()
