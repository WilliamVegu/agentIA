"""Best-effort mirror of cost records to a telemetry destination (FR-005).

This module is deliberately **not** on any critical path:

* It is never read back — the local store is the system of record, so nothing the
  report prints depends on this destination.
* Its absence is a non-event. The telemetry library may not be installed at all
  (it is not a current platform dependency), the destination may be unreachable,
  or it may reject a write. In every case the call silently does nothing, because
  a telemetry outage must not affect a generation session.

The mirror failing is therefore not a data-loss event. It is the designed
behaviour that makes the destination optional by construction.

**What "best-effort" was missing.** The destination being *unreachable* is listed above
as a non-event, but the transport did not behave that way. MLflow's own defaults are a
120-second HTTP timeout with 7 retries and exponential backoff -- its documentation puts
that at roughly 4 minutes -- so ``mlflow.start_run()`` against a dead tracking server
blocked the calling thread for minutes. That caller is ``RecordingChatClient.invoke``,
which sits on the critical path of **every** LLM call. A telemetry outage therefore stalled
generation sessions, so the mirror was neither off the critical path nor silent.
``_bound_the_transport`` pins the two environment variables MLflow reads on each request so
an unreachable destination fails fast instead. Both use ``setdefault``: an operator who
genuinely wants long retries against a healthy server can still ask for them.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from app.config import settings

# MLflow reads these from the environment on every request, not at import time.
# (See mlflow/environment_variables.py; the library's own guidance is to set exactly
# these two when the tracking server may be unreachable.)
_HTTP_TIMEOUT_ENV = "MLFLOW_HTTP_REQUEST_TIMEOUT"
_HTTP_MAX_RETRIES_ENV = "MLFLOW_HTTP_REQUEST_MAX_RETRIES"
_DEFAULT_HTTP_TIMEOUT_SECONDS = "5"
_DEFAULT_HTTP_MAX_RETRIES = "0"

_mirror_failures: List[str] = []


def _bound_the_transport() -> None:
    """Keep an unreachable destination from blocking the caller.

    Called before every send rather than at import, because the environment is the only
    knob MLflow offers and it is read per request.
    """
    os.environ.setdefault(_HTTP_TIMEOUT_ENV, _DEFAULT_HTTP_TIMEOUT_SECONDS)
    os.environ.setdefault(_HTTP_MAX_RETRIES_ENV, _DEFAULT_HTTP_MAX_RETRIES)


def mirror_failures() -> List[str]:
    """Reasons mirroring was skipped. Non-empty is expected on most hosts."""
    return list(_mirror_failures)


def _reset_failures() -> None:
    """Test hook."""
    _mirror_failures.clear()


def _tracking_uri() -> str:
    return getattr(settings, "MLFLOW_TRACKING_URI", "http://localhost:5000")


def _record(kind: str, payload: Dict[str, Any]) -> bool:
    """Send one record to the destination. Returns True only on a real write."""
    try:
        import mlflow  # imported lazily: absent by default, and that is fine
    except Exception as exc:
        _mirror_failures.append(f"{kind}: telemetry library unavailable ({type(exc).__name__})")
        return False

    try:
        _bound_the_transport()
        mlflow.set_tracking_uri(_tracking_uri())
        with mlflow.start_run(run_name=payload.get("session_id") or payload.get("call_id")):
            scalars = {
                key: value
                for key, value in payload.items()
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            }
            for key, value in scalars.items():
                mlflow.log_metric(key, float(value))
            # Identifiers only. A credential must never reach a telemetry
            # parameter -- the recording site sits directly beside the API key.
            safe_tags = {
                key: str(value)
                for key, value in payload.items()
                if key in ("session_id", "stage", "provider", "model", "pricing_basis")
                and value is not None
            }
            if safe_tags:
                mlflow.set_tags(safe_tags)
        return True
    except Exception as exc:
        _mirror_failures.append(f"{kind}: {type(exc).__name__}: {exc}")
        return False


def mirror_call_record(record: Dict[str, Any]) -> bool:
    return _record("call", record)


def mirror_session_cost_record(record: Dict[str, Any]) -> bool:
    return _record("session", record)
