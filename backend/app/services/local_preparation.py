from app.services.session_operation_lock import SessionOperationLock
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
        lock = docker_service._operation_locks.setdefault(session_id, SessionOperationLock(session_id))
    if not lock.acquire(blocking=False):
        return docker_service.get_deployment_status(session_id)
    row = LocalDeploymentSession(sessionId=session_id, status=DeploymentStatus.BUILDING, operationId=str(uuid.uuid4()), message='Preparación inicial online en curso. No constituye verificación offline.')
    docker_service._active_deployments[session_id] = row
    from app.services.local_operations import register, phase, finish
    control = register(row, 'PREPARE')
    try:
        from app.services.dependency_inputs import dependency_manifest
        requested_dependencies = dependency_manifest(workspace)
        requested_builder = builder_image(workspace)
        persist(row)
    except Exception as exc:
        row.status, row.errorMessage = DeploymentStatus.FAILED, str(exc)
        finish(row)
        lock.release()
        raise
    def worker():
        try:
            from app.services.gradle_compatibility import validate_gradle_version
            validate_gradle_version(workspace)
            commands = [
                ['docker', 'build', '--pull', '--label', 'io.agentia.operation=' + row.operationId + '-builder', '-f', 'Dockerfile.prepare', '-t', requested_builder, '.'],
                ['docker', 'build', '--pull', '--label', 'io.agentia.operation=' + row.operationId + '-runtime', '-f', 'Dockerfile.runtime', '-t', 'agentia-runtime:21-v1', '.'],
            ]
            if DATABASE_IMAGES[database]: commands.append(['docker', 'pull', DATABASE_IMAGES[database]])
            for command in commands:
                phase(row, 'PREPARE', control)
                if dependency_manifest(workspace) != requested_dependencies:
                    raise RuntimeError('Dependencias cambiadas durante preparación; regenere activos y repita la preparación explícita.')
                docker_service._log_message(session_id, '[PREPARE] ' + ' '.join(command))
                from app.services.buildkit_outcome import run_build
                runner = run_build if command[1] == 'build' else docker_service.run_logged
                extra = {'operation_id': command[command.index('--label') + 1].split('=', 1)[1], 'runner': docker_service.run_logged} if command[1] == 'build' else {}
                runner(command,
                    lambda line: docker_service._log_message(session_id, line, source='prepare'),
                    cwd=workspace, timeout=docker_service.settings.LOCAL_PREPARE_TIMEOUT, cancel_event=control, **extra)
            if dependency_manifest(workspace) != requested_dependencies:
                raise RuntimeError('Dependencias cambiadas durante preparación; no se acredita entorno preparado.')
            phase(row, 'COMPLETE', control)
            row.status, row.message = DeploymentStatus.IDLE, 'Imágenes y dependencias preparadas. Ejecute Verificar fuentes con Docker para demostrar el resultado offline.'
        except Exception as exc:
            row.status, row.errorMessage = DeploymentStatus.FAILED, str(exc)
            docker_service._log_message(session_id, '[PREPARE FAILED] ' + str(exc))
        finally:
            finish(row)
            try:
                persist(row)
            finally:
                lock.release()
    try:
        threading.Thread(target=worker, daemon=True).start()
    except Exception as exc:
        row.status, row.errorMessage = DeploymentStatus.FAILED, str(exc)
        finish(row)
        try:
            persist(row)
        finally:
            lock.release()
        raise
    return row
