"""The optimiser gate (P8): "is there anything for a loop to move?"

The gate is the proposal's own condition, not a preference: the optimiser is deferred
until the conformance measure varies across real sessions. These tests pin the two
independent questions the check asks, and the way it must refuse to manufacture a
result from repeated runs of one task.

The second question turned out to be the live one. With real builds now running, the
build OUTCOME varies while the conformance MEASURE stays flat at 0 -- including on
sessions that failed to build. An instrument that is blind to the failure it is meant
to explain cannot attribute anything to a skill edit.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from scripts.check_optimizer_gate import evaluate, render  # noqa: E402


def _record(task, build, penalty=0, run=1):
    return {
        "task": task, "arm": "control", "run": run,
        "build_success": build, "new_penalty": penalty,
    }


def test_a_constant_measure_fails_the_gate_even_when_builds_vary():
    """The live case: the outcome moves, the instrument does not.

    A curator can only act on a rule that fires. If nothing fires, there is nothing
    to edit, no matter how many builds fail.
    """
    records = [
        _record("t1", True), _record("t1", False, run=2),
        _record("t2", True), _record("t2", False, run=2),
    ]
    result = evaluate(records)

    assert result["outcome_varies"] is True
    assert result["measure_varies"] is False
    assert result["gate_passed"] is False
    # The rendered text wraps, so assert on a phrase that does not span the wrap.
    assert "conformance measure is constant" in render(result)


def test_a_constant_outcome_fails_the_gate_even_when_the_measure_varies():
    """A saturated generator has no admission test: every edit looks equally good."""
    records = [_record("t1", True, penalty=0), _record("t2", True, penalty=15)]
    result = evaluate(records)

    assert result["outcome_varies"] is False
    assert result["measure_varies"] is True
    assert result["gate_passed"] is False


def test_the_gate_passes_only_when_both_vary():
    records = [
        _record("t1", True, penalty=0), _record("t1", False, penalty=15, run=2),
        _record("t2", True, penalty=0), _record("t2", False, penalty=15, run=2),
    ]
    result = evaluate(records)

    assert result["gate_passed"] is True
    assert "GATE PASSED" in render(result)


def test_repeats_of_one_task_are_not_counted_as_a_larger_sample():
    """Five runs of one task are still one task (FR-009/FR-013).

    Counting repeats as independent observations is how a small corpus manufactures
    a result, so the distinct-task count is reported separately and a task only
    counts as varying when its OWN runs disagreed.
    """
    records = [_record("only-task", True, run=i) for i in range(1, 6)]
    result = evaluate(records)

    assert result["sessions"] == 5
    assert result["distinct_tasks"] == 1
    assert result["tasks_with_both_outcomes"] == 0


def test_a_task_varies_only_when_its_own_runs_disagreed():
    records = [
        _record("agree-passes", True, run=1),
        _record("agree-passes", True, run=2),
        _record("disagrees", True, run=1),
        _record("disagrees", False, run=2),
    ]
    result = evaluate(records)

    assert result["distinct_tasks"] == 2
    assert result["tasks_with_both_outcomes"] == 1


def test_records_without_a_build_outcome_are_not_evidence():
    """A session that never completed has no outcome to reason about."""
    records = [
        _record("t1", True, penalty=0),
        _record("t1", False, penalty=15, run=2),
        {"task": "t2", "arm": "control", "run": 1, "build_success": None},
    ]
    assert evaluate(records)["sessions"] == 2
