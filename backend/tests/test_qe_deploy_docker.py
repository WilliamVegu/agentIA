"""QE coverage: the local deploy path (``services/docker_service.py``).

This was the least covered module of any real size in the backend (40.4%), and it is
the one the demo UI drives. It matters more than a coverage number suggests, because
every branch here decides *what the operator is told about a container*:

* ``DOCKER_UNAVAILABLE`` is not a failure of the service -- it is Export-Only mode,
  and the operator must be told the difference.
* ``HEALTHY`` is a *verification claim*. It is only honest if a real
  ``/actuator/health`` answered ``UP``. Feature 012 spent a whole feature removing a
  fabricated success from the backend verifier and from this module's frontend
  callers (see ``docs/frontend_audit.md``), so the checks that keep it honest are
  pinned here.
* ``FAILED`` must carry the exit code, so a support ticket has something to go on.

No container is ever started and no socket is ever opened: the ``subprocess`` and
``requests`` boundaries are faked. The ``threading.Thread`` boundary is faked too --
the compose worker is spawned as a daemon thread, and a test that raced it would be
flaky in exactly the way that makes a suite untrustworthy.
"""

from __future__ import annotations

import queue
import subprocess
import sys
import threading
from pathlib import Path

import pytest
import requests
from types import SimpleNamespace
from app.models.execution import ExecutionMode
from app.config import settings
from app.services import local_runtime, execution_policy
from app.services.devops_service import generate_all_devops_assets

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

import app.services.docker_service as ds  # noqa: E402
from app.models.devops import DeploymentStatus, LocalDeploymentSession, SmokeTestResult  # noqa: E402

SESSION_ID = "qe-deploy-session"


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------
class _InlineThread:
    """Runs the compose worker on the calling thread.

    ``deploy_local`` returns the moment it spawns the worker, so the only way to
    assert on a *finished* deployment without sleeping is to make ``start()`` run the
    target inline. A test that polled the module dict for up to N seconds would pass
    on a fast machine and fail on a loaded one.
    """

    def __init__(self, target=None, args=(), kwargs=None, daemon=None, **extra):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        if self._target:
            self._target(*self._args, **self._kwargs)

    def join(self, timeout=None):
        return None

    def is_alive(self):
        return False


class _FakeProcess:
    """The slice of ``subprocess.Popen`` the compose worker actually uses."""

    def __init__(self, returncode: int = 0, lines: tuple = (), raise_on_wait: bool = False):
        self.returncode = returncode
        self.stdout = iter([f"{line}\n" for line in lines])
        self._raise_on_wait = raise_on_wait

    def wait(self):
        if self._raise_on_wait:
            raise OSError("worker died")
        return self.returncode


class _FakeResponse:
    def __init__(self, status_code: int = 200, payload=None, text: str = "", raise_json=False):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text
        self._raise_json = raise_json

    def json(self):
        if self._raise_json:
            raise ValueError("not JSON")
        return self._payload


@pytest.fixture(autouse=True)
def clean_deploy_state(monkeypatch, tmp_path, request):
    """Isolate the module-level stores, which are process-global by design.

    Without this, one test's deployment row leaks into the next and ``get_deployment_status``
    returns another test's session -- the classic way a suite becomes order-dependent.
    """
    monkeypatch.setattr(ds, "_active_deployments", {})
    monkeypatch.setattr(ds, "_log_queues", {})
    monkeypatch.setattr(ds, "_raw_log_history", {})
    monkeypatch.setattr(ds, "_operation_locks", {})
    monkeypatch.setattr(settings, "WORKSPACE_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "DOCKER_ENABLED", True)
    monkeypatch.setattr(execution_policy, "execution_mode", lambda *a, **kw: ExecutionMode.DOCKER)
    monkeypatch.setattr(ds, 'threading', SimpleNamespace(Thread=_InlineThread, Lock=threading.Lock, RLock=threading.RLock))
    monkeypatch.setattr(ds.subprocess, "Popen", lambda *a, **kw: _FakeProcess())
    generate_all_devops_assets(str(tmp_path), SESSION_ID, db_engine='H2')
    state = SimpleNamespace(started=False, port=8080)
    def inspected(sid):
        return LocalDeploymentSession(sessionId=sid, containerId='owned-container', hostPort=state.port, status=DeploymentStatus.RUNNING) if state.started else None
    monkeypatch.setattr(local_runtime, 'inspect_session', inspected)
    monkeypatch.setattr(local_runtime, 'available_port', lambda port: port)
    def run(cmd, **kwargs):
        if 'build' in cmd or 'up' in cmd:
            proc = ds.subprocess.Popen(cmd, **kwargs)
            stdout = ''.join(proc.stdout)
            code = proc.wait()
            if 'up' in cmd and not code:
                state.started, state.port = True, int(kwargs['env']['HOST_PORT'])
            return subprocess.CompletedProcess(cmd, code, stdout=stdout, stderr='')
        if 'down' in cmd or cmd[:2] == ['docker', 'stop']: state.started = False
        return subprocess.CompletedProcess(cmd, 0, stdout='', stderr='')
    monkeypatch.setattr(ds.subprocess, 'run', run)
    monkeypatch.setattr('app.services.runtime_lifecycle.owned_resources', lambda sid, kind='container':
        [{'Id': 'owned-container', 'State': {'Running': True}}] if kind == 'container' and state.started else [])
    # This fixture models command outcomes; real pipe/timeout behavior has separate tests.
    def logged(command, on_line, **kwargs):
        result = ds.subprocess.run(command, **kwargs)
        for line in (result.stdout or '').splitlines(): on_line(line)
        if result.returncode:
            raise RuntimeError(f'Docker exit code {result.returncode}: {result.stdout}')
        return 0
    monkeypatch.setattr(ds, 'run_logged', logged)
    monkeypatch.setattr('app.services.runtime_log_capture.ensure_capture', lambda _: None)
    # Daemon unit tests keep the real gate; operation tests simulate its availability.
    if 'daemon' not in request.node.name and 'docker_info' not in request.node.name:
        monkeypatch.setattr(ds, 'check_docker_daemon', lambda: True)
    readiness = {'test_a_healthy_actuator_passes_the_smoke_test_and_updates_the_session', 'test_a_missing_health_field_is_not_treated_as_up', 'test_a_non_json_body_degrades_to_the_raw_text_instead_of_crashing', 'test_an_unreachable_endpoint_is_retried_and_reported_as_a_timeout', 'test_a_smoke_test_passes_on_a_later_attempt_rather_than_the_first'}
    if request.node.name in readiness:
        state.started, state.port = True, 19090
        def status(sid):
            row = inspected(sid)
            ds._active_deployments[sid] = row
            return row
        monkeypatch.setattr(ds, 'get_deployment_status', status)
    yield


# ---------------------------------------------------------------------------
# check_docker_daemon -- the gate in front of every deploy
# ---------------------------------------------------------------------------
def test_the_daemon_is_reported_available_when_docker_info_exits_zero(monkeypatch):
    calls = {}

    def fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        calls["kwargs"] = kwargs
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(ds.subprocess, "run", fake_run)

    assert ds.check_docker_daemon() is True
    assert calls["cmd"] == ["docker", "info", "--format", "{{.ServerVersion}}"]
    assert calls["kwargs"]["timeout"] == 2.0, "a hung daemon must not hang the request"


@pytest.mark.parametrize(
    "failure",
    [
        FileNotFoundError("docker not installed"),
        OSError("permission denied"),
        subprocess.TimeoutExpired("docker info", 2.0),
    ],
    ids=["docker-binary-missing", "os-error", "daemon-hung"],
)
def test_an_unreachable_daemon_is_reported_unavailable_rather_than_raising(monkeypatch, failure):
    """A missing binary and a hung daemon are the same answer to the caller: no deploy.

    Raising here would turn Export-Only mode into a 500, which is precisely the
    distinction ``DOCKER_UNAVAILABLE`` exists to preserve.
    """
    def fake_run(cmd, **kwargs):
        raise failure

    monkeypatch.setattr(ds.subprocess, "run", fake_run)

    assert ds.check_docker_daemon() is False


def test_a_nonzero_docker_info_is_reported_unavailable(monkeypatch):
    monkeypatch.setattr(
        ds.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1)
    )

    assert ds.check_docker_daemon() is False


# ---------------------------------------------------------------------------
# deploy_local -- the daemon is down
# ---------------------------------------------------------------------------
def test_deploy_without_a_daemon_enters_export_only_mode_without_starting_anything(monkeypatch, tmp_path):
    monkeypatch.setattr(ds, "check_docker_daemon", lambda: False)

    def explode(*args, **kwargs):  # pragma: no cover - asserted by not being called
        raise AssertionError("no container may be launched when the daemon is unavailable")

    monkeypatch.setattr(ds.subprocess, "Popen", explode)

    # `get_deployment_status` probes http://localhost:<port>/actuator/health for real
    # when a session is not marked BUILDING. Without this the test silently depends on
    # the host: it passed only while nothing was deployed, and started failing as soon
    # as a generated service was running on port 8080 -- the probe found a healthy
    # container and reported HEALTHY for a session the daemon had refused.
    def refuse(*args, **kwargs):
        raise ds.requests.exceptions.ConnectionError("no daemon, nothing listening")

    monkeypatch.setattr(ds.requests, "get", refuse)

    session = ds.deploy_local(SESSION_ID, str(tmp_path))

    assert session.status == DeploymentStatus.DOCKER_UNAVAILABLE
    assert "Reintentar" in session.errorMessage
    assert session.startedAt is None
    assert ds.get_deployment_status(SESSION_ID).status == DeploymentStatus.DOCKER_UNAVAILABLE
    assert not ds.get_deployment_logs(SESSION_ID)


# ---------------------------------------------------------------------------
# deploy_local -- the normal path
# ---------------------------------------------------------------------------
def test_a_successful_deploy_is_only_called_healthy_after_actuator_says_up(monkeypatch, tmp_path):
    """The happy path, and the only path allowed to report HEALTHY."""
    monkeypatch.setattr(ds, "check_docker_daemon", lambda: True)

    seen = {}

    def fake_popen(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["cwd"] = kwargs.get("cwd")
        return _FakeProcess(0, ["Container order-db  Started", "Container order-api  Started"])

    monkeypatch.setattr(ds.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        ds,
        "run_smoke_test",
        lambda sid, port=18080, **kw: SmokeTestResult(
            passed=True,
            statusCode=200,
            statusPayload={"status": "UP"},
            latencyMs=42.0,
            testUrl=f"http://localhost:{port}/actuator/health",
            details="UP",
        ),
    )

    session = ds.deploy_local(SESSION_ID, str(tmp_path), host_port=18080)

    assert seen["cmd"] == ["docker", "compose", "-p", SESSION_ID, "up", "-d", "--no-build", "--pull", "never", "--wait", "--wait-timeout", "180"]
    assert seen["cwd"] == str(tmp_path), "compose must run inside the session workspace"
    assert session.status == DeploymentStatus.HEALTHY
    assert session.healthStatus == "UP"
    assert session.testUrl == "http://localhost:18080/actuator/health"

    logs = " | ".join(ds.get_deployment_logs(SESSION_ID))
    assert "Container order-db  Started" in logs, "compose stdout must reach the operator"
    assert "[HEALTHY]" in logs


def test_rebuild_is_forwarded_to_compose(monkeypatch, tmp_path):
    monkeypatch.setattr(ds, "check_docker_daemon", lambda: True)
    seen = {}

    def fake_popen(cmd, **kwargs):
        seen["cmd"] = cmd
        return _FakeProcess(0)

    monkeypatch.setattr(ds.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        ds, "run_smoke_test", lambda *a, **k: SmokeTestResult(passed=True, testUrl="u")
    )

    ds.deploy_local(SESSION_ID, str(tmp_path), rebuild=True)

    assert 'up' in seen['cmd'] and '--no-build' in seen['cmd']
    assert '--pull' in seen['cmd'] and 'never' in seen['cmd']


def test_the_deploy_returns_building_before_the_worker_finishes(monkeypatch, tmp_path):
    """``deploy_local`` is an *initiator*: the caller gets BUILDING, the thread does the work.

    Pinned because the API returns this object directly (``POST /devops/{id}/deploy``),
    and a synchronous implementation would hold the HTTP request open for the whole
    image build.
    """
    monkeypatch.setattr(ds, "check_docker_daemon", lambda: True)
    captured = {}

    class _CapturingThread:
        def __init__(self, target=None, daemon=None, **kwargs):
            captured["target"] = target

        def start(self):
            captured["started"] = True

    monkeypatch.setattr(ds.threading, "Thread", _CapturingThread)

    session = ds.deploy_local(SESSION_ID, str(tmp_path))

    assert session.status == DeploymentStatus.BUILDING
    assert captured["started"] is True, "the worker was never started"
    assert captured["target"] is not None


def test_blank_compose_output_lines_are_not_logged(monkeypatch, tmp_path):
    """Compose emits blank separators; they would render as empty rows in the log pane."""
    monkeypatch.setattr(ds, "check_docker_daemon", lambda: True)
    monkeypatch.setattr(ds.subprocess, "Popen", lambda cmd, **kw: _FakeProcess(0, ["", "  ", "real line"]))
    monkeypatch.setattr(ds, "run_smoke_test", lambda *a, **k: SmokeTestResult(passed=True, testUrl="u"))

    ds.deploy_local(SESSION_ID, str(tmp_path))

    assert ds.get_deployment_logs(SESSION_ID).count("") == 0
    assert "real line" in ds.get_deployment_logs(SESSION_ID)


# ---------------------------------------------------------------------------
# deploy_local -- the ways it fails
# ---------------------------------------------------------------------------
def test_a_compose_failure_carries_the_exit_code(monkeypatch, tmp_path):
    """The exit code is the one fact a support ticket needs; a generic string is not."""
    monkeypatch.setattr(ds, "check_docker_daemon", lambda: True)
    monkeypatch.setattr(ds.subprocess, "Popen", lambda cmd, **kw: _FakeProcess(17))

    session = ds.deploy_local(SESSION_ID, str(tmp_path))

    assert session.status == DeploymentStatus.FAILED
    assert "17" in session.errorMessage
    assert any("exit code 17" in line for line in ds.get_deployment_logs(SESSION_ID))


def test_a_container_that_never_becomes_healthy_is_failed_not_healthy(monkeypatch, tmp_path):
    """The compose exit code 0 only means "containers started", never "service works".

    This is the honesty rule of the whole module: a started-but-unhealthy API must not
    be reported as a successful deployment.
    """
    monkeypatch.setattr(ds, "check_docker_daemon", lambda: True)
    monkeypatch.setattr(ds.subprocess, "Popen", lambda cmd, **kw: _FakeProcess(0))
    monkeypatch.setattr(
        ds,
        "run_smoke_test",
        lambda *a, **k: SmokeTestResult(
            passed=False, statusCode=503, testUrl="u", details="timed out after 20 attempts"
        ),
    )

    session = ds.deploy_local(SESSION_ID, str(tmp_path))

    assert session.status == DeploymentStatus.FAILED
    assert session.healthStatus == 'UNKNOWN', "a failed smoke test must not claim confirmed health"
    assert "Smoke test failed" in session.errorMessage
    assert session.errorMessage.endswith("timed out after 20 attempts")


def test_an_exception_in_the_worker_marks_the_session_failed(monkeypatch, tmp_path):
    """An unexpected error must still resolve the session; a stuck BUILDING row is worse.

    The worker runs in a bare thread, so an escaping exception would otherwise die
    silently and leave the UI polling BUILDING forever.
    """
    monkeypatch.setattr(ds, "check_docker_daemon", lambda: True)

    def fake_popen(cmd, **kwargs):
        raise OSError("docker socket closed")

    monkeypatch.setattr(ds.subprocess, "Popen", fake_popen)

    session = ds.deploy_local(SESSION_ID, str(tmp_path))

    assert session.status == DeploymentStatus.FAILED
    assert "docker socket closed" in session.errorMessage
    assert any("[FAILED]" in line for line in ds.get_deployment_logs(SESSION_ID))


# ---------------------------------------------------------------------------
# run_smoke_test -- the readiness probe
# ---------------------------------------------------------------------------
def test_a_healthy_actuator_passes_the_smoke_test_and_updates_the_session(monkeypatch, tmp_path):
    monkeypatch.setattr(ds, "_active_deployments", {
        SESSION_ID: LocalDeploymentSession(sessionId=SESSION_ID, status=DeploymentStatus.RUNNING)
    })
    monkeypatch.setattr(ds.requests, "get", lambda url, **kw: _FakeResponse(200, {"status": "UP"}))
    monkeypatch.setattr(ds.time, "sleep", lambda s: None)

    result = ds.run_smoke_test(SESSION_ID, host_port=19090, max_retries=3)

    assert result.passed is True
    assert result.statusCode == 200
    assert result.testUrl == "http://localhost:19090/actuator/health"
    assert "UP" in result.details
    assert ds._active_deployments[SESSION_ID].status == DeploymentStatus.HEALTHY
    assert ds._active_deployments[SESSION_ID].healthStatus == "UP"


def test_a_missing_health_field_is_not_treated_as_up(monkeypatch):
    """A 200 with an unexpected body is not proof of health.

    The actuator contract is ``{"status": "UP"}``. Accepting any 200 would let a
    placeholder page or a proxy error page certify a broken deployment.
    """
    monkeypatch.setattr(ds.requests, "get", lambda url, **kw: _FakeResponse(200, {"status": "OUT_OF_SERVICE"}))
    monkeypatch.setattr(ds.time, "sleep", lambda s: None)

    result = ds.run_smoke_test(SESSION_ID, host_port=19091, max_retries=2)

    assert result.passed is False
    assert result.statusCode == 200, "preserve the actual HTTP code, without inventing success"


def test_a_non_json_body_degrades_to_the_raw_text_instead_of_crashing(monkeypatch):
    monkeypatch.setattr(
        ds.requests, "get", lambda url, **kw: _FakeResponse(200, text="<html>gateway</html>", raise_json=True)
    )
    monkeypatch.setattr(ds.time, "sleep", lambda s: None)

    result = ds.run_smoke_test(SESSION_ID, host_port=19092, max_retries=1)

    assert result.passed is False
    assert "1 attempts" in result.details


def test_an_unreachable_endpoint_is_retried_and_reported_as_a_timeout(monkeypatch):
    attempts = []

    def refuse(url, **kwargs):
        attempts.append(url)
        raise requests.ConnectionError("connection refused")

    monkeypatch.setattr(ds.requests, "get", refuse)
    monkeypatch.setattr(ds.time, "sleep", lambda s: None)

    result = ds.run_smoke_test(SESSION_ID, host_port=19093, max_retries=4)

    assert len(attempts) == 4, "the probe must retry; a container needs time to boot"
    assert result.passed is False
    assert result.statusCode == 0, "no HTTP response was received"
    assert "timed out after 4 attempts" in result.details


def test_a_smoke_test_passes_on_a_later_attempt_rather_than_the_first(monkeypatch):
    """Containers boot slowly; failing on the first refusal would mark working deploys FAILED."""
    responses = [
        requests.ConnectionError("not up yet"),
        _FakeResponse(503, {"status": "DOWN"}),
        _FakeResponse(200, {"status": "UP"}),
    ]

    def fake_get(url, **kwargs):
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(ds.requests, "get", fake_get)
    monkeypatch.setattr(ds.time, "sleep", lambda s: None)

    result = ds.run_smoke_test(SESSION_ID, host_port=19094, max_retries=5)

    assert result.passed is True
    assert responses == [], "the probe stopped before the endpoint became healthy"


# ---------------------------------------------------------------------------
# get_deployment_status
# ---------------------------------------------------------------------------
def test_a_building_session_is_returned_without_touching_the_network(monkeypatch):
    """While compose runs, the port is not listening yet -- probing it is pure latency."""
    monkeypatch.setattr(ds, "_active_deployments", {
        SESSION_ID: LocalDeploymentSession(sessionId=SESSION_ID, status=DeploymentStatus.BUILDING)
    })

    def explode(*args, **kwargs):  # pragma: no cover
        raise AssertionError("a BUILDING deployment must not be probed")

    monkeypatch.setattr(ds.requests, "get", explode)

    status = ds.get_deployment_status(SESSION_ID)

    assert status.status == DeploymentStatus.BUILDING


def test_a_container_started_outside_this_process_is_discovered(monkeypatch):
    """A container started outside this process must still be reported, not shown as IDLE.

    This replaces `test_an_unknown_session_with_a_live_endpoint_is_discovered_as_healthy`,
    which asserted the same intent through an unsafe implementation: it probed a bare
    `host_port` and, on a 200 UP, created a deployment record for whichever session was
    asked about. The port is a shared default, so ANY service on it satisfied EVERY
    session -- a loan-servicing session with no container reported HEALTHY because the
    help-desk container was running, and its 500s were then diagnosed as a container
    problem.

    The intent is kept and the attribution is fixed: an externally-started container is
    discovered by its `com.docker.compose.project` label, which compose sets to the session
    id. Discovery is now per-session, which is what "still be reported" requires.
    """
    monkeypatch.setattr(local_runtime, "inspect_session", lambda sid: LocalDeploymentSession(sessionId=sid, containerId='app555', hostPort=18081, status=DeploymentStatus.RUNNING))
    monkeypatch.setattr(ds.requests, "get", lambda url, **kw: _FakeResponse(200, {"status": "UP"}))

    status = ds.get_deployment_status(SESSION_ID)

    assert status.status == DeploymentStatus.HEALTHY
    assert status.healthStatus == "UP"
    assert status.containerId == "app555"
    assert status.hostPort == 18081, "the recovered container's own port, not a default"
    assert ds._active_deployments[SESSION_ID].status == DeploymentStatus.HEALTHY


def test_a_live_endpoint_belonging_to_another_session_is_not_this_session(monkeypatch):
    """The misattribution itself, as a test.

    Something answers on the port. It belongs to a different session. This session is not
    deployed, and saying otherwise is what made a wrong-payload failure look like a
    container failure.
    """
    monkeypatch.setattr(ds, "_containers_for_session", lambda sid: [])  # nothing for this session
    monkeypatch.setattr(ds.requests, "get", lambda url, **kw: _FakeResponse(200, {"status": "UP"}))

    status = ds.get_deployment_status(SESSION_ID)

    assert status.status != DeploymentStatus.HEALTHY
    assert status.containerId is None
    assert SESSION_ID not in ds._active_deployments


def test_an_existing_failed_session_is_cleared_when_the_endpoint_recovers(monkeypatch):
    """Recovery must erase the stale error, or the UI shows FAILED next to a healthy probe."""
    monkeypatch.setattr(ds, "_active_deployments", {
        SESSION_ID: LocalDeploymentSession(
            sessionId=SESSION_ID,
            status=DeploymentStatus.FAILED,
            errorMessage="Smoke test failed: timed out",
        )
    })
    monkeypatch.setattr(local_runtime, "inspect_session", lambda sid: LocalDeploymentSession(sessionId=sid, containerId='recovered', status=DeploymentStatus.RUNNING))
    monkeypatch.setattr(ds.requests, "get", lambda url, **kw: _FakeResponse(200, {"status": "UP"}))

    status = ds.get_deployment_status(SESSION_ID)

    assert status.status == DeploymentStatus.HEALTHY
    assert status.errorMessage is None


def test_an_unknown_session_with_no_endpoint_is_idle(monkeypatch):
    monkeypatch.setattr(ds.requests, "get", lambda url, **kw: _FakeResponse(503, {}))

    status = ds.get_deployment_status(SESSION_ID)

    assert status.status == DeploymentStatus.IDLE


def test_a_known_session_survives_an_unreachable_endpoint(monkeypatch):
    """The last known status must not be lost just because the probe failed."""
    monkeypatch.setattr(ds, "_active_deployments", {
        SESSION_ID: LocalDeploymentSession(sessionId=SESSION_ID, status=DeploymentStatus.RUNNING)
    })

    def refuse(url, **kwargs):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(local_runtime, "inspect_session", lambda sid: LocalDeploymentSession(sessionId=sid, containerId='owned', status=DeploymentStatus.RUNNING))
    monkeypatch.setattr(ds.requests, "get", refuse)

    status = ds.get_deployment_status(SESSION_ID)

    assert status.status == DeploymentStatus.DEGRADED


# ---------------------------------------------------------------------------
# stream_logs
# ---------------------------------------------------------------------------
def test_streaming_replays_history_before_live_lines():
    """A client that connects late must still see what happened; the UI has no other source."""
    ds._log_message(SESSION_ID, "first")
    ds._log_message(SESSION_ID, "second")

    stream = ds.stream_logs(SESSION_ID)

    assert next(stream) == 'id: 1\ndata: "first"\n\n'
    assert next(stream) == 'id: 2\ndata: "second"\n\n'
    stream.close()


def test_streaming_emits_a_keepalive_when_idle():
    """An idle SSE stream is closed by proxies; the keepalive comment is what keeps it open."""
    stream = ds.stream_logs("qe-idle-session")

    assert next(stream) == ": keep-alive\n\n"
    stream.close()


def test_streaming_delivers_a_line_logged_after_the_client_connected():
    stream = ds.stream_logs("qe-live-session")
    ds._log_message("qe-live-session", "compiling")

    assert next(stream) == 'id: 1\ndata: "compiling"\n\n'
    stream.close()


def test_streaming_a_never_seen_session_does_not_raise():
    """Opening the log pane before any deploy must not 500."""
    stream = ds.stream_logs("qe-unknown-session")

    assert next(stream) == ": keep-alive\n\n"
    stream.close()


# ---------------------------------------------------------------------------
# stop_deployment
# ---------------------------------------------------------------------------
def test_stopping_targets_owned_containers_and_records_the_stop(monkeypatch, tmp_path):
    monkeypatch.setattr(ds, "_active_deployments", {
        SESSION_ID: LocalDeploymentSession(sessionId=SESSION_ID, status=DeploymentStatus.HEALTHY)
    })
    seen = {}
    owned = [{'Id': 'owned-container', 'State': {'Running': True}}]
    monkeypatch.setattr('app.services.runtime_lifecycle.owned_resources', lambda *_: owned)

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        owned[0]['State']['Running'] = False
        seen["cwd"] = kwargs.get("cwd")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(ds.subprocess, "run", fake_run)

    session = ds.stop_deployment(SESSION_ID, str(tmp_path))

    assert seen["cmd"] == ["docker", "stop", '--time', '10', 'owned-container'], "stop must preserve volumes"
    assert seen["cwd"] is None, 'Identified containers do not depend on a mutable Compose file'
    assert session.status == DeploymentStatus.STOPPED
    assert any("[STOPPED]" in line for line in ds.get_deployment_logs(SESSION_ID))


def test_stopping_an_unknown_session_still_reports_stopped(monkeypatch, tmp_path):
    """Stop is idempotent from the operator's point of view: the desired state is reached."""
    monkeypatch.setattr(ds.subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0))

    session = ds.stop_deployment("qe-never-deployed", str(tmp_path))

    assert session.status == DeploymentStatus.STOPPED
    assert session.sessionId == "qe-never-deployed"


def test_a_failed_owned_container_stop_does_not_raise(monkeypatch, tmp_path):
    """Return a failed operation with its error; never invent STOPPED after timeout."""
    def explode(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 15.0)

    monkeypatch.setattr(ds.subprocess, "run", explode)
    monkeypatch.setattr('app.services.runtime_lifecycle.owned_resources', lambda *_:
                        [{'Id': 'owned-container', 'State': {'Running': True}}])

    session = ds.stop_deployment(SESSION_ID, str(tmp_path))

    assert session.status == DeploymentStatus.FAILED
    assert session.errorMessage


# ---------------------------------------------------------------------------
# log plumbing
# ---------------------------------------------------------------------------
def test_log_history_and_the_queue_stay_in_step():
    """History is broadcast independently: neither subscriber consumes the other's line."""
    ds._log_message(SESSION_ID, "only line")

    assert ds.get_deployment_logs(SESSION_ID) == ["only line"]
    first, second = ds.stream_logs(SESSION_ID), ds.stream_logs(SESSION_ID)
    assert next(first) == next(second) == 'id: 1\ndata: "only line"\n\n'
    first.close()
    second.close()


def test_logs_of_an_unknown_session_are_empty_not_an_error():
    assert ds.get_deployment_logs("qe-no-logs") == []


def test_a_log_queue_is_created_on_first_message():
    ds._log_message("qe-fresh", "hello")

    assert ds.get_deployment_logs("qe-fresh") == ['hello']
    ds._raw_log_history.clear()
    assert ds.get_deployment_logs("qe-fresh") == ['hello'], 'history must survive memory eviction'
