# Tasks: Microservice Code Studio Web Application

**Feature**: `001-microservice-code-studio`
**Input**: Design artifacts from `specs/001-microservice-code-studio/` (`spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`)
**Constitution**: `.specify/memory/constitution.md` (v1.1.0)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic workspace structure

- [X] T001 Create project directory structure (`backend/app`, `backend/tests`, `frontend/views`, `frontend/tests`) per implementation plan in `plan.md`
- [X] T002 [P] Initialize backend Python dependencies in `backend/requirements.txt` (FastAPI, Uvicorn, LangGraph, LangChain, Pydantic v2, sse-starlette, docker, GitPython, pytest)
- [X] T003 [P] Initialize frontend Python dependencies in `frontend/requirements.txt` (Streamlit, requests, sseclient-py)
- [X] T004 [P] Configure environment settings, queue concurrency limits (max 2), and logging in `backend/app/config.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure and models that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Implement SQLite/PostgreSQL database engine and session model in `backend/app/models/session.py` (`GenerationSession` with status enum: `QUEUED`, `RUNNING`, `COMPLETED`, `BLOCKED`, `CANCELLED`)
- [X] T006 [P] Implement Pydantic v2 blueprint schemas in `backend/app/models/blueprint.py` (`ArchitectureBlueprint`, `DomainEntity`, `EntityAttribute`, `UserStoryRecord`, `AcceptanceScenarioRecord`)
- [X] T007 [P] Implement artifact and verification metrics schemas in `backend/app/models/artifact.py` (`GeneratedArtifactRecord`, `VerificationMetricRecord`)
- [X] T008 Implement in-memory FIFO queue and concurrency manager (max 2 concurrent generations) in `backend/app/services/queue_service.py`
- [X] T009 Setup main FastAPI application with CORS, router mounts, and centralized error handlers in `backend/app/main.py`
- [X] T010 [P] Setup Streamlit main entrypoint, page layout, and navigation tabs in `frontend/app.py`

**Checkpoint**: Foundation ready — user story implementation can now begin in priority order.

---

## Phase 3: User Story 1 - Ingestion and Pre-Generation Validation of Service Specifications (Priority: P1) 🎯 MVP

**Goal**: Ingest pre-defined microservice specifications via either Markdown file upload (`spec.md`) or REST API JSON payload, validate completeness (entities, user stories with Given/When/Then criteria), and return parsed summary.

**Independent Test**: Can be fully tested by submitting a valid `spec.md` or JSON blueprint to `POST /api/v1/specifications/upload` or `POST /api/v1/specifications` and confirming HTTP 201 Created with parsed entities and validation status.

### Tests for User Story 1
- [X] T011 [P] [US1] Unit test for specification Markdown parser and JSON validator in `backend/tests/test_spec_service.py`
- [X] T012 [P] [US1] Contract test for specification ingestion endpoints in `backend/tests/test_routes_spec.py`

### Implementation for User Story 1
- [X] T013 [US1] Implement Spec Kit Markdown parser and structural validator in `backend/app/services/spec_service.py`
- [X] T014 [US1] Implement REST endpoints `POST /api/v1/specifications/upload` and `POST /api/v1/specifications` in `backend/app/api/routes_spec.py`
- [X] T015 [US1] Implement Streamlit file upload (`st.file_uploader`) and JSON editor view in `frontend/views/ingestion_view.py`
- [X] T016 [US1] Connect `frontend/app.py` to render `ingestion_view.py` and display live schema validation feedback

**Checkpoint**: User Story 1 is fully functional and independently testable as the MVP input stage.

---

## Phase 4: User Story 2 - Autonomous Code Generation and Live Progress Monitoring (Priority: P1)

**Goal**: Coordinate LangGraph multi-stage code synthesis compliant with Constitution v1.1.0, run hermetic `mvn test -o` in Docker sandbox (`--network none`), enforce 3-iteration self-repair loop, and stream progress over SSE.

**Independent Test**: Trigger a generation session via `POST /api/v1/sessions`, connect to `GET /api/v1/sessions/{id}/stream`, and observe real-time lifecycle phase transitions, Maven build logs, and completion/blocked events.

### Tests for User Story 2
- [X] T017 [P] [US2] Unit test for Maven stack trace error parser and retry logic in `backend/tests/test_repair_parser.py`
- [X] T018 [P] [US2] Unit test for Docker sandbox executor in `backend/tests/test_docker_runner.py`

### Implementation for User Story 2
- [X] T019 [P] [US2] Implement Docker sandbox executor running `mvn test -o` with `--network none` mounting read-only `.m2` in `backend/app/sandbox/docker_runner.py`
- [X] T020 [P] [US2] Implement Maven stack trace parser and 3-attempt bounded auto-repair logic in `backend/app/orchestrator/repair.py`
- [X] T021 [US2] Implement LangGraph state schema (`GenerationAgentState`) in `backend/app/orchestrator/state.py`
- [X] T022 [US2] Implement LangGraph synthesis nodes (scaffolder, domain entities, record DTOs, layered services, controllers, and Mockito tests) in `backend/app/orchestrator/nodes/`
- [X] T023 [US2] Assemble LangGraph workflow and state transitions with 3-iteration retry loop in `backend/app/orchestrator/graph.py`
- [X] T024 [US2] Implement session management endpoints (`POST /api/v1/sessions`, `GET /api/v1/sessions/{id}`, `GET /api/v1/sessions/{id}/stream`) in `backend/app/api/routes_session.py`
- [X] T025 [US2] Implement Streamlit live progress view with `st.status` and real-time log terminal in `frontend/views/monitor_view.py`
- [X] T026 [US2] Integrate `monitor_view.py` with SSE consumer in `frontend/app.py` displaying queue position and auto-repair badges

**Checkpoint**: User Stories 1 AND 2 are complete. Full autonomous generation, sandbox testing, and live streaming work end-to-end.

---

## Phase 5: User Story 3 - Interactive Code Exploration and Verification Inspection (Priority: P2)

**Goal**: Provide an interactive file tree explorer, syntax-highlighted source code viewer, and verification metrics dashboard.

**Independent Test**: Retrieve generated files via `GET /api/v1/sessions/{id}/artifacts` and render them in the Streamlit file explorer with Java syntax highlighting and unit test verification metrics.

### Tests for User Story 3
- [X] T027 [P] [US3] Unit test for artifact retrieval and file content endpoints in `backend/tests/test_routes_artifact.py`

### Implementation for User Story 3
- [X] T028 [US3] Implement artifact exploration endpoints (`GET /api/v1/sessions/{id}/artifacts` and `GET /api/v1/sessions/{id}/artifacts/content`) in `backend/app/api/routes_artifact.py`
- [X] T029 [US3] Implement Streamlit hierarchical file tree selector and Java syntax viewer using `st.code` in `frontend/views/explorer_view.py`
- [X] T030 [US3] Implement test verification metrics dashboard displaying total tests, pass rates, and duration in `frontend/views/explorer_view.py`
- [X] T031 [US3] Integrate `explorer_view.py` as an inspection tab in `frontend/app.py`

**Checkpoint**: User Stories 1, 2, and 3 are complete. Reviewers can inspect all generated layered components and test reports.

---

## Phase 6: User Story 4 - Project Export and Repository Integration (Priority: P3)

**Goal**: Enable downloading the full project as a standalone ZIP archive and pushing an atomic commit to a dedicated Git feature branch using ephemeral in-memory credentials.

**Independent Test**: Trigger ZIP export via `GET /api/v1/sessions/{id}/export` and test Git branch push via `POST /api/v1/sessions/{id}/publish`.

### Tests for User Story 4
- [X] T032 [P] [US4] Unit test for ZIP project bundler in `backend/tests/test_export_service.py`
- [X] T033 [P] [US4] Unit test for in-memory ephemeral Git publisher in `backend/tests/test_git_service.py`

### Implementation for User Story 4
- [X] T034 [US4] Implement project packaging service creating clean standalone ZIP archives in `backend/app/services/export_service.py`
- [X] T035 [US4] Implement Git publishing service with ephemeral in-memory token handling in `backend/app/services/git_service.py`
- [X] T036 [US4] Implement export and publish endpoints (`GET /api/v1/sessions/{id}/export` and `POST /api/v1/sessions/{id}/publish`) in `backend/app/api/routes_publish.py`
- [X] T037 [US4] Implement Streamlit download button (`st.download_button`) and Git publication modal in `frontend/views/export_view.py`
- [X] T038 [US4] Integrate `export_view.py` into `frontend/app.py`

**Checkpoint**: All 4 user stories complete. End-to-end delivery pipeline verified.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Cross-cutting improvements, healthchecks, and validation across all user stories

- [X] T039 [P] Add end-to-end integration test running quickstart Scenario 1 and Scenario 2 in `backend/tests/test_e2e_flow.py`
- [X] T040 [P] Add Docker base image verification script confirming `maven:3.9-eclipse-temurin-21` cache in `backend/app/sandbox/verify_cache.py`
- [X] T041 Add system healthcheck endpoint `GET /healthz` in `backend/app/main.py`
- [X] T042 Update root execution documentation and quickstart instructions in `README.md`

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Phase 1 completion — BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Phase 2 completion — delivers MVP input stage.
- **User Story 2 (Phase 4)**: Depends on Phase 2 and US1 schemas — delivers core generation engine.
- **User Story 3 (Phase 5)**: Depends on Phase 4 artifacts — delivers inspection UI.
- **User Story 4 (Phase 6)**: Depends on Phase 4 artifacts — delivers packaging and Git push.
- **Polish (Phase 7)**: Depends on completion of all desired user stories.

### User Story Dependencies
- **US1 (P1)**: Independent entry point.
- **US2 (P1)**: Consumes output of US1 (`specId` and parsed blueprint).
- **US3 (P2)**: Consumes output of US2 (`sessionId` and generated artifacts).
- **US4 (P3)**: Consumes output of US2 (`sessionId` and generated project files).

### Parallel Opportunities

- Within **Phase 1**: `T002`, `T003`, and `T004` can execute in parallel.
- Within **Phase 2**: `T006`, `T007`, and `T010` can execute in parallel.
- Within **Phase 3 (US1)**: Tests `T011` and `T012` can execute in parallel.
- Within **Phase 4 (US2)**: Tests `T017` and `T018`, plus implementation tasks `T019` and `T020` can execute in parallel.
- Within **Phase 5 (US3)**: Test `T027` and backend endpoint `T028` can run in parallel with frontend view `T029`.
- Within **Phase 6 (US4)**: Tests `T032` and `T033` can run in parallel.
- Across stories: Once Phase 4 (US2) completes, US3 (Exploration) and US4 (Export) can proceed in parallel.

---

## Parallel Example: User Story 2 (Generation Engine)

```bash
# Launch unit tests and isolated services for User Story 2 in parallel:
Task T017: "Unit test for Maven stack trace error parser in backend/tests/test_repair_parser.py"
Task T018: "Unit test for Docker sandbox executor in backend/tests/test_docker_runner.py"
Task T019: "Implement Docker sandbox executor in backend/app/sandbox/docker_runner.py"
Task T020: "Implement Maven stack trace parser in backend/app/orchestrator/repair.py"
```

---

## Implementation Strategy

### MVP First (Phases 1, 2, and 3)
1. Complete **Phase 1: Setup** (dependencies, configuration).
2. Complete **Phase 2: Foundational** (data models, queue service, app layout).
3. Complete **Phase 3: User Story 1** (specification ingestion and validation).
4. **STOP and VALIDATE**: Verify that `spec.md` and JSON blueprints can be ingested and validated.

### Incremental Delivery
1. **Increment 1 (MVP)**: Specification ingestion and validation working.
2. **Increment 2**: Core autonomous generation, Docker offline test execution, and SSE streaming (User Story 2).
3. **Increment 3**: Interactive code explorer and verification dashboard in Streamlit (User Story 3).
4. **Increment 4**: ZIP packaging and ephemeral Git feature branch publication (User Story 4).
5. **Increment 5**: End-to-end integration tests and healthchecks (Phase 7).

