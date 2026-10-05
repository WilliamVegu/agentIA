from app.services.session_operation_lock import SessionOperationLock
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
from app.services.logged_process import run_logged

# Runtime registry and independent snapshots; legacy queue store is unused.
_active_deployments: Dict[str, LocalDeploymentSession] = {}
_log_queues: Dict[str, queue.Queue] = {}
_operations_lock = threading.RLock()
_operation_locks = {}
_raw_log_history: Dict[str, dict] = {}


def check_docker_daemon() -> bool:
    """Checks if the local Docker daemon is running and reachable within a 2s timeout."""
    if not settings.DOCKER_ENABLED:
        return False
    try:
        # Use docker info to test daemon communication
        result = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
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
        from app.services.runtime_log_capture import stop_capture
        stop_capture(session_id)
        return LocalDeploymentSession(sessionId=session_id, status=DeploymentStatus.SKIPPED_BY_CHOICE)
    stored = _active_deployments.get(session_id) or restore(session_id)
    if stored and stored.status == DeploymentStatus.BUILDING:
        return stored
    if not check_docker_daemon():
        row = stored or LocalDeploymentSession(sessionId=session_id)
        row.status, row.healthStatus, row.testUrl = DeploymentStatus.DOCKER_UNAVAILABLE, 'UNKNOWN', None
        row.errorMessage = 'Docker no disponible. Reintentar o continuar sin Docker; no se confirma parada.'
        persist(row)
        return row
    try:
        session = inspect_session(session_id)
        if session is None:
            if stored and stored.containerId:
                stored.status, stored.healthStatus, stored.testUrl = DeploymentStatus.STOPPED, "DOWN", None
                persist(stored)
            return stored or LocalDeploymentSession(sessionId=session_id)
        if stored:
            session.operationId, session.message = stored.operationId, stored.message
            for field in ('operationKind', 'operationPhase', 'startedAt', 'finishedAt', 'cancelRequested'):
                setattr(session, field, getattr(stored, field))
            if stored.sourceSnapshotId and any(getattr(session, field) != getattr(stored, field)
                for field in ('sourceSnapshotId', 'workspaceFingerprint', 'imageId', 'executableJarSha256')):
                stored.status, stored.healthStatus, stored.testUrl = DeploymentStatus.DEGRADED, 'UNKNOWN', None
                stored.errorMessage = 'Runtime/imagen no coincide con la cadena de snapshot verificada; salud no confirmada.'
                persist(stored)
                return stored
        if session.status == DeploymentStatus.RUNNING:
            session.testUrl = f"http://localhost:{session.hostPort}/actuator/health"
            try:
                resp = requests.get(f'http://127.0.0.1:{session.hostPort}/actuator/health', timeout=1, allow_redirects=False)
                payload = resp.json()
                if resp.status_code == 200 and isinstance(payload, dict) and payload.get("status") == "UP":
                    confirmed = inspect_session(session_id)
                    if same_runtime(session, confirmed):
                        session.status, session.healthStatus = DeploymentStatus.HEALTHY, "UP"
                    else:
                        session.status, session.healthStatus, session.testUrl = DeploymentStatus.DEGRADED, 'UNKNOWN', None
                        session.errorMessage = 'La identidad o disponibilidad cambió durante la consulta de salud.'
                else:
                    session.status, session.healthStatus = DeploymentStatus.DEGRADED, "DOWN"
            except (requests.RequestException, ValueError):
                session.status, session.healthStatus = DeploymentStatus.DEGRADED, "UNKNOWN"
        _active_deployments[session_id] = session
        persist(session)
        if session.containerId:
            from app.services.runtime_log_capture import ensure_capture
            ensure_capture(session_id)
        return session
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        session = stored or LocalDeploymentSession(sessionId=session_id)
        session.status, session.healthStatus, session.errorMessage = DeploymentStatus.FAILED, "UNKNOWN", str(exc)
        session.testUrl = None
        persist(session)
        return session


def get_deployment_logs(session_id: str) -> list:
    from app.services.deployment_logs import display
    return [display(entry) for entry in _deployment_log_snapshot(session_id)['entries']]


def get_deployment_log_snapshot(session_id: str) -> dict:
    from app.services.deployment_logs import display
    history = _deployment_log_snapshot(session_id)
    return {'logs': [display(entry) for entry in history['entries']],
            'events': history['entries'], 'lastEventId': history['nextId'] - 1}


def _deployment_log_snapshot(session_id):
    from app.services.deployment_logs import load
    with _operations_lock:
        if session_id not in _raw_log_history:
            _raw_log_history[session_id] = load(session_id)
        history = _raw_log_history[session_id]
        return {**history, 'entries': [dict(entry) for entry in history['entries']]}


def _log_message(session_id: str, message: str, source='system', timestamp=None):
    from app.services.deployment_logs import append
    with _operations_lock:
        history = _deployment_log_snapshot(session_id)
        _raw_log_history[session_id] = append(session_id, history, message, source, timestamp)


def deploy_local(session_id: str, workspace_dir: str, host_port: Optional[int] = None, rebuild: bool = False) -> LocalDeploymentSession:
    import json
    import uuid
    import yaml
    from app.services.execution_policy import execution_mode
    from app.services.local_runtime import available_port, inspect_session, persist
    from app.services.local_deployment_assets import builder_image
    if execution_mode(session_id).value == "SOURCE_ONLY":
        return get_deployment_status(session_id)
    from app.services.local_configuration import resolve_configuration
    host_port = resolve_configuration(workspace_dir, session_id, port=host_port)['hostPort']
    from app.services.verification_policy import workspace_fingerprint
    input_fingerprint = workspace_fingerprint(workspace_dir)
    if not check_docker_daemon():
        return LocalDeploymentSession(sessionId=session_id, status=DeploymentStatus.DOCKER_UNAVAILABLE, errorMessage="Docker no disponible. Reintentar o continuar sin Docker.")
    with _operations_lock:
        lock = _operation_locks.setdefault(session_id, SessionOperationLock(session_id))
    if not lock.acquire(blocking=False):
        return _active_deployments.get(session_id) or get_deployment_status(session_id)
    session = LocalDeploymentSession(sessionId=session_id, status=DeploymentStatus.BUILDING, hostPort=host_port, operationId=str(uuid.uuid4()), startedAt=datetime.now(timezone.utc).isoformat())
    from app.services.local_operations import register, phase, finish
    from app.services.logged_process import CommandCancelled
    cancel_event = register(session, 'DEPLOY')
    _active_deployments[session_id] = session
    try:
        persist(session)
    except Exception as exc:
        session.status, session.errorMessage = DeploymentStatus.FAILED, str(exc)
        finish(session)
        lock.release()
        raise

    def execute(command, environment, timeout):
        phase(session, session.operationPhase or 'PREFLIGHT', cancel_event)
        _log_message(session_id, '[EXEC] ' + ' '.join(command))
        proc = subprocess.run(command, cwd=execution_workspace, env=environment, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout, check=False)
        for line in (proc.stdout + '\n' + proc.stderr).splitlines()[-1000:]:
            if line.strip():
                _log_message(session_id, line)
        if proc.returncode:
            raise RuntimeError(f"Docker exit code {proc.returncode}: " + (proc.stderr or proc.stdout or 'Docker falló')[-2000:])
        phase(session, session.operationPhase, cancel_event)
        return proc

    execution_workspace = workspace_dir
    def worker():
        nonlocal execution_workspace
        from contextlib import ExitStack
        stack = ExitStack()
        prefix = ['docker', 'compose', '-p', session_id]
        environment = os.environ.copy()
        start_attempted = False
        try:
            phase(session, 'PREFLIGHT', cancel_event)
            def require_unchanged_sources():
                if not input_fingerprint or workspace_fingerprint(workspace_dir) != input_fingerprint:
                    raise RuntimeError('Las fuentes/manifiestos cambiaron durante el despliegue. Reintente la verificación; no se arrancará con evidencia anterior.')
            require_unchanged_sources()
            from app.models.session import SessionLocal, GenerationSessionDB
            with SessionLocal() as db:
                row = db.get(GenerationSessionDB, session_id)
                metrics = json.loads(row.verification_metrics_json or '{}') if row else {}
            snapshot_id = metrics.get('sourceSnapshotId')
            if snapshot_id:
                from app.services.source_snapshot import materialize_snapshot
                execution_workspace, jar_hash = stack.enter_context(materialize_snapshot(workspace_dir, snapshot_id, input_fingerprint))
                session.sourceSnapshotId, session.workspaceFingerprint = snapshot_id, input_fingerprint
                session.executableJarSha256 = jar_hash
                # Credentials remain outside the seal, provided only at runtime.
                env_file = Path(workspace_dir) / '.env'
                if env_file.is_file(): prefix += ['--env-file', str(env_file.resolve())]
                runtime_dockerfile = '''FROM agentia-runtime:21-v1
WORKDIR /app
ARG AGENTIA_SOURCE_FINGERPRINT
ARG AGENTIA_SOURCE_SNAPSHOT
ARG AGENTIA_JAR_SHA256
LABEL io.agentia.source-fingerprint=$AGENTIA_SOURCE_FINGERPRINT io.agentia.source-snapshot=$AGENTIA_SOURCE_SNAPSHOT io.agentia.jar-sha256=$AGENTIA_JAR_SHA256
COPY --chown=10001:10001 .verified-artifact/application.jar /app/application.jar
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75.0" SERVER_PORT=8080
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=60s --retries=5 CMD wget -q -O - http://127.0.0.1:8080/actuator/health | grep -q '"status":"UP"' || exit 1
ENTRYPOINT ["java", "-jar", "/app/application.jar"]
'''
                (Path(execution_workspace) / 'Dockerfile.verified').write_text(runtime_dockerfile, encoding='utf-8')
                profile = yaml.safe_load((Path(execution_workspace) / 'docker-compose.yml').read_text(encoding='utf-8'))
                applications = [c for c in profile['services'].values() if c.get('labels', {}).get('io.agentia.role') == 'application']
                if len(applications) != 1: raise ValueError('Aplicación del snapshot ambigua')
                applications[0]['build']['dockerfile'] = 'Dockerfile.verified'
                applications[0]['build']['args'] = {'AGENTIA_SOURCE_FINGERPRINT': input_fingerprint,
                    'AGENTIA_SOURCE_SNAPSHOT': snapshot_id, 'AGENTIA_JAR_SHA256': jar_hash}
                # Existing dockerignore may exclude dotfiles: explicitly include only this JAR.
                ignore = Path(execution_workspace) / '.dockerignore'
                with ignore.open('a', encoding='utf-8') as output: output.write('\n!.verified-artifact/\n!.verified-artifact/application.jar\n')
                (Path(execution_workspace) / 'docker-compose.yml').write_text(yaml.safe_dump(profile, sort_keys=False), encoding='utf-8')
            manifest = yaml.safe_load((Path(execution_workspace) / 'docker-compose.yml').read_text(encoding='utf-8'))
            # A private Compose override ties the daemon record to this exact operation.
            overrides = {'services': {name: {'build': {'labels': {'io.agentia.operation': session.operationId}}}
                for name, config in manifest['services'].items() if config.get('build')}}
            override_path = Path(execution_workspace) / '.agentia-runtime' / ('build-' + session.operationId + '.yml')
            override_path.parent.mkdir(parents=True, exist_ok=True)
            override_path.write_text(yaml.safe_dump(overrides), encoding='utf-8')
            stack.callback(override_path.unlink, missing_ok=True)
            prefix += ['-f', str((Path(execution_workspace) / 'docker-compose.yml').resolve()), '-f', str(override_path.resolve())]
            images = {builder_image(workspace_dir), 'agentia-runtime:21-v1'}
            if snapshot_id: images.discard(builder_image(workspace_dir))
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
            _log_message(session_id, '[PHASE] Empaquetado del JAR verificado sin nuevas pruebas' if snapshot_id else '[PHASE] Construcción y pruebas offline')
            phase(session, 'BUILD', cancel_event)
            require_unchanged_sources()
            from app.services.buildkit_outcome import run_build
            run_build(prefix + ['build', '--pull=false', '--no-cache'],
                       lambda line: _log_message(session_id, line, source='build'),
                       operation_id=session.operationId, runner=run_logged,
                       cwd=execution_workspace, env=environment, timeout=settings.LOCAL_BUILD_TIMEOUT, cancel_event=cancel_event)
            phase(session, 'START', cancel_event)
            require_unchanged_sources()
            if snapshot_id:
                app = next(c for c in manifest['services'].values() if c.get('labels', {}).get('io.agentia.role') == 'application')
                tag = app['image'].replace('${COMPOSE_PROJECT_NAME}', session_id)
                metadata = json.loads(execute(['docker', 'image', 'inspect', tag], environment, 10).stdout)[0]
                labels = metadata['Config']['Labels']
                if labels.get('io.agentia.source-fingerprint') != input_fingerprint or labels.get('io.agentia.source-snapshot') != snapshot_id or labels.get('io.agentia.jar-sha256') != jar_hash:
                    raise RuntimeError('Imagen no corresponde al snapshot/JAR verificado')
                session.imageId = metadata['Id']
            for attempt in range(3):
                environment['HOST_PORT'] = str(session.hostPort)
                try:
                    start_attempted = True
                    execute(prefix + ['up', '-d', '--no-build', '--pull', 'never', '--wait', '--wait-timeout', '180'], environment, settings.LOCAL_START_TIMEOUT)
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
            if snapshot_id and (recovered.imageId != session.imageId or recovered.sourceSnapshotId != snapshot_id or recovered.workspaceFingerprint != input_fingerprint or recovered.executableJarSha256 != jar_hash):
                from app.services.runtime_lifecycle import stop_interrupted_runtime
                stop_interrupted_runtime(session_id)
                raise RuntimeError('Runtime no corresponde a imagen/snapshot verificado; recursos propios detenidos y datos conservados.')
            session.containerId, session.databaseContainerId = recovered.containerId, recovered.databaseContainerId
            session.dbEngine = recovered.dbEngine
            session.hostPort, session.status = recovered.hostPort, DeploymentStatus.RUNNING
            persist(session)
            phase(session, 'READINESS', cancel_event)
            smoke = run_smoke_test(session_id, max_retries=10, interval=1, cancel_event=cancel_event)
            if not smoke.passed:
                raise RuntimeError('Smoke test failed: ' + smoke.details)
            phase(session, 'COMPLETE', cancel_event)
            session.status, session.healthStatus, session.testUrl = DeploymentStatus.HEALTHY, 'UP', smoke.testUrl
            _log_message(session_id, '[HEALTHY] ' + smoke.testUrl)
        except Exception as exc:
            session.status, session.errorMessage = DeploymentStatus.FAILED, str(exc)
            session.healthStatus, session.testUrl = 'UNKNOWN', None
            if cancel_event.is_set() or isinstance(exc, (CommandCancelled, subprocess.TimeoutExpired)):
                session.operationPhase = 'INTERRUPTED'
                if start_attempted:
                    try:
                        from app.services.runtime_lifecycle import stop_interrupted_runtime
                        stop_interrupted_runtime(session_id)
                        session.errorMessage += ' Contenedores propios detenidos; datos conservados.'
                    except Exception as cleanup_error:
                        session.errorMessage += ' Parada no confirmada: ' + str(cleanup_error)
            _log_message(session_id, '[FAILED] ' + str(exc))
        finally:
            try:
                stack.close()
            except Exception as cleanup_error:
                session.status, session.healthStatus = DeploymentStatus.FAILED, 'UNKNOWN'
                session.errorMessage = (session.errorMessage or '') + ' Limpieza de copia de snapshot no confirmada: ' + str(cleanup_error)
            _active_deployments[session_id] = session
            finish(session)
            try:
                persist(session)
            finally:
                lock.release()
    try:
        threading.Thread(target=worker, daemon=True).start()
    except Exception as exc:
        session.status, session.errorMessage = DeploymentStatus.FAILED, str(exc)
        finish(session)
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
        lock = _operation_locks.setdefault(session_id, SessionOperationLock(session_id))
    if not lock.acquire(blocking=False):
        return LocalDeploymentSession(sessionId=session_id, status=DeploymentStatus.BUILDING, errorMessage='Espere a que termine la construcción antes de detener.')
    from app.services.runtime_log_capture import stop_capture
    stop_capture(session_id)
    session = _active_deployments.get(session_id) or LocalDeploymentSession(sessionId=session_id)
    try:
        from app.services.runtime_lifecycle import owned_resources, _command
        containers = owned_resources(session_id)
        running = [c['Id'] for c in containers if c.get('State', {}).get('Running') is True]
        if running: _command(['docker', 'stop', '--time', '10', *running], timeout=60)
        if any(c.get('State', {}).get('Running') is True for c in owned_resources(session_id)):
            raise RuntimeError('Quedan contenedores activos de esta sesión; parada no confirmada.')
        session.status, session.healthStatus, session.testUrl, session.errorMessage = DeploymentStatus.STOPPED, 'DOWN', None, None
        _log_message(session_id, '[STOPPED] Contenedores detenidos; datos conservados.')
    except Exception as exc:
        session.status, session.errorMessage = DeploymentStatus.FAILED, str(exc)
        session.healthStatus, session.testUrl = 'UNKNOWN', None
    finally:
        _active_deployments[session_id] = session
        try:
            persist(session)
        finally:
            lock.release()
    return session


def same_runtime(expected, actual):
    """Only a running inspected instance on the same localhost binding can certify a response."""
    return bool(actual and expected.containerId and actual.status == DeploymentStatus.RUNNING
                and actual.containerId == expected.containerId and actual.hostPort == expected.hostPort
                and actual.databaseContainerId == expected.databaseContainerId
                and all(not getattr(expected, field, None) or getattr(expected, field) == getattr(actual, field, None)
                        for field in ('imageId', 'sourceSnapshotId', 'workspaceFingerprint', 'executableJarSha256')))


def run_smoke_test(
    session_id: str,
    host_port: int = 8080,
    max_retries: int = 15,
    interval: float = 2.0,
    cancel_event=None,
) -> SmokeTestResult:
    """Polls http://localhost:{host_port}/actuator/health until UP or timeout."""
    from app.services.logged_process import CommandCancelled
    if cancel_event is not None and cancel_event.is_set():
        raise CommandCancelled('Readiness interrumpido; no se confirma cancelación del daemon.')
    deployment = get_deployment_status(session_id)
    if not deployment.containerId or deployment.status not in (DeploymentStatus.RUNNING, DeploymentStatus.HEALTHY, DeploymentStatus.DEGRADED):
        return SmokeTestResult(passed=False, statusCode=409, testUrl="", details="No hay un contenedor activo de esta sesión; prueba no ejecutada.")
    host_port = deployment.hostPort
    deployment = deployment.model_copy(deep=True)
    test_url = f"http://localhost:{host_port}/actuator/health"
    start_time = time.time()
    last_status = 0
    last_payload = {}

    for attempt in range(1, max_retries + 1):
        if cancel_event is not None and cancel_event.is_set():
            raise CommandCancelled('Readiness interrumpido; no se confirma cancelación del daemon.')
        from app.services.local_runtime import inspect_session
        actual = inspect_session(session_id)
        if not same_runtime(deployment, actual):
            return SmokeTestResult(passed=False, statusCode=0, testUrl=test_url, details="La identidad o disponibilidad del contenedor cambió; prueba interrumpida.")
        try:
            req_start = time.time()
            resp = requests.get(f'http://127.0.0.1:{host_port}/actuator/health', timeout=3.0, allow_redirects=False)
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
                    if not same_runtime(deployment, inspect_session(session_id)):
                        return SmokeTestResult(passed=False, statusCode=0, testUrl=test_url,
                            details='La identidad cambió durante la respuesta HTTP; salud no confirmada.')
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

        if cancel_event is not None:
            cancel_event.wait(interval)
        else:
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



def wait_for_deployment(session_id, timeout=None, stop_event=None):
    """Wait for the operation lock to be released, including smoke/persistence, not just RUNNING."""
    timeout = settings.LOCAL_DEPLOY_WAIT_TIMEOUT if timeout is None else timeout
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if stop_event is not None and stop_event.is_set():
            return LocalDeploymentSession(sessionId=session_id, status=DeploymentStatus.FAILED,
                errorMessage='Espera de Auto-Pilot interrumpida; no se confirma cancelación de Docker.')
        with _operations_lock:
            lock = _operation_locks.get(session_id)
            busy = bool(lock and lock.locked())
        if not busy:
            deployment = _active_deployments.get(session_id) or get_deployment_status(session_id)
            if deployment.status == DeploymentStatus.RUNNING:
                deployment = get_deployment_status(session_id)
        else:
            deployment = None
        if deployment is not None and deployment.status not in (DeploymentStatus.BUILDING, DeploymentStatus.RUNNING):
            return deployment
        if stop_event is not None:
            stop_event.wait(0.5)
        else:
            time.sleep(0.5)
    return LocalDeploymentSession(sessionId=session_id, status=DeploymentStatus.FAILED,
        errorMessage='El despliegue excedió el plazo de espera. La operación Docker puede seguir activa; consulte su estado.')
