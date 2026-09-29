"""The corpus report (feature 015, US2).

The report exists to state a number the platform currently cannot state. Three
contracts keep it honest, and each closes a way it could mislead:

* **Excluded sessions contribute to nothing.** A build that fell back to a
  synthetic result is not a success. Averaging it in would report achievement the
  platform never had -- the failure feature 012 exists to prevent.
* **"No data" is not zero.** An empty store must produce *no data*, never a 0%
  success rate and never a cost of zero. They are different findings and a reader
  acts on them differently.
* **Sessions are not tasks.** Running one task ten times is one task. Presenting
  it as ten observations is pseudo-replication, and it is how a corpus of five
  gets described as if it were fifty.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.corpus_report import build_report, render_report  # noqa: E402


def record(session_id, *, task="minimal", score=100, density=0.0, evaluable=True,
           unverified=False, stages=None):
    return {
        "session_id": session_id, "task": task, "score": score, "density": density,
        "evaluable": evaluable, "unverified": unverified, "artifact_count": 6,
        "raw_penalty": 100 - score, "rule_histogram": {},
        "stages": stages or [],
    }


# ---------------------------------------------------------------------------
# T015 — the population and its exclusions
# ---------------------------------------------------------------------------
def test_the_report_states_the_population_and_every_exclusion_with_its_reason():
    records = [
        record("a"), record("b"),
        record("c", unverified=True),      # synthetic build
        record("d", evaluable=False),      # nothing to evaluate
    ]

    report = build_report(records)

    assert report.sessions == 4
    assert report.verified == 2
    assert report.excluded.get("unverified") == 1
    assert report.excluded.get("not_evaluable") == 1

    text = render_report(report)
    assert "unverified" in text.lower() or "synthetic" in text.lower()


def test_the_report_states_the_conformance_distribution():
    records = [record("a", score=100, density=0.0),
               record("b", score=85, density=83.33)]

    report = build_report(records)
    text = render_report(report)

    assert report.densities, "no conformance distribution was reported"
    assert len(report.densities) == 2


def test_the_report_states_correction_effort():
    records = [record("a", stages=[
        {"stage": "DOMAIN", "request_count": 1},
        {"stage": "CONTROLLER", "request_count": 3},   # two corrections
    ])]

    report = build_report(records)

    assert report.total_requests == 4
    assert report.corrected_stages == 1, "a stage that needed corrections was not counted"


# ---------------------------------------------------------------------------
# T016 — no data is not zero
# ---------------------------------------------------------------------------
def test_an_empty_corpus_reports_no_data_rather_than_zero():
    report = build_report([])

    assert report.sessions == 0
    assert report.has_data is False

    text = render_report(report)
    assert "no data" in text.lower() or "no sessions" in text.lower()
    # What matters is what the report CLAIMS, not what it mentions. The notice
    # itself names "0%" and "$0.00" in order to say it is claiming neither, so the
    # assertion is that no rate or cost line is emitted at all.
    assert "success rate" not in text.lower(), (
        "an empty corpus emitted a success-rate line; a rate over no sessions is "
        "not a number and must not be rendered as one"
    )
    assert report.success_rate is None, "an empty corpus produced a success rate"
    assert report.cost is None, "an empty corpus produced a cost"


def test_no_cost_is_reported_without_cost_data():
    report = build_report([record("a")])

    assert report.cost is None, (
        "a cost was reported with no cost data; 'no data' and 'measured zero' are "
        "different findings"
    )


# ---------------------------------------------------------------------------
# T017 — sessions are not tasks
# ---------------------------------------------------------------------------
def test_distinct_tasks_are_reported_separately_from_sessions():
    records = [record(f"s{i}", task="minimal") for i in range(10)]

    report = build_report(records)

    assert report.sessions == 10
    assert report.distinct_tasks == 1, (
        "ten runs of one task were reported as ten tasks; that is pseudo-replication"
    )
    assert report.distinct_tasks != report.sessions


def test_several_tasks_are_counted_distinctly():
    records = [record("a", task="minimal"), record("b", task="pair-a"),
               record("c", task="minimal")]

    report = build_report(records)

    assert report.sessions == 3
    assert report.distinct_tasks == 2


def test_records_without_a_task_label_are_reported_as_untagged():
    records = [record("a", task=None), record("b", task="minimal")]

    report = build_report(records)

    assert report.untagged == 1, (
        "an unlabelled record was silently counted as a distinct task"
    )


# ---------------------------------------------------------------------------
# T018 — excluded sessions contribute to nothing
# ---------------------------------------------------------------------------
def test_unverified_sessions_do_not_enter_the_success_rate():
    """One verified success and one synthetic one must not read as 100%."""
    records = [record("a"), record("b", unverified=True)]

    report = build_report(records)

    assert report.verified == 1
    assert report.sessions == 2
    assert report.success_rate == pytest.approx(1.0), (
        "the synthetic session entered the denominator"
    )


def test_unverified_sessions_do_not_enter_the_conformance_distribution():
    records = [record("a", density=0.0), record("b", density=90.0, unverified=True)]

    report = build_report(records)

    assert report.densities == [0.0], (
        "an unverified session contributed to the conformance distribution"
    )


def test_a_failed_build_is_verified_and_does_count_as_a_failure():
    """The distinction that matters: 'could not verify' is excluded, but
    'verified and failed' is a real failure and belongs in the denominator."""
    records = [record("a", score=100), record("b", score=40, evaluable=True)]

    report = build_report(records)

    assert report.verified == 2
    assert report.excluded == {}
    # Both count. One was clean, one was not, so the rate is one in two: a
    # verified failure belongs in the denominator, unlike an unverified session.
    assert report.success_rate == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# T021 — the batch driver records every outcome, including failures
# ---------------------------------------------------------------------------
@pytest.fixture
def clean_batch_records():
    from app.models.diagnostics import SessionDiagnosticRecord, ensure_schema
    from app.models.session import SessionLocal
    names = [f"corpus-{n}" for n in
             ("minimal", "pair-a", "constrained", "multi-entity", "pair-b")]

    def _clean():
        db = SessionLocal()
        try:
            # The table is created on first write; this fixture may run before
            # any write has happened, so it ensures the schema itself.
            ensure_schema(db.get_bind())
            for name in names:
                db.query(SessionDiagnosticRecord).filter(
                    SessionDiagnosticRecord.session_id == name
                ).delete()
            db.commit()
        finally:
            db.close()

    _clean()
    yield
    _clean()


def _final_state(*, artifacts=None, fallback=False, status="COMPLETED", error=None):
    return {
        "status": status,
        "error": error,
        "generated_files": artifacts or {},
        "test_metrics": {"allPassed": status == "COMPLETED", "fallback_used": fallback},
        "generation_journal": {"entries": [
            {"stage": "DOMAIN", "outcome": "CLEAN", "request_count": 1,
             "initial_verdict": {"passed": True, "violations": []}},
        ]},
    }


def test_a_batch_records_an_outcome_for_every_blueprint(clean_batch_records):
    """Every task must produce a record, whether it succeeded, failed or crashed."""
    sys.path.insert(0, str(REPO_ROOT / "backend" / "scripts"))
    from run_corpus_baseline import run_baseline

    import json as _json
    corpus = REPO_ROOT / "backend" / "tests" / "fixtures" / "baseline_blueprints"
    from tests.fixtures import fake_model as fm
    blueprint = _json.loads((corpus / "minimal.json").read_text())

    def runner(name):
        if name == "pair-a":
            raise RuntimeError("provider unavailable")          # a crashed session
        if name == "constrained":
            return _final_state(status="BLOCKED", error="runtime unavailable")  # no artifacts
        if name == "multi-entity":
            return _final_state(artifacts=fm.compliant_artifacts("CONTROLLER", blueprint),
                                fallback=True)                   # synthetic build
        return _final_state(artifacts=fm.compliant_artifacts("CONTROLLER", blueprint))

    summary = run_baseline(
        runner=runner,
        blueprints=["minimal", "pair-a", "constrained", "multi-entity"],
        output=lambda line: None,
    )

    outcomes = {o["blueprint"]: o for o in summary["outcomes"]}
    assert set(outcomes) == {"minimal", "pair-a", "constrained", "multi-entity"}

    # A crash is an outcome, not an abort: the batch continues past it.
    assert outcomes["pair-a"]["status"] == "ERROR"
    assert "provider unavailable" in outcomes["pair-a"]["error"]

    report = summary["report"]
    assert report.sessions == 4, "a session went unrecorded"
    # Three of the four are excluded, for two distinct reasons:
    #   - multi-entity: the build fell back to a synthetic result (unverified)
    #   - constrained:  ran but produced nothing to evaluate (not evaluable)
    #   - pair-a:       crashed before producing anything (not evaluable)
    # Only minimal is verified, so only minimal enters any figure.
    assert report.excluded.get("unverified") == 1
    assert report.excluded.get("not_evaluable") == 2, (
        "a crashed session was not counted in the population it belongs to"
    )
    assert report.verified == 1
    assert report.success_rate == 1.0   # one verified, and it was clean


def test_an_empty_batch_reports_no_data(clean_batch_records):
    sys.path.insert(0, str(REPO_ROOT / "backend" / "scripts"))
    from run_corpus_baseline import run_baseline

    summary = run_baseline(runner=lambda name: _final_state(),
                           blueprints=[], output=lambda line: None)

    assert summary["report"].sessions == 0
    assert summary["report"].has_data is False
    assert summary["report"].success_rate is None


def test_the_batch_labels_each_record_with_its_task(clean_batch_records):
    """The label is what lets the report separate tasks from sessions. Without it
    repeated runs of one task would be indistinguishable from a larger sample."""
    sys.path.insert(0, str(REPO_ROOT / "backend" / "scripts"))
    from run_corpus_baseline import run_baseline
    from tests.fixtures import fake_model as fm
    import json as _json

    corpus = REPO_ROOT / "backend" / "tests" / "fixtures" / "baseline_blueprints"
    blueprint = _json.loads((corpus / "minimal.json").read_text())
    artifacts = fm.compliant_artifacts("CONTROLLER", blueprint)

    summary = run_baseline(
        runner=lambda name: _final_state(artifacts=artifacts),
        blueprints=["minimal", "pair-a"],
        output=lambda line: None,
    )

    report = summary["report"]
    assert report.distinct_tasks == 2, (
        f"the batch did not label its records by task; got {report.distinct_tasks}"
    )
    assert report.untagged == 0
