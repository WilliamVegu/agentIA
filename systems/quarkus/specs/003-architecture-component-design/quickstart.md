# Quickstart Validation Guide: Automated Architecture & Component Design

**Feature**: `003-architecture-component-design`  
**Date**: 2026-09-13  
**Status**: Ready for Validation  

This guide provides end-to-end scenarios to validate the Architecture & Component Design engine in both the Streamlit Studio interface and the FastAPI REST backend.

---

## 1. Prerequisites

- FastAPI Backend running on port 8000:
  ```bash
  python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
  ```
- Streamlit Studio running on port 8501:
  ```bash
  python -m streamlit run frontend/app.py --server.port 8501
  ```
- An ephemeral OpenAI API Key configured in the settings sidebar (or using `mock-key` for offline sandbox testing).

---

## 2. Validation Scenarios

### Scenario 1: Transition from Stories to Architecture Design
**Goal**: Verify that clicking "🏗️ Diseñar Arquitectura" in Tab 0 decomposes user stories and acceptance criteria into a 4-layer architecture with a rendered Mermaid diagram in Tab 1.

1. In Streamlit (`http://localhost:8501`), open Tab **"📝 0. Redacción & Asistente de Requisitos"**.
2. Enter requirements or load a draft (e.g. `order-service` with `Order` entity and `US-1` Create Order, `US-2` Cancel Order).
3. Ensure user stories and Given/When/Then scenarios are present.
4. Click **"🏗️ Diseñar Arquitectura"**.
5. **Expected Outcome**:
   - The backend processes `POST /api/v1/architecture/design` in under 20 seconds.
   - The UI automatically shifts focus to Tab **"🏗️ 1. Diseño Arquitectónico & Componentes"**.
   - A directed Mermaid flowchart is displayed showing:
     - `OrderController` in Presentation layer.
     - `OrderService` in Business Service layer.
     - `OrderRepository` in Persistence layer.
     - `Order` and Record DTOs (`CreateOrderRequest`, `OrderResponse`) in Domain layer.
     - `GlobalExceptionHandler` in Cross-Cutting Infrastructure layer.
   - Component cards are visible and editable.

---

### Scenario 2: Interactive Architectural Refinement (Human-in-the-Loop)
**Goal**: Verify that architects can send natural language feedback prompts to update the architecture without losing existing components.

1. In Tab **"🏗️ 1. Diseño Arquitectónico & Componentes"**, locate the **"🔄 Refinamiento Arquitectónico con IA"** section.
2. In the feedback input, type:
   ```text
   Añade un componente de servicio de notificación para alertar al cliente al crear o cancelar la orden
   ```
3. Click **"🔄 Refinar Arquitectura"**.
4. **Expected Outcome**:
   - The backend executes `POST /api/v1/architecture/refine`.
   - The component catalog updates to include `NotificationService` in the Service layer.
   - The Mermaid diagram updates to show `OrderService --> NotificationService`.
   - All other existing components and endpoints remain intact.

---

### Scenario 3: Export Artifacts (`openapi.yaml` and `architecture.md`)
**Goal**: Verify that clicking the download buttons generates compliant, non-empty files.

1. In Tab **"🏗️ 1. Diseño Arquitectónico & Componentes"**, navigate to the **"📥 Exportar Documentación y Contratos"** section.
2. Click **"📥 Descargar openapi.yaml"**:
   - Verify downloaded file is a valid OpenAPI 3.0 YAML document containing routes (e.g. `POST /api/v1/orders`), request/response schemas, and RFC 7807 error responses.
3. Click **"📥 Descargar architecture.md"**:
   - Verify downloaded file is a complete Markdown document with component descriptions, layer hierarchy, and embedded Mermaid diagrams.

---

### Scenario 4: Direct Pipeline Handoff to Code Generator
**Goal**: Verify that the validated architectural blueprint transitions directly into the Microservice Code Studio generator.

1. In Tab **"🏗️ 1. Diseño Arquitectónico & Componentes"**, click **"➡️ Transferir a Generación de Microservicio"**.
2. **Expected Outcome**:
   - The enriched blueprint is registered in `POST /api/v1/specifications`.
   - `st.session_state.current_spec_id` is populated.
   - A success banner confirms transfer.
   - Navigate to Tab **"🚀 3. Generación & Logs en Vivo"** and verify that autonomous synthesis is ready to run with the exact component structure.

