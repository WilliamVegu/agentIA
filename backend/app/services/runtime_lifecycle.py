"""Operate only on resources whose Compose ownership has been inspected."""
import json
import os
import subprocess
import threading
import uuid
from pathlib import Path
import yaml
from app.models.devops import LocalDeploymentSession, DeploymentStatus
from app.services.execution_policy import execution_mode
from app.services.local_runtime import persist, restore, inspect_session, available_port, record_directory


def owned_resources(session_id, kind='container'):
    record_directory(session_id)  # Validate identity before constructing CLI filters.
    query = ['docker', 'ps', '-a', '--format', '{{.ID}}'] if kind == 'container' else ['docker', kind, 'ls', '-q']
    result = subprocess.run(query + ['--filter', f'label=com.docker.compose.project={session_id}'],
                            capture_output=True, text=True, timeout=5, check=False)
    if result.returncode:
        raise RuntimeError('No se pudieron enumerar recursos de la sesión.')
    ids = result.stdout.split()
    if not ids: return []
    command = ['docker', 'inspect', *ids] if kind == 'container' else ['docker', kind, 'inspect', *ids]
    result = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)
    if result.returncode: raise RuntimeError('No se pudo verificar propiedad de los recursos.')
    resources = json.loads(result.stdout)
    if len(resources) != len(ids) or any(((r.get('Config', {}).get('Labels') or {}) if kind == 'container' else (r.get('Labels') or {})).get('com.docker.compose.project') != session_id for r in resources):
        raise RuntimeError('Identidad ajena o incompleta; operación rechazada.')
    return resources


def _command(command, **kwargs):
    from app.services.deployment_logs import redact
    result = subprocess.run(command, capture_output=True, text=True, timeout=kwargs.pop('timeout', 60), check=False, **kwargs)
    if result.returncode: raise RuntimeError(redact(result.stderr or result.stdout or 'Docker falló.'))
    return result


def stop_interrupted_runtime(session_id):
    """Called by the operation owner, without reacquiring its lock; never delete data."""
    if execution_mode(session_id).value == 'SOURCE_ONLY':
        raise RuntimeError('Modo fuentes: parada Docker no ejecutada.')
    containers = owned_resources(session_id)
    running = [item['Id'] for item in containers if item.get('State', {}).get('Running')]
    if running:
        _command(['docker', 'stop', '--time', '10', *running], timeout=60)
    if any(item.get('State', {}).get('Running') for item in owned_resources(session_id)):
        raise RuntimeError('Quedan contenedores propios activos.')


def cleanup_local(session_id, delete_data=False):
    from app.services import docker_service as service
    if execution_mode(session_id).value == 'SOURCE_ONLY': return service.get_deployment_status(session_id)
    if not delete_data: raise ValueError('Confirme explícitamente deleteData para borrar datos de esta sesión.')
    with service._operations_lock:
        lock = service._operation_locks.setdefault(session_id, threading.Lock())
    if not lock.acquire(blocking=False):
        return LocalDeploymentSession(sessionId=session_id, status=DeploymentStatus.BUILDING, errorMessage='Hay una operación activa; espere antes de limpiar.')
    row = service._active_deployments.get(session_id) or restore(session_id) or LocalDeploymentSession(sessionId=session_id)
    try:
        # All resource ownership must be known before the first mutation.
        containers, volumes, networks = (owned_resources(session_id, kind) for kind in ('container', 'volume', 'network'))
        from app.services.runtime_log_capture import stop_capture
        stop_capture(session_id)
        if containers: _command(['docker', 'rm', '-f', *[r['Id'] for r in containers]])
        if volumes: _command(['docker', 'volume', 'rm', *[r['Name'] for r in volumes]])
        if networks: _command(['docker', 'network', 'rm', *[r['Id'] for r in networks]])
        if any(owned_resources(session_id, kind) for kind in ('container', 'volume', 'network')):
            raise RuntimeError('Quedaron recursos propios; limpieza incompleta.')
        row.containerId = row.databaseContainerId = row.testUrl = None
        row.dbEngine = None
        row.status, row.healthStatus, row.errorMessage = DeploymentStatus.STOPPED, 'DOWN', None
        row.message = 'Recursos y datos de esta sesión eliminados explícitamente. Fuentes e historial conservados.'
        service._log_message(session_id, '[CLEANUP] ' + row.message)
    except Exception as exc:
        row.status, row.healthStatus, row.testUrl, row.errorMessage = DeploymentStatus.FAILED, 'UNKNOWN', None, str(exc)
    finally:
        service._active_deployments[session_id] = row
        try: persist(row)
        finally: lock.release()
    return row


def restart_local(session_id, workspace):
    from app.services import docker_service as service
    if execution_mode(session_id).value == 'SOURCE_ONLY': return service.get_deployment_status(session_id)
    if not service.check_docker_daemon(): return service.get_deployment_status(session_id)
    with service._operations_lock:
        lock = service._operation_locks.setdefault(session_id, threading.Lock())
    if not lock.acquire(blocking=False):
        return LocalDeploymentSession(sessionId=session_id, status=DeploymentStatus.BUILDING, errorMessage='Espere la operación activa antes de reiniciar.')
    row = service._active_deployments.get(session_id) or restore(session_id) or LocalDeploymentSession(sessionId=session_id)
    row.status, row.healthStatus, row.testUrl, row.errorMessage = DeploymentStatus.BUILDING, 'UNKNOWN', None, None
    row.operationId, row.message = str(uuid.uuid4()), 'Reinicio sin reconstrucción; datos conservados.'
    from app.services.local_operations import register, phase, finish
    from app.services.logged_process import CommandCancelled
    control = register(row, 'RESTART')
    service._active_deployments[session_id] = row
    try: persist(row)
    except Exception:
        finish(row)
        lock.release(); raise
    def worker():
        start_attempted = False
        try:
            phase(row, 'PREFLIGHT', control)
            manifest = yaml.safe_load((Path(workspace) / 'docker-compose.yml').read_text(encoding='utf-8'))
            apps = [item for item in manifest['services'].values() if item.get('labels', {}).get('io.agentia.role') == 'application']
            if len(apps) != 1 or not apps[0].get('image', '').startswith('${COMPOSE_PROJECT_NAME}-'):
                raise RuntimeError('Reinicio requiere una imagen de aplicación identificada por sesión.')
            if not apps[0].get('ports') or any(not isinstance(port, str) or not port.startswith('127.0.0.1:') for port in apps[0]['ports']):
                raise RuntimeError('Reinicio requiere publicación exclusiva en localhost.')
            for kind in ('volumes', 'networks'):
                if any(item and (item.get('external') or item.get('name')) for item in manifest.get(kind, {}).values()):
                    raise RuntimeError('Reinicio no admite recursos externos ni nombres globales.')
            if any(item.get('container_name') for item in manifest['services'].values()):
                raise RuntimeError('Reinicio no admite nombres de contenedor globales.')
            owned_resources(session_id)
            env = {**os.environ, 'HOST_PORT': str(row.hostPort)}
            prefix = ['docker', 'compose', '-p', session_id]
            _command(prefix + ['config', '--quiet'], cwd=workspace, env=env, timeout=10)
            phase(row, 'START', control)
            for attempt in range(3):
                try:
                    phase(row, 'START', control)
                    start_attempted = True
                    _command(prefix + ['up', '-d', '--force-recreate', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '180'], cwd=workspace, env=env, timeout=service.settings.LOCAL_START_TIMEOUT)
                    break
                except RuntimeError as exc:
                    if attempt == 2 or not any(value in str(exc).lower() for value in ('port is already allocated', 'address already in use', 'ports are not available')): raise
                    row.hostPort = available_port(row.hostPort + 1)
                    env['HOST_PORT'] = str(row.hostPort)
                    row.message = f'Puerto ocupado durante reinicio; se eligió {row.hostPort}. Datos conservados.'
            phase(row, 'READINESS', control)
            actual = inspect_session(session_id)
            if not actual or actual.status != DeploymentStatus.RUNNING: raise RuntimeError('Reinicio sin aplicación/BD activas de esta sesión.')
            row.containerId, row.databaseContainerId, row.dbEngine = actual.containerId, actual.databaseContainerId, actual.dbEngine
            row.hostPort, row.status = actual.hostPort, DeploymentStatus.RUNNING
            smoke = service.run_smoke_test(session_id, max_retries=10, interval=1, cancel_event=control)
            if not smoke.passed: raise RuntimeError(smoke.details)
            phase(row, 'COMPLETE', control)
            row.status, row.healthStatus, row.testUrl = DeploymentStatus.HEALTHY, 'UP', smoke.testUrl
            service._log_message(session_id, '[RESTART] ' + row.message)
        except Exception as exc:
            row.status, row.errorMessage, row.testUrl = DeploymentStatus.FAILED, str(exc), None
            row.healthStatus = 'UNKNOWN'
            if control.is_set() or isinstance(exc, (CommandCancelled, subprocess.TimeoutExpired)):
                row.operationPhase = 'INTERRUPTED'
                if start_attempted:
                    try: stop_interrupted_runtime(session_id)
                    except Exception as cleanup_error: row.errorMessage += ' Parada no confirmada: ' + str(cleanup_error)
            service._log_message(session_id, '[RESTART FAILED] ' + str(exc))
        finally:
            service._active_deployments[session_id] = row
            finish(row)
            try: persist(row)
            finally: lock.release()
    try: threading.Thread(target=worker, daemon=True).start()
    except Exception as exc:
        row.status, row.errorMessage = DeploymentStatus.FAILED, str(exc)
        finish(row)
        try: persist(row)
        finally: lock.release()
        raise
    return row
