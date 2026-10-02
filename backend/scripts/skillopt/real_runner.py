"""The production session runner for the gate (feature 014).

This is the only place generator-side dependencies enter the loop. It is used by
``run_skillopt.py --real`` and nowhere else; the test suite always injects a
scripted runner instead (Constitution Principle VI).

For each held-out blueprint it:

1. points the active-skill pointer at the skill under test, so injection actually
   uses it;
2. loads the blueprint fixture and runs a full generation session through the graph,
   which includes the sandbox build;
3. reads the build outcome and the verification-fallback marking;
4. restores the previous pointer.

**The pass signal is the build outcome, not the terminal status.** A session can
reach a terminal state without its build having been verified — and under permissive
mode a fallback returns success without compiling — so the gate reads
``build_success`` and the fallback marking together.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from app.orchestrator.graph import generation_graph
from scripts.skillopt.gate import BASELINE_BLUEPRINTS, ExecutionResult

REPO_ROOT = Path(__file__).resolve().parents[3]
CORPUS_DIR = REPO_ROOT / "backend" / "tests" / "fixtures" / "baseline_blueprints"
ACTIVE_POINTER = REPO_ROOT / "backend" / "app" / "resources" / "skills" / "active.md"


def _point_active_skill(skill_path: Path) -> Optional[str]:
    """Point the active pointer at `skill_path`, returning the previous content."""
    previous = ACTIVE_POINTER.read_text(encoding="utf-8") if ACTIVE_POINTER.exists() else None
    ACTIVE_POINTER.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE_POINTER.write_text(str(skill_path), encoding="utf-8")
    return previous


def _restore_pointer(previous: Optional[str]) -> None:
    try:
        if previous is None:
            ACTIVE_POINTER.unlink(missing_ok=True)
        else:
            ACTIVE_POINTER.write_text(previous, encoding="utf-8")
    except OSError:
        pass


def execute_session(blueprint_name: str, skill_path: Path) -> ExecutionResult:
    """Run one real session for a blueprint with `skill_path` active."""
    if blueprint_name not in BASELINE_BLUEPRINTS:
        raise ValueError(f"unknown held-out blueprint: {blueprint_name}")

    blueprint = json.loads((CORPUS_DIR / f"{blueprint_name}.json").read_text(encoding="utf-8"))
    workspace = Path(tempfile.mkdtemp(prefix=f"skillopt-{blueprint_name}-"))

    previous = _point_active_skill(Path(skill_path))
    try:
        state = {
            "session_id": f"skillopt-{blueprint_name}-{skill_path.stem}",
            "blueprint": blueprint,
            "workspace_path": str(workspace),
            "generated_files": {},
            "logs": [],
        }
        final = generation_graph.invoke(state)
    finally:
        _restore_pointer(previous)

    metrics = final.get("test_metrics") or {}
    fallback_used = bool(metrics.get("fallback_used", False))
    build_success = bool(final.get("build_success", False))

    # An execution with no build metrics at all could not be scored: `None` keeps it
    # out of the denominator rather than counting it as a failure.
    exit_code = None if not metrics else (0 if build_success else 1)

    try:
        shutil.rmtree(workspace, ignore_errors=True)
    except Exception:
        pass

    return ExecutionResult(
        blueprint=blueprint_name,
        session_id=final.get("session_id") or state["session_id"],
        exit_code=exit_code,
        fallback_used=fallback_used,
        detail=str(final.get("error") or ""),
    )


def make_real_runner():
    """A runner callable for `run_gate`, executing real sessions."""
    def _run(blueprint_name: str, skill_path: Path) -> ExecutionResult:
        return execute_session(blueprint_name, Path(skill_path))
    return _run
