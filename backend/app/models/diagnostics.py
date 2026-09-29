"""The durable session diagnostic record (feature 015, FR-001).

One row per session that reaches a terminal state, holding what was found wrong
with its artifacts. Feature 012 established that a session's verification outcome
must be recorded honestly; this records *what* was found, not just whether it
passed, so a failure is diagnosable after the fact without re-running a session
that may not reproduce.

**Why this is not in ``models/skillopt.py``.** That module holds optimization-run
records — what a skill-optimization round attempted. This holds what a *session*
produced. Folding the two together would put session telemetry behind a name that
implies an optimizer ran, which is wrong for every session that never will.

The table is created on the engine actually in use, not the one resolved at import
time. Feature 014's run records were silently swallowed by exactly that mistake:
``create_all`` bound the engine resolved at import, the test suite rebound
``SessionLocal`` to a temporary database, and the best-effort write path reported
success while logging nothing.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import Column, DateTime, Float, Integer, Text

from app.models.session import Base, SessionLocal, engine


class SessionDiagnosticRecord(Base):
    __tablename__ = "session_diagnostic_records"

    #: The session this describes. Natural key: exactly one record per session.
    session_id = Column(Text, primary_key=True)

    #: Which task the session ran, so the report can state distinct TASKS
    #: separately from sessions (FR-013). A session row itself carries no
    #: blueprint identity, and without this label repeated runs of one task would
    #: be indistinguishable from a larger sample -- which is exactly how
    #: pseudo-replication manufactures significance. NULL when the caller did not
    #: know it; such records are reported as untagged rather than guessed at.
    task = Column(Text, nullable=True)

    #: Raw weighted score. Size-dependent; not comparable across set sizes.
    score = Column(Integer, nullable=False)
    #: Unnormalised weighted penalty behind ``score``.
    raw_penalty = Column(Integer, nullable=False)
    #: Size-comparable measure: penalty per 100 artifacts (FR-007).
    #:
    #: **Retained for continuity, and NOT the decision metric.** It is a ratio, so
    #: it is lowered just as well by emitting more files as by fixing anything --
    #: the mirror image of the raw count's flaw. See ``new_penalty``.
    density = Column(Float, nullable=False)
    #: Absolute severity-weighted penalty of findings a frozen baseline does not
    #: account for. No denominator, so neither shrinking nor padding the artifact
    #: set can move it.
    #:
    #: **Nullable on purpose.** A record written before this column existed is
    #: back-filled as NULL, which means *not measured* -- and the contribution
    #: measure falls back to ``density`` for it. Defaulting to 0 would have made
    #: every historical session read as having no findings, i.e. as perfect, which
    #: is the opposite of what an unknown value should say.
    new_penalty = Column(Integer, nullable=True, default=None)
    #: How many artifacts were examined; the denominator behind ``density``.
    artifact_count = Column(Integer, nullable=False)

    #: False when no verdict could be produced. Distinct from "clean" (FR-004).
    evaluable = Column(Integer, nullable=False, default=1)
    #: True when the build fell back to a synthetic result. Excluded from
    #: evidence regardless of terminal status (FR-005).
    unverified = Column(Integer, nullable=False, default=0)

    counts_by_severity_json = Column(Text, nullable=True)
    rule_histogram_json = Column(Text, nullable=True)
    findings_json = Column(Text, nullable=True)
    stages_json = Column(Text, nullable=True)

    recorded_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


def ensure_schema(bind=None) -> None:
    """Create the table on the engine actually in use, and add any missing column.

    **``create_all`` creates missing *tables*; it never adds missing *columns*.**
    A table written by an earlier version of this module therefore keeps its old
    shape forever, and the first query naming a new column fails at runtime.

    That is not hypothetical: the ``task`` label was added to this model after the
    table had already been created, and the report crashed against the existing
    database with ``no such column``. The test suite could not catch it, because
    the test database is built fresh from the model every run — only running the
    real thing against a real database exposed it.

    So missing columns are added explicitly. The pattern mirrors the idempotent
    column shim features 011-013 used for the session table, for the same reason:
    an existing database must keep working without a manual migration.
    """
    target = bind if bind is not None else engine
    Base.metadata.create_all(bind=target)
    _add_missing_columns(target)


def _add_missing_columns(bind) -> None:
    """Add any column the model declares that the live table lacks."""
    from sqlalchemy import text

    table = SessionDiagnosticRecord.__table__
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
            if column.name in existing:
                continue
            if column.primary_key:
                continue  # cannot be added by ALTER; it is part of the original
            column_type = column.type.compile(dialect=connection.dialect)
            connection.execute(text(
                f"ALTER TABLE {table.name} ADD COLUMN {column.name} {column_type}"
            ))
        connection.commit()
    except Exception:
        # Never fatal: a schema repair that fails must not stop a session being
        # recorded. The write path reports its own failure separately.
        pass
    finally:
        if connection is not bind and hasattr(connection, "close"):
            connection.close()


def write_diagnostic_record(
    session_id: str,
    *,
    task: Optional[str] = None,
    score: int,
    raw_penalty: int,
    density: float,
    new_penalty: Optional[int] = None,
    artifact_count: int,
    evaluable: bool = True,
    unverified: bool = False,
    counts_by_severity: Optional[Dict[str, int]] = None,
    rule_histogram: Optional[Dict[str, int]] = None,
    findings: Optional[Sequence[Dict[str, Any]]] = None,
    stages: Optional[Sequence[Dict[str, Any]]] = None,
) -> bool:
    """Persist one record. Returns whether it was written.

    Never raises for the caller's benefit: a diagnostics failure must not prevent
    a session from reaching its own terminal state. The return value is how the
    failure stays visible instead of silent — which is the mistake feature 014
    made when its best-effort write path swallowed a missing table.
    """
    db = SessionLocal()
    try:
        ensure_schema(db.get_bind())
        row = db.query(SessionDiagnosticRecord).filter(
            SessionDiagnosticRecord.session_id == session_id
        ).one_or_none()
        if row is None:
            row = SessionDiagnosticRecord(session_id=session_id)
            db.add(row)

        row.task = task
        row.score = int(score)
        row.raw_penalty = int(raw_penalty)
        row.density = float(density)
        row.new_penalty = None if new_penalty is None else int(new_penalty)
        row.artifact_count = int(artifact_count)
        row.evaluable = 1 if evaluable else 0
        row.unverified = 1 if unverified else 0
        row.counts_by_severity_json = json.dumps(counts_by_severity or {}, sort_keys=True)
        row.rule_histogram_json = json.dumps(rule_histogram or {}, sort_keys=True)
        row.findings_json = json.dumps(list(findings or []), sort_keys=True, default=str)
        row.stages_json = json.dumps(list(stages or []), sort_keys=True, default=str)
        row.recorded_at = datetime.now(timezone.utc)

        db.commit()
        return True
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return False
    finally:
        db.close()


def read_diagnostic_record(session_id: str) -> Optional[Dict[str, Any]]:
    """Read one record, or None when nothing was recorded for that session."""
    db = SessionLocal()
    try:
        ensure_schema(db.get_bind())
        row = db.query(SessionDiagnosticRecord).filter(
            SessionDiagnosticRecord.session_id == session_id
        ).one_or_none()
        return _row_to_dict(row) if row is not None else None
    finally:
        db.close()


def read_diagnostic_records(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Read records, newest first."""
    db = SessionLocal()
    try:
        ensure_schema(db.get_bind())
        query = db.query(SessionDiagnosticRecord).order_by(
            SessionDiagnosticRecord.recorded_at.desc()
        )
        if limit:
            query = query.limit(limit)
        return [_row_to_dict(row) for row in query.all()]
    finally:
        db.close()


def _row_to_dict(row: SessionDiagnosticRecord) -> Dict[str, Any]:
    def _load(raw):
        if not raw:
            return {} if raw != "[]" else []
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return {}

    return {
        "session_id": row.session_id,
        "task": row.task,
        "score": row.score,
        "raw_penalty": row.raw_penalty,
        "density": row.density,
        "new_penalty": row.new_penalty,
        "artifact_count": row.artifact_count,
        "evaluable": bool(row.evaluable),
        "unverified": bool(row.unverified),
        "counts_by_severity": _load(row.counts_by_severity_json),
        "rule_histogram": _load(row.rule_histogram_json),
        "findings": _load(row.findings_json),
        "stages": _load(row.stages_json),
        "recorded_at": row.recorded_at,
    }
