# Implementation Plan: Finalize Skill Domain Set and Author Seed Skill Documents

**Branch**: `010-skill-injection` | **Date**: 2026-09-25 | **Spec**: [specs/010-skill-injection/spec.md](spec.md)

**Input**: Feature specification from `specs/010-skill-injection/spec.md` ("Finalize skill domain set and author seed skill documents: Convert Task 0's triage output into a finalized set of hand-authored skill documents, version-frozen and ready for injection. Resolve any ambiguity in the triage classification before authoring.")

---

## Summary

This feature transitions the empirical baseline findings from Task 0 (`reports/009-historical-baseline.md`) into a version-frozen, hand-authored set of seed skill markdown documents in `backend/app/resources/skills/`. It resolves all triage ambiguities between prompt skills and deterministic AST/regex fixers, defines procedural and ordered rules for surviving skill domains, authors a complete engineering specification for mechanical fixers, and documents resolutions for the three open architectural decisions.

Key deliverables:
1. **Finalized Domain Catalog** (`specs/010-skill-injection/domains.md`): Triage classifications for all 5 candidate domains with empirical citations from Task 0.
2. **Three Seed Skill Documents** (`backend/app/resources/skills/`):
   - `layer_architecture.md`: Task-level rules enforcing 4-layer isolation, immutable DTO Records, and prohibited `@Data`.
   - `exception_handling.md`: Task-level rules for `@RestControllerAdvice` and RFC 7807 `ProblemDetails` error contracts.
   - `mockito_tests.md`: Event-driven rules for Spring Boot slice tests, strict stubbing, and interaction verification.
3. **Deterministic Fixer Specification** (`specs/010-skill-injection/fixers.md`): Architectural guide for `jakarta_namespace` and `maven_pom` AST/regex post-processors.
4. **Task 1 Executive Summary** (`specs/010-skill-injection/task1-summary.md`): High-level synthesis, token budget verification, and decision resolutions.
5. **Automated Linter & Test Suite** (`backend/scripts/validate_seed_skills.py` & `backend/tests/test_seed_skills.py`): Verifies token constraints (<500 tokens/skill, <2,000 tokens total) and markdown format compliance.

---

## Technical Context

**Language/Version**: Markdown (GFM), Python 3.10+ (for validation script and tests).

**Primary Dependencies**: Standard library (`pathlib`, `re`, `argparse`), `pytest` for test execution.

**Storage**:
- Seed skills: `backend/app/resources/skills/*.md`.
- Specifications: `specs/010-skill-injection/`.

**Testing**: Pytest (`backend/tests/test_seed_skills.py`) validating structure, header presence, procedural rule syntax, empty slow-update boundaries, and token budgets.

**Target Platform**: Platform-agnostic (portable markdown assets for LLM injection).

**Project Type**: Specification & Prompt Engineering / Prompt Assets.

**Performance & Token Goals**:
- Token limit per skill: < 500 tokens.
- Token limit combined: < 2,000 tokens.
- Validation script runtime: < 0.5 seconds.

**Constraints**:
- Strict 5-section markdown structure matching CODESKILL Figures 4-5.
- Procedural, ordered rules; zero declarative advice.
- Zero instance-specific literals (no class names, repo names, file paths, or variable names).
- Empty slow-update markers (`<!-- SLOW_UPDATE_START -->` / `<!-- SLOW_UPDATE_END -->`).
- Zero changes to existing AgentIA core runtime code, database schema, or LangGraph nodes during this task.

---

## Constitution Check

*GATE: Verified against `.specify/memory/constitution.md`.*

| Principle | Relevance & Impact on Feature | Status |
|---|---|---|
| **I. Layer Isolation** | Addressed directly by `layer_architecture.md` skill, enforcing strict controller -> service -> repository isolation. | **PASS** |
| **II. Immutable DTOs & Records** | Enforced by `layer_architecture.md`, requiring native Java Records and Jakarta Validation on request DTOs. | **PASS** |
| **III. Centralized Exception Handling** | Addressed directly by `exception_handling.md`, mandating `@RestControllerAdvice` and RFC 7807 `ProblemDetails`. | **PASS** |
| **IV. Offline Determinism & Sandbox** | Addressed by `maven_pom` fixer spec, ensuring dependencies are pre-cached and builds run offline (`mvn test -o`). | **PASS** |
| **V. Quality Gates & 3-Repair Cap** | Addressed by `mockito_tests.md` skill, preventing loop exhaustion caused by Mockito strict stubbing errors. | **PASS** |
| **VI. Zero Secrets & Orchestrator Boundaries** | Seed skills do not contain or handle credentials; operate strictly within prompt asset boundaries. | **PASS** |

*Gate Verdict: ALL CONSTITUTIONAL PRINCIPLES SATISFIED. ZERO VIOLATIONS.*

---

## Project Structure

### Documentation (this feature)

```text
specs/010-skill-injection/
├── spec.md                     # Feature specification
├── plan.md                     # This implementation plan
├── research.md                 # Decision resolutions & CODESKILL mapping
├── data-model.md               # Asset specifications & schemas
├── quickstart.md               # Validation & linting guide
├── domains.md                  # Deliverable 1: Finalized domain triage catalog
├── fixers.md                   # Deliverable 3: Deterministic fixer specification
├── task1-summary.md            # Deliverable 4: Executive synthesis & viability report
├── checklists/
│   └── requirements.md         # Requirements quality checklist
└── contracts/
    ├── skill-document-contract.md  # Schema for seed skill markdown files
    └── fixer-spec-contract.md      # Schema for fixer specification entries
```

### Source Code & Resource Assets (repository root)

```text
backend/
├── app/
│   └── resources/
│       └── skills/
│           ├── layer_architecture.md    # Seed skill: 4-layer isolation & DTOs
│           ├── exception_handling.md    # Seed skill: Global advice & RFC 7807
│           └── mockito_tests.md         # Seed skill: Mockito test synthesis & stubs
├── scripts/
│   └── validate_seed_skills.py          # Standalone token & format linter script
└── tests/
    └── test_seed_skills.py              # Automated test suite for skill assets
```

**Structure Decision**: Seed skills are placed in `backend/app/resources/skills/` to sit alongside existing offline assets (`cve_database.json`) where future injection nodes can read them directly. Specification documents remain organized in `specs/010-skill-injection/`.

---

## Complexity Tracking

> **Constitution check confirmed zero violations. No unjustified complexity introduced.**

| Violation | Why Needed | Simpler Alternative Rejected Because |
| :---: | :---: | :---: |
| None | N/A | N/A |

---

## Phases & Deliverables

### Phase 0: Outline & Research *(Complete)*
- [x] Resolved Decision 1: Exclusive delegation to fixers for `jakarta_namespace` and `maven_pom` (zero token waste).
- [x] Resolved Decision 2: Assigned `task-level` to `layer_architecture` and `exception_handling`, and `event-driven` to `mockito_tests`.
- [x] Resolved Decision 3: Formulated explicit pilot viability threshold (>= 2 domains; 3 observed -> VIABLE).
- [x] Published [`research.md`](research.md).

### Phase 1: Design & Contracts *(Complete)*
- [x] Defined analytical data models and entity structures in [`data-model.md`](data-model.md).
- [x] Established strict markdown and token budget contracts in [`contracts/skill-document-contract.md`](contracts/skill-document-contract.md).
- [x] Established fixer engineering schema in [`contracts/fixer-spec-contract.md`](contracts/fixer-spec-contract.md).
- [x] Created developer validation guide in [`quickstart.md`](quickstart.md).
- [x] Completed implementation plan in [`plan.md`](plan.md).

### Phase 2: Tasks & Implementation *(Next Phase)*
- [ ] Generate dependency-ordered tasks via `/speckit-tasks`.
- [ ] Author `specs/010-skill-injection/domains.md`.
- [ ] Author `backend/app/resources/skills/layer_architecture.md`.
- [ ] Author `backend/app/resources/skills/exception_handling.md`.
- [ ] Author `backend/app/resources/skills/mockito_tests.md`.
- [ ] Author `specs/010-skill-injection/fixers.md`.
- [ ] Author `specs/010-skill-injection/task1-summary.md`.
- [ ] Implement validator script `backend/scripts/validate_seed_skills.py` and test suite `backend/tests/test_seed_skills.py`.
- [ ] Validate token budgets and format compliance.
