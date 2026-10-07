# Research: Unified End-to-End Workflow Orchestration

**Feature**: `008-unified-workflow-orchestration`  
**Date**: 2026-09-13  
**Status**: Completed  

---

## 1. Technical Decisions & Architectural Patterns

### Decision 1: Lifecycle State Machine & Transition Engine
- **Decision**: Implement a pure Python, deterministic finite state machine (FSM) encapsulated within `backend/app/services/lifecycle_service.py`, using Pydantic v2 schemas for domain modeling and SQLite (`GenerationSessionDB`) for persistent state storage.
- **Rationale**:
  - The microservice generation lifecycle consists of 7 discrete, sequential phases with well-defined prerequisites and invariant guards.
  - Using a lightweight, custom state machine avoids heavy external workflow engine dependencies (e.g. Celery, Airflow, Temporal) while maintaining complete predictability, offline execution, and immediate sub-millisecond transition evaluations.
  - The state machine strictly models transitions between phases (`INITIAL` ➔ `REQUIREMENTS` ➔ `STORIES` ➔ `ARCHITECTURE` ➔ `DATA_MODEL` ➔ `CODE_TESTS` ➔ `SECURITY_AUDIT` ➔ `DEVOPS_DEPLOY` ➔ `COMPLETED`).
- **Phase Invariant Guards**:
  - `STORIES` requires `REQUIREMENTS` completed.
  - `ARCHITECTURE` requires `STORIES` completed.
  - `DATA_MODEL` requires `ARCHITECTURE` completed.
  - `CODE_TESTS` requires `DATA_MODEL` completed.
  - `SECURITY_AUDIT` requires `CODE_TESTS` completed.
  - `DEVOPS_DEPLOY` requires `SECURITY_AUDIT` completed AND `QualityGateVerdict.canExport == True`.
- **Alternatives Considered**:
  - *Full LangGraph workflow graph*: Useful for autonomous agent nodes, but overly complex for basic UI stepper navigation, state queries, and manual step-by-step advancement.
  - *Stateless client-side progression*: Relies on browser session state; fails upon refresh, tab closure, or cross-browser resumption.

---

### Decision 2: Autonomous Auto-Pilot Background Execution & Hot-Pausing Engine
- **Decision**: Implement an asynchronous, thread-safe pipeline execution worker in `backend/app/services/pipeline_runner.py` operating via Python standard `threading.Thread`, `threading.Event`, and `queue.Queue`.
- **Rationale**:
  - Generating microservices, running Maven builds, and executing container scans can take 30–90 seconds in total. Running this synchronously inside a FastAPI route would freeze HTTP request handling or cause gateway timeouts.
  - Threading with cooperative pause signals (`_pause_event`, `_stop_event`) allows true hot-pausing: when the user clicks "⏸️ Pausar", the runner completes the active atomic step, sets session state to `PAUSED`, emits an SSE event, and safely relinquishes execution to the user in Guided Step-by-Step mode.
  - Event streaming via Server-Sent Events (`text/event-stream`) provides real-time progress percentages and log updates directly to the Web Studio terminal without polling.
- **Constitutional Safe-Halting**:
  - Auto-Pilot checks `QualityGateVerdict.canExport` after Phase 6: if `BLOCKED`, it transitions to `AWAITING_INTERVENTION` and stops automatically.
  - If self-repair in Phase 5 exhausts the 3-attempt limit, it transitions to `MANUAL_INTERVENTION_REQUIRED` and stops automatically.
- **Alternatives Considered**:
  - *Celery with Redis*: Introduces external broker dependencies violating offline-first, hermetic execution (Principle IV).
  - *Asyncio background tasks*: Harder to interrupt cooperatively during blocking subprocess calls (like `mvn test -o` or `docker compose`).

---

### Decision 3: Persistent Global Stepper & Navigation Header in Streamlit
- **Decision**: Create a dedicated component `frontend/views/lifecycle_stepper.py` rendered at the top of every page in `frontend/app.py`.
- **Rationale**:
  - Eliminates developer confusion regarding "where am I?", "what's next?", and "is my microservice ready?".
  - Renders:
    1. Overall progress bar with dynamic completion percentage.
    2. 7 interactive step badges: ✅ `COMPLETED`, ⏳ `IN_PROGRESS`, 🔒 `LOCKED`, ⚠️ `OUTDATED`, 🛑 `BLOCKED`.
    3. Clicking any unlocked or completed step instantaneously switches to its corresponding tab using Streamlit session state (`st.session_state.active_tab`).
    4. Contextual "Next Action Bar" offering a single, prominent call-to-action button (e.g. "👉 Siguiente: Generar Arquitectura") alongside a "⬅️ Paso Anterior" button.
- **Alternatives Considered**:
  - *Replacing tabs entirely with a full-page Wizard*: Hides deep-dive inspection tools (such as viewing the raw generated Java Records or Dockerfile), frustrating experienced developers who need quick access.

---

### Decision 4: Project Overview Dashboard (Default Home View)
- **Decision**: Implement a centralized landing screen `frontend/views/overview_view.py` ("🏠 0. Resumen del Proyecto") displayed when loading or creating a session.
- **Rationale**:
  - Acts as an executive summary and command center for the microservice project.
  - Displays:
    - **Header Card**: Service name, target framework (Java 21 / Spring Boot 3), database engine, creation timestamp.
    - **Visual Pipeline Stepper**: Interactive high-level view of all 7 phases.
    - **Primary Launch Controls**:
      - `🚀 Ejecutar Flujo Completo (Auto-Pilot)`
      - `👣 Continuar Paso a Paso (Guided Mode)`
    - **Key Milestone Metrics**: User stories count, entities mapped, test suite pass rate, security audit status (PASSED/BLOCKED), deployment URL.
    - **One-Click Export**: `📦 Descargar Bundle Completo (ZIP)`.
- **Alternatives Considered**:
  - *Dropping users straight into Tab 1 (Specification)*: Lacks high-level visibility for existing projects and makes Auto-Pilot initiation less prominent.

---

### Decision 5: Non-Destructive Downstream Invalidation on Upstream Edits
- **Decision**: When an earlier phase is modified (e.g. user updates user stories in Phase 2 after code generation in Phase 5), mark downstream completed phases as `OUTDATED` rather than deleting their files.
- **Rationale**:
  - Prevents disastrous accidental data loss if a user makes an exploratory tweak in an earlier tab.
  - The UI displays an amber warning banner: `"⚠️ Cambios detectados en etapas previas. Las etapas posteriores están desactualizadas."`
  - Provides a single-click action: `"🔄 Re-sincronizar y Regenerar etapas afectadas"`, which sequentially re-executes only the outdated phases.
- **Alternatives Considered**:
  - *Aggressive wipe of downstream files*: Destroys manual code edits or tests made in Phase 5 if someone accidentally touches a requirement.

---

### Decision 6: One-Click Complete Bundle Export
- **Decision**: Provide an endpoint `GET /api/v1/orchestrator/sessions/{session_id}/export-bundle` that packages all workspace artifacts into a structured ZIP file:
  - `/docs`: `spec.md`, user stories, architecture diagrams.
  - `/database`: `schema.sql`, data model docs.
  - `/microservice`: Complete Maven project (`pom.xml`, Java source code, tests).
  - `/security`: SAST scan reports, dependency vulnerability audit.
  - `/devops`: `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `.github/workflows/ci-cd.yml`, `.gitlab-ci.yml`, Kubernetes manifests.
- **Rationale**: Provides developers with an immediately usable enterprise delivery package ready for git commit, remote CI/CD, or deployment into Kubernetes clusters.

