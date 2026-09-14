# Feature Specification: End-to-End Unified Workflow Orchestration

**Feature Branch**: `008-unified-workflow-orchestration`

**Created**: 2026-09-13

**Status**: Draft

**Input**: User description: "necesito que todo el proceso este correctamente coordinado, desde principio a fin, que pueda seguir un flujo coherente, eficaz y sencillo"

---

## Overview

Following the development of seven core microservice generation capabilities (Spec Ingestion, Requirements to User Stories, Architecture & Component Design, Data Model & SQL Persistence, Automated Testing & Self-Repair, Security & Quality Gate Auditing, and Docker/CI-CD Deployment Orchestration), the platform currently functions as a collection of powerful but individually triggered modules across separate studio views.

This feature delivers a **Unified End-to-End Workflow Coordinator** that weaves all phases into a cohesive, streamlined, and dependable developer journey. It introduces:
1. A **Central Lifecycle Coordinator** managing state transitions, phase progression, and prerequisites.
2. A **Dual Execution Engine**:
   - **Guided Step-by-Step Mode**: Step-by-step wizard providing contextual recommendations, validation guards, and single-click advancement to the next logical stage.
   - **Autonomous Auto-Pilot Mode**: One-click end-to-end pipeline execution from initial natural language prompt to deployed container, automatically pausing when human intervention or quality gate decisions are required.
3. A **Persistent Studio Stepper**: A global lifecycle header visible across all Studio views, showing real-time progress, stage status, gate verdicts, and direct navigation.
4. **Resilient Session Continuity & Artifact Traceability**: Ensuring all outputs from earlier phases seamlessly feed downstream without manual carrying of IDs or fragmented state.

---

## Clarifications

### Session 2026-09-13
- Q: Studio Layout & Navigation Paradigm (FR-003) → A: Barra Superior Global Persistente ("Stepper") + Pestañas de Detalle. Se conserva el acceso a las 7 pestañas de inspección especializada y se añade una barra de cabecera fija con el flujo completo de 7 fases, porcentaje de avance, estado por etapa y botones de navegación rápida.
- Q: Execution Modes & Flow (FR-005, FR-007) → A: Dos modos de operación de primer nivel explícitamente ofrecidos:
  1. **"🚀 Ejecutar Flujo Completo (Auto-Pilot)"**: Ejecución 100% desatendida y secuencial de extremo a extremo, pausándose de forma preventiva únicamente ante violaciones constitucionales (Quality Gate `BLOCKED` o límite de 3 auto-reparaciones).
  2. **"👣 Modo Paso a Paso (Guided Step-by-Step)"**: Flujo asistido con una barra contextual de "Siguiente Acción" en cada pantalla, permitiendo revisar y ajustar artefactos antes de avanzar.
- Q: Downstream Invalidation on Upstream Edits (FR-009) → A: Alerta visual de "Desactualizado" (`OUTDATED`) con botón de re-sincronización. Si el usuario modifica artefactos de una fase anterior, las fases posteriores no se borran abruptamente; se marcan como desactualizadas y se ofrece un botón para "Re-sincronizar y Regenerar etapas afectadas".
- Q: ¿Debe el usuario poder pausar una ejecución de Auto-Pilot en curso en cualquier momento y continuar de forma interactiva en Modo Paso a Paso? (FR-005) → A: Pausa y conmutación en caliente. El usuario puede pausar en cualquier instante; el pipeline completa el paso actual, pasa el control al usuario en la pestaña activa y permite continuar interactivamente en Modo Paso a Paso o reanudar el Auto-Pilot.
- Q: ¿Cómo debe comportarse la interacción al hacer clic en los pasos del Stepper global superior? (FR-003) → A: Navegación directa a pasos desbloqueados. Cada fase completada o en curso es interactiva y permite saltar directamente a su pestaña correspondiente; las fases futuras permanecen inhabilitadas hasta que se cumplan sus prerrequisitos.
- Q: ¿Qué vista inicial debe presentarse al usuario al abrir o cargar una sesión en el Web Studio? (FR-010) → A: Dashboard de Visión General (Home View). Panel inicial con métricas del microservicio, mapa visual de progreso de las 7 fases y selector prominente entre "🚀 Ejecutar Auto-Pilot" o "👣 Modo Paso a Paso".

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Guided Step-by-Step Lifecycle Wizard & Persistent Stepper (Priority: P1) 🎯 MVP

As a developer using the Microservice Code Studio, I want a clear, coordinated step-by-step workflow with a persistent progress stepper, so that I always understand where I am in the generation lifecycle, what has been completed, and what the immediate next action is.

**Why this priority**: Solves the core user pain point: fragmented navigation, lack of process clarity, and confusion about dependencies between phases. Delivers immediate structural value with zero ambiguity.

**Independent Test**: Can be tested independently by launching the Web Studio, initiating a new microservice session, and verifying that:
1. The global stepper clearly shows the 7 lifecycle phases (`Requisitos` ➔ `Historias` ➔ `Arquitectura` ➔ `Persistencia` ➔ `Código & Tests` ➔ `Seguridad & Calidad` ➔ `DevOps & Despliegue`).
2. Each step displays its status (`PENDING`, `IN_PROGRESS`, `COMPLETED`, `BLOCKED`, `WARNING`).
3. Each phase has a prominent "Siguiente Paso" button that automatically validates prerequisites, saves state, and navigates to the next phase.

**Acceptance Scenarios**:

1. **Given** a new or existing session, **When** the user views any tab in the Web Studio, **Then** a persistent global lifecycle stepper is visible at the top showing current phase, overall completion percentage, and active session identity.
2. **Given** a user completes Phase 2 (User Stories generated), **When** they click "Avanzar a Arquitectura", **Then** the coordinator marks Phase 2 as `COMPLETED`, unlocks Phase 3, passes the session context forward, and selects Tab 3 automatically.
3. **Given** a user attempts to skip directly to Phase 5 (Code Generation) without completing Phase 3 (Architecture), **When** they attempt to generate code, **Then** the coordinator prevents the action with an informative banner explaining that an architectural blueprint is required first.

---

### User Story 2 - One-Click Autonomous Auto-Pilot Pipeline (Priority: P1)

As a busy developer or technical lead, I want to trigger a single "Ejecutar Flujo Completo (Auto-Pilot)" action from a natural language requirement, so that the entire microservice is synthesized, tested, audited, and containerized automatically without requiring manual clicks between phases.

**Why this priority**: Maximum development efficiency. Enables end-to-end automation for standard microservice synthesis while respecting constitutional quality gates.

**Independent Test**: Can be tested independently by invoking the pipeline endpoint `POST /api/v1/orchestrator/pipeline/run` with a valid session prompt, and verifying that the pipeline sequentially runs all stages, emits progress events, and halts cleanly upon completion or when a quality gate requires intervention.

**Acceptance Scenarios**:

1. **Given** a validated specification, **When** the user clicks "🚀 Ejecutar Flujo Completo (Auto-Pilot)", **Then** the coordinator runs the full sequence in the background: Stories ➔ Architecture ➔ SQL ➔ Code/Tests ➔ Security Audit ➔ DevOps Generation.
2. **Given** an autonomous pipeline run encountering a `BLOCKED` Quality Gate (Principle V / VI violation), **When** the security scanner detects critical flaws, **Then** the auto-pilot pipeline pauses gracefully, flags the phase as `BLOCKED`, and directs the user to the Security Remediation view.
3. **Given** an autonomous pipeline run where self-repair hits the 3-attempt limit, **When** automated fixes fail, **Then** the pipeline pauses in `MANUAL_INTERVENTION_REQUIRED` state and preserves all diagnostics and logs for developer inspection.

---

### User Story 3 - Centralized Session State Continuity & Traceability (Priority: P2)

As a developer navigating between phases, I want all artifacts, database choices, security verdicts, and container settings to be consistently preserved and synchronized across all views, so that I never lose work, have to re-enter parameters, or suffer state desynchronization.

**Why this priority**: Eliminates state drift, broken references, and inconsistent session states across tabs and API calls.

**Independent Test**: Can be tested independently by selecting a PostgreSQL database in Phase 4, verifying that Phase 5 tests use PostgreSQL compatibility, Phase 6 scans detect PostgreSQL dependencies, and Phase 7 compose files automatically generate PostgreSQL 16 containers with `schema.sql` mounts.

**Acceptance Scenarios**:

1. **Given** any phase update, **When** artifacts are generated or modified, **Then** the coordinator updates the unified session record in SQLite and broadcasts state changes to the UI.
2. **Given** a user refreshes their browser or returns to an existing session, **When** the studio loads, **Then** the exact phase progress, completed steps, generated artifacts, and active logs are restored immediately.

---

### User Story 4 - Iterative Rollback & Modification Management (Priority: P2)

As a developer who wants to adjust earlier design decisions, I want to be able to navigate back to an earlier phase to tweak requirements or data models, with clear visibility of which downstream artifacts will need re-synchronization.

**Why this priority**: Real-world software engineering is iterative. Developers frequently refine requirements after seeing generated models or architectural diagrams.

**Independent Test**: Can be tested independently by changing a requirement in Phase 2 after Phase 4 is completed, and verifying that downstream phases are flagged with a "Re-sincronización requerida" warning without abruptly deleting historical work.

**Acceptance Scenarios**:

1. **Given** a session with completed downstream phases, **When** the user modifies an upstream phase (e.g. architecture), **Then** downstream phases transition to `OUTDATED` status with a clear option: "Re-ejecutar etapas posteriores".
2. **Given** outdated downstream phases, **When** the user triggers re-execution, **Then** the coordinator regenerates only the affected downstream phases sequentially.

---

## Edge Cases

- **Browser Disconnection / Page Refresh**: When a user closes or refreshes the browser during an active Auto-Pilot run, the background pipeline continues executing reliably on the server, and the UI re-attaches to the live event stream upon reload.
- **Docker Daemon Inactivity during Auto-Pilot**: If Auto-Pilot reaches the final deployment stage but the local Docker daemon is not running, the pipeline does not fail with an error; it completes in `EXPORT_READY` mode, notifying the user and offering the downloaded ZIP package.
- **Concurrent Session Requests**: The coordinator locks session operations per session ID to prevent race conditions or conflicting parallel generation steps.
- **Partial Pipeline Failure**: If a specific intermediate step fails (e.g. Maven compilation error), the pipeline halts at that exact step, leaving all previous completed stages intact and accessible.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a centralized **Lifecycle Coordinator Engine** (`backend/app/services/lifecycle_service.py`) that manages the complete lifecycle state machine: `INITIAL` ➔ `REQUIREMENTS` ➔ `STORIES` ➔ `ARCHITECTURE` ➔ `DATA_MODEL` ➔ `CODE_TESTS` ➔ `SECURITY_AUDIT` ➔ `DEVOPS_DEPLOY`.
- **FR-002**: System MUST enforce prerequisite transition guards before allowing entry to any phase (e.g., cannot synthesize code without an approved architectural blueprint; cannot deploy if the Quality Gate is `BLOCKED`).
- **FR-003**: System MUST provide a persistent **Global Lifecycle Stepper** in the Web Studio (`frontend/views/lifecycle_stepper.py`) rendered at the top of every view, displaying current phase, stage status, completion percentage, and active session ID. Each unlocked or completed phase in the Stepper MUST be interactive, allowing one-click direct navigation to its corresponding tab.
- **FR-004**: System MUST provide a contextual **Next Step Action Bar** ("Barra de Siguiente Acción") on every screen indicating:
  - Summary of what was accomplished in the current step.
  - Recommended next action with a single-click button.
  - Any blocking issues or missing prerequisites.
- **FR-005**: System MUST implement a unified **Autonomous Auto-Pilot Pipeline Endpoint** (`POST /api/v1/orchestrator/pipeline/run`) that sequentially triggers all lifecycle steps in the background while broadcasting real-time Server-Sent Events (`GET /api/v1/orchestrator/pipeline/{session_id}/events`).
- **FR-006**: The Auto-Pilot pipeline MUST automatically pause execution and transition to `AWAITING_INTERVENTION` when:
  - Self-repair reaches the constitutional 3-attempt limit (Principle V).
  - Security quality gate verdict is `BLOCKED` due to critical/high vulnerabilities (Principle VI).
- **FR-007**: System MUST provide an interactive **Step-by-Step Guided Mode** allowing users to review, edit, and approve artifacts at each phase before advancing.
- **FR-008**: System MUST persist all lifecycle state and phase completion metrics in SQLite (`GenerationSessionDB`) to guarantee full state recovery across server restarts and browser refreshes.
- **FR-009**: System MUST support **Upstream Rollback & Change Detection**: when an earlier phase artifact is modified, all dependent downstream phases are flagged as `OUTDATED`, and a "Sincronizar Cambios" action is offered.
- **FR-010**: System MUST provide a **Project Overview Dashboard** (`frontend/views/overview_view.py`) acting as the default home view for any session, summarizing architecture, data entities, test results, security health, and deployment status in a single pane of glass.
- **FR-011**: System MUST provide REST API endpoints under `/api/v1/orchestrator`:
  - `GET /api/v1/orchestrator/sessions/{session_id}/lifecycle`: Returns full lifecycle status, phase states, and next recommended action.
  - `POST /api/v1/orchestrator/sessions/{session_id}/transition`: Validates and transitions to a specified phase.
  - `POST /api/v1/orchestrator/pipeline/run`: Initiates background Auto-Pilot pipeline execution.
  - `POST /api/v1/orchestrator/pipeline/{session_id}/pause`: Pauses active pipeline execution.
  - `POST /api/v1/orchestrator/pipeline/{session_id}/resume`: Resumes paused pipeline execution after manual intervention.
  - `GET /api/v1/orchestrator/pipeline/{session_id}/events`: Streams pipeline progress events via SSE.
- **FR-012**: System MUST ensure strict compliance with Constitution Principle IV (offline determinism) and Principle VI (zero hardcoded secrets).
- **FR-013**: System MUST automatically populate downstream forms and defaults using data from upstream artifacts (e.g. database choice from Phase 4 used in Phase 7 Compose generator without user re-entry).
- **FR-014**: System MUST provide a "One-Click Complete Bundle Export" downloading all generated artifacts (specs, stories, architecture blueprints, Java code, tests, Dockerfiles, CI/CD pipelines, Kubernetes manifests) in a clean ZIP archive.

---

### Key Entities

- **LifecyclePhase**: Enumeration of all phases (`INITIAL`, `REQUIREMENTS`, `STORIES`, `ARCHITECTURE`, `DATA_MODEL`, `CODE_TESTS`, `SECURITY_AUDIT`, `DEVOPS_DEPLOY`, `COMPLETED`).
- **PhaseStatus**: Status for each individual phase (`NOT_STARTED`, `IN_PROGRESS`, `COMPLETED`, `OUTDATED`, `BLOCKED`, `SKIPPED`).
- **LifecycleState**: Overall session progress representation (currentPhase, completedPhases: List[LifecyclePhase], phaseStatuses: Dict[LifecyclePhase, PhaseStatus], completionPercentage: float, canAdvance: bool, nextAction: str, blockedReason: Optional[str]).
- **PipelineRunRequest**: Configuration for autonomous pipeline execution (sessionId, targetPhase: LifecyclePhase, stopOnGate: bool, autoDeploy: bool).
- **PipelineProgressEvent**: Real-time event emitted during Auto-Pilot execution (timestamp, phase: LifecyclePhase, stepName: str, progressPercent: float, message: str, status: PhaseStatus).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can navigate from initial prompt to a running, tested, and audited microservice container in under 5 minutes using Auto-Pilot mode.
- **SC-002**: 100% of phase transitions enforce prerequisite validation, preventing invalid states (e.g. deploying without security audit).
- **SC-003**: 0% loss of session state upon browser refresh or tab switching; full lifecycle state is restored within 300ms.
- **SC-004**: Users report reduced cognitive load and zero confusion regarding the next required action, with the Next Step Action Bar providing immediate guidance at all times.
- **SC-005**: 100% of pipeline pauses due to Quality Gate or Self-Repair limits provide a direct, one-click link to the specific remediation screen.
- **SC-006**: The entire platform operates in full compliance with Platform Constitution Principles I through VI.

---

## Assumptions

- **Existing Capabilities**: Features 001 through 007 provide the underlying generative and auditing engines; this feature orchestrates them into a unified, seamless flow.
- **Session DB**: The existing SQLite database (`GenerationSessionDB`) will be extended to store structured lifecycle state.
- **Streamlit Layout**: The UI will retain deep-dive access to individual tabs while embedding the global lifecycle stepper at the header of the application.

