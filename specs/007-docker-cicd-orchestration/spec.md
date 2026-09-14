# Feature Specification: Docker Containerization, CI/CD Pipelines & Deployment Orchestration

**Feature Branch**: `007-docker-cicd-orchestration`

**Created**: 2026-09-13

**Status**: Draft

**Input**: User description: "El sistema debe gestionar la contenerización Docker, la generación de pipelines de CI/CD y la orquestación del despliegue para los microservicios Java 21 / Spring Boot 3 generados, integrándose con el ciclo de vida existente (specs 001 a 006): 1. Generación de Dockerfile multi-stage hermético y optimizado (Eclipse Temurin JRE 21, Spring Boot layered jars, usuario no-root, .dockerignore) y docker-compose.yml que orqueste el microservicio con la base de datos detectada en la spec 004 (PostgreSQL/MySQL/H2) y sus variables de entorno. 2. Generación de pipelines de CI/CD automatizados (GitHub Actions y GitLab CI) que contemplen: compilación hermética Maven, ejecución de tests unitarios y de integración (spec 005), escaneo de seguridad SAST y secretos (spec 006), build de imagen Docker y escaneo de vulnerabilidades con Trivy. 3. Motor de despliegue local en el Studio: endpoints en FastAPI (/api/v1/devops/generate, /deploy, /status) y una nueva pestaña en Streamlit ('7. DevOps & Despliegue') que permita ejecutar 'docker build' y 'docker run/compose' conectándose al daemon local de Docker, transmitiendo los logs en vivo vía Server-Sent Events (SSE). 4. Smoke testing y Healthcheck automatizado: verificación post-despliegue consultando el endpoint /actuator/health hasta confirmar estado UP y exponer la URL local de prueba. 5. Manifiestos de despliegue para producción: generación de manifiestos Kubernetes básicos (Deployment con probes liveness/readiness, Service, ConfigMap e Ingress). 6. Cumplimiento de la Constitución (Principio VI): cero secretos en disco, inyección efímera de variables de entorno y credenciales para registries."

---

## Overview

Following autonomous specification ingestion, architectural design, persistence modeling, automated testing, and security/quality gate auditing (features 001 through 006), the microservice platform must bridge the gap between verified source code and reproducible production-ready runtime deployment.

This feature delivers end-to-end containerization, enterprise continuous integration and continuous delivery (CI/CD) pipelines, live local Docker deployment with streaming real-time logs, automated post-deployment health verification (smoke tests), and production Kubernetes manifests, strictly enforcing Constitution Principle IV (offline determinism) and Principle VI (zero secrets in repositories or configuration).

---

## Clarifications

### Session 2026-09-13
- Q: ¿Cómo debe comportarse el sistema si el usuario solicita un despliegue local en la Pestaña 7 pero el Docker daemon local no está instalado o no se encuentra en ejecución? (FR-009) → A: Detección preventiva con advertencia clara y modo "Export-Only". Si el daemon de Docker no está activo o no responde al handshake inicial, la interfaz y la API notifican amigablemente que el daemon no está disponible, inhabilitan el botón de despliegue local y ofrecen descargar/exportar todos los artefactos generados (`Dockerfile`, `docker-compose.yml`, scripts) para ejecución externa.
- Q: ¿Cómo debe inicializarse el esquema y los datos relacionales generados en la Spec 004 dentro del contenedor de base de datos en `docker-compose.yml`? (FR-005) → A: Montaje automático de los scripts DDL/DML generados (`schema.sql`) en el directorio `/docker-entrypoint-initdb.d/` del contenedor de base de datos (PostgreSQL/MySQL), junto con un volumen nombrado persistente para conservar los datos entre reinicios.
- Q: ¿Qué estándar o controlador de Ingress debe configurarse por defecto en `ingress.yaml` para el microservicio? (FR-014) → A: Kubernetes Ingress estándar (`networking.k8s.io/v1`) con `ingressClassName: nginx` y annotations estándar de rewrite-target, garantizando máxima portabilidad en clústeres locales (Minikube, K3s) y administrados (EKS, GKE, AKS).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Hermetic Multi-Stage Docker Containerization & Local Orchestration (Priority: P1) 🎯 MVP

As a DevOps engineer or microservice developer, I want the system to generate an optimized, hermetic multi-stage Dockerfile and docker-compose.yml tailored to the microservice's persistence engine, so that the application can be built, packaged, and executed in an isolated runtime environment with zero manual configuration.

**Why this priority**: Fundamental foundation for modern cloud-native deployment. Without reproducible containerization, the microservice cannot be reliably tested or deployed across different environments.

**Independent Test**: Can be tested independently by taking a synthesized microservice from spec 004, generating the container artifacts, running `docker build` and verifying that:
1. The image uses Eclipse Temurin JRE 21 with layered Spring Boot jars.
2. The process runs under an unprivileged non-root user.
3. `docker-compose.yml` launches both the application and the detected database (PostgreSQL/MySQL/H2) with correct networking and environment variables.

**Acceptance Scenarios**:

1. **Given** a generated Spring Boot 3 microservice, **When** container assets are generated, **Then** the system creates a multi-stage Dockerfile utilizing Spring Boot's layered jar extractor (`layers.idx`), copying dependencies, Spring Boot loader, and application layers separately for optimal Docker layer caching.
2. **Given** the generated Dockerfile, **When** inspected for security standards, **Then** it enforces a non-root Linux user (`appuser:10001`), configures JVM container-aware memory flags (`-XX:MaxRAMPercentage=75.0`), and includes a `.dockerignore` excluding `.git`, `target/`, and secrets.
3. **Given** a microservice configured with PostgreSQL or MySQL in Spec 004, **When** `docker-compose.yml` is generated, **Then** it orchestrates the database container, initializes persistent volumes, mounts `schema.sql` into `/docker-entrypoint-initdb.d/`, establishes a private bridge network, and sets `depends_on` conditions with database healthchecks.

---

### User Story 2 - Automated Enterprise CI/CD Pipelines (Priority: P1)

As a release engineer or team lead, I want the platform to automatically generate standardized CI/CD workflow definitions (GitHub Actions and GitLab CI), so that every code commit undergoes hermetic compilation, unit/integration testing, security scanning, and container vulnerability inspection before artifact publishing.

**Why this priority**: Enterprise compliance and automated quality gating. Ensures that software delivery pipelines enforce Constitution Principles IV, V, and VI in automated remote runners.

**Independent Test**: Can be tested independently by generating pipeline manifests (`.github/workflows/ci-cd.yml` and `.gitlab-ci.yml`) for an audited project, verifying that all pipeline stages (Hermetic Maven Build, Unit & Integration Tests from Spec 005, SAST & Secret Scanner from Spec 006, Docker build, and Trivy CVE scanning) are fully articulated without syntax errors or hardcoded credentials.

**Acceptance Scenarios**:

1. **Given** a generated microservice project, **When** CI/CD pipeline generation is requested, **Then** the system outputs both a GitHub Actions workflow (`.github/workflows/ci-cd.yml`) and a GitLab CI pipeline (`.gitlab-ci.yml`).
2. **Given** the generated pipeline definitions, **When** reviewed for quality gates, **Then** the pipeline halts immediately if unit tests fail (Spec 005) or if SAST/secret scans detect `CRITICAL` or `HIGH` vulnerabilities (Spec 006).
3. **Given** the container packaging stage, **When** the pipeline builds the Docker image, **Then** it invokes a Trivy container scan step configured to fail the pipeline on severe image CVEs.

---

### User Story 3 - Local Deployment Engine with Live SSE Streaming Logs (Priority: P1)

As a developer using the Microservice Code Studio, I want a dedicated DevOps & Deployment panel in the Web Studio that triggers local container builds and deployments while streaming real-time terminal output, so that I can validate container execution locally with instant observability.

**Why this priority**: Crucial developer experience and interactive validation. Empowers users to run and test their synthesized microservice right from the browser with continuous feedback.

**Independent Test**: Can be tested independently by accessing the new Streamlit tab ("7. DevOps & Despliegue"), selecting a completed session, clicking "Desplegar Localmente (Docker)", and verifying that FastAPI backend endpoints (`/api/v1/devops/generate`, `/deploy`, `/status`) communicate with the local Docker daemon and stream build/run logs live via Server-Sent Events (SSE).

**Acceptance Scenarios**:

1. **Given** an audited session in the Web Studio, **When** opening Tab 7 ("7. DevOps & Despliegue"), **Then** the user sees container configuration summaries, service ports, target database details, and deployment action controls.
2. **Given** the user clicks "Desplegar Localmente", **When** FastAPI initiates the Docker build and compose orchestration, **Then** live terminal logs are streamed directly into an in-browser log terminal via Server-Sent Events (`text/event-stream`).
3. **Given** a running local deployment, **When** querying `/api/v1/devops/{session_id}/status`, **Then** the endpoint returns the container status, exposed port, uptime, and resource utilization.

---

### User Story 4 - Automated Smoke Testing & Healthcheck Verification (Priority: P2)

As a QA engineer or developer, I want the system to automatically perform post-deployment smoke tests by polling the microservice's `/actuator/health` endpoint until a healthy state is confirmed, so that I know with certainty that the containerized application is running and operational.

**Why this priority**: Eliminates silent container launch failures (e.g. database connectivity errors, missing environment variables, or port collisions) and guarantees end-to-end runtime readiness.

**Independent Test**: Can be tested independently by launching the container, triggering the smoke test routine, and verifying that the system polls `/actuator/health` with configurable timeouts, validates the `UP` status payload, and presents a clickable local test URL to the developer.

**Acceptance Scenarios**:

1. **Given** a freshly launched microservice container, **When** the healthcheck monitor activates, **Then** it periodically polls `http://localhost:<port>/actuator/health` up to a defined timeout threshold (e.g. 60 seconds).
2. **Given** the health endpoint returns `{"status": "UP"}`, **When** the verification completes, **Then** the system marks the deployment as `ACTIVE_HEALTHY`, displays response latency metrics, and renders a clickable local URL badge (`http://localhost:8080/api/v1/...`).
3. **Given** a container that fails to start or encounters an unhandled exception, **When** the healthcheck timeout expires, **Then** the deployment is flagged as `FAILED_UNHEALTHY` and container exit logs are surfaced with troubleshooting advice.

---

### User Story 5 - Production Kubernetes Manifests Generation (Priority: P2)

As a cloud architect or site reliability engineer, I want the system to generate production-grade Kubernetes manifests (Deployment, Service, ConfigMap, and Ingress), so that the microservice can be deployed to staging and production Kubernetes clusters following cloud-native best practices.

**Why this priority**: Bridges local container development to cloud-scale enterprise deployment on platforms like OpenShift, EKS, GKE, or AKS.

**Independent Test**: Can be tested independently by generating Kubernetes YAML manifests for a microservice, validating them against Kubernetes schema definitions, and confirming the presence of liveness and readiness probes pointing to Spring Boot Actuator endpoints.

**Acceptance Scenarios**:

1. **Given** a microservice session, **When** Kubernetes manifest generation is requested, **Then** the system outputs standard YAML manifests: `deployment.yaml`, `service.yaml`, `configmap.yaml`, and `ingress.yaml`.
2. **Given** `deployment.yaml`, **When** inspected for resilience, **Then** it defines `livenessProbe` (`/actuator/health/liveness`) and `readinessProbe` (`/actuator/health/readiness`), non-root `securityContext`, and resource limits/requests (`CPU`, `Memory`).
3. **Given** `configmap.yaml` and `ingress.yaml`, **When** inspected for security, **Then** configuration properties reference environment variables, secrets are left for external Secret Provider injection (Principio VI), and ingress rules configure host routing using `ingressClassName: nginx`.

---

## Edge Cases

- **Docker Daemon Inaccessibility**: When the host system lacks a running Docker daemon, the system activates "Export-Only" mode, notifying the user via UI and API while keeping manifest generation and download fully functional.
- **Port Conflicts**: If the standard port 8080 or 5432 is already bound by another process on the developer's machine, the deployment engine dynamically binds an available ephemeral host port and maps it to the container port.
- **H2 Database Mode**: When a microservice uses in-memory H2 (Spec 004), `docker-compose.yml` launches only the standalone microservice container with embedded H2 configuration, omitting external database containers.
- **Non-Root Permission in Volumes**: Official PostgreSQL/MySQL container images manage internal directory permissions automatically for mounted `/var/lib/.../data` volumes.
- **Slow Container Cold Starts**: Java applications in resource-constrained environments may take 20–40 seconds to boot; the healthcheck polling engine uses exponential backoff and up to 60 seconds timeout before failing.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST generate an optimized, multi-stage `Dockerfile` based on Eclipse Temurin JRE 21 LTS, leveraging Spring Boot layered jars (`java -Djarmode=layertools -jar application.jar extract`) to separate dependencies, spring-boot-loader, and application code into discrete cached layers.
- **FR-002**: System MUST generate a `.dockerignore` file excluding `.git`, `.gitignore`, `target/`, `*.log`, `Dockerfile*`, and any local credentials or secrets.
- **FR-003**: System MUST enforce container security best practices in the Dockerfile, including non-root user execution (`USER appuser`), `HEALTHCHECK` instructions, and JVM container limits (`-XX:MaxRAMPercentage=75.0`).
- **FR-004**: System MUST generate a `docker-compose.yml` orchestrating the microservice and the database engine selected in Spec 004 (PostgreSQL 16, MySQL 8, or embedded H2), configuring network bridges, healthchecks, and environment variables.
- **FR-005**: In `docker-compose.yml`, system MUST configure automated database schema initialization by mounting the generated `schema.sql` into `/docker-entrypoint-initdb.d/` with persistent named volumes for data retention.
- **FR-006**: System MUST generate automated CI/CD pipeline definitions for **GitHub Actions** (`.github/workflows/ci-cd.yml`) and **GitLab CI** (`.gitlab-ci.yml`).
- **FR-007**: Generated CI/CD pipelines MUST execute sequential verification stages: hermetic Maven build (`mvn clean test -o`), unit and integration test execution (Spec 005), SAST & secret audit gating (Spec 006), multi-stage Docker build, and Trivy vulnerability scanning.
- **FR-008**: System MUST provide backend REST API endpoints under `/api/v1/devops`:
  - `POST /api/v1/devops/{session_id}/generate`: Generates all Docker, Compose, CI/CD, and Kubernetes manifests for the session workspace.
  - `POST /api/v1/devops/{session_id}/deploy`: Triggers local Docker build and compose deployment, returning a streamable task ID.
  - `GET /api/v1/devops/{session_id}/status`: Returns current container state, port bindings, and healthcheck status.
  - `GET /api/v1/devops/{session_id}/logs/stream`: Streams live Docker build and execution logs via Server-Sent Events (SSE).
  - `POST /api/v1/devops/{session_id}/stop`: Gracefully stops and cleans up active local containers and networks.
- **FR-009**: System MUST connect to the local Docker daemon using standard Docker socket protocols (Unix socket `/var/run/docker.sock` or Windows named pipe `//./pipe/docker_engine`). If the daemon is unreachable, the system enters "Export-Only" mode with clear UI feedback.
- **FR-010**: System MUST incorporate Tab 7 ("7. DevOps & Despliegue") into the Streamlit Web Studio, presenting container settings, pipeline previews, live terminal output via SSE, and deployment controls.
- **FR-011**: System MUST perform automated post-deployment smoke tests by polling `/actuator/health` until confirming an `UP` response or reaching a 60-second timeout.
- **FR-012**: Upon successful smoke testing, system MUST expose the local test URL and key Actuator endpoints (`/actuator/health`, `/actuator/info`) in the Studio interface.
- **FR-013**: System MUST generate production-grade Kubernetes YAML manifests: `deployment.yaml` (with liveness/readiness probes and non-root security context), `service.yaml`, `configmap.yaml`, and `ingress.yaml`.
- **FR-014**: In Kubernetes `ingress.yaml`, system MUST configure the standard `networking.k8s.io/v1` API with `ingressClassName: nginx` and standard rewrite-target annotations.
- **FR-015**: System MUST strictly adhere to Constitution Principle VI: zero secrets or credentials written to disk, Dockerfiles, or pipeline files; all credentials for container registries or databases must be injected via runtime environment variables or secrets.
- **FR-016**: System MUST respect Quality Gate decisions from Spec 006: local deployment and artifact generation MUST be blocked if the session's Quality Gate status is `BLOCKED`.

---

### Key Entities *(include if feature involves data)*

- **ContainerManifestBundle**: Container and orchestration definitions generated for a microservice (Dockerfile content, .dockerignore content, docker-compose.yml content, generatedAt).
- **PipelineManifestConfig**: Continuous integration definitions (githubActionsYaml, gitlabCiYaml, buildStages, scanGates).
- **KubernetesManifestGroup**: Production orchestration files (deploymentYaml, serviceYaml, configMapYaml, ingressYaml, targetNamespace).
- **LocalDeploymentSession**: Runtime tracking for a local container instance (sessionId, containerId, status: `IDLE` | `BUILDING` | `RUNNING` | `HEALTHY` | `FAILED` | `STOPPED`, hostPort, containerPort, databaseContainerId, startedAt).
- **SmokeTestResult**: Automated health validation outcome (passed: bool, statusCode: int, responsePayload: dict, latencyMs: float, checkedAt: datetime, testUrl: str).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Generation of complete DevOps assets (Dockerfile, docker-compose, CI/CD pipelines, Kubernetes manifests) completes in under 2 seconds.
- **SC-002**: Generated Dockerfile achieves at least 50% faster rebuild times on code modifications by properly separating layered dependencies from application classes.
- **SC-003**: 100% of generated Docker images execute under an unprivileged non-root user without administrative capabilities.
- **SC-004**: Users can initiate a local deployment and observe live streaming logs in the Web Studio with under 500ms initial log latency.
- **SC-005**: Automated smoke testing confirms microservice availability and surfaces local test URLs in under 45 seconds from deployment trigger.
- **SC-006**: 100% of generated manifests and CI/CD pipelines contain zero hardcoded secrets or passwords, complying with Constitution Principle VI.

---

## Assumptions

- **Local Docker Daemon**: The developer's environment has Docker Engine or Docker Desktop installed when local deployment execution is requested; if absent, the system operates in Export-Only mode.
- **Spring Boot Actuator**: The generated Spring Boot 3 microservice includes `spring-boot-starter-actuator` to expose `/actuator/health` and probe endpoints.
- **Network Isolation**: Local containers communicate over a dedicated bridge network created specifically for the session to prevent cross-service collision.
- **Hermetic Build Images**: CI/CD pipelines specify exact versioned container base images (e.g. `eclipse-temurin:21-jre-alpine` and `maven:3.9-eclipse-temurin-21`) to guarantee reproducible determinism.
