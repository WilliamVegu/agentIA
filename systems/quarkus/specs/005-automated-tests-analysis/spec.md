# Feature Specification: Automated Test Generation, Code Analysis & Iterative Self-Repair

**Feature Branch**: `005-automated-tests-analysis`

**Created**: 2026-09-13

**Status**: Draft

**Input**: User description: "el sistema debe poder crear y ejecutar pruebas que permitan analizar el codigo generado y modificarlo hasta que corregirlos"

---

## Overview

Following the generation of architectural components, domain models, JPA entities, and relational database schemas, the system must provide autonomous capabilities for **Test Generation, Code Analysis, and Iterative Self-Repair**. 

This feature enables Microservice Code Studio to:
1. Synthesize comprehensive test suites (covering happy path, input validation, and business exceptions) derived from Given/When/Then acceptance criteria.
2. Execute the test suites within an isolated, hermetic sandbox and analyze the runtime execution traces and static code structure.
3. Diagnose compilation and test assertion failures, plan surgical source code repairs, apply code modifications, and iteratively re-run tests until all tests pass with a 100% success rate (or until reaching the constitutional limit of 3 iterations).
4. Provide a visual dashboard with real-time test execution status, diagnostics, and step-by-step diffs of each repair iteration.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Comprehensive Test Suite Synthesis (Priority: P1) 🎯 MVP

As a software quality engineer or developer, I want the system to automatically generate complete, runnable test suites for all microservice components (controllers, services, and repositories) derived from acceptance criteria, so that every business scenario is verified with zero manual test authoring.

**Why this priority**: Foundational prerequisite for code verification. Code cannot be evaluated, diagnosed, or repaired without an executable, high-fidelity test suite.

**Independent Test**: Can be tested by providing a microservice blueprint and user stories with Given/When/Then scenarios, running test generation, and verifying that the system outputs complete test files for controllers, services, and repositories with assertions matching every scenario.

**Acceptance Scenarios**:

1. **Given** a microservice blueprint with user stories and acceptance criteria, **When** test generation executes, **Then** the system produces unit tests for service business logic using mocks, covering both happy paths and edge cases.
2. **Given** REST endpoint contracts and validation rules, **When** controller test generation executes, **Then** the system creates web layer tests verifying HTTP status codes (200, 201, 400, 404, 409, 500) and response payloads.
3. **Given** acceptance scenarios with precondition data, **When** test cases are generated, **Then** test fixtures and assertions directly reflect the `Given` states and `Then` outcomes.

---

### User Story 2 - Hermetic Test Execution & Failure Diagnostics (Priority: P1)

As a DevOps engineer or reliability architect, I want the system to execute generated test suites inside an isolated hermetic execution sandbox and extract structured diagnostics from failures, so that bugs and regressions are surfaced with actionable context without external network dependencies.

**Why this priority**: Core verification engine. Converts raw build tool terminal output into machine-readable diagnostics (file paths, line numbers, error types, expected vs. actual values) necessary for autonomous repair.

**Independent Test**: Can be tested by executing a generated test suite against valid or deliberately buggy code inside the sandbox, verifying that the runner captures execution logs and outputs structured diagnostics for any compilation errors or test assertion failures.

**Acceptance Scenarios**:

1. **Given** generated source code and test files, **When** test execution is triggered, **Then** the sandbox executes the tests offline (`--network none`) and collects exit codes, passing counts, failing counts, and execution duration.
2. **Given** a compilation failure, **When** build logs are analyzed, **Then** the diagnostic engine identifies the offending file, line number, column, and compiler error message.
3. **Given** a test assertion failure, **When** test results are parsed, **Then** the diagnostic engine extracts the failing test method, expected value, actual value, and failure stack trace.

---

### User Story 3 - Autonomous Code Self-Repair Loop (Priority: P1)

As a lead developer, I want the system to automatically analyze diagnostics from failed tests or compiler errors, modify the defective source code, and re-run tests iteratively until all tests pass or the iteration limit is reached, so that generated microservices are delivered defect-free without human intervention.

**Why this priority**: Core self-healing intelligence requested by the user. Automates the iterative debugging and code correction cycle.

**Independent Test**: Can be tested by injecting a known compilation error or logical bug into a generated service, triggering the self-repair loop, and verifying that the system generates a corrective patch, recompiles, re-tests, and transitions to a verified state within a maximum of 3 iterations.

**Acceptance Scenarios**:

1. **Given** one or more failure diagnostics from test execution, **When** the repair agent analyzes the issue, **Then** it produces a targeted code patch modifying only the defective source files without breaking unrelated functionality.
2. **Given** an applied repair patch, **When** the sandbox re-executes tests, **Then** the system checks whether the failure is resolved; if resolved and all tests pass, it marks the session as `VERIFIED`.
3. **Given** a defect that persists after a repair attempt, **When** fewer than the maximum allowed attempts have been made, **Then** the system increments the iteration counter, refines its repair hypothesis with new diagnostic output, and re-attempts the repair.
4. **Given** a defect that remains unresolved after reaching the maximum allowed repair attempts (3 iterations), **When** the final iteration fails, **Then** the system stops the loop immediately and transitions to a blocked state awaiting human intervention.

---

### User Story 4 - Visual Test Explorer, Diagnostics & Repair Diff Viewer (Priority: P2)

As a solution architect or engineering manager, I want an interactive web studio dashboard showing real-time test execution progress, diagnostic details, and side-by-side code diffs for each repair iteration, so that the autonomous self-healing process is completely transparent and inspectable.

**Why this priority**: Human-in-the-loop governance and observability. Enables engineers to understand what failed, what changed between repair iterations, and maintain confidence in the autonomous decisions.

**Independent Test**: Can be tested by navigating to the test explorer tab in the web studio during or after a repair session, viewing the test suite tree, inspecting failure diagnostics, and toggling through before/after code diffs of each repair attempt.

**Acceptance Scenarios**:

1. **Given** an active or completed generation session, **When** viewing the test results view, **Then** the user sees metrics on total tests, passed tests, failed tests, code coverage estimates, and sandbox execution time.
2. **Given** a session that required self-repair iterations, **When** inspecting the repair history, **Then** the user can select iteration 1, 2, or 3 to view the diagnosed cause, applied patch summary, and syntax-highlighted code diff.
3. **Given** a session blocked after exhausting repair attempts, **When** the user inspects the blocked state, **Then** the system highlights the unresolved error and provides an interface to manually edit the code or provide corrective guidance to the AI.

---

### Edge Cases

- **Flaky or Non-Deterministic Tests**: Tests depending on wall-clock time or random values could pass and fail intermittently. The system MUST seed random generators and freeze mock clocks to guarantee deterministic runs.
- **Infinite Repair Loops**: The system MUST enforce a strict hard cap of three (3) repair iterations per Constitution Principle V; after 3 failed attempts it MUST halt and request human intervention.
- **Cascading Failures**: When fixing one error introduces a new compiler or test error in a different file, the repair planner MUST roll back regression-inducing patches or incorporate multi-file fixes in a single atomic repair step.
- **Syntactically Invalid Repair Patches**: Before executing tests in the sandbox, the system MUST validate that generated repair patches do not introduce syntax errors or broken imports.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST automatically generate unit tests for service classes with mocked repository dependencies, testing both happy paths and business exception paths.
- **FR-002**: System MUST automatically generate controller integration tests verifying HTTP endpoints, request body validation, response status codes, and error payloads.
- **FR-003**: System MUST execute all test suites inside an isolated, hermetic sandbox with zero external network connectivity (`--network none`) and offline build tool mode.
- **FR-004**: System MUST parse build output and test execution results into structured diagnostic objects containing file path, line number, error classification, expected vs. actual values, and stack traces.
- **FR-005**: System MUST prioritize compilation errors before test assertion errors during diagnostic analysis.
- **FR-006**: System MUST generate targeted, surgical source code patches at the method or code-block level to repair identified diagnostics, avoiding whole-file regeneration and preserving unmodified business logic.
- **FR-007**: System MUST re-execute the test suite after each repair patch is applied to evaluate whether all tests pass.
- **FR-008**: System MUST limit the autonomous self-repair cycle to a maximum of three (3) iterations, adhering strictly to Constitution Principle V.
- **FR-009**: System MUST transition the session to a `VERIFIED` state when 100% of tests pass, or to a `BLOCKED` state (human intervention required) if errors persist after the third repair attempt.
- **FR-010**: System MUST record and persist the complete history of each repair iteration, including the diagnostic, proposed change, applied source code diff, and subsequent test outcome.
- **FR-011**: System MUST integrate the test synthesis, execution, and self-repair loop directly into the autonomous pipeline of Tab 4 ('🚀 4. Generación & Logs en Vivo') transitioning through phases (SCAFFOLDING → CODE_GENERATION → TEST_SYNTHESIS → SANDBOX_BUILD → TEST_EXECUTION → SELF_REPAIR_LOOP → VERIFIED), and render verification metrics and repair diff history in Tab 5 ('🔍 5. Explorador de Código & Tests').
- **FR-012**: System MUST provide a side-by-side or unified code diff viewer in the web studio showing the exact lines modified during each self-repair iteration.
- **FR-013**: System MUST provide an override capability when a session is blocked, allowing the developer to review failure details, edit the defective source file directly, or provide a natural language hint to guide the next repair iteration.
- **FR-014**: System MUST ensure that test generation, execution, analysis, and repair operations function without persisting API secrets or credentials, using in-memory ephemeral keys.

- **FR-015**: System MUST synthesize a hybrid test suite comprising isolated unit tests with Mockito for business service logic and controllers (`@WebMvcTest`), plus end-to-end integration tests (`@SpringBootTest`) validating HTTP contract flows against the in-memory H2 database (`MODE=PostgreSQL`).
- **FR-016**: System MUST handle the blocked state after 3 failed repair attempts by marking the session as `BLOCKED`, displaying detailed diagnostics, and offering an in-browser code editor with AI assistance to manually inspect, edit the code, and trigger an explicit re-evaluation.
- **FR-017**: System MUST perform dual code analysis combining dynamic compiler and test execution failures (`mvn test -o`) with static architectural rule verification (strict 4-layer dependency compliance, Java Record immutability for DTOs, and Jakarta validation presence) to prevent repairs from introducing architectural drift.

---

### Key Entities

- **TestSuiteDefinition**: Represents a generated test file (class name, target component, package, test methods, dependencies to mock).
- **TestCaseDefinition**: Represents an individual test case (name, tested scenario, Given/When/Then mapping, assertions).
- **TestExecutionReport**: Represents the summary of a test run (total tests, passed tests, failed tests, execution duration, sandbox exit code).
- **FailureDiagnostic**: Represents a single diagnosed error (file path, line number, error category: `COMPILATION_ERROR` or `ASSERTION_FAILURE`, error message, expected value, actual value, stack trace).
- **CodeRepairPatch**: Represents a proposed correction for a file (target file path, before content, after content, explanation of repair hypothesis).
- **RepairIterationRecord**: Represents a complete repair attempt (iteration number, diagnostics addressed, patches applied, test outcome, diff summary).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Autonomous test suite generation completes in under 20 seconds for microservices with 2 to 10 endpoints.
- **SC-002**: Generated test suites achieve 100% pass rate on correctly scaffolded microservices upon first execution.
- **SC-003**: The self-repair engine successfully resolves over 85% of standard syntax, import, and logic assertion errors within 3 iterations without human intervention.
- **SC-004**: Each self-repair iteration (diagnosis, patch generation, re-compilation, and re-test) completes in under 30 seconds.
- **SC-005**: 100% of verified microservices pass all Maven tests in offline mode (`mvn test -o`) with zero network access.
- **SC-006**: Users can inspect the complete audit trail and code diffs of every repair iteration in the web studio in under 3 clicks.

---

## Assumptions

- Generated microservice code targets Java 21 LTS, Spring Boot 3.x, JUnit 5, Mockito, and AssertJ.
- The test runner executes inside the project Docker sandbox using pre-cached Maven dependencies in `.m2`.
- Ephemeral OpenAI API keys are supplied in memory via session state or `X-LLM-API-Key` headers; no secrets are written to disk or repository.
- Unit tests use Mockito for mocking service/repository interactions, eliminating reliance on external network services or external databases during testing.

---

## Clarifications

### Session 2026-09-13
- Q: ¿Qué alcance debe tener la suite de pruebas generada automáticamente? → A: Suite Híbrida: Pruebas unitarias con mocks (`Mockito` / `AssertJ`) para servicios y controladores web (`@WebMvcTest`) + Pruebas de integración con base de datos H2 en memoria (`@SpringBootTest`).
- Q: ¿Cómo debe comportarse el sistema cuando se agotan los 3 intentos máximos de auto-reparación? → A: Intervención Asistida en Web: Marcar sesión como `BLOCKED`, mostrar diagnóstico detallado del fallo y habilitar un editor de código en el navegador con botón "Aplicar corrección manual y reintentar".
- Q: ¿Qué profundidad debe tener el análisis del código generado y reparado? → A: Análisis Dual Dinámico + Reglas Constitucionales: Analizar errores dinámicos de compilación/test (`mvn test -o`) y verificar estáticamente el cumplimiento de la Constitución (arquitectura 4 capas sin ciclos, uso de Records DTOs inmutables y validaciones Jakarta).
- Q: ¿En qué nivel de granularidad debe el motor de auto-reparación aplicar las modificaciones al código fuente Java cuando se detecta un fallo? → A: Parches Quirúrgicos por Método/Bloque: El agente localiza el método o bloque defectuoso a partir del stack trace y aplica un reemplazo delimitado sin regenerar el archivo completo.
- Q: ¿Cómo debe integrarse el ciclo de pruebas y auto-reparación en el flujo de trabajo de Streamlit? → A: Pipeline Autónomo Integrado en Tab 4: Se ejecuta automáticamente en la Pestaña 4 pasando por las fases SCAFFOLDING → TEST_SYNTHESIS → SANDBOX_BUILD → TEST_EXECUTION → SELF_REPAIR_LOOP, y exponiendo el historial de diffs y métricas en la Pestaña 5.

