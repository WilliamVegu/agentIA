"""Cancellation controls belong to an exact operation, never to a later retry."""
import threading
from datetime import datetime, timezone
from app.services.local_runtime import persist
from app.services.logged_process import CommandCancelled
from contextlib import contextmanager
from contextvars import ContextVar

_guard = threading.RLock()
_events = {}
_borrowed_lock = ContextVar('local_borrowed_lock', default=None)


@contextmanager
def borrowed_lock(session_id):
    token = _borrowed_lock.set(session_id)
    try:
        yield
    finally:
        _borrowed_lock.reset(token)


def has_borrowed_lock(session_id):
    return _borrowed_lock.get() == session_id


def is_active(operation_id):
    with _guard:
        return operation_id in _events


def register(row, kind):
    event = threading.Event()
    row.operationKind, row.operationPhase = kind, 'QUEUED'
    row.startedAt = datetime.now(timezone.utc).isoformat()
    row.finishedAt, row.cancelRequested = None, False
    with _guard:
        _events[row.operationId] = event
    return event


def phase(row, name, event):
    from app.services.execution_policy import execution_mode
    if event.is_set() or execution_mode(row.sessionId).value == 'SOURCE_ONLY':
        row.cancelRequested = True
        event.set()
        raise CommandCancelled('Operación local interrumpida; no se confirma cancelación de tareas en el daemon Docker.')
    row.operationPhase = name
    persist(row)


def finish(row):
    row.finishedAt = datetime.now(timezone.utc).isoformat()
    with _guard:
        event = _events.pop(row.operationId, None)
        if event is not None:
            row.cancelRequested = row.cancelRequested or event.is_set()


def request_cancel(session_id, operation_id):
    from app.services import docker_service as service
    from app.services.execution_policy import execution_mode
    if execution_mode(session_id).value == 'SOURCE_ONLY':
        return service.get_deployment_status(session_id)
    with _guard:
        row = service._active_deployments.get(session_id)
        if not row or row.operationId != operation_id:
            raise ValueError('La operación cambió; actualice el estado antes de cancelar.')
        event = _events.get(operation_id)
        if event is None or row.finishedAt:
            return row
        event.set()
        row.cancelRequested = True
        row.message = 'Cancelación solicitada. Espere el resultado; no se confirma detención de BuildKit en el daemon.'
        persist(row)
        return row
