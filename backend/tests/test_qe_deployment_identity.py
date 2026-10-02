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
def clean_registry():
    """The registry is module-global; each test starts from empty."""
    saved = dict(docker_service._active_deployments)
    docker_service._active_deployments.clear()
    yield
    docker_service._active_deployments.clear()
    docker_service._active_deployments.update(saved)


def test_a_session_with_no_container_is_not_reported_healthy():
    """The regression: a 200 UP on the shared port must not register a deployment."""
    with patch("app.services.docker_service.requests.get") as probe, \
         patch("app.services.docker_service._containers_for_session", return_value=[]):
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

    with patch("app.services.docker_service.requests.get") as probe:
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
    with patch("app.services.docker_service._containers_for_session", return_value=rows), \
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
    with patch("app.services.docker_service._containers_for_session", return_value=rows):
        session = docker_service.get_deployment_status("session-y")

    assert session.status == DeploymentStatus.IDLE
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


# ---------------------------------------------------------------------------
# A port already published is a conflict the platform can name
# ---------------------------------------------------------------------------
def test_a_port_held_by_another_session_is_reported_before_anything_is_created(monkeypatch):
    """The failure this replaces, verbatim from the daemon:

        Error response from daemon: rootlessport listen tcp 0.0.0.0:8080: bind: address
        already in use

    Compose had already created the containers by then, so they sat in `Created` and the
    operator was told nothing about which deployment held the port -- or that the answer is
    to stop it or choose another. A second service cannot share 8080, and the platform knew
    which session owned it.
    """
    monkeypatch.setattr(
        "app.services.docker_service._port_holder",
        lambda port: {"name": "help-desk", "session": "other-session"},
    )
    monkeypatch.setattr("app.services.docker_service.check_docker_daemon", lambda: True)

    def _no_compose(*args, **kwargs):  # pragma: no cover - only runs on a regression
        raise AssertionError("compose was invoked despite a known port conflict")

    monkeypatch.setattr("app.services.docker_service.subprocess.Popen", _no_compose)

    session = docker_service.deploy_local("mine", "/tmp/does-not-matter", host_port=8080)

    assert session.status == DeploymentStatus.FAILED
    assert session.containerId is None
    assert "already published" in session.errorMessage
    assert "help-desk" in session.errorMessage
    assert "other-session" in session.errorMessage


def test_a_container_this_session_already_owns_is_not_a_conflict(monkeypatch):
    """A redeploy replaces its own container; it must not be refused as a conflict."""
    monkeypatch.setattr(
        "app.services.docker_service._port_holder",
        lambda port: {"name": "mine-1", "session": "mine"},
    )
    monkeypatch.setattr("app.services.docker_service.check_docker_daemon", lambda: True)

    session = docker_service.deploy_local("mine", "/tmp/does-not-matter", host_port=8080)

    assert session.status != DeploymentStatus.FAILED


@pytest.mark.parametrize("listing,port,expected", [
    ("help-desk\t0.0.0.0:8080->8080/tcp\tsess-a", 8080, "help-desk"),
    ("api\t0.0.0.0:9092->8080/tcp\tsess-b", 9092, "api"),
    # Exposed but NOT published: not a conflict, nothing is bound on the host.
    ("api\t8080/tcp\tsess-c", 8080, None),
    ("other\t0.0.0.0:9999->8080/tcp\tsess-d", 8080, None),
    ("", 8080, None),
])
def test_the_port_lookup_reads_the_published_side_only(monkeypatch, listing, port, expected):
    """`docker ps --filter publish=<port>` is rejected by some daemons and returns empty,
    which is indistinguishable from "no conflict". The listing format is stable."""
    class _Done:
        returncode = 0
        stdout = listing

    monkeypatch.setattr(
        "app.services.docker_service.subprocess.run", lambda *a, **k: _Done()
    )

    holder = docker_service._port_holder(port)

    assert (holder or {}).get("name") == expected


def test_a_daemon_that_rejects_the_listing_yields_no_conflict(monkeypatch):
    """Failing closed here would refuse every deployment on an unrecognised daemon."""
    class _Done:
        returncode = 1
        stdout = ""

    monkeypatch.setattr(
        "app.services.docker_service.subprocess.run", lambda *a, **k: _Done()
    )

    assert docker_service._port_holder(8080) is None
