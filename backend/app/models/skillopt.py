"""The SkillOpt run record (feature 014, FR-008 / T004).

One row per iteration, written on **every** exit path including failure. A crashed
iteration that left no row is indistinguishable from one that never ran, and the
run log is the only place a rejected proposal survives — v1 has no rejected-edit
buffer, so the recorded edits are the sole evidence of what the reflector tried.

The table is created from the ORM metadata. Unlike features 011/012/013, which
added columns to the existing session table through an idempotent shim, this is a
new model, so ``create_all`` (which checks first) is sufficient.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, DateTime, Float, Integer, Text

from app.models.session import Base, SessionLocal, engine

#: Decision values. `NO_FAILURES` and `NO_SESSIONS` are distinct because one means
#: the skill is working and the other means there is nothing to learn from.
DECISION_ACCEPTED = "ACCEPTED"
DECISION_REJECTED = "REJECTED"
DECISION_NO_FAILURES = "NO_FAILURES"
DECISION_NO_SESSIONS = "NO_SESSIONS"
DECISION_ERROR = "ERROR"


class SkillOptRun(Base):
    __tablename__ = "skillopt_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    started_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    n_training = Column(Integer, nullable=True)
    n_held_out = Column(Integer, nullable=True)
    current_score = Column(Float, nullable=True)
    candidate_score = Column(Float, nullable=True)
    decision = Column(Text, nullable=True)
    edits_json = Column(Text, nullable=True)
    error = Column(Text, nullable=True)


def ensure_schema(bind=None) -> None:
    """Create the run table on the engine actually in use.

    `create_all` at import time binds the engine resolved *then*. Tests rebind
    ``SessionLocal`` to a temporary database, and a long-lived process may be
    pointed elsewhere, so the table is ensured on the session's own bind before any
    read or write. Idempotent (SQLAlchemy checks first).
    """
    Base.metadata.create_all(bind=bind if bind is not None else engine)


ensure_schema()


def start_run() -> datetime:
    """Timestamp for the beginning of an iteration."""
    return datetime.now(timezone.utc)


def write_run(
    *,
    started_at: Optional[datetime] = None,
    n_training: Optional[int] = None,
    n_held_out: Optional[int] = None,
    current_score: Optional[float] = None,
    candidate_score: Optional[float] = None,
    decision: Optional[str] = None,
    edits: Optional[List[Dict[str, Any]]] = None,
    error: Optional[str] = None,
) -> int:
    """Persist one iteration. Returns the row id, or -1 when logging failed.

    Never raises for the *caller's* benefit: a logging failure must not lose an
    iteration's outcome. The caller still reports the outcome it computed.
    """
    db = SessionLocal()
    try:
        ensure_schema(db.get_bind())
        row = SkillOptRun(
            started_at=started_at or datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            n_training=n_training,
            n_held_out=n_held_out,
            current_score=current_score,
            candidate_score=candidate_score,
            decision=decision,
            edits_json=json.dumps(edits, default=str) if edits is not None else None,
            error=error,
        )
        db.add(row)
        db.commit()
        return int(row.id)
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return -1
    finally:
        db.close()


def read_runs(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Read run records, newest first."""
    db = SessionLocal()
    try:
        ensure_schema(db.get_bind())
        query = db.query(SkillOptRun).order_by(SkillOptRun.id.desc())
        if limit:
            query = query.limit(limit)
        rows = query.all()
        return [
            {
                "id": row.id,
                "started_at": row.started_at,
                "completed_at": row.completed_at,
                "n_training": row.n_training,
                "n_held_out": row.n_held_out,
                "current_score": row.current_score,
                "candidate_score": row.candidate_score,
                "decision": row.decision,
                "edits": json.loads(row.edits_json) if row.edits_json else [],
                "error": row.error,
            }
            for row in rows
        ]
    finally:
        db.close()
