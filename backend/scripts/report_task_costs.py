#!/usr/bin/env python3
"""Per-task token and cost report — the pricing input.

``report_session_costs.py`` answers "what does a *successful* generation cost": it
counts only COMPLETED, model-path, non-fallback sessions, which is the right
population for a headline claim and the wrong one for pricing. A blocked session
still spends money, and pricing a task needs its cost whether or not the session
succeeded.

This report therefore prices **every session that has cost rows**, and states what
each population is for. It groups by session id, which — after the fix in
``run_corpus_baseline.graph_runner`` — is ``<prefix>-<blueprint>``, so the task
is recoverable from the key.

WHAT THIS DELIBERATELY DOES NOT DO
----------------------------------
It does not report a mean as if it were a price. Costs are listed per session with
their call counts, unknown-usage and unpriced call counts beside them, because an
average over an unstated denominator is not a measurement (feature 013's rule, kept
here). Unknown token counts are counted, never rendered as zero.

Run:
    .venv/bin/python backend/scripts/report_task_costs.py
    .venv/bin/python backend/scripts/report_task_costs.py --prefix ver-r1
    .venv/bin/python backend/scripts/report_task_costs.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.cost import store as store_mod  # noqa: E402


def _field(call, name):
    return call.get(name) if isinstance(call, dict) else getattr(call, name, None)


def collect(prefix: Optional[str] = None) -> List[Dict[str, Any]]:
    """One row per session id, with its token and cost totals."""
    calls = store_mod.read_call_records()

    by_session: Dict[str, List[Any]] = defaultdict(list)
    for call in calls:
        session_id = _field(call, "session_id")
        if not session_id:
            # Unattributable. Counted separately rather than folded into a task,
            # because assigning them to a task would invent an attribution.
            continue
        if prefix and not str(session_id).startswith(f"{prefix}-"):
            continue
        by_session[str(session_id)].append(call)

    rows: List[Dict[str, Any]] = []
    for session_id in sorted(by_session):
        session_calls = by_session[session_id]
        priced = [c for c in session_calls if _field(c, "cost_usd") is not None]
        known = [c for c in session_calls if _field(c, "usage_known")]
        # "prefix-blueprint" -> "blueprint"; keep the whole key when there is no dash.
        task = session_id.split("-", 1)[1] if "-" in session_id else session_id
        rows.append({
            "session_id": session_id,
            "task": task,
            "calls": len(session_calls),
            "calls_priced": len(priced),
            "calls_usage_known": len(known),
            "calls_unknown_usage": len(session_calls) - len(known),
            "input_tokens": sum(int(_field(c, "input_tokens") or 0) for c in known),
            "output_tokens": sum(int(_field(c, "output_tokens") or 0) for c in known),
            "cost_usd": (
                sum(float(_field(c, "cost_usd")) for c in priced) if priced else None
            ),
        })
    return rows


def render(rows: List[Dict[str, Any]], unattributable: int) -> str:
    lines: List[str] = ["Per-task cost and token report", "=" * 62, ""]
    if not rows:
        lines.append("  No attributable cost records were found.")
        lines.append("")
        lines.append("  This is not a measurement of zero: there is no data. Sessions")
        lines.append("  are priced only when the cost recorder was given their session")
        lines.append("  id, so an empty table here usually means no priced session has")
        lines.append("  run under this prefix yet.")
        return "\n".join(lines)

    header = f"  {'task':<18}{'calls':>6}{'priced':>7}{'in tok':>10}{'out tok':>10}{'cost USD':>12}"
    lines.append(header)
    lines.append("  " + "-" * (len(header) - 2))
    for row in rows:
        cost = f"${row['cost_usd']:.4f}" if row["cost_usd"] is not None else "unpriced"
        lines.append(
            f"  {row['task']:<18}{row['calls']:>6}{row['calls_priced']:>7}"
            f"{row['input_tokens']:>10}{row['output_tokens']:>10}{cost:>12}"
        )

    total_cost = sum(r["cost_usd"] for r in rows if r["cost_usd"] is not None)
    total_priced = sum(1 for r in rows if r["cost_usd"] is not None)
    lines.append("  " + "-" * (len(header) - 2))
    lines.append(
        f"  {'TOTAL':<18}{sum(r['calls'] for r in rows):>6}"
        f"{sum(r['calls_priced'] for r in rows):>7}"
        f"{sum(r['input_tokens'] for r in rows):>10}"
        f"{sum(r['output_tokens'] for r in rows):>10}"
        f"{('$%.4f' % total_cost):>12}"
    )
    lines.append("")
    lines.append(f"  sessions priced     : {total_priced} of {len(rows)}")
    lines.append(f"  unattributable calls: {unattributable}")
    lines.append("")
    lines.append("  Per-task cost is the sum over that task's sessions; a task run")
    lines.append("  more than once appears once per session key, not once per task.")
    lines.append("  No mean is printed: an average over an unstated denominator is")
    lines.append("  not a measurement.")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Per-task token and cost report.")
    parser.add_argument("--prefix", default=None,
                        help="only sessions whose key starts with '<prefix>-'")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    all_calls = store_mod.read_call_records()
    unattributable = sum(1 for c in all_calls if not _field(c, "session_id"))
    rows = collect(prefix=args.prefix)

    if args.json:
        print(json.dumps({"rows": rows, "unattributable_calls": unattributable}, indent=2))
    else:
        print(render(rows, unattributable))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
