# Research & Technical Decisions: Docker Containerization, CI/CD Pipelines & Deployment Orchestration

**Feature**: `007-docker-cicd-orchestration`  
**Date**: 2026-09-13  
**Status**: Completed  

---

## 1. Multi-Stage Layered Docker Containerization

### Decision
Implement a 2-stage hermetic `Dockerfile` utilizing Eclipse Temurin JRE 21 LTS (`eclipse-temurin:21-jre-alpine` or `eclipse-temurin:21-jre-jammy`) and Spring Boot layered jar extraction (`java -Djarmode=layertools -jar application.jar extract`).

### Rationale
- **Optimized Layer Caching**: Spring Boot layered jar extraction separates dependencies (rarely changed) from Spring Boot loader, internal dependencies, and application classes (frequently changed). Modifications to business logic only invalidate the final ~100KB application layer, slashing container rebuild times by >50%.
- **Minimal Runtime Footprint**: Using a pure JRE runtime base image (instead of a full JDK) cuts image size from ~650MB to <180MB.
- **Defense in Depth (Non-Root Execution)**: An unprivileged system user (`appuser:10001`) with read-only root filesystem capabilities (where feasible) prevents container breakout vulnerabilities.
- **Container-Aware JVM Tuning**: Automatically injects `-XX:MaxRAMPercentage=75.0` to ensure the JVM respects cgroup memory limits without out-of-memory container kills.

### Alternatives Considered
- **Single-Stage `COPY target/*.jar app.jar`**: Inefficient layer caching; any one-line code modification forces Docker to rebuild and push the entire 50MB+ fat JAR layer.
- **Cloud Native Buildpacks (Paketo / Spring Boot Maven Plugin `mvn spring-boot:build-image`)**: Requires downloading large builder images (800MB+) from the internet, violating offline determinism under Constitution Principle IV.

---

## 2. Docker Compose Local Orchestration & Database Integration

### Decision
Generate a dynamic `docker-compose.yml` that detects the database chosen during Spec 004 (PostgreSQL 16, MySQL 8, or H2 in-memory), connects services via an isolated bridge network, and configures database healthchecks with `depends_on: { condition: service_healthy }`.

### Rationale
- **1-Click Local Execution**: Developers can run `docker compose up -d` and have both the database and the microservice start in the correct dependency order.
- **Automated DDL Initialization**: Mounting `schema.sql` (generated in Spec 004) into `/docker-entrypoint-initdb.d/` ensures that tables, indexes, and initial data are pre-populated on container startup.
- **Data Persistence**: Uses named volumes (e.g. `pgdata`, `mysqldata`) to preserve state across container restarts.
- **Graceful H2 Handling**: When in-memory H2 is selected, `docker-compose.yml` skips external database containers entirely, launching only the microservice with `SPRING_PROFILES_ACTIVE=h2`.

### Alternatives Considered
- **Manual Database Setup**: Requiring the developer to have a running PostgreSQL/MySQL instance locally creates environment discrepancy errors.
- **Flyway-Only Initialization**: While supported in production, mounting `schema.sql` directly into the database engine ensures zero cold-start delay for development.

---

## 3. Automated Enterprise CI/CD Pipelines (GitHub Actions & GitLab CI)

### Decision
Generate pre-configured, production-ready workflow definitions for both GitHub Actions (`.github/workflows/ci-cd.yml`) and GitLab CI (`.gitlab-ci.yml`), integrating hermetic Maven builds, test execution (Spec 005), security quality gates (Spec 006), and Trivy container scanning.

### Rationale
- **End-to-End Governance**: Enforces all constitutional principles in remote CI runners:
  1. *Hermetic Maven Build*: `mvn clean test -o` (Principio IV).
  2. *Automated Testing*: Unit and Integration tests must pass with 100% success rate (Principio V, Spec 005).
  3. *Security & Secret Scan*: Fails if secrets or OWASP Top 10 vulnerabilities are detected (Principio VI, Spec 006).
  4. *Container Build & Trivy Scan*: Builds the multi-stage Docker image and inspects for CVEs before pushing to registries.
- **Zero Secrets**: Pipeline files reference GitHub/GitLab repository secrets (`${{ secrets.DOCKER_REGISTRY_TOKEN }}` / `$CI_REGISTRY_PASSWORD`) rather than plaintext credentials.

### Alternatives Considered
- **Jenkinsfile**: Higher maintenance overhead for modern cloud-native teams compared to declarative GitHub Actions and GitLab CI.
- **Post-Deploy Pipelines**: Out of scope for MVP; focus remains on build, verification, security scanning, and container packaging.

---

## 4. Local Deployment Engine with Live SSE Streaming Logs

### Decision
Develop a Python-based Docker engine service (`backend/app/services/docker_service.py`) in FastAPI that communicates with the local Docker daemon via socket (`/var/run/docker.sock` on Linux/macOS or `//./pipe/docker_engine` on Windows), exposing build and run logs live via Server-Sent Events (SSE) at `/api/v1/devops/{session_id}/logs/stream`.

### Rationale
- **Sub-Second Streaming Latency**: Server-Sent Events provide lightweight, one-way HTTP streaming without the connection overhead or WebSocket complexity.
- **Preventive Daemon Detection (Ratified Option A)**: If the Docker daemon is unreachable, the system enters "Export-Only" mode, gracefully disabling local execution buttons while keeping all artifact generation and downloads active.
- **Non-Blocking Execution**: Docker builds and container orchestrations execute in background threads/subprocesses, preventing FastAPI worker lockups.

### Alternatives Considered
- **WebSockets for Terminal Logs**: Heavier protocol requiring bidirectional frames and keep-alive ping management when SSE is sufficient for log streaming.
- **Synchronous Blocking CLI Calls**: Freezes the web server during `docker build`, causing browser request timeouts.

---

## 5. Automated Smoke Testing & Healthcheck Verification

### Decision
Implement an automated post-deployment smoke testing routine in `docker_service.py` that polls `http://localhost:{host_port}/actuator/health` every 2 seconds up to 60 seconds until receiving `{"status": "UP"}`.

### Rationale
- **Guaranteed Availability**: Validates that Spring Boot successfully established database connections, executed migrations, and initialized the embedded Web server.
- **Clickable Test Exposure**: Surfaces the exact localhost URL (e.g. `http://localhost:8080/actuator/health`, `http://localhost:8080/swagger-ui.html`) directly in Streamlit Tab 7.
- **Failure Diagnostics**: If the healthcheck times out, the engine fetches the last 50 lines of container stderr/stdout to provide actionable troubleshooting advice.

---

## 6. Production Kubernetes Manifests Generation

### Decision
Generate a clean, standard set of Kubernetes YAML manifests: `deployment.yaml` (with liveness/readiness probes), `service.yaml` (ClusterIP), `configmap.yaml`, and `ingress.yaml` (configured with `ingressClassName: nginx`).

### Rationale
- **Cloud-Native Best Practices**: Configures resource limits (`cpu: 1000m`, `memory: 1024Mi`), non-root security context (`runAsNonRoot: true`), and probes mapped directly to Spring Boot Actuator endpoints (`/actuator/health/liveness` and `/actuator/health/readiness`).
- **Standard Ingress (Ratified Option A)**: Native `networking.k8s.io/v1` `Ingress` with `ingressClassName: nginx` works out-of-the-box on local Kubernetes environments (Minikube, K3s, Docker Desktop) and cloud providers (EKS, GKE, AKS).

