# Quickstart Validation Guide: Unified End-to-End Workflow Orchestration

**Feature**: `008-unified-workflow-orchestration`  
**Date**: 2026-09-13  
**Status**: Ready for Validation  

This guide provides 5 runnable end-to-end validation scenarios verifying the persistent lifecycle stepper, guided step-by-step advancement, one-click Auto-Pilot pipeline execution, in-flight hot-pausing, constitutional quality gate safety halting, and upstream change re-synchronization.

---

## 1. Prerequisites

- **FastAPI Backend running on port 8000**:
  ```bash
  python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
  ```
- **Streamlit Web Studio running on port 8501**:
  ```bash
  python -m streamlit run frontend/app.py --server.port 8501
  ```

---

## 2. Validation Scenarios

### Scenario 1: Guided Step-by-Step Navigation & Persistent Stepper
**Goal**: Verify that starting a new session loads the Project Overview Home View, renders the persistent top-level Stepper, and enables step-by-step progression with the contextual Next Action Bar.

1. Open Web Studio at `http://localhost:8501`.
2. Inspect the landing view:
   - Verify that **"🏠 0. Resumen del Proyecto"** appears by default.
   - The top header renders the persistent 7-phase Stepper (`Requisitos` ➔ `Historias` ➔ `Arquitectura` ➔ `Persistencia` ➔ `Código & Tests` ➔ `Seguridad & Calidad` ➔ `DevOps & Despliegue`).
   - Phase 1 is marked `IN_PROGRESS` or `COMPLETED`, and subsequent phases are initially `NOT_STARTED`.
3. In Phase 1 ("1. Especificación & Blueprint"), click **"👉 Siguiente Paso: Generar Historias de Usuario"**.
4. **Expected Outcome**:
   - The coordinator validates prerequisites, updates session state to Phase 2 (`STORIES`), and switches the active view to Tab 2.
   - The top Stepper highlights Phase 2 as active.
   - Clicking on the Phase 1 badge in the top Stepper immediately jumps back to Tab 1.

---

### Scenario 2: Autonomous One-Click Auto-Pilot Execution
**Goal**: Verify that triggering Auto-Pilot executes the entire microservice synthesis pipeline in the background and streams live progress events.

1. From the Project Overview screen, click **"🚀 Ejecutar Flujo Completo (Auto-Pilot)"** or invoke:
   ```bash
   curl -X POST http://localhost:8000/api/v1/orchestrator/pipeline/run \
     -H "Content-Type: application/json" \
     -d '{"sessionId": "test-session-001", "targetPhase": "DEVOPS_DEPLOY", "stopOnGate": true}'
   ```
2. Open the event stream in a browser or terminal:
   ```bash
   curl -N http://localhost:8000/api/v1/orchestrator/pipeline/test-session-001/events
   ```
3. **Expected Outcome**:
   - HTTP 202 Accepted.
   - SSE stream emits sequential `PipelineProgressEvent` objects:
     - `STORIES`: 15% - User stories synthesized.
     - `ARCHITECTURE`: 30% - Component blueprint designed.
     - `DATA_MODEL`: 45% - Entities and `schema.sql` generated.
     - `CODE_TESTS`: 65% - Spring Boot code and Mockito tests synthesized.
     - `SECURITY_AUDIT`: 80% - SAST and secrets audit executed.
     - `DEVOPS_DEPLOY`: 100% - Dockerfile, Compose, and K8s manifests generated.
   - Completion percentage updates smoothly from 0% to 100%.

---

### Scenario 3: Auto-Pilot In-Flight Hot-Pausing & Mode Switching
**Goal**: Verify that clicking "Pausar" safely interrupts the active background Auto-Pilot pipeline and hands over control in Guided Step-by-Step mode.

1. Initiate an Auto-Pilot pipeline run for a session.
2. While Phase 4 (`DATA_MODEL` or `CODE_TESTS`) is running, click **"⏸️ Pausar Auto-Pilot"** or invoke:
   ```bash
   curl -X POST http://localhost:8000/api/v1/orchestrator/pipeline/test-session-001/pause
   ```
3. **Expected Outcome**:
   - The runner finishes the active atomic step and transitions status to `PAUSED`.
   - The Studio switches from Auto-Pilot mode to `GUIDED_STEP` mode.
   - The active view opens the corresponding tab, allowing the developer to inspect and manually edit the generated code.
   - The developer can now click **"👉 Siguiente Paso"** to continue step-by-step or **"▶️ Reanudar Auto-Pilot"** to continue automatically.

---

### Scenario 4: Constitutional Quality Gate Interception & Auto-Pilot Safe Halting
**Goal**: Verify that Auto-Pilot halts safely when encountering a `BLOCKED` Quality Gate verdict (Principle V & VI).

1. Trigger Auto-Pilot on a session containing a simulated security violation (e.g. hardcoded API key).
2. Monitor pipeline progression until Phase 6 (`SECURITY_AUDIT`).
3. **Expected Outcome**:
   - The security scanner detects the violation and returns `QualityGateVerdict.canExport = False`.
   - The Auto-Pilot pipeline immediately halts in `AWAITING_INTERVENTION` state (does NOT proceed to Phase 7 Deploy).
   - An amber warning banner appears in the Studio: `"🛑 Pipeline Detenido: La Compuerta de Calidad está BLOQUEADA"`.
   - A direct one-click button `"🔍 Ir a Auditoría de Seguridad (Pestaña 6)"` opens the remediation view.

---

### Scenario 5: Upstream Modification with Outdated Downstream Flagging
**Goal**: Verify that modifying an upstream artifact flags downstream phases as `OUTDATED` without destroying existing work, offering a 1-click re-sync.

1. For a session that has completed all 7 phases, navigate back to Tab 2 ("Historias de Usuario") and modify an acceptance scenario.
2. Query the lifecycle state or view the Stepper:
   ```bash
   curl http://localhost:8000/api/v1/orchestrator/sessions/test-session-001/lifecycle
   ```
3. **Expected Outcome**:
   - Phases 3 through 7 show status `OUTDATED` with warning icons (`⚠️`).
   - The existing code and manifests are preserved on disk.
   - The UI surfaces a prominent banner: `"⚠️ Se detectaron cambios en Requisitos/Historias. Las etapas posteriores requieren sincronización"`.
   - Clicking **"🔄 Re-sincronizar y Regenerar etapas posteriores"** sequentially regenerates only the affected phases.

