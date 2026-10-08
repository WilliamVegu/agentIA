"""Transactional operation identity, compare-and-swap and crash recovery."""
import json
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.models.session import SessionLocal, GenerationSessionDB, SessionStatus, SessionPhase
from app.models.reliability import PipelineOperation, SessionEvent
from app.services.secret_redaction import without_credentials, redact

ACTIVE = {'QUEUED', 'RUNNING', 'PAUSE_REQUESTED', 'CANCEL_REQUESTED'}
TERMINAL = {'COMPLETED', 'BLOCKED', 'CANCELLED', 'INTERRUPTED'}
TRANSITIONS = {
 'QUEUED': {'RUNNING', 'CANCEL_REQUESTED', 'BLOCKED', 'INTERRUPTED'},
 'RUNNING': {'PAUSE_REQUESTED', 'CANCEL_REQUESTED', 'COMPLETED', 'BLOCKED', 'INTERRUPTED'},
 'PAUSE_REQUESTED': {'PAUSED', 'CANCEL_REQUESTED', 'BLOCKED', 'INTERRUPTED'},
 'PAUSED': {'RUNNING', 'CANCELLED'},
 'CANCEL_REQUESTED': {'CANCELLED', 'BLOCKED', 'INTERRUPTED'},
}


def transaction(db):
    if db.bind.dialect.name == 'sqlite':
        db.execute(text('BEGIN IMMEDIATE'))


def project(row):
    return {'operationId': row.operation_id, 'sessionId': row.session_id, 'version': row.version,
        'state': row.state, 'targetPhase': row.target_phase, 'revisionId': row.revision_id,
        'configurationVersion': row.config_version, 'checkpoint': json.loads(row.checkpoint_json),
        'options': json.loads(row.options_json), 'errorCode': row.error_code}


def append_event(db, session_id, event_type, payload, operation=None):
    from sqlalchemy import func
    sequence = (db.query(func.max(SessionEvent.sequence)).filter_by(session_id=session_id).scalar() or 0) + 1
    event = SessionEvent(session_id=session_id, sequence=sequence, event_type=event_type,
        operation_id=operation.operation_id if operation else None,
        operation_version=operation.version if operation else None,
        payload_json=json.dumps(redact(without_credentials(payload)), ensure_ascii=False))
    db.add(event)
    return event


def begin_operation(session_id, target_phase, options=None, expected_revision_id=None):
    from app.models.orchestrator import LifecyclePhase
    target_phase = getattr(target_phase, 'value', target_phase)
    try:
        LifecyclePhase(target_phase)
    except ValueError:
        raise HTTPException(422, 'Fase objetivo inválida')
    with SessionLocal() as db:
        try:
            transaction(db)
            session = db.get(GenerationSessionDB, session_id)
            if not session:
                raise HTTPException(404, 'Session not found')
            if expected_revision_id is not None and expected_revision_id != session.revision_id:
                raise HTTPException(409, 'La revisión ha cambiado')
            if db.query(PipelineOperation).filter_by(session_id=session_id).filter(PipelineOperation.state.in_(ACTIVE)).first():
                raise HTTPException(409, 'Ya existe una operación activa')
            session.operation_version = (session.operation_version or 0) + 1
            operation = PipelineOperation(session_id=session_id, state='QUEUED', target_phase=target_phase,
                revision_id=session.revision_id, config_version=session.configuration_version or 1,
                options_json=json.dumps(without_credentials(options or {})),
                lease_until=datetime.now(timezone.utc)+timedelta(minutes=10))
            db.add(operation); db.flush()
            append_event(db, session_id, 'operation_state', project(operation), operation)
            db.commit()
            return project(operation)
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, 'Ya existe una operación activa')


def get_operation(session_id, operation_id=None):
    with SessionLocal() as db:
        if not db.get(GenerationSessionDB, session_id):
            raise HTTPException(404, 'Session not found')
        query = db.query(PipelineOperation).filter_by(session_id=session_id)
        if operation_id:
            query = query.filter_by(operation_id=operation_id)
        row = query.order_by(PipelineOperation.created_at.desc()).first()
        return project(row) if row else None


def transition_operation(operation_id, expected_version, state, *, checkpoint=None, error_code=None):
    with SessionLocal() as db:
        transaction(db)
        operation = db.get(PipelineOperation, operation_id)
        if not operation:
            raise HTTPException(404, 'Operación inexistente')
        if operation.version != expected_version:
            raise HTTPException(409, 'Callback obsoleto: versión de operación distinta')
        latest = db.query(PipelineOperation).filter_by(session_id=operation.session_id).order_by(PipelineOperation.created_at.desc()).first()
        if latest.operation_id != operation_id:
            raise HTTPException(409, 'Callback de una operación sustituida')
        if state not in TRANSITIONS.get(operation.state, set()):
            raise HTTPException(409, 'Transición incompatible con ' + operation.state)
        operation.state = state
        operation.version += 1
        operation.updated_at = datetime.now(timezone.utc)
        operation.lease_until = datetime.now(timezone.utc)+timedelta(minutes=10) if state in ACTIVE else None
        operation.error_code = error_code
        if checkpoint is not None:
            operation.checkpoint_json = json.dumps(without_credentials(checkpoint))
        session = db.get(GenerationSessionDB, operation.session_id)
        if not session: raise HTTPException(409,'La sesión de la operación ya no existe')
        if state in {'RUNNING', 'QUEUED'}:
            session.status = SessionStatus.RUNNING
        elif state == 'PAUSED':
            session.status = SessionStatus.PAUSED
        elif state == 'BLOCKED':
            session.status = SessionStatus.BLOCKED; session.phase = SessionPhase.FAILED
        elif state == 'COMPLETED':
            session.status = SessionStatus.COMPLETED
        elif state == 'CANCELLED':
            session.status = SessionStatus.CANCELLED
        elif state == 'INTERRUPTED':
            session.status = SessionStatus.PAUSED
            session.error_message = 'Operación interrumpida; reanudación explícita necesaria'
        append_event(db, operation.session_id, 'operation_state', project(operation), operation)
        db.commit()
        return project(operation)


def checkpoint_operation(operation_id, expected_version, phase, payload=None):
    with SessionLocal() as db:
        transaction(db)
        operation = db.get(PipelineOperation, operation_id)
        if not operation or operation.version != expected_version or operation.state not in ACTIVE:
            raise HTTPException(409, 'Checkpoint obsoleto o incompatible')
        session = db.get(GenerationSessionDB, operation.session_id)
        if session.revision_id != operation.revision_id:
            raise HTTPException(409, 'La revisión cambió durante la ejecución')
        operation.checkpoint_json = json.dumps({'phase': phase, **without_credentials(payload or {})})
        operation.updated_at = datetime.now(timezone.utc)
        operation.lease_until = datetime.now(timezone.utc)+timedelta(minutes=10)
        operation.version += 1
        append_event(db, operation.session_id, 'operation_checkpoint', project(operation), operation)
        db.commit()
        return project(operation)


def recover_interrupted():
    with SessionLocal() as db:
        operations = [(row.operation_id, row.version) for row in db.query(PipelineOperation).filter(PipelineOperation.state.in_(ACTIVE)).all()]
    count = 0
    for identifier, version in operations:
        with SessionLocal() as db:
            transaction(db)
            operation=db.get(PipelineOperation,identifier)
            if not operation or operation.version!=version or operation.state not in ACTIVE:
                continue
            session_id=operation.session_id
            if not db.get(GenerationSessionDB,session_id):
                operation.state='INTERRUPTED';operation.error_code='SESSION_MISSING'
                operation.version+=1;operation.lease_until=None
                db.commit();count+=1
                import logging
                logging.getLogger(__name__).warning('Interrupted orphan operation %s; original record preserved',identifier)
                continue
        from app.services.session_operation_lock import SessionOperationLock
        lock = SessionOperationLock(session_id)
        if not lock.acquire(False):
            continue
        lock.release()
        try:
            transition_operation(identifier, version, 'INTERRUPTED', error_code='BACKEND_RESTARTED')
            count += 1
        except HTTPException as error:
            if error.status_code != 409:
                raise
    return count


def finish_operation(session_id, operation_id, desired_state, *, error_code=None):
    """Settle only this worker; concurrent control requests take precedence."""
    for _ in range(3):
        try:
            current=get_operation(session_id,operation_id)
            latest=get_operation(session_id)
        except HTTPException as error:
            if error.status_code==404: return None
            raise
        if not current or not latest or latest['operationId']!=operation_id: return None
        if current['state'] not in ACTIVE: return current
        target='CANCELLED' if current['state']=='CANCEL_REQUESTED' else 'PAUSED' if current['state']=='PAUSE_REQUESTED' else desired_state
        try:
            return transition_operation(operation_id,current['version'],target,error_code=error_code)
        except HTTPException as error:
            if error.status_code!=409: raise
    raise HTTPException(409,'La operación cambió durante su finalización; vuelva a consultar su estado')
