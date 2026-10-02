# Implementation Plan: Historical Baseline Analysis for AgentIA Skill Injection Pilot

**Branch**: `009-historical-baseline-analysis` | **Date**: 2026-09-25 | **Spec**: [specs/009-historical-baseline-analysis/spec.md](spec.md)

**Input**: Feature specification from `specs/009-historical-baseline-analysis/spec.md` ("Historical baseline analysis for AgentIA skill injection pilot: Produce a one-page distribution report analyzing existing historical session data from studio.db, and use it to inform which of five candidate failure domains survive into the skill injection pilot.")

---

## Summary

This feature delivers an empirical, data-driven historical baseline analysis utility to understand the real-world failure modes of AgentIA's Java 21 / Spring Boot 3 generation sessions in `studio.db`. The analysis evaluates five candidate failure domains (`jakarta_namespace`, `layer_architecture`, `exception_handling`, `maven_pom`, `mockito_tests`) to determine which survive into the upcoming Skill Injection Pilot versus which are better handled by deterministic AST/regex post-processors.

Key capabilities delivered:
1. **Standalone Read-Only Analyzer**: A lightweight Python 3 script (`backend/scripts/analyze_historical_baseline.py`) operating in strict read-only mode (`mode=ro`, `PRAGMA query_only=ON`) with zero external runtime dependencies.
2. **Comprehensive Metrics Engine**: Quantifies terminal outcomes (`VERIFIED` vs `BLOCKED` vs `FAILED`), repair loop attempt distributions (0..3), and exhaustion rates.
3. **Log & Diagnostic Classifier**: Parses raw compiler traces and Surefire assertion logs to categorize errors and detect domain failure signatures.
4. **Data-Driven Domain Triage Matrix**: Classifies all 5 candidate domains into `skill-layer appropriate`, `deterministic-fixer appropriate`, or `not observed`.
5. **Executive Markdown Report**: Generates `reports/009-historical-baseline.md` formatted for technical leads and executive stakeholders, ensuring dual representation (raw count + percentage) on every metric.

---

## Technical Context

**Language/Version**: Python 3.10+ (Standard Library: `sqlite3`, `re`, `argparse`, `json`, `pathlib`).

**Primary Dependencies**: Zero mandatory third-party runtime dependencies. Uses `pytest` for automated test suites in `backend/tests/`.

**Storage**: SQLite 3 database (`studio.db` / `generation_sessions` table), accessed strictly via read-only URI connections (`file:{path}?mode=ro`).

**Testing**: `pytest` (`backend/tests/test_historical_baseline.py`) with synthetic SQLite fixtures verifying read-only enforcement, error parsing, triage scoring, and report generation.

**Target Platform**: Cross-platform (Linux, macOS, Windows).

**Project Type**: Standalone CLI script + Automated Report Generator.

**Performance Goals**:
- Execution runtime: < 1.0 second for up to 1,000 historical session records.
- Memory consumption: < 30 MB peak RAM.

**Constraints**:
- Read-only database access; zero schema changes or row mutations.
- Zero code modifications to AgentIA core generation runtime.
- 100% offline determinism (no external network or LLM API calls).
- Output report path defaults to `reports/009-historical-baseline.md`.
- All reported metrics must include both raw counts and percentages.

---

## Constitution Check

*GATE: Verified against `.specify/memory/constitution.md`.*

| Principle | Relevance & Impact on Feature | Status |
|---|---|---|
| **I. Layer Isolation** | Script analyzes Java 21 microservice layer isolation violations (Controller -> Service -> Repository) to triage the `layer_architecture` domain. | **PASS** |
| **II. Immutable DTOs & Validation** | Script analyzes historical validation failures and Jakarta namespace migration issues (`jakarta_namespace`). | **PASS** |
| **III. Centralized Exception Handling** | Script evaluates historical `@RestControllerAdvice` compliance to triage the `exception_handling` domain. | **PASS** |
| **IV. Offline Determinism & Sandbox** | Standalone script runs 100% offline with zero network calls, external API dependencies, or package downloads. | **PASS** |
| **V. Quality Gates & 3-Repair Cap** | Script quantifies compliance with the 3-attempt auto-repair boundary and measures loop exhaustion frequency. | **PASS** |
| **VI. Zero Secrets & Orchestrator Boundaries** | Zero credentials or API keys used; operates completely outside LLM orchestrator boundaries as an offline analytical tool. | **PASS** |

*Gate Verdict: ALL CONSTITUTIONAL PRINCIPLES SATISFIED. ZERO VIOLATIONS.*

---

## Project Structure

### Documentation (this feature)

```text
specs/009-historical-baseline-analysis/
├── spec.md                     # Feature specification
├── plan.md                     # This implementation plan
├── research.md                 # Technical decisions & triage rubric
├── data-model.md               # Analytical data models & domain taxonomy
├── quickstart.md               # Verification & test execution guide
├── checklists/
│   └── requirements.md         # Validated requirements quality checklist
└── contracts/
    ├── cli-contract.md         # CLI flags, options, exit codes, and output modes
    └── report-schema.md        # Layout and section schema for the output report
```

### Source Code (repository root)

```text
backend/
├── scripts/
│   └── analyze_historical_baseline.py     # Standalone CLI analysis script & report generator
└── tests/
    └── test_historical_baseline.py        # Pytest test suite with synthetic SQLite fixtures

reports/
└── 009-historical-baseline.md             # Generated baseline analysis & domain triage report
```

**Structure Decision**: The analytical script is housed in `backend/scripts/` to keep it close to backend models and services while remaining executable as a standalone utility. The test suite is placed in `backend/tests/` to integrate with existing project testing practices. The generated output report is saved to `reports/` at the repository root.

---

## Complexity Tracking

> **Constitution check confirmed zero violations. No unjustified complexity introduced.**

| Violation | Why Needed | Simpler Alternative Rejected Because |
| :---: | :---: | :---: |
| None | N/A | N/A |

---

## Phases & Deliverables

### Phase 0: Outline & Research *(Complete)*
- [x] Extracted technical requirements and constraints.
- [x] Defined strict read-only SQLite access mechanics (`mode=ro`, `PRAGMA query_only = ON;`).
- [x] Established objective 3-tier domain triage framework (`skill-layer appropriate`, `deterministic-fixer appropriate`, `not observed`).
- [x] Published [`research.md`](research.md).

### Phase 1: Design & Contracts *(Complete)*
- [x] Defined analytical data entities, statistical aggregators, and domain models in [`data-model.md`](data-model.md).
- [x] Established CLI syntax, options, and exit codes in [`contracts/cli-contract.md`](contracts/cli-contract.md).
- [x] Defined the 7-section report document schema in [`contracts/report-schema.md`](contracts/report-schema.md).
- [x] Created developer validation guide in [`quickstart.md`](quickstart.md).
- [x] Completed implementation plan in [`plan.md`](plan.md).

### Phase 2: Tasks & Implementation *(Next Phase)*
- [ ] Generate dependency-ordered tasks via `/speckit-tasks`.
- [ ] Implement `backend/scripts/analyze_historical_baseline.py`.
- [ ] Implement `backend/tests/test_historical_baseline.py`.
- [ ] Execute test suite and run analysis against `studio.db`.
- [ ] Generate `reports/009-historical-baseline.md`.
