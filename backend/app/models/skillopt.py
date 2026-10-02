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
#: Feature 015: the evidence was too thin to conclude anything. This is the
#: EXPECTED outcome at the current task count, not a failure of the round.
DECISION_NO_MEASURABLE_CHANGE = "NO_MEASURABLE_CHANGE"
#: Feature 015: at least one skill measured below the evidence floor.
DECISION_REMOVED = "REMOVED"


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
    #: Feature 015: the contribution measurements taken this round, and the skills
    #: removed because of them. Each removal cites the measurement that caused it,
    #: which is what makes an eviction auditable rather than a deletion.
    measurements_json = Column(Text, nullable=True)
    removed_json = Column(Text, nullable=True)


def ensure_schema(bind=None) -> None:
    """Create the run table on the engine actually in use, and add missing columns.

    `create_all` at import time binds the engine resolved *then*, and it creates
    missing **tables** but never missing **columns**. Tests rebind ``SessionLocal``
    to a temporary database, and an existing database keeps its old shape forever
    -- the feature-015 columns below would simply be absent on any database created
    before them, and the first write naming one would fail at runtime.

    That is not hypothetical: it is exactly how feature 014's writes were silently
    swallowed, and how feature 015's own `task` label broke the corpus report with
    `no such column` against a real database while the suite stayed green. Missing
    columns are therefore added explicitly, mirroring ``models/diagnostics.py``.
    """
    target = bind if bind is not None else engine
    Base.metadata.create_all(bind=target)
    _add_missing_columns(target)


def _add_missing_columns(bind) -> None:
    """Add any column the model declares that the live table lacks."""
    from sqlalchemy import text

    table = SkillOptRun.__table__
    try:
        connection = bind.connect() if hasattr(bind, "connect") else bind
    except Exception:
        return
    try:
        rows = list(connection.execute(text(f"PRAGMA table_info({table.name})")))
        if not rows:
            return  # not SQLite, or the table did not appear — nothing to repair
        existing = {row[1] for row in rows}
        for column in table.columns:
            if column.name in existing or column.primary_key:
                continue
            column_type = column.type.compile(dialect=connection.dialect)
            connection.execute(text(
                f"ALTER TABLE {table.name} ADD COLUMN {column.name} {column_type}"
            ))
        connection.commit()
    except Exception:
        # Never fatal: a schema repair that fails must not stop a run being recorded.
        pass
    finally:
        if connection is not bind and hasattr(connection, "close"):
            connection.close()


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
    measurements: Optional[List[Dict[str, Any]]] = None,
    removed: Optional[List[str]] = None,
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
            measurements_json=(
                json.dumps(measurements, default=str) if measurements is not None else None
            ),
            removed_json=json.dumps(removed) if removed is not None else None,
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
                "measurements": (
                    json.loads(row.measurements_json) if row.measurements_json else []
                ),
                "removed": json.loads(row.removed_json) if row.removed_json else [],
            }
            for row in rows
        ]
    finally:
        db.close()
