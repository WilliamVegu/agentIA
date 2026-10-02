"""Aggregation and cost-report tests (feature 013, T017).

Covers the reconciliation between a session's calls and its aggregate, the
report's required contents, its determinism, and the exclusion rule that keeps a
session with synthetic verification out of the headline cost figure.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.config import settings  # noqa: E402
from app.cost import aggregate, store  # noqa: E402

SCRIPTS_DIR = REPO_ROOT / "backend" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
from report_session_costs import build_report  # noqa: E402


@pytest.fixture
def cost_db(tmp_path, monkeypatch):
    path = tmp_path / "cost.db"
    monkeypatch.setattr(settings, "COST_STORE_PATH", str(path), raising=False)
    return str(path)


def _call(session_id, index, stage, cost, *, known=True, priced=True, cache_known=True):
    store.write_call_record({
        "call_id": f"{session_id}-{index}",
        "session_id": session_id,
        "stage": stage,
        "provider": "deepseek",
        "model": "deepseek-flash",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "latency_ms": 10,
        "input_tokens": 1000 if known else None,
        "output_tokens": 250 if known else None,
        "cache_hit_input_tokens": None,
        "usage_known": known,
        "cache_basis_known": cache_known,
        "peak": False,
        "priced": priced,
        "cost_usd": cost,
        "pricing_basis": "off_peak/cache-miss-assumed",
    })


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
def test_totals_equal_the_sum_over_the_sessions_calls(cost_db):
    _call("s1", 0, "SCAFFOLDER", 0.0002)
    _call("s1", 1, "DOMAIN", 0.0007)
    _call("s1", 2, "TEST", 0.0001)

    record = aggregate.aggregate_session("s1", "notes", "COMPLETED", "MODEL", False, 12.0)

    assert record["model_calls_count"] == 3
    assert record["total_input_tokens"] == 3000
    assert record["total_output_tokens"] == 750
    assert record["total_cost_usd"] == pytest.approx(0.0010)
    assert record["duration_seconds"] == 12.0


def test_re_aggregation_overwrites_rather_than_double_counts(cost_db):
    _call("s1", 0, "DOMAIN", 0.0005)
    first = aggregate.aggregate_session("s1", "notes", "COMPLETED", "MODEL", False, 5.0)
    second = aggregate.aggregate_session("s1", "notes", "COMPLETED", "MODEL", False, 5.0)

    assert first["total_cost_usd"] == second["total_cost_usd"]
    assert second["model_calls_count"] == 1
    assert len(store.read_all_session_cost_records()) == 1


def test_unknown_usage_contributes_nothing_and_is_counted(cost_db):
    _call("s1", 0, "DOMAIN", 0.0010)
    _call("s1", 1, "DOMAIN", None, known=False, priced=False)

    record = aggregate.aggregate_session("s1", "notes", "COMPLETED", "MODEL", False, 1.0)

    assert record["usage_unknown_calls"] == 1
    assert record["total_input_tokens"] == 1000, "an unknown-usage call contributed tokens"
    assert record["total_cost_usd"] == pytest.approx(0.0010)


def test_a_session_with_no_calls_is_deterministic_not_zero_cost(cost_db):
    record = aggregate.aggregate_session("s1", "notes", "COMPLETED", "MODEL", False, 1.0)

    assert record["model_mode"] == "DETERMINISTIC"
    assert aggregate.completed_for_costing(record) is False


def test_cost_is_null_when_no_call_had_a_known_cost(cost_db):
    _call("s1", 0, "DOMAIN", None, known=False, priced=False)
    record = aggregate.aggregate_session("s1", "notes", "COMPLETED", "MODEL", False, 1.0)

    assert record["total_cost_usd"] is None, "an unknown cost was recorded as zero"
    assert aggregate.completed_for_costing(record) is False


def test_completed_for_costing_requires_a_genuine_verification(cost_db):
    """FR-007: a synthetic verification is not a successful generation."""
    _call("s1", 0, "DOMAIN", 0.001)
    genuine = aggregate.aggregate_session("s1", "n", "COMPLETED", "MODEL", False, 1.0)
    synthetic = aggregate.aggregate_session("s1", "n", "COMPLETED", "MODEL", True, 1.0)

    assert aggregate.completed_for_costing(genuine) is True
    assert aggregate.completed_for_costing(synthetic) is False


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------
def _seed_population():
    """Two genuine completions, one fallback-marked, one offline, one blocked."""
    for session, cost in (("s1", 0.0010), ("s2", 0.0030)):
        _call(session, 0, "DOMAIN", cost)
        aggregate.aggregate_session(session, "notes", "COMPLETED", "MODEL", False, 10.0)
    _call("s3", 0, "DOMAIN", 0.0050)
    aggregate.aggregate_session("s3", "notes", "COMPLETED", "MODEL", True, 10.0)
    aggregate.aggregate_session("s4", "notes", "COMPLETED", "DETERMINISTIC", False, 1.0)
    _call("s5", 0, "DOMAIN", 0.0005)
    aggregate.aggregate_session("s5", "notes", "BLOCKED", "MODEL", False, 4.0)


def test_report_prints_every_required_line(cost_db):
    _seed_population()
    report = build_report()

    for required in ("Sessions", "total", "completed", "blocked", "unverifiable",
                     "Cost per completed session", "average",
                     "Cost per session, regardless of status",
                     "p50", "p90", "max",
                     "Population", "model calls recorded",
                     "calls with unknown token usage", "calls with an unpriced model",
                     "Exclusions from the headline figure",
                     "Pricing basis", "peak window", "cache-miss",
                     "Cost by stage", "most expensive stage"):
        assert required in report, f"the report is missing the required line {required!r}"


def test_headline_excludes_fallback_marked_and_offline_sessions(cost_db):
    """SC-004: the excluded session is out of the figure AND visible as excluded."""
    _seed_population()
    report = build_report()

    # Genuine completions only: s1 (0.0010) and s2 (0.0030) -> average 0.0020.
    assert "$0.002000" in report, f"headline figure is wrong:\n{report}"
    assert "fallback-marked (spec 012)      1" in report
    assert "offline / deterministic         1" in report
    assert "eligible population             2" in report


def test_the_report_is_byte_identical_across_runs(cost_db):
    """SC-003: determinism is what makes the figure defensible."""
    _seed_population()
    assert build_report() == build_report()


def test_insertion_order_does_not_change_the_report(cost_db, tmp_path, monkeypatch):
    """The figures depend on the data, not on the order rows happened to arrive."""
    _call("b", 0, "DOMAIN", 0.0020)
    _call("a", 0, "DOMAIN", 0.0010)
    aggregate.aggregate_session("b", "n", "COMPLETED", "MODEL", False, 1.0)
    aggregate.aggregate_session("a", "n", "COMPLETED", "MODEL", False, 1.0)
    forward = build_report()

    # Same data, written in the opposite order, in a fresh store.
    other = tmp_path / "other.db"
    monkeypatch.setattr(settings, "COST_STORE_PATH", str(other), raising=False)
    _call("a", 0, "DOMAIN", 0.0010)
    _call("b", 0, "DOMAIN", 0.0020)
    aggregate.aggregate_session("a", "n", "COMPLETED", "MODEL", False, 1.0)
    aggregate.aggregate_session("b", "n", "COMPLETED", "MODEL", False, 1.0)
    reversed_ = build_report()

    assert forward == reversed_, "the report depends on insertion order"


def test_a_record_with_no_identity_is_rejected_not_stored(cost_db):
    """A junk row would skew the call count and could not be de-duplicated."""
    wrote = store.write_call_record({"session_id": "s1", "stage": "DOMAIN"})

    assert wrote is False
    assert store.read_call_records() == []


def test_no_data_is_stated_in_words_not_reported_as_zero(cost_db):
    report = build_report()

    assert "Nothing to report" in report
    assert "not a measurement of zero cost" in report
    assert "$0.000000" not in report, "an empty store was reported as a real cost of zero"


def test_no_eligible_population_is_stated_rather_than_a_zero_average(cost_db):
    _call("s1", 0, "DOMAIN", 0.004)
    aggregate.aggregate_session("s1", "n", "COMPLETED", "MODEL", True, 1.0)  # fallback-marked

    report = build_report()

    assert "no eligible population" in report
    assert "not a cost of zero" in report
    assert "$0.000000" not in report


def test_an_unpriced_session_is_reported_as_unknown_not_free(cost_db):
    _call("s1", 0, "DOMAIN", None, known=True, priced=False)
    aggregate.aggregate_session("s1", "n", "COMPLETED", "MODEL", False, 1.0)

    report = build_report()

    assert "calls with an unpriced model    1" in report
    assert "no session has a known cost" in report or "no eligible population" in report


def test_the_most_expensive_stage_is_named(cost_db):
    _call("s1", 0, "SCAFFOLDER", 0.0001)
    _call("s1", 1, "DOMAIN", 0.0090)
    _call("s1", 2, "TEST", 0.0002)
    aggregate.aggregate_session("s1", "n", "COMPLETED", "MODEL", False, 1.0)

    report = build_report()
    assert "most expensive stage            DOMAIN" in report
