# Tasks: SkillOpt Compact

**Input**: Design documents from `/specs/014-skillopt-compact/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md), [constitution-recheck.md](constitution-recheck.md)

**Tests**: Included. The loop's whole value is that a gate decides what is learned, so the gate and the applier are tested before the orchestrator wires them together.

**Organization**: Tasks are grouped by user story. US1 injects the skill, US2 turns failures into edits, US3 applies and gates them, US4 makes one iteration observable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Maps to a user story in [spec.md](spec.md) — US1 (P1), US2 (P1), US3 (P2), US4 (P3)
- Every task names its exact file path

## Path Conventions

Repository root is the working directory. Backend paths are `backend/app/...`, scripts are `backend/scripts/...`, tests are `backend/tests/...`.

---

## ⚠️ Two Constraints That Shape Ordering (READ FIRST)

**1. The skill document and its loader come first.** Injection, the applier and the reflector all depend on being able to load a skill, validate its markers, and know where its editable region ends. Nothing else can be built or tested until that exists. T001–T002.

**2. Injection must land before anything reads it, and must be a no-op on absence.** The skills directory is currently empty apart from placeholders, and this is the first code to read it on the generation path. If injection errors on a missing pointer, every existing session breaks the moment it ships. SC-005 — the byte-identical no-op — is the regression guard, and it is written in the same task as the injection itself.

---

## Phase 1: Setup

**Purpose**: The skill document and the code that loads it. Everything downstream depends on both.

- [ ] T001 Author the seed skill at `backend/app/resources/skills/layer_architecture.md`. It MUST follow the structure in [contracts/skill-document.md](contracts/skill-document.md) §1: `# Title`, `## Granularity` (`task-level`), `## When to apply`, numbered `## Rules` covering controller → service → repository → model layering, and **both** `<!-- SLOW_UPDATE_START -->` / `<!-- SLOW_UPDATE_END -->` markers with `START` before `END`. Hand-written, short — of the order of 250 tokens. **The file already exists at 0 bytes**; this authors its content. The content is a placeholder for the loop's benefit and is NOT validated advice.
- [ ] T002 [P] Create `backend/app/skills/__init__.py` and `backend/app/skills/document.py`: a `SkillDocument` that parses a skill file into its sections and exposes the editable text with the protected region excluded. Validation MUST be strict per [contracts/skill-document.md](contracts/skill-document.md) §1 — a missing `SLOW_UPDATE_START` or `SLOW_UPDATE_END` marker, markers in the wrong order, a missing required section, or an empty file each **raises a load error**. A missing marker MUST NOT be treated as an empty protected region, or a typo would silently unprotect the region and the applier would edit it. Also provide serialisation back to text so a candidate can be written out.

**Checkpoint**: the seed loads; a document missing a marker is rejected.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Active-skill resolution, the run record, and the four loop stages. Each is independently testable.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T003 [P] Create `backend/app/skills/active.py`: resolve the active skill from `backend/app/resources/skills/active.md`. Per [contracts/skill-document.md](contracts/skill-document.md) §3, **absence, emptiness, unreadability, and a pointer naming a non-existent skill are all no-ops** — never an error. Return `None` in every such case. Absence is the normal state, not a failure.
- [ ] T004 [P] Create `backend/app/models/skillopt.py`: the `SkillOptRun` model and its table, plus write/read helpers. Fields exactly as [data-model.md](data-model.md) §5: `id`, `started_at`, `completed_at`, `n_training`, `n_held_out`, `current_score`, `candidate_score`, `decision`, `edits_json`, `error`. The table is created from the ORM metadata (the database currently holds only the session table, so no additive-column shim is needed). Writes MUST be best-effort with respect to the iteration — a logging failure must not lose the iteration's outcome — but MUST leave **exactly one row per iteration on every exit path, including failure**, so a crashed run is distinguishable from one that never ran.
- [ ] T005 [P] Create `backend/scripts/skillopt/__init__.py` and `backend/scripts/skillopt/collect.py`: read the most recent **N** sessions (default 12) and return one record per session carrying `spec_id`, `artifact_paths`, `build_exit_code`, `terminal_status`, `verification_fallback_used`. Order deterministically by session identifier so a re-run collects the same set. Per [data-model.md](data-model.md) §3, **"no failures" and "no sessions" are distinct outcomes** and MUST be distinguishable by the caller, and a failure classification MUST count a **fallback-marked** session as a failure however its status reads.
- [ ] T006 Create `backend/scripts/skillopt/apply.py`: apply atomic edits to a **copy** per [contracts/edits.md](contracts/edits.md). Four operations (`append`, `insert_after`, `replace`, `delete`), cap **L_t = 4**. Reject **individually** — a rejected edit MUST NOT abort the batch — when the target lies in the protected region, when the target text is not found, when the operation is unknown or a required field is missing, or when `content` is supplied for `delete`. The original file MUST NOT be modified by application. Depends on T002.
- [ ] T007 [P] Author the reflector prompt at `backend/scripts/skillopt/prompts/analyst_error.md`. It MUST record that it is **adapted from Appendix C.2.1 (`analyst_error.md`) of [arXiv:2605.23904](https://arxiv.org/abs/2605.23904)**, and MUST NOT reproduce the paper's prompt text. It MUST reference **this platform's** signals: build exit codes, terminal statuses, artifact paths, and the verification-fallback marking. It MUST instruct the model to emit only the structured edit list.
- [ ] T008 Create `backend/scripts/skillopt/reflect.py`: one model call taking the failed trajectories and the current skill and returning the structured edit list, capped at **L_t = 4**. The client MUST come from a **direct call to the model factory**, in the same request-construction path as the generation stages — no wrapper, no conditional, no shared helper. An unparseable response MUST be treated as a failure of the iteration, never applied as a partially parsed result. Depends on T007.

**Checkpoint**: the document loads, the pointer resolves or no-ops, the collector returns classified outcomes, the applier transforms a copy, and the reflector produces bounded edits.

---

## Phase 3: User Story 1 — The skill is injected into generation (Priority: P1) 🎯 MVP

**Goal**: Every model request carries the active skill's content alongside the stage's own instructions — and when there is no active skill, the request is byte-identical to before.

**Independent Test**: With an active skill, assert the skill's text appears in a rendered request. Remove the pointer, render again, and assert byte-identity with the pre-feature request.

### Tests for User Story 1

- [ ] T009 [P] [US1] Create `backend/tests/test_skillopt_injection.py`: assert the skill's content is present in a request rendered by the stage boundary when the active pointer names a valid skill; assert the request is **byte-identical** to the pre-feature rendering when the pointer is absent; assert empty, unreadable, and dangling-pointer cases are all no-ops that raise nothing; assert the stage's artifact scope and payload are unchanged by injection. Per [contracts/skill-document.md](contracts/skill-document.md) §4 and SC-005.

### Implementation for User Story 1

- [ ] T010 [US1] Update `backend/app/orchestrator/stages/runner.py` to **prepend** the active skill's content to the request it renders, alongside — never instead of — the stage's own instructions. When no skill resolves, render exactly what is rendered today. **This is the only change to the generation path in this feature**; do not touch the artifact scope, the payload, or the output contract. Depends on T002, T003.

**Checkpoint**: US1 works standalone. This is the MVP — it is the one part that pays off on the very next session.

---

## Phase 4: User Story 2 — A failed outcome becomes a proposed edit (Priority: P1)

**Goal**: Recent failures plus the current skill become a small bounded set of concrete edits.

**Independent Test**: Given recorded failures and a skill document, run reflection with a scripted client and assert a bounded list of well-formed edits.

### Tests for User Story 2

- [ ] T011 [P] [US2] Create `backend/tests/test_skillopt_collect.py`: assert one record per session with all five fields; assert deterministic ordering across two runs; assert **"no failures" and "no sessions" are distinguished**; assert a fallback-marked session with a completed status is classified as a **failure**.
- [ ] T012 [P] [US2] Create `backend/tests/test_skillopt_reflect.py`: with a scripted client, assert the returned edits are well-formed and capped at 4; assert more proposals than the budget are clipped to it; assert an **unparseable response** raises rather than applying a partial parse; assert the client is obtained by a direct factory call — the test replaces the provider class so the **real** factory runs, and the assertion fails if the reflector reached the model any other way.

### Implementation for User Story 2

*(T005, T007 and T008 deliver US2's implementation in Phase 2; this phase adds the tests that pin it.)*

**Checkpoint**: US1 and US2 both work independently. Collect and reflect turn recorded history into a candidate edit set.

---

## Phase 5: User Story 3 — An edit is applied only if it measurably helps (Priority: P2)

**Goal**: The candidate is scored on fresh executions the proposal was not derived from, and accepted only on a strict improvement.

**Independent Test**: Score a candidate and assert acceptance happens only on a strict improvement, ties are rejected, and the two evidence sets provably do not overlap.

### Tests for User Story 3

- [ ] T013 [P] [US3] Create `backend/tests/test_skillopt_apply.py`: every operation (`append`, `insert_after`, `replace`, `delete`) against a present target; **protected-region target rejected**; **not-found target rejected**; unknown operation and `delete`-with-content rejected; one bad edit among good ones does **not** abort the batch; and the **original file is unchanged after application**. Also cover the loader's strictness from T002: a document missing a marker, markers out of order, a missing section, and an empty file each raise.
- [ ] T014 [P] [US3] Create `backend/tests/test_skillopt_gate.py`: the three outcomes (**strictly greater → ACCEPTED**, **equal → REJECTED**, **lower → REJECTED**); both skills scored on the **identical** held-out selection; exactly **2×M** fresh executions (default 8); a **fallback-marked execution does not count as a pass even at exit code zero**; an **unscorable** execution is reported separately from a failure; the **disjointness assertion fails loudly** when a session identifier appears in both sets (forced in the test); and rotation is deterministic across two runs with the same iteration identity.

### Implementation for User Story 3

- [ ] T015 [US3] Create `backend/scripts/skillopt/gate.py`: execute fresh sessions against the held-out blueprints with the skill under test active, via a runner supplied **as a parameter** so the test injects a scripted one and no test calls a provider. Held-out set is the **five existing baseline blueprints** — **no new fixtures** — M=4 of 5 with one as a rotation buffer, rotated deterministically from the iteration's identity. Score = pass rate, where a pass is a **zero build/test exit code** and a **fallback-marked execution never passes**. Compute `current_score` and `candidate_score` in the same run on the identical selection, and **assert disjointness against the collected training outcomes, failing loudly rather than scoring on overlap**. Depends on T004, T005.

**Checkpoint**: US1–US3 all functional. A candidate that does not strictly beat the current skill is rejected, and the comparison is provably made on unseen evidence.

---

## Phase 6: User Story 4 — One iteration is observable and reproducible (Priority: P3)

**Goal**: One command runs the whole loop, prints the four facts, and leaves exactly one run record.

**Independent Test**: Run one iteration with a scripted client and an injected runner; assert the four printed facts and exactly one row.

### Tests for User Story 4

- [ ] T016 [P] [US4] Create `backend/tests/test_skillopt_iteration.py`: one full iteration with a scripted client and injected runner completes and prints **current score, candidate score, decision, edit count**; **exactly one** run row exists with both scores, the decision, the proposed edits, and the sample sizes; a **failing** iteration also leaves exactly one row carrying the error; **no failures** and **no sessions** stop the iteration **without calling a model**; and re-running the same iteration identity selects the same held-out blueprints.
- [ ] T017 [US4] Add the opt-in real iteration to `backend/tests/test_skillopt_iteration.py`, gated behind `AGENTIA_RUN_REAL_SKILLOPT` **and** a provider key so the default suite makes no provider call (Constitution Principle VI). It MUST skip cleanly when either is absent, and the skip reason MUST name which one is missing. **If it skips, SC-007 is reported as *not verified*, never inferred from the scripted path.**

### Implementation for User Story 4

- [ ] T018 [US4] Create `backend/scripts/run_skillopt.py`: the single-iteration orchestrator. Collect N training sessions → reflect into edits → apply to a candidate copy → gate **both** skills on the identical held-out selection → accept iff strictly greater → log exactly one run row on every exit path → print current score, candidate score, decision, and edit count. Dependency order: T005, T006, T008, T015.

**Checkpoint**: all four stories functional. One command, one iteration, one record.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T019 Run the full suite and verify the guardrails: `backend/app/orchestrator/graph.py`, all node files, the deterministic emitters, the model stages, both validator families, and every test file from specs 011/012/013 are byte-identical; `backend/tests/fixtures/fake_model.py` changed **additively only** if it changed at all; and **no sixth blueprint** was added under `backend/tests/fixtures/baseline_blueprints/`.
- [ ] T020 [P] Validate `specs/014-skillopt-compact/quickstart.md` scenarios 1–6 by running their commands and recording the observed output in `specs/014-skillopt-compact/quickstart.md`.
- [ ] T021 Verify the injection no-op guard directly against `backend/app/orchestrator/stages/runner.py`: render a request with no active pointer and confirm it is byte-identical to the rendering produced by the pre-change code path, then confirm generation still completes end to end with no pointer present, recording the evidence in `specs/014-skillopt-compact/quickstart.md`.
- [ ] T022 Reconcile the design artifacts with what was built: update `specs/014-skillopt-compact/plan.md`, `specs/014-skillopt-compact/research.md`, `specs/014-skillopt-compact/constitution-recheck.md`, and `specs/014-skillopt-compact/quickstart.md` with the actual outcomes — including the SC-007 result from T017 — and mark every task in `specs/014-skillopt-compact/tasks.md` complete.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies. **T001–T002 gate everything.**
- **Foundational (Phase 2)**: depends on T002 for the applier and T007 for the reflector. Blocks all user stories.
- **User Stories (Phases 3–6)**: depend on Phase 2. US1 is independent and is the MVP; US2 supplies the edits; US3 consumes them; US4 wires the loop.
- **Polish (Phase 7)**: after US4.

### Task-level dependencies

1. **T002 before T006 and T010.** The applier and injection both need the document model.
2. **T003 before T010.** Injection needs active-skill resolution to know whether to prepend anything.
3. **T007 before T008.** The reflector loads its prompt from the file.
4. **T004 and T005 before T015.** The gate writes run state and asserts disjointness against the collected outcomes.
5. **T005, T006, T008, T015 before T018.** The orchestrator wires all four stages.
6. **T017 last of the test tasks** — it is the only one that spends money.

### Within each user story

TDD where it is cheap and meaningful: the injection test (T009) is written with the injection (T010) because SC-005's byte-identity guarantee is the regression guard for the whole feature. The applier and gate tests (T013, T014) are written before the gate implementation (T015), because the gate is the component whose correctness decides whether anything is learned.

---

## Parallel Opportunities

Tasks marked [P] touch different files and can run together.

```bash
# Phase 1-2 — four independent files:
Task: "T002 Create backend/app/skills/document.py"
Task: "T003 Create backend/app/skills/active.py"
Task: "T004 Create backend/app/models/skillopt.py"
Task: "T005 Create backend/scripts/skillopt/collect.py"

# Phase 5-6 — three independent test files:
Task: "T013 Tests for the applier in backend/tests/test_skillopt_apply.py"
Task: "T014 Tests for the gate in backend/tests/test_skillopt_gate.py"
Task: "T016 Iteration tests in backend/tests/test_skillopt_iteration.py"
```

**Not parallel**: T001 → T002 (the loader validates the authored document); T006 → T015 (both handle the document and the protected region); T008 → T015 → T018 (each needs the previous).

---

## Implementation Strategy

### MVP first

1. **T001–T002** — the seed document and its loader.
2. **T003, T010, T009** — active resolution, injection, and the byte-identity guard.
3. **STOP and VALIDATE**: scenario 1 of [quickstart.md](quickstart.md). The skill reaches the request, and with no pointer the request is unchanged.
4. **This is genuinely valuable alone** — it is the only part of the feature that changes generation behaviour, and it does so without any model call.

### Incremental delivery

1. Setup + injection → the skill reaches generation; no pointer means no change.
2. Collect + reflect → failures become a bounded edit set.
3. Apply + gate → a candidate is accepted only on a strict held-out improvement.
4. Orchestrator → one command, one iteration, one record.
5. Polish → guardrails verified, SC-007 either run with a key or recorded as unverified.

---

## Notes

- **No task may change generation behaviour when no active skill is present.** SC-005 is the regression guard, and `runner.py` is the only generation-path file this feature touches.
- **No task may add a fixture** under `baseline_blueprints/`. Five is the contract.
- **No task may let a fallback-marked execution count as a pass**, at any exit code. The optimiser would exploit it.
- **No task may score the two skills on different held-out samples.** A comparison across samples is meaningless while still producing a number.
- **No task may modify the original skill file except on acceptance**, and then by exactly the applied edit set.
- **No task may write to the protected region.** It is honoured so that the deferred slow/meta update needs no change to the edit contract.
- **T017 is the only task that spends money.** Everything else runs against a scripted client.
- **The paper's prompt text is not reproduced.** The prompt file records what it was adapted from.
- Commit after each task or logical group. T001–T002 deserve their own commit so the seed document and its validation are trivially identifiable.
