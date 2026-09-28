# Quickstart: LLM-Driven Generation Stages

**Feature**: LLM-Driven Generation Stages
**Branch**: `feature/011-llm-generation-nodes`
**Date**: 2026-09-28

A validation and measurement guide. It documents *how to prove the feature works* and *how to measure the specified outcomes*. Implementation detail belongs in `tasks.md`.

---

## 1. Prerequisites

| Requirement | Notes |
|---|---|
| Repository checkout at the feature branch | |
| Python 3.12 environment with backend requirements installed | `pip install -r backend/requirements.txt` |
| pytest | Configured at the repo root: `testpaths = backend/tests`, `pythonpath = backend` |
| Docker + a warm Maven cache | **Only** for direct workspace builds (§5). Not required for the automated suite. |
| Model credentials | **Not required for any automated check.** Required only for the manual live-model scenario (§4.3), which is a smoke test, not a gate. |

**Constitutional constraint on this guide**: no automated step may call a model provider over the network. Every model-path check runs against the scripted fake client (research D5). The live-model scenario in §4.3 is manual, explicitly labeled, and outside the automated suite.

---

## 2. Reference material

| Topic | Document |
|---|---|
| The seam's behavior and invariants | [contracts/stage-execution.md](contracts/stage-execution.md) |
| Verdict normalization and the severity merge | [contracts/compliance-verdict.md](contracts/compliance-verdict.md) |
| Instruction format and revision scheme | [contracts/instruction-document.md](contracts/instruction-document.md) |
| Baseline format and corpus requirements | [contracts/baseline-artifact.md](contracts/baseline-artifact.md) |
| Entities and state transitions | [data-model.md](data-model.md) |
| Decisions and rejected alternatives | [research.md](research.md) |

---

## 3. Phase 0 gate — baseline captured before any migration

Run this **first**, before any stage is migrated.

```bash
# Capture the pre-migration baseline using the deterministic path
python backend/scripts/capture_generation_baseline.py
```

**Expected outcome**: both artifacts appear under `reports/baselines/`, and the JSON contains, for each frozen blueprint, the artifact path set, per-artifact digests, full content for the comparison subset, a duration, and a terminal status.

**Verification checklist**:

- [ ] The constrained blueprint in the corpus produces output in which declared attribute constraints leave **no trace** — this is the pre-migration signature, and it is what SC-001 later measures against.
- [ ] The paired blueprints produce near-identical output — the pre-migration signature for SC-002.
- [ ] Durations are recorded per blueprint.
- [ ] The aggregate block reports completed and intervention counts.
- [ ] The corpus is committed and will not change during the migration.
- [ ] The baseline is treated as immutable from this point.

**Gate**: do not proceed to §4 on any stage until this checklist is complete and reviewed.

---

## 4. Functional validation

### 4.1 Offline parity — FR-013, SC-004

```bash
pytest backend/tests/test_generation_stages_offline.py -v
```

**Expected outcomes**:
- Every session completes with no model credentials.
- Generated output is **equivalent to the baseline** for each corpus blueprint.
- No correction attempts are recorded; the journal marks each stage `SUCCEEDED` with `request_count = 0`.
- The pre-existing end-to-end suite still passes unchanged. Those tests assert template-specific strings; they now describe the offline path and must not be rewritten to accommodate model output.

### 4.2 Model path against the scripted fake — FR-001…FR-012

```bash
pytest backend/tests/test_generation_stages_model.py -v
```

**Expected outcomes**:
- A well-formed scripted response passes validation and is persisted; provenance records carry provider, model, and instruction revision.
- A scripted response violating each constitutional rule in turn is rejected; **no file from it appears in the workspace**.
- A whole-project-rule omission does not reject the stage that cannot satisfy it (FR-006), and is recorded as `ACCUMULATED`.
- Two rejected responses followed by a passing one leaves both rejected attempts in the journal and persists only the third.
- Three rejected responses block the session, set the same terminal status the repair loop sets, and **retain the full correction history**.
- An unextractable response consumes an attempt and persists nothing.
- A missing instruction document raises at load time and never degrades to the deterministic path.

### 4.3 Both execution paths — FR-022

Run the graph-orchestrated path and the sequential auto-pilot path against the same blueprint.

**Expected outcomes**:
- Both produce the same artifact path set.
- Both produce provenance records.
- Neither relies on in-place mutation of dictionaries retrieved from state — verify by confirming the sequential path consumes returned state (this is the aliasing hazard from research D8; it must be gone, not merely unobserved).
- Graph-driven phase transitions, build-log streaming, and repair-iteration events still fire as before (FR-021).

### 4.4 Manual live-model smoke test *(not automated)*

Optional. Confirms real-provider behavior end to end. Requires credentials.

**Expected outcomes**: a session completes in `MODEL` mode; every artifact carries provenance naming the real provider and model; the journal's `total_requests` is at most 15; no credential appears anywhere in state, journal, provenance, or generated artifacts.

---

## 5. Correctness verification — build the workspace directly

**Do not use the platform's sandbox verifier as a measurement instrument.** It can report synthetic success without executing a build, and repairing it is explicitly out of scope (plan Constraint 5, research D11).

For any claim that generated code is correct, build and test the generated workspace directly:

```bash
# Build and test the generated project outside the platform's sandbox wrapper
docker run --rm --network none \
  -v "$(pwd)/<session-workspace>:/workspace" \
  -v "$HOME/.m2/repository:/root/.m2/repository:ro" \
  -w /workspace maven:3.9-eclipse-temurin-21 mvn test -o
```

**Expected outcome**: the build and tests succeed on a warm cache. An unresolved-dependency failure here is the FR-017 failure mode — the model declared something outside the allowlist — and it must be treated as a generation defect, not an environment problem. Note that the platform's own verifier would likely have absorbed exactly this failure into its environment fallback.

---

## 6. Measurement

### 6.1 SC-001 — blueprint semantics reach the generated service

Compare the migrated output against the baseline for the constrained corpus blueprint.

| Check | Expectation |
|---|---|
| Constraint traceability | Generated entity and test artifacts exhibit at least one behavior traceable to the declared constraints |
| Baseline contrast | The baseline output for the same blueprint exhibits none such |
| Coverage | 100% of designated entity and test artifacts pass the first check |

### 6.2 SC-002 — paired blueprints

Compare the paired blueprints' migrated output. The differences must correspond to the differing declared constraints and scenarios. Confirm the pre-migration pairing did **not** differ, using the baseline.

### 6.3 SC-003, SC-007, SC-008 — fault injection at the model boundary

Scripted responses, never session outcomes. Because the verifier is unreliable, a session that reaches a success terminal state proves nothing about compliance; the assertion must be on the workspace contents.

- [ ] Zero non-compliant artifacts persisted, across every constitutional rule.
- [ ] 100% of always-non-compliant sessions terminate within budget, blocked, with no unbounded retries.
- [ ] 100% of blocked sessions retain the full correction history for every exhausted stage.

### 6.4 SC-005, SC-009 — budget independence

- [ ] No session exceeds 15 requests.
- [ ] A session that exhausts the generation correction budget still has its full sandbox repair budget available. Inspect both counters.

### 6.5 SC-011 — absolute intervention ceiling

Measure over at least 30 sessions with a live model. SC-011 is an **absolute** threshold,
not a comparison against the frozen baseline, which cannot supply a session-level
intervention rate — its count is structurally zero by construction. See §7 of
[`reports/baselines/011-pre-migration-generation-baseline.md`](../../reports/baselines/011-pre-migration-generation-baseline.md).

- [ ] SC-011: human-intervention rate ≤ **15%**.

**SC-010 is retired** and needs no evaluation. It bounded session duration at 3× the
pre-migration median; that median is 1.134 ms of in-process string assembly with no I/O,
so the ratio compared two quantities four orders of magnitude apart and measured nothing
about this feature. The request budget is owned by SC-005 (§6.4). See
[research.md](research.md) D14.

**Interpretation caution — severity merge**: the compliance-verdict severity merge
(research D4/D13, `compliance-verdict.md` §5) increases blocking verdicts independently of
model quality, and against an absolute ceiling there is no baseline slack to absorb it.
Before attributing a rate above 15% to the migrated stages, check how many sessions
blocked on a violation that Family A alone would have rated non-blocking. The baseline
retains full content for its comparison subset precisely so this delta can be computed
post hoc. This is the single most likely false attribution in the measurement phase.

**Interpretation caution — verifier bias, now in the permissive direction**: the sandbox
verifier can report synthetic success without running a build (plan Constraint 5). A
lenient verifier under-reports blocked sessions, which makes an absolute ceiling *easier*
to pass. Meeting SC-011 therefore does not by itself demonstrate generation quality; read
it alongside SC-003 and the direct-build checks in §5.

---

## 7. Definition of done

- [ ] Phase 0 baseline captured, reviewed, and frozen before the first stage migration.
- [ ] Offline parity holds; the pre-existing suite passes unchanged.
- [ ] Every constitutional rule has a passing fault-injection check.
- [ ] Both execution paths exhibit the migrated behavior, and the aliasing hazard is removed.
- [ ] Provenance is complete for 99%+ of artifacts and contains no credentials.
- [ ] Budget independence verified.
- [ ] SC-001 and SC-002 evaluated against the frozen baseline; SC-005 budget verified; SC-011 absolute ceiling measured over ≥ 30 sessions. (SC-010 retired — no evaluation required.)
- [ ] Constitution Check re-evaluated, with a recorded decision on the Principle V governance question.
