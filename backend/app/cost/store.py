"""The durable local cost store — the authoritative system of record (FR-005).

Every model call and every session aggregate is written here first. A telemetry
destination may be mirrored to, but it is never read back: the report reads this
store only, which is what makes the figures deterministic and offline (FR-006) and
makes an unreachable destination a non-event (SC-006).

Two invariants are enforced at the write boundary rather than left to callers:

* ``usage_known = False`` means the token counts and the cost are stored as
  ``NULL``, never ``0``. A zero would be indistinguishable from a genuinely cheap
  call and would bias the headline average downward.
* ``priced = False`` means the cost is ``NULL``. A missing price silently becoming
  zero would understate spend.

Writes are best-effort with respect to the *session*: a cost-store problem must
never break generation. Failures are counted rather than swallowed silently, so a
test can assert that nothing was suppressed.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings

_CALL_TABLE = "model_calls"
_SESSION_TABLE = "session_costs"

_lock = threading.Lock()
_failures: List[str] = []


def recording_failures() -> List[str]:
    """Reasons recording was suppressed. Empty means nothing was lost."""
    return list(_failures)


def _reset_failures() -> None:
    """Test hook: clear the suppressed-failure log."""
    _failures.clear()


def _resolve_path(path: Optional[str] = None) -> Path:
    raw = path or getattr(settings, "COST_STORE_PATH", "backend/cost_tracking.db")
    resolved = Path(raw)
    if not resolved.is_absolute():
        # Anchor to the repository root (the parent of backend/) so the path in
        # configuration stays relative and readable.
        resolved = Path(__file__).resolve().parents[3] / resolved
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


_CALL_COLUMNS = [
    "call_id", "session_id", "stage", "provider", "model", "timestamp",
    "latency_ms", "input_tokens", "cache_hit_input_tokens", "output_tokens",
    "usage_known", "cache_basis_known", "peak", "priced", "cost_usd", "pricing_basis",
]

_SESSION_COLUMNS = [
    "session_id", "spec_name", "terminal_status", "model_mode",
    "verification_fallback_used", "total_input_tokens", "total_output_tokens",
    "total_cost_usd", "duration_seconds", "model_calls_count",
    "usage_unknown_calls", "unpriced_calls", "cache_miss_assumed_calls", "updated_at",
]


def _connect(path: Optional[str] = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(_resolve_path(path)))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(path: Optional[str] = None) -> None:
    """Create the tables if they are absent. Idempotent."""
    with _lock, _connect(path) as conn:
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {_CALL_TABLE} (
                call_id TEXT PRIMARY KEY,
                session_id TEXT,
                stage TEXT,
                provider TEXT,
                model TEXT,
                timestamp TEXT,
                latency_ms INTEGER,
                input_tokens INTEGER,
                cache_hit_input_tokens INTEGER,
                output_tokens INTEGER,
                usage_known INTEGER,
                cache_basis_known INTEGER,
                peak INTEGER,
                priced INTEGER,
                cost_usd REAL,
                pricing_basis TEXT
            )"""
        )
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{_CALL_TABLE}_session ON {_CALL_TABLE} (session_id)"
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS {_SESSION_TABLE} (
                session_id TEXT PRIMARY KEY,
                spec_name TEXT,
                terminal_status TEXT,
                model_mode TEXT,
                verification_fallback_used INTEGER,
                total_input_tokens INTEGER,
                total_output_tokens INTEGER,
                total_cost_usd REAL,
                duration_seconds REAL,
                model_calls_count INTEGER,
                usage_unknown_calls INTEGER,
                unpriced_calls INTEGER,
                cache_miss_assumed_calls INTEGER,
                updated_at TEXT
            )"""
        )


def _normalise_call(record: Dict[str, Any]) -> Dict[str, Any]:
    """Apply the store's invariants to a call record before writing it.

    Unknown values become ``NULL``. This is the single place the rule is enforced,
    so no caller can accidentally write a zero that reads as a real measurement.
    """
    usage_known = bool(record.get("usage_known", False))
    priced = bool(record.get("priced", False))

    normalised = dict(record)
    normalised["usage_known"] = int(usage_known)
    normalised["priced"] = int(priced)
    normalised["cache_basis_known"] = int(bool(record.get("cache_basis_known", False)))
    normalised["peak"] = int(bool(record.get("peak", False)))

    if not usage_known:
        normalised["input_tokens"] = None
        normalised["output_tokens"] = None
        normalised["cache_hit_input_tokens"] = None
    if not (usage_known and priced):
        normalised["cost_usd"] = None

    for column in _CALL_COLUMNS:
        normalised.setdefault(column, None)
    return normalised


def write_call_record(record: Dict[str, Any], path: Optional[str] = None) -> bool:
    """Persist one call record. Returns True when it was written.

    Never raises: cost telemetry must not break a generation session. A failure is
    counted and retrievable through :func:`recording_failures`.
    """
    if not record.get("call_id"):
        # A record with no identity cannot be de-duplicated on re-run, and a
        # malformed record must not become a junk row that skews the call count.
        _failures.append("write_call_record: rejected a record with no call_id")
        return False
    try:
        ensure_schema(path)
        row = _normalise_call(record)
        payload = [row.get(column) for column in _CALL_COLUMNS]
        placeholders = ", ".join("?" for _ in _CALL_COLUMNS)
        with _lock, _connect(path) as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO {_CALL_TABLE} "
                f"({', '.join(_CALL_COLUMNS)}) VALUES ({placeholders})",
                payload,
            )
        return True
    except Exception as exc:  # pragma: no cover - defensive
        _failures.append(f"write_call_record: {type(exc).__name__}: {exc}")
        return False


def write_session_cost_record(record: Dict[str, Any], path: Optional[str] = None) -> bool:
    """Persist one session cost record. Idempotent — re-aggregation overwrites."""
    try:
        ensure_schema(path)
        row = dict(record)
        row["verification_fallback_used"] = int(bool(row.get("verification_fallback_used", False)))
        if not row.get("total_cost_usd") and row.get("total_cost_usd") != 0:
            row["total_cost_usd"] = None
        for column in _SESSION_COLUMNS:
            row.setdefault(column, None)
        payload = [row.get(column) for column in _SESSION_COLUMNS]
        placeholders = ", ".join("?" for _ in _SESSION_COLUMNS)
        with _lock, _connect(path) as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO {_SESSION_TABLE} "
                f"({', '.join(_SESSION_COLUMNS)}) VALUES ({placeholders})",
                payload,
            )
        return True
    except Exception as exc:  # pragma: no cover - defensive
        _failures.append(f"write_session_cost_record: {type(exc).__name__}: {exc}")
        return False


def _row_to_dict(row: sqlite3.Row, bool_columns: List[str]) -> Dict[str, Any]:
    result = dict(row)
    for column in bool_columns:
        if column in result and result[column] is not None:
            result[column] = bool(result[column])
    return result


_CALL_BOOLS = ["usage_known", "cache_basis_known", "peak", "priced"]
_SESSION_BOOLS = ["verification_fallback_used"]


def read_call_records(session_id: Optional[str] = None, path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Read call records, oldest first and deterministically ordered."""
    ensure_schema(path)
    with _lock, _connect(path) as conn:
        if session_id is None:
            cursor = conn.execute(f"SELECT * FROM {_CALL_TABLE} ORDER BY timestamp, call_id")
        else:
            cursor = conn.execute(
                f"SELECT * FROM {_CALL_TABLE} WHERE session_id = ? ORDER BY timestamp, call_id",
                (session_id,),
            )
        return [_row_to_dict(row, _CALL_BOOLS) for row in cursor.fetchall()]


def read_session_cost_record(session_id: str, path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    ensure_schema(path)
    with _lock, _connect(path) as conn:
        cursor = conn.execute(
            f"SELECT * FROM {_SESSION_TABLE} WHERE session_id = ?", (session_id,)
        )
        row = cursor.fetchone()
        return _row_to_dict(row, _SESSION_BOOLS) if row else None


def read_all_session_cost_records(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Read every session record, ordered by session identifier.

    The ordering is part of the report's determinism guarantee: insertion order
    must not be able to influence a printed figure (FR-006, SC-003).
    """
    ensure_schema(path)
    with _lock, _connect(path) as conn:
        cursor = conn.execute(f"SELECT * FROM {_SESSION_TABLE} ORDER BY session_id")
        return [_row_to_dict(row, _SESSION_BOOLS) for row in cursor.fetchall()]
