# Implementation Plan: Docker Containerization, CI/CD Pipelines & Deployment Orchestration

**Branch**: `007-docker-cicd-orchestration` | **Date**: 2026-09-13 | **Spec**: [specs/007-docker-cicd-orchestration/spec.md](file:///c:/Users/willi/Downloads/agentIA/specs/007-docker-cicd-orchestration/spec.md)

**Input**: Feature specification from `specs/007-docker-cicd-orchestration/spec.md` ("El sistema debe gestionar la contenerización Docker, la generación de pipelines de CI/CD y la orquestación del despliegue para los microservicios Java 21 / Spring Boot 3 generados, integrándose con el ciclo de vida existente (specs 001 a 006)...")

---

## Summary

This feature extends the Microservice Code Studio with production-grade DevOps lifecycle capabilities:
1. **Hermetic Layered Containerization**: 2-stage Dockerfile based on Eclipse Temurin JRE 21 LTS using Spring Boot layered jars (`layertools`), non-root user execution (`appuser:10001`), `.dockerignore`, and cgroup-aware JVM memory limits (`-XX:MaxRAMPercentage=75.0`).
2. **Local Multi-Container Orchestration**: Dynamic `docker-compose.yml` orchestrating the microservice with the target persistence engine from Spec 004 (PostgreSQL 16, MySQL 8, or H2), mounting `schema.sql` into `/docker-entrypoint-initdb.d/` with persistent volumes.
3. **Enterprise CI/CD Pipelines**: Automated GitHub Actions (`.github/workflows/ci-cd.yml`) and GitLab CI (`.gitlab-ci.yml`) definitions enforcing hermetic Maven builds, test suites (Spec 005), SAST & secret audits (Spec 006), and Trivy vulnerability scans.
4. **Local Deployment & Live SSE Streaming**: Dedicated FastAPI engine connecting to the local Docker daemon via socket/pipe with live Server-Sent Events (SSE) streaming logs, paired with a preventive "Export-Only" fallback if Docker is inactive.
5. **Automated Smoke Testing**: Post-deployment health verification polling `/actuator/health` until confirming status `UP`, exposing the local test URL.
6. **Production Kubernetes Manifests**: Declarative YAML manifests (`deployment.yaml` with liveness/readiness probes, `service.yaml`, `configmap.yaml`, and `ingress.yaml` targeting `ingressClassName: nginx`).

---

## Technical Context

**Language/Version**: Python 3.11+ (FastAPI backend, Streamlit frontend); Target: Java 21 LTS / Spring Boot 3.x microservices; Container Platforms: Docker Engine, Docker Compose v2, Kubernetes.

**Primary Dependencies**:
- Backend: FastAPI, Pydantic v2, Uvicorn, Python standard libraries (`asyncio`, `subprocess`, `threading`, `queue`, `shutil`).
- Frontend: Streamlit, Requests, SSE Client / EventStream parser.
- Container Tools: Local Docker socket / named pipe (`/var/run/docker.sock`, `//./pipe/docker_engine`).

**Storage**:
- SQLite (`sessions.db`) for session metadata and deployment status tracking.
- Workspace directories (`workspaces/{session_id}/`) storing Dockerfile, Compose, CI/CD, and Kubernetes manifests.

**Testing**: Pytest (`python -m pytest backend/tests -o pythonpath=backend`), validating manifest generation, Dockerfile syntax, compose topology, CI/CD stages, SSE stream endpoints, and smoke testing logic.

**Target Platform**: Cross-platform (Windows, Linux, macOS).

**Performance Goals**:
- Full DevOps asset generation: < 2.0 seconds.
- Initial SSE streaming log latency: < 500 milliseconds.
- Smoke test polling interval: 2 seconds (up to 60s timeout).
- Rebuild speedup: > 50% faster incremental builds via Spring Boot layered jar caching.

**Constraints**:
- Constitution Principle IV: Hermetic offline reproducibility (`mvn clean test -o`).
- Constitution Principle VI: Zero secrets on disk or in repository/Dockerfiles; ephemeral runtime injection only.
- Quality Gate Guard: Prohibit deployment and artifact generation if session Quality Gate status is `BLOCKED`.

---

## Constitution Check

*GATE: Verified against `.specify/memory/constitution.md`.*

| Principle | Relevance & Impact on Feature | Status |
|---|---|---|
| **I. Layer Isolation** | Containerization packages the clean 4-layer microservice without interfering with internal component boundaries. | **PASS** |
| **II. Immutable DTOs & Validation** | DevOps REST endpoints use strict Pydantic v2 models with validation for all requests and responses. | **PASS** |
| **III. Centralized Error Handling** | FastAPI DevOps endpoints use centralized exception handling, returning RFC 7807 error structures. | **PASS** |
| **IV. Offline Determinism & Sandbox** | Multi-stage Dockerfile and CI/CD pipelines enforce offline-first Maven compilation (`mvn clean test -o`) and pinned image versions (`eclipse-temurin:21-jre-alpine`). | **PASS** |
| **V. Quality Gates & Auto-Repair** | Local deployment checks `QualityGateVerdict.canExport`; blocks container execution if `BLOCKED` until issues are resolved. | **PASS** |
| **VI. Zero Secrets & Ephemeral Boundary** | All container, pipeline, and Kubernetes files use environment variable interpolations (`${DB_PASSWORD}`); zero plaintext secrets on disk. | **PASS** |

**GATES RESULT**: **PASS**. Fully compliant with Platform Constitution.

---

## Project Structure

### Documentation (this feature)

```text
specs/007-docker-cicd-orchestration/
├── plan.md              # Implementation plan (/speckit-plan output)
├── research.md          # Technical decisions: multi-stage, compose, CI/CD, SSE, K8s (/speckit-plan output)
├── data-model.md        # Schemas & Mermaid class/sequence diagrams (/speckit-plan output)
├── quickstart.md        # 5 runnable validation scenarios (/speckit-plan output)
├── contracts/           # API specifications (/speckit-plan output)
│   └── devops-api.yaml  # OpenAPI 3.0 specification for /api/v1/devops/*
└── checklists/
    └── requirements.md  # 16/16 requirements validation checklist (PASS)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/
│   │   ├── routes_devops.py            # [NEW] Endpoints: /api/v1/devops/{session_id}/generate, /deploy, /status, /logs/stream, /stop, /smoke-test
│   │   └── ... (existing routers)
│   ├── models/
│   │   ├── devops.py                   # [NEW] Pydantic models: DevOpsManifestBundle, LocalDeploymentSession, SmokeTestResult, etc.
│   │   └── ... (existing models)
│   ├── services/
│   │   ├── devops_service.py           # [NEW] Generator for Dockerfile, .dockerignore, docker-compose.yml, CI/CD pipelines & K8s manifests
│   │   ├── docker_service.py           # [NEW] Docker daemon integration, SSE live log streamer, process manager, and smoke test runner
│   │   └── ... (existing services)
│   └── main.py                         # [MODIFY] Register routes_devops router
└── tests/
    ├── test_devops_service.py          # [NEW] Unit tests for manifest generation (Dockerfile, Compose, CI/CD, K8s)
    ├── test_routes_devops.py           # [NEW] Contract tests for DevOps API endpoints and Quality Gate guards
    └── ... (existing 80 passing tests)

frontend/
├── views/
│   ├── devops_view.py                  # [NEW] Tab 7 '🚀 7. DevOps & Despliegue' view with controls, live terminal, and K8s preview
│   └── ... (existing views)
└── app.py                              # [MODIFY] Add Tab 7 '🚀 7. DevOps & Despliegue' to main navigation
```

---

## Source Code Touchpoints & Implementation Details

1. **`backend/app/models/devops.py` [NEW]**:
   - Enums: `DeploymentStatus` (`IDLE`, `BUILDING`, `RUNNING`, `HEALTHY`, `FAILED`, `STOPPED`, `DOCKER_UNAVAILABLE`), `DatabaseEngine` (`POSTGRESQL`, `MYSQL`, `H2`).
   - Models: `DevOpsManifestBundle`, `LocalDeploymentSession`, `SmokeTestResult`, `DevOpsDeployRequest`.

2. **`backend/app/services/devops_service.py` [NEW]**:
   - `generate_dockerfile(service_name: str) -> str`: Generates multi-stage Dockerfile with `layertools`, non-root user `appuser`, JVM cgroup flags, and Actuator `HEALTHCHECK`.
   - `generate_dockerignore() -> str`: Generates `.dockerignore` excluding `.git`, `target/`, and secrets.
   - `generate_docker_compose(service_name: str, db_engine: str, host_port: int) -> str`: Generates `docker-compose.yml` with database container, volume mounts for `schema.sql`, healthchecks, and bridge network.
   - `generate_github_actions(service_name: str) -> str`: Generates `.github/workflows/ci-cd.yml` with Maven build, test suite, security scan, and Trivy CVE container scan.
   - `generate_gitlab_ci(service_name: str) -> str`: Generates `.gitlab-ci.yml` with pipeline stages.
   - `generate_kubernetes_manifests(service_name: str, host_port: int) -> Dict[str, str]`: Generates `deployment.yaml` (with liveness/readiness probes), `service.yaml`, `configmap.yaml`, and `ingress.yaml` (`ingressClassName: nginx`).
   - `generate_all_devops_assets(workspace_dir: str, session_id: str, service_name: str, db_engine: str) -> DevOpsManifestBundle`: Orchestrates creation of all files in workspace.

3. **`backend/app/services/docker_service.py` [NEW]**:
   - `check_docker_daemon() -> bool`: Tests socket/named pipe connectivity to verify if Docker daemon is active.
   - `deploy_local(session_id: str, workspace_dir: str, host_port: int) -> LocalDeploymentSession`: Launches background thread running `docker compose up --build -d` and capturing stdout/stderr into a thread-safe queue.
   - `stream_logs(session_id: str) -> Generator[str, None, None]`: Streams events via `text/event-stream` for live SSE terminal.
   - `get_deployment_status(session_id: str) -> LocalDeploymentSession`: Queries container inspect / ps for active session.
   - `stop_deployment(session_id: str, workspace_dir: str) -> LocalDeploymentSession`: Runs `docker compose down -v`.
   - `run_smoke_test(session_id: str, host_port: int) -> SmokeTestResult`: Polls `http://localhost:{host_port}/actuator/health` up to 60s, measures latency, and returns parsed payload.

4. **`backend/app/api/routes_devops.py` [NEW]**:
   - `POST /api/v1/devops/{session_id}/generate`: Invokes `devops_service.generate_all_devops_assets`. Blocks if Quality Gate is `BLOCKED`.
   - `POST /api/v1/devops/{session_id}/deploy`: Checks Docker daemon. If unavailable, returns `DOCKER_UNAVAILABLE` (Export-Only). Otherwise launches deployment. Blocks if Quality Gate is `BLOCKED`.
   - `GET /api/v1/devops/{session_id}/status`: Returns current status and smoke test info.
   - `GET /api/v1/devops/{session_id}/logs/stream`: Returns SSE `StreamingResponse`.
   - `POST /api/v1/devops/{session_id}/stop`: Graceful shutdown.
   - `POST /api/v1/devops/{session_id}/smoke-test`: Triggers healthcheck verification.

5. **`backend/app/main.py` [MODIFY]**:
   - Register `routes_devops.router` under prefix `/api/v1`.

6. **`frontend/views/devops_view.py` [NEW]**:
   - Tab 7 UI implementation:
     - Header & Status Badges: Container status (`HEALTHY`, `RUNNING`, `STOPPED`, `DOCKER_UNAVAILABLE`).
     - Action Controls: "🚀 Desplegar Localmente", "🛑 Detener Contenedores", "🧪 Ejecutar Smoke Test", "📦 Descargar Artefactos DevOps".
     - Real-Time Terminal View: Live log streamer using SSE or auto-refreshing log box.
     - Actuator & Test URL Card: Clickable URL badge (`http://localhost:8080/actuator/health`) when `UP`.
     - Manifest Inspection Accordions: Syntax-highlighted views of `Dockerfile`, `docker-compose.yml`, GitHub Actions, GitLab CI, and Kubernetes YAMLs.

7. **`frontend/app.py` [MODIFY]**:
   - Add Tab 7 ("🚀 7. DevOps & Despliegue") to top navigation.

8. **`backend/tests/test_devops_service.py` & `test_routes_devops.py` [NEW]**:
   - Tests validating all manifest generation patterns, layered jars, database compose topologies, Quality Gate guards, and REST endpoints.

---

## Complexity Tracking

*No constitutional violations. Zero entries required.*
