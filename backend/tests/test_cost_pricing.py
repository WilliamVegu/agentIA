"""Pricing tests (feature 013, T016).

Verifies the two dimensions the provider's published rates actually vary on —
peak vs off-peak, and cache hit vs miss — and the two rules that keep the headline
figure honest: an unknown model is never priced at zero, and a response with no
cache breakdown is priced on the upper bound.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.cost import pricing as pricing_mod  # noqa: E402
from app.cost.pricing import PricingTableError, is_peak, load_pricing_table, price_call  # noqa: E402

#: Monday 02:00 UTC — inside the peak window.
PEAK_MOMENT = datetime(2026, 9, 28, 2, 0, tzinfo=timezone.utc)
#: Monday 12:00 UTC — outside it.
OFF_PEAK_MOMENT = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
#: Saturday 02:00 UTC — the clock falls in a peak range but the day does not.
WEEKEND_MOMENT = datetime(2026, 10, 3, 2, 0, tzinfo=timezone.utc)


def test_the_table_cites_its_source():
    """Rates must be fetched and cited, never recalled."""
    table = load_pricing_table()
    assert table["source"].startswith("https://")
    assert "deepseek" in table["source"]
    assert table["retrieved_at"]


def test_off_peak_is_exactly_half_of_peak():
    """The published relationship, asserted at load time as a consistency check."""
    table = load_pricing_table()
    for provider, models in table["models"].items():
        for model, rates in models.items():
            for field in ("input_cache_hit", "input_cache_miss", "output"):
                assert rates["off_peak"][field] == pytest.approx(rates["peak"][field] / 2), (
                    f"{provider}/{model}.{field} violates the published relationship"
                )


def test_peak_window_is_computed_from_the_calls_own_timestamp():
    assert is_peak(PEAK_MOMENT) is True
    assert is_peak(OFF_PEAK_MOMENT) is False
    # The clock is inside a peak range but the day is not.
    assert is_peak(WEEKEND_MOMENT) is False


def test_identical_calls_inside_and_outside_peak_differ_by_the_published_ratio():
    """SC-007: the basis is per call, not per session or per report."""
    peak = price_call("deepseek", "deepseek-flash", 1000, 500, PEAK_MOMENT)
    off = price_call("deepseek", "deepseek-flash", 1000, 500, OFF_PEAK_MOMENT)

    assert peak["priced"] and off["priced"]
    assert peak["peak"] is True and off["peak"] is False
    assert peak["pricing_basis"].startswith("peak")
    assert off["pricing_basis"].startswith("off_peak")
    assert peak["cost_usd"] / off["cost_usd"] == pytest.approx(2.0)


def test_cache_hit_input_is_priced_at_the_hit_rate_not_the_miss_rate():
    """On Flash the input rate spans a factor of fifty between hit and miss."""
    all_hit = price_call("deepseek", "deepseek-flash", 1_000_000, 0, OFF_PEAK_MOMENT,
                         cache_hit_input_tokens=1_000_000)
    all_miss = price_call("deepseek", "deepseek-flash", 1_000_000, 0, OFF_PEAK_MOMENT,
                          cache_hit_input_tokens=0)

    assert all_hit["cost_usd"] == pytest.approx(0.003)
    assert all_miss["cost_usd"] == pytest.approx(0.15)
    assert all_hit["cost_usd"] < all_miss["cost_usd"]


def test_a_partial_cache_hit_splits_the_prompt():
    half = price_call("deepseek", "deepseek-flash", 1_000_000, 0, OFF_PEAK_MOMENT,
                      cache_hit_input_tokens=500_000)
    # 0.5M at $0.003 + 0.5M at $0.15
    assert half["cost_usd"] == pytest.approx(0.5 * 0.003 + 0.5 * 0.15)


def test_missing_cache_breakdown_is_priced_as_a_cache_miss():
    """The upper bound, chosen because guessing a hit would understate cost."""
    unknown_cache = price_call("deepseek", "deepseek-flash", 1_000_000, 0, OFF_PEAK_MOMENT,
                               cache_hit_input_tokens=None)

    assert unknown_cache["cache_basis_known"] is False
    assert "cache-miss-assumed" in unknown_cache["pricing_basis"]
    assert unknown_cache["cost_usd"] == pytest.approx(0.15), (
        "an unknown cache outcome was priced as though the prompt were cached"
    )


def test_an_unknown_model_is_unpriced_never_zero():
    """SC-005: a missing price must not silently become free."""
    result = price_call("deepseek", "model-that-does-not-exist", 1000, 500, PEAK_MOMENT)

    assert result["priced"] is False
    assert result["cost_usd"] is None, "an unpriced model produced a cost, probably zero"
    assert result["pricing_basis"] == "unpriced"


def test_unknown_usage_is_unpriced_never_zero():
    result = price_call("deepseek", "deepseek-flash", None, None, PEAK_MOMENT)
    assert result["priced"] is False
    assert result["cost_usd"] is None
    assert result["pricing_basis"] == "usage-unknown"


def test_output_tokens_are_priced_at_the_output_rate():
    result = price_call("deepseek", "deepseek-flash", 0, 1_000_000, OFF_PEAK_MOMENT)
    assert result["cost_usd"] == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# Load-time validation
# ---------------------------------------------------------------------------
def test_an_uncited_table_fails_to_load(tmp_path):
    uncited = tmp_path / "uncited.json"
    uncited.write_text(json.dumps({"models": {"deepseek": {"m": {
        "peak": {"input_cache_hit": 1, "input_cache_miss": 2, "output": 3},
        "off_peak": {"input_cache_hit": 0.5, "input_cache_miss": 1, "output": 1.5},
    }}}}), encoding="utf-8")

    with pytest.raises(PricingTableError, match="source"):
        load_pricing_table(str(uncited))


def test_a_table_violating_the_published_relationship_fails_to_load(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({
        "source": "https://api-docs.deepseek.com/quick_start/pricing",
        "models": {"deepseek": {"m": {
            "peak": {"input_cache_hit": 1, "input_cache_miss": 2, "output": 3},
            # output is NOT half of peak -> contradicts the cited source
            "off_peak": {"input_cache_hit": 0.5, "input_cache_miss": 1, "output": 1},
        }}},
    }), encoding="utf-8")

    with pytest.raises(PricingTableError, match="half of peak"):
        load_pricing_table(str(bad))


def test_a_malformed_entry_is_a_load_error_not_a_silent_skip(tmp_path):
    """A typo must not quietly drop a model into the unpriced bucket."""
    bad = tmp_path / "missing_field.json"
    bad.write_text(json.dumps({
        "source": "https://api-docs.deepseek.com/quick_start/pricing",
        "models": {"deepseek": {"m": {
            "peak": {"input_cache_hit": 1, "input_cache_miss": 2},
            "off_peak": {"input_cache_hit": 0.5, "input_cache_miss": 1},
        }}},
    }), encoding="utf-8")

    with pytest.raises(PricingTableError, match="output"):
        load_pricing_table(str(bad))


def test_seeded_rates_match_the_published_page():
    """Guards against a silent edit of the fetched numbers."""
    table = load_pricing_table()
    flash = table["models"]["deepseek"]["deepseek-flash"]
    assert flash["peak"]["input_cache_hit"] == 0.006
    assert flash["peak"]["input_cache_miss"] == 0.30
    assert flash["peak"]["output"] == 1.20
    assert flash["off_peak"]["input_cache_hit"] == 0.003
    assert flash["off_peak"]["input_cache_miss"] == 0.15
    assert flash["off_peak"]["output"] == 0.60
    pro = table["models"]["deepseek"]["deepseek-v4-pro"]
    assert pro["peak"]["input_cache_miss"] == 1.32
    assert pro["off_peak"]["output"] == 1.98
