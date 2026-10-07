# Implementation Plan: Automated Domain Models & SQL Schema Generation

**Branch**: `004-domain-models-sql` | **Date**: 2026-09-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/004-domain-models-sql/spec.md`

---

## Summary

This feature integrates an automated **Domain Models & SQL Schema Generation Engine** into Microservice Code Studio, accessible via a dedicated tab (**`💾 2. Modelos de Dominio & Esquema SQL`**) in the Streamlit frontend. It bridges architectural components (Feature 003) with database persistence and code generation (Feature 001).

The engine analyzes domain entities, attributes, and user stories to synthesize:
1. **JPA Domain Entity Models** (Java 21 classes with Jakarta Persistence `@Entity`, `@Table`, numeric identity primary keys `Long id`, getters/setters, and audit timestamps `Instant`).
2. **Relational SQL Database Scripts** (`schema.sql` for table DDL, constraints, foreign keys, and indexes; and `data.sql` for Given-based seed DML) compatible with PostgreSQL and H2 in-memory mode.
3. **Live Visual Entity-Relationship Diagramming** (`erDiagram` in Mermaid) with interactive cardinalities (`||--o{`).
4. **Interactive Human-in-the-Loop Review & AI Refinement** (card-based property editing and natural language prompt adjustments).
5. **Dual Artifact Export** (`schema.sql`, `data.sql`, Java entity source files) and direct 1-click pipeline handoff to the autonomous code generator.

---

## Technical Context

**Platform Language & Runtime**: Python 3.12+ (FastAPI Backend & Streamlit Frontend)  
**Target Generated Artifacts**: Java 21 LTS (Spring Boot 3.x Jakarta Persistence Entities) & SQL ANSI/PostgreSQL DDL/DML  
**AI Orchestration**: LangChain / OpenAI Chat Models with structured Pydantic extraction and deterministic offline fallbacks  
**Primary Dependencies**:
- *Backend*: `fastapi>=0.111.0`, `pydantic>=2.7.0`, `langchain-openai>=0.1.0`, `pyyaml>=6.0.0`
- *Frontend*: `streamlit>=1.36.0`, `requests>=2.31.0`

**Storage**:
- In-memory Streamlit session state (`st.session_state.data_model_design`) for interactive visualization.
- FastAPI in-memory specification store (`SPECIFICATIONS_STORE` in `spec_service.py`) for pipeline handoff.

**Testing Framework**: `pytest`, `httpx`  
**Target Platform**: Web browsers (port 8501) and internal REST API (port 8000).  

**Performance Goals**:
- Initial domain model and SQL schema synthesis < 15 seconds.
- Refinement prompt delta updates < 8 seconds.

**Constraints & Governance**:
- **Constitution Principle I**: Strict 4-layer unidirectional architecture (`controller` ➔ `service` ➔ `repository` ➔ `model`). Models encapsulate entity definitions with zero outward dependency on controllers.
- **Constitution Principle II**: DTOs decoupled from entities; entities represent internal database state and never leak unchecked to controllers.
- **Constitution Principle III**: Uniform error responses and Clean Code standards.
- **Constitution Principle IV**: Offline-first testability with deterministic mocks; generated `schema.sql` and `data.sql` execute cleanly in H2 (`MODE=PostgreSQL`) inside the Docker sandbox (`--network none`).
- **Constitution Principle VI**: Cero hardcoded secrets; ephemeral API keys handled in memory via `X-LLM-API-Key`.

---

## Constitution Check

*GATE: Post-design evaluation against Constitution v1.1.0.*

| Constitutional Principle | Requirement | Plan Compliance Status | Verification Mechanism |
|:---|:---|:---:|:---|
| **I. Arquitectura en Capas Estricta** | Entidades de dominio desacopladas en capa `model`. | **PASS** | `DomainEntityDefinition` pertenece a `packageName.model` sin referencias a controladores. |
| **II. Contratos Inmutables y Validación** | DTOs como Records y entidades con validación Jakarta. | **PASS** | Entidades utilizan `@NotNull`, `@Column` y se acompañan de DTOs Records en la capa de API. |
| **III. Manejo Centralizado de Excepciones** | Respuestas de error uniformes RFC 7807 ante fallos. | **PASS** | `ApiErrorResponse` con timestamp y mensaje descriptivo en rutas `/api/v1/models/*`. |
| **IV. Determinismo Offline-First** | `schema.sql` y `data.sql` ejecutables en sandbox hermético sin red. | **PASS** | DDL compatible con H2 `MODE=PostgreSQL` probado herméticamente con mock determinista. |
| **V. Quality Gates y Cobertura Exhaustiva** | Cobertura total de pruebas unitarias y de integración. | **PASS** | Pruebas de síntesis, generación SQL, Mermaid ER y endpoints REST en `backend/tests/`. |
| **VI. Seguridad de Secretos y Frontera de IA** | Cero secretos persistidos; API keys efímeras en memoria. | **PASS** | Header `X-LLM-API-Key` y payload en memoria; 401 si falta en producción. |

---

## Project Structure

### Documentation (this feature)

```text
specs/004-domain-models-sql/
├── spec.md              # Feature specification & clarifications
├── plan.md              # Implementation plan (this file)
├── research.md          # Technical research & decisions (Phase 0)
├── data-model.md        # Schemas & sequence diagram (Phase 1)
├── quickstart.md        # End-to-end runnable validation scenarios (Phase 1)
├── contracts/
│   └── models-sql-api.yaml # OpenAPI 3.0 contract for models & SQL endpoints (Phase 1)
└── checklists/
    └── requirements.md  # Quality verification checklist
```

### Source Code Touchpoints

```text
backend/
├── app/
│   ├── main.py                         # Mount models router (/api/v1/models)
│   ├── api/
│   │   └── routes_models_sql.py        # POST /generate, POST /refine
│   ├── models/
│   │   ├── domain_model.py             # Schemas: DomainEntityDefinition, SqlSchemaScript, DataModelSynthesisResponse
│   │   └── __init__.py                 # Export new domain model schemas
│   └── services/
│       └── model_sql_service.py        # JPA entity generator, schema.sql/data.sql generator, Mermaid ER generator
└── tests/
    ├── test_model_sql_service.py       # Unit tests for DDL/DML, JPA classes, Mermaid ER
    └── test_routes_models_sql.py       # Contract tests for /generate, /refine, and 401 guards

frontend/
├── app.py                              # Register Tab 2 ("💾 2. Modelos de Dominio & Esquema SQL")
└── views/
    ├── architecture_view.py            # Add "💾 Diseñar Modelos & SQL" transition button in Tab 1
    └── models_sql_view.py              # Visual ER diagram, interactive entity cards, SQL editor, export/handoff buttons
```

---

## Complexity Tracking

*No constitutional violations. Zero unwarranted complexity.*
