"""A playground call must reach this session's own container, or not be sent.

The proxy is the platform's, so it is the last place that can tell whose service is
listening. It fell back to the shared default port 8080, and because
`LocalDeploymentSession.hostPort` DEFAULTS to 8080, that fallback fired for undeployed
sessions too. Their calls were delivered to another session's service and returned its 500
for an endpoint it does not have -- reported to the operator as "the service rejected the
record; check that the container is running". The container was running, and was not theirs.
"""
from unittest.mock import patch

import pytest

from app.services import playground_proxy


def test_an_undeployed_session_refuses_instead_of_using_the_shared_port():
    with patch("app.services.playground_proxy.get_deployment_status") as status:
        from app.models.devops import DeploymentStatus, LocalDeploymentSession

        # Exactly what an undeployed session returns: no container, and the field's own
        # 8080 default sitting there ready to be mistaken for a real published port.
        status.return_value = LocalDeploymentSession(
            sessionId="s", status=DeploymentStatus.IDLE, containerId=None, hostPort=8080
        )

        with pytest.raises(playground_proxy.PlaygroundProxyError) as refused:
            playground_proxy._resolve_port("s")

    message = str(refused.value)
    assert "no container of its own" in message
    assert "different session" in message, "the reason must name the misattribution"


def test_a_deployed_session_uses_its_own_published_port():
    with patch("app.services.playground_proxy.get_deployment_status") as status:
        from app.models.devops import DeploymentStatus, LocalDeploymentSession

        status.return_value = LocalDeploymentSession(
            sessionId="s", status=DeploymentStatus.HEALTHY,
            containerId="abc123", hostPort=9099,
        )

        assert playground_proxy._resolve_port("s") == 9099


def test_a_deployment_without_a_published_port_is_refused():
    """A container with no mapping is still not reachable by a guessed port."""
    with patch("app.services.playground_proxy.get_deployment_status") as status:
        from app.models.devops import DeploymentStatus, LocalDeploymentSession

        session = LocalDeploymentSession(
            sessionId="s", status=DeploymentStatus.RUNNING, containerId="abc123",
        )
        session.hostPort = 0  # falsy: nothing was published
        status.return_value = session

        with pytest.raises(playground_proxy.PlaygroundProxyError):
            playground_proxy._resolve_port("s")


def test_the_route_reports_a_refusal_as_400_not_500():
    """The caller asked for something the proxy will not do; that is a client error."""
    from fastapi.testclient import TestClient

    from app.main import app

    # Authenticate the test and resolve its workspace so the refusal handler is reached.
    # A 401/404 before forwarding would not exercise the intended contract.
    with patch('app.main.authenticated_user', return_value={'username': 'test'}), \
         patch('app.api.routes_devops._resolve_session_context', return_value=(None, None)), \
         patch("app.api.routes_devops.forward", side_effect=playground_proxy.PlaygroundProxyError(
        "this session has no container of its own (state: IDLE)."
    )):
        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/v1/devops/some-session/playground",
            json={"method": "GET", "path": "/api/v1/things"},
        )

    assert response.status_code == 400, (
        "a refused forward must not surface as a 500"
    )
