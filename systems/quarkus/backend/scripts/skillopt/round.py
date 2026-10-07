"""One evolution round, decided from recorded evidence (feature 015).

**Contract**: ``specs/015-diagnostic-skill-evolution/contracts/evolution-round.md``

The round is the piece that makes the proposal *run*: it reads the recorded
diagnostics, reflects a bounded edit set out of the rules that actually recurred,
measures each skill's contribution by leave-one-out, and decides. Feature 014's
strict-improvement gate is retained, but only as a **regression veto** -- a binary
comparison over a handful of tasks cannot separate a real change from variance, so
it no longer decides whether a round produced a result (D9).

**One record, always.** Every exit path writes exactly one row, including the
failure path. A round that crashed without a record is indistinguishable from one
that never ran, and at this scale the most common outcome is
``NO_MEASURABLE_CHANGE`` -- which must be *recorded*, not inferred from a missing
row.

**Every seam is a parameter.** The collector, the reflector, the applier, the
per-skill measurement and the guardrail are all injected. That is feature 014's
discipline, kept: a monkeypatch would let a refactor silently stop injecting and
leave the suite executing real sessions that spend real money.

**What the round cannot reach.** It cannot alter the counting rules, the severity
weights or the evidence floor: the floor is a module constant in
``skillopt.currency``, and this module reads it rather than accepting it. A round
able to lower the bar for its own removals is a round that can manufacture them
(FR-014 / SC-010).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from app.models.skillopt import (
    DECISION_ACCEPTED,
    DECISION_ERROR,
    DECISION_NO_FAILURES,
    DECISION_NO_MEASURABLE_CHANGE,
    DECISION_NO_SESSIONS,
    DECISION_REJECTED,
    DECISION_REMOVED,
    start_run,
    write_run,
)
from app.services.skill_contribution import (
    ContributionMeasurement,
    measurements_as_dicts,
)
from scripts.skillopt.collect import (
    COLLECTION_NO_FAILURES,
    COLLECTION_NO_SESSIONS,
    collect_outcomes,
)
from scripts.skillopt.currency import (
    MAX_SKILLS_PER_ROUND,
    bound_skills,
    skills_to_evict,
)


@dataclass
class RoundResult:
    """What a round did. Serialisable; never claims more than the evidence supports."""

    decision: str
    measurements: List[Dict[str, Any]] = field(default_factory=list)
    removed: List[str] = field(default_factory=list)
    applied: List[Dict[str, Any]] = field(default_factory=list)
    rejected: List[Dict[str, Any]] = field(default_factory=list)
    held_out: List[str] = field(default_factory=list)
    current_score: Optional[float] = None
    candidate_score: Optional[float] = None
    error: Optional[str] = None
    run_id: Optional[int] = None
    note: str = ""


def run_round(
    *,
    skills: Sequence[str],
    task_set: Sequence[str],
    collector: Callable[[], Dict[str, Any]] = collect_outcomes,
    reflector: Optional[Callable[[Any, List[Dict[str, Any]]], List[Dict[str, Any]]]] = None,
    load_skill: Optional[Callable[[str], Any]] = None,
    apply_edits: Optional[Callable[[Any, List[Dict[str, Any]]], Any]] = None,
    measure_skill: Optional[Callable[[str], ContributionMeasurement]] = None,
    guardrail: Optional[Callable[[Any, Any], Any]] = None,
    max_skills: int = MAX_SKILLS_PER_ROUND,
    iteration_id: str = "round",
) -> RoundResult:
    """Run one round and record exactly one outcome.

    The path taken, in the contract's order:

    ``collect`` -> no sessions -> ``NO_SESSIONS``
                -> no failures -> ``NO_FAILURES``
                -> reflect -> apply -> measure
                   -> any removable          -> ``REMOVED``
                   -> all insufficient       -> ``NO_MEASURABLE_CHANGE``
                   -> otherwise              -> guardrail -> ``ACCEPTED``/``REJECTED``
    Any exception -> ``ERROR`` (recorded, with the exception).
    """
    started = start_run()
    bounded = bound_skills(skills, limit=max_skills)

    try:
        collected = collector()
        status = collected.get("status")
        if status == COLLECTION_NO_SESSIONS:
            return _finish(started, RoundResult(
                decision=DECISION_NO_SESSIONS,
                note="nothing recorded to learn from",
            ))

        failures = list(collected.get("failures") or [])
        if status == COLLECTION_NO_FAILURES or not failures:
            return _finish(started, RoundResult(
                decision=DECISION_NO_FAILURES,
                note="sessions recorded and all clean — the set is working",
            ))

        # --- propose ------------------------------------------------------
        applied: List[Dict[str, Any]] = []
        rejected: List[Dict[str, Any]] = []
        candidate_skill = None
        if reflector is not None and load_skill is not None and apply_edits is not None:
            skill = load_skill(bounded[0]) if bounded else None
            if skill is not None:
                edits = reflector(skill, failures)
                application = apply_edits(skill, edits)
                applied = list(getattr(application, "applied", []) or [])
                rejected = list(getattr(application, "rejected", []) or [])
                # ApplyResult names it `candidate`; accept `document` too so a
                # differently-shaped applier cannot silently yield None here.
                candidate_skill = getattr(application, "candidate", None) or getattr(
                    application, "document", None
                )

        # --- measure contribution (leave-one-out) --------------------------
        measurements: List[ContributionMeasurement] = []
        if measure_skill is not None:
            measurements = [measure_skill(skill_id) for skill_id in bounded]

        # --- decide --------------------------------------------------------
        doomed = skills_to_evict(measurements)
        if doomed:
            return _finish(started, RoundResult(
                decision=DECISION_REMOVED,
                measurements=measurements_as_dicts(measurements),
                removed=doomed,
                applied=applied,
                rejected=rejected,
                note="at least one skill measured below the evidence floor",
            ))

        if measurements and not any(m.sufficient for m in measurements):
            # The expected outcome at this scale, and a result in its own right.
            return _finish(started, RoundResult(
                decision=DECISION_NO_MEASURABLE_CHANGE,
                measurements=measurements_as_dicts(measurements),
                applied=applied,
                rejected=rejected,
                note=(
                    "the evidence cannot support a conclusion at this task count; "
                    "nothing was changed and no improvement is claimed"
                ),
            ))

        # --- guardrail (regression veto, not the objective) ----------------
        if guardrail is not None and candidate_skill is not None and bounded:
            verdict = guardrail(load_skill(bounded[0]), candidate_skill)
            decision = getattr(verdict, "decision", DECISION_REJECTED)
            return _finish(started, RoundResult(
                decision=DECISION_ACCEPTED if decision == DECISION_ACCEPTED else DECISION_REJECTED,
                measurements=measurements_as_dicts(measurements),
                applied=applied,
                rejected=rejected,
                held_out=list(getattr(verdict, "held_out_blueprints", []) or []),
                current_score=getattr(verdict, "current_score", None),
                candidate_score=getattr(verdict, "candidate_score", None),
                note="guardrail verdict; it can veto, never confer a result",
            ))

        return _finish(started, RoundResult(
            decision=DECISION_NO_MEASURABLE_CHANGE,
            measurements=measurements_as_dicts(measurements),
            applied=applied,
            rejected=rejected,
            note="no measurement and no guardrail were supplied; nothing was decided",
        ))

    except Exception as exc:
        return _finish(started, RoundResult(
            decision=DECISION_ERROR,
            error=f"{type(exc).__name__}: {exc}",
            note="the round failed; the record carries the exception",
        ))


def _finish(started, result: RoundResult) -> RoundResult:
    """Write the single round record and return the result."""
    result.run_id = write_run(
        started_at=started,
        n_training=len(result.applied) or None,
        n_held_out=len(result.held_out) or None,
        current_score=result.current_score,
        candidate_score=result.candidate_score,
        decision=result.decision,
        edits=result.applied,
        error=result.error,
        measurements=result.measurements,
        removed=result.removed,
    )
    return result
