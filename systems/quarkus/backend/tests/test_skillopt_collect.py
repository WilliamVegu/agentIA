"""Collector tests (feature 014, T011 / US2).

The collector reads recorded sessions and classifies them. Two distinctions it
makes are load-bearing:

* **"no failures" is not "no sessions".** The first means the skill is working; the
  second means there is nothing to learn from. Collapsing them would make the
  orchestrator call a model with an empty failure set and apply whatever it
  invented.
* **A fallback-marked session is a failure**, however its terminal status reads.
  Feature 012 established that a synthetic verification is not a success, and the
  skill is being asked to prevent *real* build failures.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.models.session import (  # noqa: E402
    GenerationSessionDB,
    SessionLocal,
    SessionPhase,
    SessionStatus,
)
import json  # noqa: E402

from scripts.skillopt.collect import (  # noqa: E402
    COLLECTION_NO_FAILURES,
    COLLECTION_NO_SESSIONS,
    COLLECTION_OK,
    collect_outcomes,
)

SESSION_IDS = ["t011-a", "t011-b", "t011-c"]


@pytest.fixture
def seeded_sessions():
    db = SessionLocal()
    try:
        for sid in SESSION_IDS:
            db.query(GenerationSessionDB).filter(GenerationSessionDB.id == sid).delete()
        db.commit()
    finally:
        db.close()
    yield SESSION_IDS
    db = SessionLocal()
    try:
        for sid in SESSION_IDS:
            db.query(GenerationSessionDB).filter(GenerationSessionDB.id == sid).delete()
        db.commit()
    finally:
        db.close()


def _add(session_id, status, *, fallback=False, all_passed=True, provenance=None):
    db = SessionLocal()
    try:
        db.add(GenerationSessionDB(
            id=session_id,
            spec_id=f"spec-{session_id}",
            spec_name="notes",
            status=status,
            phase=SessionPhase.VERIFIED if status == SessionStatus.COMPLETED else SessionPhase.FAILED,
            verification_metrics_json=json.dumps({
                "allPassed": all_passed, "fallback_used": fallback,
                "fallback_reason": "synthetic" if fallback else None,
            }),
            artifact_provenance_json=json.dumps(provenance or []),
        ))
        db.commit()
    finally:
        db.close()


PROVENANCE = [
    {"artifact_path": "src/main/java/com/corp/notes/model/entity/Note.java"},
    {"artifact_path": "pom.xml"},
]


def test_collects_one_record_per_session_with_the_required_fields(seeded_sessions):
    _add("t011-a", SessionStatus.COMPLETED, provenance=PROVENANCE)
    _add("t011-b", SessionStatus.BLOCKED)

    result = collect_outcomes(limit=10, session_ids=SESSION_IDS)

    assert result["status"] == COLLECTION_OK
    by_id = {record["session_id"]: record for record in result["records"]}
    assert set(by_id) == {"t011-a", "t011-b"}
    for field in ("spec_id", "artifact_paths", "build_exit_code",
                  "terminal_status", "verification_fallback_used"):
        assert field in by_id["t011-a"], f"the collected record is missing {field}"
    assert by_id["t011-a"]["artifact_paths"] == [
        "src/main/java/com/corp/notes/model/entity/Note.java", "pom.xml"
    ]
    assert by_id["t011-a"]["terminal_status"] == "COMPLETED"


def test_no_sessions_is_distinct_from_no_failures(seeded_sessions):
    empty = collect_outcomes(limit=10, session_ids=SESSION_IDS)
    assert empty["status"] == COLLECTION_NO_SESSIONS
    assert empty["records"] == []

    _add("t011-a", SessionStatus.COMPLETED)

    healthy = collect_outcomes(limit=10, session_ids=SESSION_IDS)
    assert healthy["status"] == COLLECTION_NO_FAILURES, (
        "all-success sessions were not distinguished from an empty session set"
    )
    assert healthy["failures"] == []


def test_a_fallback_marked_session_is_a_failure_however_its_status_reads(seeded_sessions):
    """A synthetic verification is not a success (feature 012)."""
    _add("t011-a", SessionStatus.COMPLETED, fallback=True, all_passed=True)

    result = collect_outcomes(limit=10, session_ids=SESSION_IDS)

    assert result["status"] == COLLECTION_OK
    assert len(result["failures"]) == 1
    assert result["failures"][0]["session_id"] == "t011-a"
    assert result["failures"][0]["verification_fallback_used"] is True


def test_a_failed_build_is_a_failure(seeded_sessions):
    _add("t011-a", SessionStatus.COMPLETED, all_passed=False)
    result = collect_outcomes(limit=10, session_ids=SESSION_IDS)

    assert result["status"] == COLLECTION_OK
    assert len(result["failures"]) == 1
    assert result["failures"][0]["build_exit_code"] != 0


def test_collection_order_is_deterministic(seeded_sessions):
    _add("t011-a", SessionStatus.BLOCKED)
    _add("t011-b", SessionStatus.BLOCKED)
    _add("t011-c", SessionStatus.BLOCKED)

    first = [r["session_id"] for r in collect_outcomes(limit=10, session_ids=SESSION_IDS)["records"]]
    second = [r["session_id"] for r in collect_outcomes(limit=10, session_ids=SESSION_IDS)["records"]]

    assert first == second
    assert first == sorted(first), "collection order is not deterministic"


def test_the_limit_selects_a_stable_window(seeded_sessions):
    for sid, status in zip(SESSION_IDS, [SessionStatus.BLOCKED] * 3):
        _add(sid, status)

    result = collect_outcomes(limit=2, session_ids=SESSION_IDS)

    assert len(result["records"]) == 2
