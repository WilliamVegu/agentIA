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

# In-memory tracking for active deployments and log queues
_active_deployments: Dict[str, LocalDeploymentSession] = {}
_log_queues: Dict[str, queue.Queue] = {}
_raw_log_history: Dict[str, list] = {}


def check_docker_daemon() -> bool:
    """Checks if the local Docker daemon is running and reachable within a 2s timeout."""
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


def get_deployment_status(session_id: str, host_port: int = 8080) -> LocalDeploymentSession:
    """Returns the current deployment tracking state for a session, actively checking actual container health."""
    session = _active_deployments.get(session_id)
    if session and session.status == DeploymentStatus.BUILDING:
        return session

    # Check if container is actually running and healthy via Actuator
    test_url = f"http://localhost:{host_port}/actuator/health"
    try:
        resp = requests.get(test_url, timeout=0.8)
        if resp.status_code == 200 and resp.json().get("status") == "UP":
            if not session:
                session = LocalDeploymentSession(
                    sessionId=session_id,
                    status=DeploymentStatus.HEALTHY,
                    hostPort=host_port,
                    containerPort=8080,
                    testUrl=test_url,
                    healthStatus="UP",
                )
                _active_deployments[session_id] = session
            else:
                session.status = DeploymentStatus.HEALTHY
                session.healthStatus = "UP"
                session.testUrl = test_url
                session.errorMessage = None
            return session
    except Exception:
        pass

    if session:
        return session
    return LocalDeploymentSession(sessionId=session_id, status=DeploymentStatus.IDLE)


def get_deployment_logs(session_id: str) -> list:
    """Returns the captured logs history for a session."""
    return _raw_log_history.get(session_id, [])


def _log_message(session_id: str, message: str):
    """Appends a log line to the session queue and history."""
    if session_id not in _log_queues:
        _log_queues[session_id] = queue.Queue()
    if session_id not in _raw_log_history:
        _raw_log_history[session_id] = []

    _log_queues[session_id].put(message)
    _raw_log_history[session_id].append(message)


def deploy_local(
    session_id: str,
    workspace_dir: str,
    host_port: int = 8080,
    rebuild: bool = False
) -> LocalDeploymentSession:
    """Initiates background local container deployment using docker-compose."""
    # 1. Preventive Daemon Check (Ratified Option A)
    if not check_docker_daemon():
        session = LocalDeploymentSession(
            sessionId=session_id,
            status=DeploymentStatus.DOCKER_UNAVAILABLE,
            hostPort=host_port,
            containerPort=8080,
            errorMessage="Docker daemon is not running or accessible on the host. Entering Export-Only mode.",
            startedAt=datetime.now(timezone.utc).isoformat(),
        )
        _active_deployments[session_id] = session
        _log_message(session_id, "[ERROR] Docker daemon is unreachable. Local deployment disabled.")
        return session

    # 2. Setup Active Deployment Tracking
    session = LocalDeploymentSession(
        sessionId=session_id,
        status=DeploymentStatus.BUILDING,
        hostPort=host_port,
        containerPort=8080,
        startedAt=datetime.now(timezone.utc).isoformat(),
    )
    _active_deployments[session_id] = session
    _log_queues[session_id] = queue.Queue()
    _raw_log_history[session_id] = []

    _log_message(session_id, f"[INFO] Initializing Docker Compose deployment for session {session_id} on port {host_port}...")

    # 3. Spawn Background Execution Thread
    def _run_compose():
        try:
            cmd = ["docker", "compose", "up", "-d"]
            if rebuild:
                cmd.append("--build")

            _log_message(session_id, f"[EXEC] Running: {' '.join(cmd)}")
            proc = subprocess.Popen(
                cmd,
                cwd=workspace_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            if proc.stdout:
                for line in proc.stdout:
                    clean_line = line.strip()
                    if clean_line:
                        _log_message(session_id, clean_line)

            proc.wait()

            if proc.returncode == 0:
                _log_message(session_id, "[SUCCESS] Docker Compose containers launched successfully.")
                session.status = DeploymentStatus.RUNNING
                # Run automated smoke test
                _log_message(session_id, "[SMOKE_TEST] Polling /actuator/health for readiness...")
                smoke_res = run_smoke_test(session_id, host_port, max_retries=20, interval=2.0)
                if smoke_res.passed:
                    session.status = DeploymentStatus.HEALTHY
                    session.healthStatus = "UP"
                    session.testUrl = smoke_res.testUrl
                    _log_message(session_id, f"[READY] Application is HEALTHY at {smoke_res.testUrl} (Latency: {smoke_res.latencyMs:.1f}ms)")
                else:
                    session.status = DeploymentStatus.FAILED
                    session.errorMessage = f"Smoke test failed: {smoke_res.details}"
                    _log_message(session_id, f"[WARNING] Smoke test failed: {smoke_res.details}")
            else:
                session.status = DeploymentStatus.FAILED
                session.errorMessage = f"Docker compose failed with exit code {proc.returncode}"
                _log_message(session_id, f"[ERROR] Docker compose failed with exit code {proc.returncode}")

        except Exception as e:
            session.status = DeploymentStatus.FAILED
            session.errorMessage = str(e)
            _log_message(session_id, f"[FATAL] Deployment exception: {str(e)}")

    thread = threading.Thread(target=_run_compose, daemon=True)
    thread.start()

    return session


def stream_logs(session_id: str) -> Generator[str, None, None]:
    """Generates Server-Sent Events (SSE) from the session log queue."""
    if session_id not in _log_queues:
        _log_queues[session_id] = queue.Queue()

    # Replay existing log history first
    history = _raw_log_history.get(session_id, [])
    for msg in history:
        yield f"data: {msg}\n\n"

    # Stream new logs live
    q = _log_queues[session_id]
    timeout_counter = 0
    while timeout_counter < 30:  # Terminate stream after 30 idle iterations (~15s)
        try:
            msg = q.get(timeout=0.5)
            timeout_counter = 0
            yield f"data: {msg}\n\n"
        except queue.Empty:
            timeout_counter += 1
            yield f": keep-alive\n\n"


def stop_deployment(session_id: str, workspace_dir: str) -> LocalDeploymentSession:
    """Stops and cleans up active containers via docker compose down."""
    session = _active_deployments.get(session_id, LocalDeploymentSession(sessionId=session_id))
    try:
        subprocess.run(
            ["docker", "compose", "down", "-v"],
            cwd=workspace_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15.0,
            check=False,
        )
    except Exception:
        pass

    session.status = DeploymentStatus.STOPPED
    _log_message(session_id, "[STOPPED] Containers and networks terminated.")
    return session


def run_smoke_test(
    session_id: str,
    host_port: int = 8080,
    max_retries: int = 15,
    interval: float = 2.0
) -> SmokeTestResult:
    """Polls http://localhost:{host_port}/actuator/health until UP or timeout."""
    test_url = f"http://localhost:{host_port}/actuator/health"
    start_time = time.time()

    for attempt in range(1, max_retries + 1):
        try:
            req_start = time.time()
            resp = requests.get(test_url, timeout=3.0)
            latency = (time.time() - req_start) * 1000.0

            if resp.status_code == 200:
                try:
                    payload = resp.json()
                except Exception:
                    payload = {"raw": resp.text}

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
            pass

        time.sleep(interval)

    total_latency = (time.time() - start_time) * 1000.0
    return SmokeTestResult(
        passed=False,
        statusCode=503,
        statusPayload={"status": "DOWN"},
        latencyMs=round(total_latency, 2),
        testUrl=test_url,
        details=f"Actuator healthcheck timed out after {max_retries} attempts.",
    )

