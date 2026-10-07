# Quickstart Validation Guide: Docker Containerization, CI/CD Pipelines & Deployment Orchestration

**Feature**: `007-docker-cicd-orchestration`  
**Date**: 2026-09-13  
**Status**: Ready for Validation  

This guide provides 5 end-to-end runnable scenarios verifying containerization generation, multi-stage non-root builds, local Compose orchestration with database integration, real-time SSE streaming logs, automated smoke testing, and graceful fallback handling.

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
- **Local Docker Daemon**: Docker Desktop / Docker Engine (or Export-Only mode if daemon is absent).

---

## 2. Validation Scenarios

### Scenario 1: Generation of Complete DevOps Assets Bundle
**Goal**: Verify that calling the generation endpoint creates all container, compose, CI/CD, and Kubernetes manifests matching the microservice's database engine.

1. Submit an existing session with PostgreSQL persistence: `POST /api/v1/devops/{session_id}/generate`.
2. **Expected Outcome**:
   - HTTP 200 OK.
   - `dockerfileContent` contains `FROM eclipse-temurin:21-jre-alpine` and `java -Djarmode=layertools`.
   - `dockerignoreContent` excludes `.git`, `target/`, and `*.log`.
   - `dockerComposeContent` orchestrates the service with `postgres:16-alpine`, mounts `schema.sql` to `/docker-entrypoint-initdb.d/`, and defines a persistent volume.
   - `githubActionsWorkflow` and `gitlabCiWorkflow` contain hermetic Maven, test execution, SAST/secrets gating, and Trivy container scan stages.
   - `kubernetesManifests` contains `deployment.yaml`, `service.yaml`, `configmap.yaml`, and `ingress.yaml` (`ingressClassName: nginx`).

---

### Scenario 2: Multi-Stage Layered Dockerfile Security Verification
**Goal**: Inspect generated Dockerfile for compliance with non-root security standards and container-aware JVM flags.

1. Inspect the generated `Dockerfile` in the session workspace.
2. **Expected Outcome**:
   - Extraction stage uses `layertools`.
   - Creates unprivileged user: `USER appuser` (UID 10001).
   - Entrypoint sets `-XX:MaxRAMPercentage=75.0`.
   - Defines a native `HEALTHCHECK` checking `/actuator/health`.
   - Zero hardcoded secrets in `ENV` or `ARG` instructions (Principio VI).

---

### Scenario 3: Local Deployment & Live SSE Streaming Logs
**Goal**: Verify that triggering a local deployment connects to the Docker daemon and streams real-time build and execution logs via Server-Sent Events.

1. Open Tab 7 ("7. DevOps & Despliegue") in the Web Studio.
2. Click **"🚀 Desplegar Localmente (Docker)"** or invoke `POST /api/v1/devops/{session_id}/deploy`.
3. Open EventSource stream: `GET /api/v1/devops/{session_id}/logs/stream`.
4. **Expected Outcome**:
   - HTTP 200 OK with `Content-Type: text/event-stream`.
   - Stream delivers build step outputs, layer extraction logs, and compose container launch status in real time.
   - Initial log event arrives within 500ms.

---

### Scenario 4: Automated Smoke Testing & Healthcheck Verification
**Goal**: Verify post-deployment health by polling `/actuator/health` until confirming status UP.

1. Call `POST /api/v1/devops/{session_id}/smoke-test`.
2. **Expected Outcome**:
   - HTTP 200 OK.
   - `passed` equals `true`.
   - `statusCode` equals 200.
   - `statusPayload.status` equals `"UP"`.
   - `latencyMs` is measured and under 500ms.
   - `testUrl` points to `http://localhost:8080/actuator/health`.
   - Clickable URL badge appears in the Web Studio interface.

---

### Scenario 5: Quality Gate Guard & Docker Daemon Fallback Mode
**Goal**: Verify that sessions with a `BLOCKED` Quality Gate cannot be deployed, and verify that if Docker daemon is stopped, system enters Export-Only mode.

1. For a session with `BLOCKED` Quality Gate:
   - Call `POST /api/v1/devops/{session_id}/deploy`.
   - **Expected Outcome**: HTTP 403 Forbidden with error stating Quality Gate is BLOCKED.
2. For an environment where Docker daemon is stopped:
   - Check `GET /api/v1/devops/{session_id}/status`.
   - **Expected Outcome**: Status reports `DOCKER_UNAVAILABLE`.
   - In Streamlit Tab 7, deployment buttons are disabled with an informational banner, and a "📦 Descargar Artefactos DevOps (ZIP)" button is enabled.

