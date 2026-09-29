"""Analyse the polarity experiment against its PRE-REGISTERED decision rule.

The rule was fixed before the run (see `run_instruction_experiment.py`) and is not
renegotiated here:

* **prohibition is supported** only if it beats BOTH `control` and `placebo` on
  every task where they differ, in the same direction, on at least 6 of 6 tasks.
  At n=6 the minimum attainable two-sided p is 0.03125, so a unanimous result is the
  only significant one available.
* beating `control` but **not** `placebo` is a **priming** result. That is a real
  finding and it is NOT evidence for polarity -- which is exactly the distinction
  arXiv:2604.11088 draws between content-dependent and content-independent gains.
* `placebo` beating both is pure priming with no instruction content.

**Why the placebo comparison carries the weight.** The same study found rule-file
gains largely content-independent: random, shuffled and mismatched-domain files all
matched curated ones. Any instruction change therefore tends to "work" by adding
priming, so a prohibition-vs-control win on its own would be uninterpretable.

**Why repeats are pooled per task and not treated as sample size.** Five runs of one
task are one task. Pooling gives a per-task pass rate on both arms; the *task* is the
unit of the paired comparison, and n is the number of tasks.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

REPO = Path(__file__).resolve().parents[2]

#: The arithmetic floor: the smallest number of tasks at which an exact two-sided
#: paired test can reach p < 0.05 at all. Six tasks, and then only unanimously.
MIN_TASKS_FOR_SIGNIFICANCE = 6


def _rates(records: Sequence[Dict[str, Any]]) -> Tuple[Dict[Tuple[str, str], float], Dict[str, int]]:
    """Per-(task, arm) pass rate, plus the runs behind each cell."""
    counts: Dict[Tuple[str, str], List[bool]] = defaultdict(list)
    for record in records:
        if record.get("build_success") is None:
            continue
        counts[(record["task"], record["arm"])].append(bool(record["build_success"]))

    rates = {key: (sum(values) / len(values)) for key, values in counts.items()}
    runs = {arm: 0 for arm in {key[1] for key in counts}}
    for (_, arm), values in counts.items():
        runs[arm] = max(runs[arm], len(values))
    return rates, runs


def _sign_test_p(wins: int, losses: int) -> Optional[float]:
    """Exact two-sided sign-test p over discordant pairs. None when n is 0."""
    n = wins + losses
    if n == 0:
        return None
    k = min(wins, losses)
    tail = sum(_comb(n, i) for i in range(0, k + 1))
    return min(1.0, 2 * tail / (2 ** n))


def _comb(n: int, k: int) -> int:
    from math import comb

    return comb(n, k)


def analyse(records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    rates, runs = _rates(records)
    tasks = sorted({task for task, _ in rates})
    arms = sorted({arm for _, arm in rates})

    comparisons: Dict[str, Any] = {}
    for challenger, baseline in (("prohibition", "control"), ("prohibition", "placebo"),
                                 ("placebo", "control")):
        if challenger not in arms or baseline not in arms:
            continue
        wins = losses = ties = 0
        per_task = []
        for task in tasks:
            challenger_rate = rates.get((task, challenger))
            baseline_rate = rates.get((task, baseline))
            if challenger_rate is None or baseline_rate is None:
                continue
            if challenger_rate > baseline_rate:
                wins += 1
                verdict = "challenger"
            elif challenger_rate < baseline_rate:
                losses += 1
                verdict = "baseline"
            else:
                ties += 1
                verdict = "tie"
            per_task.append({
                "task": task,
                "challenger_rate": round(challenger_rate, 3),
                "baseline_rate": round(baseline_rate, 3),
                "verdict": verdict,
            })
        comparisons[f"{challenger}_vs_{baseline}"] = {
            "wins": wins, "losses": losses, "ties": ties,
            "discordant": wins + losses,
            "p_value": _sign_test_p(wins, losses),
            "per_task": per_task,
        }

    n_tasks = len(tasks)
    unanimous = comparisons.get("prohibition_vs_control", {}).get("losses") == 0 and \
        comparisons.get("prohibition_vs_control", {}).get("wins", 0) > 0 and \
        comparisons.get("prohibition_vs_control", {}).get("ties", 0) == 0
    beats_control = comparisons.get("prohibition_vs_control", {}).get("wins", 0) >= MIN_TASKS_FOR_SIGNIFICANCE
    beats_placebo = comparisons.get("prohibition_vs_placebo", {}).get("wins", 0) >= MIN_TASKS_FOR_SIGNIFICANCE

    if n_tasks < MIN_TASKS_FOR_SIGNIFICANCE:
        conclusion = (
            f"INSUFFICIENT: only {n_tasks} task(s). At fewer than "
            f"{MIN_TASKS_FOR_SIGNIFICANCE} tasks no paired two-sided test can reach "
            f"p<0.05 under any outcome. Report this as insufficient evidence, not as "
            f"a trend."
        )
    elif beats_control and beats_placebo and unanimous:
        conclusion = (
            "SUPPORTED: prohibition beat both control and placebo on every task. "
            "The effect is attributable to polarity rather than to priming."
        )
    elif beats_control and not beats_placebo:
        conclusion = (
            "PRIMING: prohibition beat control but NOT placebo. This is a real "
            "finding and it is not evidence for polarity -- the gain is consistent "
            "with the content-independent priming effect arXiv:2604.11088 reports."
        )
    else:
        conclusion = (
            "NO DIFFERENCE DETECTED at this resolution. This is the expected outcome "
            "at this sample size and is what most small instruction experiments "
            "actually support."
        )

    return {
        "tasks": n_tasks,
        "arms": arms,
        "runs_per_cell": runs,
        "comparisons": comparisons,
        "conclusion": conclusion,
        "min_attainable_p": (2 / (2 ** n_tasks)) if n_tasks else None,
    }


def render(result: Dict[str, Any]) -> str:
    lines = ["Instruction polarity experiment", "=" * 62, ""]
    lines.append(f"  tasks            : {result['tasks']}")
    lines.append(f"  arms             : {', '.join(result['arms'])}")
    lines.append(
        f"  runs per cell    : "
        + ", ".join(f"{a}={n}" for a, n in sorted(result["runs_per_cell"].items()))
    )
    lines.append(
        f"  min attainable p : "
        + (f"{result['min_attainable_p']:.5f}" if result["min_attainable_p"] else "n/a")
    )
    lines.append("")
    for name, comparison in sorted(result["comparisons"].items()):
        p = comparison["p_value"]
        lines.append(
            f"  {name:32} W{comparison['wins']} L{comparison['losses']} "
            f"T{comparison['ties']}"
            + (f"  p={p:.4f}" if p is not None else "  p=n/a")
        )
    lines.append("")
    lines.append(f"  {result['conclusion']}")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", default="reports/measurements/instruction-polarity.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    path = REPO / args.results
    if not path.is_file():
        print(f"No results at {path}.", file=sys.stderr)
        return 2
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("records", [])
    if not records:
        print("No records yet.", file=sys.stderr)
        return 2

    result = analyse(records)
    print(json.dumps(result, indent=2) if args.json else render(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
