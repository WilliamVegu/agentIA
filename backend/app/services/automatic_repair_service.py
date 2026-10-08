"""A bounded repair applies current sources once and records a native verification result."""
import hashlib,json
from contextlib import nullcontext
from fastapi import HTTPException
from app.models.session import SessionLocal,GenerationSessionDB,SessionStatus,SessionPhase
from app.models.reliability import RepairAttempt,PipelineOperation
from app.models.test_analysis import RepairOutcome,RepairIterationRecord
from app.services.workspace_guard import get_validated_workspace_path,resolve_workspace_file,atomic_write_workspace_file,io_path
from app.services.session_operation_lock import SessionOperationLock
from app.services.verification_evidence import invalidate_evidence,verification_metrics
from app.services.verification_policy import tests_really_passed
from app.services.secret_redaction import redact


def automatic_repair(request,framework='springboot',effective_key=None, *, _operation_id=None):
    from app.services.test_analysis_service import test_analysis_service
    ws=get_validated_workspace_path(request.sessionId,require_exists=True)
    lock=SessionOperationLock(request.sessionId)
    owns_lock=_operation_id is None
    if owns_lock and not lock.acquire(False): raise HTTPException(409,'Otra operación escribe esta sesión')
    if not owns_lock and not lock.locked(): raise HTTPException(409,'El grafo requiere su escritor activo')
    repair_id=None
    try:
        if not request.sourceFiles: raise HTTPException(422,'Se requieren fuentes actuales para aplicar una reparación')
        paths={relative:resolve_workspace_file(request.sessionId,relative,require_exists=True) for relative in request.sourceFiles}
        for relative,file in paths.items():
            if io_path(file).read_text(encoding='utf-8')!=request.sourceFiles[relative]:
                raise HTTPException(409,'Las fuentes cambiaron; recargue antes de reparar')
        with SessionLocal() as db:
            active=db.query(PipelineOperation).filter_by(session_id=request.sessionId).filter(PipelineOperation.state.in_(['QUEUED','RUNNING','PAUSE_REQUESTED','CANCEL_REQUESTED'])).first()
            session=db.get(GenerationSessionDB,request.sessionId)
            if _operation_id is None and active:
                raise HTTPException(409,'Existe una operación activa')
            if _operation_id is not None and (not active or active.operation_id!=_operation_id or active.state!='RUNNING'
                    or active.revision_id!=session.revision_id or active.config_version!=(session.configuration_version or 1)):
                raise HTTPException(409,'La reparación del grafo no pertenece a la operación vigente')
            attempts=db.query(RepairAttempt).filter_by(session_id=request.sessionId,automatic=1).count()
            if attempts>=3 or request.iterationNumber!=attempts+1: raise HTTPException(409,'Límite de tres intentos o número de intento obsoleto')
            session=db.get(GenerationSessionDB,request.sessionId)
            previous=json.loads(session.verification_metrics_json or '{}');mode=session.execution_mode
            attempt=RepairAttempt(session_id=request.sessionId,relative_path=next(iter(paths)),automatic=1,iteration=attempts+1,outcome='PLANNING')
            db.add(attempt);db.commit();repair_id=attempt.repair_id
        # No model call occurs until identity, ownership, sources and budget have passed.
        options={'session_id':request.sessionId,'iteration_number':request.iterationNumber,'diagnostics':request.diagnostics,'source_files':request.sourceFiles,'api_key':effective_key or request.apiKey}
        if framework=='springboot': options.update(provider=request.provider,model_name=request.modelName)
        record=test_analysis_service.execute_repair_iteration(**options)
        current=dict(request.sourceFiles)
        for patch in record.patchesApplied: current,_=test_analysis_service.apply_code_patch(current,patch)
        if set(current)!=set(paths): raise HTTPException(422,'La reparación no puede agregar rutas fuera de las fuentes validadas')
        # Revalidate every input before the first mutation.
        for relative,file in paths.items():
            if io_path(file).read_text(encoding='utf-8')!=request.sourceFiles[relative]: raise HTTPException(409,'Fuente modificada durante la planificación')
        invalidate_evidence(request.sessionId)
        with SessionLocal() as db:
            session=db.get(GenerationSessionDB,request.sessionId);session.status=SessionStatus.BLOCKED;session.phase=SessionPhase.FAILED;db.commit()
        for relative,content in current.items():
            if content!=request.sourceFiles[relative]: atomic_write_workspace_file(request.sessionId,relative,content)
        from app.services.workspace_verification import run_workspace_verification
        context=nullcontext()
        if framework=='springboot':
            from app.services.local_operations import borrowed_lock
            context=borrowed_lock(request.sessionId)
        with context: verification=run_workspace_verification(str(ws),mode=mode)
        metrics=verification_metrics(verification);verified=tests_really_passed(metrics)
        if verification.result.verification_skipped and previous:
            metrics={**previous,'verificationOutdated':True,'sourceDeliveryReady':False}
        record.passedTestsBefore=previous.get('passedTests',0);record.failedTestsBefore=previous.get('failedTests',0)
        record.passedTestsAfter=metrics.get('passedTests',0);record.failedTestsAfter=metrics.get('failedTests',0)
        record.outcome=RepairOutcome.SUCCESS if verified else RepairOutcome.FAILED_BLOCKED if request.iterationNumber>=3 else RepairOutcome.FAILED_CONTINUE
        with SessionLocal() as db:
            session=db.get(GenerationSessionDB,request.sessionId)
            session.verification_metrics_json=json.dumps(metrics)
            session.status=SessionStatus.COMPLETED if verified else SessionStatus.BLOCKED
            session.phase=SessionPhase.VERIFIED if verified else SessionPhase.FAILED
            session.error_message=None if verified else 'Reparación aplicada; pruebas no aprobadas'
            attempt=db.get(RepairAttempt,repair_id)
            attempt.outcome='VERIFIED' if verified else 'APPLIED_UNVERIFIED' if verification.result.verification_skipped else 'FAILED_BLOCKED'
            attempt.guidance_hint=json.dumps({'record':redact(record.model_dump(mode='json'))},ensure_ascii=False)
            attempt.before_hash=hashlib.sha256(json.dumps(request.sourceFiles,sort_keys=True).encode()).hexdigest()
            attempt.after_hash=hashlib.sha256(json.dumps(current,sort_keys=True).encode()).hexdigest()
            from app.models.reliability import VerificationRun
            run=db.query(VerificationRun).filter_by(session_id=request.sessionId).order_by(VerificationRun.created_at.desc()).first()
            attempt.verification_run_id=run.run_id if run else None
            db.commit()
        return record
    except Exception as error:
        if repair_id:
            with SessionLocal() as db:
                attempt=db.get(RepairAttempt,repair_id);attempt.outcome='FAILED_BLOCKED';attempt.guidance_hint=json.dumps({'error':redact(str(error))})
                session=db.get(GenerationSessionDB,request.sessionId);session.status=SessionStatus.BLOCKED;session.error_message=redact(str(error));db.commit()
        raise
    finally:
        if owns_lock: lock.release()


def repair_history(session_id):
    from app.models.test_analysis import RepairHistoryResponse
    from app.services.verification_policy import session_is_verified
    with SessionLocal() as db:
        session=db.get(GenerationSessionDB,session_id)
        if not session: raise HTTPException(404,'Session not found')
        attempts=db.query(RepairAttempt).filter_by(session_id=session_id).order_by(RepairAttempt.created_at).all()
        records=[]
        for attempt in attempts:
            try:
                payload=json.loads(attempt.guidance_hint or '{}')
                if 'record' in payload: records.append(RepairIterationRecord.model_validate(payload['record']))
            except (ValueError,TypeError): continue
        state='VERIFIED' if session_is_verified(session) else 'BLOCKED' if session.status==SessionStatus.BLOCKED else 'UNVERIFIED'
        return RepairHistoryResponse(sessionId=session_id,totalIterations=sum(bool(attempt.automatic) for attempt in attempts),finalState=state,iterations=records,canRetryManually=state=='BLOCKED')
