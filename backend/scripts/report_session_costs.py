#!/usr/bin/env python3
"""Cost report for feature 013 — the number a stakeholder reads.

Prints what a completed microservice generation costs, over the sessions actually
persisted in the local cost store.

WHAT MAKES THIS FIGURE DEFENSIBLE
---------------------------------
1. **The headline excludes anything that was not a genuine success.** A session
   counts only if it is COMPLETED, used the model path, was **not** marked as
   having used a verification fallback (feature 012), and has a known cost. A
   session whose verification was synthetic cannot be claimed as a successful
   generation, so it cannot be priced as one.
2. **Every figure carries its population.** Sessions, calls, unknown-usage calls
   and unpriced calls are printed alongside the numbers. An average over an
   unstated denominator is not a measurement.
3. **Unknown is never printed as zero.** A missing token count or a model absent
   from the pricing table is reported as unknown and counted, because a zero is a
   claim and an absence is not.
4. **It is deterministic.** It reads the local store only, makes no live call,
   requires no telemetry destination, orders rows by session identifier, and uses
   nearest-rank percentiles at fixed precision — so two runs over unchanged data
   are byte-identical.

Run:  .venv/bin/python backend/scripts/report_session_costs.py
"""

from __future__ import annotations

import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.cost import store as store_mod  # noqa: E402
from app.cost.aggregate import MODE_MODEL, completed_for_costing  # noqa: E402

#: Currency is printed at this fixed precision, with fixed rounding, so that
#: accumulation order cannot change a printed figure between runs.
_CENTS = Decimal("0.000001")


def money(value: Optional[float]) -> str:
    if value is None:
        return "unknown"
    quantised = Decimal(str(value)).quantize(_CENTS, rounding=ROUND_HALF_UP)
    return f"${quantised:,.6f}"


def _percentile(sorted_values: List[float], fraction: float) -> Optional[float]:
    """Nearest-rank percentile.

    Stated explicitly because the convention matters for reproducibility: an
    interpolating definition would make the figure depend on an unstated method,
    and two runs could differ on a tie.
    """
    if not sorted_values:
        return None
    rank = int(fraction * len(sorted_values) + 0.999999)  # ceil(fraction * n)
    rank = max(1, min(rank, len(sorted_values)))
    return sorted_values[rank - 1]


def build_report(path: Optional[str] = None) -> str:
    """Build the report text. Pure read — deterministic for a given store."""
    records = sorted(
        store_mod.read_all_session_cost_records(path=path),
        key=lambda r: r.get("session_id") or "",
    )
    calls = store_mod.read_call_records(path=path)

    lines: List[str] = []
    lines.append("Cost report — microservice generation")
    lines.append("=" * 62)

    if not records:
        lines.append("")
        lines.append("No sessions found in the cost store. Nothing to report.")
        lines.append("")
        lines.append(
            "This is not a measurement of zero cost — there is no data. Run "
            "sessions with recording enabled, then re-run this report."
        )
        return "\n".join(lines) + "\n"

    total = len(records)
    completed = [r for r in records if r.get("terminal_status") == "COMPLETED"]
    blocked = [r for r in records if r.get("terminal_status") == "BLOCKED"]
    unverifiable = [r for r in records if r.get("verification_fallback_used")]

    eligible = [r for r in records if completed_for_costing(r)]
    excluded_unverifiable = [r for r in records if r.get("verification_fallback_used")]
    excluded_offline = [
        r for r in records
        if r.get("model_mode") != MODE_MODEL and not r.get("verification_fallback_used")
    ]
    excluded_no_cost = [
        r for r in records
        if r.get("verification_fallback_used") is False
        and r.get("model_mode") == MODE_MODEL
        and r.get("total_cost_usd") is None
    ]

    # --- session counts ----------------------------------------------------
    lines.append("")
    lines.append("Sessions")
    lines.append(f"  total                           {total}")
    lines.append(f"  completed                       {len(completed)}")
    lines.append(f"  blocked                         {len(blocked)}")
    lines.append(f"  unverifiable (synthetic verify) {len(unverifiable)}")

    # --- the headline ------------------------------------------------------
    lines.append("")
    lines.append("Cost per completed session  (headline — genuine completions only)")
    if eligible:
        eligible_costs = sorted(float(r["total_cost_usd"]) for r in eligible)
        headline = sum(eligible_costs) / len(eligible_costs)
        lines.append(f"  average                         {money(headline)}")
        lines.append(f"  p50                             {money(_percentile(eligible_costs, 0.50))}")
        lines.append(f"  p90                             {money(_percentile(eligible_costs, 0.90))}")
        lines.append(f"  max                             {money(eligible_costs[-1])}")
        lines.append("  percentile method               nearest-rank over the eligible population")
    else:
        lines.append("  average                         no eligible population")
        lines.append(
            "  Reason: no session is simultaneously COMPLETED, model-mode, not "
            "fallback-marked, and priced. This is not a cost of zero."
        )

    # --- across all sessions ----------------------------------------------
    priced_all = [float(r["total_cost_usd"]) for r in records if r.get("total_cost_usd") is not None]
    lines.append("")
    lines.append("Cost per session, regardless of status")
    if priced_all:
        lines.append(f"  average                         {money(sum(priced_all) / len(priced_all))}")
        ordered_all = sorted(priced_all)
        lines.append(f"  p50                             {money(_percentile(ordered_all, 0.50))}")
        lines.append(f"  p90                             {money(_percentile(ordered_all, 0.90))}")
        lines.append(f"  max                             {money(ordered_all[-1])}")
        lines.append(f"  sessions with a known cost      {len(priced_all)} of {total}")
    else:
        lines.append("  average                         no session has a known cost")

    # --- exclusions --------------------------------------------------------
    lines.append("")
    lines.append("Exclusions from the headline figure")
    lines.append(f"  fallback-marked (spec 012)      {len(excluded_unverifiable)}")
    lines.append(f"  offline / deterministic         {len(excluded_offline)}")
    lines.append(f"  no known cost (unpriced)        {len(excluded_no_cost)}")
    lines.append(f"  eligible population             {len(eligible)}")

    # --- population statement ---------------------------------------------
    unknown_usage = sum(int(r.get("usage_unknown_calls") or 0) for r in records)
    unpriced = sum(int(r.get("unpriced_calls") or 0) for r in records)
    cache_assumed = sum(int(r.get("cache_miss_assumed_calls") or 0) for r in records)
    lines.append("")
    lines.append("Population")
    lines.append(f"  sessions in this report         {total}")
    lines.append(f"  model calls recorded            {len(calls)}")
    lines.append(f"  calls with unknown token usage  {unknown_usage}")
    lines.append(f"  calls with an unpriced model    {unpriced}")
    lines.append(
        "  (unknown-usage and unpriced calls contribute to no total; they are "
        "counted, never treated as free)"
    )

    # --- pricing basis -----------------------------------------------------
    bases = sorted({c.get("pricing_basis") for c in calls if c.get("pricing_basis")})
    lines.append("")
    lines.append("Pricing basis")
    lines.append(f"  bases applied                   {', '.join(bases) if bases else 'none'}")
    lines.append("  peak window                     01:00-04:00 and 06:00-10:00 UTC, Mon-Fri")
    lines.append(f"  priced on the cache-miss bound  {cache_assumed} call(s)")
    lines.append(
        "  (the provider's public-holiday calendar is not modelled, so a holiday "
        "call priced off-peak by the provider is priced at peak here — this "
        "overstates, never understates)"
    )

    # --- per-stage breakdown ----------------------------------------------
    lines.append("")
    lines.append("Cost by stage")
    by_stage: Dict[str, Dict[str, float]] = {}
    for call in calls:
        stage = call.get("stage") or "<unknown>"
        bucket = by_stage.setdefault(stage, {"cost": 0.0, "calls": 0})
        bucket["calls"] += 1
        if call.get("cost_usd") is not None:
            bucket["cost"] += float(call["cost_usd"])
    if by_stage:
        for stage in sorted(by_stage):
            bucket = by_stage[stage]
            lines.append(
                f"  {stage:<22} {money(bucket['cost']):>18}   ({int(bucket['calls'])} call(s))"
            )
        dearest = max(sorted(by_stage), key=lambda s: by_stage[s]["cost"])
        lines.append(f"  most expensive stage            {dearest} ({money(by_stage[dearest]['cost'])})")
    else:
        lines.append("  no calls recorded")

    return "\n".join(lines) + "\n"


def main() -> int:
    sys.stdout.write(build_report())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
