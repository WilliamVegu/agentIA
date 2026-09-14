# Quickstart Validation Guide: Microservice Code Studio

**Feature**: `001-microservice-code-studio`
**Date**: 2026-09-13
**Status**: Ready for Implementation Verification (FastAPI + Streamlit + LangGraph)

This guide outlines runnable end-to-end scenarios to validate the Microservice Code Studio functionality against its specification and constitutional rules.

---

## 1. Environment Prerequisites

- **Python Runtime**: Python 3.11+ (`python --version`).
- **Container Runtime**: Docker Desktop / Docker Engine active (`docker info`).
- **Local JDK (optional for verification)**: Java 21 LTS (`java -version`).
- **Build Tool (in base Docker image)**: Apache Maven 3.9+ with pre-warmed local cache (`.m2/repository`).

---

## 2. Setup & Execution Commands

### 2.1 Backend Studio Engine (FastAPI + LangGraph)
```bash
# Navigate to backend directory and install dependencies
cd backend
pip install -r requirements.txt

# Start FastAPI server on port 8000
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
*API Documentation will be live at*: `http://localhost:8000/docs` (Swagger UI).

### 2.2 Frontend Studio Interface (Streamlit)
```bash
# In a separate terminal, navigate to frontend directory and install dependencies
cd frontend
pip install -r requirements.txt

# Start Streamlit application on port 8501
streamlit run app.py --server.port 8501
```
*Web Application will be accessible at*: `http://localhost:8501`.

---

## 3. End-to-End Validation Scenarios

### Scenario 1: Dual Ingestion & Pre-Generation Validation
**Objective**: Prove that the studio accepts specifications via both Streamlit UI upload and FastAPI REST endpoint.

1. **Option A: Ingestion via Streamlit UI**:
   - Open browser at `http://localhost:8501`.
   - In the "Ingest Specification" tab, drag and drop `specs/001-microservice-code-studio/spec.md`.
   - Observe immediate green validation badge: "Specification Parsed & Ready: 1 Domain Entity, 4 User Stories".

2. **Option B: Ingestion via FastAPI REST Endpoint**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/specifications/upload \
     -F "file=@specs/001-microservice-code-studio/spec.md"
   ```
   *Expected Outcome*: HTTP 201 Created with JSON body containing `specId`, parsed entities, and `isValid: true`.

---

### Scenario 2: Autonomous Generation & Real-Time SSE Streaming
**Objective**: Verify the live progress stream, execution of `mvn test -o` in Docker, and receipt of lifecycle events.

1. **Trigger Generation via Streamlit**:
   - In Streamlit, click **"🚀 Generate Microservice"**.
   - Streamlit connects to `http://localhost:8000/api/v1/sessions/{id}/stream`.
   - Observe `st.status` advancing through stages:
     - `SCAFFOLDING` -> `pom.xml` generated with Java 21 & Spring Boot 3.3.
     - `CODE_GENERATION` -> Java Records, Controllers, Repositories, and Mockito tests synthesized.
     - `SANDBOX_BUILD` -> Docker container launched with `--network none`.
     - `TEST_EXECUTION` -> Live terminal stdout showing `mvn test -o` running unit tests.
     - `COMPLETED` -> 100% tests passed.

2. **Verify via CLI / curl**:
   ```bash
   # Ingest JSON blueprint
   curl -X POST http://localhost:8000/api/v1/sessions \
     -H "Content-Type: application/json" \
     -d '{"specId": "<SPEC_ID>"}'

   # Stream events live
   curl -N http://localhost:8000/api/v1/sessions/<SESSION_ID>/stream
   ```

---

### Scenario 3: Bounded Self-Repair Loop Verification
**Objective**: Confirm that when a build or test assertion fails, the system executes up to 3 automatic repairs analyzing Maven stack traces, or halts at attempt 3 with `Blocked: Human Intervention Required`.

1. **Submit Specification with Intentional Inconsistency**:
   Submit an entity with validation rules contradicting the user story assertion.
2. **Observe Self-Repair in Streamlit**:
   - Status badge shows `Attempt 1/3: Analyzing Maven stack trace...`.
   - LangGraph repair node patches the service implementation.
   - Re-runs `mvn test -o` in Docker sandbox.
   - If test passes on attempt 2, status marks as `VERIFIED`.
   - If error persists past attempt 3, status halts with `Bloqueo por intervención humana requerida` and displays full stack trace.

---

### Scenario 4: Code Inspection, Package Export & Ephemeral Git Publish
**Objective**: Verify exploration of layered artifacts, ZIP packaging, and zero-secret Git push.

1. **Explore Generated Code in Streamlit**:
   - Navigate to the "Code Explorer" tab.
   - Select files from the dropdown (e.g., `OrderController.java`, `OrderService.java`, `OrderServiceTest.java`).
   - Confirm strict layered architecture and immutable Java Records DTOs formatted with syntax highlighting.

2. **Download Project ZIP**:
   - Click the "📦 Download ZIP Package" button in Streamlit.
   - Extract archive locally and confirm complete standalone Maven project.

3. **Publish to Git Feature Branch**:
   - Open the "Publish to Git" modal in Streamlit.
   - Enter repository URL and ephemeral Git PAT (in memory).
   - Click "Push to Branch".
   - Confirm atomic commit created on branch `feature/001-microservice-code-studio` and token cleared from memory.
