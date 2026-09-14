# Implementation Plan: Automated Test Generation, Code Analysis & Iterative Self-Repair

**Branch**: `005-automated-tests-analysis` | **Date**: 2026-09-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-automated-tests-analysis/spec.md`

---

## Summary

This feature delivers an autonomous verification, static/dynamic code analysis, and iterative self-repair engine for Microservice Code Studio. It bridges code scaffolding with production readiness by:
1. Automatically synthesizing **Hybrid Test Suites** (unit tests with Mockito for services/controllers and `@SpringBootTest` integration tests with in-memory H2 PostgreSQL mode) derived from Given/When/Then acceptance scenarios.
2. Executing tests inside an isolated, hermetic Docker sandbox (`--network none`, `mvn test -o`).
3. Diagnosing compiler errors and test assertion failures into structured `FailureDiagnostic` objects.
4. Enforcing static architectural compliance (Constitution Principles I, II, III, IV) to prevent illegal code shortcuts.
5. Planning and applying **surgical code patches** at the method/block level, re-running tests up to the constitutional limit of 3 iterations.
6. Providing a **Human-in-the-Loop Blocked Mode** with an in-browser code editor and AI hint assistance when autonomous attempts are exhausted, and an interactive **Repair Diff Viewer** in Streamlit.

---

## Technical Context

**Platform Language & Runtime**: Python 3.12+ (FastAPI Backend & Streamlit Frontend)  
**Target Generated Codebase**: Java 21 LTS, Spring Boot 3.x, JUnit 5 (Jupiter), Mockito, AssertJ, H2 Database (`MODE=PostgreSQL`)  
**AI Orchestration**: LangChain / OpenAI Chat Models (`gpt-4o-mini`) with structured Pydantic extraction and deterministic offline fallbacks  
**Primary Dependencies**:
- *Backend*: `fastapi>=0.111.0`, `pydantic>=2.7.0`, `langchain-openai>=0.1.0`, `docker>=7.0.0`
- *Frontend*: `streamlit>=1.36.0`, `requests>=2.31.0`

**Storage**:
- In-memory session state & artifact store (`SESSIONS_STORE`, `ARTIFACTS_STORE`).
- Ephemeral repair iteration records (`RepairIterationRecord`, `RepairHistoryResponse`).

**Testing Framework**: `pytest`, `httpx`  
**Target Platform**: Web browsers (port 8501) and internal REST API (port 8000).  

**Performance Goals**:
- Autonomous test suite generation < 20 seconds.
- Diagnostic extraction & repair patch generation < 15 seconds per iteration.
- Total repair loop execution < 90 seconds (for 3 iterations).

**Constraints & Governance**:
- **Constitution Principle I**: Strict 4-layer unidirectional architecture (`controller` ➔ `service` ➔ `repository` ➔ `model`).
- **Constitution Principle II**: DTOs strictly Java Records; no JPA entity leakage.
- **Constitution Principle III**: Uniform `@RestControllerAdvice` error responses.
- **Constitution Principle IV**: 100% offline Docker execution (`--network none`, `mvn test -o`).
- **Constitution Principle V**: Strict hard cap of 3 self-repair attempts; transition to `BLOCKED` upon exhaustion.
- **Constitution Principle VI**: Zero secrets persisted; ephemeral API keys handled in memory via `X-LLM-API-Key`.

---

## Constitution Check

*GATE: Post-design evaluation against Constitution v1.1.0.*

| Constitutional Principle | Requirement | Plan Compliance Status | Verification Mechanism |
|:---|:---|:---:|:---|
| **I. Arquitectura en Capas Estricta** | Reparaciones nunca deben violar la separación de 4 capas. | **PASS** | `CodeComplianceAnalyzer` valida estáticamente que controladores no llamen repositorios ni entidades directamente. |
| **II. Contratos Inmutables y Validación** | DTOs inmutables como Records con validación Jakarta. | **PASS** | Verificación estática rechaza parches que reemplacen Records con clases mutables o eliminen validaciones. |
| **III. Manejo Centralizado de Excepciones** | Sin bloques try-catch ad-hoc en controladores; uso de `@RestControllerAdvice`. | **PASS** | Analizador estático verifica que errores sigan el manejador global. |
| **IV. Determinismo Offline-First** | Ejecución de tests hermética en sandbox sin red. | **PASS** | `DockerRunner` ejecuta con `--network none` y caché `.m2` de solo lectura. |
| **V. Quality Gates y Límite de 3 Intentos** | 100% de tests aprobados; máximo 3 iteraciones; bloqueo si persiste. | **PASS** | Contador estricto de iteraciones en `TestAnalysisService`; transiciona a `BLOCKED` al fallar el 3er intento. |
| **VI. Seguridad de Secretos y Frontera de IA** | Cero claves API persistidas en disco o repositorio. | **PASS** | Tokens manejados en memoria; llamadas a LLM desacopladas del código Java generado. |

---

## Project Structure

### Documentation (this feature)

```text
specs/005-automated-tests-analysis/
├── spec.md              # Feature specification & clarifications
├── plan.md              # Implementation plan (this file)
├── research.md          # Technical research & decisions (Phase 0)
├── data-model.md        # Schemas & sequence diagram (Phase 1)
├── quickstart.md        # End-to-end runnable validation scenarios (Phase 1)
├── contracts/
│   └── tests-analysis-api.yaml # OpenAPI 3.0 contract for tests & repair API (Phase 1)
└── checklists/
    └── requirements.md  # Quality verification checklist
```

### Source Code Touchpoints

```text
backend/
├── app/
│   ├── main.py                         # Mount tests router (/api/v1/tests)
│   ├── api/
│   │   ├── routes_tests.py             # POST /synthesize, POST /analyze, POST /repair, GET /repairs, POST /manual-repair
│   │   └── routes_session.py           # Emit SSE events for TEST_SYNTHESIS and SELF_REPAIR_LOOP phases
│   ├── models/
│   │   ├── test_analysis.py            # Schemas: TestSuiteDefinition, FailureDiagnostic, CodeRepairPatch, RepairIterationRecord
│   │   └── __init__.py                 # Export new test analysis models
│   └── services/
│       ├── test_analysis_service.py    # Test generator (Mockito/@SpringBootTest), failure parser, compliance analyzer, repair planner
│       └── repair_parser.py            # Granular Maven Surefire and compiler diagnostic extractor
└── tests/
    ├── test_test_analysis_service.py   # Unit tests for test synthesis, diagnostics extraction, compliance, and surgical patching
    └── test_routes_tests.py            # Contract tests for /synthesize, /analyze, /repair, /manual-repair, and 3-attempt limit

frontend/
├── app.py                              # Update tab state flow and session handling
└── views/
    ├── monitor_view.py                 # Live terminal and status indicators for TEST_SYNTHESIS, SELF_REPAIR_LOOP, and BLOCKED state
    └── explorer_view.py                # Test Suite tree explorer, repair diff viewer, and in-browser manual code editor for BLOCKED sessions
```

---

## Complexity Tracking

*No constitutional violations. Zero unwarranted complexity. All 3 repair attempts strictly bounded.*
