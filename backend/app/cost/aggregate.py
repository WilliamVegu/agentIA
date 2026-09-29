"""Per-session cost aggregation (FR-002).

Rolls a session's call records into one cost record carrying what the session
cost, how long it took, how many calls it made, and what happened to it —
including whether its verification was real.

Three honesty rules, all inherited from the record contract:

* Unknown-usage calls contribute to **no total**. They are counted instead. A call
  with unknown usage is not a free call, and treating it as zero would bias the
  average downward.
* ``total_cost_usd`` is ``NULL`` when no call had a known cost, never ``0``.
* A session with **zero** call rows is a deterministic (offline) session, not a
  zero-cost model session. Recording it as the latter would drag the cost average
  toward zero and misstate the unit economics.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.cost import store as store_mod

#: Generation mode recorded for a session that made no model calls.
MODE_DETERMINISTIC = "DETERMINISTIC"
MODE_MODEL = "MODEL"


def aggregate_session(
    session_id: str,
    spec_name: Optional[str] = None,
    terminal_status: Optional[str] = None,
    model_mode: Optional[str] = None,
    verification_fallback_used: bool = False,
    duration_seconds: float = 0.0,
    path: Optional[str] = None,
) -> Dict[str, Any]:
    """Build and persist the cost record for one session. Idempotent.

    Re-aggregating a session overwrites its record rather than double-counting,
    because the row is keyed by session and totals are recomputed from the call
    rows rather than accumulated in place.
    """
    calls = store_mod.read_call_records(session_id, path=path)

    total_input = 0
    total_output = 0
    total_cost = 0.0
    any_known_cost = False
    usage_unknown = 0
    unpriced = 0
    cache_miss_assumed = 0

    for call in calls:
        if not call.get("usage_known"):
            usage_unknown += 1
            continue
        total_input += call.get("input_tokens") or 0
        total_output += call.get("output_tokens") or 0
        if call.get("priced") and call.get("cost_usd") is not None:
            total_cost += float(call["cost_usd"])
            any_known_cost = True
        else:
            unpriced += 1
        if not call.get("cache_basis_known"):
            cache_miss_assumed += 1

    # A session that made no model calls is deterministic, whatever the caller
    # passed. This is what keeps offline sessions out of a money average.
    resolved_mode = model_mode or (MODE_MODEL if calls else MODE_DETERMINISTIC)
    if not calls:
        resolved_mode = MODE_DETERMINISTIC

    record = {
        "session_id": session_id,
        "spec_name": spec_name,
        "terminal_status": terminal_status,
        "model_mode": resolved_mode,
        "verification_fallback_used": bool(verification_fallback_used),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cost_usd": total_cost if any_known_cost else None,
        "duration_seconds": float(duration_seconds or 0.0),
        "model_calls_count": len(calls),
        "usage_unknown_calls": usage_unknown,
        "unpriced_calls": unpriced,
        "cache_miss_assumed_calls": cache_miss_assumed,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    store_mod.write_session_cost_record(record, path=path)
    return record


def completed_for_costing(record: Dict[str, Any]) -> bool:
    """Whether a session may be counted in the headline cost average (FR-007).

    Every clause earns its place:

    * ``COMPLETED`` -- a blocked session is not a successful generation.
    * ``MODEL`` -- an offline session has no model spend; including it would drag
      the average toward zero and misstate the unit economics.
    * ``not verification_fallback_used`` -- a session whose verification was
      synthetic cannot be claimed as a successful generation, so it cannot be
      priced as one. This is feature 012's honesty constraint applied to money.
    * ``total_cost_usd is not None`` -- an unpriced session entering a money
      average would count as free.
    """
    return (
        record.get("terminal_status") == "COMPLETED"
        and record.get("model_mode") == MODE_MODEL
        and not record.get("verification_fallback_used", False)
        and record.get("total_cost_usd") is not None
    )
