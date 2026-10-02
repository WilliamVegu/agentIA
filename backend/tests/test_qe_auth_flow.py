"""QE coverage: the session authentication flow (``services/auth_service.py``).

Feature-level authentication arrived with the studio's server-side session: a middleware in
``app/main.py`` answers ``401`` for every request under ``/api/v1`` that does not carry a
valid ``agentia_session`` cookie. Nothing tested it.

That gap was visible in the worst possible way. When the middleware landed, **154 existing
tests failed at once** -- every API test in the suite, all of them with ``401``, none of them
wrong about what they were testing. A security control with no test of its own had silently
changed the contract of every endpoint in the product, and the suite could only report it as
a wall of unrelated failures. ``tests/auth_client.py`` provides the authenticated client that
unblocks those tests; *this* file tests the control itself.

The parts worth pinning are the ones where a mistake is a security hole rather than a bug:

* the guard covers **every** ``/api/v1`` route, and is not bypassable by a header;
* failing closed -- an unconfigured or short credential must refuse login (``503``), never
  accept a guess;
* the session cookie is ``HttpOnly``, ``SameSite=strict`` and scoped to ``/api/v1``;
* logout actually revokes, on the server, rather than only clearing the browser's copy;
* automatic local access is granted **only** to loopback callers (``auth/mvp``), which is
  what keeps "convenient on this machine" from meaning "open on every machine".
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from tests.auth_client import LOOPBACK_BASE_URL, LOOPBACK_CLIENT, PLAIN_TEST_CLIENT  # noqa: E402

from app.main import app  # noqa: E402
from app.services import auth_service  # noqa: E402

COOKIE = auth_service.COOKIE
PROTECTED = "/api/v1/sessions"


@pytest.fixture(autouse=True)
def isolated_auth_state(monkeypatch):
    """Swap the process-global stores for throwaway ones -- do not clear them.

    The session store is process-global by design, and so is the consequence of clearing
    it: every other test module builds its ``TestClient`` at *import* time, and that client
    already holds a session cookie by the time this file runs. ``_sessions.clear()``
    invalidated those cookies, so 52 tests in unrelated files started answering 401 in a
    full-suite run while passing perfectly in isolation.

    Replacing the objects instead isolates this file just as well -- the auth tests get an
    empty store -- and ``monkeypatch`` puts the originals back untouched, so nobody else's
    session is disturbed.
    """
    monkeypatch.setattr(auth_service, "_sessions", {})
    monkeypatch.setattr(auth_service, "_attempts", {})


@pytest.fixture
def loopback():
    """A client that looks like a browser on this machine, and nothing else."""
    return PLAIN_TEST_CLIENT(app, base_url=LOOPBACK_BASE_URL, client=LOOPBACK_CLIENT)


@pytest.fixture
def remote():
    """A client that looks like a browser somewhere else on the network."""
    return PLAIN_TEST_CLIENT(app, base_url="http://10.0.0.9:8000", client=("10.0.0.9", 51000))


# ---------------------------------------------------------------------------
# The guard itself
# ---------------------------------------------------------------------------
def test_a_request_without_a_session_is_refused(loopback):
    response = loopback.get(PROTECTED)

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"


def test_a_request_with_a_session_is_allowed(loopback):
    assert loopback.post("/api/v1/auth/mvp").status_code == 200

    assert loopback.get(PROTECTED).status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/sessions",
        "/api/v1/specifications",
        "/api/v1/orchestrator/pipeline/status",
    ],
)
def test_the_guard_covers_the_whole_api_surface(loopback, path):
    """One protected route proves nothing; the middleware must cover the prefix."""
    assert loopback.get(path).status_code == 401


def test_the_guard_cannot_be_bypassed_with_a_header(loopback):
    """A cookie is the only credential. No header may stand in for it."""
    for header in (
        {"X-Session-ID": "anything"},
        {"X-User": "mvp@localhost"},
        {"Authorization": "Bearer whatever"},
        {"X-Forwarded-For": "127.0.0.1"},
    ):
        assert loopback.get(PROTECTED, headers=header).status_code == 401, header


def test_a_preflight_request_is_not_guarded(loopback):
    """CORS preflight carries no credentials by definition; blocking it breaks the browser."""
    assert loopback.options(PROTECTED).status_code != 401


def test_a_route_outside_the_api_prefix_is_not_guarded(loopback):
    """The health probe must answer before anyone can log in."""
    assert loopback.get("/healthz").status_code == 200


# ---------------------------------------------------------------------------
# Automatic local access
# ---------------------------------------------------------------------------
def test_a_local_caller_enters_the_mvp_session_and_receives_a_cookie(loopback):
    response = loopback.post("/api/v1/auth/mvp")

    assert response.status_code == 200
    assert response.json()["accessMode"] == "mvp"
    assert COOKIE in loopback.cookies


def test_a_remote_caller_is_refused_automatic_access(remote):
    """The convenience is bound to the machine, not to the deployment."""
    response = remote.post("/api/v1/auth/mvp")

    assert response.status_code == 403
    assert COOKIE not in remote.cookies


def test_automatic_access_can_be_switched_off(loopback, monkeypatch):
    monkeypatch.setenv("STUDIO_AUTO_LOGIN", "false")

    assert loopback.post("/api/v1/auth/mvp").status_code == 403


# ---------------------------------------------------------------------------
# Credential login fails closed
# ---------------------------------------------------------------------------
def test_login_is_refused_when_no_credential_is_configured(loopback, monkeypatch):
    monkeypatch.delenv("STUDIO_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("STUDIO_USER_EMAIL", raising=False)

    response = loopback.post("/api/v1/auth/login", json={"email": "a@b.test", "password": "x" * 20})

    assert response.status_code == 503
    assert COOKIE not in loopback.cookies


def test_a_short_configured_credential_is_refused(loopback, monkeypatch):
    """A 6-character password is not a credential, and the endpoint must say so rather than
    accept it because it happens to match."""
    monkeypatch.setenv("STUDIO_USER_EMAIL", "operator@example.test")
    monkeypatch.setenv("STUDIO_ACCESS_TOKEN", "short")

    response = loopback.post(
        "/api/v1/auth/login", json={"email": "operator@example.test", "password": "short"}
    )

    assert response.status_code == 503


def test_correct_credentials_create_a_working_session(loopback, monkeypatch):
    monkeypatch.setenv("STUDIO_USER_EMAIL", "operator@example.test")
    monkeypatch.setenv("STUDIO_ACCESS_TOKEN", "a-sufficiently-long-token")

    response = loopback.post(
        "/api/v1/auth/login",
        json={"email": "operator@example.test", "password": "a-sufficiently-long-token"},
    )

    assert response.status_code == 200
    assert loopback.get(PROTECTED).status_code == 200


def test_a_wrong_password_is_refused(loopback, monkeypatch):
    monkeypatch.setenv("STUDIO_USER_EMAIL", "operator@example.test")
    monkeypatch.setenv("STUDIO_ACCESS_TOKEN", "a-sufficiently-long-token")

    response = loopback.post(
        "/api/v1/auth/login",
        json={"email": "operator@example.test", "password": "wrong-but-long-enough"},
    )

    assert response.status_code == 401


def test_an_unknown_email_is_refused(loopback, monkeypatch):
    monkeypatch.setenv("STUDIO_USER_EMAIL", "operator@example.test")
    monkeypatch.setenv("STUDIO_ACCESS_TOKEN", "a-sufficiently-long-token")

    response = loopback.post(
        "/api/v1/auth/login",
        json={"email": "intruder@example.test", "password": "a-sufficiently-long-token"},
    )

    assert response.status_code == 401


def test_the_email_comparison_is_case_insensitive(loopback, monkeypatch):
    """The operator types their address; the configured value is lower-cased."""
    monkeypatch.setenv("STUDIO_USER_EMAIL", "Operator@Example.Test")
    monkeypatch.setenv("STUDIO_ACCESS_TOKEN", "a-sufficiently-long-token")

    response = loopback.post(
        "/api/v1/auth/login",
        json={"email": "OPERATOR@EXAMPLE.TEST", "password": "a-sufficiently-long-token"},
    )

    assert response.status_code == 200


def test_repeated_failures_are_throttled(loopback, monkeypatch):
    """Brute force needs a cost. Ten attempts in a minute, then a refusal."""
    monkeypatch.setenv("STUDIO_USER_EMAIL", "operator@example.test")
    monkeypatch.setenv("STUDIO_ACCESS_TOKEN", "a-sufficiently-long-token")
    body = {"email": "operator@example.test", "password": "wrong-but-long-enough"}

    statuses = [loopback.post("/api/v1/auth/login", json=body).status_code for _ in range(12)]

    assert 429 in statuses, "the login endpoint never throttled"
    assert statuses[-1] == 429


def test_the_throttle_window_expires(loopback, monkeypatch):
    """Throttling must not lock the operator out permanently."""
    monkeypatch.setenv("STUDIO_USER_EMAIL", "operator@example.test")
    monkeypatch.setenv("STUDIO_ACCESS_TOKEN", "a-sufficiently-long-token")
    auth_service._attempts["127.0.0.1"] = [time.time() - 61] * 10

    response = loopback.post(
        "/api/v1/auth/login",
        json={"email": "operator@example.test", "password": "a-sufficiently-long-token"},
    )

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# The session cookie
# ---------------------------------------------------------------------------
def test_the_session_cookie_is_hardened(loopback):
    """HttpOnly keeps it away from scripts; SameSite=strict blocks it riding a cross-site
    request; the path keeps it off every route that does not need it."""
    response = loopback.post("/api/v1/auth/mvp")

    header = response.headers["set-cookie"]
    assert "httponly" in header.lower()
    assert "samesite=strict" in header.lower().replace(" ", "")
    assert "path=/api/v1" in header.lower().replace(" ", "")


def test_the_session_token_is_not_the_stored_form(loopback):
    """The store is keyed by a SHA-256 of the token, so a memory dump does not hand over
    usable credentials."""
    loopback.post("/api/v1/auth/mvp")
    token = loopback.cookies[COOKIE]

    assert token not in auth_service._sessions
    assert auth_service.authenticated_user(_RequestWith(token)) is not None


class _RequestWith:
    """The smallest thing ``authenticated_user`` needs: a cookie jar."""

    def __init__(self, token: str):
        self.cookies = {COOKIE: token}


def test_a_forged_token_is_not_accepted(loopback):
    loopback.cookies.set(COOKIE, "not-a-real-token", path="/api/v1")

    assert loopback.get(PROTECTED).status_code == 401


def test_reading_the_session_returns_the_operator(loopback):
    loopback.post("/api/v1/auth/mvp")

    body = loopback.get("/api/v1/auth/session").json()

    assert body["email"] == "mvp@localhost"
    assert body["accessMode"] == "mvp"


def test_reading_the_session_without_one_is_refused(loopback):
    assert loopback.get("/api/v1/auth/session").status_code == 401


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------
def test_logout_revokes_the_session_on_the_server(loopback):
    """Clearing the browser's copy is not revocation. If the token survived in the store,
    a captured cookie would keep working after the operator logged out."""
    loopback.post("/api/v1/auth/mvp")
    token = loopback.cookies[COOKIE]

    assert loopback.post("/api/v1/auth/logout").status_code == 200
    assert loopback.get("/api/v1/auth/session").status_code == 401
    assert auth_service.authenticated_user(_RequestWith(token)) is None


def test_logout_without_a_session_is_not_an_error(loopback):
    """Logging out twice, or from another tab, must not surface a failure."""
    assert loopback.post("/api/v1/auth/logout").status_code == 200


def test_one_logout_does_not_revoke_another_operators_session(loopback):
    """The session store is shared; revoking must remove exactly one entry."""
    loopback.post("/api/v1/auth/mvp")
    first_token = loopback.cookies[COOKIE]
    second = PLAIN_TEST_CLIENT(app, base_url=LOOPBACK_BASE_URL, client=LOOPBACK_CLIENT)
    second.post("/api/v1/auth/mvp")

    loopback.post("/api/v1/auth/logout")

    assert auth_service.authenticated_user(_RequestWith(second.cookies[COOKIE])) is not None
    assert auth_service.authenticated_user(_RequestWith(first_token)) is None
