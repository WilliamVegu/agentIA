"""Playground proxy guards.

**Why the proxy exists.** The Live Playground used to `fetch("http://localhost:8080/...")`
straight from the browser. That cannot work: the generated service ships no CORS
configuration, so every call is cross-origin and rejected. Measured against a real
deployment:

    OPTIONS /api/v1/customers  Origin: http://localhost:3000  -> 403 Invalid CORS request
    GET     /api/v1/customers  Origin: http://localhost:3000  -> 200, no ACAO header
    GET     /api/v1/customers  (no Origin, what curl sends)   -> 200

`curl` worked all along; the browser never could. The operator saw "Failed to fetch"
with Docker perfectly healthy, and concluded the deploy had failed.

**Why the tests are mostly about refusal.** Forwarding a caller-supplied path to a
container is an SSRF surface. The design puts the host out of reach -- it comes from
the session's deployment record, never the request -- so what remains to attack is the
path, and that is what these assert.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _a_session_that_owns_a_container(monkeypatch):
    """Give forwarding tests a session with its own container.

    `_resolve_port` now refuses a session that owns no container, because falling back to
    the shared default port delivered one session's calls to another session's service.
    These tests are about *forwarding* -- headers, truncation, timeouts, the verb -- so
    they need a reachable target and nothing more. The tests that assert targeting patch
    the deployment themselves and override this.
    """
    from app.models.devops import DeploymentStatus, LocalDeploymentSession
    from app.services import playground_proxy

    monkeypatch.setattr(
        playground_proxy,
        "get_deployment_status",
        lambda session_id: LocalDeploymentSession(
            sessionId=session_id,
            status=DeploymentStatus.HEALTHY,
            containerId="test-container",
            hostPort=8123,
        ),
    )


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.playground_proxy import (  # noqa: E402
    ALLOWED_METHODS,
    PlaygroundProxyError,
    discover_resources,
    forward,
    normalise_path,
)

#: Paths a proxy must refuse. Each is a real technique, not a hypothetical.
HOSTILE_PATHS = {
    "absolute_url": "http://169.254.169.254/latest/meta-data/",
    "scheme_relative": "//169.254.169.254/latest/meta-data/",
    "no_leading_slash": "api/v1/customers",
    "traversal_literal": "/a/../../etc/passwd",
    "traversal_encoded": "/a/%2e%2e/etc/passwd",
    "traversal_upper_encoded": "/a/%2E%2E/etc/passwd",
    "credentials": "/user:pass@evil.com/x",
    "whitespace": "/a b",
    "newline_injection": "/a\nHost: evil.com",
    "backslash": "/a\\..\\b",
    "empty": "",
    "blank": "   ",
}





@pytest.mark.parametrize("label", sorted(HOSTILE_PATHS))
def test_a_hostile_path_is_refused(label):
    with pytest.raises(PlaygroundProxyError):
        normalise_path(HOSTILE_PATHS[label])


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/customers",
        "/actuator/health",
        "/api/v1/customers/42",
        "/api/v1/customers?page=1&size=10",
        "/api/v1/tickets/1/status",
    ],
)
def test_an_ordinary_path_is_accepted_unchanged(path):
    assert normalise_path(path) == path


def test_a_disallowed_method_is_refused_before_any_socket_opens():
    for method in ("TRACE", "CONNECT", "OPTIONS", "BREW"):
        with pytest.raises(PlaygroundProxyError):
            forward("s", method, "/api/v1/customers")


def test_an_omitted_method_defaults_to_get(monkeypatch):
    """Documented rather than asserted-by-accident: `method` defaults to GET in the
    request model, so an empty value reaching the proxy means "not specified". It is
    normalised, not refused -- refusing it would reject the model's own default."""
    from app.services import playground_proxy

    captured = {}

    def capture(method, url, **kwargs):
        captured["method"] = method
        return _Response()

    monkeypatch.setattr(playground_proxy.requests, "request", capture)

    forward("s", "", "/api/v1/customers")

    assert captured["method"] == "GET"


def test_the_host_comes_from_the_deployment_not_the_request(monkeypatch):
    """The property that makes this endpoint safe: a caller cannot name a destination."""
    from app.services import playground_proxy

    monkeypatch.setattr(playground_proxy, "_resolve_port", lambda session_id: 8123)

    url = playground_proxy.build_target_url("session-a", "/api/v1/customers")

    assert url == "http://127.0.0.1:8123/api/v1/customers"


def test_the_port_is_read_per_session(monkeypatch):
    from app.services import playground_proxy

    monkeypatch.setattr(playground_proxy, "_resolve_port", lambda session_id: 9001 if session_id == "b" else 8000)

    assert ":9001/" in playground_proxy.build_target_url("b", "/x")
    assert ":8000/" in playground_proxy.build_target_url("a", "/x")


# ---------------------------------------------------------------------------
# Failure is reported, never fabricated
# ---------------------------------------------------------------------------
def test_an_unreachable_service_is_reported_as_such(monkeypatch):
    """The previous client-side code answered a thrown fetch with a synthetic 200."""
    from app.services import playground_proxy

    def explode(*args, **kwargs):
        import requests

        raise requests.exceptions.ConnectionError("connection refused")

    monkeypatch.setattr(playground_proxy.requests, "request", explode)

    result = forward("s", "GET", "/api/v1/customers")

    assert result["statusCode"] is None, "a status was invented for a call that never happened"
    assert result["error"] and "ConnectionError" in result["error"]
    assert result["body"] is None


def test_a_timeout_is_reported_as_such(monkeypatch):
    from app.services import playground_proxy

    def time_out(*args, **kwargs):
        import requests

        raise requests.exceptions.Timeout()

    monkeypatch.setattr(playground_proxy.requests, "request", time_out)

    result = forward("s", "GET", "/x", timeout=2.5)

    assert result["statusCode"] is None
    assert "2.5" in result["error"]


class _Response:
    def __init__(self, status_code=200, content=b"{}", headers=None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {"Content-Type": "application/json"}


def test_a_real_response_is_returned_with_its_status(monkeypatch):
    from app.services import playground_proxy

    monkeypatch.setattr(
        playground_proxy.requests, "request",
        lambda *a, **k: _Response(201, b'{"id": 7, "email": "a@b.com"}'),
    )

    result = forward("s", "POST", "/api/v1/customers", {"email": "a@b.com"})

    assert result["statusCode"] == 201
    assert result["body"] == {"id": 7, "email": "a@b.com"}
    assert result["error"] is None
    assert result["latencyMs"] is not None


def test_a_non_json_body_is_returned_as_text(monkeypatch):
    """A service may answer HTML or plain text; that must not be a crash."""
    from app.services import playground_proxy

    monkeypatch.setattr(
        playground_proxy.requests, "request",
        lambda *a, **k: _Response(200, b"<html>nope</html>", {"Content-Type": "text/html"}),
    )

    result = forward("s", "GET", "/x")

    assert result["statusCode"] == 200
    assert result["body"] == "<html>nope</html>"


def test_an_oversized_response_is_truncated(monkeypatch):
    from app.services import playground_proxy

    huge = b"x" * (playground_proxy.MAX_RESPONSE_BYTES + 5000)
    monkeypatch.setattr(playground_proxy.requests, "request", lambda *a, **k: _Response(200, huge))

    result = forward("s", "GET", "/x")

    assert result["truncated"] is True
    assert len(result["bodyText"]) == playground_proxy.MAX_RESPONSE_BYTES


def test_client_headers_are_not_forwarded(monkeypatch):
    """A caller must not be able to smuggle Host or Authorization into the container."""
    from app.services import playground_proxy

    seen = {}

    def capture(method, url, **kwargs):
        seen.update(kwargs)
        return _Response()

    monkeypatch.setattr(playground_proxy.requests, "request", capture)

    forward("s", "GET", "/api/v1/customers")

    assert set(seen["headers"]) == {"Content-Type", "Accept"}, (
        "the proxy forwards headers it chose, not headers the caller chose"
    )
    assert seen["allow_redirects"] is False, "a redirect could send the call off-target"


# ---------------------------------------------------------------------------
# Resource discovery replaces the hardcoded /api/v1/orders
# ---------------------------------------------------------------------------
def test_resources_are_read_from_the_generated_controllers(tmp_path):
    """The real deployment exposed /api/v1/customers and /api/v1/tickets.

    The CRUD form posted to a hardcoded /api/v1/orders, so for any service whose
    blueprint had no Order entity it targeted a path that did not exist -- and the
    silent fallback of the day turned that 404 into a green "201 CREATED" in the log.
    """
    controller = tmp_path / "src/main/java/com/corp/helpdesk/controller/CustomerController.java"
    controller.parent.mkdir(parents=True)
    controller.write_text(
        'package com.corp.helpdesk.controller;\n'
        '@RestController\n@RequestMapping("/api/v1/customers")\n'
        'public class CustomerController {\n'
        '  @GetMapping("/{id}") public Object get() { return null; }\n'
        '}\n',
        encoding="utf-8",
    )

    assert discover_resources("s", str(tmp_path)) == ["/api/v1/customers"]


def test_no_controllers_means_no_resources_rather_than_a_guess(tmp_path):
    assert discover_resources("s", str(tmp_path)) == []


def test_a_missing_workspace_is_not_an_error():
    assert discover_resources("s", "/nonexistent/workspace") == []
