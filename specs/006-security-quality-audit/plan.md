# Implementation Plan: Security Vulnerability Auditing & Code Quality Standards

**Branch**: `006-security-quality-audit` | **Date**: 2026-09-13 | **Spec**: [specs/006-security-quality-audit/spec.md](file:///c:/Users/willi/Downloads/agentIA/specs/006-security-quality-audit/spec.md)

**Input**: Feature specification from `specs/006-security-quality-audit/spec.md` ("el sistema debe revisar vulnerabilidades y problemas de seguridad y evaluar calidad y estándares.")

---

## Summary

This feature equips the Autonomous Java 21 / Spring Boot 3.x Microservice Engineering Platform with comprehensive Static Application Security Testing (SAST), Secret Leak Detection, hermetic Software Composition Analysis (SCA), and architectural/maintainability quality auditing. 

The implementation introduces a high-speed (<1s) deterministic Python-native AST and pattern-matching engine in the FastAPI backend (`backend/app/services/security_service.py`), supported by a local pre-cached CVE database (`backend/app/resources/cve_database.json`) adhering to Constitution Principle IV (`--network none`). An overarching Quality Gate engine computes a composite verdict (`PASS`, `WARNING`, `BLOCKED`) that strictly prevents artifact export (ZIP) and Git branch publication if `CRITICAL` or `HIGH` vulnerabilities or constitutional violations are present. Users inspect issues and apply 1-click surgical patches in a dedicated subtab ("🛡️ Auditoría de Seguridad & Calidad") inside Tab 5 of the Streamlit Web Studio.

---

## Technical Context

**Language/Version**: Python 3.11+ (FastAPI backend & Streamlit frontend); Audited Target: Java 21 LTS / Spring Boot 3.x microservices.

**Primary Dependencies**:
- Backend: FastAPI, Pydantic v2, Uvicorn, Python standard libraries (`re`, `json`, `pathlib`, `ast`, `difflib`).
- Frontend: Streamlit, Requests.
- Offline Security Resource: Embedded `cve_database.json` for Maven dependency CVE lookups.

**Storage**:
- SQLite (`sessions.db`) for generation session tracking and Quality Gate verdict persistence.
- Session workspace directories (`workspaces/{session_id}/`) containing generated Java source files and `pom.xml`.
- Pre-cached local vulnerability database in `backend/app/resources/cve_database.json`.

**Testing**: Pytest (`python -m pytest backend/tests -o pythonpath=backend`), asserting 100% test pass rate with coverage across SAST patterns, secret regexes, CVE matching, Quality Gate enforcement, and API contracts.

**Target Platform**: Windows, Linux, and Docker containerized sandboxes with `--network none`.

**Project Type**: Web Service (FastAPI REST API) + Web Application (Streamlit UI).

**Performance Goals**:
- Full security & quality audit execution: < 1.0 second for standard microservices (up to 30 classes).
- CVE dependency lookup: < 50 milliseconds.
- Quality Gate export blocking evaluation: < 10 milliseconds.
- Streamlit subtab rendering: < 1.5 seconds.

**Constraints**:
- 100% Offline Hermetic Operation: Zero outbound network calls during scanning (Constitution Principle IV).
- Zero Hardcoded Secrets: No credentials or tokens persisted to disk or logs (Constitution Principle VI).
- Strict Quality Gate Blocking: `CRITICAL` and `HIGH` findings prohibit export and Git publishing.
- Non-Destructive Auditing: Source code is modified only when explicit user-initiated remediation is invoked.

**Scale/Scope**: Microservices up to 50 classes / 10,000 LOC per session; instant feedback in interactive Web Studio.

---

## Constitution Check

*GATE: All principles verified against `.specify/memory/constitution.md`.*

| Principle | Relevance & Impact on Feature | Status |
|-----------|-------------------------------|--------|
| **I. Strict Layering** | The architecture auditor checks Java code for unidirectional flow (`controller` ➔ `service` ➔ `repository` ➔ `model`). Detects illegal direct imports/calls from controller to repository or JPA entities. | **PASS** |
| **II. Immutable DTOs & Validation** | The auditor validates that all classes in `dto/` are Java Records with Jakarta validation (`@NotNull`, `@NotBlank`, etc.) and flags any JPA entity exposed in controllers. | **PASS** |
| **III. Centralized Error Handling** | The auditor verifies the presence of `@RestControllerAdvice` producing RFC 7807 `ProblemDetails` or `ApiErrorRecord`, and flags forbidden ad-hoc `try-catch` blocks in controllers. | **PASS** |
| **IV. Offline Determinism & Sandbox** | SCA dependency scanning uses a local embedded `cve_database.json` without external network queries, fully compliant with `--network none`. | **PASS** |
| **V. Quality Gates & Auto-Repair** | Computes `QualityGateVerdict` (`PASS`, `WARNING`, `BLOCKED`). Automatically blocks ZIP export and Git publish on `CRITICAL`/`HIGH` issues. Provides 1-click surgical auto-repair patches for common violations. | **PASS** |
| **VI. Zero Secrets & Orchestrator Boundary** | High-entropy secret scanner flags API keys (OpenAI, Anthropic, AWS, JWT, GitHub tokens) in source, properties, Dockerfiles, and scripts. Protects runtime secrets. | **PASS** |

**GATES RESULT**: **PASS**. No constitutional violations. Fully compliant.

---

## Project Structure

### Documentation (this feature)

```text
specs/006-security-quality-audit/
├── plan.md              # This implementation plan (/speckit-plan output)
├── research.md          # Technical decisions: SAST, SCA, Secrets, Clean Code (/speckit-plan output)
├── data-model.md        # Schemas & Mermaid class/sequence diagrams (/speckit-plan output)
├── quickstart.md        # 5 runnable end-to-end validation scenarios (/speckit-plan output)
├── contracts/           # API interface specifications (/speckit-plan output)
│   └── security-quality-api.yaml # OpenAPI 3.0 specification for /api/v1/security/* & audit
└── checklists/
    └── requirements.md  # 16/16 requirements validation checklist
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── api/
│   │   ├── routes_security.py          # [NEW] Endpoints: /api/v1/security/audit, /api/v1/security/remediate, /api/v1/sessions/{id}/audit
│   │   ├── routes_publish.py           # [MODIFY] Enforce Quality Gate blocking check on /export and /publish
│   │   └── ... (existing routers)
│   ├── models/
│   │   ├── security_quality.py         # [NEW] Pydantic models: SecurityVulnerabilityFinding, StandardsComplianceViolation, CodeQualityMetrics, QualityGateVerdict, SecurityQualityAuditReport
│   │   └── ... (existing models)
│   ├── resources/
│   │   └── cve_database.json           # [NEW] Curated offline CVE database for Maven/Spring Boot artifacts
│   ├── services/
│   │   ├── security_service.py         # [NEW] SAST rule engine, Secret scanner, SCA CVE checker, Architecture compliance, Code metrics, 1-click surgical repair
│   │   └── ... (existing services)
│   └── main.py                         # [MODIFY] Register routes_security router
└── tests/
    ├── test_security_service.py        # [NEW] Unit tests for SAST, secrets, SCA, architecture, metrics, and remediation
    ├── test_routes_security.py         # [NEW] Contract & endpoint tests for security routes and Quality Gate blocking
    └── ... (existing 65 passing tests)

frontend/
├── views/
│   ├── explorer_view.py                # [MODIFY] Subtab '🛡️ Auditoría de Seguridad & Calidad' in Tab 5 with metrics, badges, finding cards & 1-click auto-repair
│   └── ... (existing views)
└── app.py                              # Main Streamlit application
```

**Structure Decision**: Web application layout integrating into existing FastAPI backend and Streamlit frontend. Adds dedicated security domain models, resources, services, and API routes while guarding export touchpoints in `routes_publish.py`.

---

## Source Code Touchpoints & Implementation Details

1. **`backend/app/models/security_quality.py` [NEW]**:
   - Enumerations: `QualityGateStatus` (`PASS`, `WARNING`, `BLOCKED`), `SeverityLevel` (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`), `VulnerabilityCategory` (`SAST_INJECTION`, `SAST_DESERIALIZATION`, `SAST_ACCESS_CONTROL`, `SAST_DATA_EXPOSURE`, `SECRET_LEAK`, `CVE_DEPENDENCY`), `ConstitutionPrinciple`.
   - Models: `SecurityVulnerabilityFinding`, `StandardsComplianceViolation`, `CodeQualityMetrics`, `QualityGateVerdict`, `SecurityQualityAuditReport`, `RemediationRequest`, `RemediationResponse`.

2. **`backend/app/resources/cve_database.json` [NEW]**:
   - Curated dictionary of Maven dependency coordinates, vulnerable version ranges, CVE identifiers, CVSS scores, descriptions, and recommended safe versions (e.g., `org.yaml:snakeyaml`, `org.springframework:spring-webmvc`, `com.fasterxml.jackson.core:jackson-databind`, `ch.qos.logback:logback-core`, `org.apache.tomcat.embed:tomcat-embed-core`).

3. **`backend/app/services/security_service.py` [NEW]**:
   - `scan_sast_and_secrets(files: dict[str, str]) -> tuple[list[SecurityVulnerabilityFinding], list[StandardsComplianceViolation]]`: Scans Java source code, `application.yml`/`.properties`, scripts, and Dockerfiles for OWASP Top 10 vulnerabilities (SQL injection, path traversal, missing `@Valid`, insecure deserialization, sensitive logging) and hardcoded secrets (JWT, OpenAI, AWS, GitHub PATs, private keys).
   - `scan_dependencies_cve(pom_content: str) -> list[SecurityVulnerabilityFinding]`: Parses XML dependencies from `pom.xml` and compares against `cve_database.json`.
   - `evaluate_architecture_and_metrics(files: dict[str, str]) -> tuple[list[StandardsComplianceViolation], CodeQualityMetrics]`: Enforces Constitution Principles I (layering), II (Records DTOs), III (`@RestControllerAdvice`), Lombok constraints (no `@Data`, `@Value`, `@SneakyThrows`), and calculates cyclomatic complexity (threshold $\le 10$), method lines (threshold $\le 50$), and duplication (threshold $\le 3\%$).
   - `evaluate_quality_gate(vulnerabilities: list, violations: list, metrics: CodeQualityMetrics) -> QualityGateVerdict`: Computes status (`BLOCKED` if any `CRITICAL` or `HIGH` security flaw or constitution violation; `WARNING` if only `MEDIUM`/`LOW`; `PASS` otherwise), overall score (0-100), and `canExport` boolean.
   - `audit_workspace(workspace_dir: str, session_id: str, service_name: str) -> SecurityQualityAuditReport`: Orchestrates complete scan of workspace files.
   - `apply_surgical_remediation(finding_id: str, file_path: str, source_code: str) -> tuple[str, str]`: Generates targeted code patch (e.g. converting class DTO to Record, parameterizing query, replacing `@Data` with permitted Lombok annotations, adding `@Valid`).

4. **`backend/app/api/routes_security.py` [NEW]**:
   - `POST /api/v1/security/audit`: Run direct in-memory audit on provided source files and `pom.xml`.
   - `GET /api/v1/sessions/{session_id}/audit`: Retrieve or execute audit report for a persisted workspace session.
   - `POST /api/v1/security/remediate`: Execute 1-click surgical auto-repair patch on a specified finding.

5. **`backend/app/main.py` [MODIFY]**:
   - Register `routes_security.router` with prefix `/api/v1`.

6. **`backend/app/api/routes_publish.py` [MODIFY]**:
   - In `export_session_project` and `publish_session_project`, invoke `security_service.audit_workspace(...)` to verify `QualityGateVerdict.canExport`. If `False`, return HTTP 403 Forbidden with detailed blocking reasons.

7. **`frontend/views/explorer_view.py` [MODIFY]**:
   - Add subtab `🛡️ Auditoría de Seguridad & Calidad` inside Tab 5 (`🔍 5. Explorador de Código, Tests & Auto-Reparación`).
   - Display overall Quality Gate banner (`PASS` in green, `WARNING` in orange, `BLOCKED` in red).
   - Display score cards (Security Rating A-F, Compliance %, Vulnerability count by severity).
   - Display categorized finding accordions with code snippets, line numbers, and 1-click auto-repair buttons.
   - Display Clean Code / Maintainability metrics table.

8. **`backend/tests/test_security_service.py` & `backend/tests/test_routes_security.py` [NEW]**:
   - Comprehensive test suite covering SAST patterns, secret detection, CVE matching, Quality Gate computation, export blocking guard, and surgical patching.

---

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*No violations detected. Zero entries required.*
