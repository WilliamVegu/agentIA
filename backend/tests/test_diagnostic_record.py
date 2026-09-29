"""The durable session diagnostic record (feature 015, US1).

Three requirements carry this file, and each closes a way the record could lie:

* **Determinism** — a record that drifts would let a later "improvement" be the
  instrument moving rather than the system.
* **Three states** — *evaluated and clean*, *evaluated with findings*, and *not
  evaluable* must never be conflated. An empty artifact set scores 100 with no
  findings, so unless it is flagged it is indistinguishable from success, and
  "nothing to evaluate" would be reported as "verified clean".
* **Exclusion of unverified sessions** — a build that fell back to a synthetic
  result must be marked, because counting it would reward changes that make
  verification less likely to run. This is the failure feature 012 exists for.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.models.diagnostics import (  # noqa: E402
    read_diagnostic_record,
    read_diagnostic_records,
    write_diagnostic_record,
)
from app.models.session import SessionLocal, engine  # noqa: E402
from app.services.conformance_diagnostics import diagnose  # noqa: E402
from tests.fixtures import fake_model as fm  # noqa: E402

CORPUS_DIR = REPO_ROOT / "backend" / "tests" / "fixtures" / "baseline_blueprints"
SESSION_IDS = ["t015-a", "t015-b", "t015-c", "t015-d"]


def _blueprint(name: str = "minimal") -> dict:
    return json.loads((CORPUS_DIR / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def clean_records():
    db = SessionLocal()
    try:
        from app.models.diagnostics import SessionDiagnosticRecord
        for sid in SESSION_IDS:
            db.query(SessionDiagnosticRecord).filter(
                SessionDiagnosticRecord.session_id == sid
            ).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        from app.models.diagnostics import SessionDiagnosticRecord
        for sid in SESSION_IDS:
            db.query(SessionDiagnosticRecord).filter(
                SessionDiagnosticRecord.session_id == sid
            ).delete()
        db.commit()
    finally:
        db.close()


def _write(session_id, report, **overrides):
    payload = dict(
        score=report.score,
        raw_penalty=report.raw_penalty,
        density=report.density,
        artifact_count=report.evaluated_artifact_count,
        evaluable=report.evaluable,
        counts_by_severity=report.counts_by_severity,
        rule_histogram=report.rule_histogram,
        findings=[v.to_dict() for v in report.violations],
    )
    payload.update(overrides)
    return write_diagnostic_record(session_id, **payload)


# ---------------------------------------------------------------------------
# T006 — the table is created on the engine actually in use
# ---------------------------------------------------------------------------
def test_a_write_succeeds_on_whatever_engine_the_session_is_bound_to():
    """Feature 014's run records were silently swallowed by getting this wrong:
    create_all bound the import-time engine, the suite rebound SessionLocal, and
    every write failed into a best-effort path that reported success."""
    report = diagnose(fm.compliant_artifacts("CONTROLLER", _blueprint()))

    assert _write("t015-a", report) is True, (
        "the write reported failure; the table was not created on the engine the "
        "session is actually bound to"
    )
    assert read_diagnostic_record("t015-a") is not None


# ---------------------------------------------------------------------------
# T007 — the record names the defect
# ---------------------------------------------------------------------------
def test_the_record_names_the_rule_the_artifact_and_the_severity():
    report = diagnose(fm.violating_artifacts("LAYER_ISOLATION", _blueprint()))
    _write("t015-a", report)

    record = read_diagnostic_record("t015-a")

    assert record["rule_histogram"], "the record carried no rule histogram"
    assert "PRINCIPLE_I_LAYER_ISOLATION" in record["rule_histogram"]
    findings = record["findings"]
    assert findings, "the record carried no findings"
    first = findings[0]
    for field in ("rule_id", "artifact_path", "severity"):
        assert first.get(field), f"a finding is missing {field}"


# ---------------------------------------------------------------------------
# T008 — determinism
# ---------------------------------------------------------------------------
def test_two_records_over_identical_artifacts_are_identical():
    blueprint = _blueprint()
    artifacts = fm.violating_artifacts("CONTRACT_IMMUTABILITY", blueprint)

    _write("t015-a", diagnose(artifacts))
    _write("t015-b", diagnose(artifacts))

    first = read_diagnostic_record("t015-a")
    second = read_diagnostic_record("t015-b")
    first.pop("session_id"), second.pop("session_id")
    first.pop("recorded_at"), second.pop("recorded_at")

    assert first == second, (
        "two records over byte-identical artifacts disagreed; a later improvement "
        "could not be told apart from the instrument drifting"
    )


# ---------------------------------------------------------------------------
# T009 — three states, never conflated
# ---------------------------------------------------------------------------
def test_nothing_to_evaluate_is_not_recorded_as_clean():
    report = diagnose({})

    assert report.evaluable is False, (
        "an artifact set with nothing in it reported as evaluable; an empty set "
        "scores 100 with no findings and would read as verified clean"
    )
    assert report.evaluated_artifact_count == 0


def test_a_clean_set_is_evaluable_and_scores_full():
    report = diagnose(fm.compliant_artifacts("CONTROLLER", _blueprint()))

    assert report.evaluable is True
    assert report.score == 100
    assert report.rule_histogram == {}


def test_a_set_with_findings_is_evaluable_and_flagged():
    report = diagnose(fm.violating_artifacts("LAYER_ISOLATION", _blueprint()))

    assert report.evaluable is True
    assert report.score < 100
    assert report.rule_histogram


def test_the_three_states_are_distinguishable_after_round_trip():
    _write("t015-a", diagnose({}))                                  # not evaluable
    _write("t015-b", diagnose(fm.compliant_artifacts("CONTROLLER", _blueprint())))
    _write("t015-c", diagnose(fm.violating_artifacts("LAYER_ISOLATION", _blueprint())))

    empty = read_diagnostic_record("t015-a")
    clean = read_diagnostic_record("t015-b")
    dirty = read_diagnostic_record("t015-c")

    assert empty["evaluable"] is False
    assert clean["evaluable"] is True and clean["rule_histogram"] == {}
    assert dirty["evaluable"] is True and dirty["rule_histogram"] != {}


# ---------------------------------------------------------------------------
# T010 — unverified sessions are marked
# ---------------------------------------------------------------------------
def test_an_unverified_session_is_marked_whatever_it_scored():
    report = diagnose(fm.compliant_artifacts("CONTROLLER", _blueprint()))
    _write("t015-a", report, unverified=True)

    record = read_diagnostic_record("t015-a")

    assert record["unverified"] is True, (
        "a session whose build fell back to a synthetic result was not marked; "
        "counting it would report a success the platform never achieved"
    )
    assert record["score"] == 100, "the marking must not alter the measured score"


def test_a_verified_session_is_not_marked():
    _write("t015-b", diagnose(fm.compliant_artifacts("CONTROLLER", _blueprint())))
    assert read_diagnostic_record("t015-b")["unverified"] is False


# ---------------------------------------------------------------------------
# T012 — per-stage attribution (FR-006, SC-002)
# ---------------------------------------------------------------------------
def test_findings_are_attributed_to_the_stage_that_introduced_them():
    from app.services.conformance_diagnostics import stage_attribution

    journal = {"entries": [
        {"stage": "SCAFFOLDER", "outcome": "CLEAN", "request_count": 1,
         "initial_verdict": {"passed": True, "violations": []}},
        {"stage": "CONTROLLER", "outcome": "CORRECTED", "request_count": 2,
         "initial_verdict": {"passed": False, "violations": [
             {"rule_id": "PRINCIPLE_I_LAYER_ISOLATION", "severity": "HIGH",
              "artifact_path": "NoteController.java", "message": "x"},
         ]}},
    ]}

    attributed = stage_attribution(journal)
    by_stage = {entry["stage"]: entry for entry in attributed}

    assert by_stage["SCAFFOLDER"]["rule_histogram"] == {}
    assert by_stage["CONTROLLER"]["rule_histogram"] == {"PRINCIPLE_I_LAYER_ISOLATION": 1}, (
        "the violation was not attributed to the stage that introduced it"
    )
    assert by_stage["CONTROLLER"]["counts_by_severity"] == {"HIGH": 1}


def test_attribution_reads_a_missing_or_empty_journal_without_raising():
    from app.services.conformance_diagnostics import stage_attribution

    assert stage_attribution(None) == []
    assert stage_attribution({}) == []
    assert stage_attribution({"entries": []}) == []
    # A malformed entry must not abort attribution of the well-formed ones.
    assert stage_attribution({"entries": ["not a mapping", {"stage": "DOMAIN"}]}) == [
        {"stage": "DOMAIN", "outcome": None, "request_count": None,
         "rule_histogram": {}, "counts_by_severity": {}, "passed": True}
    ]


# ---------------------------------------------------------------------------
# T014 — findings survive a run that fails after producing artifacts
# ---------------------------------------------------------------------------
def test_a_blocked_session_still_records_what_was_found():
    """A blocked session is the one most worth diagnosing, so the failing path
    must not be the path that skips recording."""
    from app.api.routes_session import _persist_diagnostics

    blueprint = _blueprint()
    final_state = {
        "status": "BLOCKED",
        "error": "tests failed after 5 attempts",
        "generated_files": fm.violating_artifacts("LAYER_ISOLATION", blueprint),
        "test_metrics": {"allPassed": False, "fallback_used": False},
        "generation_journal": {"entries": [
            {"stage": "CONTROLLER", "outcome": "EXHAUSTED", "request_count": 3,
             "initial_verdict": {"passed": False, "violations": [
                 {"rule_id": "PRINCIPLE_I_LAYER_ISOLATION", "severity": "HIGH",
                  "artifact_path": "NoteController.java", "message": "x"}]}},
        ]},
    }

    assert _persist_diagnostics("t015-d", final_state) is True

    record = read_diagnostic_record("t015-d")
    assert record is not None, "a blocked session produced no diagnostic record"
    assert "PRINCIPLE_I_LAYER_ISOLATION" in record["rule_histogram"], (
        "the findings produced before the failure were discarded"
    )
    assert record["stages"], "per-stage attribution was not recorded"
    assert any(s["stage"] == "CONTROLLER" for s in record["stages"])


def test_a_session_with_no_artifacts_records_as_not_evaluable_not_as_clean():
    """A blocked session that produced nothing must be distinguishable from one
    that produced nothing *wrong*."""
    from app.api.routes_session import _persist_diagnostics

    final_state = {"status": "BLOCKED", "error": "runtime unavailable",
                   "generated_files": {}, "test_metrics": {"fallback_used": True}}

    assert _persist_diagnostics("t015-c", final_state) is True

    record = read_diagnostic_record("t015-c")
    assert record["evaluable"] is False, "nothing to evaluate was recorded as clean"
    assert record["unverified"] is True, "a synthetic verification was not marked"
