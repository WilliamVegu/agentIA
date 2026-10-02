# Tasks: Historical Baseline Analysis for AgentIA Skill Injection Pilot

**Input**: Design documents from `specs/009-historical-baseline-analysis/` (`spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`)

**Prerequisites**: `plan.md` (required), `spec.md` (required for user stories), `research.md`, `data-model.md`, `contracts/`

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `- [ ] [ID] [P?] [Story] Description with file path`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (`[US1]`, `[US2]`, `[US3]`)
- Exact file paths included in every description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, directory structure, and shared test fixtures

- [X] T001 Create backend script directory `backend/scripts/` and output directory `reports/`
- [X] T002 [P] Create mock database builder and schema helper in `backend/tests/fixtures/baseline_fixture_db.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core read-only database connectivity and metric data structures required by all user stories

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T003 Implement strict read-only SQLite connector with `file:{path}?mode=ro` and `PRAGMA query_only = ON;` in `backend/scripts/analyze_historical_baseline.py`
- [X] T004 [P] Implement core metric dataclasses (`RawSessionRecord`, `SessionOutcomeMetrics`, `RepairLoopMetrics`, `CandidateDomainEvaluation`) in `backend/scripts/analyze_historical_baseline.py`
- [X] T005 Create baseline test suite scaffold with temporary SQLite database fixtures in `backend/tests/test_historical_baseline.py`

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Historical Failure Distribution & Repair Loop Analysis (Priority: P1) 🎯 MVP

**Goal**: Query historical generation sessions, compute terminal outcome distribution (Verified vs Blocked vs Failed), analyze repair loop attempt distributions (0..3), and calculate loop exhaustion rate with exact counts and percentages.

**Independent Test**: Execute the script against a historical database containing session records and verify that outcome counts, repair attempt distributions, and loop exhaustion percentages match database rows exactly.

### Tests for User Story 1 ⚠️

- [X] T006 [P] [US1] Write unit tests for session outcome aggregation and repair attempt distribution calculation in `backend/tests/test_historical_baseline.py`
- [X] T007 [P] [US1] Write unit tests for compiler and Surefire log extraction regex in `backend/tests/test_historical_baseline.py`

### Implementation for User Story 1

- [X] T008 [US1] Implement session query and outcome distribution calculator (`calculate_outcome_metrics`) in `backend/scripts/analyze_historical_baseline.py`
- [X] T009 [US1] Implement repair loop metrics engine (`calculate_repair_metrics`) measuring attempt distribution (0, 1, 2, 3) and exhaustion rate in `backend/scripts/analyze_historical_baseline.py`
- [X] T010 [US1] Implement regex diagnostic extractor for Java compilation errors and Surefire assertion failures in `backend/scripts/analyze_historical_baseline.py`

**Checkpoint**: User Story 1 is fully functional and testable independently (MVP complete).

---

## Phase 4: User Story 2 - Data-Driven Candidate Domain Triage (Priority: P2)

**Goal**: Scan error traces against the 5 candidate domains (`jakarta_namespace`, `layer_architecture`, `exception_handling`, `maven_pom`, `mockito_tests`), evaluate constitutional validator findings, and assign objective triage verdicts (`skill-layer appropriate`, `deterministic-fixer appropriate`, `not observed`).

**Independent Test**: Run domain triage against synthetic session logs containing known domain failure signatures and verify each domain receives the expected classification and technical rationale.

### Tests for User Story 2 ⚠️

- [X] T011 [P] [US2] Write unit tests for candidate domain keyword/regex classification in `backend/tests/test_historical_baseline.py`
- [X] T012 [P] [US2] Write unit tests verifying triage classification rules and scorecard formatting in `backend/tests/test_historical_baseline.py`

### Implementation for User Story 2

- [X] T013 [US2] Implement candidate domain pattern matchers and incident counting for the 5 target domains in `backend/scripts/analyze_historical_baseline.py`
- [X] T014 [US2] Implement constitutional validator violation frequency aggregation (Principles I-VI) in `backend/scripts/analyze_historical_baseline.py`
- [X] T015 [US2] Implement domain triage evaluation engine (`evaluate_domains`) assigning verdicts and technical justifications in `backend/scripts/analyze_historical_baseline.py`

**Checkpoint**: User Stories 1 AND 2 are both fully functional and testable independently.

---

## Phase 5: User Story 3 - Standalone Read-Only Execution & Edge Case Resilience (Priority: P3)

**Goal**: Provide CLI argument parsing (`--db-path`, `--output`, `--json`, `--verbose`), environment variable fallbacks, strict error exit codes, empty database handling, and markdown report generation conforming to contracts.

**Independent Test**: Invoke the CLI with custom arguments, invalid paths, and empty databases; verify expected exit codes, JSON output mode, and markdown report formatting.

### Tests for User Story 3 ⚠️

- [X] T016 [P] [US3] Write unit tests verifying CLI arguments, environment variable overrides, and exit codes in `backend/tests/test_historical_baseline.py`
- [X] T017 [P] [US3] Write unit tests verifying empty database handling and read-only write protection (verifying `sqlite3.OperationalError` on write attempt) in `backend/tests/test_historical_baseline.py`

### Implementation for User Story 3

- [X] T018 [US3] Implement CLI argument parsing and environment variable resolution conforming to `specs/009-historical-baseline-analysis/contracts/cli-contract.md` in `backend/scripts/analyze_historical_baseline.py`
- [X] T019 [US3] Implement Markdown report generator conforming to `specs/009-historical-baseline-analysis/contracts/report-schema.md` writing to `reports/009-historical-baseline.md` in `backend/scripts/analyze_historical_baseline.py`
- [X] T020 [US3] Implement JSON output mode (`--json`) emitting structured telemetry to stdout in `backend/scripts/analyze_historical_baseline.py`

**Checkpoint**: All three user stories are functional and testable independently.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final test execution, documentation, and report generation

- [X] T021 [P] Add module docstrings, CLI usage examples, and type annotations in `backend/scripts/analyze_historical_baseline.py`
- [X] T022 Execute test suite via `pytest backend/tests/test_historical_baseline.py` to confirm 100% pass rate
- [X] T023 Execute `analyze_historical_baseline.py` end-to-end to generate the baseline distribution report at `reports/009-historical-baseline.md`
- [X] T024 Validate generated report against the quickstart checklist in `specs/009-historical-baseline-analysis/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories.
- **User Stories (Phases 3-5)**: All depend on Foundational phase completion.
  - Can proceed sequentially in priority order (`US1` ➔ `US2` ➔ `US3`) or in parallel.
- **Polish (Phase 6)**: Depends on all user story implementations being complete.

### User Story Dependencies

- **User Story 1 (P1)**: Depends on Phase 2. Core analytical engine for session distribution and repair logs.
- **User Story 2 (P2)**: Depends on Phase 2 and parses diagnostic events from US1 data structures.
- **User Story 3 (P3)**: Depends on Phase 2; wraps US1 and US2 into the CLI interface and Markdown report writer.

### Parallel Opportunities

- `T002` (test fixture builder) can run in parallel with `T001`.
- `T004` (dataclasses) can run in parallel with `T003` (read-only connector).
- Tests within each user story (`T006`/`T007`, `T011`/`T012`, `T016`/`T017`) can be developed in parallel with or prior to implementation.
- `T021` (docstrings) can run in parallel with final verification tasks.

---

## Parallel Example: User Story 1

```bash
# Launch test development in parallel:
Task T006: "Write unit tests for session outcome aggregation and repair attempt distribution"
Task T007: "Write unit tests for compiler and Surefire log extraction regex"

# Then implement calculators:
Task T008: "Implement session query and outcome distribution calculator"
Task T009: "Implement repair loop metrics engine"
Task T010: "Implement regex diagnostic extractor"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (`T001`, `T002`).
2. Complete Phase 2: Foundational (`T003` - `T005`).
3. Complete Phase 3: User Story 1 (`T006` - `T010`).
4. **STOP and VALIDATE**: Run tests for US1 to verify outcome aggregation and repair distributions on historical sessions.

### Incremental Delivery

1. Foundation ready (`T001` - `T005`).
2. Add User Story 1 (`T006` - `T010`) ➔ Test independently (MVP: outcomes + repair loops).
3. Add User Story 2 (`T011` - `T015`) ➔ Test independently (Domain triage + scorecard).
4. Add User Story 3 (`T016` - `T020`) ➔ Test independently (CLI + Markdown report export).
5. Polish & Verification (`T021` - `T024`) ➔ Full test run and generation of `reports/009-historical-baseline.md`.
