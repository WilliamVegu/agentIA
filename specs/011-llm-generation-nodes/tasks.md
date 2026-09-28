---

description: "Task list for LLM-Driven Generation Stages"
---

# Tasks: LLM-Driven Generation Stages

**Input**: Design documents from `specs/011-llm-generation-nodes/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included. The specification requires them — SC-003 (fault injection covering every constitutional rule), SC-004 (offline parity), SC-007/SC-008 (bounded failure and journal retention) are all only verifiable by test. Per Constitution Principle VI, **no test may make a network call to a model provider**; every model-path test runs against the scripted fake client (T017).

**Organization**: Tasks are grouped by user story. Phases 1–2 are prerequisites for all stories; Phases 3–5 are the three user stories in priority order; Phase 6 is polish.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths are included in every task

## Path Conventions

Web application layout, per [plan.md](plan.md): backend at `backend/`, tests at `backend/tests/`, feature documentation at `specs/011-llm-generation-nodes/`, measurement artifacts at `reports/baselines/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Author the versioned instruction set and the dependency allowlist. These are content artifacts, independent of all code changes.

- [X] T001 Create the instruction resource directory with `backend/app/resources/instructions/VERSION` and `backend/app/resources/instructions/manifest.json`. The manifest MUST map each of the five stage names (`SCAFFOLDER`, `DOMAIN`, `SERVICE`, `CONTROLLER`, `TEST`) to its instruction file and MUST NOT be included in the instruction-set revision digest.

- [X] T002 [P] Author `backend/app/resources/instructions/scaffolder.md` with the four required sections (`## Technology contract`, `## Rules`, `## Output contract`, `## Prohibitions`). The Output contract MUST enumerate every workspace-relative artifact path the scaffolder owns. The Prohibitions section MUST forbid declaring any dependency outside the allowlist and MUST forbid credentials.

- [X] T003 [P] Author `backend/app/resources/instructions/domain.md` with the four required sections. Rules MUST be imperative and ordered; the Technology contract MUST explicitly state contract immutability (Request/Response as records) so the model is not left to infer it.

- [X] T004 [P] Author `backend/app/resources/instructions/service.md` with the four required sections. The Technology contract MUST state the layering direction explicitly (controller → service → repository → model).

- [X] T005 [P] Author `backend/app/resources/instructions/controller.md` with the four required sections. The Rules MUST require that no controller catches exceptions for error-body formatting, so the whole-project error-handler rule is satisfied by construction.

- [X] T006 [P] Author `backend/app/resources/instructions/test.md` with the four required sections. Rules MUST require tests derived from the supplied acceptance scenarios rather than a fixed set of method names.

- [X] T007 [P] Create `backend/app/resources/dependency_allowlist.json` seeded from the dependency set of the current known-good POM template. It MUST live **outside** `backend/app/resources/instructions/` so that editing it does not perturb the instruction-set revision.

**Checkpoint**: Instruction set and allowlist exist. No code depends on them yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Capture the pre-migration baseline, then build the seam. Both block every user story.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete. The baseline gate in particular is ordered first — see [plan.md](plan.md) Constraint 2.

### Baseline capture — blocking gate

- [X] T008 [GATE] Implement `backend/scripts/capture_generation_baseline.py` as a standalone script. It MUST force `DETERMINISTIC` mode, MUST NOT require credentials, and MUST record per blueprint: artifact path set, per-artifact content digest, full content for a designated comparison subset, wall-clock duration, and terminal status; plus aggregate completed/intervention counts, duration median and spread, session count, and an environment fingerprint. Content retention for the comparison subset is mandatory — SC-001 needs behavior-level traceability, which digests cannot provide. See [contracts/baseline-artifact.md](contracts/baseline-artifact.md) §4.

- [X] T009 [P] [GATE] Create the frozen blueprint corpus as `backend/tests/fixtures/baseline_blueprints/pair-a.json`, `pair-b.json`, `minimal.json`, `multi-entity.json`, and `constrained.json`, containing at least four blueprints per [contracts/baseline-artifact.md](contracts/baseline-artifact.md) §5: (a) a paired set differing only in declared attribute constraints and acceptance scenarios, (b) a minimal single-entity blueprint, (c) a multi-entity blueprint with differing attribute types, (d) a constrained blueprint whose attributes carry non-nullable and format constraints.

- [X] T010 [GATE] Run `backend/scripts/capture_generation_baseline.py` and commit both `reports/baselines/011-pre-migration-generation-baseline.json` and `reports/baselines/011-pre-migration-generation-baseline.md`. Verify the constrained blueprint's output leaves **no trace** of the declared constraints — this is the pre-migration signature SC-001 measures against. Depends on T008, T009.

> **🚫 GATE — do not start Phase 3 until T010 is complete and reviewed.** The baseline is capturable only while the deterministic implementation is the only implementation. Re-capture after any migration invalidates SC-001 and SC-002. (SC-010 was retired and SC-011 reframed as absolute and baseline-independent — [research.md](research.md) D14 — so neither is affected by a re-capture.)

### Seam infrastructure

- [ ] T011 [P] Implement the instruction loader and set-revision computation in `backend/app/orchestrator/stages/instructions.py`. Revision MUST be a digest over the canonicalized map of `stage → content` (stages sorted, line endings normalized), NOT a Git SHA and NOT the `VERSION` label. Loading MUST fail loudly — never fall back to the deterministic implementation — when any document is missing, when digests are inconsistent across the set, or when content appears to contain a credential. Invariant 11 of [contracts/stage-execution.md](contracts/stage-execution.md).

- [ ] T012 [P] Extend `backend/app/orchestrator/state.py` with four **additive** fields, all optional so existing callers still type-check: `generation_mode`, `instruction_set_revision`, `generation_journal`, `artifact_provenance`. Existing structural fields — generated-artifact map, log list, workspace path, repair-attempt counter, diagnostic field — MUST keep their current names and semantics. Do not introduce the correction counter as a new top-level state field; it lives in the journal.

- [ ] T013 [P] Extend `backend/app/models/session.py` additively with the generation journal and provenance storage. Storage MUST be a new additive column; the existing free-form phase-progress JSON column MUST NOT be repurposed, because the specification does not permit assuming existing columns change meaning. Provider and model identifiers MAY be stored; credentials MUST NOT.

- [ ] T014 [P] Implement the compliance verdict adapter in `backend/app/orchestrator/stages/compliance.py`. It MUST invoke **both** existing validator families, union their findings, deduplicate by `(artifact_path, rule_id)`, retain the most severe severity on collision, union `contributing_sources`, and carry `suggested_fix` through. Blocking rule MUST be `CRITICAL`, `BLOCKING`, and `HIGH` blocking; `MEDIUM` and `LOW` advisory. It MUST compute `attribution` as `LOCAL` when the violation's artifact path falls inside the current stage's `artifact_scope`, otherwise `ACCUMULATED`. The existing validators MUST NOT be modified. See [contracts/compliance-verdict.md](contracts/compliance-verdict.md).

- [ ] T015 [P] Implement journal accumulation in `backend/app/orchestrator/stages/journal.py`. `attempt_ordinal` MUST NOT exceed 2 — a third record is a budget violation and MUST fail loudly rather than be appended. `total_requests` MUST NOT exceed 15 (5 stages × (1 initial + 2 corrections)). The journal MUST record provider and model identifiers only, never credentials. A `CorrectionAttemptRecord` whose `request_digest` equals its predecessor's SHOULD be flagged, since an identical request yielding an identical rejection indicates the correction feedback was not incorporated.

- [ ] T016 Implement the stage execution boundary in `backend/app/orchestrator/stages/runner.py`. Single entry point for both execution paths. It MUST: resolve `generation_mode` and fail loudly if absent (never default); for `DETERMINISTIC` invoke the retained implementation with **no validation gate** and `request_count = 0`; for `MODEL` build the request, extract, validate against the accumulated set, and persist only on pass; append journal entries and provenance on **every** exit path including exhaustion; return **updated state** for callers to consume. The absence of the gate on the deterministic path is a deliberate, documented asymmetry — deterministic output is compliant by construction, and gating it would change offline behavior in violation of FR-013. Depends on T011–T015.

- [ ] T017 [P] Implement the scripted fake model client in `backend/tests/fixtures/fake_model.py`. It MUST return predetermined well-formed responses per stage, MUST support scripting a violation of each constitutional rule in turn, and MUST make **no network call** (Principle VI). It is a distinct concept from the platform's existing mock provider — that provider returns no client, which is the deterministic-fallback trigger, so reusing it would test the fallback path instead of the model path.

- [ ] T018 Implement session-start mode selection in `backend/app/api/routes_session.py` and `backend/app/services/pipeline_runner.py`, in this decision order: (1) an explicit operator request for deterministic generation wins even when credentials are present; (2) explicit offline/mock selection forces deterministic; (3) otherwise attempt to construct the model client and fall back to deterministic if it is unavailable or fails. The mode MUST be decided once per session and recorded before the first stage runs, so all five stages agree and the session is auditable as wholly one mode or the other.

- [ ] T019 Re-point the sequential execution path in `backend/app/services/pipeline_runner.py` at the seam, and make it **consume returned state**. It MUST NOT rely on in-place mutation of dictionaries retrieved from state. This removes the aliasing hazard recorded in [research.md](research.md) D8: the path currently discards node return values and works only because the stages mutate retrieved dicts in place, so a model-driven stage building a fresh dict would silently produce an empty workspace. Depends on T016.

- [ ] T020 Delegate the five existing node callables in `backend/app/orchestrator/nodes/scaffolder_node.py`, `domain_node.py`, `service_node.py`, `controller_node.py`, and `test_node.py` to the seam, keeping the graph's node names, topology, and conditional edges unchanged so that phase-transition events, build-log streaming, and repair-iteration events continue to fire (FR-021). The retained deterministic implementations MUST remain behaviorally identical to their pre-migration form. Depends on T016.

- [ ] T021 [P] Create `backend/tests/test_generation_stages_offline.py` asserting full offline parity (SC-004): every session completes with no credentials; generated output is equivalent to the captured baseline for each corpus blueprint; no correction attempts are recorded; and the pre-existing end-to-end suite passes **unchanged** — those tests assert template-specific strings and now describe the offline path. They MUST NOT be rewritten to accommodate model output. Depends on T010, T020.

**Checkpoint**: Baseline frozen, seam in place, both paths routed through it, offline parity proven, no stage migrated. Foundation ready.

---

## Phase 3: User Story 1 - Blueprint semantics reach the generated service (Priority: P1) 🎯 MVP

**Goal**: Each of the five stages obtains its artifacts from the configured model, driven by a mechanism-explicit instruction and a blueprint-derived payload, so that declared constraints and acceptance scenarios leave a trace in the generated source.

**Independent Test**: Run two sessions from the paired corpus blueprints and confirm the generated sources now differ in ways tracking the differing constraints and scenarios, and that output for the constrained blueprint exhibits behavior the baseline could not produce. See [quickstart.md](quickstart.md) §6.1–6.2.

### Implementation for User Story 1

- [ ] T022 [US1] Implement the task payload builder in `backend/app/orchestrator/stages/runner.py`. It MUST project the blueprint — service identity, package, entities with attributes/types/constraints, user stories, acceptance scenarios — and MUST include prior artifacts only from the union of the stage's declared dependencies' artifact scopes. It MUST include only already-persisted artifacts, never rejected ones. Payloads MUST NOT be silently truncated; an oversized payload records `UNUSABLE_RESPONSE` and consumes an attempt.

- [ ] T023 [US1] Implement model response extraction in `backend/app/orchestrator/stages/runner.py`. It MUST locate source content when the model wraps it in prose or a fenced block, discard surrounding commentary without corrupting the emitted file, and set `extraction_ok = false` for absent, truncated, or unmappable responses. Ambiguous responses (several artifacts where one was requested, or the reverse) MUST NOT be persisted silently. Every path in the candidate set MUST fall inside the stage's `artifact_scope`; an out-of-scope path is a rejection condition because a stage inventing paths would break the index contract (FR-021).

- [ ] T024 [P] [US1] Implement the model-driven domain stage in `backend/app/orchestrator/stages/model/domain.py` — instruction-driven artifact synthesis replacing the retained template emitter, persisting only on pass. Relevant artifact scope: entity and data-contract artifacts under the service package.

- [ ] T025 [P] [US1] Implement the model-driven service stage in `backend/app/orchestrator/stages/model/service.py` — instruction-driven artifact synthesis, persisting only on pass. Its Technology contract MUST carry the layering direction so generated service code cannot reach past its layer.

- [ ] T026 [P] [US1] Implement the model-driven test stage in `backend/app/orchestrator/stages/model/test.py` — artifact synthesis driven by the blueprint's acceptance scenarios rather than a fixed method set, persisting only on pass.

- [ ] T027 [P] [US1] Implement the model-driven controller stage in `backend/app/orchestrator/stages/model/controller.py` — artifact synthesis, persisting only on pass, with the no-ad-hoc-error-handling prohibition carried in the instruction so the whole-project rule is satisfied by construction rather than by correction.

- [ ] T028 [US1] Implement the model-driven scaffolder stage in `backend/app/orchestrator/stages/model/scaffolder.py`. Deliberately last of the five: its output is build configuration, so its failure mode is a hermetic-build violation rather than a code-quality problem. It MUST constrain declared dependencies to the allowlist from T007 and MUST NOT persist a configuration declaring anything outside it. Depends on T007.

- [ ] T029 [US1] Create `backend/tests/test_generation_stages_model.py` covering: a well-formed scripted response passes and is persisted; blueprint-declared constraints appear in generated entity and test artifacts where the baseline shows none; paired blueprints produce correspondingly differing output; unextractable responses consume an attempt and persist nothing; out-of-scope artifact paths are rejected. All tests use the fake client (T017) — no network calls.

**Checkpoint**: User Story 1 functional and independently testable against the frozen baseline.

> **⚠️ Not deployable on its own.** US1 without US2 persists model output gated only by the seam's minimal pass/fail policy, with no correction recovery and no adversarial verification. Do not enable model mode in a shared environment until Phase 4 is complete.

---

## Phase 4: User Story 2 - No non-compliant artifact is ever persisted (Priority: P2)

**Goal**: Artifacts that violate the platform's constitutional rules never reach the workspace, the session reports what blocked them, and rejection is recoverable within a bounded correction budget before the session blocks.

**Independent Test**: Drive a stage with a scripted response violating each constitutional rule in turn; confirm no file from that response reaches the workspace, the violation is reported with the offending artifact identified, and the session either recovers within budget or blocks without looping. See [quickstart.md](quickstart.md) §6.3.

### Implementation for User Story 2

- [ ] T030 [US2] Implement violation attribution handling in `backend/app/orchestrator/stages/runner.py`. A blocking `LOCAL` violation MUST reject the candidate set and consume a correction attempt. An `ACCUMULATED` violation MUST be recorded but MUST NOT reject the current stage or consume an attempt. This distinction is what stops a whole-project rule — notably the global error-handler requirement, satisfiable only after the controller stage has run — from rejecting the scaffolding, domain, service, and test stages for an omission none of them is responsible for. Depends on T014.

- [ ] T031 [US2] Implement the correction loop in `backend/app/orchestrator/stages/runner.py`: on a blocking `LOCAL` violation, re-request the stage's artifacts supplying the identified violations and their `suggested_fix` values back to the model, up to a maximum of **two** correction attempts per stage. After the second failure the session MUST transition to the human-intervention terminal state. The generation correction counter MUST be tracked separately from the sandbox repair counter and MUST NOT share, read, or write it. Depends on T030.

- [ ] T032 [US2] Make generation-budget exhaustion produce the **same** terminal session status the sandbox repair loop already produces on exhaustion, in `backend/app/orchestrator/stages/runner.py` and `backend/app/api/routes_session.py`, so the existing human-intervention path and unlock console handle both uniformly (FR-010). Verify the sandbox repair counter is untouched by generation-stage exhaustion. Depends on T031.

- [ ] T033 [P] [US2] Add adversarial fault-injection tests in `backend/tests/test_generation_stages_model.py`, one scripted case per constitutional rule, asserting zero artifacts persisted (SC-003). Injection MUST occur at the model boundary, not by observing session outcomes — the platform's verifier can report synthetic success, so a session reaching a success state proves nothing about compliance. Cover: layer isolation, contract immutability, missing centralized error handler, prohibited annotations, and embedded credentials.

- [ ] T034 [P] [US2] Add a whole-project-rule test in `backend/tests/test_generation_stages_model.py` asserting that a stage which cannot satisfy the global error-handler rule is not rejected for its absence (`ACCUMULATED` attribution), while a genuinely absent project-wide artifact is still surfaced at session level. Covers FR-006 and the concrete case in [contracts/compliance-verdict.md](contracts/compliance-verdict.md) §4.

- [ ] T035 [P] [US2] Add budget-exhaustion tests in `backend/tests/test_generation_stages_model.py` asserting that an always-non-compliant session terminates within budget, blocked, with zero non-compliant artifacts persisted and zero unbounded retries (SC-007), and that the generation correction budget never consumes or reduces the sandbox repair loop's available attempts (SC-009).

**Checkpoint**: User Stories 1 and 2 both functional. The gate is adversarial-verified against every constitutional rule.

---

## Phase 5: User Story 3 - Generation is attributable and bounded (Priority: P3)

**Goal**: Every artifact can be traced to the provider, model, and instruction revision that produced it; sessions are bounded; and a blocked session retains the full trajectory of rejected attempts.

**Independent Test**: Complete a session with the fake client and inspect provenance for each artifact — provider, model, and instruction revision all present and matching configured values. Then run an always-non-compliant session and confirm it blocks within budget while retaining every correction attempt. See [quickstart.md](quickstart.md) §6.4.

### Implementation for User Story 3

- [ ] T036 [US3] Implement provenance recording in `backend/app/orchestrator/stages/runner.py`, emitting one record per persisted artifact with `artifact_path`, `stage`, `generation_mode`, `provider`, `model`, `instruction_set_revision`, `attempt_ordinal`, and `created_at`. For `MODEL` sessions provider, model, and instruction revision MUST all be present. For `DETERMINISTIC` sessions provider and model MUST be **absent rather than filled with placeholders**, so offline sessions are not miscounted as model-generated. Credentials MUST never appear.

- [ ] T037 [US3] Implement per-session request accounting in `backend/app/orchestrator/stages/journal.py` and enforce the session budget of 15 requests (5 stage requests plus at most 2 corrections per stage), terminating in the human-intervention state on exhaustion. Depends on T015, T036.

- [ ] T038 [US3] Persist the generation journal and provenance through the additive storage in `backend/app/models/session.py`, driven from `backend/app/orchestrator/stages/journal.py`, and ensure the journal is written on every exit path including exhaustion. The correction history MUST be retained in full when the session terminates in the human-intervention state and MUST NOT be discarded on exhaustion; it MUST survive beyond process life, since the existing in-memory session stores do not. Depends on T013, T037.

- [ ] T039 [P] [US3] Add provenance and budget tests in `backend/tests/test_generation_stages_model.py`: at least 99% of generated artifacts carry a complete provenance record (SC-006); a `MODEL` session never transitions to `DETERMINISTIC`; a `DETERMINISTIC` session records no provider or model; no session exceeds 15 requests (SC-005); and no credential appears anywhere in state, journal, provenance, or generated artifacts (FR-018, Principle VI).

- [ ] T040 [P] [US3] Add journal-retention tests in `backend/tests/test_generation_stages_model.py` asserting that 100% of sessions terminating in the human-intervention state retain the complete correction history for every exhausted stage — the violation set and model response for each rejected attempt (SC-008) — including the oscillation case where a later attempt introduces a different violation.

- [ ] T041 [US3] Create the measurement harness in `backend/tests/test_generation_stage_measurement.py` driving the corpus through the model path and producing the SC-001 and SC-002 comparisons against the frozen baseline, plus verification of the SC-005 request budget, with output written alongside `reports/baselines/`. SC-010 is retired and SC-011 is absolute and baseline-independent, so neither is produced here (see [research.md](research.md) D14). Depends on T010, T029.

**Checkpoint**: All three user stories functional and independently verifiable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, governance, and end-to-end validation.

- [ ] T042 [P] Write `specs/011-llm-generation-nodes/migration-notes.md` recording the deliberate behavior change from the conservative severity merge in [contracts/compliance-verdict.md](contracts/compliance-verdict.md) §5: a Lombok-prohibition violation becomes blocking where one validator family alone rated it non-blocking. Note that this can convert previously-completing sessions into blocked ones, counts directly against SC-011's absolute 15% ceiling, and is the most likely source of a false attribution. Also record the substitute mitigation from [research.md](research.md) D13: the adapter can be run post hoc over the baseline's retained comparison-subset content to isolate the lenient-to-strict delta.

- [ ] T043 [P] Document the deliberate gate asymmetry in `backend/app/orchestrator/stages/runner.py` — the compliance gate applies to the `MODEL` path only — with the FR-013 rationale, so it is not later "fixed" as an oversight.

- [ ] T044 Record the Constitution Principle V governance decision in `specs/011-llm-generation-nodes/constitution-recheck.md`: whether the cap governs the build-repair loop only (making the generation correction budget compliant) or is a global autonomy budget (requiring an amendment). Re-evaluate the Constitution Check per [plan.md](plan.md) Post-Design Constitution Re-Check and record the outcome.

- [ ] T045 [P] Verify FR-021 holds end to end across `backend/app/api/routes_artifact.py` and `backend/app/api/routes_session.py`: artifact listing, session detail, and ZIP export still function, and the generated artifact path set and index contract are unchanged.

- [ ] T046 [P] Confirm the FR-023 boundary was not breached in `backend/app/orchestrator/nodes/sandbox_node.py` and `backend/app/orchestrator/nodes/repair_node.py`: the sandbox verifier and self-repair stage remain behaviorally unchanged, and Path B still performs no sandbox verification or repair — that pre-existing gap MUST NOT have been closed as a side effect.

- [ ] T047 Run the full validation suite documented in `specs/011-llm-generation-nodes/quickstart.md` §7 and confirm every definition-of-done item. Any correctness claim about generated code MUST be verified by building the workspace directly outside the platform's sandbox wrapper, never by reading session terminal status.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies. T002–T007 marked [P] can run in parallel.
- **Foundational (Phase 2)**: Depends on Setup. **Blocks all user stories.** The baseline gate (T008–T010) comes first and is irreversible once the first stage is migrated.
- **User Stories (Phases 3–5)**: All depend on Foundational. In priority order: US1 → US2 → US3.
- **Polish (Phase 6)**: Depends on all user stories.

### Critical ordering constraints

1. **T010 before T024–T028.** The baseline is capturable only while the deterministic implementation is the only implementation.
2. **T014 before T030, T016 before T019/T020.** The adapter and seam precede all consumers.
3. **T019 before T024–T028.** The sequential path must consume returned state before any model-driven stage exists, or it will silently produce an empty workspace.
4. **T007 before T028.** The scaffolder is the only stage constrained by the dependency allowlist, and it is migrated last for that reason.
5. **T012/T013 before T038.** Additive state and storage precede journal persistence.

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational. No dependency on US2 or US3. **Not deployable alone** — see the checkpoint warning.
- **US2 (P2)**: Can start after Foundational. Depends on US1's stage implementations to have something to reject; independently testable via scripted non-compliant responses.
- **US3 (P3)**: Can start after Foundational. Depends on US1 for artifacts to attribute. Independently testable via provenance and budget assertions.

### Within Each User Story

- Payload building and extraction before stage implementations.
- Stage implementations before their tests.
- The gate policy (T030) before the correction loop (T031), which precedes terminal-status parity (T032).

---

## Parallel Opportunities

### Setup phase

```bash
# All five instruction documents are independent files — launch together:
Task: "T002 Author scaffolder instruction in backend/app/resources/instructions/scaffolder.md"
Task: "T003 Author domain instruction in backend/app/resources/instructions/domain.md"
Task: "T004 Author service instruction in backend/app/resources/instructions/service.md"
Task: "T005 Author controller instruction in backend/app/resources/instructions/controller.md"
Task: "T006 Author test instruction in backend/app/resources/instructions/test.md"

# Plus, independently:
Task: "T007 Create backend/app/resources/dependency_allowlist.json"
```

### Foundational phase

```bash
# After T010 clears the gate, these touch different files:
Task: "T011 Implement instruction loader in backend/app/orchestrator/stages/instructions.py"
Task: "T012 Extend state in backend/app/orchestrator/state.py"
Task: "T013 Extend storage in backend/app/models/session.py"
Task: "T014 Implement verdict adapter in backend/app/orchestrator/stages/compliance.py"
Task: "T015 Implement journal in backend/app/orchestrator/stages/journal.py"
Task: "T017 Implement fake model client in backend/tests/fixtures/fake_model.py"
```

### User Story 1 — stage implementations

```bash
# Four stages are independent of each other once T022/T023 land:
Task: "T024 [US1] Implement model-driven domain stage"
Task: "T025 [US1] Implement model-driven service stage"
Task: "T026 [US1] Implement model-driven test stage"
Task: "T027 [US1] Implement model-driven controller stage"
# T028 (scaffolder) is deliberately sequential — depends on T007 and carries allowlist risk.
```

### User Story 2 — test authoring

```bash
Task: "T033 [P] [US2] Adversarial fault-injection tests, one per constitutional rule"
Task: "T034 [P] [US2] Whole-project-rule attribution test"
Task: "T035 [P] [US2] Budget-exhaustion and independence tests"
```

---

## Parallel Example: User Story 1

```bash
# Launch the four independent stage implementations together:
Task: "T024 [US1] Implement model-driven domain stage — entity and data-contract artifacts"
Task: "T025 [US1] Implement model-driven service stage — layering direction in the technology contract"
Task: "T026 [US1] Implement model-driven test stage — artifacts derived from acceptance scenarios"
Task: "T027 [US1] Implement model-driven controller stage — no ad-hoc error handling"
```

---

## Implementation Strategy

### MVP First

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational — **including the T010 baseline gate**. This phase is not optional and cannot be reordered.
3. Complete Phase 3: US1.
4. **STOP and VALIDATE**: run [quickstart.md](quickstart.md) §6.1–6.2 against the frozen baseline.
5. **Do not deploy.** US1 alone lacks correction recovery and adversarial verification. The MVP milestone is a validated internal increment, not a release.

### Incremental Delivery

1. Setup + Foundational (baseline frozen, seam live, offline parity proven) → no behavior change in production.
2. Add US1 → validate against baseline → internal increment.
3. Add US2 → the gate is adversarially verified → first point at which model mode is safe to enable in a shared environment.
4. Add US3 → attribution, budget enforcement, and journal retention → observable and operable.
5. Phase 6 → governance decision recorded, migration notes published.

### Parallel Team Strategy

With three developers after Foundational:

- **Developer A**: US1 stage implementations (T022–T029). Largest critical path; start here first.
- **Developer B**: US2 gate semantics (T030–T035) — can begin from scripted responses before US1 completes.
- **Developer C**: US3 provenance and budget (T036–T041) — depends on US1 artifacts but the accounting and persistence work can proceed in parallel.

US1 is the longest pole and gates the other two. If only one developer is available, run strictly in phase order.

---

## Notes

- **[P] tasks** touch different files and have no dependencies on incomplete tasks.
- **No task may introduce a network call to a model provider** (Constitution Principle VI). All model-path work uses the fake client from T017.
- The pre-existing test suite asserts template-specific strings and now describes the offline path. It MUST keep passing unchanged (T021); do not relax it to accommodate model output.
- The sandbox verifier and self-repair stage are explicitly out of scope (FR-023). T046 verifies that boundary was respected.
- Any correctness claim about generated code requires a direct workspace build, not a session terminal status (T047).
- Commit after each task or logical group; the baseline artifacts (T010) should be committed on their own so they are trivially identifiable.
