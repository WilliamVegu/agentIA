# Feature Specification: Microservice Code Studio Web Application

**Feature Branch**: `001-microservice-code-studio`

**Created**: 2026-09-13

**Status**: Draft

**Input**: User description: "quiero una aplicacion web que me permita desarrollar código Java/Spring Boot en base a arquitectura, historias de usuario y criterios de aceptacion"

## Clarifications

### Session 2026-09-13
- Q: ¿Cómo interactuará el usuario para definir y editar la arquitectura, las historias de usuario y los criterios de aceptación en la interfaz web? (FR-001) → A: Fuera de alcance para esta especificación; la edición/redacción interactiva de especificaciones será gestionada por otra especificación del sistema. Esta especificación se enfoca exclusivamente en la ingesta y validación de especificaciones existentes para ejecutar la generación autónoma de código, compilación hermética, pruebas unitarias, monitoreo en vivo, auto-reparación (hasta 3 intentos) y exportación.
- Q: ¿En qué formato espera la aplicación web recibir o ingerir la especificación predefinida desde el otro componente para iniciar la generación? (FR-001) → A: Soporte dual: ingesta mediante carga de archivo Markdown estándar de Spec Kit (`spec.md`) y mediante endpoint API REST que recibe un payload JSON estructurado.
- Q: ¿Cómo debe la aplicación web gestionar la autenticación de usuarios y las credenciales para la publicación en repositorios Git? (FR-011, FR-012) → A: Modo workspace interno ágil sin login obligatorio de usuario para generar y explorar código; las credenciales para publicación en repositorios Git se suministran de forma efímera por sesión en memoria o mediante variables de entorno del servidor, sin persistencia en disco ni bases de datos.
- Q: ¿Qué protocolo en tiempo real debe emplear la aplicación web para transmitir el progreso de generación, los logs de Maven y los eventos de auto-reparación al navegador? (FR-005) → A: Server-Sent Events (SSE), proporcionando streaming unidireccional continuo sobre HTTP con soporte nativo de reconexión automática para el flujo de logs, etapas del ciclo de vida y métricas de prueba.
- Q: ¿Cómo debe la aplicación web gestionar la concurrencia y los recursos cuando múltiples solicitudes de generación se envían simultáneamente? (FR-004) → A: Cola de espera FIFO con límite de concurrencia configurable (máximo 2 ejecuciones simultáneas en paralelo); las solicitudes adicionales se encolan mostrando su posición en tiempo real al usuario.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ingestion and Pre-Generation Validation of Service Specifications (Priority: P1)

As a developer or automated client, I want to submit or load pre-existing microservice specifications (containing architecture definitions, user stories, and formal acceptance criteria) through dual mechanisms—either by uploading a standard Spec Kit Markdown file (`spec.md`) or sending a structured JSON payload via REST API—so that the system can validate their completeness and verify compliance with technical standards before initiating autonomous code generation.

*(Note: Authoring or interactive editing of specifications is out of scope for this feature and handled by a dedicated sister specification).*

**Why this priority**: The generation engine requires a structured, unambiguous specification as input. Validating the received specification before triggering generation prevents malformed or incomplete runs.

**Independent Test**: Can be fully tested by submitting a complete specification payload (via web upload of `spec.md` or a POST request to the REST ingestion endpoint) and verifying that the validation engine checks all required components (entities, user stories, Given/When/Then scenarios) and emits an unambiguous readiness signal.

**Acceptance Scenarios**:

1. **Given** a pre-defined Spec Kit Markdown file (`spec.md`) or a structured JSON payload, **When** a user or client submits it to the web application via file upload or REST endpoint, **Then** the system parses the document, validates the schema (architecture, stories, criteria), and returns a parsed summary with a valid session ID.
2. **Given** a valid specification payload, **When** the user or client requests pre-generation validation, **Then** the system verifies that all user stories contain Given/When/Then acceptance criteria and that entity relationships are well-formed, transitioning to a ready-to-generate state.
3. **Given** an incomplete or malformed specification payload (e.g. missing acceptance criteria or unregistered entities), **When** validation is run, **Then** the system highlights the missing elements, reports validation errors, and blocks code generation.

---

### User Story 2 - Autonomous Code Generation and Live Progress Monitoring (Priority: P1)

As a developer, I want to trigger the autonomous generation of the microservice and observe real-time execution logs, compilation events, and automated test execution streamed via Server-Sent Events (SSE) so that I have complete visibility into the generation process and self-healing cycles.

**Why this priority**: Represents the core value proposition of the system: transforming verified specifications into executable source code and comprehensive automated test suites autonomously.

**Independent Test**: Can be fully tested by submitting a validated specification, triggering the generation process, and observing real-time phase transitions (scaffolding, component synthesis, offline compilation, unit test execution, and self-repair status) streamed to the client over an SSE connection.

**Acceptance Scenarios**:

1. **Given** a validated specification, **When** the user clicks "Generate Microservice", **Then** the system initiates an autonomous generation session, opens an SSE stream, and displays live stage indicators for scaffolding, layers, and test suite creation.
2. **Given** an active generation session where a compilation or test assertion failure occurs, **When** the autonomous engine initiates self-repair, **Then** the interface displays the current repair iteration number (up to 3 attempts) and streams the diagnostic failure output.
3. **Given** a generation session that successfully passes 100% of automated unit tests, **When** execution concludes, **Then** the interface transitions to a success state displaying the build summary, test metrics, and file manifest.
4. **Given** a generation session where compilation or test errors persist after the 3rd repair attempt, **When** the retry limit is exhausted, **Then** the system halts execution, transitions to a "Blocked: Human Intervention Required" state, and presents a diagnostic report.
5. **Given** maximum concurrent generation sessions running (e.g., 2 active), **When** another generation is triggered, **Then** the system places the request into a FIFO queue and streams the queue position to the client until a worker becomes available.

---

### User Story 3 - Interactive Code Exploration and Verification Inspection (Priority: P2)

As a technical reviewer or auditor, I want to explore the generated microservice file tree, inspect source code with syntax highlighting, and examine automated test results in an integrated web viewer so that I can audit quality, layer boundaries, and compliance before publishing.

**Why this priority**: High priority for governance, security, and developer trust. Allows engineers to inspect what was built, verify clean code practices, and confirm test coverage before committing artifacts.

**Independent Test**: Can be fully tested by opening a completed generation session, expanding the interactive file tree across presentation, service, repository, and test folders, and verifying file contents, line numbering, and test report summaries.

**Acceptance Scenarios**:

1. **Given** a successfully generated microservice session, **When** the user accesses the code exploration tab, **Then** the system renders an interactive file explorer reflecting the strict layered package hierarchy.
2. **Given** the file explorer, **When** the user selects any source file or test file, **Then** the system renders the source code in a read-only viewer with syntax highlighting and line indicators.
3. **Given** a completed session, **When** the user opens the verification panel, **Then** the system displays comprehensive test execution results (total tests executed, pass rate, execution duration, and mock coverage).

---

### User Story 4 - Project Export and Repository Integration (Priority: P3)

As a team lead or developer, I want to export the generated project as a downloadable compressed archive or publish it directly to an isolated version control branch with an atomic commit and Pull Request reference using ephemeral session credentials so that the code seamlessly integrates into the enterprise CI/CD workflow.

**Why this priority**: Essential for integrating generated microservices into downstream pipelines, source control, and deployment systems once validated.

**Independent Test**: Can be fully tested by selecting "Download Archive" to receive a clean ZIP archive of the project, or providing in-memory ephemeral repository details to trigger a feature branch push and receiving a valid Pull Request reference.

**Acceptance Scenarios**:

1. **Given** a validated and approved microservice session, **When** the user clicks "Download Archive", **Then** the system bundles the complete project files and delivers a clean ZIP file download.
2. **Given** configured in-memory repository credentials or server environment variables, **When** the user clicks "Publish to Branch", **Then** the system pushes the atomic commit to a dedicated feature branch following naming conventions and provides a direct Pull Request link without storing credentials permanently.

---

### Edge Cases

- **Session Disconnection During Generation**: If a user closes the browser or experiences network interruption while code generation is running, the server-side process must continue unimpeded; upon reconnecting via SSE using the last event ID, the application catches up with the latest execution status and resumes real-time log streaming.
- **Empty or Incomplete Acceptance Criteria in Ingested Spec**: If an ingested user story has a title but lacks Given/When/Then scenarios, the validation engine must flag the story as incomplete and disable generation until at least one scenario is provided.
- **Complex Inter-Entity Dependencies**: When an ingested specification defines circular or deeply nested entity relationships, the validator must verify navigation paths and prevent contradictory data models before code synthesis begins.
- **Persistent Compilation Failure**: If the autonomous generator cannot fix a compilation error within the strict 3-iteration limit, the system must cleanly terminate the session, prevent endless execution loops, and preserve full log diagnostics for user analysis.
- **Concurrent Resource Saturation**: When generation requests exceed active worker capacity, additional requests remain safely enqueued in FIFO order without dropping connections or exceeding system memory constraints.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide dual ingestion mechanisms: (1) web file upload supporting standard Spec Kit Markdown (`spec.md`) documents, and (2) a REST API endpoint accepting structured JSON payloads representing architecture blueprints, user stories, and acceptance criteria.
- **FR-001a (Scope Boundary)**: Interactive authoring, visual editing, and drafting of specifications from scratch is explicitly OUT OF SCOPE for this feature and MUST be handled by a dedicated specification authoring component.
- **FR-002**: System MUST validate ingested specifications for structural completeness, domain consistency, and format compliance prior to enabling code generation.
- **FR-003**: System MUST verify that ingested specifications contain prioritized user stories (P1, P2, P3) and structured acceptance criteria (Given/When/Then format).
- **FR-004**: System MUST orchestrate autonomous code generation sessions through an execution engine with a configurable FIFO queue (default: maximum 2 concurrent generations), managing sandbox worker resources for isolated builds and tests.
- **FR-005**: System MUST stream real-time progress updates, active lifecycle phases, Maven build logs, queue status, and auto-repair diagnostic events to the browser client using Server-Sent Events (SSE) with automatic reconnection capabilities.
- **FR-006**: System MUST execute automated unit tests and enforce an automated self-repair loop with a strict limit of 3 consecutive correction attempts upon build or assertion failure.
- **FR-007**: System MUST immediately abort generation and label the session as "Blocked: Human Intervention Required" if errors persist following the 3rd correction attempt.
- **FR-008**: System MUST provide an integrated file tree explorer and code viewer with syntax highlighting to inspect all generated source code and configuration files.
- **FR-009**: System MUST display an automated verification dashboard showing test execution statistics, pass/fail status, and coverage metrics.
- **FR-010**: System MUST enable users to download the full generated project as a compressed archive package.
- **FR-011**: System MUST allow users to publish generated code to a dedicated version control feature branch with atomic commits ready for Pull Request review using ephemeral session tokens or server-configured environment variables.
- **FR-012**: System MUST operate under an internal workspace model without mandatory user authentication for code generation/exploration, and MUST treat all Git credentials as strictly ephemeral (in-memory only or via server environment variables), prohibiting persistent disk or database storage of secrets in compliance with Constitution Principle VI.

### Key Entities *(include if feature involves data)*

- **ArchitectureBlueprint**: Represents the received structural definition of the microservice, including service name, package identifier, layer definitions, domain models, and persistence configuration.
- **UserStoryDefinition**: Represents an ingested prioritized user requirement containing priority level (P1, P2, P3), stakeholder role, desired action, business rationale, and associated acceptance scenarios.
- **AcceptanceScenario**: Represents a formal behavioral test criterion linked to a user story, defined using structured Given (precondition), When (action/event), and Then (expected outcome) clauses.
- **GenerationSession**: Represents a discrete execution run of the code synthesis engine, tracking session state (Queued, Generating, Testing, Completed, Blocked), queue position, iteration counters, timestamps, and execution logs.
- **GeneratedArtifact**: Represents an individual synthesized file (source code, configuration, or unit test) associated with a generation session, including relative path, file type, and file content.
- **VerificationMetric**: Represents the outcome of the automated build and test pipeline, capturing total tests executed, pass rate, failure traces, execution duration, and compliance check results.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Ingestion and automated validation of a complete pre-defined specification payload takes under 5 seconds.
- **SC-002**: 100% of specifications that pass pre-generation validation and complete the generation cycle produce a project that successfully compiles and passes 100% of automated unit tests.
- **SC-003**: Live generation progress, queue position, and phase updates appear in the web interface with latency under 1 second from server event emission via SSE.
- **SC-004**: In automated error scenarios, the self-repair cycle resolves at least 70% of recoverable compilation or test assertion failures within the 3-iteration limit without human intervention.
- **SC-005**: 100% of generation sessions failing after the 3rd repair attempt are cleanly halted and marked as "Blocked: Human Intervention Required" with a complete diagnostic trace.
- **SC-006**: 95% of first-time users can navigate from specification ingestion to code exploration and archive export without encountering unhandled application errors.

## Assumptions

- Specifications are authored in an external tool or sister specification module and supplied to this application in standard structured format (e.g. Spec Kit Markdown or JSON).
- The application operates as an internal engineering workspace tool; network or perimeter security controls access, requiring no internal user login for generation.
- The web application backend provides an isolated, offline-capable sandbox environment for executing build and testing pipelines.
- Ingested specifications and generated session metadata are stored in the application backend to allow users to pause, resume, and re-run generation sessions.
- In-memory test persistence and mock frameworks are utilized during test phases so that builds require zero external network dependencies.
- Repository export uses ephemeral in-memory tokens or pre-configured server environment variables; no secret keys are permanently saved to database or disk.
