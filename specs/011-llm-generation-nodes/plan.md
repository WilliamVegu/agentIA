# Implementation Plan: LLM-Driven Generation Stages

**Branch**: `skillopt_implementation` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/011-llm-generation-nodes/spec.md`

**Scope note**: This plan is deliberately held at the **integration-boundary level**. It names seams, contracts, ownership, and sequencing — not file-level edits or function bodies. Those belong to `/speckit-tasks`.

---

## Summary

The platform's five generation stages currently produce Java from hardcoded templates. This feature moves them onto the configured language model while keeping the platform's constitutional guarantees intact, by gating every artifact behind compliance validation before it reaches disk.

The plan introduces **one new integration seam** — a *stage execution boundary* — that both of the platform's disjoint execution paths call. Each stage becomes a pair of interchangeable implementations behind that seam: a model-driven implementation (new) and the existing deterministic implementation (retained verbatim as the offline fallback). The seam owns the concerns that must not be duplicated per stage: mode selection, request/correction budgeting, validation gating, provenance recording, and correction-journal retention.

Five constraints from the user shape the sequencing. In particular, **the pre-migration baseline is captured before any stage is migrated**, because three of the specification's success criteria are defined relative to it.

## Technical Context

**Language/Version**: Python 3.12 (runtime target of the existing backend)

**Primary Dependencies**: Existing stack only — FastAPI, LangGraph, LangChain provider clients. No new third-party dependency is introduced by this feature.

**Storage**: Existing session store, extended additively with a generation journal. Instruction set is stored as repository-tracked resource files.

**Testing**: pytest. A scripted fake model client is required so the model-driven path is testable without network access.

**Target Platform**: Linux server, same as the existing backend.

**Project Type**: Web service (backend orchestrator for a code-generation platform).

**Performance Goals**: Median end-to-end session duration with a live model within 3× the pre-migration median (SC-010). Session model consumption bounded at 5 stage requests plus at most 2 corrections per stage (SC-005).

**Constraints**: Offline operation must remain complete and intact (FR-013). Both execution paths must exhibit the migrated behavior (FR-022). Generated build configuration is constrained to the pre-cached dependency set (FR-017). Generated artifacts must contain no secrets (FR-018). The sandbox verifier is explicitly out of scope.

**Scale/Scope**: Five generation stages, two execution paths, one new seam, one new fallback-preserving implementation pair per stage. Correction budget of 2 per stage; session request budget of 15.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment | Status |
|---|---|---|
| **I. Strict Layering** | Generated code must still satisfy unidirectional layering. Enforced pre-persistence by the compliance gate (FR-004–FR-007) rather than by construction. The gate is what converts this from a hope into a guarantee. | **PASS** |
| **II. Immutable Contracts & Early Validation** | Request/response contracts must remain immutable records with declarative validation. Same mechanism: pre-persistence gate. | **PASS** |
| **III. Centralized Error Handling** | A global error handler must exist; this is a whole-project rule, which is why validation evaluates the accumulated artifact set (FR-005) and why FR-006 distinguishes local from accumulated violations. | **PASS** |
| **IV. Offline-First Determinism & Sandbox Isolation** | **Tension.** The feature introduces a network-dependent, non-deterministic generation step into a platform whose constitution mandates determinism. Justified by three mitigations: (a) the *build and verification* remain 100% hermetic — generation precedes them and does not touch the sandbox; (b) offline operation is preserved intact as the fallback path (FR-013), so a credential-free deployment behaves exactly as today; (c) generated build configuration is barred from declaring dependencies outside the pre-cached set (FR-017), which is the specific way a non-deterministic generator could break hermeticity. | **PASS (justified)** |
| **V. Quality Gates & Bounded Self-Repair** | **Tension — and a governance question, not just a technical one.** The constitution fixes autonomous correction at exactly three iterations. This feature adds a *separate* budget of two generation-stage correction attempts. The intended reading is that Principle V's cap governs the **build/test-driven repair loop** — corrections guided by a Maven stack trace — and that pre-persistence validation retry is a different loop with a different trigger. FR-009/FR-010 enforce that the two never share a counter. **A strict reading of Principle V as a global autonomy budget would make this an amendment, not an implementation.** Flagged in Complexity Tracking. Note also that the codebase already drifts here (the repair cap is configured at 5 while the constitution, README, and baseline report all state 3), so the project has precedent for treating the configured value as authoritative — which is itself an unresolved governance question this plan does not resolve. | **PASS (justified, amendment may be required)** |
| **VI. Secret Safety & Orchestrator Boundary** | Three sub-obligations, all satisfiable. *Zero hardcoded secrets*: provenance records provider and model identifier but never credentials — an explicit requirement to carry into tasks. *LangGraph boundary*: generation stays in the orchestrator, outside the generated artifact. *Zero LLM network calls in tests*: the generated service contains no model client, and the platform's own model-path tests must use a scripted fake client — never a live call. This last point is a hard test-strategy obligation on this feature, not an aspiration. | **PASS** |

**Gate verdict**: All six principles satisfied. Two require recorded justification (IV, V) and one (V) carries an open governance question. No principle is violated outright, so the gate passes and work proceeds; the V question is surfaced to the user rather than silently resolved.

## Project Structure

### Documentation (this feature)

```text
specs/011-llm-generation-nodes/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0: decisions with alternatives
├── data-model.md        # Phase 1: entities, state, journal schema
├── quickstart.md        # Phase 1: validation & measurement guide
├── checklists/
│   └── requirements.md  # Spec quality checklist (from /speckit-specify)
├── contracts/           # Phase 1: interface contracts
│   ├── instruction-document.md      # Instruction set format & revision scheme
│   ├── stage-execution.md           # The new stage execution boundary
│   ├── compliance-verdict.md        # Normalized validator result
│   └── baseline-artifact.md         # Pre-migration baseline format
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source layout (repository root)

```text
backend/
├── app/
│   ├── orchestrator/
│   │   ├── stages/              # NEW — the stage execution boundary
│   │   │   ├── runner.py        #   mode selection, budget, gate, provenance
│   │   │   ├── compliance.py    #   validator adapter → normalized verdict
│   │   │   └── journal.py       #   correction history accumulation
│   │   ├── nodes/               # EXISTING deterministic emitters, retained
│   │   └── state.py             # EXISTING state, extended additively
│   ├── resources/
│   │   ├── cve_database.json    # EXISTING resource-loader precedent
│   │   ├── skills/              # Sibling feature's dir — DO NOT COLLIDE
│   │   └── instructions/        # NEW — versioned instruction set
│   └── services/
│       └── pipeline_runner.py   # EXISTING path B — re-pointed at the seam
├── scripts/
│   └── capture_generation_baseline.py   # NEW — pre-migration baseline capture
└── tests/
    ├── fixtures/
    │   ├── baseline_blueprints/ # NEW — frozen blueprint corpus
    │   └── fake_model.py        # NEW — scripted model client for CI
    ├── test_generation_stages_model.py   # NEW — model-path behavior
    └── test_generation_stages_offline.py # NEW — fallback-path parity
reports/
└── baselines/
    ├── 011-pre-migration-generation-baseline.json   # NEW — machine-readable
    └── 011-pre-migration-generation-baseline.md     # NEW — human-readable
```

**Structure Decision**: The stage execution boundary is a new package under `backend/app/orchestrator/` because it orchestrates stages and owns session-scoped policy — it is agent-side control-plane logic, which keeps it on the correct side of the LangGraph boundary (Principle VI). Instruction resources live under `backend/app/resources/instructions/`, following the existing `cve_database.json` loader precedent that `specs/010-skill-injection/plan.md` also cites, and deliberately **separate from** `backend/app/resources/skills/` so this feature does not collide with the skill-injection work. The baseline is captured to `reports/baselines/` in both machine-readable and human-readable form because three success criteria depend on it and one of them (SC-001) requires content-level comparison.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Network-dependent, non-deterministic generation step in an offline-first platform (Principle IV) | FR-001 requires model-driven synthesis; the feature's entire value is that blueprint semantics survive into code, which fixed templates cannot do. | Making generation deterministic by pinning model output was rejected: it would require caching every blueprint→source mapping, which reintroduces templates under a different name. Retaining the deterministic path as an automatic fallback for credential-free deployments (FR-013) preserves the offline guarantee where it actually matters. |
| A second autonomous-correction budget (Principle V), capped at 2, separate from the repair loop's cap | FR-008 requires bounded recovery from a rejected generation response. Without a correction attempt, every non-compliant model response blocks the session, which SC-011 (intervention rate) cannot tolerate. | Reusing the repair loop's counter was rejected and is explicitly forbidden by FR-009: the two loops have different triggers (compliance verdict vs. Maven stack trace), different units of work (a stage's artifact set vs. a surgical patch), and different failure semantics. Sharing a counter would let a stage's validation churn consume the budget that exists to recover from real build failures. **Open governance question**: whether Principle V's cap is a *global* autonomy budget (requiring a constitution amendment) or the build-repair loop's cap (making this compliant). Surfaced to the user; not resolved here. |

## Migration Strategy

### Constraint 1 — Both execution paths

The two paths are genuinely disjoint today and share no runner:

| Path | Entry | Dispatch | State handling |
|---|---|---|---|
| **A — Graph-orchestrated** | Session creation endpoint → background pipeline | `generation_graph.stream(...)` over 8 LangGraph nodes | LangGraph merges each node's returned dict into accumulated state |
| **B — Sequential auto-pilot** | Auto-pilot start endpoint, or quick-start with auto-run | Direct calls to the five node callables in sequence | **Return values discarded.** Relies on the nodes mutating the `generated_files` and `logs` dicts *in place*, which happens to work today because each node does `state.get(...)` and mutates the retrieved object |

**This aliasing is the single most important integration hazard in the feature.** Path B works only by accident of today's implementation. A model-driven stage that constructs a fresh dict instead of mutating the retrieved one — the natural way to write it — would cause Path B to silently generate nothing and then hand an empty workspace to the security audit and DevOps stages. The failure would look like a downstream bug, not a generation bug.

**Decision: migrate at the stage implementation boundary, and re-point Path B at it.**

- The new stage execution boundary is the *only* place a stage is invoked. Both paths call it.
- Path A keeps the LangGraph graph as its dispatcher; the graph's node callables become thin delegations to the seam. The graph topology, node names, and conditional edges are unchanged, so the existing phase-transition events, build-log streaming, and repair-iteration events continue to fire without modification (FR-021).
- Path B is re-pointed from "five direct callables" to "the seam, invoked five times with accumulated state". It must **consume returned state** rather than rely on aliasing, which removes the hazard permanently rather than preserving it.
- Consequence to verify: Path B currently performs no sandbox verification and no repair (documented in `reports/agentia-state-map.md`). This feature **does not change that** — FR-023 keeps the repair stage's behavior unchanged, and closing the Path B verification gap is a separate concern. The plan must not accidentally couple the two.

Because both paths converge on one seam, FR-022 is satisfied by construction rather than by two parallel migrations that could drift.

### Constraint 2 — Baseline before migration

**Sequencing is a hard gate: no stage is migrated until the baseline artifact exists.** SC-001, SC-010, and SC-011 are all defined relative to a pre-migration baseline, and the baseline can only be captured while the deterministic implementation is the only implementation.

- **Script**: `backend/scripts/capture_generation_baseline.py` — its own script, runnable standalone, following the existing `backend/scripts/` convention.
- **Artifacts**: `reports/baselines/011-pre-migration-generation-baseline.json` (machine-readable, the one SC-001 diffs against) and a sibling `.md` summary for reviewers.
- **Frozen input corpus**: `backend/tests/fixtures/baseline_blueprints/` — a fixed set of blueprint documents, committed, so before/after runs are comparable. Without a frozen corpus, SC-002's paired-blueprint comparison is not reproducible.
- **What it records**: per blueprint — the generated artifact path set, a content hash per artifact, and the full content of a designated comparison subset (SC-001 needs behavior-level traceability, which hashes alone cannot show); per session — wall-clock duration; in aggregate — completed vs. human-intervention counts (SC-011).
- **Capture conditions**: the deterministic path with no model credentials, which is today's default behavior. Capture is therefore purely additive and cannot destabilize the running system.
- **Re-capture rule**: the baseline is immutable for the duration of the migration. If a defect is found in the capture script, the baseline is re-captured *before* any stage migration begins, never after.

### Constraint 3 — Offline path preserved; how the two coexist and switch

The deterministic implementations are **not deleted**. Each stage becomes a pair of interchangeable implementations behind the seam: the retained deterministic emitter, and the new model-driven emitter.

**The switch is decided once per session, at session start, never per stage.** Per-stage switching would produce hybrid output — some artifacts template-shaped, some model-shaped — which would make SC-001, SC-002, and SC-010 uninterpretable. The decided mode is recorded in session state and in the provenance record, so every session is auditable as wholly one or wholly the other.

Decision order at session start:

1. **Explicit operator selection wins.** A session may explicitly request deterministic generation even when credentials are present. This is required, not a convenience: the baseline capture depends on it, and it is what makes a controlled before/after comparison possible without juggling credentials.
2. **Explicit offline/mock selection** — the existing mock-signalling conventions on the session payload, and the existing offline-mock configuration knob — forces deterministic mode.
3. **Otherwise, attempt to construct the model client.** If it is unavailable (`None`) or construction fails, fall back to deterministic mode.
4. **Once a session has started in model-driven mode, it never falls back.** A stage that exhausts its correction budget blocks the session (FR-008, FR-010) — it does **not** revert to the deterministic implementation.

Step 4 is a deliberate and load-bearing distinction. The fallback is a **pre-request** condition, not a **post-failure** recovery. Allowing post-failure fallback would quietly reproduce the rejected "discard the response and use the template" policy, in which a prompt defect manifests as the platform silently emitting pre-migration boilerplate while reporting success — exactly the masking this feature must avoid, and it would make SC-001 unmeasurable. The seam must therefore treat "no model available" and "model responded but the response was rejected" as categorically different outcomes.

### Constraint 4 — Instruction storage and revision scheme

**Layout** (under the existing resource-loader precedent):

```text
backend/app/resources/instructions/
├── VERSION          # human-readable label; release notes pointer
├── manifest.json    # stage → instruction file mapping
├── scaffolder.md
├── domain.md
├── service.md
├── controller.md
└── test.md
```

**Revision scheme: content-addressed, with a human-readable label.**

- The **authoritative** instruction-set revision is a digest computed over the canonicalized map of stage → instruction content (stages sorted, content normalized for line endings). Truncated to a short hex form for readability.
- `VERSION` carries a human-facing label and changelog pointer, used in reporting and release notes. It is deliberately **not** the identifier recorded in provenance.

Rationale: a content digest changes automatically on any edit, cannot silently drift from the content it names, and requires no runtime Git dependency — important because a session workspace may be exported or executed without repository history. A bare `VERSION` file would let content and label diverge under a hurried edit. A bare Git SHA would be precise but would make provenance recording depend on a `.git` directory being present at runtime, and would change on unrelated commits touching the directory.

**Alternatives considered**: Git commit SHA (rejected: runtime Git dependency, non-local changes); explicit `VERSION`-only identifier (rejected: drifts from content); per-artifact ad-hoc prompt strings with no versioning (rejected: FR-020 requires a revision that identifies the exact instructions in force).

**Collision note**: this directory is intentionally distinct from `backend/app/resources/skills/`, which the skill-injection feature owns. Both are currently-empty placeholders in that feature's case; sharing a directory would entangle two independent features' lifecycles.

### Constraint 5 — Sandbox verifier explicitly out of scope

The sandbox verifier's synthetic-success fallback (documented in `reports/agentia-state-map.md`) is **a separate bug and is not a deliverable of this feature.** FR-023 preserves the verifier's behavior unchanged.

Its status in this plan is a **measurement dependency**, recorded here so the measurement design does not silently assume a working verifier:

- **It invalidates end-to-end pass/fail as a primary signal.** Because the verifier can report success without running a real build, "the session reached VERIFIED" cannot be used to judge whether model-generated code is correct. SC-003's fault injection must be performed **at the model boundary** (feed a known non-compliant response, assert nothing is persisted), not by observing session outcomes.
- **It weakens SC-011.** Intervention rate is still observable, but a *reduction* in interventions could come from the verifier's leniency rather than from better generation. SC-011 is therefore stated as a non-regression bound (must not worsen by more than 10 percentage points) rather than as an improvement target — a bound is robust to a lenient verifier in a way a target is not.
- **SC-010 remains measurable**, since duration is measured end-to-end regardless of what the verifier concludes.
- **Consequence for the plan**: for any claim about generated code being *correct*, verification must be performed by building the generated workspace directly, outside the platform's sandbox wrapper. The quickstart's validation guide specifies this explicitly.

## Phases & Deliverables

### Phase 0 — Baseline capture *(blocking gate)*

- [ ] Author the baseline capture script and the frozen blueprint corpus.
- [ ] Capture the pre-migration baseline and commit both artifacts.
- [ ] Confirm the captured baseline adequately supports SC-001 (content-level comparison available, not hashes alone), SC-010 (durations), and SC-011 (intervention counts).
- [ ] **Gate**: no stage migration may begin until this is complete and reviewed.

### Phase 1 — Design *(this command's output)*

- [x] Resolve all Technical Context unknowns; record decisions and rejected alternatives in `research.md`.
- [x] Define the stage execution boundary, the compliance verdict normalization, and the instruction document format in `contracts/`.
- [x] Define entities, session state extensions, and the correction journal in `data-model.md`.
- [x] Author the validation and measurement guide in `quickstart.md`.

### Phase 2 — Seam implementation, no stage migrated

- [ ] Introduce the stage execution boundary with the deterministic implementation wired in as the only implementation.
- [ ] Normalize the two existing validator families behind one verdict contract via an adapter — **without modifying the validators themselves** (spec assumption).
- [ ] Extend session state with the generation journal and provenance fields; extend storage additively.
- [ ] Install the scripted fake model client and confirm the model path is exercisable in CI without network access (Principle VI).
- [ ] **Parity check**: all sessions behave exactly as before. Path B consumes returned state instead of relying on aliasing. Existing end-to-end tests pass unchanged — they now describe the offline path.

### Phase 3 — Migrate the stages

- [ ] Migrate the stages in dependency order, lowest-risk first. Suggested order, with rationale:
  1. **domain** and **service** — highest value for SC-001 (blueprint semantics surface here), and their outputs are the most locally checkable.
  2. **controller** — carries the whole-project error-handler rule, exercising FR-005/FR-006.
  3. **test** — tied to acceptance scenarios; the main SC-002 signal.
  4. **scaffolder** — last, deliberately. Its output is build configuration, so its failure mode is a hermetic-build violation (FR-017) rather than a code-quality problem, and it is the stage least likely to benefit from model reasoning.
- [ ] After each stage: confirm both execution paths, confirm offline parity, confirm the correction budget and journal behave per contract.
- [ ] Confirm provenance is recorded for every artifact (FR-019) and that no credential ever reaches a provenance record (Principle VI).

### Phase 4 — Measurement

- [ ] Evaluate SC-001 and SC-002 against the frozen baseline.
- [ ] Evaluate SC-005 through SC-009 by fault injection at the model boundary.
- [ ] Evaluate SC-010 and SC-011 over the stated session counts, using direct workspace builds (not the sandbox wrapper) for any correctness claim.
- [ ] Re-evaluate the Constitution Check post-implementation, with particular attention to Principle V's open governance question.

## Dependencies & Measurement Risks

| Item | Nature | Effect on this plan |
|---|---|---|
| Sandbox verifier synthetic-success fallback | **Separate bug, not a deliverable** | Forces model-boundary fault injection and direct-build verification; SC-011 demoted from target to non-regression bound |
| Constitution Principle V cap ambiguity (3 documented vs. 5 configured) | **Open governance question** | The generation correction budget of 2 is compliant under the build-repair reading; the global-budget reading requires an amendment. Flagged, not resolved |
| Two overlapping constitutional validator implementations | Pre-existing, explicitly out of scope (spec assumption) | A normalization adapter is required at the seam; the validators' internal inconsistency is not repaired here |
| The existing node callables are covered by tests asserting template-specific strings | Pre-existing test contract | Those tests become the offline-path suite and must keep passing unchanged; they must not be rewritten to accommodate model output |
| Path B performs no sandbox verification or repair | Pre-existing gap, out of scope | Must not be "fixed" as a side effect; FR-023 keeps it as-is |
| No live model credentials in CI | Environment constraint (Principle VI) | Requires the scripted fake client; the existing mock provider returns "no client", which is the fallback trigger, so the fake must be a distinct concept from mock |

## Post-Design Constitution Re-Check

*Re-evaluated after Phase 1 design (`research.md`, `data-model.md`, `contracts/`).*

The gate verdict is **unchanged: all six principles satisfied**, with the same two recorded justifications (IV, V) and the same open governance question on V. Design decisions surfaced four items that were not visible at the pre-design gate; none changes the verdict, and all four are recorded here so they are not rediscovered during implementation.

| Design decision | Constitutional bearing | Assessment |
|---|---|---|
| **The compliance gate is not applied to the deterministic path** (`stage-execution.md` §2.2) | Principle IV — offline behavior must not change | Correct and required. The gate exists to constrain a non-deterministic generator; deterministic output is compliant by construction. Applying the gate offline would alter pre-migration behavior and break FR-013. The asymmetry is intentional and must be documented in code, since it will otherwise read as an oversight. |
| **Conservative severity merge tightens the gate** (`compliance-verdict.md` §5) | Principle V — quality gates | Strictly more protective. No violation. But it is a behavior change that can block previously-completing sessions, so it interacts with SC-011 and is the most likely source of a false regression attribution. Recorded in the measurement guidance. |
| **Generation journal and provenance records are persisted additively** (`data-model.md` §4) | Principle VI — zero hardcoded secrets | Compliant provided the journal never records credentials — an explicit invariant (data-model §7.6) and an explicit load-bearing absence: provider and model identifiers are recorded, API keys are not. Tasks must treat this as a requirement, not a default. |
| **The seam lives under `backend/app/orchestrator/`** (`plan.md` Project Structure) | Principle VI — LangGraph boundary | Compliant. The seam is control-plane logic and must not become a dependency of the generated artifact. Placement in the orchestrator keeps it on the correct side; a placement under `services/` would have invited leakage into the generated dependency surface. |

**No new violations. No Complexity Tracking entries added.** The two entries recorded at the pre-design gate remain the only ones, and the Principle V question remains surfaced rather than resolved.
