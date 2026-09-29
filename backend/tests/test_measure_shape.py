"""The shape of the conformance measure (decision D6, corrected).

D6 normalised the measure for artifact-set size because a raw finding count "rewards
generating less code". That is true, and the normalisation chosen -- penalty per 100
artifacts -- introduces the mirror-image defect: it rewards generating *more* files,
because extra artifacts dilute the ratio. Both are ratios, and every ratio built from
findings has a denominator a candidate can move.

The tests below pin both halves: first that the density really can be improved by
padding, then that the baseline-relative absolute penalty cannot.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.orchestrator.stages.compliance import (  # noqa: E402
    SEVERITY_HIGH,
    SEVERITY_LOW,
    ComplianceViolation,
)
from app.services.conformance_diagnostics import (  # noqa: E402
    baseline_from_histogram,
    diagnose,
    measure_for,
    new_penalty,
    violations_beyond_baseline,
)


def _violation(rule_id: str, severity: str = SEVERITY_HIGH) -> ComplianceViolation:
    return ComplianceViolation(
        artifact_path="src/main/java/x/Foo.java",
        rule_id=rule_id,
        severity=severity,
        message="test fixture",
    )


def _two_findings():
    return (_violation("PRINCIPLE_I_LAYER_ISOLATION"), _violation("STACK_LOMBOK_RESTRICTION"))


def test_density_is_improved_by_padding_the_artifact_set():
    """The exploit D6 opened, pinned so it cannot be reintroduced by accident.

    The same two findings measure half as dense when the set is twice the size, so
    an optimizer scored on density can lower its number by emitting more files --
    without fixing anything.
    """
    violations = _two_findings()

    small = measure_for(violations, 20)
    padded = measure_for(violations, 40)

    assert padded < small, "density must fall as the same findings are spread thinner"
    assert padded == round(small / 2, 2)


def test_the_absolute_new_penalty_cannot_be_moved_by_artifact_count():
    """The fix: with the denominator gone, neither shrinking nor padding helps.

    ``new_penalty`` does not take an artifact count at all, which is the point --
    there is nothing to trade against the findings.
    """
    violations = _two_findings()
    baseline = baseline_from_histogram({"PRINCIPLE_I_LAYER_ISOLATION": 1})

    # One finding is forgiven by the baseline; the other is charged at its own
    # severity weight. Read the weight rather than restating it, so a future
    # re-weighting does not silently invalidate this test.
    from app.services.conformance_diagnostics import _SEVERITY_PENALTY

    charged = violations_beyond_baseline(violations, baseline)
    assert len(charged) == 1
    assert charged[0].rule_id == "STACK_LOMBOK_RESTRICTION"
    assert new_penalty(violations, baseline) == _SEVERITY_PENALTY[SEVERITY_HIGH]
    # And it is independent of any notion of set size, by construction.
    assert new_penalty(violations, baseline) == new_penalty(violations, baseline)


def test_an_absent_baseline_forgives_nothing():
    """The conservative direction: an unknown baseline must not excuse a finding."""
    violations = _two_findings()
    assert new_penalty(violations, None) == new_penalty(violations, {})
    assert violations_beyond_baseline(violations, None) == violations


def test_the_baseline_forgives_exactly_its_allowance_per_rule():
    violations = (
        _violation("RULE_A"),
        _violation("RULE_A"),
        _violation("RULE_A"),
        _violation("RULE_B"),
    )
    baseline = baseline_from_histogram({"RULE_A": 2})

    beyond = violations_beyond_baseline(violations, baseline)

    assert [v.rule_id for v in beyond] == ["RULE_A", "RULE_B"]
    # An allowance is consumed, not a blanket exemption for the rule.
    assert len(beyond) == 2


def test_the_allowance_is_consumed_in_order_so_results_are_deterministic():
    violations = (_violation("RULE_A", SEVERITY_LOW), _violation("RULE_A", SEVERITY_HIGH))
    baseline = baseline_from_histogram({"RULE_A": 1})

    first = violations_beyond_baseline(violations, baseline)
    second = violations_beyond_baseline(violations, baseline)

    assert first == second
    assert len(first) == 1
    assert first[0].severity == SEVERITY_HIGH, "the surviving finding keeps its identity"


def test_size_floor_is_reported_rather_than_enforced():
    """A one-file set with no findings is not evidence of a clean service.

    Reported as a flag so no existing rate changes meaning silently.
    """
    artifacts = {"src/main/java/x/Foo.java": "class Foo {}"}

    below = diagnose(artifacts, min_artifacts=10)
    above = diagnose(artifacts, min_artifacts=0)

    assert below.size_floor == 10
    assert below.size_floor_met is False
    assert above.size_floor_met is True
    # The floor does not change evaluation: both were evaluated.
    assert below.evaluable is True


def test_diagnose_charges_only_findings_beyond_the_baseline():
    """End to end through the public entry point."""
    artifacts = {"src/main/java/x/Foo.java": "class Foo {}"}
    report = diagnose(artifacts)
    baseline = baseline_from_histogram(report.rule_histogram)

    same = diagnose(artifacts, baseline=baseline)

    assert same.raw_penalty == report.raw_penalty, "the raw penalty is unchanged"
    assert same.new_penalty == 0, "nothing is new relative to itself"
    assert same.baseline_penalty == report.raw_penalty
    assert same.new_violations == ()
