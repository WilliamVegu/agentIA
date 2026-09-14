# Implementation Plan: Automated Architecture & Component Design from User Stories

**Branch**: `003-architecture-component-design` | **Date**: 2026-09-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/003-architecture-component-design/spec.md`

---

## Summary

This feature adds an automated **Architecture & Component Design Engine** into Microservice Code Studio, accessible via a dedicated tab (**`🏗️ 1. Diseño Arquitectónico & Componentes`**) in the Streamlit frontend. It bridges behavioral user stories and acceptance criteria (Feature 002) with autonomous code generation (Feature 001).

The engine analyzes user stories, Given/When/Then criteria, and domain entities to synthesize:
1. A **strict 4-layer Spring Boot 3 architecture** (`controller` ➔ `service` ➔ `repository` ➔ `model`/`entity`) plus cross-cutting infrastructure (`@RestControllerAdvice`).
2. A **REST API Endpoint Catalog** with derived request/response Java Record DTOs and status codes.
3. A **real-time directional Mermaid flowchart** visualizing components, layers, and dependency flows.
4. An **interactive human-in-the-loop review and refinement loop** (in-place edits and natural language re-prompting).
5. **Dual artifact export** (`openapi.yaml` and `architecture.md`) and direct 1-click pipeline handoff to the code generation engine.

---

## Technical Context

**Platform Language & Runtime**: Python 3.12+ (FastAPI Backend & Streamlit Frontend)  
**AI Orchestration**: LangChain / OpenAI-compatible Chat Models with structured Pydantic output  
**Primary Dependencies**:
- *Backend*: `fastapi>=0.111.0`, `pydantic>=2.7.0`, `langchain-openai>=0.1.0`, `pyyaml>=6.0.0`
- *Frontend*: `streamlit>=1.36.0`, `requests>=2.31.0`

**Storage**:
- In-memory session state in Streamlit (`st.session_state`) for draft manipulation and tab transition.
- FastAPI in-memory blueprint store (`SPECIFICATIONS_STORE` in `spec_service.py`) for handoff.

**Testing Framework**: `pytest`, `httpx`  
**Target Platform**: Web browsers (port 8501) and internal REST API (port 8000).  

**Performance Goals**:
- Initial architectural synthesis < 20 seconds.
- Refinement prompt delta updates < 10 seconds.

**Constraints & Governance**:
- **Constitution Principle I**: Strict 4-layer unidirectional architecture (`controller` ➔ `service` ➔ `repository` ➔ `model`). Zero circular dependencies.
- **Constitution Principle II**: DTOs designed strictly as immutable Java Records with Jakarta validation annotations. Zero JPA entity exposure in controllers.
- **Constitution Principle III**: Centralized `@RestControllerAdvice` handling and RFC 7807 problem details synthesized as cross-cutting infrastructure.
- **Constitution Principle IV & VI**: Offline-first testability with deterministic mocks; zero persisted or hardcoded secrets.

---

## Constitution Check

*GATE: Post-design evaluation against Constitution v1.1.0.*

| Constitutional Principle | Requirement | Plan Compliance Status | Verification Mechanism |
|:---|:---|:---:|:---|
| **I. Arquitectura en Capas Estricta** | Capas controller ➔ service ➔ repository ➔ model/entity unidireccionales. | **PASS** | `ComponentDefinition.dependencies` valida estricta unidireccionalidad sin ciclos. |
| **II. Contratos Inmutables y Validación** | DTOs de request/response como Java Records con anotaciones Jakarta. | **PASS** | `ApiEndpointDefinition` especifica `requestDto` y `responseDto` como records inmutables con `@Valid`. |
| **III. Manejo Centralizado de Excepciones** | `@RestControllerAdvice` y respuestas de error RFC 7807 uniformes. | **PASS** | El sintetizador genera automáticamente `GlobalExceptionHandler` y mapea códigos 400/404/500 en la sección de infraestructura. |
| **IV. Determinismo Offline-First** | Modo offline y pruebas sin red externa en sandbox. | **PASS** | Generador mock determinista para pruebas unitarias y sandbox sin llamadas a APIs externas. |
| **V. Quality Gates y Cobertura Exhaustiva** | Mapeo 1:1 de cada historia y criterio BDD a componentes y endpoints. | **PASS** | Cada endpoint y componente registra `mappedStories` y `mappedScenarioId` trazables. |
| **VI. Seguridad de Secretos y Frontera de IA** | Cero secretos persistidos; API keys efímeras en memoria. | **PASS** | Key resuelta mediante header `X-LLM-API-Key` o payload en memoria; 401 si falta. |

---

## Project Structure

### Documentation (this feature)

```text
specs/003-architecture-component-design/
├── spec.md              # Feature specification & clarifications
├── plan.md              # Implementation plan (this file)
├── research.md          # Technical research & decisions
├── data-model.md        # Schemas & sequence diagram
├── quickstart.md        # End-to-end runnable validation scenarios
├── contracts/
│   └── architecture-api.yaml # OpenAPI 3.0 contract for architecture endpoints
└── checklists/
    └── requirements.md  # Quality verification checklist
```

### Source Code Touchpoints

```text
backend/
├── app/
│   ├── main.py                         # Mount architecture router (/api/v1/architecture)
│   ├── api/
│   │   └── routes_architecture.py      # POST /design, POST /refine
│   ├── models/
│   │   └── architecture.py             # Schemas: ComponentDefinition, ApiEndpointDefinition, ArchitectureDesignResponse
│   └── services/
│       └── architecture_service.py     # Prompt engineering, 4-layer synthesis, Mermaid & OpenAPI generator
└── tests/
    ├── test_architecture_service.py    # Unit tests for component synthesis, Mermaid & OpenAPI generation
    └── test_routes_architecture.py     # Contract tests for /design, /refine, and 401 guards

frontend/
├── app.py                              # Register Tab 1 ("🏗️ 1. Diseño Arquitectónico & Componentes")
└── views/
    ├── requirements_view.py            # Add "🏗️ Diseñar Arquitectura" transition button in Tab 0
    └── architecture_view.py            # Streamlit visual architecture canvas, Mermaid viewer, component cards, export buttons
```

---

## Complexity Tracking

*No constitutional violations. Zero unwarranted complexity.*
