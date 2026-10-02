#!/usr/bin/env python3
"""Generate a real project so the offline Maven cache can be warmed.

**Why this is needed.** The sandbox runs ``mvn test -o`` with ``--network none``
by design (constitution IV: every dependency must already be cached). So a cache
gap is *indistinguishable from a code defect at runtime* — both produce BLOCKED.
Warming the cache once, with network, removes that ambiguity.

**Why it generates rather than shipping a hand-written pom.** The project is built
by the agent's **own deterministic emitters**, so the ``pom.xml`` it warms is
exactly the ``pom.xml`` the sandbox will later build. A hand-written warm-up pom
could quietly omit a dependency and give false confidence — the cache would look
complete right up until the first real run failed.

**No model calls, no cost.** Only the deterministic emitters run; no provider is
contacted. The generated project is written to a directory you choose, so it
survives the script (unlike the baseline capture, which discards its workspace).

Usage:
    PYTHONPATH=backend .venv/bin/python backend/scripts/warm_maven_cache.py \\
        --output-dir /tmp/agentia-warmup

    # then, from a shell where the container runtime is reachable:
    docker run --rm -v ~/.m2/repository:/root/.m2/repository \\
        -v /tmp/agentia-warmup/minimal:/workspace -w /workspace \\
        maven:3.9-eclipse-temurin-21 mvn -B test
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.orchestrator.stages.deterministic import (  # noqa: E402
    controller,
    domain,
    scaffolder,
    service,
    test_synthesis,
)

CORPUS_DIR = REPO_ROOT / "backend" / "tests" / "fixtures" / "baseline_blueprints"

#: The deterministic stages, in the order the graph runs them. Each consumes the
#: accumulated state, so order matters: the controller stage needs the domain and
#: service artifacts to exist before it can refer to them.
STAGES = (
    ("scaffolder", scaffolder),
    ("domain", domain),
    ("service", service),
    ("controller", controller),
    ("test", test_synthesis),
)


def generate_project(blueprint_name: str, destination: Path) -> Dict[str, Any]:
    """Run the deterministic stages and write the project to `destination`."""
    blueprint_path = CORPUS_DIR / f"{blueprint_name}.json"
    if not blueprint_path.exists():
        raise FileNotFoundError(f"unknown blueprint: {blueprint_name}")
    blueprint = json.loads(blueprint_path.read_text(encoding="utf-8"))

    state: Dict[str, Any] = {
        "session_id": f"warmup-{blueprint_name}",
        "blueprint": blueprint,
        "workspace_path": str(destination),
        "generated_files": {},
        "logs": [],
    }

    for _name, module in STAGES:
        result = module.emit(state) or {}
        produced = result.get("generated_files") or {}
        state["generated_files"].update(produced)
        if result.get("logs"):
            state["logs"].extend(result["logs"])
        state.update({k: v for k, v in result.items() if k not in ("generated_files", "logs")})

    written = []
    for relative_path, content in state["generated_files"].items():
        target = destination / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(content), encoding="utf-8")
        written.append(relative_path)

    return {"blueprint": blueprint_name, "files": written, "destination": destination}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a project to warm the Maven cache.")
    parser.add_argument("--output-dir", default="/tmp/agentia-warmup")
    parser.add_argument("--blueprints", default="minimal",
                        help="comma-separated; one project per blueprint")
    args = parser.parse_args(argv)

    out_root = Path(args.output_dir)
    names = [n.strip() for n in args.blueprints.split(",") if n.strip()]

    print("Maven cache warm-up project")
    print("=" * 62)
    for name in names:
        destination = out_root / name
        destination.mkdir(parents=True, exist_ok=True)
        try:
            result = generate_project(name, destination)
        except FileNotFoundError as exc:
            print(f"  !! {exc}", file=sys.stderr)
            return 2
        print(f"  {name}: {len(result['files'])} files -> {destination}")
        for path in result["files"]:
            print(f"      {path}")

    first = out_root / names[0]
    print()
    print("  Generated with the deterministic emitters only: no model calls, no cost.")
    print("  The pom.xml above is the SAME one the sandbox will later build offline,")
    print("  so warming with it proves the cache covers what the sandbox needs.")
    print()
    print("  Now run this where the container runtime is reachable:")
    print()
    print("    docker run --rm \\")
    print("      -v ~/.m2/repository:/root/.m2/repository \\")
    print(f"      -v {first}:/workspace -w /workspace \\")
    print("      maven:3.9-eclipse-temurin-21 \\")
    print("      mvn -B test")
    print()
    print("  Note the absence of --network none and -o: this run is deliberately")
    print("  ONLINE so Maven can fill the gaps. The sandbox stays offline afterwards.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
