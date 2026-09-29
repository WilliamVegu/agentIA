"""Gate tests (feature 014, T014 / US3).

The gate is the component whose correctness decides whether anything is learned, so
these tests carry more weight than the rest.

Four properties, each of which has a silent failure mode if it is wrong:

* **Strict acceptance.** A tie is rejected. Accepting ties would let a skill drift
  on noise while every step looked successful.
* **Both skills on the same sample.** Scoring them on different samples would
  produce a comparison that is meaningless while still yielding a number.
* **A fallback-marked execution never passes.** Under permissive mode a synthetic
  verification returns exit code zero without compiling anything, so scoring on the
  exit code alone would reward a skill for making the verifier give up — and a text
  optimiser will find that exploit.
* **Disjointness.** If the gate scored the candidate on the sessions the proposal
  came from, the candidate would look better for the wrong reason, and nothing in
  the score would say so.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from scripts.skillopt.gate import (  # noqa: E402
    BASELINE_BLUEPRINTS,
    DECISION_ACCEPTED,
    DECISION_REJECTED,
    ExecutionResult,
    HELD_OUT_DEFAULT,
    GateError,
    run_gate,
    select_held_out,
)

TRAINING_IDS = ["train-1", "train-2", "train-3"]


class ScriptedRunner:
    """An injected runner. Records what it was asked to do.

    This is the injectable seam: it is passed as a **parameter**, not monkeypatched,
    so a refactor cannot silently stop injecting and leave the gate running real
    sessions in the suite.
    """

    def __init__(self, outcomes):
        self._outcomes = outcomes
        self.calls = []

    def __call__(self, blueprint: str, skill_path) -> ExecutionResult:
        self.calls.append((blueprint, str(skill_path)))
        outcome = self._outcomes.get(blueprint)
        if callable(outcome):
            outcome = outcome(skill_path)
        return ExecutionResult(
            blueprint=blueprint,
            session_id=getattr(outcome, "session_id", f"session-{blueprint}"),
            exit_code=getattr(outcome, "exit_code", 0),
            fallback_used=getattr(outcome, "fallback_used", False),
        )


class Outcome:
    def __init__(self, exit_code=0, fallback_used=False, session_id=None):
        self.exit_code = exit_code
        self.fallback_used = fallback_used
        self.session_id = session_id


def _skill(tmp_path, name, body="1. A rule."):
    path = tmp_path / name
    path.write_text(
        f"# S\n\n## Granularity\ntask-level\n\n## When to apply\nAlways.\n\n"
        f"## Rules\n{body}\n\n<!-- SLOW_UPDATE_START -->\n<!-- SLOW_UPDATE_END -->\n",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# The held-out set
# ---------------------------------------------------------------------------
def test_held_out_is_drawn_from_the_existing_baseline_blueprints():
    assert len(BASELINE_BLUEPRINTS) == 5, "the contract is the five existing fixtures"
    assert HELD_OUT_DEFAULT == 4, "M defaults to 4, leaving one rotation buffer"


def test_the_held_out_selection_is_deterministic():
    first = select_held_out("iteration-1")
    second = select_held_out("iteration-1")

    assert first == second, "the same iteration identity selected different blueprints"
    assert len(first) == 4
    assert len(set(first)) == 4, "a blueprint was selected twice"


def test_rotation_moves_the_excluded_blueprint():
    """One blueprint is always left out, so the exam is not fixed forever."""
    selections = {tuple(select_held_out(f"iteration-{n}")) for n in range(8)}

    assert len(selections) > 1, "rotation never changes the held-out set"
    assert all(len(selection) == 4 for selection in selections)


# ---------------------------------------------------------------------------
# Strict acceptance
# ---------------------------------------------------------------------------
def test_a_strictly_better_candidate_is_accepted(tmp_path):
    current = _skill(tmp_path, "current.md")
    candidate = _skill(tmp_path, "candidate.md", "1. A better rule.")

    # Every blueprint passes under the candidate, one fails under the current skill.
    held = select_held_out("it-accept")
    outcomes = {
        blueprint: (Outcome(exit_code=0) if blueprint != held[0] else
                    (lambda skill: Outcome(exit_code=0 if "candidate" in str(skill) else 1)))
        for blueprint in held
    }
    runner = ScriptedRunner(outcomes)

    result = run_gate(current, candidate, runner=runner,
                      training_session_ids=TRAINING_IDS, iteration_id="it-accept")

    assert result.candidate_score > result.current_score
    assert result.decision == DECISION_ACCEPTED


def test_an_equal_score_is_rejected(tmp_path):
    current = _skill(tmp_path, "current.md")
    candidate = _skill(tmp_path, "candidate.md", "1. A different rule.")
    runner = ScriptedRunner({b: Outcome(exit_code=0) for b in select_held_out("it-tie")})

    result = run_gate(current, candidate, runner=runner,
                      training_session_ids=TRAINING_IDS, iteration_id="it-tie")

    assert result.candidate_score == result.current_score
    assert result.decision == DECISION_REJECTED, "a tie was accepted"


def test_a_worse_candidate_is_rejected(tmp_path):
    current = _skill(tmp_path, "current.md")
    candidate = _skill(tmp_path, "candidate.md", "1. A worse rule.")
    held = select_held_out("it-worse")
    outcomes = {
        b: (Outcome(exit_code=0) if "candidate" not in b else Outcome(exit_code=1))
        for b in held
    }
    runner = ScriptedRunner({b: (lambda skill, b=b: Outcome(
        exit_code=0 if "candidate" not in str(skill) else 1)) for b in held})

    result = run_gate(current, candidate, runner=runner,
                      training_session_ids=TRAINING_IDS, iteration_id="it-worse")

    assert result.decision == DECISION_REJECTED


# ---------------------------------------------------------------------------
# Same sample, both skills
# ---------------------------------------------------------------------------
def test_both_skills_are_scored_on_the_identical_held_out_set(tmp_path):
    current = _skill(tmp_path, "current.md")
    candidate = _skill(tmp_path, "candidate.md", "1. Other.")
    runner = ScriptedRunner({b: Outcome(exit_code=0) for b in select_held_out("it-same")})

    result = run_gate(current, candidate, runner=runner,
                      training_session_ids=TRAINING_IDS, iteration_id="it-same")

    assert len(result.executions) == 2 * HELD_OUT_DEFAULT, (
        "the gate did not score both skills on M blueprints each"
    )
    current_blueprints = [e.blueprint for e in result.executions if e.skill == "current"]
    candidate_blueprints = [e.blueprint for e in result.executions if e.skill == "candidate"]
    assert current_blueprints == candidate_blueprints, (
        "the two skills were scored on different held-out samples"
    )
    assert set(current_blueprints) == set(result.held_out_blueprints)


# ---------------------------------------------------------------------------
# The pass rule
# ---------------------------------------------------------------------------
def test_a_fallback_marked_execution_does_not_pass_even_at_exit_code_zero(tmp_path):
    """The exploit this rule closes: make the verifier give up and the score rises."""
    current = _skill(tmp_path, "current.md")
    candidate = _skill(tmp_path, "candidate.md", "1. Other.")
    held = select_held_out("it-fallback")

    # The candidate makes every run fall back to a synthetic success.
    runner = ScriptedRunner({
        b: (lambda skill, b=b: Outcome(
            exit_code=0,
            fallback_used="candidate" in str(skill),
        ))
        for b in held
    })

    result = run_gate(current, candidate, runner=runner,
                      training_session_ids=TRAINING_IDS, iteration_id="it-fallback")

    assert result.candidate_score == 0.0, (
        "a fallback-marked execution counted as a pass — the gate rewards making "
        "the verifier give up"
    )
    assert result.decision == DECISION_REJECTED


def test_an_unscorable_execution_is_excluded_not_counted_as_a_failure(tmp_path):
    current = _skill(tmp_path, "current.md")
    candidate = _skill(tmp_path, "candidate.md", "1. Other.")
    held = select_held_out("it-unscorable")
    runner = ScriptedRunner({
        b: (Outcome(exit_code=None) if b == held[0] else Outcome(exit_code=0))
        for b in held
    })

    result = run_gate(current, candidate, runner=runner,
                      training_session_ids=TRAINING_IDS, iteration_id="it-unscorable")

    assert result.unscorable >= 2, "unscorable executions were not tracked"
    # The remaining 3 of 4 blueprints passed for both skills.
    assert result.current_score == 1.0
    assert result.candidate_score == 1.0


def test_the_score_is_undefined_when_nothing_could_be_scored(tmp_path):
    current = _skill(tmp_path, "current.md")
    candidate = _skill(tmp_path, "candidate.md", "1. Other.")
    runner = ScriptedRunner({b: Outcome(exit_code=None) for b in select_held_out("it-none")})

    result = run_gate(current, candidate, runner=runner,
                      training_session_ids=TRAINING_IDS, iteration_id="it-none")

    assert result.current_score is None and result.candidate_score is None
    assert result.decision == DECISION_REJECTED, (
        "a gate that could score nothing must not accept"
    )


# ---------------------------------------------------------------------------
# Disjointness
# ---------------------------------------------------------------------------
def test_overlap_between_training_and_held_out_fails_loudly(tmp_path):
    """The structural guarantee, asserted rather than argued."""
    current = _skill(tmp_path, "current.md")
    candidate = _skill(tmp_path, "candidate.md", "1. Other.")
    # Every fresh execution reuses a training session identifier.
    runner = ScriptedRunner({
        b: Outcome(exit_code=0, session_id="train-1")
        for b in select_held_out("it-overlap")
    })

    with pytest.raises(GateError, match="disjoint|overlap"):
        run_gate(current, candidate, runner=runner,
                 training_session_ids=TRAINING_IDS, iteration_id="it-overlap")


def test_disjoint_evidence_scores_normally(tmp_path):
    current = _skill(tmp_path, "current.md")
    candidate = _skill(tmp_path, "candidate.md", "1. Other.")
    runner = ScriptedRunner({
        b: Outcome(exit_code=0, session_id=f"fresh-{b}")
        for b in select_held_out("it-disjoint")
    })

    result = run_gate(current, candidate, runner=runner,
                      training_session_ids=TRAINING_IDS, iteration_id="it-disjoint")

    assert result.disjoint is True
