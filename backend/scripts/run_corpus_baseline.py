#!/usr/bin/env python3
"""Run a session batch over the held-out blueprints and record every outcome.

This is the step that produces traces. It exists because there was previously no
way to drive sessions in bulk: the API persists outcomes one session at a time,
and nothing drove it in a loop. Without this, "run the app to get a baseline" had
no vehicle.

**Run it where the container runtime is reachable.** If the runtime is not
available the honest verifier refuses to substitute a synthetic success, every
session terminates BLOCKED, and the records are marked *unverified* — correct
behaviour, but useless as a baseline, because unverified sessions are excluded
from every figure by design. The report says so rather than reporting a rate.

**What it does per blueprint:** runs one generation session through the existing
graph, then records a diagnostic record labelled with the blueprint name. The
label matters: without it, repeated runs of one task would be indistinguishable
from a larger sample, which is how a five-task corpus gets described as fifty.

**Cost is reported only when cost data exists.** The cost store is empty until
sessions run with recording active, and reporting a cost of zero would be a claim
this driver cannot support.

Usage:
    PYTHONPATH=backend .venv/bin/python backend/scripts/run_corpus_baseline.py
    PYTHONPATH=backend .venv/bin/python backend/scripts/run_corpus_baseline.py --blueprints minimal,pair-a
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.models.diagnostics import (  # noqa: E402
    read_diagnostic_records,
    write_diagnostic_record,
)
from app.services.conformance_diagnostics import diagnose, stage_attribution  # noqa: E402
from app.services.corpus_report import build_report, render_report  # noqa: E402

CORPUS_DIR = REPO_ROOT / "backend" / "tests" / "fixtures" / "baseline_blueprints"

#: The held-out task set. The five fixtures frozen by feature 011 — deliberately
#: not new fixtures, because a task set authored alongside the thing it evaluates
#: measures the author.
DEFAULT_BLUEPRINTS = ("constrained", "minimal", "multi-entity", "pair-a", "pair-b")


def available_blueprints() -> List[str]:
    return sorted(path.stem for path in CORPUS_DIR.glob("*.json"))


def graph_runner(blueprint_name: str, *, provider: Optional[str] = None,
                 api_key: Optional[str] = None, model_name: Optional[str] = None) -> Dict[str, Any]:
    """Run one session through the existing graph and return its final state.

    The production path. Kept as a module-level function so a caller can pass its
    own runner instead — the seam is a PARAMETER, never a monkeypatch, so a
    refactor cannot silently stop injecting and leave the suite running real
    sessions against a live provider.
    """
    from app.orchestrator.graph import generation_graph

    blueprint = json.loads((CORPUS_DIR / f"{blueprint_name}.json").read_text(encoding="utf-8"))
    workspace = Path(tempfile.mkdtemp(prefix=f"corpus-{blueprint_name}-"))

    state: Dict[str, Any] = {
        "session_id": f"corpus-{blueprint_name}",
        "blueprint": blueprint,
        "workspace_path": str(workspace),
        "generated_files": {},
        "logs": [],
    }
    if provider:
        state["llm_provider"] = provider
    if api_key:
        state["llm_api_key"] = api_key
    if model_name:
        state["llm_model"] = model_name
    return generation_graph.invoke(state)


def record_one(session_id: str, task: str, final_state: Dict[str, Any]) -> bool:
    """Persist one diagnostic record from a finished session.

    A session that produced no artifacts is recorded as *not evaluable*, not as
    clean, and a session whose build fell back to a synthetic result is marked
    *unverified* so it can be excluded from every figure.
    """
    try:
        report = diagnose(dict(final_state.get("generated_files") or {}))
        metrics = final_state.get("test_metrics") or {}
        return write_diagnostic_record(
            session_id,
            task=task,
            score=report.score,
            raw_penalty=report.raw_penalty,
            density=report.density,
            artifact_count=report.evaluated_artifact_count,
            evaluable=report.evaluable,
            unverified=bool(metrics.get("fallback_used", False)),
            counts_by_severity=report.counts_by_severity,
            rule_histogram=report.rule_histogram,
            findings=[v.to_dict() for v in report.violations],
            stages=stage_attribution(final_state.get("generation_journal")),
        )
    except Exception:
        # A failure to record one session must not abandon the batch: the
        # sessions either side of it are still worth recording.
        return False


def run_baseline(
    *,
    runner: Callable[[str], Dict[str, Any]],
    blueprints: Sequence[str] = DEFAULT_BLUEPRINTS,
    output: Callable[[str], None] = print,
) -> Dict[str, Any]:
    """Run one session per blueprint, record every outcome, and report.

    Returns a summary including the report object and per-blueprint outcomes, so
    a caller can assert on it without parsing the rendered text.
    """
    records: List[Dict[str, Any]] = []
    outcomes: List[Dict[str, Any]] = []

    total = len(blueprints)
    for index, blueprint_name in enumerate(blueprints, start=1):
        session_id = f"corpus-{blueprint_name}"
        output(f"  [{index}/{total}] {blueprint_name} ...")

        try:
            final_state = runner(blueprint_name)
            status = str(final_state.get("status") or "UNKNOWN")
            error = final_state.get("error")
        except Exception as exc:  # a crashed session is an outcome, not an abort
            final_state = {}
            status = "ERROR"
            error = f"{type(exc).__name__}: {exc}"

        # Recorded unconditionally, including after a crash. A session that ran
        # and failed is part of the population, and a batch that ran four tasks
        # must report four -- silently dropping the ones that crashed would
        # overstate the denominator the success rate is taken over. Such a record
        # is *not evaluable*, which is the honest description, and the report
        # states that exclusion rather than hiding it.
        recorded = record_one(session_id, blueprint_name, final_state or {})
        metrics = (final_state or {}).get("test_metrics") or {}

        outcomes.append({
            "blueprint": blueprint_name,
            "session_id": session_id,
            "status": status,
            "error": error,
            "recorded": recorded,
            "artifact_count": len((final_state or {}).get("generated_files") or {}),
            "fallback_used": bool(metrics.get("fallback_used", False)),
        })

        marker = "recorded" if recorded else "NOT RECORDED"
        detail = f" ({error})" if error else ""
        output(f"        {status}, {outcomes[-1]['artifact_count']} artifacts, {marker}{detail}")

    # Read back what was written, so the report reflects the store rather than a
    # second in-memory copy that could drift from it.
    stored = [r for r in read_diagnostic_records() if r.get("task") in set(blueprints)]
    report = build_report(stored, cost=_cost_for(stored))

    output("")
    output(render_report(report))

    return {"report": report, "outcomes": outcomes, "recorded": len(stored)}


def _cost_for(records: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Cost aggregate for these sessions, or None when no cost data exists.

    None is the honest answer. Returning zero would assert a measurement nobody
    made — the same distinction feature 013's own report draws.
    """
    if not records:
        return None
    try:
        from app.models.session import SessionLocal
        from app.services import cost_store  # type: ignore
    except Exception:
        return None

    db = SessionLocal()
    try:
        rows = [
            row
            for row in db.execute(
                # Read the aggregate only if the table exists and carries rows.
                __import__("sqlalchemy").text(
                    "SELECT session_id, total_cost_usd FROM session_costs"
                )
            )
            if row[0] in {r["session_id"] for r in records}
        ]
    except Exception:
        return None
    finally:
        db.close()

    if not rows:
        return None
    total = sum(float(r[1] or 0.0) for r in rows)
    return {"sessions_with_cost": len(rows), "total_usd": total}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Record a generation baseline.")
    parser.add_argument("--blueprints", default=",".join(DEFAULT_BLUEPRINTS),
                        help="comma-separated blueprint names")
    parser.add_argument("--provider", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--api-key", default=None)
    args = parser.parse_args(argv)

    names = [n.strip() for n in args.blueprints.split(",") if n.strip()]
    known = available_blueprints()
    unknown = [n for n in names if n not in known]
    if unknown:
        print(f"Unknown blueprints: {unknown}. Available: {known}", file=sys.stderr)
        return 2

    # Resolve the provider key, falling back to the environment. Without this the
    # pipeline runs in MOCK mode -- `detect_provider` returns "mock" for an empty
    # key and does NOT consult the environment itself -- so every session would
    # block and the batch would report "no data" without saying why. Failing
    # loudly is the only honest option: a mock run produces a baseline that
    # measures nothing while looking like it measured something.
    api_key = args.api_key or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
    provider = args.provider or ("deepseek" if os.environ.get("DEEPSEEK_API_KEY") else None)

    if not api_key:
        print("No API key found.", file=sys.stderr)
        print()
        print("Set DEEPSEEK_API_KEY in the environment (backend/.env is loaded), or pass", file=sys.stderr)
        print("--api-key. Refusing to run: with no key the pipeline silently uses MOCK,", file=sys.stderr)
        print("every session blocks, and the resulting 'baseline' measures nothing.", file=sys.stderr)
        return 2

    print("Generation baseline")
    print("=" * 62)
    print(f"  blueprints : {', '.join(names)}")
    print(f"  provider   : {provider or 'default'}  (key present: {bool(api_key)})")
    print()

    summary = run_baseline(
        runner=lambda name: graph_runner(
            name, provider=provider, api_key=api_key, model_name=args.model
        ),
        blueprints=names,
    )

    unverified = summary["report"].excluded.get("unverified", 0)
    if unverified:
        print()
        print(f"  {unverified} of {len(names)} sessions could not be verified and were")
        print("  excluded from every figure above. If the container runtime is not")
        print("  reachable from this shell, that is why: the honest verifier refuses")
        print("  to substitute a synthetic success. Run this where the runtime works.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
