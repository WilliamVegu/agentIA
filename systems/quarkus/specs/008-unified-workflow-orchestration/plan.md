# Implementation Plan: End-to-End Unified Workflow Orchestration

**Branch**: `008-unified-workflow-orchestration` | **Date**: 2026-09-13 | **Spec**: [specs/008-unified-workflow-orchestration/spec.md](file:///c:/Users/willi/Downloads/agentIA/specs/008-unified-workflow-orchestration/spec.md)

**Input**: Feature specification from `specs/008-unified-workflow-orchestration/spec.md` ("necesito que todo el proceso este correctamente coordinado, desde principio a fin, que pueda seguir un flujo coherente, eficaz y sencillo...")

---

## Summary

This feature bridges all isolated generation tabs and phases (Specs 001 through 007) into a unified, coherent, and developer-friendly lifecycle experience:
1. **Central Lifecycle State Machine**: In `backend/app/services/lifecycle_service.py`, tracking and enforcing sequential phase transitions (`INITIAL` ➔ `REQUIREMENTS` ➔ `STORIES` ➔ `ARCHITECTURE` ➔ `DATA_MODEL` ➔ `CODE_TESTS` ➔ `SECURITY_AUDIT` ➔ `DEVOPS_DEPLOY` ➔ `COMPLETED`) with invariant prerequisite guards.
2. **Dual Operational Execution Modes**:
   - **One-Click Autonomous Auto-Pilot**: Sequential background pipeline runner (`backend/app/services/pipeline_runner.py`) that generates the complete microservice end-to-end, with real-time SSE progress events and constitutional safe-halting (pausing on `BLOCKED` Quality Gate or 3-attempt self-repair exhaustion).
   - **Guided Step-by-Step Mode**: Interactive step-by-step wizard providing contextual recommendations, validation guards, and a prominent "Siguiente Paso" action bar on each view.
3. **In-Flight Hot-Pausing & Mode Switching**: Allows developers to pause an active Auto-Pilot run in mid-execution, inspect generated code in the relevant tab, make edits, and either proceed step-by-step or resume Auto-Pilot.
4. **Persistent Global Stepper & Navigation Header**: A fixed top navigation bar in Streamlit (`frontend/views/lifecycle_stepper.py`) showing the 7 lifecycle phases, progress percentage, phase status badges, and 1-click jump navigation to any unlocked stage.
5. **Default Project Overview Dashboard**: A centralized landing screen (`frontend/views/overview_view.py`) acting as the home view with project metrics, visual pipeline, and launch controls.
6. **Non-Destructive Downstream Invalidation**: Flags downstream phases as `OUTDATED` when upstream changes occur, preserving code while offering a 1-click re-synchronization action.
7. **One-Click Complete Bundle Export**: Packages documentation, architecture, Java code, tests, SQL scripts, Dockerfile, CI/CD, and Kubernetes manifests into a clean ZIP archive.

---

## Technical Context

**Language/Version**: Python 3.11+ (FastAPI backend, Streamlit frontend); Target Microservices: Java 21 LTS / Spring Boot 3.x.

**Primary Dependencies**:
- Backend: FastAPI, Pydantic v2, Uvicorn, Python standard libraries (`asyncio`, `threading`, `queue`, `zipfile`, `pathlib`).
- Frontend: Streamlit, Requests, SSE client / EventStream.

**Storage**:
- SQLite (`sessions.db` with extended `GenerationSessionDB` schema) storing lifecycle phase states, active execution mode, and completion percentages.
- Workspace directories (`workspaces/{session_id}/`) storing generated assets.

**Testing**: Pytest (`python -m pytest backend/tests -o pythonpath=backend`), verifying lifecycle FSM transitions, prerequisite guards, Auto-Pilot background execution, hot-pausing, SSE event streams, and full bundle ZIP exports.

**Target Platform**: Cross-platform (Windows, Linux, macOS).

**Performance Goals**:
- Lifecycle state resolution: < 50 milliseconds.
- Auto-Pilot initial SSE connection latency: < 300 milliseconds.
- End-to-end autonomous microservice synthesis: < 5 minutes total.
- Full bundle ZIP packaging: < 1.0 second.

**Constraints**:
- Constitution Principle IV: Hermetic offline reproducibility.
- Constitution Principle V: Auto-Pilot MUST halt if self-repair exhausts 3 attempts or if unit tests fail.
- Constitution Principle VI: Zero plaintext secrets; Auto-Pilot MUST halt if Quality Gate is `BLOCKED`.

---

## Constitution Check

*GATE: Verified against `.specify/memory/constitution.md`.*

| Principle | Relevance & Impact on Feature | Status |
|---|---|---|
| **I. Layer Isolation** | Orchestrator coordinates lifecycle stages without altering the 4-layer Java microservice boundaries. | **PASS** |
| **II. Immutable DTOs & Validation** | Orchestrator REST endpoints use strict Pydantic v2 request/response models with field validations. | **PASS** |
| **III. Centralized Error Handling** | FastAPI orchestrator endpoints use centralized exception handling returning RFC 7807 error structures. | **PASS** |
| **IV. Offline Determinism & Sandbox** | Orchestrator pipeline runs entirely offline (`mvn test -o`) with zero external network downloads. | **PASS** |
| **V. Quality Gates & Auto-Repair** | Auto-Pilot halts immediately if tests fail or self-repair hits 3 attempts, transitioning to `AWAITING_INTERVENTION`. | **PASS** |
| **VI. Zero Secrets & Ephemeral Boundary** | Auto-Pilot halts if the security quality gate flags critical/high flaws or secrets (`QualityGateVerdict.canExport == False`). | **PASS** |

**GATES RESULT**: **PASS**. Fully compliant with Platform Constitution.

---

## Project Structure

### Documentation (this feature)

```text
specs/008-unified-workflow-orchestration/
├── spec.md              # Feature specification (/speckit-specify output)
├── plan.md              # Implementation plan (/speckit-plan output)
├── research.md          # Technical decisions: FSM, threading, stepper, overview (/speckit-plan output)
├── data-model.md        # Schemas & sequence diagrams (/speckit-plan output)
├── quickstart.md        # 5 runnable validation scenarios (/speckit-plan output)
├── contracts/           # API specifications (/speckit-plan output)
│   └── orchestrator-api.yaml # OpenAPI 3.0 specification for /api/v1/orchestrator/*
└── checklists/
    └── requirements.md  # 16/16 requirements validation checklist (PASS)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/
│   │   ├── routes_orchestrator.py      # [NEW] Endpoints: /api/v1/orchestrator/sessions/{id}/overview, /lifecycle, /transition, /pipeline/run, /pause, /resume, /events, /export-bundle
│   │   └── ... (existing routers)
│   ├── models/
│   │   ├── orchestrator.py             # [NEW] Pydantic models: LifecyclePhase, PhaseStatus, LifecycleState, PipelineRunRequest, etc.
│   │   ├── session.py                  # [MODIFY] Extend GenerationSessionDB with lifecycle fields
│   │   └── ... (existing models)
│   ├── services/
│   │   ├── lifecycle_service.py        # [NEW] Finite State Machine managing phases, guards, outdated status, and next actions
│   │   ├── pipeline_runner.py          # [NEW] Background thread worker executing Auto-Pilot pipeline with hot-pausing & SSE queue
│   │   ├── export_service.py           # [MODIFY] Add export_full_bundle creating unified delivery ZIP
│   │   └── ... (existing services)
│   └── main.py                         # [MODIFY] Register routes_orchestrator router
└── tests/
    ├── test_lifecycle_service.py       # [NEW] Unit tests for FSM transitions, prerequisite guards, and outdated propagation
    ├── test_pipeline_runner.py         # [NEW] Unit tests for Auto-Pilot execution, hot-pausing, and quality gate halting
    ├── test_routes_orchestrator.py     # [NEW] Contract tests for orchestrator API endpoints
    └── ... (existing 106 passing tests)

frontend/
├── views/
│   ├── lifecycle_stepper.py            # [NEW] Persistent header component with 7-phase stepper, progress bar, and action bar
│   ├── overview_view.py                # [NEW] Default landing dashboard ("🏠 0. Resumen del Proyecto") with mode selectors and metrics
│   └── ... (existing views: tab 1 to 7)
└── app.py                              # [MODIFY] Embed persistent stepper at header and integrate Tab 0 (Overview)
```

---

## Source Code Touchpoints & Implementation Details

1. **`backend/app/models/orchestrator.py` [NEW]**:
   - Defines `LifecyclePhase`, `PhaseStatus`, `PipelineExecutionMode`, `PipelineRunStatus`, `PhaseState`, `LifecycleState`, `PipelineRunRequest`, `PipelineProgressEvent`, `PhaseTransitionRequest`, and `ProjectOverviewSummary`.

2. **`backend/app/services/lifecycle_service.py` [NEW]**:
   - `get_session_lifecycle(session_id: str) -> LifecycleState`: Inspects session artifacts and database records to compute phase statuses and determine next recommended actions.
   - `transition_phase(session_id: str, target_phase: LifecyclePhase, force: bool = False) -> LifecycleState`: Validates prerequisite rules and updates current phase.
   - `mark_downstream_outdated(session_id: str, modified_phase: LifecyclePhase)`: Flags subsequent phases as `OUTDATED`.
   - `get_project_overview(session_id: str) -> ProjectOverviewSummary`: Compiles aggregate project metrics for the Home View.

3. **`backend/app/services/pipeline_runner.py` [NEW]**:
   - `run_pipeline(session_id: str, target_phase: LifecyclePhase, stop_on_gate: bool, auto_deploy: bool)`: Spawns a background thread that sequentially invokes generators (Spec 002 ➔ 003 ➔ 004 ➔ 005 ➔ 006 ➔ 007).
   - `pause_pipeline(session_id: str)`: Signals `_pause_event` to finish the active atomic step, save state as `PAUSED`, and switch mode to `GUIDED_STEP`.
   - `resume_pipeline(session_id: str)`: Resumes paused pipeline.
   - `stream_pipeline_events(session_id: str) -> Generator[str, None, None]`: Emits SSE `PipelineProgressEvent` items.

4. **`backend/app/services/export_service.py` [MODIFY]**:
   - Add `export_full_bundle(session_id: str, workspace_dir: str) -> str`: Packages all generated docs, schemas, code, tests, security audits, Dockerfile, CI/CD, and K8s manifests into a structured ZIP file.

5. **`backend/app/api/routes_orchestrator.py` [NEW]**:
   - REST endpoints matching `contracts/orchestrator-api.yaml`:
     - `GET /api/v1/orchestrator/sessions/{session_id}/overview`
     - `GET /api/v1/orchestrator/sessions/{session_id}/lifecycle`
     - `POST /api/v1/orchestrator/sessions/{session_id}/transition`
     - `POST /api/v1/orchestrator/pipeline/run`
     - `POST /api/v1/orchestrator/pipeline/{session_id}/pause`
     - `POST /api/v1/orchestrator/pipeline/{session_id}/resume`
     - `GET /api/v1/orchestrator/pipeline/{session_id}/events`
     - `GET /api/v1/orchestrator/sessions/{session_id}/export-bundle`

6. **`backend/app/main.py` [MODIFY]**:
   - Register `orchestrator_router` under prefix `/api/v1/orchestrator`.

7. **`frontend/views/lifecycle_stepper.py` [NEW]**:
   - Persistent Stepper Component:
     - Header progress bar with percentage.
     - 7 phase chips with status icons and 1-click navigation.
     - Next Action Bar with "Siguiente Paso" and "Paso Anterior" buttons.

8. **`frontend/views/overview_view.py` [NEW]**:
   - Project Overview Home View ("🏠 0. Resumen del Proyecto"):
     - Metadata card (spec name, framework, DB).
     - Visual lifecycle map.
     - Mode action buttons ("🚀 Ejecutar Flujo Completo (Auto-Pilot)" and "👣 Modo Paso a Paso").
     - Key milestone metrics grid and "📦 Descargar Bundle Completo (ZIP)".

9. **`frontend/app.py` [MODIFY]**:
   - Renders `render_lifecycle_stepper` at the top of the main layout.
   - Adds Tab 0 ("🏠 0. Resumen") as the initial tab in the top navigation tabs.

---

## Verification Plan

### Automated Tests
- Unit tests: `backend/tests/test_lifecycle_service.py` validating state machine transitions, prerequisite invariant checking, and outdated status handling.
- Unit tests: `backend/tests/test_pipeline_runner.py` validating Auto-Pilot sequencing, hot-pausing, and quality gate halting.
- Contract tests: `backend/tests/test_routes_orchestrator.py` validating REST endpoints and SSE streams.
- Full regression suite across all 106 existing tests:
  ```bash
  python -m pytest backend/tests -o pythonpath=backend
  ```

### Manual Verification
- Execute the 5 scenarios from `quickstart.md`:
  1. Guided step-by-step navigation via Stepper.
  2. One-click Auto-Pilot run from prompt to container deployment.
  3. In-flight hot-pausing and switching to guided mode.
  4. Quality gate halting on simulated security violation.
  5. Upstream change re-synchronization.
