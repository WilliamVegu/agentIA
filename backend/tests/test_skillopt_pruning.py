"""Eviction with an evidence floor (feature 015, D4 / FR-012 / FR-017).

The removal decision is the one that decides whether a skill library stays usable,
so it gets its own file. The behaviour under test is mostly an *absence*: the
module must refuse to remove a skill on "we could not prove it helps", because with
noisy measurement that converts noise into removals.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.skill_contribution import (  # noqa: E402
    EVIDENCE_FLOOR,
    ContributionMeasurement,
)
from scripts.skillopt.currency import (  # noqa: E402
    MAX_SKILLS_PER_ROUND,
    bound_skills,
    skills_to_evict,
)


def measurement(skill_id, delta, *, sufficient=True, error=None, distinct=8):
    """A measurement with the fields the eviction decision reads."""
    return ContributionMeasurement(
        skill_id=skill_id,
        delta=delta,
        distinct_tasks=distinct,
        min_detectable_effect=1.0 if sufficient else None,
        sufficient=sufficient,
        floor=EVIDENCE_FLOOR,
        error=error,
    )


# ---------------------------------------------------------------------------
# The bound (FR-017)
# ---------------------------------------------------------------------------
def test_skills_are_bounded_per_round():
    many = [f"skill-{i}" for i in range(20)]

    bounded = bound_skills(many)

    assert len(bounded) == MAX_SKILLS_PER_ROUND, (
        "attribution cost is skills x tasks; an unbounded set makes the measurement "
        "unaffordable, and an unaffordable measurement is worse than a smaller one"
    )
    assert bounded == many[:MAX_SKILLS_PER_ROUND]


def test_the_bound_counts_distinct_skills():
    assert bound_skills(["a", "a", "b", "a", "c"], limit=3) == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# What evicts
# ---------------------------------------------------------------------------
def test_a_sufficient_below_floor_skill_is_evicted():
    doomed = skills_to_evict([
        measurement("helps", 2.0),
        measurement("hurts", -1.5),
    ])

    assert doomed == ["hurts"], "a measurably harmful skill was retained"


def test_a_sufficient_at_floor_skill_is_retained():
    assert skills_to_evict([measurement("neutral", EVIDENCE_FLOOR)]) == []


# ---------------------------------------------------------------------------
# What must NOT evict -- the point of the floor
# ---------------------------------------------------------------------------
def test_not_proven_to_help_does_not_evict():
    """The D4 distinction: 'no proven benefit' is not 'it hurts'."""
    insufficient = measurement("unproven", -3.0, sufficient=False)

    assert skills_to_evict([insufficient]) == [], (
        "an insufficient measurement drove a removal; at this sample size that is "
        "measurement noise deciding the skill set"
    )


def test_an_abandoned_measurement_never_evicts():
    abandoned = measurement("broken", None, sufficient=False, error="RuntimeError: boom")

    assert skills_to_evict([abandoned]) == []


def test_no_measurements_means_no_removals():
    """An empty set is a valid outcome, not an error (FR-015)."""
    assert skills_to_evict([]) == []


# ---------------------------------------------------------------------------
# The judge is out of reach (FR-014 / SC-010)
# ---------------------------------------------------------------------------
def test_the_floor_is_not_a_parameter_of_the_round():
    """A round able to lower its own bar for removals can manufacture them.

    Asserted structurally rather than by "trying" to pass a floor: the absence of
    the parameter is what makes the attempt impossible, and a test that passed one
    would be testing a signature it then relies on.
    """
    parameters = set(inspect.signature(skills_to_evict).parameters)

    assert parameters == {"measurements"}, (
        f"skills_to_evict accepts {sorted(parameters - {'measurements'})}; a floor or "
        f"a counting rule reachable from a round is the exploit SC-010 forbids"
    )
