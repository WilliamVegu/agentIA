#!/usr/bin/env python3
"""Run one SkillOpt iteration (FR-007 / T018).

    collect N training sessions
      -> reflect into bounded edits
      -> apply them to a COPY
      -> gate BOTH skills on the same held-out blueprints
      -> accept iff strictly greater
      -> log exactly one run record
      -> print current score, candidate score, decision, edit count

One iteration, one skill, no memory between runs. Everything the source method
uses to make skill training *stable* is absent by design: no rejected-edit buffer,
no learning-rate schedule, no epoch-wise slow/meta update, no multi-skill bank.

The original skill file is written **only** when a candidate is accepted, and then
its content is exactly the applied edit set.

Usage:
    python backend/scripts/run_skillopt.py [--skill PATH] [--iterations N]

Real execution needs a provider key; see the `--real` flag in `main()`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.models.skillopt import (  # noqa: E402
    DECISION_ACCEPTED,
    DECISION_ERROR,
    DECISION_NO_FAILURES,
    DECISION_NO_SESSIONS,
    DECISION_REJECTED,
    start_run,
    write_run,
)
from app.skills.document import load_skill  # noqa: E402
from scripts.skillopt.apply import apply_edits  # noqa: E402
from scripts.skillopt.collect import (  # noqa: E402
    COLLECTION_NO_FAILURES,
    COLLECTION_NO_SESSIONS,
    DEFAULT_LIMIT,
    collect_outcomes,
)
from scripts.skillopt.gate import HELD_OUT_DEFAULT, run_gate  # noqa: E402
from scripts.skillopt.reflect import reflect  # noqa: E402

DEFAULT_SKILL = REPO_ROOT / "backend" / "app" / "resources" / "skills" / "layer_architecture.md"


def run_iteration(
    *,
    skill_path: Path,
    runner: Callable[[str, Path], Any],
    n_training: int = DEFAULT_LIMIT,
    m: int = HELD_OUT_DEFAULT,
    iteration_id: str = "iteration",
    session_ids: Optional[Sequence[str]] = None,
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    output: Callable[[str], None] = print,
) -> Dict[str, Any]:
    """One iteration. Returns a summary; never leaves without a run record."""
    started = start_run()
    skill_path = Path(skill_path)
    summary: Dict[str, Any] = {
        "current_score": None, "candidate_score": None,
        "decision": DECISION_ERROR, "edit_count": 0,
        "held_out_blueprints": [], "error": None,
    }

    try:
        document = load_skill(skill_path)

        # 1. collect ---------------------------------------------------------
        collected = collect_outcomes(limit=n_training, session_ids=session_ids)
        training_ids = [record["session_id"] for record in collected["records"]]

        if collected["status"] == COLLECTION_NO_SESSIONS:
            summary["decision"] = DECISION_NO_SESSIONS
            _report(output, summary)
            write_run(started_at=started, n_training=0, n_held_out=m,
                      decision=DECISION_NO_SESSIONS, edits=[], **{})
            return summary

        if collected["status"] == COLLECTION_NO_FAILURES:
            # Nothing to learn from. Calling a model here would invent edits.
            summary["decision"] = DECISION_NO_FAILURES
            _report(output, summary)
            write_run(started_at=started, n_training=len(training_ids), n_held_out=m,
                      decision=DECISION_NO_FAILURES, edits=[])
            return summary

        failures = collected["failures"]

        # 2. reflect ---------------------------------------------------------
        edits = reflect(document, failures, api_key=api_key, provider=provider,
                        model_name=model_name)
        summary["edit_count"] = len(edits)

        # 3. apply to a COPY -------------------------------------------------
        applied = apply_edits(document, edits)
        candidate_path = skill_path.with_suffix(".candidate.md")
        applied.candidate.write(candidate_path)

        # 4. gate BOTH skills on the same held-out blueprints ----------------
        gate = run_gate(
            skill_path,
            candidate_path,
            runner=runner,
            training_session_ids=training_ids,
            iteration_id=iteration_id,
            m=m,
        )
        summary["current_score"] = gate.current_score
        summary["candidate_score"] = gate.candidate_score
        summary["decision"] = gate.decision
        summary["held_out_blueprints"] = gate.held_out_blueprints
        summary["unscorable"] = gate.unscorable

        # 5. accept only on a strict improvement -----------------------------
        if gate.decision == DECISION_ACCEPTED:
            skill_path.write_text(applied.candidate.render(), encoding="utf-8")

        _safe_unlink(candidate_path)

        # 6. exactly one record, on this exit path ---------------------------
        write_run(started_at=started, n_training=len(training_ids), n_held_out=len(gate.held_out_blueprints),
                  current_score=gate.current_score, candidate_score=gate.candidate_score,
                  decision=gate.decision, edits=edits)
        _report(output, summary)
        return summary

    except Exception as exc:
        # A failed iteration still leaves exactly one row, carrying the error.
        summary["decision"] = DECISION_ERROR
        summary["error"] = f"{type(exc).__name__}: {exc}"
        write_run(started_at=started, n_training=summary.get("training_count"),
                  n_held_out=m, decision=DECISION_ERROR,
                  edits=None, error=summary["error"])
        raise


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def _report(output: Callable[[str], None], summary: Dict[str, Any]) -> None:
    def _fmt(score):
        return "n/a" if score is None else f"{score:.4f}"

    output(f"  current_score   : {_fmt(summary['current_score'])}")
    output(f"  candidate_score : {_fmt(summary['candidate_score'])}")
    output(f"  decision        : {summary['decision']}")
    output(f"  edit count      : {summary['edit_count']}")


def _real_runner():
    """Execute one fresh session for a blueprint with a skill active.

    This is the production runner, and it is the only place that generator-side
    dependencies enter the loop. It runs a real generation session with the
    candidate skill pointed at by the active pointer.
    """
    def _run(blueprint_name: str, skill_path: Path):
        from scripts.skillopt.real_runner import execute_session
        return execute_session(blueprint_name, skill_path)
    return _run


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run one SkillOpt iteration.")
    parser.add_argument("--skill", default=str(DEFAULT_SKILL))
    parser.add_argument("--n-training", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--m", type=int, default=HELD_OUT_DEFAULT)
    parser.add_argument("--iteration-id", default="cli")
    parser.add_argument("--real", action="store_true",
                        help="execute real sessions for the gate (spends money)")
    args = parser.parse_args(argv)

    if not args.real:
        print(
            "Refusing to run: the gate needs a session runner. Pass --real to execute "
            "real sessions (this spends money and needs a provider key), or call "
            "run_iteration() from tests with an injected runner.",
            file=sys.stderr,
        )
        return 2

    from scripts.skillopt.real_runner import make_real_runner

    summary = run_iteration(
        skill_path=Path(args.skill),
        runner=make_real_runner(),
        n_training=args.n_training,
        m=args.m,
        iteration_id=args.iteration_id,
    )
    return 0 if summary["decision"] != DECISION_ERROR else 1


if __name__ == "__main__":
    raise SystemExit(main())
