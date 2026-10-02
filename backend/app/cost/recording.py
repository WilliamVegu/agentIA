"""The recording seam: a context, and a proxy that records every invocation.

Two halves, deliberately together because they only make sense as a pair:

* **The context** carries the stage name and session identifier. It is a
  ``contextvars.ContextVar`` rather than a module global because the platform runs
  sessions concurrently, and rather than an explicit parameter because that would
  change five model stage signatures and remain forgettable. The stage execution
  boundary (``stages/runner.py``) establishes it around client construction.
* **The proxy** wraps the client the model factory returns and records every
  invocation before returning its result.

The wrapping condition is **"is a recording context active"**, never **"is this a
test"**. That distinction is the whole point: a test-shaped condition would leave
every production call unrecorded while the suite stayed green. Direct factory calls
— which is what the existing factory-seam tests make — have no context and get the
unwrapped client, so those tests are untouched by construction.

Recording is best-effort with respect to the *session*: a recording failure must
never break generation. Failures are counted (see ``store.recording_failures``)
rather than swallowed silently, so a test can assert nothing was suppressed.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, Optional

from app.cost import pricing as pricing_mod
from app.cost import store as store_mod
from app.cost.mlflow_sink import mirror_call_record

_recording_context: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "cost_recording_context", default=None
)

_recording_failures: list = []


def recording_failures() -> list:
    """Reasons a call could not be recorded. Empty means nothing was lost."""
    return list(_recording_failures)


def _reset_failures() -> None:
    """Test hook."""
    _recording_failures.clear()


@contextmanager
def recording_context(session_id: Optional[str], stage: str) -> Iterator[None]:
    """Mark the enclosed work as belonging to ``session_id`` / ``stage``.

    Established by the stage execution boundary around client construction. Any
    client the factory builds inside this block is wrapped, so a future call site
    that knows nothing about recording is still covered.
    """
    token = _recording_context.set({"session_id": session_id, "stage": stage})
    try:
        yield
    finally:
        _recording_context.reset(token)


def active_context() -> Optional[Dict[str, Any]]:
    return _recording_context.get()


def is_recording_active() -> bool:
    """The wrapping condition. Keys on recording, not on test presence."""
    return _recording_context.get() is not None


def _extract_usage(response: Any) -> Dict[str, Any]:
    """Read token counts off a response, defensively.

    Returns ``usage_known = False`` when the response reports nothing — which is
    the behaviour of the default test double and of any provider that omits usage.
    That is recorded as an explicit marker, never as a zero: a zero is
    indistinguishable from a genuinely cheap call and would bias the average down.
    """
    usage = getattr(response, "usage_metadata", None)
    if not isinstance(usage, dict):
        return {"usage_known": False, "input_tokens": None, "output_tokens": None}

    input_tokens = usage.get("input_tokens")
    output_tokens = usage.get("output_tokens")
    if input_tokens is None or output_tokens is None:
        return {"usage_known": False, "input_tokens": None, "output_tokens": None}
    try:
        return {"usage_known": True, "input_tokens": int(input_tokens),
                "output_tokens": int(output_tokens)}
    except (TypeError, ValueError):
        return {"usage_known": False, "input_tokens": None, "output_tokens": None}


def build_call_record(
    provider: str,
    model: str,
    latency_ms: float,
    response: Any,
) -> Dict[str, Any]:
    """Assemble the record for one call. Pure with respect to the context."""
    context = active_context() or {}
    usage = _extract_usage(response)
    cache_hit = pricing_mod.cache_hit_tokens_from_response(response)
    timestamp = datetime.now(timezone.utc)

    priced = pricing_mod.price_call(
        provider=provider,
        model=model,
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        timestamp=timestamp,
        cache_hit_input_tokens=cache_hit,
    )

    return {
        "call_id": str(uuid.uuid4()),
        "session_id": context.get("session_id"),
        "stage": context.get("stage"),
        "provider": provider,
        "model": model,
        "timestamp": timestamp.isoformat(),
        "latency_ms": int(latency_ms),
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "cache_hit_input_tokens": cache_hit,
        "usage_known": usage["usage_known"],
        "cache_basis_known": priced["cache_basis_known"],
        "peak": priced["peak"],
        "priced": priced["priced"],
        "cost_usd": priced["cost_usd"],
        "pricing_basis": priced["pricing_basis"],
    }


def _record_call(provider: str, model: str, latency_ms: float, response: Any) -> None:
    """Persist one call. Never raises."""
    try:
        record = build_call_record(provider, model, latency_ms, response)
        store_mod.write_call_record(record)
        mirror_call_record(record)
    except Exception as exc:  # pragma: no cover - defensive
        _recording_failures.append(f"{type(exc).__name__}: {exc}")


class RecordingChatClient:
    """Wraps a chat client and records every invocation before returning.

    Attribute access is delegated, so the wrapped client's own surface (a test
    double's ``calls`` and ``call_count``, a real client's configuration) remains
    reachable and existing tests keep working.

    **Partial-interface handling.** A client may implement the synchronous entry
    point, the asynchronous one, or both; the platform's fake implements only the
    synchronous one. When the asynchronous entry point is called on such a client
    the wrapper **delegates to the synchronous implementation** and records the
    call, rather than raising. A silent pass-through was rejected: a call that
    happens is a call that costs, and an unrecorded one would be a second, quieter
    form of the silent-spend problem this feature exists to close.
    """

    def __init__(self, inner: Any, provider: str, model: str) -> None:
        # Set through __dict__ so __getattr__ delegation cannot recurse during
        # construction.
        self.__dict__["_inner"] = inner
        self.__dict__["_provider"] = provider
        self.__dict__["_model"] = model
        self.__dict__["_has_async"] = callable(getattr(inner, "ainvoke", None))

    def __getattr__(self, name: str) -> Any:
        return getattr(self.__dict__["_inner"], name)

    def invoke(self, request: Any, *args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        response = self._inner.invoke(request, *args, **kwargs)
        _record_call(self._provider, self._model,
                    (time.perf_counter() - started) * 1000.0, response)
        return response

    async def ainvoke(self, request: Any, *args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        if self.__dict__["_has_async"]:
            response = await self._inner.ainvoke(request, *args, **kwargs)
        else:
            # Delegate to the synchronous implementation without blocking the loop.
            response = await asyncio.to_thread(
                lambda: self._inner.invoke(request, *args, **kwargs)
            )
        _record_call(self._provider, self._model,
                     (time.perf_counter() - started) * 1000.0, response)
        return response
