"""An authenticated ``TestClient``, because every API endpoint now requires a session.

The studio gained server-side authentication: a middleware in ``app/main.py`` answers
``401`` for anything under ``/api/v1`` without a valid ``agentia_session`` cookie. That is
the right behaviour for the product and it silently invalidated 150-odd existing tests,
none of which authenticated -- they were written before there was anything to authenticate
against.

The repair is deliberately **not** a bypass. ``AuthenticatedTestClient`` reaches the real
``POST /api/v1/auth/mvp`` endpoint and keeps the cookie it returns, so tests exercise the
real middleware, the real session store and the real cookie path. It only arranges for the
request to look like what it is: a browser on the same machine.

Two details make that work, and both matter:

* ``client=("127.0.0.1", ...)`` -- the automatic local access is granted only to loopback
  callers (``auth_service._local_host``). TestClient's default address is the literal
  string ``"testclient"``, which is not a host at all, so the auto-login refuses it.
* ``base_url="http://127.0.0.1:8000"`` -- the guard also checks ``request.url.hostname``.

Installation happens at import of ``conftest.py``, which pytest loads *before* collecting
test modules. That timing is the whole trick: the test modules do
``from fastapi.testclient import TestClient`` at module level, so patching the class first
means they receive this one, and the 26 existing call sites need no edit at all.

``PLAIN_TEST_CLIENT`` is the escape hatch. Anything that needs to observe *unauthenticated*
behaviour -- the 401 itself, logout, the login endpoint -- must use it explicitly, so that
"this test is about the absence of a session" is a visible decision rather than an accident
of shared fixtures.
"""

from __future__ import annotations

from typing import Any, Tuple

from starlette.testclient import TestClient

#: The unpatched client. Use it for tests whose subject *is* the absence of a session.
PLAIN_TEST_CLIENT = TestClient

LOOPBACK_CLIENT: Tuple[str, int] = ("127.0.0.1", 50000)
LOOPBACK_BASE_URL = "http://127.0.0.1:8000"


class AuthenticatedTestClient(TestClient):
    """A ``TestClient`` that has already entered the local MVP session.

    Construction performs the login, so a test can simply use ``client.get(...)`` and get
    the behaviour of an authenticated operator. A failed login is swallowed rather than
    raised: some tests construct a client only to exercise a public route, and the auth
    endpoint being unavailable must not turn that into an error at construction time.
    """

    def __init__(self, app: Any, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("base_url", LOOPBACK_BASE_URL)
        kwargs.setdefault("client", LOOPBACK_CLIENT)
        super().__init__(app, *args, **kwargs)
        try:
            self.post("/api/v1/auth/mvp")
        except Exception:  # pragma: no cover - construction must never explode
            pass


def install_authenticated_default() -> None:
    """Make ``TestClient(...)`` mean the authenticated client, for every importer.

    Both module paths are patched because ``fastapi.testclient`` re-exports the Starlette
    class: whichever the test module imports, it must find the same object.
    """
    import starlette.testclient

    starlette.testclient.TestClient = AuthenticatedTestClient
    try:
        import fastapi.testclient

        fastapi.testclient.TestClient = AuthenticatedTestClient
    except Exception:  # pragma: no cover - fastapi always present in this suite
        pass
