# Technical Research & Architectural Decisions: Component & Architecture Design

**Feature**: `003-architecture-component-design`  
**Date**: 2026-09-13  
**Status**: Completed  

---

## 1. Technical Context & Scope

This feature introduces an automated **Architecture & Component Design Engine** into the Microservice Code Studio. It bridges the gap between approved User Stories / BDD Acceptance Criteria (Feature 002) and code generation (Feature 001).

The engine must synthesize:
1. **Strict 4-Layer Topology** conforming to Constitution Principle I:
   - `controller`: Inbound HTTP REST handlers, request validation triggers, response DTO formatting.
   - `service`: Business logic interfaces and implementations, transaction boundaries, domain rules.
   - `repository`: Spring Data JPA persistence interfaces, custom query contracts.
   - `model` / `entity`: Domain entities and immutable Java Record DTOs (`Create*Request`, `*Response`).
   - `infrastructure` / `cross-cutting`: `GlobalExceptionHandler` (`@RestControllerAdvice`), validation filters, RFC 7807 problem details.
2. **REST Endpoint Catalog**: Derived deterministically from Given/When/Then criteria (HTTP method, route, request DTO, response DTO, status codes 201/200/400/404/500).
3. **Mermaid Layer & Interaction Diagram**: Directed graph visual showing unidirectional flows (`Controller ➔ Service ➔ Repository ➔ Entity`) with zero cyclic dependencies.
4. **Dual Export & Pipeline Handoff**: Downloading `openapi.yaml` and `architecture.md`, and direct 1-click transfer to Feature 001.

---

## 2. Key Decisions & Rationale

### Decision 1: Architecture Synthesis Algorithm & Prompt Engineering
- **Decision**: Use `ChatOpenAI.with_structured_output()` in LangChain backed by a strongly-typed Pydantic model (`ArchitectureDesignPayload`), decomposing stories by Domain Aggregate.
- **Rationale**: 
  - The LLM receives the active `SpecificationDraft` (stories, Given/When/Then scenarios, domain entities).
  - A specialized system prompt with Enterprise Solutions Architect persona maps functional criteria to standard Spring Boot 3 components.
  - Granularity is grouped by Domain Entity/Aggregate (e.g. `OrderController`, `OrderService`, `OrderRepository`), as chosen in Clarification #3.
  - Strict unidirectional validation checks ensure that controllers never depend on repositories directly, and services never return entities directly.
- **Alternatives Considered**:
  - *Regex/AST Rule-based Synthesis*: Lacks semantic understanding of complex business verbs in Given/When/Then statements.
  - *Unstructured Markdown Output*: Prone to schema variations, difficult to edit interactively in Streamlit.

### Decision 2: OpenAPI 3.0 & Documentation Serialization
- **Decision**: Generate canonical OpenAPI 3.0 YAML (`openapi.yaml`) and a comprehensive Architecture Document (`architecture.md`) using dedicated Python serializers.
- **Rationale**:
  - `openapi.yaml` enables frontend teams, QA, and API gateways to immediately consume API contracts with schemas and error objects conforming to Constitution Principle II (Java Records / Jakarta Validation) and Principle III (RFC 7807 error responses).
  - `architecture.md` embeds the component catalog, traceability matrix (which user story maps to which component/endpoint), and Mermaid diagrams.
  - Both files can be downloaded directly in the UI (`st.download_button`).
- **Alternatives Considered**:
  - *Postman Collection only*: Proprietary format, less standard than OpenAPI 3.0.
  - *Swagger 2.0*: Obsolete specification format.

### Decision 3: Visual Diagramming with Mermaid.js in Streamlit
- **Decision**: Generate clean Mermaid flowchart syntax (`graph TD` / `flowchart TD`) rendered directly in Streamlit using `st.markdown("```mermaid\n...\n```")`.
- **Rationale**:
  - Mermaid is natively supported by Streamlit, Markdown viewers, GitHub, and Spec Kit.
  - Allows clear subgraphs representing architectural layers:
    ```mermaid
    flowchart TD
        subgraph Presentation["Capa Controlador (REST)"]
            OrderController["OrderController<br/>POST /api/v1/orders<br/>GET /api/v1/orders/{id}"]
        end
        subgraph Business["Capa Servicio (Business Logic)"]
            OrderService["OrderService (Interface & Impl)"]
        end
        subgraph Persistence["Capa Repositorio (Spring Data JPA)"]
            OrderRepository["OrderRepository"]
        end
        subgraph Domain["Capa Dominio & DTOs"]
            OrderEntity["Order (JPA Entity)"]
            OrderDTO["CreateOrderRequest, OrderResponse (Records)"]
        end
        subgraph Infrastructure["Componentes Transversales"]
            GlobalException["GlobalExceptionHandler (@RestControllerAdvice)"]
        end
        OrderController --> OrderService
        OrderService --> OrderRepository
        OrderRepository --> OrderEntity
        OrderService -.-> OrderDTO
    ```
  - Zero heavy frontend dependencies or external rendering servers needed.
- **Alternatives Considered**:
  - *Graphviz (dot)*: Requires binary installation on the host system (problematic on some Windows environments).
  - *D3.js custom canvas*: High maintenance overhead and complex synchronization with Streamlit state.

### Decision 4: Interactive UI Integration & Tab Progression
- **Decision**: Implement a dedicated view `frontend/views/architecture_view.py` registered as **`🏗️ 1. Diseño Arquitectónico & Componentes`** in `frontend/app.py`.
- **Rationale**:
  - Creates a natural, progressive 6-tab pipeline:
    0. `📝 0. Redacción & Asistente de Requisitos`
    1. `🏗️ 1. Diseño Arquitectónico & Componentes` (NEW)
    2. `📥 2. Ingesta de Especificación`
    3. `🚀 3. Generación & Logs en Vivo`
    4. `🔍 4. Explorador de Código & Tests`
    5. `📦 5. Exportar & Publicar`
  - In Tab 0, clicking "🏗️ Diseñar Arquitectura" sends the draft to the backend, stores the resulting design in `st.session_state.architecture_design`, and redirects the user to Tab 1.
  - In Tab 1, the user can review the Mermaid diagram, inspect component cards, adjust endpoints/DTOs, refine via natural language prompts, and click "➡️ Transferir a Generación de Microservicio".
- **Alternatives Considered**:
  - *Embedding into Tab 0*: Would clutter Tab 0, making it excessively long and conflating business analysis with software architecture.

### Decision 5: Offline-First Determinism & Constitution Principle VI
- **Decision**: Provide deterministic mock synthesis for unit and contract testing (when API key is `mock-key` or `test-key`), ensuring zero remote network calls occur in automated test runs.
- **Rationale**: Conforms strictly to Constitution Principle IV (offline-first execution) and Principle VI (zero hardcoded secrets, no remote LLM calls in CI/tests).

---

## 3. Best Practices & Pattern Matrix

| Component Layer | Responsibility | Allowed Dependencies | Prohibited Dependencies |
|:---|:---|:---|:---|
| **Controller** | HTTP binding, path routing, status codes, `@Valid` | Service interfaces only | Repositories, JPA Entities (must use Record DTOs) |
| **Service Interface & Impl** | Business rules, transactions (`@Transactional`), BDD assertions | Repositories, domain models, other services | Controllers, HTTP Servlets, HTTP status codes |
| **Repository** | JPA queries, derived finders, CRUD operations | Entities, Spring Data JPA | Services, Controllers, DTOs |
| **Domain Model / Entities** | Entity state, table mapping, primary keys | Internal utility classes | Services, Controllers, Repositories |
| **DTOs (Java Records)** | Immutable data contracts, Jakarta annotations | Standard Java types | Mutable state, JPA annotations |
| **Cross-Cutting** | `@RestControllerAdvice`, exception translation | ProblemDetails, standard exceptions | Domain persistence queries |

