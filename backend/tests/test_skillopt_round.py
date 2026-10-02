"""The whole proposal, offline: collect -> reflect -> apply -> measure -> decide.

Feature 015's evolution-round contract requires exactly one record per round on
**every** exit path, because a round that crashed without a record is
indistinguishable from one that never ran. These tests drive `run_round` with
injected seams -- the collector, reflector, applier, per-skill measurement and
guardrail are all parameters -- so the entire chain is exercised with **no model
call, no network and no spend**.

The expected outcome at this platform's task count is `NO_MEASURABLE_CHANGE`: five
distinct tasks cannot reach p<0.05 under any outcome. A test asserting that is not
a pessimistic test; it is the honest behaviour, and the contract says so.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.models.diagnostics import write_diagnostic_record  # noqa: E402
from app.models.session import (  # noqa: E402
    GenerationSessionDB,
    SessionLocal,
    SessionPhase,
    SessionStatus,
)
from app.models.skillopt import read_runs  # noqa: E402
from app.services.skill_contribution import (  # noqa: E402
    EVIDENCE_FLOOR,
    ContributionMeasurement,
    TaskOutcome,
    measure_contribution,
)
from app.skills.document import load_skill  # noqa: E402
from scripts.skillopt.apply import apply_edits  # noqa: E402
from scripts.skillopt.collect import (  # noqa: E402
    COLLECTION_NO_FAILURES,
    COLLECTION_NO_SESSIONS,
    collect_outcomes,
)
from scripts.skillopt.reflect import build_prompt  # noqa: E402
from scripts.skillopt.round import run_round  # noqa: E402

ROUND_SESSION = "t015-round"

SKILL_TEXT = """# A Skill

## Granularity
task-level

## When to apply
Whenever.

## Rules
1. Keep controllers out of the repository layer.

<!-- SLOW_UPDATE_START -->
<!-- SLOW_UPDATE_END -->
"""


def _runs() -> int:
    return len(read_runs())


def _measurement(skill_id, delta, *, sufficient, distinct=8):
    return ContributionMeasurement(
        skill_id=skill_id,
        delta=delta,
        distinct_tasks=distinct,
        min_detectable_effect=1.0 if sufficient else None,
        sufficient=sufficient,
        floor=EVIDENCE_FLOOR,
    )


@pytest.fixture
def skill_path(tmp_path):
    path = tmp_path / "skill.md"
    path.write_text(SKILL_TEXT, encoding="utf-8")
    return path


@pytest.fixture
def recorded_failure():
    """One blocked session carrying a rule histogram, as the retarget expects."""
    db = SessionLocal()
    try:
        db.query(GenerationSessionDB).filter(GenerationSessionDB.id == ROUND_SESSION).delete()
        db.add(GenerationSessionDB(
            id=ROUND_SESSION, spec_id="spec-t015-round", spec_name="notes-service",
            status=SessionStatus.BLOCKED, phase=SessionPhase.FAILED, repair_attempts=0,
        ))
        db.commit()
    finally:
        db.close()

    write_diagnostic_record(
        ROUND_SESSION, task="minimal", score=70, raw_penalty=30, density=10.0,
        artifact_count=3, evaluable=True, counts_by_severity={"HIGH": 1},
        rule_histogram={"PRINCIPLE_I_LAYER_ISOLATION": 1},
        findings=[{"rule_id": "PRINCIPLE_I_LAYER_ISOLATION"}],
        stages=[{"stage": "CONTROLLER", "rule_histogram": {"PRINCIPLE_I_LAYER_ISOLATION": 1}}],
    )
    yield ROUND_SESSION

    db = SessionLocal()
    try:
        db.query(GenerationSessionDB).filter(GenerationSessionDB.id == ROUND_SESSION).delete()
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# One record per round, on every path
# ---------------------------------------------------------------------------
def test_no_sessions_is_recorded():
    before = _runs()

    result = run_round(
        skills=["layer_architecture"],
        task_set=["minimal"],
        collector=lambda: {"status": COLLECTION_NO_SESSIONS, "records": [], "failures": []},
    )

    assert result.decision == "NO_SESSIONS"
    assert _runs() == before + 1, "a terminal state left no record"
    assert read_runs(limit=1)[0]["decision"] == "NO_SESSIONS"


def test_no_failures_is_recorded():
    before = _runs()

    result = run_round(
        skills=["layer_architecture"],
        task_set=["minimal"],
        collector=lambda: {"status": COLLECTION_NO_FAILURES, "records": [{}], "failures": []},
    )

    assert result.decision == "NO_FAILURES"
    assert _runs() == before + 1


def test_a_crashing_round_is_recorded_with_its_exception():
    before = _runs()

    def exploding_collector():
        raise RuntimeError("the store is unreachable")

    result = run_round(
        skills=["layer_architecture"], task_set=["minimal"], collector=exploding_collector,
    )

    assert result.decision == "ERROR"
    assert "the store is unreachable" in (result.error or "")
    assert _runs() == before + 1, "a crashed round left no record"
    assert read_runs(limit=1)[0]["error"]


# ---------------------------------------------------------------------------
# The expected outcome at this task count
# ---------------------------------------------------------------------------
def test_insufficient_evidence_records_no_measurable_change_and_changes_nothing():
    before = _runs()

    result = run_round(
        skills=["layer_architecture"],
        task_set=[f"task-{i}" for i in range(5)],
        collector=lambda: {"status": "OK", "records": [{}], "failures": [{"session_id": "s"}]},
        measure_skill=lambda skill_id: _measurement(skill_id, -5.0, sufficient=False, distinct=5),
    )

    assert result.decision == "NO_MEASURABLE_CHANGE"
    assert result.removed == [], "an insufficient measurement drove a removal"
    assert _runs() == before + 1


# ---------------------------------------------------------------------------
# A sufficient below-floor measurement evicts
# ---------------------------------------------------------------------------
def test_a_measurably_harmful_skill_is_removed_and_the_measurement_is_recorded():
    before = _runs()

    result = run_round(
        skills=["layer_architecture"],
        task_set=[f"task-{i}" for i in range(8)],
        collector=lambda: {"status": "OK", "records": [{}], "failures": [{"session_id": "s"}]},
        measure_skill=lambda skill_id: _measurement(skill_id, -2.0, sufficient=True),
    )

    assert result.decision == "REMOVED"
    assert result.removed == ["layer_architecture"]
    assert _runs() == before + 1
    stored = read_runs(limit=1)[0]
    assert stored["removed"] == ["layer_architecture"], "the removal cited no measurement"
    assert stored["measurements"] and stored["measurements"][0]["delta"] == -2.0


# ---------------------------------------------------------------------------
# The whole chain, offline, with real components wherever they are free
# ---------------------------------------------------------------------------
def test_the_full_chain_runs_offline(skill_path, recorded_failure):
    """collect (real) -> prompt -> scripted reflect -> apply (real) -> measure -> REMOVED.

    Only the two things that would spend money or execute code are injected: the
    reflector (a scripted edit set instead of a model call) and the per-skill
    measurement (a scripted runner instead of fresh sessions). Everything else is
    the production implementation.
    """
    # 1. Collect real recorded evidence and confirm the diagnostics reached it.
    collected = collect_outcomes(limit=5, session_ids=[recorded_failure])
    record = next(r for r in collected["records"] if r["session_id"] == recorded_failure)
    assert record["rule_histogram"] == {"PRINCIPLE_I_LAYER_ISOLATION": 1}

    # 2. The prompt the reflector would build carries the recurring rule.
    skill = load_skill(skill_path)
    prompt = build_prompt(skill, collected["failures"])
    assert "PRINCIPLE_I_LAYER_ISOLATION" in prompt

    # 3. A scripted reflection (no model call) and the REAL applier.
    proposed = [{
        "op": "append",
        "content": "Never import a repository type into a controller; depend on the service.",
    }]

    def scripted_reflector(document, failures):
        return proposed

    # 4. A scripted leave-one-out measurement: sufficient and below the floor.
    def scripted_measure(skill_id):
        return _measurement(skill_id, -1.5, sufficient=True)

    before = _runs()
    result = run_round(
        skills=["layer_architecture"],
        task_set=["minimal", "pair-a"],
        collector=lambda: collected,
        reflector=scripted_reflector,
        load_skill=lambda name: skill,
        apply_edits=apply_edits,
        measure_skill=scripted_measure,
    )

    assert result.decision == "REMOVED"
    assert result.removed == ["layer_architecture"]
    assert result.applied, "the proposed edit was not applied to a candidate"
    assert result.run_id and result.run_id > 0
    assert _runs() == before + 1


# ---------------------------------------------------------------------------
# The measurement itself, over the same recorded evidence
# ---------------------------------------------------------------------------
def test_leave_one_out_over_recorded_density_separates_a_real_skill_from_an_inert_one():
    """The retarget end to end: recorded density in, a contribution decision out."""
    tasks = [f"task-{i}" for i in range(8)]

    def runner(density_by_task):
        def run(task):
            return TaskOutcome(evaluable=True, measure=-float(density_by_task[task]))
        return run

    # A load-bearing skill: with it, every task carries no penalty; without it, all do.
    load_bearing = measure_contribution(
        "layer_architecture", tasks,
        runner({t: 0.0 for t in tasks}),
        runner({t: 40.0 for t in tasks}),
    )
    # An inert one: identical either way.
    inert = measure_contribution(
        "noop_skill", tasks,
        runner({t: 10.0 for t in tasks}),
        runner({t: 10.0 for t in tasks}),
    )

    assert load_bearing.sufficient is True
    assert load_bearing.improvement == pytest.approx(40.0)
    assert inert.sufficient is True
    assert inert.improvement is None, "an inert skill was reported as an improvement"
    assert inert.delta == pytest.approx(0.0)
