# Implementation Plan: Natural Language Requirements to User Stories & Acceptance Criteria Transformation

**Branch**: `002-requirements-to-stories` | **Date**: 2026-09-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-requirements-to-stories/spec.md`

---

## Summary

This feature extends the **Microservice Code Studio** with an intelligent requirements authoring wizard embedded as the initial tab (`📝 0. Redacción & Asistente de Requisitos`) in the Streamlit frontend. It enables business analysts, developers, and product owners to enter free-form natural language requirements and automatically synthesize:
1. Canonical **User Stories** (`As a [role], I want [action], so that [benefit]`) prioritized by importance (P1, P2, P3).
2. Comprehensive **Acceptance Scenarios** formatted strictly in Given/When/Then (at least 2 per story: happy path + validation/error).
3. Inferred **Domain Entities** with typed attributes and designated primary keys.
4. An **Interactive Refinement Loop** (direct field edits + natural language re-prompting) and **Direct Pipeline Handoff** into the existing microservice code generator.

---

## Technical Context

**Platform Language & Runtime**: Python 3.12+ (FastAPI Backend & Streamlit Frontend)  
**AI Orchestration**: LangChain / OpenAI-compatible Chat Models with structured Pydantic output  
**Primary Dependencies**:
- *Backend*: `fastapi>=0.111.0`, `pydantic>=2.7.0`, `langchain-openai>=0.1.0`, `langchain-core>=0.2.0`
- *Frontend*: `streamlit>=1.36.0`, `requests>=2.31.0`

**Storage**:
- In-memory session state in Streamlit (`st.session_state`) for draft manipulation.
- FastAPI in-memory blueprint store (`SPECIFICATIONS_STORE` in `spec_service.py`) and SQLite `GenerationSessionDB` for handoff.

**Testing Framework**: `pytest`, `pytest-mock`, `httpx`

**Target Platform**: Web browsers (port 8501) and internal REST API (port 8000).

**Performance Goals**:
- Initial requirements decomposition < 15 seconds.
- Refinement prompt delta updates < 10 seconds.

**Constraints & Governance**:
- **Constitution Principle VI**: Ephemeral API key handling in memory; zero hardcoded or persisted credentials.
- **Constitution Principle II & V**: All synthesized stories must mandate Record DTOs and include happy path and negative error scenarios.

---

## Constitution Check

*GATE: Post-design evaluation against Constitution v1.1.0.*

| Constitutional Principle | Requirement | Plan Compliance Status | Verification Mechanism |
|---|---|:---:|---|
| **I. Arquitectura en Capas Estricta** | Entidades extraídas deben respetar separación de capas. | **PASS** | `DomainEntity` mappings respetan `model/entity` y DTOs separados. |
| **II. Contratos Inmutables y Validación** | DTOs como Java Records con Jakarta validation. | **PASS** | Las historias generadas exigen DTOs inmutables y validaciones tempranas. |
| **III. Manejo Centralizado de Excepciones** | `@RestControllerAdvice` uniforme. | **PASS** | Los escenarios de error (When/Then) corresponden con respuestas de error estandarizadas. |
| **IV. Determinismo Offline-First** | Especificaciones listas para compilación determinista. | **PASS** | El blueprint resultante alimenta directamente el motor hermético de Feature 001. |
| **V. Quality Gates y Cobertura Exhaustiva** | Al menos 2 escenarios por historia (éxito + error). | **PASS** | El prompt de LangChain exige `>= 2` escenarios BDD por historia. |
| **VI. Seguridad de Secretos y Frontera de IA** | Cero persistencia de claves; claves efímeras en memoria. | **PASS** | La API key viaja por header `X-LLM-API-Key` o payload en memoria, jamás se guarda en disco/DB. |

---

## Project Structure

### Documentation (this feature)

```text
specs/002-requirements-to-stories/
├── spec.md              # Feature specification & clarifications
├── plan.md              # Implementation plan (this file)
├── research.md          # Phase 0 technical decisions
├── data-model.md        # Entities, schemas, sequence diagram
├── quickstart.md        # Runnable end-to-end validation scenarios
├── contracts/
│   └── requirements-api.yaml # OpenAPI 3.0 specification
└── checklists/
    └── requirements.md  # Quality verification checklist
```

### Source Code Touchpoints

```text
backend/
├── app/
│   ├── main.py                         # Mount requirements router (/api/v1/requirements)
│   ├── api/
│   │   └── routes_requirements.py      # POST /transform, POST /refine
│   ├── models/
│   │   └── requirements.py             # Request & Response schemas (SpecificationDraft)
│   └── services/
│       └── requirements_service.py     # Prompt engineering & Pydantic structured output
└── tests/
    ├── test_requirements_service.py    # Unit tests for prompt generation & fallback
    └── test_routes_requirements.py     # Contract tests for /transform & /refine

frontend/
├── app.py                              # Register Tab 0 ("📝 0. Redacción & Asistente de Requisitos")
└── views/
    └── requirements_view.py            # Streamlit interactive authoring & refinement UI
```
