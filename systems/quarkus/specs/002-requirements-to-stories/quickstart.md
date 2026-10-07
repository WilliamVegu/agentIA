# Quickstart Validation Guide: Requirements to Stories Transformation

**Feature**: `002-requirements-to-stories`  
**Date**: 2026-09-13  
**Status**: Ready for Validation  

This guide provides end-to-end scenarios to validate the Requirements Transformation & Refinement engine in both the Streamlit Studio interface and the FastAPI REST backend.

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
- An ephemeral OpenAI API Key (or set via `OPENAI_API_KEY` in `.env` / environment).

---

## 2. Validation Scenarios

### Scenario 1: Transform Free-Form Requirements to Structured Stories

**Goal**: Verify that entering raw text produces prioritized User Stories with at least two Given/When/Then scenarios (happy path + exception) and extracted domain entities.

1. In Streamlit (`http://localhost:8501`), navigate to the new initial tab: **"📝 0. Redacción & Asistente de Requisitos"**.
2. Enter an OpenAI API key in the sidebar under "🔒 Credenciales Efímeras" (or confirm environment variable).
3. In the text area, input:
   ```text
   Necesito un microservicio para gestionar órdenes de compra (Order).
   Cada orden tiene cliente (customerEmail) y monto total (totalAmount).
   El cliente puede crear una orden, consultar sus órdenes y cancelar una orden si está pendiente.
   Se debe rechazar la orden si el monto total es menor o igual a cero.
   ```
4. Click **"✨ Transformar a Historias y Criterios"**.
5. **Expected Outcome**:
   - Extraction completes in under 15 seconds.
   - Identified service name: `order-service`, package: `com.corp.order`.
   - Domain entity `Order` extracted with attributes: `id` (Long, PK), `customerEmail` (String), `totalAmount` (BigDecimal).
   - User stories generated (P1: Create order, P2: Query orders, P3: Cancel order).
   - Each story displays at least 2 acceptance criteria:
     - `AC-1.1` (Happy path): Given valid customer and positive amount, When POST /orders is called, Then 201 Created is returned.
     - `AC-1.2` (Validation error): Given amount <= 0, When POST /orders is called, Then 400 Bad Request is returned.

---

### Scenario 2: Interactive Prompt Refinement (Human-in-the-Loop)

**Goal**: Verify that submitting a natural language refinement prompt updates the draft without losing existing data.

1. Below the generated stories, locate the **"💬 Sugerencia de Refinamiento con IA"** input.
2. Type:
   ```text
   Agrega un criterio de aceptación para evitar órdenes duplicadas del mismo cliente en menos de 1 minuto.
   ```
3. Click **"🔄 Refinar con IA"**.
4. **Expected Outcome**:
   - Story `US-1` is updated with a new scenario `AC-1.3` specifying duplicate order rejection.
   - Other stories and entities remain preserved.

---

### Scenario 3: Missing API Key Enforcement

**Goal**: Verify Constitution Principle VI and requirement that absence of an API key blocks transformation.

1. Clear the API key input in the sidebar (ensure no `OPENAI_API_KEY` in environment).
2. Click **"✨ Transformar a Historias y Criterios"**.
3. **Expected Outcome**:
   - System refuses transformation and displays an error alert: *"⚠️ Se requiere una API Key para utilizar el asistente de transformación. Ingrésala en la barra lateral."*
   - Backend endpoint returns HTTP 401 Unauthorized.

---

### Scenario 4: Export to `spec.md` & Direct Pipeline Handoff

**Goal**: Verify exporting the document and transitioning directly to code generation.

1. Click **"⬇️ Descargar spec.md"**:
   - Verify that the downloaded Markdown file matches the canonical Spec Kit template.
2. Click **"➡️ Transferir a Generación de Microservicio"**:
   - The system registers the blueprint in `POST /api/v1/specifications`.
   - The UI automatically updates `st.session_state.current_spec_id`.
   - Navigate to Tab 1 / Tab 2 and observe the summary card loaded and ready to generate!

