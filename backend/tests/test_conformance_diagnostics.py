"""Conformance diagnostics — the diagnostic channel (the INSTRUMENT, not the optimizer).

**Why this module exists first.** CoEvoSkills (COLM 2026) reached 71.1 on
SkillsBench with reflective skill evolution, but its own ablation shows that
replacing the diagnostic verifier with an opaque pass/fail oracle drops it to
**41.1**, while removing evolution entirely scores **42.4**. A loop with only a
binary verifier is statistically indistinguishable from no loop at all. The
diagnostic channel is therefore worth more than the loop that consumes it, and is
built and measured first.

**The seam:** ``diagnose(artifacts) -> ConformanceReport``. Deterministic and
model-free, so it costs nothing to run and cannot be talked into a verdict. It
reuses the existing merge layer for both validator families rather than
re-deriving their union, so it cannot drift from the gate that already enforces
them.

**Why a histogram and not just a score.** A score says how bad a session was; it
does not say what to change. ``PRINCIPLE_I_LAYER_ISOLATION`` firing on three
artifacts is actionable evidence about a recurring procedural defect; "score 55"
is not. The histogram is the part a curator can consume.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.conformance_diagnostics import diagnose  # noqa: E402
from tests.fixtures import fake_model as fm  # noqa: E402

CORPUS_DIR = REPO_ROOT / "backend" / "tests" / "fixtures" / "baseline_blueprints"
MINIMAL = "minimal"


def _blueprint(name: str = MINIMAL) -> dict:
    return json.loads((CORPUS_DIR / f"{name}.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Slice 1 — the report exists and names the defect
# ---------------------------------------------------------------------------
def test_a_layering_violation_is_reported_by_rule_id():
    artifacts = fm.violating_artifacts("LAYER_ISOLATION", _blueprint())

    report = diagnose(artifacts)

    rule_ids = {v.rule_id for v in report.violations}
    assert "PRINCIPLE_I_LAYER_ISOLATION" in rule_ids, (
        f"the layer-isolation rule did not reach the report; got {sorted(rule_ids)}"
    )


def test_a_violating_artifact_set_scores_below_a_clean_one():
    blueprint = _blueprint()
    clean = fm.compliant_artifacts("CONTROLLER", blueprint)
    dirty = fm.violating_artifacts("LAYER_ISOLATION", blueprint)

    clean_report = diagnose(clean)
    dirty_report = diagnose(dirty)

    assert clean_report.score > dirty_report.score, (
        f"a violating set ({dirty_report.score}) did not score below a compliant "
        f"one ({clean_report.score})"
    )


# ---------------------------------------------------------------------------
# Slice 2 — the report is actionable and trustworthy as an optimizer input
# ---------------------------------------------------------------------------
def test_the_histogram_names_which_rules_fired_and_how_often():
    """A score says a session went badly; it does not say what to change."""
    artifacts = fm.violating_artifacts("LAYER_ISOLATION", _blueprint())

    report = diagnose(artifacts)

    assert report.rule_histogram, "the report carried no rule histogram"
    assert sum(report.rule_histogram.values()) == len(report.violations)
    assert "PRINCIPLE_I_LAYER_ISOLATION" in report.rule_histogram
    assert report.rule_histogram["PRINCIPLE_I_LAYER_ISOLATION"] >= 1
    assert "PRINCIPLE_I_LAYER_ISOLATION" in report.rule_ids


def test_every_violation_kind_is_distinguishable_by_rule_id():
    """The channel must resolve the whole rule vocabulary, not just one rule.

    A channel that collapses distinct defects into one bucket cannot tell a
    curator which skill to revise.
    """
    blueprint = _blueprint()
    seen = {}
    for kind in sorted(fm.VIOLATION_BUILDERS):
        report = diagnose(fm.violating_artifacts(kind, blueprint))
        assert report.violations, f"{kind} produced no diagnostic at all"
        seen[kind] = report.rule_ids

    # Distinct defect kinds must not all collapse onto a single rule id.
    flattened = {rid for ids in seen.values() for rid in ids}
    assert len(flattened) > 1, f"every violation kind collapsed to {flattened}"
    # And at least the four constitutional rules must be individually reachable.
    assert "PRINCIPLE_I_LAYER_ISOLATION" in seen["LAYER_ISOLATION"]
    assert "PRINCIPLE_II_IMMUTABLE_DTOS" in seen["CONTRACT_IMMUTABILITY"]


def test_the_report_is_deterministic():
    """A judge that drifts would let a curator 'improve' by judging differently."""
    artifacts = fm.violating_artifacts("LAYER_ISOLATION", _blueprint())

    first = diagnose(artifacts)
    second = diagnose(artifacts)

    assert first.to_dict() == second.to_dict(), (
        "two diagnoses of identical input disagreed; an optimizer fed this "
        "channel could not tell its own effect from the judge's noise"
    )


def test_the_score_floors_at_zero_rather_than_going_negative():
    """Enough critical findings must not produce a negative score."""
    violations = tuple(
        v for v in diagnose(fm.violating_artifacts("LAYER_ISOLATION", _blueprint())).violations
    )
    assert violations
    from app.services.conformance_diagnostics import score_for

    many = violations * 20
    assert score_for(many) == 0


def test_a_clean_set_is_not_blocking_and_scores_full():
    blueprint = _blueprint()
    report = diagnose(fm.compliant_artifacts("SCAFFOLDER", blueprint))

    assert report.score == 100, f"a compliant set scored {report.score}: {report.to_dict()}"
    assert report.blocking is False
    assert report.rule_histogram == {}
