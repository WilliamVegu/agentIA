"""Cancellation controls belong to an exact operation, never to a later retry."""
import threading
from datetime import datetime, timezone
from app.services.local_runtime import persist
from app.services.logged_process import CommandCancelled
from contextlib import contextmanager
from contextvars import ContextVar
from app.services.local_runtime import record_directory
import re

_guard = threading.RLock()
_events = {}
_borrowed_lock = ContextVar('local_borrowed_lock', default=None)


class OperationCancelEvent(threading.Event):
    """The exact operation's cancel request is visible to another worker process."""
    def __init__(self, row):
        super().__init__()
        if not re.fullmatch(r'[a-zA-Z0-9-]{1,100}', row.operationId):
            raise ValueError('Identidad de operacion invalida')
        self.path = record_directory(row.sessionId) / ('cancel-' + row.operationId)

    def is_set(self):
        if any(event.is_set() for event in getattr(self,"parent_controls",())):
            return True
        return super().is_set() or self.path.is_file()

    def set(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise ValueError('Solicitud de cancelacion enlazada')
        self.path.write_text('CANCEL_REQUESTED', encoding='ascii')
        super().set()


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
    event = OperationCancelEvent(row)
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
        from app.services.local_runtime import restore
        row = service._active_deployments.get(session_id) or restore(session_id)
        if not row or row.operationId != operation_id:
            raise ValueError('La operación cambió; actualice el estado antes de cancelar.')
        event = _events.get(operation_id)
        if row.finishedAt:
            return row
        if event is None:
            from app.services.session_operation_lock import SessionOperationLock
            if not SessionOperationLock(session_id).locked():
                return row
            event = OperationCancelEvent(row)
        event.set()
        row.cancelRequested = True
        row.message = 'Cancelación solicitada. Espere el resultado; no se confirma detención de BuildKit en el daemon.'
        persist(row)
        return row
