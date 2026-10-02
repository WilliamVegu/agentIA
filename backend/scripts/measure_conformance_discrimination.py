#!/usr/bin/env python3
"""Measure whether the conformance channel can discriminate.

**The question this answers.** Verification-guided selection only pays if the
verifier separates good artifacts from bad ones. R2E-Gym found single verifier
axes saturate around 42-43% with *low distinguishability*, and CoEvoSkills'
ablation puts a 30-point cliff between an opaque pass/fail oracle and a
diagnostic one. Before building any loop on top of this channel, measure whether
it sees anything.

**What it does.** For each held-out blueprint it diagnoses the compliant artifact
set and then each violating variant, and reports the resulting score matrix. A
violation kind that scores the same as the compliant set is INVISIBLE to this
channel — a real gap, reported as such rather than smoothed over.

Costs no model calls and no generations: the whole measurement is static analysis.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.conformance_diagnostics import diagnose  # noqa: E402
from tests.fixtures import fake_model as fm  # noqa: E402

CORPUS_DIR = REPO_ROOT / "backend" / "tests" / "fixtures" / "baseline_blueprints"
STAGES = ("SCAFFOLDER", "DOMAIN", "SERVICE", "CONTROLLER", "TEST")


def _blueprints() -> Dict[str, dict]:
    found = {}
    for path in sorted(CORPUS_DIR.glob("*.json")):
        found[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    return found


def _compliant_sets(blueprint: dict) -> Dict[str, str]:
    """The union of every stage's compliant artifacts: a whole service."""
    merged: Dict[str, str] = {}
    for stage in STAGES:
        merged.update(fm.compliant_artifacts(stage, blueprint))
    return merged


def main() -> int:
    blueprints = _blueprints()
    print("Conformance channel discrimination")
    print("=" * 78)
    print(f"  blueprints: {', '.join(blueprints)}")
    print("  model calls: 0    generation cost: 0")
    print()

    kinds = sorted(fm.VIOLATION_BUILDERS)
    header = f"  {'blueprint':<14} {'clean':>6} " + " ".join(f"{k[:9]:>10}" for k in kinds)
    print(header)
    print("  " + "-" * (len(header) - 2))

    rows: List[Dict[str, Any]] = []
    for name, blueprint in blueprints.items():
        clean = diagnose(_compliant_sets(blueprint))
        row = {"blueprint": name, "clean": clean.score, "kinds": {}}
        cells = []
        for kind in kinds:
            report = diagnose(fm.violating_artifacts(kind, blueprint))
            row["kinds"][kind] = report.score
            marker = "" if report.score < clean.score else "!"
            cells.append(f"{report.score:>9}{marker}")
        rows.append(row)
        print(f"  {name:<14} {clean.score:>6} " + " ".join(f"{c:>10}" for c in cells))
    print()
    print("  '!' marks a violating set that scored no lower than the clean set:")
    print("      the channel did not see that defect.")

    # --- the discrimination verdict -----------------------------------------
    clean_scores = {r["clean"] for r in rows}
    blind: List[str] = []
    for kind in kinds:
        seen = {r["kinds"][kind] for r in rows}
        # A kind is detected if it drops below the clean score on at least one
        # blueprint; blind if it never does.
        if all(r["kinds"][kind] >= r["clean"] for r in rows):
            blind.append(kind)

    distinct = sorted({r["kinds"][k] for r in rows for k in kinds})
    print()
    print("  VERDICT")
    print(f"    clean scores observed      : {sorted(clean_scores)}")
    print(f"    distinct violation scores  : {distinct}")
    print(f"    violation kinds detected   : {len(kinds) - len(blind)}/{len(kinds)}")
    if blind:
        print(f"    BLIND TO                   : {', '.join(blind)}")
    else:
        print("    BLIND TO                   : nothing in the fixture vocabulary")
    print()

    if clean_scores == {100} and len(distinct) > 1:
        print("  The channel separates compliant from violating artifact sets on every")
        print("  blueprint, at zero cost. It is usable as a selection signal.")
        print("  NOTE: this measures SEPARATION, not whether the separation predicts")
        print("  real build outcomes. That requires executing the blueprints.")
    else:
        print("  The channel does NOT cleanly separate. Do not build a loop on it yet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
