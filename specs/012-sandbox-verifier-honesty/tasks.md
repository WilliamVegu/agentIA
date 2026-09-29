# Tasks: Sandbox Verifier Honesty

**Input**: Design documents from `/specs/012-sandbox-verifier-honesty/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md), [constitution-recheck.md](constitution-recheck.md)

**Tests**: Included. The plan names `backend/tests/test_sandbox_verifier_honesty.py` and [quickstart.md](quickstart.md) defines the validation scenarios each task must satisfy.

**Organization**: Tasks are grouped by user story. US1 delivers the honest default, US2 the opt-in escape hatch, US3 the observability surfaces.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Maps to a user story in [spec.md](spec.md) — US1 (P1), US2 (P2), US3 (P3)
- Every task names its exact file path

## Path Conventions

Repository root is the working directory. Backend paths are `backend/app/...` and tests are `backend/tests/...`.

---

## ⚠️ Ordering Constraint (READ FIRST)

**T001 MUST be completed before any other task.**

`backend/tests/test_docker_runner.py` contains three pre-existing tests that assert the bug as required behavior — they demand `exit_code == 0` and `"BUILD SUCCESS"` under exactly the conditions FR-001 says must now fail. They cannot pass unchanged once the honest default lands.

Re-pointing them **first** means an implementer who later sees red knows the failure is in the *new* behavior, not in a test that still encodes the old contract. If they are left until last, the natural (and wrong) response to a red suite is to relax FR-001. See [research.md](research.md) D9.

---

## Phase 1: Setup

**Purpose**: Make permissive mode expressible and stop the pre-existing tests from asserting behavior FR-001 forbids.

- [X] T001 Add `ALLOW_HERMETIC_FALLBACK: bool = False` to `Settings` in `backend/app/config.py` (mirroring the existing `ALLOW_OFFLINE_MOCK` pattern), then re-point the three synthetic-success tests in `backend/tests/test_docker_runner.py` (`test_run_docker_sandbox_daemon_offline_fallback`, `test_run_docker_sandbox_daemon_pipe_error_fallback`, `test_run_docker_sandbox_image_missing_fallback`) to enable permissive mode explicitly via `monkeypatch.setattr(settings, "ALLOW_HERMETIC_FALLBACK", True)`, so the synthetic-success assertions survive only under the flag. Do not delete or weaken the three tests; do not assert synthetic success under the default configuration.

**Checkpoint**: the pre-existing suite passes again, and no test asserts synthetic success without opting in.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The data carriers every user story reads and writes. No story can be completed without these.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 Add four fields to `DockerExecutionResult` in `backend/app/sandbox/docker_runner.py`: `fallback_used: bool = False`, `fallback_reason: Optional[str] = None`, `matched_pattern: Optional[str] = None`, `attribution_ambiguous: bool = False`. All defaulted so existing constructions stay valid. Per [contracts/verification-result.md](contracts/verification-result.md) §1.
- [X] T003 [P] Add `fallback_used: bool = False` and `fallback_reason: Optional[str] = None` to `VerificationMetrics` in `backend/app/models/artifact.py`. Defaulted, so every existing `VerificationMetrics(...)` call site remains valid.
- [X] T004 [P] Add an optional `verification_fallback_used: bool` field (alias `verificationFallbackUsed`, default `False`) to `GenerationAgentState` in `backend/app/orchestrator/state.py`.
- [X] T005 Add a `verification_metrics_json` `Text` column to `GenerationSessionDB` in `backend/app/models/session.py`, registered through the existing idempotent `_ensure_generation_columns()` helper (`PRAGMA table_info` check → `ALTER TABLE ... ADD COLUMN` when absent). Purely additive; no new migration tool. Reuse of this mechanism is required, per [research.md](research.md) D7.
- [X] T006 Add `verification_fallback_used: bool = False` (alias `verificationFallbackUsed`) to `GenerationSessionDetail` in `backend/app/models/session.py`. Sequential with T005 — same file.

**Checkpoint**: the flag can be carried from the verifier to the database and the API. Test suite still green.

---

## Phase 3: User Story 1 — An unverified workspace is never reported as verified (Priority: P1) 🎯 MVP

**Goal**: When verification cannot be performed, say so. Default mode reports a non-success outcome, marks it, records why, and terminates the session in the human-intervention state without entering the repair loop.

**Independent Test**: With no reachable runtime and default configuration, run a session to the sandbox step. Assert a non-zero outcome with the marking set, a recorded reason, no synthetic `BUILD SUCCESS` in the output, and a `BLOCKED` terminal state that never visited the repair node.

### Tests for User Story 1

- [X] T007 [P] [US1] Create `backend/tests/test_sandbox_verifier_honesty.py` with the honest-default suite: for **each of the four** substitution triggers (daemon unreachable, runtime executable absent, runtime communication failure, environment-looking build failure), assert `exit_code != 0`, `fallback_used is True`, a non-empty `fallback_reason`, and that the synthetic `BUILD SUCCESS` text is absent from stdout/stderr. Per [contracts/verification-result.md](contracts/verification-result.md) §2–§4.
- [X] T008 [P] [US1] Add to `backend/tests/test_sandbox_verifier_honesty.py` the terminal-state test: a resolved-via-fallback sandbox step returns `BLOCKED` with phase `FAILED`, writes the reason to the **`error`** state key, and the repair node is **not** visited. Assert the recorded reason states verification could not be performed and does not read as a test or compilation failure.
- [X] T009 [P] [US1] Add to `backend/tests/test_sandbox_verifier_honesty.py` the ambiguity test for trigger 4: assert `attribution_ambiguous is True`, `matched_pattern` names the pattern that matched, and — per [research.md](research.md) Q2 resolution — that the recognised pattern set was **not** narrowed.

### Implementation for User Story 1

- [X] T010 [US1] Replace `_build_hermetic_fallback_result` in `backend/app/sandbox/docker_runner.py` with a single policy function behind **all four** substitution call sites. Default mode (`ALLOW_HERMETIC_FALLBACK` false): `exit_code = 1`, no synthetic stdout, `fallback_used = True`, `fallback_reason` set. Permissive mode: legacy `exit_code = 0` plus the synthetic stdout, still `fallback_used = True`. Per [contracts/verification-result.md](contracts/verification-result.md) §3.
- [X] T011 [US1] In `backend/app/sandbox/docker_runner.py`, set `matched_pattern` and `attribution_ambiguous = True` only on the environment-pattern branch (trigger 4), retaining the existing pattern list verbatim. The three unambiguous triggers leave both unset.
- [X] T012 [US1] Update `backend/app/orchestrator/nodes/sandbox_node.py`: copy `result.fallback_used` into `VerificationMetrics`; when `fallback_used` is true **and** permissive mode is disabled, return `status = SessionStatus.BLOCKED.value`, `current_phase = SessionPhase.FAILED.value`, `build_success = False`, and the reason on the **`error`** key. Do not enter the repair path. **Do not modify `backend/app/orchestrator/graph.py`** — `_route_after_sandbox` already returns `END` on `BLOCKED` ([research.md](research.md) D4).

**Checkpoint**: US1 fully functional and independently testable. A workspace that cannot be verified is never reported as verified.

---

## Phase 4: User Story 2 — Local development can opt into permissive verification (Priority: P2)

**Goal**: An explicit opt-in restores the pre-change behavior so offline development can run end to end, while the fallback marking is still recorded.

**Independent Test**: With no reachable runtime and `ALLOW_HERMETIC_FALLBACK=true`, run the same session as US1. Assert the outcome matches the pre-change behavior **and** that `fallback_used` is still `True` with the reason recorded.

### Tests for User Story 2

- [ ] T013 [P] [US2] Add to `backend/tests/test_sandbox_verifier_honesty.py` the permissive-mode suite (SC-002): legacy outcome restored, and `fallback_used is True` with `fallback_reason` set on every substituted result — the FR-007 audit-blind-spot check.
- [ ] T014 [P] [US2] Add to `backend/tests/test_sandbox_verifier_honesty.py` the mode-detection tests: flag absent → honest default; flag explicitly `False` → honest default; flag set to an unrecognized value → treated as disabled (fails safe).

### Implementation for User Story 2

- [ ] T015 [US2] Confirm and, if necessary, complete the permissive branch in the policy function in `backend/app/sandbox/docker_runner.py` so that permissive mode permits a session to reach the verified state (FR-002 relaxing FR-003, per the Q1 resolution) **and** still records the marking on every result and on the metrics.

**Checkpoint**: US1 and US2 both work independently. Permissive mode is opt-in, never inferred, and never silent.

---

## Phase 5: User Story 3 — Verification source is visible to every consumer (Priority: P3)

**Goal**: The marking reaches the metrics payload, the session detail endpoint, and the live event stream.

**Independent Test**: Complete a session under fallback conditions and confirm the marking appears in all three surfaces, and that the detail endpoint still reports it after a process restart.

### Tests for User Story 3

- [ ] T016 [P] [US3] Add to `backend/tests/test_sandbox_verifier_honesty.py` the metrics-payload test: `fallback_used` mirrors the verification result, and `allPassed=True` with `fallback_used=True` is reachable only in permissive mode.
- [ ] T017 [P] [US3] Add to `backend/tests/test_sandbox_verifier_honesty.py` the session-detail tests (SC-005): `verificationFallbackUsed` is present and true for a substituted session, is readable through a **fresh database session** (proving it survived a restart), and degrades to `False` without raising when persisted metrics are absent or unparseable.
- [ ] T018 [P] [US3] Add to `backend/tests/test_sandbox_verifier_honesty.py` the live-stream test: the marking is observable **before** the session reaches a terminal state, and is a structured field rather than only a free-text log line.

### Implementation for User Story 3

- [ ] T019 [US3] Persist the serialized `VerificationMetrics` into `verification_metrics_json` in `backend/app/api/routes_session.py` (or the node that owns the session row) so the detail endpoint can read it after a restart.
- [ ] T020 [US3] Expose `verification_fallback_used` on `GET /api/v1/sessions/{session_id}` in `backend/app/api/routes_session.py`, reading the persisted metrics and degrading to `False` without raising when they are absent or unparseable. Additive and optional, so no existing client breaks.
- [ ] T021 [US3] Include the structured marking for the verification step in the session event stream in `backend/app/api/routes_session.py`, so a watcher learns the verification was synthetic even when the session proceeds to `VERIFIED` under permissive mode.

**Checkpoint**: all three user stories functional and independently verifiable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Measurement integrity, the real-build verification, and the guardrail checks.

- [ ] T022 [P] Implement FR-008 in `backend/tests/test_generation_stage_measurement.py`: exclude every fallback-marked result from published figures **regardless of terminal state** (permissive-mode sessions can reach `VERIFIED`, so the status must not be the discriminator), and record the excluded count in the generated report.
- [ ] T023 Regenerate `reports/measurements/011-sc011-intervention-rate.md` and `reports/measurements/011-us1-baseline-comparison.md` so the committed artifacts reflect the filtered population and the recorded exclusion count.
- [ ] T024 Add the SC-003 real-build case to `backend/tests/test_sandbox_verifier_honesty.py` and verify it with a **real** offline build from a shell that can reach the container runtime: run the passing-test and failing-test cases end to end and assert `fallback_used is False` and the genuine Maven output. If the executing shell cannot reach the runtime (see [constitution-recheck.md](constitution-recheck.md) §3 and [quickstart.md](quickstart.md) Scenario 3), report SC-003 as **not verified by me** and have it verified from a capable shell — never infer it from a second-hand report.
- [ ] T025 Run the full suite and verify the guardrails: `graph.py` unchanged, `backend/app/orchestrator/nodes/repair_node.py` unchanged, the offline generation path unmodified, and no test asserts synthetic success under the default configuration.
- [ ] T026 Update `specs/012-sandbox-verifier-honesty/plan.md`, `specs/012-sandbox-verifier-honesty/research.md` (D10), `specs/012-sandbox-verifier-honesty/constitution-recheck.md` §3, and `specs/012-sandbox-verifier-honesty/quickstart.md` with the actual SC-003 outcome, replacing the "testable" statement with what was observed.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies. **T001 gates everything** — see the ordering constraint above.
- **Foundational (Phase 2)**: depends on T001. Blocks all user stories.
- **User Stories (Phases 3–5)**: depend on Phase 2. US1 → US2 → US3 in priority order.
- **Polish (Phase 6)**: depends on US1 (the honest outcome must exist before figures can be filtered on it) and US3 (the marking must be persisted before figures can read it).

### Task-level dependencies

1. **T001 before T010.** Re-pointing the tests first is the whole point of the ordering constraint.
2. **T002 before T010/T011/T012.** The result fields must exist before the policy can populate them.
3. **T003 before T012.** Metrics cannot carry the flag before the field exists.
4. **T005 before T019/T020.** Persistence precedes exposure.
5. **T006 after T005** (same file — `backend/app/models/session.py`).
6. **T012 before T013–T015.** Permissive mode is meaningful only once the honest default exists.
7. **T019 before T020/T021.** Both surfaces read what persistence wrote.
8. **T022 after T019.** FR-008 reads the persisted marking.
9. **T024 last of the verification tasks** — it needs the complete honest path.

### Within each user story

Tests may be written before or alongside implementation, but the **T007–T009 assertions must be red before T010–T012 land**, otherwise they are not proving the fix. T024 is the only task that requires a real container runtime.

---

## Parallel Opportunities

Tasks marked [P] touch different files and can run together.

```bash
# Phase 2 — independent carriers:
Task: "T003 Add fallback fields to VerificationMetrics in backend/app/models/artifact.py"
Task: "T004 Add verification_fallback_used to GenerationAgentState in backend/app/orchestrator/state.py"

# Phase 3 — all three test tasks touch one new file each, written before implementation:
Task: "T007 Honest-default suite for all four triggers"
Task: "T008 Terminal-state and repair-bypass test"
Task: "T009 Ambiguity recording test for trigger 4"

# Phase 5 — three independent observability tests:
Task: "T016 Metrics-payload test"
Task: "T017 Session-detail persistence and degradation tests"
Task: "T018 Live-stream structured-field test"
```

**Not parallel**: T005 and T006 (same file), T010 and T011 (same function region), T019–T021 (same module, sequential edits).

---

## Implementation Strategy

### MVP first

1. **T001** — re-point the bug-asserting tests. Non-negotiable first step.
2. **Phase 2** — the four data carriers.
3. **Phase 3 (US1)** — the honest default.
4. **STOP and VALIDATE**: run [quickstart.md](quickstart.md) Scenario 1. An unverifiable workspace must never report verified.
5. **Do not deploy yet.** US1 alone blocks every session on a host without a container runtime, which is correct but not yet operable.

### Incremental delivery

1. T001 + Phase 2 → suite green, no behavior change.
2. US1 → the platform stops lying. Sessions without a runtime block instead of falsely verifying.
3. US2 → offline development works again, audibly.
4. US3 → the marking is observable and survives a restart.
5. Phase 6 → figures are computed over verified sessions only, and SC-003 is confirmed against a real build.

---

## Notes

- **No task may modify `backend/app/orchestrator/graph.py`.** T012 relies on the existing `_route_after_sandbox` `BLOCKED` branch. If a task appears to need a graph change, the design has been misread — re-read [research.md](research.md) D4.
- **No task may narrow the environment-pattern list.** Q2 chose to record the ambiguity rather than resolve it.
- **The hardcoded 5/5 test counts are out of scope.** They remain reachable only through a *permitted* substitution, which is the improvement; correcting them is a separate change.
- **`backend/app/orchestrator/nodes/repair_node.py` must stay unchanged.** T008 asserts the repair loop is not entered, not that it behaves differently.
- **The reason goes in the `error` state key, not `error_message`.** `routes_session` persists `final_state.get("error")` into the `error_message` column; using the column's name as the key silently discards the reason ([research.md](research.md) D5).
- **T024 is the only task needing a real container runtime.** Everything else runs with the daemon absent or faked, satisfying Constitution Principle VI.
- Commit after each task or logical group. T001 deserves its own commit so the test re-pointing is trivially identifiable.
