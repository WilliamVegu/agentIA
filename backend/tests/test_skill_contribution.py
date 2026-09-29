"""Per-skill leave-one-out contribution (feature 015).

Contract: ``specs/015-diagnostic-skill-evolution/contracts/contribution-measurement.md``

The measurement decides whether a skill leaves the library, so each of the
contract's rules gets a test here. All of them are model-free and cost nothing: the
runners are injected functions, so nothing touches the network and nothing spends.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.skill_contribution import (  # noqa: E402
    EVIDENCE_FLOOR,
    TaskOutcome,
    measure_contribution,
    min_detectable_effect,
    quality_from_density,
)


def runner_from(scores, *, evaluable=None, calls=None, raises=False):
    """A task runner over a ``task -> measure`` mapping.

    Records the tasks it was asked for when ``calls`` is supplied, so a test can
    assert both arms ran the identical set.
    """
    def run(task):
        if calls is not None:
            calls.append(task)
        if raises:
            raise RuntimeError("task runner exploded")
        ok = True if evaluable is None else bool(evaluable.get(task, True))
        return TaskOutcome(evaluable=ok, measure=float(scores.get(task, 0.0)))
    return run


def scores(n, base):
    """``n`` distinct tasks, each measuring ``base``."""
    return {f"task-{i}": float(base) for i in range(n)}


# ---------------------------------------------------------------------------
# Rule 1 -- repeats are not evidence
# ---------------------------------------------------------------------------
def test_repeats_of_one_task_are_counted_once():
    tasks = ["minimal", "minimal", "minimal", "pair-a"]

    measurement = measure_contribution(
        "rule-x", tasks,
        runner_from({"minimal": 1.0, "pair-a": 1.0}),
        runner_from({"minimal": 0.0, "pair-a": 0.0}),
    )

    assert measurement.distinct_tasks == 2, (
        "three runs of one task were counted as three observations; a round could "
        "manufacture significance by repeating itself"
    )


# ---------------------------------------------------------------------------
# Rule 2 -- insufficiency is a result, not an improvement
# ---------------------------------------------------------------------------
def test_insufficient_evidence_reports_itself_and_never_an_improvement():
    measurement = measure_contribution(
        "rule-x", [f"task-{i}" for i in range(5)],
        runner_from(scores(5, 1.0)),
        runner_from(scores(5, 0.5)),
    )

    assert measurement.delta == pytest.approx(0.5), "the observation is still reported"
    assert measurement.sufficient is False
    assert measurement.improvement is None, (
        "a delta the evidence cannot support was presented as an improvement"
    )
    assert "insufficient" in measurement.conclusion
    assert "0.5" in measurement.conclusion or "+0.500" in measurement.conclusion


def test_an_empty_task_set_is_insufficient_and_has_no_delta():
    measurement = measure_contribution("rule-x", [], runner_from({}), runner_from({}))

    assert measurement.distinct_tasks == 0
    assert measurement.delta is None
    assert measurement.sufficient is False
    assert measurement.improvement is None


# ---------------------------------------------------------------------------
# Rule 4 -- both arms on the identical task set
# ---------------------------------------------------------------------------
def test_both_arms_run_the_identical_task_set():
    with_calls, without_calls = [], []
    tasks = ["minimal", "pair-a", "pair-b"]

    measure_contribution(
        "rule-x", tasks,
        runner_from(scores(3, 1.0), calls=with_calls),
        runner_from(scores(3, 0.0), calls=without_calls),
    )

    assert with_calls == without_calls == tasks, (
        "the arms ran different task sets; the comparison would be meaningless "
        "while still producing a number"
    )


# ---------------------------------------------------------------------------
# Failure behaviour -- an asymmetric task set is not a comparison
# ---------------------------------------------------------------------------
def test_a_task_evaluable_in_one_arm_only_is_excluded_from_both():
    tasks = [f"task-{i}" for i in range(6)]
    present = {"task-3": 1.0}
    absent = {"task-3": 0.0}

    measurement = measure_contribution(
        "rule-x", tasks,
        runner_from(scores(6, 1.0), evaluable=present),
        runner_from(scores(6, 0.0), evaluable=absent),
    )

    assert measurement.excluded_tasks == ("task-3",)
    assert measurement.distinct_tasks == 5, "the asymmetric task was counted in an arm"
    assert len(measurement.with_skill) == len(measurement.without_skill) == 5


def test_a_raising_runner_abandons_the_measurement():
    measurement = measure_contribution(
        "rule-x", [f"task-{i}" for i in range(6)],
        runner_from(scores(6, 1.0), raises=True),
        runner_from(scores(6, 0.0)),
    )

    assert measurement.error and "task runner exploded" in measurement.error
    assert measurement.delta is None
    assert measurement.sufficient is False
    assert measurement.removable is False, "an abandoned measurement removed a skill"


# ---------------------------------------------------------------------------
# Rule 3 / D4 -- removal needs sufficiency AND a delta below the floor
# ---------------------------------------------------------------------------
def test_sufficient_evidence_below_the_floor_is_removable():
    measurement = measure_contribution(
        "rule-x", [f"task-{i}" for i in range(6)],
        runner_from(scores(6, 0.0)),
        runner_from(scores(6, 0.5)),
    )

    assert measurement.sufficient is True
    assert measurement.delta == pytest.approx(-0.5)
    assert measurement.removable is True


def test_sufficient_evidence_above_the_floor_is_retained():
    measurement = measure_contribution(
        "rule-x", [f"task-{i}" for i in range(6)],
        runner_from(scores(6, 0.5)),
        runner_from(scores(6, 0.0)),
    )

    assert measurement.removable is False
    assert measurement.improvement == pytest.approx(0.5)


def test_insufficient_evidence_never_removes_even_when_the_delta_is_negative():
    """The distinction the floor exists for: not proven != hurts."""
    measurement = measure_contribution(
        "rule-x", [f"task-{i}" for i in range(5)],
        runner_from(scores(5, 0.0)),
        runner_from(scores(5, 0.9)),
    )

    assert measurement.delta is not None and measurement.delta < EVIDENCE_FLOOR
    assert measurement.sufficient is False
    assert measurement.removable is False, "noise was converted into a removal"


# ---------------------------------------------------------------------------
# The arithmetic floor, stated in the platform's own reports
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "tasks, expected",
    [
        (0, None),
        (4, None),      # best attainable p = 0.125
        (5, None),      # best attainable p = 0.0625 -- cannot reach p<0.05
        (6, 1.0),       # 2 * 0.5**6 = 0.03125, the first size that can
        (10, 0.9),
    ],
)
def test_min_detectable_effect_matches_the_documented_floor(tasks, expected):
    assert min_detectable_effect(tasks) == expected


def test_the_measure_is_higher_is_better_once_inverted():
    """The platform's density is penalty-per-100-artifacts: lower is better."""
    assert quality_from_density(0.0) == 0.0
    assert quality_from_density(12.5) == -12.5
    assert quality_from_density(-3.0) == 3.0
