import os
import queue
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, Optional

import requests

from app.models.devops import DeploymentStatus, LocalDeploymentSession, SmokeTestResult
from app.config import settings

# In-memory tracking for active deployments and log queues
_active_deployments: Dict[str, LocalDeploymentSession] = {}
_log_queues: Dict[str, queue.Queue] = {}
_operations_lock = threading.RLock()
_operation_locks = {}
_raw_log_history: Dict[str, list] = {}


def check_docker_daemon() -> bool:
    """Checks if the local Docker daemon is running and reachable within a 2s timeout."""
    if not settings.DOCKER_ENABLED:
        return False
    try:
        # Use docker info to test daemon communication
        result = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2.0,
            check=False,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return False


def _containers_for_session(session_id: str) -> list:
    """Containers belonging to a session, identified by the compose project label.

    The deployment registry is in memory, so a backend restart used to orphan every running
    container: the platform forgot it had deployed anything and reported IDLE while the
    service was up. Docker already records the association -- `docker compose` names the
    project after the session id -- so the state can be recovered rather than guessed.

    Read-only. On any failure it returns an empty list, which degrades to "not deployed":
    the honest answer when the state cannot be established.
    """
    try:
        proc = subprocess.run(
            [
                "docker", "ps",
                "--filter", f"label=com.docker.compose.project={session_id}",
                "--format", "{{.ID}}\t{{.Names}}\t{{.Ports}}\t{{.Status}}",
            ],
            capture_output=True, text=True, timeout=3.0, check=False,
        )
        if proc.returncode != 0:
            return []
        rows = []
        for line in proc.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) == 4:
                rows.append({"id": parts[0], "name": parts[1], "ports": parts[2], "status": parts[3]})
        return rows
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return []


def _host_port_from_ports(ports: str) -> int | None:
    """`0.0.0.0:8080->8080/tcp` -> 8080."""
    try:
        for chunk in ports.split(","):
            chunk = chunk.strip()
            if "->" not in chunk:
                continue
            host_side, container_side = chunk.split("->", 1)
            container_port = container_side.split("/")[0]
            if container_port != "8080":
                continue
            return int(host_side.rsplit(":", 1)[-1])
    except (ValueError, IndexError):
        return None
    return None


def _recover_deployment(session_id):
    from app.services.local_runtime import inspect_session
    return inspect_session(session_id)


def get_deployment_status(session_id: str, host_port: int = 8080) -> LocalDeploymentSession:
    from app.services.execution_policy import execution_mode
    from app.services.local_runtime import inspect_session, restore, persist
    if execution_mode(session_id).value == "SOURCE_ONLY":
        return LocalDeploymentSession(sessionId=session_id, status=DeploymentStatus.SKIPPED_BY_CHOICE)
    stored = _active_deployments.get(session_id) or restore(session_id)
    if stored and stored.status == DeploymentStatus.BUILDING:
        return stored
    if not check_docker_daemon():
        return LocalDeploymentSession(sessionId=session_id, status=DeploymentStatus.DOCKER_UNAVAILABLE, errorMessage="Docker no disponible. Reintentar o continuar sin Docker.")
    try:
        session = inspect_session(session_id)
        if session is None:
            if stored and stored.containerId:
                stored.status, stored.healthStatus, stored.testUrl = DeploymentStatus.STOPPED, "DOWN", None
                persist(stored)
            return stored or LocalDeploymentSession(sessionId=session_id)
        if stored:
            session.operationId, session.message = stored.operationId, stored.message
        if session.status == DeploymentStatus.RUNNING:
            session.testUrl = f"http://localhost:{session.hostPort}/actuator/health"
            try:
                resp = requests.get(session.testUrl, timeout=1)
                payload = resp.json()
                if resp.status_code == 200 and isinstance(payload, dict) and payload.get("status") == "UP":
                    session.status, session.healthStatus = DeploymentStatus.HEALTHY, "UP"
                else:
                    session.status, session.healthStatus = DeploymentStatus.DEGRADED, "DOWN"
            except (requests.RequestException, ValueError):
                session.status, session.healthStatus = DeploymentStatus.DEGRADED, "UNKNOWN"
        _active_deployments[session_id] = session
        persist(session)
        return session
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        session = stored or LocalDeploymentSession(sessionId=session_id)
        session.status, session.healthStatus, session.errorMessage = DeploymentStatus.FAILED, "UNKNOWN", str(exc)
        persist(session)
        return session


def get_deployment_logs(session_id: str) -> list:
    return [entry['message'] for entry in _deployment_log_snapshot(session_id)['entries']]


def _deployment_log_snapshot(session_id):
    from app.services.deployment_logs import load
    with _operations_lock:
        if session_id not in _raw_log_history:
            _raw_log_history[session_id] = load(session_id)
        history = _raw_log_history[session_id]
        return {**history, 'entries': [dict(entry) for entry in history['entries']]}


def _log_message(session_id: str, message: str):
    from app.services.deployment_logs import append
    with _operations_lock:
        history = _deployment_log_snapshot(session_id)
        _raw_log_history[session_id] = append(session_id, history, message)


def deploy_local(session_id: str, workspace_dir: str, host_port: int = 8080, rebuild: bool = False) -> LocalDeploymentSession:
    import json
    import uuid
    import yaml
    from app.services.execution_policy import execution_mode
    from app.services.local_runtime import available_port, inspect_session, persist
    from app.services.local_deployment_assets import builder_image
    if execution_mode(session_id).value == "SOURCE_ONLY":
        return get_deployment_status(session_id)
    if not check_docker_daemon():
        return LocalDeploymentSession(sessionId=session_id, status=DeploymentStatus.DOCKER_UNAVAILABLE, errorMessage="Docker no disponible. Reintentar o continuar sin Docker.")
    with _operations_lock:
        lock = _operation_locks.setdefault(session_id, threading.Lock())
    if not lock.acquire(blocking=False):
        return _active_deployments[session_id]
    session = LocalDeploymentSession(sessionId=session_id, status=DeploymentStatus.BUILDING, hostPort=host_port, operationId=str(uuid.uuid4()), startedAt=datetime.now(timezone.utc).isoformat())
    _active_deployments[session_id] = session
    try:
        persist(session)
    except Exception as exc:
        session.status, session.errorMessage = DeploymentStatus.FAILED, str(exc)
        lock.release()
        raise

    def execute(command, environment, timeout):
        _log_message(session_id, '[EXEC] ' + ' '.join(command))
        proc = subprocess.run(command, cwd=workspace_dir, env=environment, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout, check=False)
        for line in (proc.stdout + '\n' + proc.stderr).splitlines()[-1000:]:
            if line.strip():
                _log_message(session_id, line)
        if proc.returncode:
            raise RuntimeError(f"Docker exit code {proc.returncode}: " + (proc.stderr or proc.stdout or 'Docker falló')[-2000:])
        return proc

    def worker():
        prefix = ['docker', 'compose', '-p', session_id]
        environment = os.environ.copy()
        try:
            manifest = yaml.safe_load((Path(workspace_dir) / 'docker-compose.yml').read_text(encoding='utf-8'))
            images = {builder_image(workspace_dir), 'agentia-runtime:21-v1'}
            images.update(c['image'] for c in manifest['services'].values() if 'build' not in c)
            for image in sorted(images):
                try:
                    execute(['docker', 'image', 'inspect', image], environment, 10)
                except RuntimeError:
                    raise RuntimeError(f'Imagen offline ausente: {image}. Ejecute prepare-local.ps1 con conexión y reintente.')
            session.hostPort = available_port(host_port)
            environment['HOST_PORT'] = str(session.hostPort)
            if session.hostPort != host_port:
                session.message = f'Puerto {host_port} ocupado. Se eligió {session.hostPort}.'
                _log_message(session_id, session.message)
            execute(prefix + ['config', '--quiet'], environment, 10)
            _log_message(session_id, '[PHASE] Construcción y pruebas offline')
            execute(prefix + ['build', '--pull=false', '--no-cache'], environment, 600)
            for attempt in range(3):
                environment['HOST_PORT'] = str(session.hostPort)
                try:
                    execute(prefix + ['up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '180'], environment, 200)
                    break
                except RuntimeError as exc:
                    if attempt == 2 or not any(p in str(exc).lower() for p in ('port is already allocated', 'address already in use', 'ports are not available')):
                        raise
                    session.hostPort = available_port(session.hostPort + 1)
                    session.message = f'Conflicto de puerto durante el arranque. Puerto elegido: {session.hostPort}.'
                    _log_message(session_id, session.message)
            recovered = inspect_session(session_id)
            if not recovered or recovered.status != DeploymentStatus.RUNNING:
                raise RuntimeError('Compose terminó sin el contenedor activo de esta sesión.')
            session.containerId, session.databaseContainerId = recovered.containerId, recovered.databaseContainerId
            session.hostPort, session.status = recovered.hostPort, DeploymentStatus.RUNNING
            persist(session)
            smoke = run_smoke_test(session_id, max_retries=10, interval=1)
            if not smoke.passed:
                raise RuntimeError('Smoke test failed: ' + smoke.details)
            session.status, session.healthStatus, session.testUrl = DeploymentStatus.HEALTHY, 'UP', smoke.testUrl
            _log_message(session_id, '[HEALTHY] ' + smoke.testUrl)
        except Exception as exc:
            session.status, session.errorMessage = DeploymentStatus.FAILED, str(exc)
            _log_message(session_id, '[FAILED] ' + str(exc))
        finally:
            _active_deployments[session_id] = session
            try:
                persist(session)
            finally:
                lock.release()
    try:
        threading.Thread(target=worker, daemon=True).start()
    except Exception as exc:
        session.status, session.errorMessage = DeploymentStatus.FAILED, str(exc)
        try:
            persist(session)
        finally:
            lock.release()
        raise
    return session


def stream_logs(session_id: str, after_id: int = 0) -> Generator[str, None, None]:
    from app.services.deployment_logs import frames
    delivered = after_id
    for _ in range(60):
        for delivered, frame in frames(_deployment_log_snapshot(session_id), delivered):
            yield frame
        yield ': keep-alive\n\n'
        time.sleep(1)


def stop_deployment(session_id: str, workspace_dir: str) -> LocalDeploymentSession:
    from app.services.execution_policy import execution_mode
    from app.services.local_runtime import persist, inspect_session
    if execution_mode(session_id).value == 'SOURCE_ONLY':
        return get_deployment_status(session_id)
    with _operations_lock:
        lock = _operation_locks.setdefault(session_id, threading.Lock())
    if not lock.acquire(blocking=False):
        return LocalDeploymentSession(sessionId=session_id, status=DeploymentStatus.BUILDING, errorMessage='Espere a que termine la construcción antes de detener.')
    session = _active_deployments.get(session_id) or LocalDeploymentSession(sessionId=session_id)
    try:
        proc = subprocess.run(['docker', 'compose', '-p', session_id, 'down'], cwd=workspace_dir, capture_output=True, text=True, timeout=60, check=False)
        if proc.returncode:
            raise RuntimeError(proc.stderr or 'Docker Compose no pudo detener los contenedores.')
        actual = inspect_session(session_id)
        if actual and actual.status != DeploymentStatus.STOPPED:
            raise RuntimeError('El contenedor de esta sesión sigue activo.')
        session.status, session.healthStatus, session.testUrl, session.errorMessage = DeploymentStatus.STOPPED, 'DOWN', None, None
        _log_message(session_id, '[STOPPED] Contenedores detenidos; datos conservados.')
    except Exception as exc:
        session.status, session.errorMessage = DeploymentStatus.FAILED, str(exc)
    finally:
        _active_deployments[session_id] = session
        try:
            persist(session)
        finally:
            lock.release()
    return session


def run_smoke_test(
    session_id: str,
    host_port: int = 8080,
    max_retries: int = 15,
    interval: float = 2.0
) -> SmokeTestResult:
    """Polls http://localhost:{host_port}/actuator/health until UP or timeout."""
    deployment = get_deployment_status(session_id)
    if not deployment.containerId or deployment.status not in (DeploymentStatus.RUNNING, DeploymentStatus.HEALTHY, DeploymentStatus.DEGRADED):
        return SmokeTestResult(passed=False, statusCode=409, testUrl="", details="No hay un contenedor activo de esta sesión; prueba no ejecutada.")
    host_port = deployment.hostPort
    test_url = f"http://localhost:{host_port}/actuator/health"
    start_time = time.time()
    last_status = 0
    last_payload = {}

    for attempt in range(1, max_retries + 1):
        from app.services.local_runtime import inspect_session
        actual = inspect_session(session_id)
        if not actual or actual.containerId != deployment.containerId or actual.hostPort != host_port or actual.status != DeploymentStatus.RUNNING:
            return SmokeTestResult(passed=False, statusCode=0, testUrl=test_url, details="La identidad o disponibilidad del contenedor cambió; prueba interrumpida.")
        try:
            req_start = time.time()
            resp = requests.get(test_url, timeout=3.0)
            latency = (time.time() - req_start) * 1000.0
            last_status = resp.status_code
            last_payload = {}

            if resp.status_code == 200:
                try:
                    payload = resp.json()
                except ValueError:
                    payload = {"error": "La respuesta de salud no es JSON."}
                if not isinstance(payload, dict):
                    payload = {"error": "La respuesta de salud no es un objeto JSON."}
                last_payload = payload

                if payload.get("status") == "UP":
                    result = SmokeTestResult(
                        passed=True,
                        statusCode=200,
                        statusPayload=payload,
                        latencyMs=round(latency, 2),
                        testUrl=test_url,
                        details="Actuator reports application status is UP.",
                    )
                    if session_id in _active_deployments:
                        _active_deployments[session_id].status = DeploymentStatus.HEALTHY
                        _active_deployments[session_id].healthStatus = "UP"
                        _active_deployments[session_id].testUrl = test_url
                    return result
        except requests.RequestException:
            last_status, last_payload = 0, {"error": "No se recibió respuesta HTTP."}

        time.sleep(interval)

    total_latency = (time.time() - start_time) * 1000.0
    return SmokeTestResult(
        passed=False,
        statusCode=last_status,
        statusPayload=last_payload,
        latencyMs=round(total_latency, 2),
        testUrl=test_url,
        details=f"Actuator healthcheck timed out after {max_retries} attempts.",
    )



def wait_for_deployment(session_id, timeout=850):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        deployment = get_deployment_status(session_id)
        if deployment.status != DeploymentStatus.BUILDING:
            return deployment
        time.sleep(0.5)
    return LocalDeploymentSession(sessionId=session_id, status=DeploymentStatus.FAILED, errorMessage='El despliegue excedió el plazo de espera.')
