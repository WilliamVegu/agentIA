"""Deployment status must describe a session's OWN container.

The DevOps tab reported HEALTHY / UP / PostgreSQL for a session that had no container at
all. `get_deployment_status` probed a fixed `localhost:8080` and, on a 200 UP, CREATED a
deployment record for whichever session was asked about. The port is a shared default, so
any service listening on it satisfied every session.

The consequence was a wrong diagnosis rather than a cosmetic bug: a loan-servicing session
with no endpoints on the running (help-desk) container returned 500 for `/api/borrowers`,
and the UI -- having been told the service was deployed and healthy -- reported "verifica
que el contenedor está en ejecución". The container was running. It belonged to a
different service.
"""
from unittest.mock import patch

import pytest

from app.models.devops import DeploymentStatus
from app.services import docker_service


@pytest.fixture(autouse=True)
def clean_registry(monkeypatch, tmp_path):
    """The registry is module-global; each test starts from empty."""
    saved = dict(docker_service._active_deployments)
    from app.config import settings
    from app.models.execution import ExecutionMode
    monkeypatch.setattr(settings, 'WORKSPACE_DIR', str(tmp_path))
    monkeypatch.setattr('app.services.execution_policy.execution_mode', lambda _: ExecutionMode.DOCKER)
    monkeypatch.setattr(docker_service, 'check_docker_daemon', lambda: True)
    monkeypatch.setattr('app.services.runtime_log_capture.ensure_capture', lambda _: None)
    docker_service._active_deployments.clear()
    yield
    docker_service._active_deployments.clear()
    docker_service._active_deployments.update(saved)


def test_a_session_with_no_container_is_not_reported_healthy():
    """The regression: a 200 UP on the shared port must not register a deployment."""
    with patch("app.services.docker_service.requests.get") as probe, \
         patch("app.services.local_runtime.inspect_session", return_value=None):
        probe.return_value.status_code = 200
        probe.return_value.json.return_value = {"status": "UP"}

        session = docker_service.get_deployment_status("session-with-no-container")

    assert session.status == DeploymentStatus.IDLE
    assert session.containerId is None
    assert session.healthStatus is None
    assert "session-with-no-container" not in docker_service._active_deployments, (
        "probing a port must never create a deployment record"
    )


def test_an_existing_record_is_probed_on_its_own_port():
    """Health updates belong to a record that exists, on the port it was deployed to."""
    session = docker_service.LocalDeploymentSession(
        sessionId="s1", containerId="abc123", status=DeploymentStatus.RUNNING, hostPort=9091,
    )
    docker_service._active_deployments["s1"] = session

    with patch("app.services.docker_service.requests.get") as probe, \
         patch("app.services.local_runtime.inspect_session", side_effect=lambda _: session.model_copy(deep=True)):
        probe.return_value.status_code = 200
        probe.return_value.json.return_value = {"status": "UP"}
        result = docker_service.get_deployment_status("s1")

    assert result.status == DeploymentStatus.HEALTHY
    assert result.healthStatus == "UP"
    assert "9091" in probe.call_args[0][0], "must probe the session's own port"


def test_state_is_recovered_from_the_compose_project_label():
    """A backend restart must not orphan running containers.

    The registry is in memory, so after a restart every running service reported IDLE while
    it was up. Docker already records the association: `docker compose` names the project
    after the session id.
    """
    rows = [
        {"id": "app111", "name": "loanservice", "ports": "0.0.0.0:9092->8080/tcp", "status": "Up"},
        {"id": "db222", "name": "loanservice-postgres", "ports": "0.0.0.0:5432->5432/tcp", "status": "Up"},
    ]
    inspected = docker_service.LocalDeploymentSession(sessionId='session-x', containerId='app111',
        databaseContainerId='db222', hostPort=9092, status=DeploymentStatus.RUNNING)
    with patch("app.services.local_runtime.inspect_session", side_effect=lambda _: inspected.model_copy(deep=True)), \
         patch("app.services.docker_service.requests.get") as probe:
        probe.return_value.status_code = 200
        probe.return_value.json.return_value = {"status": "UP"}
        session = docker_service.get_deployment_status("session-x")

    assert session.containerId == "app111", "the app container, not the database"
    assert session.databaseContainerId == "db222"
    assert session.hostPort == 9092
    assert session.status == DeploymentStatus.HEALTHY


def test_the_database_container_is_never_mistaken_for_the_service():
    """Only a database container running means the service is not up."""
    rows = [{"id": "db222", "name": "svc-postgres", "ports": "0.0.0.0:5432->5432/tcp", "status": "Up"}]
    inspected = docker_service.LocalDeploymentSession(sessionId='session-y', databaseContainerId='db222',
        status=DeploymentStatus.DEGRADED, healthStatus='DOWN')
    with patch("app.services.local_runtime.inspect_session", return_value=inspected):
        session = docker_service.get_deployment_status("session-y")

    assert session.status == DeploymentStatus.DEGRADED
    assert session.containerId is None


@pytest.mark.parametrize("ports,expected", [
    ("0.0.0.0:8080->8080/tcp", 8080),
    ("0.0.0.0:9092->8080/tcp", 9092),
    ("0.0.0.0:9092->8080/tcp, 0.0.0.0:5432->5432/tcp", 9092),
    ("8080/tcp", None),
    ("", None),
])
def test_host_port_is_read_from_the_published_mapping(ports, expected):
    assert docker_service._host_port_from_ports(ports) == expected


def test_an_unreachable_docker_degrades_to_not_deployed():
    """Recovery is read-only and best-effort: failure means "cannot establish", not an error."""
    with patch("app.services.docker_service.subprocess.run", side_effect=OSError("no docker")):
        assert docker_service._containers_for_session("anything") == []
