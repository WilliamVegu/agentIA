"""The polarity experiment's decision rule, pinned.

The rule was pre-registered before the run. Its whole value is that it cannot be
renegotiated once the numbers are in, so it needs the same test discipline as any
other specification -- a mis-implemented rule would report the experiment wrongly
while looking like an analysis.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from scripts.analyse_instruction_experiment import (  # noqa: E402
    MIN_TASKS_FOR_SIGNIFICANCE,
    _sign_test_p,
    analyse,
)


def _records(task_arm_pass: dict) -> list:
    """``{(task, arm): [bool, ...]}`` -> experiment records."""
    records = []
    for (task, arm), outcomes in task_arm_pass.items():
        for index, passed in enumerate(outcomes, start=1):
            records.append({
                "task": task, "arm": arm, "run": index,
                "build_success": passed, "new_penalty": 0,
            })
    return records


def _six_tasks(control, prohibition, placebo):
    """Six tasks with a constant per-arm outcome."""
    data = {}
    for i in range(6):
        task = f"t{i}"
        data[(task, "control")] = [control]
        data[(task, "prohibition")] = [prohibition]
        data[(task, "placebo")] = [placebo]
    return _records(data)


def test_the_sign_test_matches_the_arithmetic_floor():
    """At n=6 unanimous, the exact two-sided p is 2/2^6 = 0.03125."""
    assert _sign_test_p(6, 0) == 2 / (2 ** 6)
    assert _sign_test_p(6, 0) < 0.05
    # n=5 unanimous cannot reach significance, which is why 6 is the minimum.
    assert _sign_test_p(5, 0) == 2 / (2 ** 5)
    assert _sign_test_p(5, 0) > 0.05
    assert _sign_test_p(0, 0) is None


def test_unanimous_prohibition_beats_both_arms_is_supported():
    result = analyse(_six_tasks(control=False, prohibition=True, placebo=False))

    assert result["tasks"] == 6
    assert "SUPPORTED" in result["conclusion"]
    assert result["comparisons"]["prohibition_vs_placebo"]["wins"] == 6


def test_beating_control_but_not_placebo_is_reported_as_priming():
    """The distinction the placebo exists to make.

    A win over control alone is consistent with the content-independent priming
    effect, so calling it evidence for polarity would be a false attribution.
    """
    result = analyse(_six_tasks(control=False, prohibition=True, placebo=True))

    assert "PRIMING" in result["conclusion"]
    assert "not evidence for polarity" in result["conclusion"]


def test_no_separation_is_reported_as_no_difference_not_as_a_trend():
    result = analyse(_six_tasks(control=True, prohibition=True, placebo=True))

    assert "NO DIFFERENCE DETECTED" in result["conclusion"]


def test_fewer_than_six_tasks_is_reported_as_insufficient():
    """At fewer than six tasks no paired two-sided test can reach p<0.05 at all."""
    data = {("t0", "control"): [True], ("t0", "prohibition"): [False],
            ("t0", "placebo"): [True]}
    result = analyse(_records(data))

    assert result["tasks"] < MIN_TASKS_FOR_SIGNIFICANCE
    assert "INSUFFICIENT" in result["conclusion"]


def test_repeats_are_pooled_into_a_rate_and_the_task_is_the_unit():
    """Five runs of one task are one task, not five observations."""
    data = {("t0", "control"): [True] * 5, ("t0", "prohibition"): [False] * 5,
            ("t0", "placebo"): [True] * 5}
    result = analyse(_records(data))

    assert result["tasks"] == 1, "repeats must not inflate the task count"
    assert result["runs_per_cell"]["control"] == 5


def test_a_task_counts_as_a_win_only_on_its_pooled_rate():
    """2/5 vs 1/5 is a win; 2/5 vs 2/5 is a tie."""
    data = {
        ("win", "control"): [True, False, False, False, False],
        ("win", "prohibition"): [True, True, False, False, False],
        ("win", "placebo"): [True, False, False, False, False],
        ("tie", "control"): [True, True, False, False, False],
        ("tie", "prohibition"): [True, True, False, False, False],
        ("tie", "placebo"): [True, True, False, False, False],
    }
    comparison = analyse(_records(data))["comparisons"]["prohibition_vs_control"]

    assert comparison["wins"] == 1
    assert comparison["ties"] == 1
