"""Explicit initial online preparation. Never stores an offline verification pass."""
import subprocess
import threading
import uuid
from pathlib import Path
from app.models.devops import LocalDeploymentSession, DeploymentStatus
from app.services import docker_service
from app.services.execution_policy import execution_mode
from app.services.local_deployment_assets import builder_image, DATABASE_IMAGES
from app.services.local_runtime import persist


def prepare_local(session_id, workspace, database):
    if execution_mode(session_id).value == 'SOURCE_ONLY' or not docker_service.check_docker_daemon():
        return docker_service.get_deployment_status(session_id)
    with docker_service._operations_lock:
        lock = docker_service._operation_locks.setdefault(session_id, threading.Lock())
    if not lock.acquire(blocking=False):
        return docker_service.get_deployment_status(session_id)
    row = LocalDeploymentSession(sessionId=session_id, status=DeploymentStatus.BUILDING, operationId=str(uuid.uuid4()), message='Preparación inicial online en curso. No constituye verificación offline.')
    docker_service._active_deployments[session_id] = row
    try:
        persist(row)
    except Exception as exc:
        row.status, row.errorMessage = DeploymentStatus.FAILED, str(exc)
        lock.release()
        raise
    def worker():
        try:
            commands = [
                ['docker', 'build', '--pull', '-f', 'Dockerfile.prepare', '-t', builder_image(workspace), '.'],
                ['docker', 'build', '--pull', '-f', 'Dockerfile.runtime', '-t', 'agentia-runtime:21-v1', '.'],
            ]
            if DATABASE_IMAGES[database]: commands.append(['docker', 'pull', DATABASE_IMAGES[database]])
            for command in commands:
                docker_service._log_message(session_id, '[PREPARE] ' + ' '.join(command))
                result = subprocess.run(command, cwd=workspace, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=900, check=False)
                for line in (result.stdout + '\n' + result.stderr).splitlines()[-1000:]:
                    docker_service._log_message(session_id, line)
                if result.returncode: raise RuntimeError((result.stderr or result.stdout or 'Preparación falló')[-2000:])
            row.status, row.message = DeploymentStatus.IDLE, 'Imágenes y dependencias preparadas. Ejecute Verificar fuentes con Docker para demostrar el resultado offline.'
        except Exception as exc:
            row.status, row.errorMessage = DeploymentStatus.FAILED, str(exc)
            docker_service._log_message(session_id, '[PREPARE FAILED] ' + str(exc))
        finally:
            try:
                persist(row)
            finally:
                lock.release()
    try:
        threading.Thread(target=worker, daemon=True).start()
    except Exception as exc:
        row.status, row.errorMessage = DeploymentStatus.FAILED, str(exc)
        try:
            persist(row)
        finally:
            lock.release()
        raise
    return row
