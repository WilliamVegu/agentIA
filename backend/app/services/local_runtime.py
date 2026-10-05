"""Small runtime primitives: isolated identities, localhost ports and durable records."""
import json
import socket
import subprocess
import threading
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


def persist(row):
    with _record_lock:
        directory = record_directory(row.sessionId)
        directory.mkdir(parents=True, exist_ok=True)
        temporary = directory / "deployment.tmp"
        temporary.write_text(row.model_dump_json(), encoding="utf-8")
        temporary.replace(directory / "deployment.json")


def restore(session_id):
    try:
        row = LocalDeploymentSession.model_validate_json((record_directory(session_id) / "deployment.json").read_text(encoding="utf-8"))
        if row.sessionId != session_id:
            return None
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
