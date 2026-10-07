# Implementation Plan: Microservice Code Studio Web Application

**Branch**: `001-microservice-code-studio` | **Date**: 2026-09-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-microservice-code-studio/spec.md`

## Summary

The Microservice Code Studio is an enterprise fullstack web platform that ingests pre-defined microservice specifications (via Spec Kit Markdown file upload or REST API JSON payload) and coordinates autonomous code synthesis compliant with Constitution v1.1.0. 

The studio platform is implemented as a decoupled system:
- **Backend (FastAPI on port 8000)**: Houses the LangGraph orchestration state machine, asynchronous FIFO queue, Docker sandbox executor for hermetic offline compilation (`mvn test -o`), and Server-Sent Events (SSE) streaming.
- **Frontend (Streamlit on port 8501)**: Provides an interactive, developer-friendly web UI for specification upload, live progress monitoring, syntax-highlighted code exploration, and ZIP/Git export.
- **Target Deliverable**: Produces modular, audit-ready, enterprise-grade Java 21 LTS / Spring Boot 3.x REST microservices with 100% Mockito unit test coverage.

---

## Technical Context

**Platform Language & Runtime**: Python 3.11+ (Studio Backend & UI)
**Target Generated Code**: Java 21 LTS / Spring Boot 3.3.x (Corporate Microservices)

**Primary Dependencies**:
- *Backend Engine*: FastAPI 0.111+, Uvicorn, LangGraph 0.1+, LangChain Core, Pydantic v2, `sse-starlette`, `docker` (Docker SDK for Python), `GitPython`.
- *Frontend UI*: Streamlit 1.36+, `requests`, `sseclient-py`.
- *Target Microservice Stack*: Spring Boot 3.3.x (Spring Web, Spring Data JPA, Spring Validation), Maven 3.9+, H2 in-memory Database (`MODE=PostgreSQL`), JUnit 5 (Jupiter), Mockito, AssertJ, Lombok (restricted).

**Storage**: SQLite (development/local) or PostgreSQL (production) via SQLAlchemy for studio session metadata; in-memory `asyncio.Queue` for concurrency control.

**Testing Frameworks**: 
- Studio Platform: `pytest`, `pytest-asyncio`, `pytest-mock`.
- Generated Microservices: JUnit 5 (Jupiter), Mockito, AssertJ.

**Target Platform**: Linux Container Sandbox (Docker with `--network none`) & Modern Web Browsers.

**Project Type**: Web Application (FastAPI REST/SSE Service + Streamlit Interactive Studio).

**Performance Goals**:
- Ingestion and schema pre-validation < 5 seconds.
- SSE event streaming latency < 1 second.
- Support up to 2 concurrent sandbox builds with FIFO queuing for overflow.

**Constraints**:
- Strictly offline hermetic compilation (`mvn test -o`) with pre-cached Maven artifacts.
- Bounded 3-iteration self-repair loop analyzing only Maven stack traces.
- Zero persisted secrets: Git tokens held only in ephemeral memory during push.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Constitutional Principle | Requirement | Plan Compliance Status | Verification Mechanism |
|---|---|:---:|---|
| **I. Arquitectura en Capas Estricta** | `controller` -> `service` -> `repository` -> `model` en microservicios generados. | **PASS** | El nodo sintetizador de LangGraph genera paquetes separados y prohíbe lógica en controllers. |
| **II. Contratos Inmutables y Validación** | DTOs como Java Records nativos con validación temprana de Jakarta. | **PASS** | Plantillas de síntesis generan Java Records inmutables con `@NotNull`, `@NotBlank`, `@Positive`. |
| **III. Manejo Centralizado de Excepciones** | `@RestControllerAdvice` global con `ProblemDetails` / `ApiErrorRecord`. Clean Code. | **PASS** | Generación mandatoria de `GlobalExceptionHandler` con formato estándar de error y timestamp. |
| **IV. Determinismo Offline-First** | `mvn test -o` en contenedor Docker sin red (`--network none`) y dependencias cacheadas. | **PASS** | `DockerSandboxService` ejecuta contenedores con flag `--network none` y `.m2` montado en solo lectura. |
| **V. Quality Gates y Auto-Reparación** | 100% tests aprobados. Cobertura Mockito. Máximo 3 reintentos de auto-corrección; bloqueo al 3er fallo. | **PASS** | `SelfRepairService` limita el contador a 3 intentos analizando stack traces; transiciona a `BLOCKED` al 3er fallo. |
| **VI. Seguridad de Secretos y LangGraph** | LangGraph en plano de control externo. Cero secretos en repo/disco. Sin llamadas LLM en tests. | **PASS** | LangGraph reside en FastAPI (Python); tokens Git efímeros en memoria; microservicio 100% puro en Java. |

---

## Project Structure

### Documentation (this feature)

```text
specs/001-microservice-code-studio/
├── spec.md              # Feature specification & clarifications
├── plan.md              # Implementation plan (this file)
├── research.md          # Technical decisions & research
├── data-model.md        # Entities, validation rules, state machine
├── quickstart.md        # Runnable end-to-end validation scenarios
├── contracts/
│   ├── ingestion-api.yaml # OpenAPI 3.0 REST specification (FastAPI)
│   └── sse-events.md      # Server-Sent Events stream specification
├── checklists/
│   ├── requirements.md  # Built-in spec quality checklist
│   └── review.md        # Custom QA & architecture review checklist
└── tasks.md             # Implementation tasks (generated in Phase 2)
```

### Source Code Structure

```text
backend/                                # FastAPI + LangGraph Engine
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── main.py                         # FastAPI app, CORS, router mounting
│   ├── config.py                       # Environment settings & constants
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes_spec.py              # POST /specifications/upload, POST /specifications
│   │   ├── routes_session.py           # POST /sessions, GET /sessions/{id}, GET /stream
│   │   ├── routes_artifact.py          # GET /artifacts, GET /content, GET /export
│   │   └── routes_publish.py           # POST /publish (Git feature branch push)
│   ├── orchestrator/                   # LangGraph Autonomous Agent
│   │   ├── __init__.py
│   │   ├── graph.py                    # StateGraph definition & workflow transitions
│   │   ├── state.py                    # GenerationAgentState schema
│   │   ├── nodes/
│   │   │   ├── validator_node.py       # Validates blueprint & acceptance criteria
│   │   │   ├── scaffolder_node.py      # Creates pom.xml, directories, config
│   │   │   ├── domain_node.py          # Generates JPA entities & Record DTOs
│   │   │   ├── service_node.py         # Generates Services & Repositories
│   │   │   ├── controller_node.py      # Generates Controllers & @RestControllerAdvice
│   │   │   └── test_node.py            # Generates Mockito unit tests
│   │   └── repair.py                   # Maven stack trace parser & 3-attempt loop
│   ├── sandbox/                        # Docker Execution Sandbox
│   │   ├── __init__.py
│   │   └── docker_runner.py            # docker run --network none ... mvn test -o
│   ├── models/                         # Pydantic Schemas & DB Models
│   │   ├── __init__.py
│   │   ├── blueprint.py                # Architecture & User Story schemas
│   │   ├── session.py                  # GenerationSession DB model
│   │   └── artifact.py                 # GeneratedArtifact schema
│   └── services/                       # Business Services
│       ├── __init__.py
│       ├── spec_service.py             # Markdown parser & JSON validator
│       ├── queue_service.py            # FIFO Concurrency Queue manager
│       └── git_service.py              # In-memory ephemeral Git publisher
└── tests/
    ├── test_routes_spec.py
    ├── test_routes_session.py
    ├── test_repair_parser.py
    └── test_docker_runner.py

frontend/                               # Streamlit UI
├── requirements.txt
├── app.py                              # Streamlit main entrypoint & sidebar
└── views/
    ├── __init__.py
    ├── ingestion_view.py               # File uploader for spec.md & JSON editor
    ├── monitor_view.py                 # Live SSE progress bar, terminal & status
    ├── explorer_view.py                # File tree selector & st.code viewer
    └── export_view.py                  # ZIP download button & Git push modal
```

**Structure Decision**: Decoupled Python architecture using FastAPI as the headless orchestrator (accessible by humans and external specs) and Streamlit as the developer studio UI.

---

## Complexity Tracking

> **Status**: No constitutional violations or unwarranted complexity. All principles adhered to natively.

| Aspect | Justification |
|---|---|
| FastAPI + Streamlit Decoupling | Required so that the sister specification module can invoke code generation via REST API, while human users interact with an intuitive UI. |
| In-Memory Async Queue | Guarantees that at most 2 Docker sandboxes run concurrently, protecting host resources from CPU/memory exhaustion. |
| Ephemeral Secret Memory | Guarantees compliance with Constitution Principle VI by holding Git tokens only in local execution scope during the push. |
