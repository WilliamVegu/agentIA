# Quickstart Validation Guide: Domain Models & SQL Schema Generation

**Feature**: `004-domain-models-sql`  
**Date**: 2026-09-13  
**Status**: Ready for Validation  

This guide provides end-to-end validation scenarios for the Domain Models & SQL Schema Generation engine across the FastAPI REST backend and Streamlit Web Studio.

---

## 1. Prerequisites

- FastAPI Backend running on port 8000:
  ```bash
  python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
  ```
- Streamlit Web Studio running on port 8501:
  ```bash
  python -m streamlit run frontend/app.py --server.port 8501
  ```
- Ephemeral OpenAI API Key configured in the settings sidebar (or using deterministic offline mock test mode).

---

## 2. Validation Scenarios

### Scenario 1: Transition from Architecture to Domain Models & SQL
**Goal**: Verify that clicking `"💾 Diseñar Modelos & SQL"` in Tab 1 triggers backend model synthesis and shifts focus to Tab 2 (`💾 2. Modelos de Dominio & Esquema SQL`).

1. Open Streamlit (`http://localhost:8501`) and generate requirements in Tab 0 (e.g. `Order` and `OrderItem`).
2. Advance to Tab 1 (`🏗️ 1. Diseño Arquitectónico & Componentes`) and ensure the 4-layer topology is generated.
3. In Tab 1, click the primary transition button: **"💾 Diseñar Modelos & SQL"**.
4. **Expected Outcome**:
   - Backend processes `POST /api/v1/models/generate` in under 15 seconds.
   - UI focus shifts to Tab **"💾 2. Modelos de Dominio & Esquema SQL"**.
   - A live directional Mermaid Entity-Relationship diagram (`erDiagram`) is rendered showing `ORDER ||--o{ ORDER_ITEM`.
   - Both entities display numeric primary keys (`id: BIGINT PK`) and audit fields (`created_at`, `updated_at`).

---

### Scenario 2: Interactive Attribute Editing & Real-time SQL Sync
**Goal**: Verify that editing an attribute or constraint in the interactive entity cards dynamically updates the synchronized SQL DDL script.

1. In Tab **"💾 2. Modelos de Dominio & Esquema SQL"**, locate the entity card for `Order`.
2. Find the attribute `status` and toggle the **"Unique"** checkbox to checked, or edit the column name to `order_status`.
3. **Expected Outcome**:
   - The synchronized SQL editor immediately reflects `order_status VARCHAR(50) NOT NULL UNIQUE`.
   - The Mermaid ER diagram updates its attribute listing to match.

---

### Scenario 3: AI-Assisted Schema Refinement (Human-in-the-Loop)
**Goal**: Verify that sending natural language refinement instructions updates the entity models, relationships, and SQL scripts.

1. In Tab **"💾 2. Modelos de Dominio & Esquema SQL"**, navigate to the **"🔄 4. Asistente de Refinamiento de Datos con IA"** section.
2. In the feedback input, type:
   ```text
   Agrega un campo trackingNumber de tipo String único en Order y un índice para búsquedas rápidas
   ```
3. Click **"🔄 Refinar Modelos & SQL"**.
4. **Expected Outcome**:
   - Backend processes `POST /api/v1/models/refine`.
   - `Order` entity now contains `trackingNumber` (`VARCHAR(255) UNIQUE`).
   - The `schema.sql` script contains `CREATE INDEX idx_orders_tracking_number ON orders(tracking_number);`.
   - The Mermaid ER diagram displays `tracking_number` under `ORDER`.

---

### Scenario 4: Export Artifacts and Pipeline Handoff to Generator
**Goal**: Verify that `schema.sql` and `data.sql` are downloadable, and that clicking "Transferir al Motor de Generación" registers the enriched blueprint into Feature 001.

1. In Tab **"💾 2. Modelos de Dominio & Esquema SQL"**, section **"🚀 5. Exportación y Transferencia al Generador"**:
2. Click **"📥 Descargar schema.sql"**:
   - Verify downloaded file is a valid PostgreSQL/H2 DDL script.
3. Click **"📥 Descargar data.sql"**:
   - Verify downloaded file contains valid sample `INSERT INTO` statements.
4. Click **"➡️ Transferir al Motor de Generación"**:
   - The enriched blueprint containing domain entities, JPA code, and SQL scripts is persisted in `POST /api/v1/specifications`.
   - A success banner instructs the user to proceed to Tab **"🚀 4. Generación & Logs en Vivo"**.

