"""The held-out gate (FR-006, FR-006a, FR-007 / T015).

Scores **both** skills on the **same** fresh executions and accepts the candidate
only on a **strict** improvement.

Four properties, each closing a silent failure mode:

1. **Fresh execution, not recorded verdicts.** Training evidence is recorded
   sessions produced under the *previous* skill; a recorded verdict cannot be
   re-attributed to the candidate. The gate therefore executes.
2. **A fallback-marked execution never passes**, even at exit code zero. Under
   permissive mode a synthetic verification returns success without compiling
   anything, so scoring on the exit code alone would reward a skill for making the
   verifier give up — and a text optimiser will find that exploit, because
   "improve the score" is exactly what it is asked to do.
3. **Both skills on the identical sample.** Scoring them on different samples would
   produce a comparison that is meaningless while still yielding a number.
4. **Disjointness asserted, not argued.** Recorded sessions predate the candidate,
   so the two sets cannot overlap *today*; the assertion is what keeps that true
   when the code changes.

The runner is a **parameter**, never a monkeypatch: the seam is explicit, so a
refactor cannot silently stop injecting and leave the suite running real sessions.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

#: The held-out task set. The five fixtures frozen by feature 011 — deliberately
#: NOT new fixtures, because a task set authored alongside the thing it evaluates
#: measures the author.
BASELINE_BLUEPRINTS = ("pair-a", "pair-b", "minimal", "multi-entity", "constrained")

#: M. Four of five, leaving one as a rotation buffer so successive iterations are
#: not scored on an identical fixed exam.
HELD_OUT_DEFAULT = 4

DECISION_ACCEPTED = "ACCEPTED"
DECISION_REJECTED = "REJECTED"


class GateError(RuntimeError):
    """The gate refused to score — an overlap, or a broken precondition."""


@dataclass
class ExecutionResult:
    blueprint: str
    session_id: Optional[str] = None
    #: ``None`` means the execution could not be scored at all — no build ran, no
    #: workspace. Distinct from a failure, and excluded from the denominator.
    exit_code: Optional[int] = None
    fallback_used: bool = False
    skill: str = ""
    detail: str = ""


@dataclass
class GateResult:
    current_score: Optional[float]
    candidate_score: Optional[float]
    decision: str
    held_out_blueprints: List[str]
    executions: List[ExecutionResult] = field(default_factory=list)
    unscorable: int = 0
    disjoint: bool = True


def select_held_out(iteration_id: str, m: int = HELD_OUT_DEFAULT) -> List[str]:
    """Deterministically choose which blueprints are held out.

    Derived from the iteration's identity rather than from the clock or process
    randomness, so re-running an iteration selects the same set and the comparison
    reproduces (SC-010).
    """
    ordered = list(BASELINE_BLUEPRINTS)
    if m >= len(ordered):
        return ordered
    digest = hashlib.sha256(str(iteration_id).encode("utf-8")).digest()
    # Rotate the excluded blueprint by the digest, leaving exactly one out.
    excluded = digest[0] % len(ordered)
    return [b for index, b in enumerate(ordered) if index != excluded][:m]


def is_pass(execution: ExecutionResult) -> Optional[bool]:
    """Whether an execution counts as a pass. ``None`` when it could not be scored.

    A pass requires a real zero exit code **and** no synthetic verification. The
    second clause is the one that matters: a fallback returns zero without building.
    """
    if execution.exit_code is None:
        return None
    return execution.exit_code == 0 and not execution.fallback_used


def _score(executions: Sequence[ExecutionResult]) -> Optional[float]:
    scorable = [e for e in executions if is_pass(e) is not None]
    if not scorable:
        return None
    passed = sum(1 for e in scorable if is_pass(e))
    return passed / len(scorable)


def run_gate(
    current_skill: Path,
    candidate_skill: Path,
    *,
    runner: Callable[[str, Path], ExecutionResult],
    training_session_ids: Sequence[str] = (),
    iteration_id: str = "iteration",
    m: int = HELD_OUT_DEFAULT,
) -> GateResult:
    """Score both skills on the same held-out blueprints and decide.

    `runner` is the injectable seam: it executes one fresh session for a blueprint
    with the given skill active and returns what happened. Production passes the
    real runner; the suite passes a scripted one.
    """
    held_out = select_held_out(iteration_id, m=m)
    training = set(training_session_ids)

    executions: List[ExecutionResult] = []
    fresh_session_ids: List[str] = []

    for skill_label, skill_path in (("current", current_skill), ("candidate", candidate_skill)):
        for blueprint in held_out:
            outcome = runner(blueprint, Path(skill_path))
            outcome.skill = skill_label
            executions.append(outcome)
            if outcome.session_id:
                fresh_session_ids.append(outcome.session_id)

    # --- disjointness: the structural guarantee, asserted ---------------------
    overlap = training.intersection(fresh_session_ids)
    if overlap:
        raise GateError(
            f"held-out executions are not disjoint from the training evidence: "
            f"{sorted(overlap)} appear in both. The gate would be scoring the candidate "
            f"on the sessions the proposal came from, and nothing in the score would say so."
        )

    current_executions = [e for e in executions if e.skill == "current"]
    candidate_executions = [e for e in executions if e.skill == "candidate"]

    current_score = _score(current_executions)
    candidate_score = _score(candidate_executions)

    if current_score is None or candidate_score is None:
        # Nothing could be scored. A gate that measured nothing must not accept.
        decision = DECISION_REJECTED
    else:
        decision = DECISION_ACCEPTED if candidate_score > current_score else DECISION_REJECTED

    return GateResult(
        current_score=current_score,
        candidate_score=candidate_score,
        decision=decision,
        held_out_blueprints=held_out,
        executions=executions,
        unscorable=sum(1 for e in executions if e.exit_code is None),
        disjoint=True,
    )
