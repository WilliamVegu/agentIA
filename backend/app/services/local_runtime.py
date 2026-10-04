"""Small runtime primitives: isolated identities, localhost ports and durable records."""
import json
import socket
import subprocess
import threading
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
    app = next((c for c in containers if role(c) == "application"), None)
    database = next((c for c in containers if role(c) == "database"), None)
    if app is None:
        return None
    bindings = app.get("HostConfig", {}).get("PortBindings", {}).get("8080/tcp") or []
    if len(bindings) != 1 or bindings[0].get("HostIp") != "127.0.0.1":
        raise RuntimeError("El servicio no está publicado exclusivamente en localhost.")
    running = app.get("State", {}).get("Running") is True
    db_running = not database or database.get("State", {}).get("Running") is True
    return LocalDeploymentSession(sessionId=session_id, containerId=app["Id"], databaseContainerId=database["Id"] if database else None, hostPort=int(bindings[0]["HostPort"]),
        status=DeploymentStatus.RUNNING if running and db_running else (DeploymentStatus.DEGRADED if running else DeploymentStatus.STOPPED), healthStatus="UNKNOWN" if running else "DOWN")
