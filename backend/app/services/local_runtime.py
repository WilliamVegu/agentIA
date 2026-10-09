"""Small runtime primitives: isolated identities, localhost ports and durable records."""
import json
import socket
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from app.config import settings
from app.models.devops import LocalDeploymentSession, DeploymentStatus

_record_lock = threading.RLock()


def record_directory(session_id):
    root = Path(settings.WORKSPACE_DIR).resolve()
    directory = (root / session_id / ".agentia-runtime").resolve()
    if Path(session_id).name != session_id or not directory.is_relative_to(root):
        raise ValueError("Invalid session identity")
    return directory


def _stored_runtime(session_id):
    from app.models.session import SessionLocal,GenerationSessionDB
    from app.models.reliability import DeploymentOperation
    with SessionLocal() as db:
        if not db.get(GenerationSessionDB,session_id): return None
        operation=db.query(DeploymentOperation).filter_by(session_id=session_id).order_by(DeploymentOperation.created_at.desc()).first()
        if not operation: return None
        payload=json.loads(operation.bindings_json).get('projection')
        if payload is None: return None
        row=LocalDeploymentSession.model_validate(payload)
        if row.sessionId!=session_id: raise ValueError('Runtime projection belongs to another session')
        return row


def _persist_runtime(row):
    from app.models.session import SessionLocal,GenerationSessionDB
    from app.models.reliability import DeploymentOperation
    from app.services.operation_repository import transaction
    from app.services.secret_redaction import redact
    with SessionLocal() as db:
        transaction(db)
        if not db.get(GenerationSessionDB,row.sessionId): return True  # Legacy file; never creates a session.
        latest=db.query(DeploymentOperation).filter_by(session_id=row.sessionId).order_by(DeploymentOperation.created_at.desc()).first()
        operation_id=row.operationId or (latest.operation_id if latest else str(uuid.uuid4()))
        operation=db.get(DeploymentOperation,operation_id)
        if operation and (operation.session_id!=row.sessionId or latest and latest.operation_id!=operation_id): return False
        if not operation:
            operation=DeploymentOperation(operation_id=operation_id,session_id=row.sessionId,framework='springboot',state=row.status.value)
            db.add(operation)
        operation.state=row.status.value
        operation.source_snapshot_id=row.sourceSnapshotId
        operation.fingerprint=row.workspaceFingerprint
        operation.compose_project=row.sessionId
        operation.container_ids_json=json.dumps([value for value in (row.containerId,row.databaseContainerId) if value])
        operation.image_id=row.imageId
        operation.labels_json=json.dumps({'com.docker.compose.project':row.sessionId})
        operation.bindings_json=json.dumps({'hostPort':row.hostPort,'projection':redact(row.model_dump(mode='json'))})
        operation.error_code=redact(row.errorMessage)[:100] if row.errorMessage else None
        operation.updated_at=datetime.now(timezone.utc)
        db.commit()
        return True


def persist(row):
    with _record_lock:
        directory = record_directory(row.sessionId)
        directory.mkdir(parents=True, exist_ok=True)
        # A status probe can finish after the worker has persisted completion.
        # Preserve terminal operation metadata when that probe carries an older
        # copy, while still saving the newly observed container health.
        try:
            stored = _stored_runtime(row.sessionId)
            if stored is None:
                stored = LocalDeploymentSession.model_validate_json(
                    (directory / 'deployment.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            stored = None
        if (stored is not None and stored.sessionId == row.sessionId
                and stored.operationId == row.operationId and stored.operationId
                and stored.finishedAt and not row.finishedAt):
            row.finishedAt = stored.finishedAt
            row.operationPhase = stored.operationPhase
            row.cancelRequested = row.cancelRequested or stored.cancelRequested
            row.message = stored.message
        if not _persist_runtime(row): return False
        temporary = directory / ("deployment-" + uuid.uuid4().hex + ".tmp")
        temporary.write_text(row.model_dump_json(), encoding="utf-8")
        try:
            for attempt in range(5):
                try:
                    temporary.replace(directory / "deployment.json")
                    break
                except OSError as error:
                    if getattr(error, 'winerror', None) not in (5, 32, 33) or attempt == 4:
                        raise
                    time.sleep(0.05 * (attempt + 1))
        finally:
            temporary.unlink(missing_ok=True)


def restore(session_id):
    try:
        row = _stored_runtime(session_id)
        if row is None:
            row = LocalDeploymentSession.model_validate_json((record_directory(session_id) / "deployment.json").read_text(encoding="utf-8"))
        if row.sessionId != session_id:
            return None
        from app.services.session_operation_lock import SessionOperationLock
        if SessionOperationLock(session_id).locked():
            return row
        if row.status == DeploymentStatus.BUILDING:
            row.status = DeploymentStatus.FAILED
            row.errorMessage = "Construcción interrumpida por un reinicio. Reintente."
        if row.operationKind and not row.finishedAt:
            from app.services.local_operations import is_active
            if not is_active(row.operationId):
                row.finishedAt = datetime.now(timezone.utc).isoformat()
                row.operationPhase = 'INTERRUPTED'
                row.message = 'El worker local no está activo. Compruebe Docker; no se confirma cancelación de tareas del daemon.'
        return row
    except (OSError, ValueError):
        return None


def available_port(preferred):
    for port in range(preferred, min(preferred + 100, 65536)):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No hay puertos localhost disponibles en el rango solicitado.")


def inspect_session(session_id):
    listing = subprocess.run(["docker", "ps", "-a", "--filter", f"label=com.docker.compose.project={session_id}", "--format", "{{.ID}}"], capture_output=True, text=True, timeout=4, check=False)
    if listing.returncode:
        raise RuntimeError("No se pudo consultar Docker.")
    ids = listing.stdout.split()
    if not ids:
        return None
    inspection = subprocess.run(["docker", "inspect", *ids], capture_output=True, text=True, timeout=4, check=False)
    if inspection.returncode:
        raise RuntimeError("No se pudo identificar el contenedor de esta sesión.")
    containers = [c for c in json.loads(inspection.stdout) if c.get("Config", {}).get("Labels", {}).get("com.docker.compose.project") == session_id]
    if any(c.get('Config',{}).get('Labels',{}).get('io.agentia.owner')!=session_id or c.get('Config',{}).get('Labels',{}).get('io.agentia.studio')!='springboot' for c in containers):
        raise RuntimeError('Runtime legacy/unowned: identidad no confirmada')
    def role(c):
        return c.get("Config", {}).get("Labels", {}).get("io.agentia.role")
    applications = [c for c in containers if role(c) == 'application']
    databases = [c for c in containers if role(c) == 'database']
    if len(applications) > 1 or len(databases) > 1:
        raise RuntimeError('Identidad de runtime ambigua: varias aplicaciones/BD de esta sesión.')
    app = applications[0] if applications else None
    database = databases[0] if databases else None
    if app is None:
        if database and database.get('State', {}).get('Running'):
            stored = restore(session_id) or LocalDeploymentSession(sessionId=session_id)
            stored.containerId, stored.databaseContainerId = None, database['Id']
            stored.status, stored.healthStatus, stored.testUrl = DeploymentStatus.DEGRADED, 'DOWN', None
            stored.errorMessage = 'La BD sigue activa, pero no hay aplicación de esta sesión.'
            return stored
        return None
    bindings = app.get("HostConfig", {}).get("PortBindings", {}).get("8080/tcp") or []
    if len(bindings) != 1 or bindings[0].get("HostIp") != "127.0.0.1":
        raise RuntimeError("El servicio no está publicado exclusivamente en localhost.")
    running = app.get("State", {}).get("Running") is True
    db_running = not database or database.get("State", {}).get("Running") is True
    environment = dict(value.split('=', 1) for value in app.get('Config', {}).get('Env', []) if '=' in value)
    driver = environment.get('SPRING_DATASOURCE_DRIVER_CLASS_NAME')
    engine = {'org.h2.Driver': 'H2', 'org.postgresql.Driver': 'POSTGRESQL',
              'com.mysql.cj.jdbc.Driver': 'MYSQL'}.get(driver)
    failed = not running and (app.get('State', {}).get('ExitCode', 0) not in (0, 143) or bool(app.get('State', {}).get('Error')) or app.get('State', {}).get('OOMKilled') is True)
    unhealthy = any(c and c.get('State', {}).get('Health', {}).get('Status') == 'unhealthy' for c in (app, database))
    database_missing = engine in ('MYSQL', 'POSTGRESQL') and database is None
    status = (DeploymentStatus.FAILED if failed else DeploymentStatus.STOPPED) if not running else (
        DeploymentStatus.DEGRADED if not db_running or unhealthy or database_missing else DeploymentStatus.RUNNING)
    return LocalDeploymentSession(sessionId=session_id, containerId=app["Id"], databaseContainerId=database["Id"] if database else None, hostPort=int(bindings[0]["HostPort"]),
        imageId=app.get('Image'),
        sourceSnapshotId=app.get('Config', {}).get('Labels', {}).get('io.agentia.source-snapshot'),
        workspaceFingerprint=app.get('Config', {}).get('Labels', {}).get('io.agentia.source-fingerprint'),
        executableJarSha256=app.get('Config', {}).get('Labels', {}).get('io.agentia.jar-sha256'),
        dbEngine=engine,
        status=status, healthStatus="UNKNOWN" if running else "DOWN",
        errorMessage=f"Aplicación detenida con exit code {app.get('State', {}).get('ExitCode', 0)}." if failed else None)
