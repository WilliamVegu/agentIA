# Research & Technical Decisions: Microservice Code Studio

**Feature**: `001-microservice-code-studio`
**Date**: 2026-09-13
**Status**: Completed (Updated for FastAPI + Streamlit + LangGraph)

## Overview

Microservice Code Studio is an enterprise platform designed to ingest formal microservice specifications (architecture blueprints, user stories, and acceptance criteria), orchestrate autonomous code synthesis adhering strictly to Constitution v1.1.0 (Java 21 LTS, Spring Boot 3.x, layered architecture, immutable records, Mockito unit tests), execute hermetic offline compilation and testing (`mvn test -o`) within isolated Docker sandboxes, stream real-time progress via Server-Sent Events (SSE), enforce a strict 3-iteration self-repair loop, and package or publish the resulting code to Git feature branches.

The studio platform itself is implemented with **FastAPI** (headless backend API & LangGraph execution engine) paired with **Streamlit** (interactive developer web UI) in Python 3.11+.

---

## Technical Decisions

### Decision 1: Platform Architecture — FastAPI (Backend) + Streamlit (Frontend) + LangGraph

- **Decision**: Architect the studio platform using a decoupled Python-based architecture:
  - **Backend API & Engine (FastAPI on port 8000)**: Implements the REST API endpoints and Server-Sent Events (`EventSourceResponse`). Houses the **LangGraph** state machine, Pydantic v2 schemas, session queue manager, and Docker sandbox executor.
  - **Frontend UI (Streamlit on port 8501)**: Provides an interactive, rapid web interface for developers and architects, communicating with FastAPI via HTTP and SSE.
  - **Target Deliverable**: Pure Java 21 LTS / Spring Boot 3.x corporate microservices complying with the repository constitution.
- **Rationale**: 
  - **Dual Access Model**: Satisfies user clarification 1 & 2: external services (like the sister specification authoring module) or CI pipelines can trigger code generation programmatically via FastAPI's REST API (`POST /api/v1/sessions`), while human engineers can use Streamlit for visual file uploading, live log streaming, code exploration, and ZIP export.
  - **Native LangGraph Integration**: Running LangGraph inside FastAPI leverages Python's native async runtime, state management, and memory safety without language-bridging overhead.
  - **Rapid UI Iteration**: Streamlit provides built-in `st.file_uploader`, `st.status`, `st.code(language="java")`, and `st.download_button`, eliminating hundreds of hours of custom frontend component plumbing while providing a sleek experience.
- **Alternatives Considered**:
  - *Spring Boot (Java) backend for the studio*: Rejected because running Python LangGraph agents from a Java backend requires complex subprocesses or HTTP sidecars, creating unnecessary operational complexity.
  - *Streamlit Solo (without FastAPI)*: Evaluated, but rejected because a standalone Streamlit app cannot expose headless REST endpoints for programmatic invocation by the sister specification module.
  - *React / Next.js frontend*: Evaluated, but Streamlit offers vastly faster delivery with native Python integration for code exploration and live log streaming.

---

### Decision 2: Hermetic Offline Sandbox & Build Execution (`mvn test -o`)

- **Decision**: Execute all generated code builds, compilation, and JUnit 5 unit tests inside ephemeral Docker containers running with `--network none` and mounting a pre-warmed, read-only local Maven cache (`/root/.m2/repository:ro`).
- **Rationale**:
  - Directly enforces Constitution Principle IV (Deterministic Offline-First & Sandbox Isolation).
  - With network disabled (`--network none`), the container cannot download unauthorized dynamic dependencies, connect to external network services, or leak environment variables/secrets.
  - Running `mvn test -o` deterministically verifies that all required plugins and dependencies (Spring Boot starter, JPA, Validation, H2, JUnit 5, Mockito, AssertJ) exist in the base cache.
  - In Python, the `docker` SDK (`docker-py`) or `asyncio.create_subprocess_exec` manages container lifecycles cleanly and captures stdout/stderr line-by-line for streaming.
- **Alternatives Considered**:
  - *Process-level execution on host (`subprocess` without Docker)*: Fails to guarantee network isolation; a prompt hallucination or rogue dependency could initiate outbound HTTP calls.

---

### Decision 3: Autonomous Code Synthesis Engine with LangGraph

- **Decision**: The autonomous generation pipeline is structured as an asynchronous state graph (`StateGraph`) in LangGraph:
  1. *Validator Node*: Validates ingested blueprint, entity mappings, and Given/When/Then criteria against constitutional rules.
  2. *Scaffolder Node*: Synthesizes project root, `pom.xml` (with pinned dependency versions), package structure, and `application.yml`.
  3. *Domain & Contract Synthesizer*: Generates JPA entities, Jakarta-validated Request/Response Java Records, and custom business exceptions.
  4. *Layered Component Synthesizer*: Generates Spring Data Repositories, Service interfaces with `@Service` implementations, and `@RestController` with `@RestControllerAdvice`.
  5. *Test Suite Synthesizer*: Generates comprehensive JUnit 5, Mockito, and AssertJ test classes covering happy paths and exception paths.
- **Rationale**:
  - Complies with Constitution Principle VI: LangGraph resides solely in the orchestration plane; the generated Spring Boot microservice contains zero dependencies on LangGraph or LLM libraries.
  - Multi-stage graph nodes provide deterministic rollback and inspection at each layer.

---

### Decision 4: Bounded Self-Repair Loop (Anti-Hallucination Gate)

- **Decision**: When `mvn test -o` exits with a non-zero code in Docker, a specialized regex parser extracts only compiler errors and Surefire/Failsafe failure traces from the build log.
  - The repair node receives ONLY this diagnostic trace and the affected Java file.
  - The graph increments `repair_attempts` (1, 2, 3).
  - If attempt 3 fails, the graph immediately transitions to the `BLOCKED` state, sets status to `Bloqueo por intervención humana requerida`, and emits an SSE event.
- **Rationale**:
  - Directly fulfills Constitution Principle V.
  - Strict input focus (Maven stack trace only) prevents context bloat and compounding hallucinations.
  - Explicit 3-attempt ceiling prevents infinite compute loops and API cost runaway.

---

### Decision 5: Real-Time Streaming Architecture via Server-Sent Events (SSE)

- **Decision**: FastAPI uses `sse-starlette` (`EventSourceResponse`) to expose `GET /api/v1/sessions/{id}/stream`.
  - Emits typed events: `phase_transition`, `queue_status`, `build_log`, `repair_diagnostic`, `session_completed`, `session_blocked`.
  - Streamlit consumes this stream using `sseclient-py` inside a background generator or thread, updating `st.status()` and log containers progressively.
- **Rationale**:
  - Complies with user clarification 4.
  - Standard HTTP, lightweight, and supports automatic reconnection with `Last-Event-ID`.

---

### Decision 6: Concurrency Control & Worker Queue

- **Decision**: FastAPI implements an in-memory `asyncio.Queue` with a semaphore limiting active concurrent generations to `MAX_CONCURRENT_SESSIONS = 2`.
  - Excess requests are enqueued in FIFO order.
  - Real-time queue position is broadcasted over SSE (`queue_status`).
- **Rationale**:
  - Complies with user clarification 5.
  - Prevents host memory exhaustion caused by parallel Docker containers running Maven compiler JVMs.

---

### Decision 7: Ephemeral Secret Management for VCS Delivery

- **Decision**: Git Personal Access Tokens (PATs) are accepted in the payload of `POST /api/v1/sessions/{id}/publish`. The token is held only in a local method variable during the Git push operation via `GitPython` or `git CLI`, after which it is immediately dereferenced and purged from memory. No token is ever written to the database, disk, or logs.
- **Rationale**:
  - Adheres to Constitution Principle VI and User Clarification 3.
  - Prevents accidental token leakage across shared development workspaces.
