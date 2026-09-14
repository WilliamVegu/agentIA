# Technical Research & Decisions: Automated Test Generation, Code Analysis & Iterative Self-Repair

**Feature**: `005-automated-tests-analysis`  
**Date**: 2026-09-13  
**Status**: Completed  

---

## 1. Context & Objectives

The goal of this feature is to enable autonomous, high-integrity verification and self-healing of generated Java 21 / Spring Boot 3 microservices. It must automatically author comprehensive test suites, execute them within an offline Docker sandbox, parse structured diagnostics from compiler/assertion errors, perform static architecture compliance checks, apply surgical code modifications, and iterate up to 3 times until the microservice is verified or requires human intervention.

---

## 2. Research Topics & Architectural Decisions

### Decision 1: Hybrid Test Synthesis Architecture (Unit + Web/DB Integration)

- **Decision**: Synthesize two complementary tiers of automated tests:
  1. **Unit Tests (Mockito + AssertJ)**: Target `@Service` implementations by mocking `@Repository` interfaces and collaborator services. Focus on business logic, edge conditions, null handling, and domain exceptions. Also target `@RestController` via `@WebMvcTest` with mocked services for request validation and HTTP status code mappings.
  2. **Integration Tests (`@SpringBootTest` + `MockMvc`)**: Full application context tests using the in-memory H2 database (`MODE=PostgreSQL`). Execute end-to-end HTTP request/response flows and verify data persistence against the generated `schema.sql` and `data.sql`.
- **Rationale**:
  - Unit tests run in milliseconds and pinpoint internal logic defects without database overhead.
  - Integration tests validate real JPA entity mappings, database constraints (unique, foreign key, not null), and HTTP serialization.
  - Both tiers run 100% offline in the Docker sandbox without external network or Docker-in-Docker requirements.
- **Alternatives Considered**:
  - *Unit tests only*: Rejected because it leaves JPA entity mappings, table constraints, and SQL DDL unverified in real runtime conditions.
  - *Integration tests only*: Rejected because large context reloads make the self-repair loop excessively slow and isolate internal branch errors poorly.

---

### Decision 2: Structured Diagnostic Parsing & Surgical Patch Strategy

- **Decision**: Parse Maven compiler logs (`[ERROR] /path/to/File.java:[line,col] error: ...`) and Surefire test reports (`<<< FAILURE! ... ComparisonFailure: expected:<...> but was:<...>`) into a normalized `FailureDiagnostic` model. When diagnosing, the repair agent isolates the enclosing method or block and outputs a targeted search-and-replace or method-level replacement patch rather than regenerating entire source files.
- **Rationale**:
  - Regenerating entire classes is computationally expensive, risks hallucinating regressions in unrelated working methods, and generates massive, unreadable git diffs.
  - Surgical patches preserve unmodified code, localize changes, and allow the developer to clearly understand what the self-repair engine modified.
- **Alternatives Considered**:
  - *Full-class rewriting*: Rejected due to high risk of regression, token overhead, and poor diff clarity.
  - *Unified diff (`patch`) tool*: Considered, but whitespace and line-number drift make direct `patch` brittle in automated environments. A method/block replacement pattern is more robust.

---

### Decision 3: Dual-Mode Code Analysis (Dynamic Runtime + Constitutional Static Gate)

- **Decision**: Implement a two-tier analysis engine:
  1. **Dynamic Analysis**: Captures compiler exit codes, syntax errors, uncaught exceptions, and failed assertions from Maven Surefire reports.
  2. **Static Architecture Gate (`CodeComplianceAnalyzer`)**: Parses Java source files using regular expressions/AST heuristics to enforce Constitution rules before recompiling:
     - **Principle I**: Controllers never reference repositories or JPA entities directly.
     - **Principle II**: Request/Response DTOs are strictly Java Records.
     - **Principle III**: Controllers do not catch exceptions or return ad-hoc error bodies; errors flow through `@RestControllerAdvice`.
     - **Principle IV**: Zero dynamic dependency downloads in `pom.xml`.
- **Rationale**:
  - Without static architecture checks, an AI repair agent might "fix" a test failure by taking illegal architectural shortcuts (e.g. injecting a repository into a controller or mutating a DTO).
  - Catching architectural violations statically prevents non-compliant code from ever reaching the build stage.
- **Alternatives Considered**:
  - *SonarQube / Checkstyle in Docker*: Rejected for runtime overhead; lightweight in-process Python AST/regex rules run instantaneously without adding container dependencies.

---

### Decision 4: Self-Repair State Machine & Human-in-the-Loop Blocked Mode

- **Decision**: Orchestrate self-repair through a formal state machine:
  ```text
  INITIALIZATION ➔ SCAFFOLDING ➔ TEST_SYNTHESIS ➔ SANDBOX_BUILD ➔ TEST_EXECUTION
        │                                                                │
        │                                            (Tests Pass 100%)   │ (Tests Fail)
        │                                                    ▼           ▼
        │                                                VERIFIED   SELF_REPAIR_LOOP (Iter 1..3)
        │                                                                │
        │                                                    (Attempt > 3)
        │                                                                ▼
        └─────────────────────────────────────────────────────────►   BLOCKED
  ```
  When the session enters `BLOCKED`, Streamlit renders:
  1. Detailed failure diagnostics and stack traces.
  2. An interactive in-browser code editor (Monaco or Streamlit text area) displaying the defective file.
  3. An AI hint assistant allowing the developer to provide natural language guidance or manual code adjustments and click `"🔄 Aplicar Corrección y Reintentar"`.
- **Rationale**:
  - Complies strictly with Constitution Principle V (hard cap of 3 autonomous attempts).
  - Empowers developers to unblock edge-case failures without discarding the entire project or starting over.
- **Alternatives Considered**:
  - *Automatic project rollback*: Frustrating to users as it discards 95% of working code due to a minor assertion failure.
  - *Infinite auto-repair*: Prohibited by Constitution Principle V to avoid infinite token loops.

---

### Decision 5: Ephemeral Security & Zero-Secret Governance

- **Decision**: Maintain all LLM interactions (diagnostic explanation, patch generation, manual hint resolution) in memory using the session's active OpenAI key (`X-LLM-API-Key` or payload). No keys or tokens are stored in the database, Docker containers, or git commits.
- **Rationale**: Strict compliance with Constitution Principle VI.

