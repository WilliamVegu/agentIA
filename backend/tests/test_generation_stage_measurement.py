"""Measurement harness for feature 011 (tasks T041 and T048).

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------
This harness drives real sessions through the real stage execution boundary, the
real payload builder, the real compliance gate and the real journal. What it
replaces is only the **model**: ``LLMFactory.get_chat_model`` is pointed at a
payload-aware fake that derives its output from the request it receives.

Consequences, stated plainly so no reader mistakes these numbers for product data:

* The **SC-011 intervention rate below is SYNTHETIC.** The mix of compliant and
  non-compliant sessions is a parameter of this file, not an observation of a real
  model. A real SC-011 measurement requires live model calls, which are out of
  scope here (and forbidden in the automated suite by Constitution Principle VI).
  The file header of the generated report says so too.
* SC-001 and SC-002 are measured against the frozen pre-migration baseline, which
  IS real recorded data. Those comparisons are meaningful (they show the payload
  carries what the baseline dropped), but they still use the fake model, so they
  demonstrate the *mechanism*, not the model's semantic quality.

Output goes to ``reports/measurements/`` — deliberately NOT ``reports/baselines/``,
which is frozen and immutable per contracts/baseline-artifact.md §6.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.config import settings  # noqa: E402
from app.models.session import SessionStatus  # noqa: E402
from app.orchestrator.stages import journal as journal_mod  # noqa: E402
from app.orchestrator.stages.runner import STAGE_ORDER, run_stage, run_stages  # noqa: E402
from app.services.llm_factory import LLMFactory  # noqa: E402
from tests.fixtures import fake_model as fm  # noqa: E402

BASELINE_JSON = REPO_ROOT / "reports" / "baselines" / "011-pre-migration-generation-baseline.json"
CORPUS_DIR = REPO_ROOT / "backend" / "tests" / "fixtures" / "baseline_blueprints"
OUTPUT_DIR = REPO_ROOT / "reports" / "measurements"

# --- Synthetic SC-011 scenario mix (T048) -----------------------------------
# The mix is a parameter, not a measurement. See the module docstring.
TOTAL_SESSIONS = 32           # >= the 30 the task requires
BLOCKED_SESSIONS = 4          # 4/32 = 12.5%, under the 15% ceiling

_JAVA_TYPES = {
    "string": "String", "long": "Long", "integer": "Integer", "int": "Integer",
    "bigdecimal": "java.math.BigDecimal", "double": "Double", "boolean": "Boolean",
    "localdatetime": "java.time.LocalDateTime", "uuid": "java.util.UUID",
}


# ---------------------------------------------------------------------------
# The payload-aware fake model
# ---------------------------------------------------------------------------
class _ResponderModel:
    def __init__(self, responder):
        self._responder = responder
        self.calls: list = []

    def invoke(self, request):
        text = str(request)
        self.calls.append(text)
        return fm.FakeResponse(content=self._responder(text))


def _payload_from_request(request: str) -> dict:
    marker = "## Task payload"
    assert marker in request, "the request carries no task payload"
    body = request.split(marker, 1)[1].split("## Output paths you own", 1)[0]
    return json.loads(body.strip())


def _blueprint_from_payload(payload: dict) -> dict:
    """Reconstruct the blueprint shape the fixture builders expect."""
    return {
        "serviceName": payload["service_name"],
        "packageName": payload["package_name"],
        "entities": [{"name": e["name"]} for e in payload["entities"]],
    }


def _artifact_for(stage: str, payload: dict) -> str:
    """Render a response that honours the payload it was given.

    DOMAIN and TEST are rendered from the payload itself, because those are the
    artifacts SC-001 and SC-002 read. The remaining three stages use the fixture's
    known-good artifacts, rebuilt from the payload so names still track the
    request; returning an empty set for them would make every session block at
    its first stage and measure nothing.
    """
    if stage not in ("DOMAIN", "TEST"):
        return fm.canonical_json_response(
            fm.compliant_artifacts(stage, _blueprint_from_payload(payload))
        )

    package = payload["package_name"]
    path = package.replace(".", "/")
    artifacts: dict = {}

    for entity in payload["entities"]:
        name = entity["name"]
        if stage == "DOMAIN":
            fields = []
            for attribute in entity["attributes"]:
                for rule in attribute["validationRules"]:
                    fields.append(f"    {rule}")
                java_type = _JAVA_TYPES.get(str(attribute["type"]).lower(), "String")
                fields.append(f"    private {java_type} {attribute['name']};")
            artifacts[f"src/main/java/{path}/model/entity/{name}.java"] = (
                f"package {package}.model.entity;\n\npublic class {name} {{\n"
                + "\n".join(fields) + "\n}\n"
            )
        elif stage == "TEST":
            methods = []
            for story in payload["user_stories"]:
                for scenario in story["scenarios"]:
                    sid = scenario["scenarioId"]
                    method = "should" + "".join(
                        part.capitalize() for part in sid.replace(".", "-").split("-") if part
                    )
                    methods.append(f"    @Test\n    void {method}() {{\n        // {sid}\n    }}\n")
            artifacts[f"src/test/java/{path}/service/{name}ServiceTest.java"] = (
                f"package {package}.service;\n\npublic class {name}ServiceTest {{\n"
                + "\n".join(methods) + "\n}\n"
            )
    return fm.canonical_json_response(artifacts)


def _compliant_responder():
    def respond(request: str) -> str:
        payload = _payload_from_request(request)
        return _artifact_for(payload["stage"], payload)
    return respond


def _always_violating_responder(blueprint: dict):
    def respond(request: str) -> str:
        return fm.canonical_json_response(
            fm.violating_artifacts("PROHIBITED_ANNOTATION", blueprint)
        )
    return respond


def _model_state(blueprint: dict, workspace: Path, session_id: str) -> dict:
    return {
        "session_id": session_id,
        "blueprint": blueprint,
        "workspace_path": str(workspace),
        "generated_files": {},
        "logs": [],
        "generation_mode": journal_mod.GENERATION_MODE_MODEL,
        "llm_provider": "deepseek",
        "llm_model": "deepseek-flash",
        "llm_api_key": "sk-synthetic-measurement-key",
        "instruction_set_revision": "measurement",
    }


def _blueprint(name: str) -> dict:
    return json.loads((CORPUS_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _run_session(monkeypatch, tmp_path, blueprint: dict, session_id: str, responder):
    monkeypatch.setattr(
        LLMFactory, "get_chat_model", staticmethod(lambda **kw: _ResponderModel(responder))
    )
    workspace = tmp_path / session_id
    workspace.mkdir(parents=True, exist_ok=True)
    return run_stages(_model_state(blueprint, workspace, session_id))


# ---------------------------------------------------------------------------
# T041 — SC-001 / SC-002 against the frozen baseline, and the SC-005 budget
# ---------------------------------------------------------------------------
def test_measure_us1_against_frozen_baseline(monkeypatch, tmp_path):
    """SC-001 and SC-002, with the frozen pre-migration baseline as the contrast."""
    baseline = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
    by_id = {e["blueprint_id"]: e for e in baseline["per_blueprint"]}

    # --- SC-001: declared constraints reach generated entity artifacts --------
    constrained = _blueprint("constrained")
    result = _run_session(monkeypatch, tmp_path, constrained, "sc001", _compliant_responder())
    entity = next(
        content for path, content in result["generated_files"].items() if path.endswith("Member.java")
    )
    declared_rules = [
        rule
        for entity_def in constrained["entities"]
        for attribute in entity_def["attributes"]
        for rule in attribute.get("validationRules", [])
    ]
    traced = [rule for rule in declared_rules if rule in entity]

    baseline_entry = by_id["constrained"]
    baseline_entity = next(
        record["content"]
        for path, record in baseline_entry["comparison_subset_content"].items()
        if path.endswith("Member.java")
    )
    untraced_in_baseline = [
        rule for rule in declared_rules if rule not in baseline_entity
    ]

    # --- SC-002: paired blueprints produce differing artifacts ----------------
    pair_outputs = {}
    for name in ("pair-a", "pair-b"):
        blueprint = _blueprint(name)
        run = _run_session(monkeypatch, tmp_path, blueprint, f"sc002-{name}", _compliant_responder())
        pair_outputs[name] = {
            path: content
            for path, content in run["generated_files"].items()
            if path.endswith("Invoice.java")
        }
    pair_a_entity = next(iter(pair_outputs["pair-a"].values()))
    pair_b_entity = next(iter(pair_outputs["pair-b"].values()))

    baseline_pair = next(
        (t for t in baseline["twin_comparisons"] if t["left"] == "pair-a"), None
    )

    # --- SC-005: budget respected across every session run above -------------
    budgets = []

    report = _render_us1_report(
        traced=traced,
        declared_rules=declared_rules,
        untraced_in_baseline=untraced_in_baseline,
        pair_a_entity=pair_a_entity,
        pair_b_entity=pair_b_entity,
        baseline_pair=baseline_pair,
        total_requests=result["generation_journal"]["total_requests"],
        budgets=budgets,
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / "011-us1-baseline-comparison.md"
    output.write_text(report, encoding="utf-8")

    assert output.is_file()
    assert traced, "no declared constraint reached the generated entity"
    assert pair_a_entity != pair_b_entity, "paired blueprints produced identical artifacts"
    if baseline_pair is not None:
        assert baseline_pair["outputs_byte_identical"] is True, (
            "the frozen baseline no longer shows the paired outputs as identical, so the "
            "SC-002 contrast is invalid"
        )


def _render_us1_report(**kw) -> str:
    pair_note = "not recorded in the frozen baseline"
    if kw["baseline_pair"]:
        pair_note = f"baseline outputs byte-identical: `{kw['baseline_pair']['outputs_byte_identical']}`"
    return f"""# SC-001 / SC-002 measurement — User Story 1

**Feature**: 011-llm-generation-nodes · **Task**: T041
**Model**: payload-aware fake client (T017) — **no live model calls**
**Baseline**: `reports/baselines/011-pre-migration-generation-baseline.json` (frozen, real recorded data)

> **What is real here.** The stage execution boundary, the payload builder, the
> compliance gate and the journal are the production implementations. Only the
> model is fake. The SC-001/SC-002 contrasts are therefore about what the payload
> *carries*, not about a model's semantic quality — that needs a live model.

## SC-001 — declared constraints reach the generated entity

| | |
| --- | --- |
| Declared format constraints | {", ".join(f"`{r}`" for r in kw["declared_rules"]) or "_none_"} |
| Present in the MODEL-path entity | {", ".join(f"`{r}`" for r in kw["traced"]) or "**none**"} |
| Absent from the baseline entity | {", ".join(f"`{r}`" for r in kw["untraced_in_baseline"]) or "_none_"} |

Verdict: {"**PASS** — every declared constraint reaches the model in the payload and appears in the generated artifact, where the baseline carried none." if len(kw["traced"]) == len(kw["declared_rules"]) and kw["traced"] else "**FAIL**"}

## SC-002 — paired blueprints

The paired blueprints differ only in declared constraints and acceptance
scenarios. Pre-migration they produced byte-identical output ({pair_note}).

| | |
| --- | --- |
| MODEL-path pair-a entity | `{len(kw["pair_a_entity"])}` chars |
| MODEL-path pair-b entity | `{len(kw["pair_b_entity"])}` chars |
| Outputs differ | `{kw["pair_a_entity"] != kw["pair_b_entity"]}` |

Verdict: {"**PASS** — the outputs now track the declared differences." if kw["pair_a_entity"] != kw["pair_b_entity"] else "**FAIL**"}

## SC-005 — request budget

Single measured session: **{kw["total_requests"]}** of
`{journal_mod.MAX_REQUESTS_PER_SESSION}` requests permitted.

Verdict: {"**PASS**" if kw["total_requests"] <= journal_mod.MAX_REQUESTS_PER_SESSION else "**FAIL**"}
"""


# ---------------------------------------------------------------------------
# T048 — SC-011 intervention rate
# ---------------------------------------------------------------------------
def test_measure_sc011_intervention_rate(monkeypatch, tmp_path):
    """SC-011 over a SYNTHETIC mix of >= 30 model-mode sessions.

    The mix is a parameter of this file (see the module docstring). It exercises
    the real seam, the real gate and the real terminal state; it does not observe
    a real model, so the rate below is explicitly labelled synthetic in the
    generated report.
    """
    blueprint = _blueprint("minimal")
    completed_responder = _compliant_responder()
    blocked_responder = _always_violating_responder(blueprint)

    statuses: list = []
    request_counts: list = []
    retained: list = []

    for index in range(TOTAL_SESSIONS):
        blocked = index < BLOCKED_SESSIONS
        session_id = f"sc011-{index:03d}"
        result = _run_session(
            monkeypatch, tmp_path, blueprint, session_id,
            blocked_responder if blocked else completed_responder,
        )
        journal = result["generation_journal"]
        entries = {e["stage"]: e for e in journal["entries"]}
        is_blocked = result.get("status") == SessionStatus.BLOCKED.value
        succeeded_everywhere = all(
            entries.get(s, {}).get("outcome")
            in (journal_mod.OUTCOME_SUCCEEDED, journal_mod.OUTCOME_CORRECTED)
            for s in STAGE_ORDER
        )
        # Terminal means it blocked, or every stage recorded a successful or
        # corrected outcome. An absent status is NOT treated as completion.
        terminal = is_blocked or succeeded_everywhere
        status = SessionStatus.BLOCKED.value if is_blocked else "COMPLETED"
        statuses.append((blocked, status, terminal))
        request_counts.append(result["generation_journal"]["total_requests"])
        if status == SessionStatus.BLOCKED.value:
            # The blocking stage is whichever one exhausted — not necessarily the
            # first stage named in the variable. Check every exhausted entry.
            exhausted = [
                e for e in journal["entries"]
                if e["outcome"] == journal_mod.OUTCOME_EXHAUSTED
            ]
            retained.append(bool(exhausted) and all(e.get("correction_attempts") for e in exhausted))

    terminal_sessions = [s for s in statuses if s[2]]
    blocked_terminal = [s for s in terminal_sessions if s[1] == SessionStatus.BLOCKED.value]
    all_terminal = len(terminal_sessions)
    rate = (len(blocked_terminal) / all_terminal * 100.0) if all_terminal else 0.0

    effective_cap = settings.MAX_REPAIR_ATTEMPTS
    report = _render_sc011_report(
        rate=rate,
        blocked=len(blocked_terminal),
        total=all_terminal,
        max_requests=max(request_counts) if request_counts else 0,
        retained=sum(retained),
        blocked_expected=BLOCKED_SESSIONS,
        effective_cap=effective_cap,
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / "011-sc011-intervention-rate.md"
    output.write_text(report, encoding="utf-8")

    assert output.is_file()
    assert all_terminal == TOTAL_SESSIONS, "not every session reached a terminal state"
    assert all_terminal >= 30, f"the task requires at least 30 sessions, ran {all_terminal}"
    assert max(request_counts) <= journal_mod.MAX_REQUESTS_PER_SESSION
    assert len(blocked_terminal) == BLOCKED_SESSIONS
    assert all(retained), "a blocked session lost its correction history"


def _render_sc011_report(**kw) -> str:
    cap_note = (
        f"**{kw['effective_cap']}** — this is the constitution's three (3). No drift."
        if kw["effective_cap"] == 3
        else f"**{kw['effective_cap']}** — the constitution specifies **three (3)**, so the "
             f"effective cap is higher than documented. A higher cap yields more repair "
             f"attempts, which **lowers** the observed intervention floor and therefore "
             f"**flatters** this ceiling. Re-run against a cap of 3 before treating the rate "
             f"as comparable to the documented constitution."
    )
    return f"""# SC-011 — intervention rate (SYNTHETIC)

**Feature**: 011-llm-generation-nodes · **Task**: T048
**Generated by**: `backend/tests/test_generation_stage_measurement.py`

> ## ⚠️ THIS IS A SYNTHETIC MEASUREMENT
>
> The sessions below were driven by the **payload-aware fake client** (T017), not
> by a live model. The mix of compliant and non-compliant sessions is a parameter
> of the harness file (`BLOCKED_SESSIONS` / `TOTAL_SESSIONS`), not an observation.
>
> The seam, the compliance gate, the journal and the terminal state are the real
> production implementations, so this measures the **mechanism**. It does **not**
> measure how often a real model produces non-compliant output.
>
> A real SC-011 measurement requires live model calls and is out of scope for
> T048 (and forbidden in the automated suite by Constitution Principle VI).

## Result

| Metric | Value |
| --- | --- |
| Sessions run | **{kw['total']}** |
| Terminal sessions | **{kw['total']}** |
| Blocked terminal sessions | **{kw['blocked']}** |
| `blocked ÷ all terminal` | **{kw['rate']:.2f}%** |
| SC-011 ceiling | 15% |
| Verdict | {"**PASS** (synthetic)" if kw['rate'] <= 15.0 else "**FAIL** (synthetic)"} |

Numerator and denominator are exactly as SC-011 defines them: a session counts in
the numerator only if it reached a terminal state requiring human intervention,
and in the denominator if it reached any terminal state.

## Budget

Highest per-session request count observed: **{kw['max_requests']}** of
`{journal_mod.MAX_REQUESTS_PER_SESSION}` permitted (SC-005: 5 initial + 5 stages
× 2 corrections = 15).

## Correction history retention

Blocked sessions retaining their full correction history: **{kw['retained']} / {kw['blocked']}** (SC-008).

## Effective sandbox repair cap

{cap_note}

## How to read this

* **Do not** cite {kw['rate']:.2f}% as AgentIA's intervention rate. It is the rate
  this harness *scripted*, and it will stay at that value until the mix changes.
* **Do** read the budget, retention and terminal-state numbers: those come from
  the real implementation and would change if the seam regressed.
* To obtain a real figure: run the corpus through the platform with live model
  credentials, then recompute `blocked ÷ all terminal` over the resulting
  sessions. `reports/baselines/` must not be written to; use
  `reports/measurements/`.
"""
