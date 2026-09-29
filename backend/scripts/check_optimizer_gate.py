"""Decide whether the optimiser may be run (P8's gate), from measured evidence.

**The gate is not a policy preference; it is the proposal's own condition.**
`specs/015-diagnostic-skill-evolution/spec.md` and the optimization proposal both
defer the optimiser until "the conformance measure **varies** across real sessions".
The reasoning is arithmetic: if every recorded session scores identically there is
nothing for a loop to move, and the effort belongs on a different lever. This script
turns that condition into a check that can pass or fail on data.

Two independent things must vary, and they are not the same question:

1. **The outcome.** If every session builds and passes, the generator is saturated on
   this corpus and no admission test can separate a good edit from a bad one. This is
   the measured form of the null the readiness report hit: 15 sessions, 75 stage runs,
   zero violations, every score 100.
2. **The conformance measure.** A build outcome can vary while the instrument that is
   supposed to *attribute* the change stays flat. If `new_penalty` is 0 everywhere,
   there is nothing for a curator to act on even when builds fail.

Both must vary, because the loop needs a moving target AND an attributable signal.

**What this refuses to do.** It does not compute a p-value over repeated runs of the
same task and call it significance. Repeats are not independent observations: five
runs of one task are still one task, and treating them otherwise is how a small
corpus manufactures a result (FR-009/FR-013). Distinct tasks are counted separately
and reported as such.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

REPO = Path(__file__).resolve().parents[2]


def _load(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [r for r in payload.get("records", []) if r.get("build_success") is not None]


def evaluate(records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Whether the evidence satisfies the gate, and why.

    Records without a build outcome are dropped here rather than only at the file
    boundary: a session that never completed has no outcome to reason about, and a
    caller handing this function in-memory records must get the same answer as one
    reading a results file.
    """
    records = [r for r in records if r.get("build_success") is not None]

    outcomes = Counter(bool(r["build_success"]) for r in records)
    penalties = Counter(int(r.get("new_penalty") or 0) for r in records)
    tasks = defaultdict(set)
    for record in records:
        tasks[record["task"]].add(bool(record["build_success"]))

    # A task "varies" only if its own runs disagreed. With one run per task this is
    # always False, which is correct: a single observation cannot vary.
    varying_tasks = sum(1 for values in tasks.values() if len(values) > 1)

    outcome_varies = len(outcomes) > 1
    measure_varies = len(penalties) > 1

    return {
        "sessions": len(records),
        "distinct_tasks": len(tasks),
        "tasks_with_both_outcomes": varying_tasks,
        "outcome_distribution": dict(outcomes),
        "penalty_distribution": dict(penalties),
        "outcome_varies": outcome_varies,
        "measure_varies": measure_varies,
        "gate_passed": bool(outcome_varies and measure_varies),
    }


def render(result: Dict[str, Any]) -> str:
    lines = ["Optimiser gate (P8)", "=" * 62, ""]
    lines.append(f"  sessions                   : {result['sessions']}")
    lines.append(f"  distinct tasks             : {result['distinct_tasks']}")
    lines.append(f"  tasks with both outcomes   : {result['tasks_with_both_outcomes']}")
    lines.append(f"  build outcomes             : {result['outcome_distribution']}")
    lines.append(f"  new_penalty values         : {result['penalty_distribution']}")
    lines.append("")
    lines.append(f"  the OUTCOME varies         : {result['outcome_varies']}")
    lines.append(f"  the MEASURE varies         : {result['measure_varies']}")
    lines.append("")

    if result["gate_passed"]:
        lines.append("  GATE PASSED -- the optimiser may be run.")
        lines.append("")
        lines.append("  The round is already built (scripts/skillopt/round.py) and reads")
        lines.append("  recorded evidence. Run it against THIS corpus, and judge the result")
        lines.append("  on defects found, not on a score improved (D8).")
    else:
        lines.append("  GATE NOT PASSED -- do not run the optimiser.")
        lines.append("")
        if not result["outcome_varies"]:
            lines.append(
                "  Every session produced the same build outcome. The generator is"
            )
            lines.append(
                "  saturated on this corpus: no admission test can separate a good"
            )
            lines.append("  edit from a bad one. Widen difficulty or the rule set first.")
        if not result["measure_varies"]:
            lines.append(
                "  The conformance measure is constant, so there is nothing for a"
            )
            lines.append(
                "  curator to act on even where builds fail. The instrument must"
            )
            lines.append("  carry variance before a loop can move it.")
    lines.append("")
    lines.append(
        "  Note: repeated runs of one task are NOT independent observations and are"
    )
    lines.append(
        "  never counted as a larger sample (FR-009/FR-013)."
    )
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--results",
        default="reports/measurements/instruction-polarity.json",
        help="a run_instruction_experiment results file",
    )
    parser.add_argument("--json", action="store_true", help="emit the result as JSON")
    args = parser.parse_args(argv)

    path = REPO / args.results
    if not path.is_file():
        print(f"No results at {path}.", file=sys.stderr)
        print("Run the experiment first; the gate is decided from its records.", file=sys.stderr)
        return 2

    records = _load(path)
    if not records:
        print(f"{path} has no completed sessions yet.", file=sys.stderr)
        return 2

    result = evaluate(records)
    print(json.dumps(result, indent=2) if args.json else render(result))
    # Exit code carries the verdict so this can gate a script.
    return 0 if result["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
