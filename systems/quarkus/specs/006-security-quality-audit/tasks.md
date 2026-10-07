# Tasks: Security Vulnerability Auditing & Code Quality Standards

**Branch**: `006-security-quality-audit` | **Date**: 2026-09-13 | **Spec**: [specs/006-security-quality-audit/spec.md](file:///c:/Users/willi/Downloads/agentIA/specs/006-security-quality-audit/spec.md) | **Plan**: [specs/006-security-quality-audit/plan.md](file:///c:/Users/willi/Downloads/agentIA/specs/006-security-quality-audit/plan.md)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish security domain models, schemas, and offline vulnerability resources.

- [X] T001 Create security and quality data models and enums in `backend/app/models/security_quality.py` with `QualityGateStatus` (`PASS`, `WARNING`, `BLOCKED`), `SeverityLevel` (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`), `VulnerabilityCategory` (`SAST_INJECTION`, `SAST_DESERIALIZATION`, `SAST_ACCESS_CONTROL`, `SAST_DATA_EXPOSURE`, `SECRET_LEAK`, `CVE_DEPENDENCY`), `ConstitutionPrinciple`, `SecurityVulnerabilityFinding`, `StandardsComplianceViolation`, `CodeQualityMetrics`, `QualityGateVerdict`, and `SecurityQualityAuditReport`
- [X] T002 [P] Create curated offline CVE database resource in `backend/app/resources/cve_database.json` containing known vulnerable Maven artifacts (`org.yaml:snakeyaml`, `org.springframework:spring-webmvc`, `com.fasterxml.jackson.core:jackson-databind`, `ch.qos.logback:logback-core`, `org.apache.tomcat.embed:tomcat-embed-core`) with affected version ranges, CVSS scores, and safe upgrade targets

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core engine skeleton and API routing structure that all user stories depend on.

- [X] T003 Implement security service skeleton and Quality Gate scoring evaluator in `backend/app/services/security_service.py` implementing `evaluate_quality_gate` (`BLOCKED` on any `CRITICAL`/`HIGH` finding, `WARNING` on `MEDIUM`/`LOW`, `PASS` otherwise) and `audit_workspace`
- [X] T004 [P] Create FastAPI security router in `backend/app/api/routes_security.py` and register it in `backend/app/main.py` under prefix `/api/v1`

---

## Phase 3: User Story 1 - Static Application Security Testing (SAST) & Secret Detection (Priority: P1) 🎯 MVP

**Goal**: Automatically analyze generated Java source files, configuration files, and scripts for injection vulnerabilities (SQL, path traversal, missing `@Valid`), insecure deserialization, sensitive data logging, and hardcoded credentials/API keys.

**Independent Test**: Submit source files with deliberate security flaws (hardcoded OpenAI key `sk-...`, unparameterized `@Query` concatenation, missing `@Valid`), run audit, and verify all issues are flagged with precise line numbers and `CRITICAL`/`HIGH` severity.

### Tests for User Story 1
- [X] T005 [P] [US1] Unit and contract tests for SAST injection patterns and secret detection in `backend/tests/test_security_service.py`

### Implementation for User Story 1
- [X] T006 [P] [US1] Implement secret detection rules in `backend/app/services/security_service.py` scanning for high-entropy tokens, JWTs (`eyJ...`), OpenAI/Anthropic keys (`sk-...`), AWS credentials (`AKIA...`), GitHub PATs (`ghp_...`), private keys (`-----BEGIN PRIVATE KEY-----`), and plaintext passwords
- [X] T007 [US1] Implement SAST vulnerability scanner in `backend/app/services/security_service.py` detecting SQL injection in `@Query` and `EntityManager`, path traversal in `File`/`Paths.get`, unvalidated controller `@RequestBody` missing `@Valid`, insecure deserialization, and sensitive data exposure in logs
- [X] T008 [US1] Implement in-memory audit endpoint `POST /api/v1/security/audit` in `backend/app/api/routes_security.py` for direct code and configuration inspection

**Checkpoint**: User Story 1 is fully functional — SAST vulnerabilities and secrets are detected in sub-second execution.

---

## Phase 4: User Story 2 - Dependency Vulnerability & Software Composition Analysis (Priority: P1)

**Goal**: Inspect third-party dependencies in `pom.xml` against the local offline CVE database in compliance with Constitution Principle IV (`--network none`).

**Independent Test**: Analyze a `pom.xml` declaring a vulnerable dependency (e.g., `snakeyaml:1.30`), and verify that CVE-2022-25857 is reported with CVSS 7.5+ and safe upgrade recommendation `snakeyaml:2.0+` with zero external network requests.

### Tests for User Story 2
- [X] T009 [P] [US2] Unit tests for offline dependency CVE matching in `backend/tests/test_security_service.py`

### Implementation for User Story 2
- [X] T010 [US2] Implement `scan_dependencies_cve` in `backend/app/services/security_service.py` to parse XML dependencies from `pom.xml` and match artifact coordinates against `backend/app/resources/cve_database.json`
- [X] T011 [US2] Integrate dependency CVE scanning into `POST /api/v1/security/audit` and session workspace audit workflows in `backend/app/services/security_service.py`

**Checkpoint**: User Stories 1 and 2 work independently and concurrently without network access.

---

## Phase 5: User Story 3 - Architectural Standards & Code Quality Assessment (Priority: P1)

**Goal**: Evaluate microservices against strict architectural rules (4-layer unidirectional flow, Java Records DTOs, centralized exception handling, Lombok restrictions) and quantitative maintainability metrics (cyclomatic complexity $\le 10$, method length $\le 50$, duplication $\le 3\%$).

**Independent Test**: Submit source code with architectural bypasses (controller importing repository, non-record DTO, ad-hoc `try-catch`, Lombok `@Data`, or long/complex methods), and verify that structured violations and metrics are accurately generated.

### Tests for User Story 3
- [X] T012 [P] [US3] Unit tests for architectural compliance checks and maintainability metrics in `backend/tests/test_security_service.py`

### Implementation for User Story 3
- [X] T013 [P] [US3] Implement architectural compliance rules in `backend/app/services/security_service.py` enforcing Principle I (layering), Principle II (immutable Records in `dto/` with Jakarta validation), Principle III (`@RestControllerAdvice` presence, no custom controller `try-catch`), and Lombok restrictions (prohibiting `@Data`, `@Value`, `@SneakyThrows`)
- [X] T014 [US3] Implement quantitative code maintainability calculation in `backend/app/services/security_service.py` for cyclomatic complexity (threshold $\le 10$), method lines (threshold $\le 50$), duplication (threshold $\le 3\%$), and assertion density
- [X] T015 [US3] Implement session audit endpoint `GET /api/v1/sessions/{session_id}/audit` in `backend/app/api/routes_security.py` reading workspace files and returning the complete `SecurityQualityAuditReport`

**Checkpoint**: User Stories 1, 2, and 3 are fully operational, delivering comprehensive SAST, SCA, and architectural quality audits.

---

## Phase 6: User Story 4 - Quality Gate Dashboard & Actionable Remediation Guidance (Priority: P2)

**Goal**: Provide a centralized Quality Gate subtab in the Streamlit Web Studio (Tab 5), enforce strict export blocking (`BLOCKED` on `CRITICAL`/`HIGH` issues), and enable 1-click surgical auto-repair patches.

**Independent Test**: Verify that calling `GET /api/v1/sessions/{id}/export` on a session with `CRITICAL` or `HIGH` findings returns HTTP 403 with detailed rejection reasons, and verify that `POST /api/v1/security/remediate` applies surgical patches that clear the Quality Gate.

### Tests for User Story 4
- [X] T016 [P] [US4] Contract tests for Quality Gate export blocking and 1-click remediation in `backend/tests/test_routes_security.py` and `backend/tests/test_routes_publish.py`

### Implementation for User Story 4
- [X] T017 [US4] Implement surgical auto-repair patch generator in `backend/app/services/security_service.py` (`apply_surgical_remediation`) for converting class DTOs to Java Records, replacing prohibited `@Data` with permitted annotations, adding missing `@Valid`, and parameterizing dynamic queries
- [X] T018 [US4] Implement surgical remediation endpoint `POST /api/v1/security/remediate` in `backend/app/api/routes_security.py` returning unified diff and remediated code
- [X] T019 [US4] Implement Quality Gate export guard in `backend/app/api/routes_publish.py` verifying `QualityGateVerdict.canExport` before ZIP export and Git branch publication, returning HTTP 403 if `BLOCKED`
- [X] T020 [US4] Build interactive subtab `🛡️ Auditoría de Seguridad & Calidad` inside Tab 5 in `frontend/views/explorer_view.py` displaying Quality Gate status banner, score badges, categorized finding cards, syntax-highlighted code snippets, and 1-click auto-repair buttons

**Checkpoint**: All user stories complete — end-to-end security and quality auditing, export protection, and remediation are available via UI and API.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end scenario validation, full regression test execution, and documentation polishing.

- [X] T021 [P] Validate all 5 scenarios from `specs/006-security-quality-audit/quickstart.md` using the implemented endpoints
- [X] T022 Execute full backend pytest suite across all existing 65 tests plus new security tests ensuring 100% pass rate without regressions in `backend/tests/`
- [X] T023 [P] Add detailed docstrings and OpenAPI metadata to `backend/app/services/security_service.py` and `backend/app/api/routes_security.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — BLOCKS all user stories
- **User Stories (Phases 3–6)**: Depend on Phase 2 completion
  - US1 (Phase 3): Independent security/secret engine
  - US2 (Phase 4): Independent dependency scanner, integrates into audit pipeline
  - US3 (Phase 5): Independent architecture & metrics engine, integrates into audit pipeline
  - US4 (Phase 6): Integrates US1–US3 findings into UI dashboard, export blocking, and surgical auto-repair
- **Polish (Phase 7)**: Depends on all user stories being complete

```mermaid
graph TD
    Phase1[Phase 1: Setup Models & CVE DB] --> Phase2[Phase 2: Foundational Service & Router]
    Phase2 --> Phase3[Phase 3: US1 - SAST & Secrets]
    Phase2 --> Phase4[Phase 4: US2 - Hermetic SCA CVEs]
    Phase2 --> Phase5[Phase 5: US3 - Architecture & Quality]
    Phase3 --> Phase6[Phase 6: US4 - Quality Gate UI, Blocking & Remediation]
    Phase4 --> Phase6
    Phase5 --> Phase6
    Phase6 --> Phase7[Phase 7: Polish & Regression Tests]
```

---

## Parallel Execution Examples

### User Story 1
```bash
# Tests and rules can be prepared in parallel:
Task: "T005 [P] [US1] Unit and contract tests for SAST injection patterns and secret detection in backend/tests/test_security_service.py"
Task: "T006 [P] [US1] Implement secret detection rules in backend/app/services/security_service.py"
```

### User Story 2 & 3
```bash
# US2 and US3 models/rules can be developed concurrently once Foundation is complete:
Task: "T009 [P] [US2] Unit tests for offline dependency CVE matching in backend/tests/test_security_service.py"
Task: "T012 [P] [US3] Unit tests for architectural compliance checks and maintainability metrics in backend/tests/test_security_service.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)
1. Complete Phase 1: Models & offline CVE DB
2. Complete Phase 2: Foundational service & router
3. Complete Phase 3: SAST & secret scanner (MVP)
4. Validate detection of SQL injection and credentials via `POST /api/v1/security/audit`

### Incremental Delivery
1. **Increment 1 (MVP)**: SAST injection & secret detection active.
2. **Increment 2**: Offline dependency CVE scanning added without external network calls.
3. **Increment 3**: Architectural compliance (4 layers, Records DTOs) and Clean Code metrics added.
4. **Increment 4**: Quality Gate export guard active (`BLOCKED` prohibits ZIP/Git publish), Streamlit subtab live, and 1-click surgical auto-repair enabled.
5. **Increment 5**: Full validation of quickstart scenarios and zero regressions in existing test suite.
