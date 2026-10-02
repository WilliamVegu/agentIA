"""Eviction with an evidence floor (decision D4, feature 015).

**Contract**: ``specs/015-diagnostic-skill-evolution/contracts/evolution-round.md``
(decision rules 2 and 5; FR-012, FR-017)

A skill library that can only grow degrades until *injecting a skill scores worse
than injecting nothing* (arXiv:2605.22148), and the repair is contribution-based
eviction. This module is the repair, and it is deliberately the smallest possible
one, because the removal decision is the operation that decides whether the set
stays usable at all.

**Two conditions, both required.** A skill leaves the set only when its measured
contribution is **sufficient** *and* **below the floor**. "We could not prove it
helps" is explicitly not grounds for removal: with noisy measurement, conflating it
with "it hurts" converts measurement noise into removals. Operationally that means
:func:`skills_to_evict` reads
:attr:`~app.services.skill_contribution.ContributionMeasurement.removable`, which
already requires both.

**The floor is not a parameter of the round.** It is the module constant
:data:`EVIDENCE_FLOOR`, re-exported from the measurement module so there is one
definition. A round cannot pass its own floor, because a round able to lower the bar
for its own removals is a round that can manufacture them (FR-014: the judge is out
of reach). The add-only behaviour this replaces is the worst measured configuration:
add-only 47.0 against 59.0 for add + remove + rewrite (arXiv:2605.29440).
"""

from __future__ import annotations

from typing import Iterable, List, Sequence

from app.services.skill_contribution import (
    EVIDENCE_FLOOR,
    ContributionMeasurement,
)

#: FR-017: a round considers a bounded number of skills. Attribution cost is
#: multiplicative -- skills x tasks -- so an unbounded set makes measurement
#: unaffordable, and a measurement that cannot be run is worse than a smaller set
#: that is.
MAX_SKILLS_PER_ROUND = 4

__all__ = ["EVIDENCE_FLOOR", "MAX_SKILLS_PER_ROUND", "bound_skills", "skills_to_evict"]


def bound_skills(skill_ids: Iterable[str], limit: int = MAX_SKILLS_PER_ROUND) -> List[str]:
    """The skills a round may consider, capped at the documented bound.

    Order is preserved and duplicates collapse, so the bound is applied to distinct
    skills rather than to repeated mentions of one.
    """
    distinct: List[str] = list(dict.fromkeys(str(skill) for skill in skill_ids))
    return distinct[: max(0, int(limit))]


def skills_to_evict(measurements: Sequence[ContributionMeasurement]) -> List[str]:
    """Skills whose measured contribution is sufficient *and* below the floor.

    An abandoned measurement (``error`` set) never removes anything: a measurement
    that could not be taken is not evidence of harm.

    Note what is absent: there is no "not proven to help" branch. A sufficient
    measurement at or above the floor keeps the skill, and an insufficient one keeps
    it too. That is the whole point of the floor.
    """
    doomed: List[str] = []
    for measurement in measurements:
        if getattr(measurement, "error", None):
            continue
        if measurement.removable:
            doomed.append(measurement.skill_id)
    return doomed
