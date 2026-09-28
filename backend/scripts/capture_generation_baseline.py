#!/usr/bin/env python3
"""
Pre-migration baseline capture for feature 011-llm-generation-nodes (task T008).

WHAT THIS DOES
--------------
Runs the five retained *deterministic* generation stages over a frozen blueprint
corpus and records what they produce, how long they take, and — critically —
whether the constraints and acceptance scenarios declared in each blueprint leave
any observable trace in the generated source.

It exists because three success criteria (SC-001, SC-010, SC-011) are defined
relative to a pre-migration baseline, and that baseline is capturable only while
the deterministic implementation is the only implementation. Once the first stage
is migrated the window closes.

Reference: specs/011-llm-generation-nodes/contracts/baseline-artifact.md

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
- It does not require, read, or use model credentials. It never touches the LLM
  factory. This is a pre-request *deterministic* capture, which is exactly today's
  default behaviour, so the capture is purely additive and cannot destabilise the
  running platform.
- It does not invoke the sandbox verifier or the self-repair loop. Generation only.
  Consequence, recorded explicitly in the artifact: the "human intervention" count
  is a *generation-stage* count and is always zero here. It is NOT a session-level
  intervention rate, and SC-011's baseline must be captured at session level by
  separate means. This limitation is written into the output so it cannot be
  mistaken for the session-level figure later.
- It does not use the stage execution seam, which does not exist yet (T016). It
  calls the retained node callables directly. That is the point: it measures the
  implementation we are about to move away from.

USAGE
-----
    python backend/scripts/capture_generation_baseline.py
    python backend/scripts/capture_generation_baseline.py --corpus-dir ... --output-dir ...

Exit codes: 0 success, 1 one or more blueprints failed, 2 corpus unusable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import statistics
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --------------------------------------------------------------------------
# Path bootstrap (mirrors backend/scripts/seed_historical_baseline.py)
# --------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
for _p in (REPO_ROOT, BACKEND_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from app.orchestrator.nodes.scaffolder_node import scaffolder_node  # noqa: E402
from app.orchestrator.nodes.domain_node import domain_node  # noqa: E402
from app.orchestrator.nodes.service_node import service_node  # noqa: E402
from app.orchestrator.nodes.controller_node import controller_node  # noqa: E402
from app.orchestrator.nodes.test_node import test_node  # noqa: E402

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------
ARTIFACT_STEM = "011-pre-migration-generation-baseline"
DEFAULT_CORPUS_DIR = BACKEND_DIR / "tests" / "fixtures" / "baseline_blueprints"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "reports" / "baselines"

# The five stages in execution order. This mirrors the pre-migration dispatch used
# by the sequential auto-pilot path, which calls exactly these five callables.
STAGES: List[Tuple[str, Any]] = [
    ("SCAFFOLDER", scaffolder_node),
    ("DOMAIN", domain_node),
    ("SERVICE", service_node),
    ("CONTROLLER", controller_node),
    ("TEST", test_node),
]

# The designated comparison subset: the artifacts where SC-001's behaviour-level
# traceability lives. Digests alone can prove two outputs differ; they cannot show
# that an output reflects a declared constraint. So full content is retained for
# these and only these, keeping the committed artifact reviewable.
COMPARISON_SUBSET = [
    ("entity", re.compile(r"/model/entity/[^/]+\.java$")),
    ("request-contract", re.compile(r"/model/dto/Create[^/]+\.java$")),
    ("service-test", re.compile(r"/service/[^/]+ServiceTest\.java$")),
]

# Structural fields the rest of the platform depends on (FR-021). Recorded so that
# path-contract drift is detectable after migration.
STRUCTURAL_FIELDS = ["generated_files", "logs", "workspace_path", "blueprint"]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _to_pascal_case(text: str) -> str:
    cleaned = text.replace("-", " ").replace("_", " ")
    return "".join(w.capitalize() for w in cleaned.split())


def _package_path(blueprint: Dict[str, Any]) -> str:
    pkg = blueprint.get("packageName") or blueprint.get("package_name") or "com.corp.service"
    return pkg.replace(".", "/")


def _collect_artifacts_from_disk(workspace: Path) -> Dict[str, str]:
    """Read back exactly what the stages wrote. Ground truth is the filesystem,
    not the in-memory map, because the baseline must record what was produced."""
    artifacts: Dict[str, str] = {}
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(workspace).as_posix()
        try:
            artifacts[rel] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            artifacts[rel] = f"<binary:{path.stat().st_size} bytes>"
    return artifacts


def _is_comparison_member(rel_path: str) -> Optional[str]:
    for label, pattern in COMPARISON_SUBSET:
        if pattern.search(rel_path):
            return label
    return None


def _module_digests() -> Dict[str, str]:
    """Digest the five retained stage modules. This is the strongest part of the
    environment fingerprint: it pins the exact implementation the baseline was
    captured against, so a reviewer can confirm the capture really is
    pre-migration rather than trusting a timestamp."""
    digests: Dict[str, str] = {}
    for stage_name, fn in STAGES:
        src = Path(fn.__code__.co_filename)
        if src.exists():
            digests[stage_name] = _sha256(src.read_text(encoding="utf-8"))
    return digests


def _blueprint_signature(bp: Dict[str, Any]) -> str:
    """A structural signature used to detect twin blueprints that should produce
    identical output. Deliberately excludes validationRules and userStories — those
    are the only things the paired corpus members vary, and the whole question is
    whether they have any effect."""
    parts = [bp.get("serviceName", ""), bp.get("packageName", "")]
    for ent in bp.get("entities", []):
        attr_sig = ",".join(
            f"{a.get('name')}:{a.get('type')}:{a.get('nullable')}" for a in ent.get("attributes", [])
        )
        parts.append(f"{ent.get('name')}({attr_sig})")
    return "|".join(parts)


def _declared_validation_rules(bp: Dict[str, Any]) -> List[str]:
    rules: List[str] = []
    for ent in bp.get("entities", []):
        for attr in ent.get("attributes", []):
            for rule in attr.get("validationRules", []) or []:
                if rule not in rules:
                    rules.append(rule)
    return rules


def _count_scenarios(bp: Dict[str, Any]) -> int:
    return sum(len(story.get("scenarios", []) or []) for story in bp.get("userStories", []))


def _constraint_trace(blueprint: Dict[str, Any], artifacts: Dict[str, str]) -> Dict[str, Any]:
    """Determine, factually, which declared constraints are observable in output.

    This is the pre-migration signature SC-001 measures against. It is reported in
    two distinct categories rather than as a single 'no trace' claim, because the
    pre-migration stages DO honour one kind of constraint (a non-nullable attribute
    produces a required-attribute annotation) while ignoring format constraints and
    acceptance scenarios entirely. Collapsing those into one verdict would
    overstate the finding.
    """
    pkg_path = _package_path(blueprint)
    declared_rules = _declared_validation_rules(blueprint)

    traced_rules: Dict[str, List[str]] = {}
    untraced_rules: List[str] = []
    for rule in declared_rules:
        hits = [p for p, content in artifacts.items() if rule in content]
        if hits:
            traced_rules[rule] = sorted(hits)
        else:
            untraced_rules.append(rule)

    required_attrs = [
        a.get("name")
        for ent in blueprint.get("entities", [])
        for a in ent.get("attributes", [])
        if a.get("nullable") is False and not a.get("isPrimaryKey")
    ]
    required_annotation_observed = any(
        marker in content for content in artifacts.values() for marker in ("@NotBlank", "@NotNull")
    )

    test_method_counts: Dict[str, Any] = {}
    for ent in blueprint.get("entities", []):
        ent_name = ent.get("name", "Entity")
        key = f"src/test/java/{pkg_path}/service/{ent_name}ServiceTest.java"
        content = artifacts.get(key)
        test_method_counts[ent_name] = {
            "path": key,
            "present": content is not None,
            "test_method_count": content.count("@Test") if content else 0,
        }

    declared_scenarios = _count_scenarios(blueprint)
    observed_methods = sum(v["test_method_count"] for v in test_method_counts.values() if v["present"])
    # Pre-migration, the test stage emits a fixed method set per entity irrespective of
    # how many scenarios the blueprint declares, so the counts diverge. Report the
    # comparison directly rather than under a name that could be read backwards.
    counts_match = declared_scenarios > 0 and observed_methods == declared_scenarios

    return {
        "declared_validation_rules": declared_rules,
        "format_constraints_traced": traced_rules,
        "format_constraints_untraced": untraced_rules,
        "required_attributes_declared": required_attrs,
        "required_annotation_observed_in_output": required_annotation_observed,
        "test_method_counts": test_method_counts,
        "declared_scenario_count": declared_scenarios,
        "observed_test_method_count": observed_methods,
        "test_count_matches_declared_scenarios": counts_match,
        "tests_ignore_declared_scenarios": not counts_match,
        "verdict": (
            "Pre-migration signature: "
            f"{len(untraced_rules)}/{len(declared_rules)} declared format constraints leave no trace; "
            f"required-attribute annotation observed={required_annotation_observed}; "
            f"declared scenarios={declared_scenarios}, observed test methods={observed_methods}, "
            f"counts match={counts_match} (tests ignore declared scenarios={not counts_match})."
        ),
    }


def _run_stages_deterministic(blueprint: Dict[str, Any], workspace: Path) -> Dict[str, Any]:
    """Execute the five retained stages exactly as the pre-migration sequential path
    does, then accumulate returned state. The accumulation mirrors the corrected
    contract the seam will enforce (consume returned state) without altering what
    the stages themselves do, so the measurement stays faithful to the baseline."""
    state: Dict[str, Any] = {
        "session_id": f"baseline-{blueprint.get('blueprintId', 'unknown')}",
        "blueprint": blueprint,
        "workspace_path": str(workspace),
        "current_phase": "INITIALIZATION",
        "generated_files": {},
        "logs": [],
        "repair_attempts": 0,
    }
    stage_timings: List[Dict[str, Any]] = []
    for stage_name, fn in STAGES:
        t0 = time.perf_counter()
        out = fn(state)
        elapsed = (time.perf_counter() - t0) * 1000.0
        if isinstance(out, dict):
            state.update(out)
        stage_timings.append({"stage": stage_name, "duration_ms": round(elapsed, 3)})
    state["_stage_timings"] = stage_timings
    return state


def _duration_stats(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {"count": 0}
    return {
        "count": len(values),
        "median_ms": round(statistics.median(values), 3),
        "mean_ms": round(statistics.fmean(values), 3),
        "min_ms": round(min(values), 3),
        "max_ms": round(max(values), 3),
        "stdev_ms": round(statistics.stdev(values), 3) if len(values) > 1 else 0.0,
    }


# --------------------------------------------------------------------------
# Capture
# --------------------------------------------------------------------------
def capture(corpus_dir: Path, output_dir: Path) -> int:
    if not corpus_dir.is_dir():
        print(f"[ERROR] corpus directory not found: {corpus_dir}", file=sys.stderr)
        return 2
    blueprint_files = sorted(corpus_dir.glob("*.json"))
    if not blueprint_files:
        print(f"[ERROR] no blueprint JSON found in: {corpus_dir}", file=sys.stderr)
        return 2

    started_at = datetime.now(timezone.utc)
    workspace_root = Path(tempfile.mkdtemp(prefix="agentia-baseline-"))

    entries: List[Dict[str, Any]] = []
    failures = 0

    try:
        for bp_file in blueprint_files:
            print(f"[INFO] capturing {bp_file.name} ...")
            try:
                blueprint = json.loads(bp_file.read_text(encoding="utf-8"))
            except Exception as exc:  # noqa: BLE001
                failures += 1
                entries.append({
                    "blueprint_id": bp_file.stem,
                    "source_file": bp_file.name,
                    "terminal_status": "FAILED",
                    "error": f"unreadable blueprint: {exc}",
                })
                continue

            bp_id = blueprint.get("blueprintId") or bp_file.stem
            ws = workspace_root / bp_id
            ws.mkdir(parents=True, exist_ok=True)

            entry: Dict[str, Any] = {
                "blueprint_id": bp_id,
                "source_file": bp_file.name,
                "corpus_role": blueprint.get("corpusRole"),
                "service_name": blueprint.get("serviceName"),
                "package_name": blueprint.get("packageName"),
                "structural_signature": _blueprint_signature(blueprint),
                "entity_count": len(blueprint.get("entities", [])),
                "declared_scenario_count": _count_scenarios(blueprint),
            }

            t0 = time.perf_counter()
            try:
                state = _run_stages_deterministic(blueprint, ws)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                terminal_status = "COMPLETED"
                error = None
            except Exception as exc:  # noqa: BLE001
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                terminal_status = "FAILED"
                error = f"{type(exc).__name__}: {exc}"
                state = None
                failures += 1

            artifacts = _collect_artifacts_from_disk(ws)
            digests = {p: _sha256(c) for p, c in artifacts.items()}

            comparison_content: Dict[str, Any] = {}
            for rel, content in artifacts.items():
                label = _is_comparison_member(rel)
                if label:
                    comparison_content[rel] = {"subset_label": label, "content": content}

            entry.update({
                "terminal_status": terminal_status,
                "error": error,
                "duration_ms": round(elapsed_ms, 3),
                "generation_stage_duration_ms_total": round(elapsed_ms, 3),
                "artifact_count": len(artifacts),
                "artifact_paths": sorted(artifacts.keys()),
                "artifact_digests": digests,
                "comparison_subset_patterns": [label for label, _ in COMPARISON_SUBSET],
                "comparison_subset_artifact_count": len(comparison_content),
                "comparison_subset_content": comparison_content,
                "stage_timings": state.get("_stage_timings") if state else None,
                "structural_contract_present": (
                    sorted(k for k in STRUCTURAL_FIELDS if state and k in state) if state else []
                ),
                "constraint_trace": _constraint_trace(blueprint, artifacts),
            })
            entries.append(entry)
            print(
                f"        -> {terminal_status}, {len(artifacts)} artifacts, "
                f"{round(elapsed_ms, 1)} ms, "
                f"format constraints untraced: "
                f"{len(entry['constraint_trace']['format_constraints_untraced'])}"
            )

        # ------------------------------------------------------------------
        # Twin comparison: blueprints sharing a structural signature differ only
        # in their declared constraints and scenarios, so pre-migration output
        # must be identical. This is the SC-002 signature.
        # ------------------------------------------------------------------
        twin_groups: Dict[str, List[Dict[str, Any]]] = {}
        for e in entries:
            if e.get("terminal_status") == "COMPLETED":
                twin_groups.setdefault(e["structural_signature"], []).append(e)

        twin_comparisons: List[Dict[str, Any]] = []
        for sig, group in twin_groups.items():
            if len(group) < 2:
                continue
            base = group[0]
            for other in group[1:]:
                identical = base["artifact_digests"] == other["artifact_digests"]
                differing = sorted(
                    set(base["artifact_digests"]) ^ set(other["artifact_digests"])
                ) or sorted(
                    p for p in base["artifact_digests"]
                    if base["artifact_digests"][p] != other["artifact_digests"].get(p)
                )
                twin_comparisons.append({
                    "signature": sig,
                    "left": base["blueprint_id"],
                    "right": other["blueprint_id"],
                    "left_declared_rules": base["constraint_trace"]["declared_validation_rules"],
                    "right_declared_rules": other["constraint_trace"]["declared_validation_rules"],
                    "left_declared_scenarios": base["declared_scenario_count"],
                    "right_declared_scenarios": other["declared_scenario_count"],
                    "outputs_byte_identical": identical,
                    "differing_artifacts": differing,
                })

        durations = [e["duration_ms"] for e in entries if e.get("terminal_status") == "COMPLETED"]
        completed = [e for e in entries if e.get("terminal_status") == "COMPLETED"]
        failed = [e for e in entries if e.get("terminal_status") == "FAILED"]

        try:
            from app.config import settings  # noqa: PLC0415
            sandbox_image = settings.DOCKER_IMAGE
            maven_cache = str(settings.MAVEN_CACHE_DIR)
            workspace_dir = str(settings.WORKSPACE_DIR)
        except Exception:  # noqa: BLE001
            sandbox_image = maven_cache = workspace_dir = "unavailable"

        artifact = {
            "schema_version": 1,
            "feature": "011-llm-generation-nodes",
            "artifact": "pre-migration generation baseline",
            "artifact_stem": ARTIFACT_STEM,
            "generated_at": started_at.isoformat(),
            "generated_by": "backend/scripts/capture_generation_baseline.py",
            "capture_conditions": {
                "generation_mode": "DETERMINISTIC",
                "mode_note": (
                    "Forced deterministic. This script calls the five retained stage callables "
                    "directly and never constructs a model client, so no credentials were "
                    "required and no network call was made. This is the pre-migration "
                    "implementation and the only mode in which the baseline is capturable."
                ),
                "credentials_required": False,
                "stages_invoked": [name for name, _ in STAGES],
                "sandbox_verifier_invoked": False,
                "repair_loop_invoked": False,
                "immutability": (
                    "Frozen for the duration of the migration. Re-capturing after any stage is "
                    "migrated invalidates SC-001, SC-010 and SC-011. If this capture is found "
                    "defective it must be re-taken BEFORE migration begins, never after."
                ),
            },
            "corpus": {
                "directory": str(corpus_dir.relative_to(REPO_ROOT)),
                "blueprint_files": [f.name for f in blueprint_files],
                "blueprint_count": len(blueprint_files),
                "coverage": {
                    "paired_set": ["pair-a.json", "pair-b.json"],
                    "minimal_single_entity": ["minimal.json"],
                    "multi_entity_differing_types": ["multi-entity.json"],
                    "constrained_non_nullable_and_format": ["constrained.json"],
                },
            },
            "environment_fingerprint": {
                "python_version": sys.version.split()[0],
                "platform": platform.platform(),
                "implementation": "pre-migration deterministic f-string stage emitters",
                "stage_module_digests": _module_digests(),
                "network_access_used": False,
                "sandbox_image": sandbox_image,
                "maven_cache_dir": maven_cache,
                "workspace_dir": workspace_dir,
            },
            "per_blueprint": entries,
            "twin_comparisons": twin_comparisons,
            "aggregate": {
                "session_count": len(entries),
                "completed": len(completed),
                "failed": len(failed),
                "human_intervention": 0,
                "human_intervention_note": (
                    "Always zero in this capture, and NOT a session-level intervention rate. "
                    "This script exercises the generation stages only; it does not run the "
                    "sandbox verifier or the self-repair loop, which are the stages that "
                    "produce session-level interventions. SC-011's baseline must therefore be "
                    "captured at session level by separate means. Recording a zero here without "
                    "this caveat would make SC-011 look measurable when it is not."
                ),
                "duration_stats": _duration_stats(durations),
                "total_artifacts_generated": sum(e.get("artifact_count", 0) for e in entries),
            },
            "limitations": [
                "Generation-stage capture only. No sandbox verification, no self-repair, no session-level intervention rate.",
                "The blocked/intervention count is structurally zero here and must not be used as SC-011's baseline.",
                "Duration figures cover the five generation stages, not end-to-end session time. SC-010's comparison must use a like-for-like end-to-end measurement or state the difference.",
                "The sandbox verifier's synthetic-success fallback is out of scope for feature 011 and is not exercised or repaired by this script.",
            ],
        }

        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / f"{ARTIFACT_STEM}.json"
        md_path = output_dir / f"{ARTIFACT_STEM}.md"
        json_path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        md_path.write_text(_render_markdown(artifact), encoding="utf-8")

        print(f"\n[SUCCESS] wrote {json_path.relative_to(REPO_ROOT)}")
        print(f"[SUCCESS] wrote {md_path.relative_to(REPO_ROOT)}")
        print(
            f"[SUMMARY] {len(completed)}/{len(entries)} completed, {failures} failed, "
            f"median {artifact['aggregate']['duration_stats'].get('median_ms')} ms, "
            f"{artifact['aggregate']['total_artifacts_generated']} artifacts"
        )

        twins_ok = all(t["outputs_byte_identical"] for t in twin_comparisons)
        if twin_comparisons:
            print(
                f"[SIGNATURE] twin comparison: {len(twin_comparisons)} pair(s), "
                f"byte-identical={twins_ok} (expected True pre-migration)"
            )
        return 1 if failures else 0

    finally:
        shutil.rmtree(workspace_root, ignore_errors=True)


# --------------------------------------------------------------------------
# Markdown rendering
# --------------------------------------------------------------------------
def _render_markdown(a: Dict[str, Any]) -> str:
    agg = a["aggregate"]
    ds = agg["duration_stats"]
    env = a["environment_fingerprint"]
    lines: List[str] = []

    lines.append("# Pre-Migration Generation Baseline")
    lines.append("")
    lines.append(f"**Feature**: {a['feature']} (LLM-Driven Generation Stages)")
    lines.append(f"**Captured**: {a['generated_at']}")
    lines.append(f"**By**: `{a['generated_by']}`")
    lines.append(f"**Generation mode**: `{a['capture_conditions']['generation_mode']}` — "
                 f"implemented as {env['implementation']}")
    lines.append("")
    lines.append("> **Immutability.** This baseline is frozen for the duration of the migration. "
                 "It is capturable only while the deterministic implementation is the only "
                 "implementation. Re-capturing after any stage is migrated invalidates SC-001, "
                 "SC-010 and SC-011 at once.")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 1. Capture conditions")
    lines.append("")
    lines.append("| Condition | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Generation mode | `{a['capture_conditions']['generation_mode']}` |")
    lines.append(f"| Credentials required | `{a['capture_conditions']['credentials_required']}` |")
    lines.append(f"| Network access used | `{env['network_access_used']}` |")
    lines.append(f"| Stages invoked | `{', '.join(a['capture_conditions']['stages_invoked'])}` |")
    lines.append(f"| Sandbox verifier invoked | `{a['capture_conditions']['sandbox_verifier_invoked']}` |")
    lines.append(f"| Repair loop invoked | `{a['capture_conditions']['repair_loop_invoked']}` |")
    lines.append(f"| Python | `{env['python_version']}` |")
    lines.append(f"| Platform | `{env['platform']}` |")
    lines.append("")
    lines.append("**Implementation fingerprint** (SHA-256 of the retained stage modules — this is what "
                 "pins the capture to the pre-migration implementation):")
    lines.append("")
    lines.append("| Stage | Module digest |")
    lines.append("| --- | --- |")
    for stage, digest in env["stage_module_digests"].items():
        lines.append(f"| `{stage}` | `{digest[:16]}…` |")
    lines.append("")

    lines.append("## 2. Frozen corpus")
    lines.append("")
    lines.append(f"Directory: `{a['corpus']['directory']}` — {a['corpus']['blueprint_count']} blueprints.")
    lines.append("")
    lines.append("| Category | Files |")
    lines.append("| --- | --- |")
    for label, files in a["corpus"]["coverage"].items():
        lines.append(f"| {label.replace('_', ' ')} | {', '.join('`' + f + '`' for f in files)} |")
    lines.append("")

    lines.append("## 3. Per-blueprint results")
    lines.append("")
    lines.append("| Blueprint | Status | Artifacts | Duration (ms) | Declared rules | Untraced rules | Declared scenarios | Observed test methods |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for e in a["per_blueprint"]:
        if e.get("terminal_status") != "COMPLETED":
            lines.append(f"| `{e['blueprint_id']}` | **{e['terminal_status']}** | — | {e.get('duration_ms', 0):.1f} | — | — | — | — |")
            continue
        ct = e["constraint_trace"]
        lines.append(
            f"| `{e['blueprint_id']}` | {e['terminal_status']} | {e['artifact_count']} | "
            f"{e['duration_ms']:.1f} | {len(ct['declared_validation_rules'])} | "
            f"{len(ct['format_constraints_untraced'])} | {ct['declared_scenario_count']} | "
            f"{ct['observed_test_method_count']} |"
        )
    lines.append("")

    lines.append("## 4. Constraint and scenario trace — the SC-001 signature")
    lines.append("")
    lines.append("This is the core measurement. It is reported in two categories rather than as a "
                 "single \"no trace\" claim, because the pre-migration stages **do** honour one class "
                 "of constraint while ignoring the rest. Collapsing them would overstate the finding.")
    lines.append("")
    for e in a["per_blueprint"]:
        if e.get("terminal_status") != "COMPLETED":
            continue
        ct = e["constraint_trace"]
        lines.append(f"### 4.{a['per_blueprint'].index(e) + 1} `{e['blueprint_id']}`")
        lines.append("")
        lines.append(f"- Declared format constraints: "
                     f"{', '.join('`' + r + '`' for r in ct['declared_validation_rules']) or '_none_'}")
        lines.append(f"- **Traced in output**: "
                     f"{', '.join('`' + r + '`' for r in ct['format_constraints_traced']) or '**none**'}")
        lines.append(f"- **Untraced**: "
                     f"{', '.join('`' + r + '`' for r in ct['format_constraints_untraced']) or '_none_'}")
        lines.append(f"- Required (non-nullable) attributes declared: "
                     f"{', '.join('`' + r + '`' for r in ct['required_attributes_declared']) or '_none_'}")
        lines.append(f"- Required-attribute annotation observed anywhere in output: "
                     f"`{ct['required_annotation_observed_in_output']}`")
        lines.append(f"- Declared acceptance scenarios: **{ct['declared_scenario_count']}**; "
                     f"observed test methods: **{ct['observed_test_method_count']}**; "
                     f"counts match: `{ct['test_count_matches_declared_scenarios']}` → "
                     f"tests ignore declared scenarios: `{ct['tests_ignore_declared_scenarios']}`")
        lines.append("")
        lines.append(f"> {ct['verdict']}")
        lines.append("")

    lines.append("## 5. Twin (paired) comparison — the SC-002 signature")
    lines.append("")
    if not a["twin_comparisons"]:
        lines.append("_No twin blueprints detected in the corpus._")
    else:
        lines.append("Blueprints sharing a structural signature differ **only** in declared "
                     "constraints and acceptance scenarios. Since the pre-migration stages read "
                     "neither, their output must be byte-identical. That identity is precisely "
                     "what the migration is expected to break.")
        lines.append("")
        lines.append("| Left | Right | Declared rules L→R | Scenarios L→R | Byte-identical | Differing artifacts |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for t in a["twin_comparisons"]:
            lines.append(
                f"| `{t['left']}` | `{t['right']}` | {len(t['left_declared_rules'])}→"
                f"{len(t['right_declared_rules'])} | {t['left_declared_scenarios']}→"
                f"{t['right_declared_scenarios']} | **{t['outputs_byte_identical']}** | "
                f"{len(t['differing_artifacts'])} |"
            )
        lines.append("")
        all_identical = all(t["outputs_byte_identical"] for t in a["twin_comparisons"])
        lines.append(
            f"**Interpretation**: byte-identical=`{all_identical}` confirms that declared constraints and "
            "acceptance scenarios had **zero** effect on pre-migration output. The migrated "
            "implementation must make this comparison differ in exactly the corresponding artifacts."
        )
    lines.append("")

    lines.append("## 6. Aggregate")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    lines.append(f"| Blueprints captured | {agg['session_count']} |")
    lines.append(f"| Completed | {agg['completed']} |")
    lines.append(f"| Failed | {agg['failed']} |")
    lines.append(f"| Human intervention (generation-stage) | {agg['human_intervention']} |")
    lines.append(f"| Total artifacts generated | {agg['total_artifacts_generated']} |")
    lines.append(f"| Duration median (ms) | {ds.get('median_ms')} |")
    lines.append(f"| Duration mean (ms) | {ds.get('mean_ms')} |")
    lines.append(f"| Duration min / max (ms) | {ds.get('min_ms')} / {ds.get('max_ms')} |")
    lines.append(f"| Duration stdev (ms) | {ds.get('stdev_ms')} |")
    lines.append("")

    lines.append("## 7. Limitations — read before using this artifact")
    lines.append("")
    for lim in a["limitations"]:
        lines.append(f"- {lim}")
    lines.append("")
    lines.append("**Specifically on SC-011**: the intervention count above is structurally zero because "
                 "this capture never reaches the stages that produce interventions. It is not a "
                 "session-level rate and must not be used as SC-011's baseline. That baseline requires "
                 "a separate session-level capture.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Generated by `backend/scripts/capture_generation_baseline.py` (task T008) for feature "
                 "011-llm-generation-nodes. See `specs/011-llm-generation-nodes/contracts/baseline-artifact.md`.*")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture the pre-migration generation baseline for feature 011."
    )
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR,
                        help=f"Frozen blueprint corpus (default: {DEFAULT_CORPUS_DIR})")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
                        help=f"Artifact destination (default: {DEFAULT_OUTPUT_DIR})")
    args = parser.parse_args()

    print("[INFO] Pre-migration generation baseline capture")
    print(f"[INFO] repository root : {REPO_ROOT}")
    print(f"[INFO] corpus          : {args.corpus_dir}")
    print(f"[INFO] output          : {args.output_dir}")
    print("[INFO] mode            : DETERMINISTIC (no model client constructed)")
    print()

    try:
        return capture(args.corpus_dir, args.output_dir)
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
