"""Verification-guided selection (best-of-k, P5).

The mechanism has to be right about three things before it is worth spending money
on, and each of them is a way to report a success that did not happen:

* it must not select a candidate the verifier rejected,
* it must not treat a verifier that could not run as a pass,
* it must stop at the first pass rather than spending the whole budget.

The last one is cost, not correctness, but a selection loop that always spends k is
the "uniform budgets are strictly suboptimal" result reproduced in the wrong
direction.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.verification_selection import select_first_verified  # noqa: E402


def _candidates(items):
    yield from items


def test_the_first_verified_candidate_is_selected_and_the_rest_are_never_generated():
    """Cost is attempts made, not the budget: the generator is consumed lazily."""
    produced = []

    def candidates():
        for index in range(6):
            produced.append(index)
            yield f"candidate-{index}"

    outcome = select_first_verified(candidates(), lambda c: c == "candidate-2")

    assert outcome.verified is True
    assert outcome.selected_index == 2
    assert outcome.attempts == 3
    assert produced == [0, 1, 2], "generation continued past the first verified candidate"


def test_no_candidate_verifying_selects_nothing_and_says_so():
    outcome = select_first_verified(_candidates(["a", "b", "c"]), lambda c: False)

    assert outcome.verified is False
    assert outcome.selected_index is None
    assert outcome.attempts == 3
    assert "not a selection success" in outcome.reason


def test_an_unverified_candidate_is_never_selected_as_the_best_of_a_bad_set():
    """The conflation feature 012 exists to prevent, one level down.

    Selecting the least-bad failing candidate and reporting it as the outcome is
    how a system reports a success its own verifier denied.
    """
    outcome = select_first_verified(_candidates(["bad", "worse"]), lambda c: False)

    assert outcome.selected_index is None
    assert outcome.verified is False


def test_a_verifier_that_cannot_run_is_not_a_pass():
    """A raising verifier verified nothing, and the reason names the fault."""

    def verify(candidate):
        raise RuntimeError("container runtime unreachable")

    outcome = select_first_verified(_candidates(["a", "b"]), verify)

    assert outcome.verified is False
    assert outcome.selected_index is None
    assert outcome.attempts == 1, "there is no point generating more against a broken verifier"
    assert "RuntimeError" in outcome.reason
    assert "Nothing was verified" in outcome.reason


def test_the_candidate_budget_is_respected():
    outcome = select_first_verified(
        _candidates([f"c{i}" for i in range(10)]), lambda c: False, max_candidates=4
    )

    assert outcome.attempts == 4
    assert outcome.verified is False


def test_an_empty_candidate_stream_reports_that_nothing_was_attempted():
    """Distinguishes 'generated and none passed' from 'never generated'."""
    outcome = select_first_verified(_candidates([]), lambda c: True)

    assert outcome.attempts == 0
    assert outcome.verified is False
    assert "no candidate was generated" in outcome.reason


def test_verifier_results_are_kept_in_order_for_diagnosis():
    outcome = select_first_verified(_candidates(["a", "b", "c"]), lambda c: c == "c")

    assert outcome.verifier_results == (False, False, True)


def test_a_candidate_that_passes_is_selected_even_when_earlier_ones_raised():
    """One unverifiable attempt must not poison the whole selection."""
    seen = {"n": 0}

    def verify(candidate):
        seen["n"] += 1
        if candidate == "broken":
            raise RuntimeError("transient")
        return candidate == "good"

    outcome = select_first_verified(_candidates(["broken", "good"]), verify)

    assert outcome.verified is False, "a raising verifier stops selection by design"
    assert seen["n"] == 1
