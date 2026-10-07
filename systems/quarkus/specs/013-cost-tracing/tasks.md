# Tasks: Cost Tracing

**Input**: Design documents from `/specs/013-cost-tracing/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md), [constitution-recheck.md](constitution-recheck.md)

**Tests**: Included, in a consolidated phase after the report generator, per the explicit sequencing instruction for this feature. The one exception is T001, which writes the first end-to-end test **before** anything else so that every later task is checked against a recorded value rather than an absence.

**Organization**: Tasks are grouped by user story. US1 captures per-call telemetry, US2 aggregates per session, US3 produces the report a stakeholder reads.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Maps to a user story in [spec.md](spec.md) — US1 (P1), US2 (P2), US3 (P3)
- Every task names its exact file path

## Path Conventions

Repository root is the working directory. Backend paths are `backend/app/...`, tests are `backend/tests/...`, scripts are `backend/scripts/...`.

---

## ⚠️ Ordering Constraints (READ FIRST)

**1. T001 is first.** The fake client reports no token usage today, so every recording assertion written before it is extended would exercise only the unknown-usage path. SC-001 claims ten sessions produce records with **non-zero** token counts — without the extension that claim is untestable, and every downstream task reading a recorded token count is unverifiable. See [research.md](research.md) D12.

**T001 extends the fake; it does not reshape it.** Existing tests assert on `.content` and `.calls`. Usage metadata is additive and defaulted, and **no pre-existing assertion may be weakened** to accommodate it.

**2. The recording wrapper and the storage layer precede the report generator.** The report reads what they produce; there is nothing to report before they exist. T008–T012 come before T013.

**3. The report generator (T013) is the last substantive task before the test phase.**

---

## Phase 1: Setup

**Purpose**: Give the fake client token usage, and write the first end-to-end test so the rest of the feature is measured against real recorded values.

- [X] T001 Extend `backend/tests/fixtures/fake_model.py` so `FakeResponse` carries **additive, defaulted** usage metadata (input tokens, output tokens, and the cache-hit field), leaving `.content`, `.calls` and every existing assertion untouched. Then add the first test to `backend/tests/test_cost_recording.py`: it drives the **synchronous** invocation path through the stage boundary and asserts the call is recorded **end to end through the wrapper into the local store**, with non-zero token counts. **This test is expected to fail until T008–T012 land** — it is the red anchor for the whole feature, and it is the only test written before the implementation it exercises. Do not weaken any existing test to make the extension fit.

**Checkpoint**: the fake reports usage; the end-to-end test exists and is red for the right reason (nothing records yet).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The pricing table, configuration, and the three storage/pricing modules every story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T002 [P] Create `backend/app/resources/model_pricing.json` with the **expanded schema**: per `(provider, model)`, a `peak` and an `off_peak` block, each carrying `input_cache_hit`, `input_cache_miss` and `output` rates per 1M tokens. Include a mandatory `source` field set to the fetched pricing page, `retrieved_at`, and a `peak_window` object (01:00–04:00 and 06:00–10:00 UTC, Monday–Friday, with the excluded-holiday caveat). Seed `deepseek-flash` and `deepseek-v4-pro` from the published rates recorded in [research.md](research.md) D4. Rates MUST be fetched-and-cited, never recalled. Do NOT model the provider's holiday calendar ([contracts/cost-record.md](contracts/cost-record.md) §2.4).
- [X] T003 [P] Add `MLFLOW_TRACKING_URI` (default `http://localhost:5000`) and the local cost store path to `backend/app/config.py` as annotated `Settings` fields with defaults, mirroring the existing boolean/string flag pattern. The local store path MUST default to somewhere the report can read without configuration.
- [X] T004 [P] Create `backend/app/cost/__init__.py` exporting the package's public surface. Keep it a thin re-export module — no logic.
- [X] T005 Create `backend/app/cost/store.py`: the **durable local SQLite store that is the authoritative system of record** (FR-005). Define the model-call table and the session-cost table per [data-model.md](data-model.md) §1 and §3, with the validation rules enforced on write: `usage_known = False ⟹ token counts and cost are NULL, never 0`; `priced = False ⟹ cost is NULL`; and **no field may contain a credential**. Provide the write path used by the recorder and the read path used by the report. Idempotent per session so re-aggregation overwrites rather than double-counts.
- [X] T006 Create `backend/app/cost/pricing.py`: load `model_pricing.json` and expose the per-call price lookup. Enforce the load-time validations — a missing `source` is a load error, and `off_peak == peak / 2` for every field is asserted because the cited source states that relationship ([data-model.md](data-model.md) §2). Unknown `(provider, model)` MUST return an explicit **unpriced** result, never zero (FR-009). Implement the cache split exactly as [contracts/cost-record.md](contracts/cost-record.md) §2.2: `cache_miss_input = input_tokens − cache_hit_input_tokens`, defaulting the whole prompt to cache-miss when the response reports no cache breakdown, and returning which basis was applied for `pricing_basis`.
- [X] T007 [P] Create `backend/app/cost/mlflow_sink.py`: a **best-effort mirror** to the configured tracking destination (FR-005). Its absence MUST be a non-event — no exception surfaced, no retry storm, no effect on the session or the report. It MUST NOT be on the report's read path.

**Checkpoint**: pricing resolves for a real model and returns *unpriced* for an unknown one; the store persists a hand-written row and reads it back; the mirror fails silently when the destination is unreachable.

---

## Phase 3: User Story 1 — Every model call is recorded with its tokens and latency (Priority: P1) 🎯 MVP

**Goal**: A recording wrapper around the model client captures every invocation, including correction attempts, with the stage and session that produced it — and records nothing when recording is not active.

**Independent Test**: Run a session that makes several model calls, then read the recorded call data back. Assert one record per call, each carrying session, stage, provider, model, both token counts and a latency.

### Implementation for User Story 1

- [X] T008 [US1] Create `backend/app/cost/recording.py` containing both halves of the recording seam:
  - the **recording context** — a `contextvars.ContextVar` carrying the stage name and session identifier, set by the stage boundary (T010). A context variable is required rather than a module global because the platform runs sessions concurrently, and rather than explicit parameters because that would change five model stage signatures and remain forgettable ([research.md](research.md) D2).
  - the **proxy** — wraps the client the factory returns, records on **every** invocation *before* returning, and delegates attribute access so the wrapped client's own attributes remain reachable.
  - **Partial-interface handling (FR-001, SC-010)**: probe the wrapped client at construction. If it implements the asynchronous entry point, delegate to it. If it does **not** — as the fake client does not — **delegate the asynchronous call to the client's synchronous entry point** and record it. Do not raise. Do not pass through unrecorded: a call that happens is a call that costs, and an unrecorded pass-through is a second, quieter form of the silent-spend problem this feature closes ([research.md](research.md) D11). Document the chosen behaviour in the module.
  - **Credential rule**: the proxy sits directly beside the API key; it MUST record provider and model identifiers only and never the key.
- [X] T009 [US1] Update `backend/app/services/llm_factory.py` to return the **wrapped** client **only while a recording context is active**, across every provider branch that returns a client. When no context is active the factory returns exactly what it returns today. The condition MUST be *"is recording active"*, **never** *"is this a test"*: a test-shaped bypass would leave production unprotected, whereas this one is true for every real session and false for direct factory calls ([research.md](research.md) D1, [plan.md](plan.md) post-design re-check).
- [X] T010 [US1] Update `backend/app/orchestrator/stages/runner.py` to establish the recording context around the client-construction call (`implementation.build_client(state, api_key)`), carrying the current stage name and session identifier, and to clear it afterwards. Every production construction happens inside this boundary, which is what makes the wrapper unbypassable in production while leaving direct factory calls untouched.

**Checkpoint**: US1 works standalone. A call made through the stage boundary is recorded; a call made by calling the factory directly is not, and behaves exactly as before.

---

## Phase 4: User Story 2 — Each session aggregates to a cost and a status (Priority: P2)

**Goal**: A per-session record with summed tokens, cost from the pricing table, duration, call count, and the session's outcome — including whether its verification was real.

**Independent Test**: Complete a session with a known number of calls, then read its per-session record and check the totals equal the sum of its calls, the cost matches the table applied to those tokens, and the outcome fields match the session.

### Implementation for User Story 2

- [X] T011 [US2] Create `backend/app/cost/aggregate.py`: roll a session's call rows into one session cost record per [data-model.md](data-model.md) §3 and [contracts/cost-record.md](contracts/cost-record.md) §3. Sums MUST include only known values; unknown-usage calls contribute to no total and increment `usage_unknown_calls` instead of contributing a zero. `total_cost_usd` is `NULL` when no call had a known cost, never `0`. Carry `verification_fallback_used` from the session's persisted verification metrics (feature 012) so FR-007's exclusion is a property of the record. A session with zero call rows is recorded as a **deterministic** session, not a zero-cost model session. Aggregation is idempotent.
- [X] T012 [US2] Add a `cost_record_json` `Text` column to `GenerationSessionDB` in `backend/app/models/session.py`, registered through the existing idempotent `_ensure_generation_columns()` helper (`PRAGMA table_info` then `ALTER TABLE ... ADD COLUMN` when absent). Purely additive, reusing the mechanism feature 011 introduced and feature 012 reused — no new migration tool, no existing column repurposed.

**Checkpoint**: US1 and US2 both work independently. A session's totals reconcile against its call rows, and a fallback-marked session carries that fact on its cost record.

---

## Phase 5: User Story 3 — The cost report is durable and reproducible (Priority: P3)

**Goal**: One command prints the counts, the headline average cost per completed session, the overall average, p50/p90/max, and the per-stage breakdown — deterministically, from the local store, with its population stated.

**Independent Test**: Run the report twice against the same persisted data and diff the output. Then run it against data containing a fallback-marked session and confirm that session is excluded from (or separated from) the completed-session average.

### Implementation for User Story 3

- [X] T013 [US3] Create `backend/scripts/report_session_costs.py` — **the last substantive task before the test phase**. It MUST print every line required by [contracts/cost-report.md](contracts/cost-report.md) §1, and MUST satisfy:
  - **the exclusion rule (§3)**: the headline "average cost per completed session" is computed over `terminal_status == "COMPLETED" and model_mode == "MODEL" and verification_fallback_used == False and total_cost_usd is not NULL`. Every clause is load-bearing and the reasoning is in the contract — in particular a fallback-marked session (FR-007) cannot be priced as a successful generation, and an offline session must not drag the average toward zero.
  - **the population statement (§2)**: sessions, calls, unknown-usage calls, and unpriced calls. A figure without its denominator is not defensible (FR-008).
  - **the pricing basis statement**: the basis applied, the peak window, and the cache-miss-assumed count (FR-003a).
  - **determinism (§4, FR-006)**: reads the local store **only**, makes no live call, requires no tracking destination, orders rows by session identifier before aggregation and percentile selection, prints currency at fixed precision with fixed rounding, and uses **nearest-rank** percentiles with the method stated in the output.
  - **the empty/degenerate cases (§5)**: no data at all, and no eligible population, MUST each be stated in words. The report MUST NOT print zeroes that read as a real measurement of zero cost.
  - **never zero for unknown (FR-009)**: an unpriced model or an unknown usage is reported as unknown, never as `0`.

**Checkpoint**: the report runs with no tracking destination, prints the headline figure with its population, and excludes fallback-marked sessions visibly.

---

## Phase 6: Tests

**Purpose**: The contract tests for the three stories, plus the two guardrail tests that keep the seam honest.

- [X] T014 [P] Create `backend/tests/test_cost_recording.py` with the per-call recording tests: one record per invocation including a correction attempt; every required field present; a response with no usage produces a record marked `usage_known = False` rather than a dropped or zero-valued record; a deterministic session produces **no** call records; a call records no credential. **The test written in T001 must go green here** — it is the same file. **This file MUST include at least one case that records a call made through the stage boundary** (not through a hand-built context): without it, deleting T010's context wiring would leave the whole suite green while production recorded nothing.
- [X] T015 Add to `backend/tests/test_cost_recording.py` the **async-on-sync-only-client test (SC-010)**: wrap the fake client, which implements only the synchronous entry point, and invoke it through the wrapper's **asynchronous** path. Assert **both** that it does not raise **and** that the documented behaviour actually occurred — that the call was delegated to the synchronous implementation **and recorded** with the same fields as a synchronous call. Asserting only "does not raise" would let the recording silently disappear later. (Same file as T014, therefore not `[P]`.)
- [X] T016 [P] Create `backend/tests/test_cost_pricing.py` with the pricing tests: two otherwise identical calls inside and outside the peak window priced in the published ratio (SC-007); a cache-hit call priced at the cache-hit rate rather than the miss rate; the seeded table's `off_peak` exactly half its `peak` and its `source` present; an unknown model returns **unpriced** and never zero (SC-005); a response with no cache breakdown priced as cache-miss and counted; a missing `source` fails to load.
- [X] T017 [P] Create `backend/tests/test_cost_report.py` with the aggregation and report tests: totals equal the sum over the session's calls; re-aggregation overwrites rather than double-counts; the report prints every required line including the population statement; two runs over unchanged data are byte-identical (SC-003); a fallback-marked session is excluded from the headline figure with the exclusion count visible (SC-004); a session with no eligible population states that in words rather than printing `0.00`; an unpriced or unknown-usage session is reported as unknown, never as free.
- [X] T018 [P] Create `backend/tests/test_cost_seam.py` with the seam guardrail tests (SC-009): the recording wrapper is **inert** for the fake path; the seven `isinstance(model, ChatOpenAI/Groq/GoogleGenerativeAI)` assertions in `backend/tests/test_llm_factory.py` still hold by running that module unmodified; and a client constructed with no recording context is returned unwrapped. These tests must assert behaviour, not inspect the wrapper's type.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Whole-suite validation, the durable-store claim under a dead destination, and the opt-in real-session criterion.

- [X] T019 Run the full suite (`.venv/bin/python -m pytest -q`) and verify the untouched-file guardrails: `backend/app/orchestrator/graph.py`, the five deterministic emitters, the five model stages, both validator families, and the pre-existing test files named as out of bounds for this feature are byte-identical. Confirm `backend/tests/fixtures/fake_model.py` changed **additively only** — no pre-existing assertion weakened.
- [X] T020 [P] Validate `specs/013-cost-tracing/quickstart.md` scenarios 1–6 and 8 by running their commands, and record the observed output in `specs/013-cost-tracing/quickstart.md`. Scenario 6 in particular MUST be run with `MLFLOW_TRACKING_URI` pointed at an unreachable port, demonstrating byte-identical re-runs and no lost records (SC-003, SC-006).
- [X] T021 Add the opt-in ten-real-session test to `backend/tests/test_cost_recording.py`, gated behind `AGENTIA_RUN_REAL_COST_TRACING` so the default suite makes no provider call (Constitution Principle VI). Twelve sessions' worth of assertions per SC-001: non-zero token counts, no unpriced calls, a real `pricing_basis` on every call. **If the key is absent it skips, and SC-001's literal form is reported as *not verified by me*** — never inferred from the fake path, which is exactly the substitution feature 012 refused.
- [X] T022 Reconcile the design artifacts with what was built: update `specs/013-cost-tracing/plan.md`, `specs/013-cost-tracing/research.md`, `specs/013-cost-tracing/constitution-recheck.md`, and `specs/013-cost-tracing/quickstart.md` with the actual outcomes (including the SC-001 result from T021), and mark every task in `specs/013-cost-tracing/tasks.md` complete.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies. **T001 gates everything.**
- **Foundational (Phase 2)**: depends on T001 (the pricing schema and store schema are shaped by what the fake can report).
- **User Stories (Phases 3–5)**: depend on Phase 2. US1 → US2 → US3 in priority order; US2 sums what US1 records, US3 reports what US2 aggregates.
- **Tests (Phase 6)**: after T013, per the explicit sequencing instruction for this feature.
- **Polish (Phase 7)**: after the tests.

### Task-level dependencies

1. **T001 before everything.** Without a usage-reporting fake, no recording assertion is meaningful.
2. **T002 and T006 together.** The pricing module validates the table it loads; neither is useful alone.
3. **T005 before T008.** The proxy writes to the store; the store's write path must exist.
4. **T008 before T009.** The factory can only return a wrapped client once the wrapper exists.
5. **T009 and T010 are a pair.** Either alone is broken: the wrapper never applies (T009 without T010) or the context is never set (T010 without T008/T009). **T014's through-the-seam case is what fails if either is dropped.**
6. **T011 after T005.** Aggregation reads the call rows.
7. **T012 after T011** — the column stores T011's record.
8. **T013 last of the implementation tasks.** It reads what T005 and T011 wrote.
9. **T014–T018 after T013**, per the sequencing instruction.
10. **T021 last of the test tasks** — it is the only one that spends money.

### Within each user story

TDD is preserved where it matters: T001 writes the feature's first end-to-end test before any implementation, so every later task is checked against a recorded value. The remaining tests are consolidated after T013 by explicit instruction.

---

## Parallel Opportunities

Tasks marked [P] touch different files and can run together.

```bash
# Phase 2 — four independent files:
Task: "T002 Create backend/app/resources/model_pricing.json"
Task: "T003 Add cost settings to backend/app/config.py"
Task: "T004 Create backend/app/cost/__init__.py"
Task: "T007 Create backend/app/cost/mlflow_sink.py"

# Phase 6 — four independent test files:
Task: "T014 Per-call recording tests in backend/tests/test_cost_recording.py"
Task: "T016 Pricing tests in backend/tests/test_cost_pricing.py"
Task: "T017 Aggregation and report tests in backend/tests/test_cost_report.py"
Task: "T018 Seam guardrail tests in backend/tests/test_cost_seam.py"
```

**Not parallel**: T005 → T008 → T009 (each needs the previous), T014 and T015 (same file), T011 → T012 → T013.

---

## Implementation Strategy

### MVP first

1. **T001** — the usage-reporting fake and the red end-to-end test. Non-negotiable first step.
2. **Phase 2** — pricing, store, mirror.
3. **Phase 3 (US1)** — context, proxy, wrapping, seam wiring.
4. **STOP and VALIDATE**: T001's test goes green. One call through the stage boundary produces one priced record with non-zero tokens.
5. **Do not deploy yet.** US1 alone records calls but reports nothing.

### Incremental delivery

1. T001 + Phase 2 → the fake reports usage; pricing and the store exist; nothing recorded yet.
2. US1 → calls are recorded and priced. Real telemetry exists for the first time.
3. US2 → sessions aggregate to a cost and an outcome.
4. US3 → the headline figure is printable and defensible.
5. Tests + Polish → the seam is proven intact, the figures are proven reproducible, and SC-001's literal form is either verified with a key or explicitly recorded as unverified.

---

## Notes

- **No task may add anything to the generated microservice's dependency surface** (Principle VI). The wrapper is orchestration-side only.
- **No task may record a credential.** The proxy sits beside the API key, which is where leaking it is easiest (feature 011's FR-018 credential rule, Principle VI).
- **No task may make the report depend on the tracking destination.** The local store is authoritative; the destination is a mirror whose absence is a non-event (FR-005).
- **No task may price an unknown model at zero or assume a cache hit.** Unknown is reported as unknown and counted (FR-009, [contracts/cost-record.md](contracts/cost-record.md) §2.2).
- **The fake is extended, never reshaped.** A task that wants to relax a pre-existing assertion is a signal the extension was done wrong.
- **T021 is the only task that spends money.** Everything else runs offline against the fake.
- `reports/measurements/` and `reports/baselines/` are untouched by this feature — cost is a separate artifact with a separate audience.
- Commit after each task or logical group. T001 deserves its own commit so the fake extension and the red anchor are trivially identifiable.

---

## Answering the seam-risk question

Two tasks could, if written carelessly, let the proxy be bypassed or the fake path break **without a failing test**. Both are called out above so the risk is closed by construction rather than noticed later:

1. **T014 must record a call made through the stage boundary**, not only through a hand-built context. Without that one case, deleting T010's context wiring leaves the suite green while production records nothing — the proxy would be bypassed silently.
2. **T015 must assert that the async call is recorded**, not merely that it does not raise. Without it, T008's delegation could be replaced by a silent pass-through and no test would notice.

A third risk is closed by T009's wording: the wrapping condition must key on *"is recording active"*, never on *"is this a test"*. A test-shaped condition would satisfy T018 (the fake stays unwrapped) yet leave every production call unrecorded — and T014's through-the-seam case is what makes that visible.
