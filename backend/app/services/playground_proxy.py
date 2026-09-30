"""Playground proxy: the browser talks to the platform, the platform talks to the container.

**Why this exists.** The Live Playground used to `fetch("http://localhost:8080/...")`
directly from the browser. That cannot work: the generated service ships no CORS
configuration, so every call is cross-origin and rejected. Measured against a real
deployment:

    OPTIONS /api/v1/customers   Origin: http://localhost:3000
    -> HTTP 403 "Invalid CORS request"

    GET /api/v1/customers       Origin: http://localhost:3000
    -> HTTP 200 but no Access-Control-Allow-Origin

`curl` worked throughout because it sends no `Origin`; a browser always does. The
playground therefore failed for *every* generated service in *every* browser, and the
operator saw "Failed to fetch" with Docker healthy underneath.

Proxying through the platform removes the cross-origin request entirely: the browser
calls its own origin, and the forwarding happens server-side. It also puts the call
somewhere the platform can guard it.

**This is a request-forwarding endpoint, so it is an SSRF surface, and the design
reflects that:**

* the **host is never taken from the request**. It is resolved from the session's own
  deployment record -- `127.0.0.1` and the port that deployment published. A caller
  cannot make the platform talk to an arbitrary address because it cannot name one.
* the **path must be a plain absolute path**. Anything carrying a scheme, an authority,
  a backslash, control characters, whitespace or a `..` segment is refused before a
  socket is opened. `//evil` is refused too: it is authority-shaped to some clients.
* the **method is an allow-list**. No `TRACE`, no `CONNECT`.
* **client headers are not forwarded.** `Content-Type` is set by the platform, so a
  caller cannot smuggle `Host`, `Authorization` or a hop-by-hop header into the
  container.
* the **response is bounded**: a timeout, and a body cap, because a container is not
  trusted to answer politely.

**Nothing here reports a success it did not observe.** A failure is returned as a
failure with its cause, which is the whole point of the exercise: the previous
client-side implementation fabricated a 200 when the fetch threw.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.services.docker_service import get_deployment_status

#: Methods the playground may forward. Deliberately small.
ALLOWED_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"})

#: A container is not trusted to answer promptly or briefly.
DEFAULT_TIMEOUT_SECONDS = 15.0
MAX_RESPONSE_BYTES = 256 * 1024

#: Characters that have no business in a path and are usually an escape attempt.
_FORBIDDEN_IN_PATH = re.compile(r"[\s\\\x00-\x1f\x7f]")

_REQUEST_MAPPING = re.compile(r'@RequestMapping\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']')


class PlaygroundProxyError(ValueError):
    """The request was refused before it was forwarded."""


def _resolve_port(session_id: str) -> int:
    """The port THIS session's deployment published. Never from the caller."""
    deployment = get_deployment_status(session_id)
    port = getattr(deployment, "hostPort", None)
    return int(port) if port else 8080


def normalise_path(path: str) -> str:
    """Validate a playground path, or refuse it.

    Returned with a leading slash and no trailing whitespace. Every rejection here is
    a reason a real proxy is attacked, so each is stated rather than collapsed into a
    generic 400 -- an operator debugging a legitimate call needs to know which rule
    fired.
    """
    if not isinstance(path, str) or not path.strip():
        raise PlaygroundProxyError("path is required")

    candidate = path.strip()

    if not candidate.startswith("/"):
        raise PlaygroundProxyError("path must start with '/'")
    if "://" in candidate:
        raise PlaygroundProxyError("path must not contain a scheme")
    if candidate.startswith("//"):
        raise PlaygroundProxyError("path must not begin with '//'")
    if "@" in candidate.split("?")[0]:
        raise PlaygroundProxyError("path must not contain credentials or a userinfo part")
    if _FORBIDDEN_IN_PATH.search(candidate):
        raise PlaygroundProxyError("path must not contain whitespace or control characters")

    # Normalise dot segments the way a server would, then refuse if any survived.
    # Checking the raw string is not enough: `/a/../../etc` has no literal `..` after
    # normalisation but `/a/%2e%2e/` does, so both the decoded and raw forms are
    # examined and the *result* is what must stay under the root.
    decoded = candidate.replace("%2e", ".").replace("%2E", ".")
    if any(segment == ".." for segment in decoded.split("?")[0].split("/")):
        raise PlaygroundProxyError("path must not contain a '..' segment")

    return candidate


def build_target_url(session_id: str, path: str) -> str:
    """The absolute URL to forward to. Host comes from the deployment, never the request."""
    port = _resolve_port(session_id)
    return f"http://127.0.0.1:{port}{normalise_path(path)}"


def forward(
    session_id: str,
    method: str,
    path: str,
    body: Optional[Any] = None,
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Forward one playground call and describe exactly what happened.

    Returns ``statusCode: None`` and a populated ``error`` when the call did not
    complete. There is no fabricated status: the previous client-side code answered
    a thrown fetch with a synthetic 200 and a plausible body, which is how a dead
    container looked healthy in the console.
    """
    verb = (method or "GET").strip().upper()
    if verb not in ALLOWED_METHODS:
        raise PlaygroundProxyError(
            f"method '{verb}' is not allowed; permitted: {', '.join(sorted(ALLOWED_METHODS))}"
        )

    url = build_target_url(session_id, path)
    started = time.perf_counter()

    try:
        response = requests.request(
            verb,
            url,
            json=body if verb in {"POST", "PUT", "PATCH"} and body is not None else None,
            headers={"Content-Type": "application/json", "Accept": "application/json, */*"},
            timeout=timeout,
            allow_redirects=False,
        )
    except requests.exceptions.Timeout:
        return {
            "statusCode": None, "url": url, "latencyMs": int((time.perf_counter() - started) * 1000),
            "body": None, "error": f"the service did not answer within {timeout:g}s",
        }
    except requests.exceptions.RequestException as exc:
        return {
            "statusCode": None, "url": url, "latencyMs": int((time.perf_counter() - started) * 1000),
            "body": None,
            "error": (
                f"{type(exc).__name__}: {exc}. Nada respondió en esa dirección -- comprueba "
                f"que el contenedor sigue desplegado (pestaña DevOps: 'Desplegar Localmente')."
            ),
        }

    latency_ms = int((time.perf_counter() - started) * 1000)
    raw = response.content or b""
    truncated = len(raw) > MAX_RESPONSE_BYTES
    text = raw[:MAX_RESPONSE_BYTES].decode("utf-8", errors="replace")

    try:
        parsed: Any = json.loads(text) if text.strip() else None
    except json.JSONDecodeError:
        parsed = None

    return {
        "statusCode": response.status_code,
        "url": url,
        "latencyMs": latency_ms,
        "contentType": response.headers.get("Content-Type", ""),
        "truncated": truncated,
        # `body` is the parsed form when the service answered JSON, else the raw text.
        # A caller should not have to guess which it got, so both are explicit.
        "body": parsed if parsed is not None else text,
        "bodyText": text,
        "error": None,
    }


def discover_resources(session_id: str, workspace_dir: str) -> List[str]:
    """The REST paths the generated service actually exposes.

    Derived from the generated controllers rather than assumed. The playground's CRUD
    form previously posted to a hardcoded ``/api/v1/orders``, so for any service whose
    blueprint had no ``Order`` entity -- which is every service with other entities --
    the form targeted a path that did not exist, and the old silent fallback hid the
    404. Reading the controllers is what makes the form correct for *this* service.
    """
    base = Path(workspace_dir)
    if not base.exists():
        return []

    found: List[str] = []
    for java_file in sorted(base.glob("src/main/java/**/controller/*.java")):
        try:
            source = java_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in _REQUEST_MAPPING.finditer(source):
            value = match.group(1).strip()
            if value.startswith("/") and value not in found:
                found.append(value)
    return found


def default_resource(session_id: str, workspace_dir: str) -> Optional[str]:
    """The collection path a CRUD form should default to: the first non-actuator one."""
    for path in discover_resources(session_id, workspace_dir):
        if not path.startswith("/actuator"):
            return path
    return None
