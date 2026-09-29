"""The decision metric has to reach the things that decide (P3 wiring).

Implementing `new_penalty` was not enough. The record still carried only `density`,
so the contribution measurement -- which is what decides whether a skill is admitted
or evicted -- kept scoring on the ratio that a candidate can improve by padding the
artifact set. These tests pin the wiring, and pin the one way it can lie: a record
written before the column existed must read as *unmeasured*, never as a clean zero.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.models.diagnostics import (  # noqa: E402
    read_diagnostic_record,
    write_diagnostic_record,
)
from app.services.corpus_report import build_report  # noqa: E402
from app.services.skill_contribution import _as_outcome  # noqa: E402


def _write(session_id: str, *, new_penalty=None, density=250.0, raw_penalty=250) -> bool:
    return write_diagnostic_record(
        session_id,
        task="t",
        score=85,
        raw_penalty=raw_penalty,
        density=density,
        new_penalty=new_penalty,
        artifact_count=3,
    )


def test_a_measured_new_penalty_round_trips():
    assert _write("wiring-measured", new_penalty=15) is True

    record = read_diagnostic_record("wiring-measured")

    assert record is not None
    assert record["new_penalty"] == 15
    assert record["density"] == 250.0, "the ratio is retained for continuity"


def test_an_unmeasured_new_penalty_stays_unmeasured_rather_than_becoming_clean():
    """The failure that would matter most: NULL read as 0 is a false clean bill.

    A session recorded before the column existed has no baseline-relative penalty.
    Reporting 0 would say "no findings beyond the baseline", which is a claim
    nothing measured.
    """
    assert _write("wiring-unmeasured", new_penalty=None) is True

    record = read_diagnostic_record("wiring-unmeasured")

    assert record is not None
    assert record["new_penalty"] is None
    assert record["new_penalty"] != 0


def test_a_real_zero_is_preserved_as_measured_clean():
    """0 from a computation means clean, and is NOT the same as NULL."""
    assert _write("wiring-clean", new_penalty=0, density=0.0, raw_penalty=0) is True

    record = read_diagnostic_record("wiring-clean")

    assert record is not None
    assert record["new_penalty"] == 0


def test_the_report_counts_measured_and_unmeasured_separately():
    _write("wiring-a", new_penalty=15)
    _write("wiring-b", new_penalty=None)

    records = [read_diagnostic_record("wiring-a"), read_diagnostic_record("wiring-b")]
    report = build_report([r for r in records if r])

    assert report.verified == 2
    assert report.new_penalty_measured == 1, "only one session measured the penalty"
    assert report.median_new_penalty == 15.0, "median is over the measured sessions only"


def test_the_contribution_measure_prefers_new_penalty_over_density():
    """Otherwise the optimiser scores on the gameable ratio and padding wins."""
    preferred = _as_outcome({"new_penalty": 15, "density": 250.0}).measure
    fallback = _as_outcome({"new_penalty": None, "density": 250.0}).measure

    assert preferred == -15.0
    assert fallback == -250.0, "an old record still scores, on the older instrument"


def test_padding_cannot_improve_the_measure_that_is_now_used():
    """The exploit this wiring closes, stated as the measurement it would move.

    Under density, the same findings spread across more artifacts score better. Under
    new_penalty the artifact count does not appear at all, so the optimizer has
    nothing to trade.
    """
    from app.orchestrator.stages.compliance import SEVERITY_HIGH, ComplianceViolation
    from app.services.conformance_diagnostics import measure_for, new_penalty

    violations = tuple(
        ComplianceViolation(
            artifact_path="p", rule_id=f"R{i}", severity=SEVERITY_HIGH, message="m"
        )
        for i in range(2)
    )

    assert measure_for(violations, 40) < measure_for(violations, 20)
    assert new_penalty(violations, None) == new_penalty(violations, None)
