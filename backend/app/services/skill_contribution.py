"""Per-skill contribution by leave-one-out (decision D3, feature 015).

**Contract**: ``specs/015-diagnostic-skill-evolution/contracts/contribution-measurement.md``

This is the primitive that converts *"the output got better"* into *"this rule was
responsible"*, and it is the one the evidence base says must exist before a loop is
worth running: a single monolithic skill document cannot be attributed, because
co-applied rules confound one another.

The shape is deliberately training-free and is exactly
``delta(task, skill) = r(task, skill) - r(task, absent)``: replay the identical task
set with the skill present and with it absent, and compare. Both arms run the
**same** tasks, because a comparison across different task sets is meaningless while
still producing a number.

Three rules carry the honesty of the result, and each closes a way it could lie:

* **Repeats are not evidence.** One task measured N times is one task.
* **Insufficiency is a result.** Below the arithmetic floor no outcome can be
  significant, and the measurement says so rather than presenting a delta.
* **No removal on "not proven".** Removal needs a *sufficient* measurement below
  the floor. Absence of demonstrated benefit is not evidence of harm (D4).

The inferential basis is the **exact two-sided sign test**, not a paired t-test. It
assumes nothing about the distribution of per-task differences -- which this platform
cannot check at these sample sizes -- and it is the test its own arithmetic floor is
stated in (the reports cite n=4 -> p=0.125, n=5 -> p=0.0625, n=6 -> 0.03125).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import comb
from statistics import mean
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

#: The stated evidence floor. A skill is removable only on a **sufficient**
#: measurement whose delta is strictly below this.
#:
#: Zero is the minimal defensible floor: it asks for evidence of *harm*, not merely
#: absence of proven benefit (D4). The `sufficient` flag is what stops noise from
#: manufacturing that evidence -- without it, a floor of zero would remove every
#: skill whose contribution happened to measure slightly negative in one run.
EVIDENCE_FLOOR = 0.0

#: The largest exact two-sided sign-test p-value that counts as a result.
SIGNIFICANCE = 0.05


@dataclass(frozen=True)
class TaskOutcome:
    """One arm's result for one task.

    ``measure`` is the conformance measure on a **higher-is-better** scale. The
    platform records ``density`` (penalty per 100 artifacts, lower is better), so the
    wiring negates it with :func:`quality_from_density`. Doing the inversion in one
    named place is what stops a sign error from turning "the skill helps" into "the
    skill hurts" in a removal decision.
    """

    evaluable: bool
    measure: float = 0.0


def quality_from_density(density: float) -> float:
    """The platform's size-comparable density, as a higher-is-better measure."""
    return -float(density)


@dataclass(frozen=True)
class ContributionMeasurement:
    """What one (skill, task set) measurement concluded."""

    skill_id: str
    #: Observed difference, with the skill present minus absent. ``None`` when it
    #: could not be computed at all. Present-but-insufficient is a valid state: the
    #: observation is reported, and :attr:`improvement` still refuses to call it one.
    delta: Optional[float]
    #: **Distinct** tasks behind the delta. Repeats add nothing (FR-009).
    distinct_tasks: int
    #: Smallest fraction of the task set an exact sign test can call significant at
    #: this size. ``None`` when no fraction can -- the arithmetic floor.
    min_detectable_effect: Optional[float]
    #: Whether the evidence supports any conclusion (FR-008).
    sufficient: bool
    #: The evidence floor this measurement was taken against.
    floor: float = EVIDENCE_FLOOR
    with_skill: Tuple[float, ...] = ()
    without_skill: Tuple[float, ...] = ()
    #: Tasks evaluable in one arm but not the other. Excluded from both arms and
    #: counted in neither: an asymmetric task set is not a comparison.
    excluded_tasks: Tuple[str, ...] = ()
    #: Populated when the measurement was abandoned (a runner raised).
    error: Optional[str] = None

    @property
    def improvement(self) -> Optional[float]:
        """The delta, but only when the evidence supports calling it an improvement.

        This is the property a round must read. ``delta`` alone must never be
        presented as a gain (FR-016): at this scale it is usually noise.
        """
        if not self.sufficient or self.delta is None or self.delta <= 0:
            return None
        return self.delta

    @property
    def removable(self) -> bool:
        """Removal requires **both** sufficiency and a delta below the floor (FR-012)."""
        return self.sufficient and self.delta is not None and self.delta < self.floor

    @property
    def conclusion(self) -> str:
        """A one-line, non-overstating summary. Never says "improved" without evidence."""
        if self.error:
            return f"measurement abandoned: {self.error}"
        if not self.sufficient:
            # The observation is reported AND marked as not a result. Hiding it
            # would lose information; presenting it without the caveat is the
            # failure this property exists to prevent.
            observed = (
                f"observed delta {self.delta:+.3f} is not a result at this size"
                if self.delta is not None
                else "no delta could be computed"
            )
            return (
                f"insufficient evidence: {self.distinct_tasks} distinct task(s) cannot "
                f"reach p<{SIGNIFICANCE} under any outcome; {observed}"
            )
        if self.removable:
            return f"contribution {self.delta:+.3f} is below the floor {self.floor:+.3f}"
        if self.improvement is not None:
            return f"contribution {self.improvement:+.3f} above the floor"
        return f"contribution {self.delta:+.3f} at or above the floor"


def min_detectable_effect(distinct_tasks: int) -> Optional[float]:
    """Smallest fraction of the task set an exact sign test can call significant.

    Computed, not tabulated: find the smallest number of consistently-signed tasks
    whose exact two-sided sign-test p-value falls below 0.05, and express it as a
    fraction of the task set. At 6 tasks that is all six (2 * 0.5^6 = 0.03125); at
    10 it is nine (0.0215); at 5 **no** fraction works (the best is 2 * 0.5^5 =
    0.0625), which is the arithmetic floor this platform's reports cite.

    Returns ``None`` when no outcome can reach significance, which is what makes
    :attr:`ContributionMeasurement.sufficient` false.
    """
    n = int(distinct_tasks)
    if n <= 0:
        return None
    total = 2 ** n
    for k in range(1, n + 1):
        tail = sum(comb(n, i) for i in range(k, n + 1))
        if (2 * tail) / total < SIGNIFICANCE:
            return k / n
    return None


def _as_outcome(value: Any) -> TaskOutcome:
    """Accept a TaskOutcome, a mapping, or a bare number for one arm's result."""
    if isinstance(value, TaskOutcome):
        return value
    if isinstance(value, Mapping):
        measure = value.get("measure")
        if measure is None:
            measure = value.get("density", value.get("score", 0.0))
        return TaskOutcome(evaluable=bool(value.get("evaluable", True)), measure=float(measure or 0.0))
    if isinstance(value, (int, float)):
        return TaskOutcome(evaluable=True, measure=float(value))
    raise TypeError(
        f"a task runner must return a TaskOutcome, a mapping or a number; got {type(value).__name__}"
    )


def measure_contribution(
    skill_id: str,
    task_set: Sequence[str],
    run_with: Callable[[str], Any],
    run_without: Callable[[str], Any],
    *,
    floor: float = EVIDENCE_FLOOR,
) -> ContributionMeasurement:
    """Measure one skill's contribution by replaying the task set with and without it.

    ``run_with`` / ``run_without`` are **injected runners**, as in feature 014: a
    parameter and never a monkeypatch, so a refactor cannot silently stop injecting
    and leave the suite executing real sessions. Each takes a task identifier and
    returns that arm's outcome (see :func:`_as_outcome`).

    The task set is de-duplicated before anything runs: repeated runs of one task are
    not independent observations, and counting them would let a round manufacture
    significance by repeating itself.
    """
    tasks: List[str] = list(dict.fromkeys(str(task) for task in task_set))

    with_values: List[float] = []
    without_values: List[float] = []
    excluded: List[str] = []

    try:
        for task in tasks:
            with_outcome = _as_outcome(run_with(task))
            without_outcome = _as_outcome(run_without(task))
            if not with_outcome.evaluable or not without_outcome.evaluable:
                # A task evaluable in one arm only is dropped from both. Keeping it
                # would compare different task sets and still produce a number.
                excluded.append(task)
                continue
            with_values.append(with_outcome.measure)
            without_values.append(without_outcome.measure)
    except Exception as exc:
        # Contract: a runner raising abandons the measurement; the round records it.
        return ContributionMeasurement(
            skill_id=skill_id,
            delta=None,
            distinct_tasks=0,
            min_detectable_effect=None,
            sufficient=False,
            floor=floor,
            excluded_tasks=tuple(excluded),
            error=f"{type(exc).__name__}: {exc}",
        )

    distinct = len(with_values)
    delta = (mean(with_values) - mean(without_values)) if distinct else None
    detectable = min_detectable_effect(distinct)

    return ContributionMeasurement(
        skill_id=skill_id,
        delta=delta,
        distinct_tasks=distinct,
        min_detectable_effect=detectable,
        sufficient=detectable is not None,
        floor=floor,
        with_skill=tuple(with_values),
        without_skill=tuple(without_values),
        excluded_tasks=tuple(excluded),
    )


def measurements_as_dicts(measurements: Sequence[ContributionMeasurement]) -> List[Dict[str, Any]]:
    """Serialisable form, for the round record's ``measurements`` field."""
    return [
        {
            "skill_id": m.skill_id,
            "delta": m.delta,
            "distinct_tasks": m.distinct_tasks,
            "min_detectable_effect": m.min_detectable_effect,
            "sufficient": m.sufficient,
            "floor": m.floor,
            "excluded_tasks": list(m.excluded_tasks),
            "error": m.error,
            "conclusion": m.conclusion,
        }
        for m in measurements
    ]
