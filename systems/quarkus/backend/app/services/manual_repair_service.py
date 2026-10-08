"""Apply exactly one local edit; verify native sources without regeneration."""
import hashlib
import json
from contextlib import nullcontext
from fastapi import HTTPException
from app.models.session import SessionLocal, GenerationSessionDB, SessionStatus, SessionPhase
from app.models.reliability import RepairAttempt, PipelineOperation
from app.services.workspace_guard import resolve_workspace_file, atomic_write_workspace_file, io_path
from app.services.session_operation_lock import SessionOperationLock
from app.services.secret_redaction import redact
from app.services.verification_evidence import invalidate_evidence, verification_metrics


def manual_repair(session_id, request):
    file=resolve_workspace_file(session_id,request.filePath,require_exists=True)
    if request.modifiedCode is None:
        raise HTTPException(422,'modifiedCode es obligatorio; una pista no aplica una reparación')
    lock=SessionOperationLock(session_id)
    if not lock.acquire(False):
        raise HTTPException(409,'Ya existe una operación escritora')
    try:
        with SessionLocal() as db:
            if db.query(PipelineOperation).filter_by(session_id=session_id).filter(PipelineOperation.state.in_(['QUEUED','RUNNING','PAUSE_REQUESTED','CANCEL_REQUESTED'])).first():
                raise HTTPException(409,'Espere a la operación activa')
            session=db.get(GenerationSessionDB,session_id)
            previous=json.loads(session.verification_metrics_json or '{}')
            mode=session.execution_mode
        before=hashlib.sha256(io_path(file).read_bytes()).hexdigest()
        invalidate_evidence(session_id)
        atomic_write_workspace_file(session_id,request.filePath,request.modifiedCode)
        with SessionLocal() as db:
            session=db.get(GenerationSessionDB,session_id)
            session.status=SessionStatus.BLOCKED;session.phase=SessionPhase.FAILED
            attempt=RepairAttempt(session_id=session_id,relative_path=request.filePath,
                before_hash=before,after_hash=hashlib.sha256(request.modifiedCode.encode()).hexdigest(),
                guidance_hint=redact(request.guidanceHint),outcome='APPLIED_UNVERIFIED')
            db.add(attempt);db.commit();repair_id=attempt.repair_id
        from app.services.workspace_verification import run_workspace_verification
        from app.services.verification_policy import tests_really_passed
        context=nullcontext()
        if 'quarkus' == 'springboot':
            from app.services.local_operations import borrowed_lock
            context=borrowed_lock(session_id)
        try:
            with context:
                verification=run_workspace_verification(file_root(session_id),mode=mode)
            metrics=verification_metrics(verification)
            verified=tests_really_passed(metrics)
            if verification.result.verification_skipped and previous:
                metrics={**previous, 'verificationOutdated':True, 'sourceDeliveryReady':False}
            with SessionLocal() as db:
                session=db.get(GenerationSessionDB,session_id)
                session.verification_metrics_json=json.dumps(metrics)
                session.status=SessionStatus.COMPLETED if verified else SessionStatus.BLOCKED
                session.phase=SessionPhase.VERIFIED if verified else SessionPhase.FAILED
                session.error_message=None if verified else 'Edición aplicada; verificación no aprobada'
                attempt=db.get(RepairAttempt,repair_id)
                attempt.outcome='VERIFIED' if verified else 'APPLIED_UNVERIFIED'
                from app.models.reliability import VerificationRun
                record=db.query(VerificationRun).filter_by(session_id=session_id).order_by(VerificationRun.created_at.desc()).first()
                attempt.verification_run_id=record.run_id if record else None
                db.commit()
        except Exception as error:
            with SessionLocal() as db:
                session=db.get(GenerationSessionDB,session_id)
                session.error_message=redact(str(error))
                db.commit()
            verified=False
        return {'sessionId':session_id,'status':'VERIFIED' if verified else 'APPLIED_UNVERIFIED',
            'diagnosticsResolved':verified,'message':'Pruebas reales aprobadas' if verified else 'Edición aplicada; verificación no aprobada'}
    finally:
        lock.release()


def file_root(session_id):
    from app.services.workspace_guard import get_validated_workspace_path
    return get_validated_workspace_path(session_id,require_exists=True)
