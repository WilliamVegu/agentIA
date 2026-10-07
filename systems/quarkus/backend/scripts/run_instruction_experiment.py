"""P4: does prohibition phrasing beat prescription -- and does it beat a placebo?

PRE-REGISTERED BEFORE THE RUN
=============================

**Primary metric.** Build-and-test pass rate, binary per session: ``build_success``
from the hermetic sandbox. Chosen because a binary whole-task outcome is measurable
at this sample size, where a conformance nudge of a few points is not (single-run
pass@1 varies 2.2-6.0 pp; arXiv:2602.07150).

**Secondary metrics.** First-attempt stage success, ``new_penalty`` (the absolute
baseline-relative conformance penalty), and cost per session.

**Arms.** ``control`` (the repository instructions), ``prohibition`` (the same
constraints, inverted polarity), ``placebo`` (length-matched to the treatment,
constraining nothing). Only the Rules section differs between arms.

**Decision rule, fixed in advance.** The comparison is paired by task.

* ``prohibition`` is supported only if it beats **both** ``control`` and ``placebo``
  on every task where they differ, in the same direction, on at least 6 of 6 tasks.
  At n=6 the minimum attainable two-sided p is 0.03125, so a unanimous result is the
  *only* significant one available. A less consistent result is reported as "no
  difference detected at this resolution" -- not as a trend.
* Beating ``control`` but **not** ``placebo`` is a **priming** result. That is a
  real finding and it is NOT evidence for polarity, which is exactly the
  distinction arXiv:2604.11088 draws between content-dependent and
  content-independent gains.
* ``placebo`` beating both is a pure priming effect with no instruction content.

**What this cannot show.** Six tasks cannot establish a modest effect. The honest
output here is a bound and a direction, and the report must say so.

**Cost.** Hard cap from the cost store; the run aborts cleanly and keeps whatever it
has recorded. Results are written incrementally so an abort is never data loss.
"""

from __future__ import annotations

import argparse
import json
import queue
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from scripts.instruction_arms import ARMS, build_arm, arm_revision  # noqa: E402

GRADED_DIR = REPO / "backend" / "tests" / "fixtures" / "graded_blueprints"

#: Six tasks, the arithmetic minimum at which a two-sided paired comparison can
#: reach p < 0.05 at all (0.03125). Three tiers, so the effect is not measured at a
#: single difficulty.
DEFAULT_TASKS = ("tier1-01", "tier2-01", "tier2-02", "tier3-01", "tier3-02", "tier4-01")


def _spend_usd() -> float:
    """Total recorded spend, from the platform's own store (the system of record).

    Reads the **call** records, not the session aggregates. The session table is
    written by the API route, and this experiment drives the graph directly, so the
    session rows never exist -- an earlier version of this function summed them,
    returned zero, and left the cost cap silently unenforced on a run that spends
    real money. A budget guard that cannot see the spend is worse than none, because
    it is trusted.
    """
    try:
        from app.cost.store import read_call_records

        return sum(float(record.get("cost_usd") or 0.0) for record in read_call_records())
    except Exception:
        return 0.0


def _run_session(
    *,
    arm: str,
    task: str,
    run_index: int,
    arm_dir: Path,
    provider: Optional[str],
    api_key: Optional[str],
    model_name: Optional[str],
    workspace_root: Path,
    tag: str = "",
) -> Dict[str, Any]:
    """One session: graph in, observed outcome out."""
    from app.orchestrator.graph import generation_graph
    from app.services.conformance_diagnostics import diagnose

    blueprint = json.loads((GRADED_DIR / f"{task}.json").read_text(encoding="utf-8"))
    scope = f"{tag}-" if tag else ""
    workspace = Path(
        tempfile.mkdtemp(prefix=f"p4-{scope}{arm}-{task}-r{run_index}-", dir=workspace_root)
    )
    session_id = f"p4-{scope}{arm}-{task}-r{run_index}"

    state: Dict[str, Any] = {
        "session_id": session_id,
        "blueprint": blueprint,
        "workspace_path": str(workspace),
        "generated_files": {},
        "logs": [],
        # The seam that makes this a controlled comparison rather than two runs
        # against two checkouts.
        "instruction_dir": str(arm_dir),
    }
    if provider:
        state["llm_provider"] = provider
    if api_key:
        state["llm_api_key"] = api_key
    if model_name:
        state["llm_model"] = model_name

    started = time.time()
    final_state = generation_graph.invoke(state)
    duration = time.time() - started

    metrics = final_state.get("test_metrics") or {}
    report = diagnose(dict(final_state.get("generated_files") or {}))

    return {
        "session_id": session_id,
        "arm": arm,
        "task": task,
        "run": run_index,
        "build_success": bool(final_state.get("build_success")),
        "terminal_status": final_state.get("status"),
        "verification_fallback_used": bool(metrics.get("fallback_used", False)),
        "tests_total": int(metrics.get("totalTests") or 0),
        "tests_passed": int(metrics.get("passedTests") or 0),
        "new_penalty": report.new_penalty,
        "raw_penalty": report.raw_penalty,
        "artifact_count": report.evaluated_artifact_count,
        "duration_seconds": round(duration, 1),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tasks", default=",".join(DEFAULT_TASKS))
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--arms", default=",".join(ARMS))
    parser.add_argument("--provider", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--cap-usd", type=float, default=10.0)
    parser.add_argument(
        "--workers", type=int, default=1,
        help=(
            "concurrent sessions. Sessions are independent (own workspace, own "
            "session id), and workers pull from the interleaved plan in order, so "
            "concurrency cuts wall-clock without unbalancing the arms."
        ),
    )
    parser.add_argument("--pilot", action="store_true",
                        help="1 run, 2 tasks: validate the harness cheaply first")
    parser.add_argument("--out", default="reports/measurements/instruction-polarity.json")
    parser.add_argument(
        "--resume", action="store_true",
        help=(
            "carry forward completed cells from --out and run only what is missing. "
            "A 90-session run takes hours; without this a relaunch re-runs cells under "
            "the SAME session ids and merges two attempts' cost under one identity."
        ),
    )
    parser.add_argument(
        "--tag", default="",
        help=(
            "run-scoped prefix on session ids and workspaces. Without it a re-run "
            "reuses the same session keys as an earlier one, so cost rows accumulate "
            "under one identity and the per-run spend becomes unattributable."
        ),
    )
    args = parser.parse_args(argv)

    tasks = [t.strip() for t in args.tasks.split(",") if t.strip()]
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    runs = 1 if args.pilot else args.runs
    if args.pilot:
        tasks = tasks[:2]

    # Resolve the provider key exactly as the corpus driver does, and import the
    # config first because that is what loads backend/.env into os.environ. With no
    # key `detect_provider` returns "mock" and does NOT consult the environment, so
    # every session would run deterministically, block, and produce an experiment
    # that measured nothing while looking like it measured something.
    import os

    import app.config  # noqa: F401  (loads backend/.env into os.environ)

    api_key = args.api_key or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
    provider = args.provider or ("deepseek" if os.environ.get("DEEPSEEK_API_KEY") else None)
    if not api_key:
        print("No API key found. Refusing to run:", file=sys.stderr)
        print("  with no key the pipeline silently uses MOCK, every session blocks,", file=sys.stderr)
        print("  and the resulting 'experiment' measures nothing.", file=sys.stderr)
        return 2

    arms_root = REPO / "warmup" / "instruction-arms"
    workspace_root = REPO / "warmup" / "p4-workspaces"
    workspace_root.mkdir(parents=True, exist_ok=True)

    revisions: Dict[str, str] = {}
    for arm in arms:
        arm_dir = build_arm(arm, arms_root / arm)
        revisions[arm] = arm_revision(arm_dir)

    total_sessions = len(tasks) * len(arms) * runs
    out_path = REPO / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # A 90-session run takes hours and dies with its shell. Resuming the cells that
    # already produced a record costs nothing and is the difference between losing
    # two hours of spend and losing none -- but the cells must be skipped rather than
    # re-run, because re-running reuses the SAME session id (arm/task/run) and would
    # accumulate two attempts' cost under one identity, making the per-cell spend
    # unattributable.
    records: List[Dict[str, Any]] = []
    done: set = set()
    if args.resume and out_path.is_file():
        try:
            previous = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            previous = {}
        for record in previous.get("records", []):
            if record.get("build_success") is None:
                continue  # an errored cell has no outcome; it is worth retrying
            records.append(record)
            done.add((record["run"], record["task"], record["arm"]))
        print(f"resume   : {len(done)} completed cell(s) carried forward")

    remaining = total_sessions - len(done)
    print(f"tasks    : {len(tasks)} -> {', '.join(tasks)}")
    print(f"arms     : {', '.join(arms)}")
    print(f"runs/task: {runs}   sessions: {total_sessions}   remaining: {remaining}")
    print(f"cap      : ${args.cap_usd:.2f}   spend already recorded: ${_spend_usd():.4f}")
    for arm, revision in revisions.items():
        print(f"  {arm:12} revision {revision[:16]}")
    print()

    baseline_spend = _spend_usd()

    def flush(status: str) -> None:
        out_path.write_text(
            json.dumps(
                {
                    "pre_registration": {
                        "primary_metric": "build_success (binary, per session)",
                        "decision_rule": (
                            "prohibition must beat control AND placebo on >= 6/6 tasks; "
                            "min attainable two-sided p at n=6 is 0.03125"
                        ),
                        "runs_per_task": runs,
                        "tasks": tasks,
                        "arms": arms,
                        "arm_revisions": revisions,
                    },
                    "status": status,
                    "spend_usd": round(_spend_usd() - baseline_spend, 4),
                    "records": records,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    aborted = ""
    lock = threading.Lock()

    # Interleaved by run, then task, then arm, so a provider degradation or a rate
    # limit hits all three arms at once rather than one arm entirely -- which is the
    # difference between noise and a fake effect. Workers pull from this queue in
    # that order, so concurrency preserves the interleaving rather than destroying
    # it.
    plan = [
        (run_index, task, arm)
        for run_index in range(1, runs + 1)
        for task in tasks
        for arm in arms
        if (run_index, task, arm) not in done
    ]
    work: "queue.Queue" = queue.Queue()
    for item in plan:
        work.put(item)
    stop = threading.Event()

    def worker() -> None:
        nonlocal aborted
        while not stop.is_set():
            try:
                run_index, task, arm = work.get_nowait()
            except queue.Empty:
                return
            try:
                # Checked per session, immediately before spending, because the
                # store only reflects COMPLETED sessions: checking once up front
                # would let an entire queue run past the cap.
                spent = _spend_usd() - baseline_spend
                if spent >= args.cap_usd:
                    with lock:
                        aborted = aborted or (
                            f"cost cap reached (${spent:.2f} >= ${args.cap_usd:.2f})"
                        )
                    stop.set()
                    return

                record = _run_session(
                    arm=arm,
                    task=task,
                    run_index=run_index,
                    arm_dir=arms_root / arm,
                    provider=provider,
                    api_key=api_key,
                    model_name=args.model,
                    workspace_root=workspace_root,
                    tag=args.tag,
                )
            except Exception as exc:  # noqa: BLE001
                # One failed session must not abandon the experiment: the sessions
                # either side of it are still evidence, and the failure is recorded.
                with lock:
                    records.append({
                        "arm": arm, "task": task, "run": run_index,
                        "error": f"{type(exc).__name__}: {exc}", "build_success": None,
                    })
                    flush("running")
                continue
            finally:
                work.task_done()

            with lock:
                records.append(record)
                print(
                    f"  r{run_index} {task:10} {arm:12} "
                    f"build={'PASS' if record['build_success'] else 'FAIL'} "
                    f"tests={record['tests_passed']}/{record['tests_total']} "
                    f"new_penalty={record['new_penalty']} ({record['duration_seconds']}s)"
                    f"   [{len(records)}/{total_sessions}, ${_spend_usd() - baseline_spend:.3f}]"
                )
                flush("running")

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(max(1, args.workers))]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            while thread.is_alive():
                thread.join(timeout=1.0)
    except KeyboardInterrupt:
        aborted = aborted or "interrupted"
        stop.set()

    flush("aborted: " + aborted if aborted else "complete")

    spend = _spend_usd() - baseline_spend
    print(f"\nsessions: {len(records)}/{total_sessions}   spend: ${spend:.4f}")
    if aborted:
        print(f"ABORTED: {aborted}")
    print(f"written : {out_path.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
