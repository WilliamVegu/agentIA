# Feature Specification: Security Vulnerability Auditing & Code Quality Standards Evaluation

**Feature Branch**: `006-security-quality-audit`

**Created**: 2026-09-13

**Status**: Draft

**Input**: User description: "el sistema debe revisar vulnerabilidades y problemas de seguridad y evaluar calidad y estándares."

---

## Overview

Following autonomous scaffolding, component generation, relational persistence design, and automated test execution, the microservice engineering platform must ensure that synthesized code complies with strict enterprise security benchmarks and institutional quality standards. 

This feature provides **Static Application Security Testing (SAST)**, **Software Composition Analysis (SCA)**, **Secret Leak Detection**, and **Architectural & Code Quality Standards Evaluation** with a unified Quality Gate dashboard before code is approved for export or production Git publishing.

---

## Clarifications

### Session 2026-09-13
- Q: ¿Dónde debe ejecutarse y cómo debe implementarse el motor de análisis estático de seguridad (SAST) y detección de secretos? (FR-001) → A: Motor nativo en el backend FastAPI utilizando análisis AST y reglas estructuradas de patrones (OWASP Top 10, inyecciones, tokens/secretos) para evaluación instantánea (<1s) sin sobrecarga de arranque de la JVM.
- Q: ¿Qué umbrales específicos deben activar advertencias o fallos de mantenibilidad en la complejidad ciclomática y longitud de métodos? (FR-006) → A: Estándar Clean Code/SonarQube: Complejidad ciclomática ≤ 10 por método, longitud ≤ 50 líneas por método y duplicación ≤ 3%. Métodos que excedan estos umbrales generan advertencias de mantenibilidad en el Quality Gate.
- Q: ¿En qué ubicación de la interfaz de Streamlit debe integrarse el panel del Quality Gate y la auditoría de seguridad? (FR-011) → A: Como subpestaña dedicada ('🛡️ Auditoría de Seguridad & Calidad') dentro de la Pestaña 5 ('🔍 5. Explorador de Código, Tests & Auto-Reparación'), consolidando la inspección de artefactos, suites de pruebas, historial de reparaciones y auditoría en un único centro de observabilidad.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Static Application Security Testing (SAST) & Secret Detection (Priority: P1) 🎯 MVP

As a security engineer or developer, I want the system to automatically analyze generated source code for security vulnerabilities, injection risks, and credential leaks, so that every synthesized microservice is protected against OWASP Top 10 vulnerabilities before deployment.

**Why this priority**: Fundamental requirement for software trust and compliance. Code that functions correctly and passes functional tests may still harbor dangerous security vulnerabilities (such as SQL injection, insecure deserialization, or exposed credentials violating Constitution Principle VI).

**Independent Test**: Can be tested independently by submitting microservice source files with deliberate security defects (e.g. dynamic SQL concatenation, hardcoded API keys, unvalidated path parameters, or missing `@Valid` annotations), calling the security inspection engine, and verifying that all vulnerabilities are identified with precise line locations and severity ratings.

**Acceptance Scenarios**:

1. **Given** generated Java source files, **When** static security analysis runs, **Then** the system detects any hardcoded secrets, API tokens, passwords, or private keys, classifying them as `CRITICAL` violations per Constitution Principle VI.
2. **Given** controller and repository classes, **When** security analysis runs, **Then** the system flags SQL injection risks (e.g. string concatenation in `@Query`), path traversal risks, and unvalidated input payloads lacking Jakarta validation constraints.
3. **Given** Spring Boot configuration files, **When** security analysis runs, **Then** the system audits sensitive properties, verifying that SSL/TLS, secure cookie flags, and restrictive CORS headers are properly defined.

---

### User Story 2 - Dependency Vulnerability & Software Composition Analysis (Priority: P1)

As a DevOps engineer or release manager, I want the system to inspect third-party dependencies in `pom.xml` for known CVEs and outdated libraries, so that no vulnerable transitive dependencies enter the deployment pipeline.

**Why this priority**: Over 80% of enterprise software vulnerabilities originate from third-party libraries. Evaluating dependency health is vital for production readiness and supply chain security.

**Independent Test**: Can be tested independently by analyzing a `pom.xml` file containing both secure and vulnerable dependency coordinates, verifying that known CVEs are surfaced with CVSS scores and upgrade recommendations without requiring live network calls in hermetic mode.

**Acceptance Scenarios**:

1. **Given** a generated `pom.xml`, **When** dependency vulnerability scanning is executed, **Then** the system checks declared and transitive dependencies against an offline security database of known CVEs.
2. **Given** a dependency with an active CVE, **When** the vulnerability report is generated, **Then** the report details the CVE identifier, CVSS severity score, affected artifact, and safe patch version.

---

### User Story 3 - Architectural Standards & Code Quality Assessment (Priority: P1)

As a lead architect or quality assurance engineer, I want the system to evaluate the microservice against strict architectural principles (4-layer unidirectional flow, Java Records for DTOs, centralized exception handling) and maintainability metrics, so that technical debt and architectural drift are prevented.

**Why this priority**: Preserves long-term code maintainability, clean architecture, and adherence to repository conventions and constitutional constraints.

**Independent Test**: Can be tested independently by submitting source code with architectural violations (e.g. controller calling repository directly, mutable classes used as DTOs, ad-hoc try-catch error bodies, Lombok `@Data` usage, or high cyclomatic complexity), verifying that the quality engine outputs structured violations and maintainability scores.

**Acceptance Scenarios**:

1. **Given** microservice source files, **When** architectural compliance evaluation runs, **Then** the system verifies strict unidirectional layering (`controller` ➔ `service` ➔ `repository` ➔ `model`) and flags any illegal cross-layer bypasses.
2. **Given** Request and Response DTOs, **When** compliance evaluation runs, **Then** the system validates that all DTOs are immutable Java Records and that JPA entities are never exposed in REST controllers.
3. **Given** service implementation classes, **When** code quality metrics are computed, **Then** the system measures cyclomatic complexity, method line count, cognitive complexity, and code duplication, flagging methods exceeding maintainability thresholds.

---

### User Story 4 - Quality Gate Dashboard & Actionable Remediation Guidance (Priority: P2)

As an engineering manager or lead developer, I want a centralized Security & Quality Gate dashboard in the web studio showing an executive summary, severity breakdown, and actionable remediation instructions, so that teams have clear visibility into code health and can resolve findings quickly.

**Why this priority**: Observability and human-in-the-loop decision-making. Provides stakeholders with clear pass/fail criteria and clear instructions on how to remediate detected issues.

**Independent Test**: Can be tested independently by navigating to the Security & Quality tab in the Streamlit Web Studio for a generated session, reviewing the Quality Gate verdict (`PASS`, `WARNING`, `FAIL`), inspecting categorized findings, and testing remediation actions.

**Acceptance Scenarios**:

1. **Given** an audited microservice session, **When** opening the Security & Quality view in the web studio, **Then** the user sees high-level health badges: Security Rating (A-F), Standards Compliance (%), Total Vulnerabilities by Severity, and Overall Quality Gate Status.
2. **Given** an identified security or standards issue, **When** the user expands the finding card, **Then** the system displays the code snippet, explanation of the risk, and exact step-by-step remediation guidance.
3. **Given** a session where the Quality Gate is blocked by critical findings, **When** the user reviews the audit, **Then** the system offers one-click automated remediation for standard patterns (e.g. replacing `@Data`, adding missing `@Valid`, or parameterizing dynamic queries).

---

### Edge Cases

- **Zero-Dependency or Minimal Codebase**: For microservices with minimal logic, the quality engine MUST NOT fail or report false positives; metrics must adapt gracefully to small codebases.
- **Offline / Air-Gapped Operation**: In alignment with Constitution Principle IV (`--network none`), CVE dependency auditing and SAST rule engines MUST operate 100% offline using a bundled or pre-cached vulnerability database.
- **False Positive Suppression**: If a developer intentionally employs a pattern flagged as a code smell, the system MUST support inline suppression annotations (e.g. `@SuppressWarnings("audit:...")`) with required justification comments.
- **Mixed Severity Findings**: When a scan produces both critical security flaws and low-severity formatting suggestions, the system MUST prioritize security and constitutional blocking issues over stylistic suggestions.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST perform Static Application Security Testing (SAST) on all generated Java 21 / Spring Boot 3.x source files using a native, deterministic rule engine in the FastAPI backend (AST parsing and structured pattern matching), checking for injection vulnerabilities (SQL, path traversal), insecure deserialization, broken access control, and sensitive data disclosure in under 1 second.
- **FR-002**: System MUST inspect source code, configuration files (`application.yml`, `application.properties`), and build scripts for hardcoded secrets, API tokens, passwords, and private keys, enforcing Constitution Principle VI.
- **FR-003**: System MUST scan microservice dependencies declared in `pom.xml` using a bundled local pre-cached CVE database to guarantee 100% offline hermetic execution in compliance with Constitution Principle IV (`--network none`).
- **FR-004**: System MUST classify all detected security findings by severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`) and map them to recognized industry taxonomies (CWE and OWASP Top 10).
- **FR-005**: System MUST evaluate architectural compliance against Constitution Principles:
  - *Principle I*: Strict 4-layer unidirectional communication (`controller` ➔ `service` ➔ `repository` ➔ `model`).
  - *Principle II*: DTOs MUST be immutable Java Records with declarative Jakarta Validation (`@NotNull`, `@NotBlank`, `@Size`, etc.); zero JPA entity leakage in controllers.
  - *Principle III*: Uniform exception handling via `@RestControllerAdvice`; prohibition of ad-hoc controller `try-catch` blocks returning custom error bodies.
  - *Stack Rules*: Strict prohibition of Project Lombok `@Data`, `@Value`, and `@SneakyThrows`.
- **FR-006**: System MUST calculate quantitative code maintainability metrics based on Clean Code / SonarQube benchmarks: cyclomatic complexity (threshold: ≤ 10 per method), method length (threshold: ≤ 50 lines), class coupling, and code duplication (threshold: ≤ 3%), flagging any method or class exceeding these thresholds as a maintainability warning in the Quality Gate.
- **FR-007**: System MUST evaluate test code quality, verifying assertion presence in every test method, mock independence, and test isolation.
- **FR-008**: System MUST compute a composite Quality Gate verdict (`PASS`, `WARNING`, `BLOCKED`) based on configurable thresholds and constitutional principles.
- **FR-009**: System MUST enforce Quality Gate policies by transitioning the session to `BLOCKED` and strictly preventing artifact export (ZIP) and Git branch publication whenever `CRITICAL` or `HIGH` security vulnerabilities or Constitution violations are detected, until all blocking issues are resolved.
- **FR-010**: System MUST generate a structured audit report (`SecurityQualityAuditReport`) accessible via REST API (`GET /api/v1/sessions/{id}/audit`).
- **FR-011**: System MUST integrate an interactive Security & Quality audit panel as a dedicated subtab ('🛡️ Auditoría de Seguridad & Calidad') within Tab 5 ('🔍 5. Explorador de Código, Tests & Auto-Reparación') of the Streamlit Web Studio, displaying ratings (A-F), categorized finding cards, and syntax-highlighted code evidence.
- **FR-012**: System MUST provide a hybrid remediation mechanism supporting both 1-click surgical auto-repair patches for common standard patterns (e.g. converting mutable DTO classes to immutable Java Records, eliminating prohibited Lombok `@Data`, adding missing Jakarta `@Valid` annotations, and parameterizing dynamic queries) and an in-browser code editor with AI assistance for complex custom logic.
- **FR-013**: System MUST operate completely offline during sandbox execution, utilizing pre-cached rules and dictionaries without external network dependencies.
- **FR-014**: System MUST process all security evaluations in memory using ephemeral API keys when LLM-assisted analysis is utilized, persisting zero credentials or sensitive code to external storage.

---

### Key Entities *(include if feature involves data)*

- **SecurityVulnerabilityFinding**: Represents an identified security issue (id, title, category: `SAST_VULNERABILITY`, `SECRET_LEAK`, `CVE_DEPENDENCY`, cweId, owaspCategory, severity: `CRITICAL` | `HIGH` | `MEDIUM` | `LOW`, filePath, lineNumber, codeSnippet, description, remediationGuidance).
- **StandardsComplianceViolation**: Represents an architectural or quality violation (id, principle: `CONSTITUTION_I` | `CONSTITUTION_II` | `CONSTITUTION_III` | `LOMBOK_RESTRICTION` | `CODE_COMPLEXITY`, severity, filePath, offendingElement, ruleDescription, suggestedFix).
- **CodeQualityMetrics**: Quantitative metrics for the codebase (averageCyclomaticComplexity, maxCyclomaticComplexity, totalCodeSmells, linesOfCode, duplicationPercentage, testAssertionDensity).
- **QualityGateVerdict**: The overall governance decision (status: `PASS` | `WARNING` | `BLOCKED`, score: 0-100, blockingIssuesCount, warningsCount, evaluatedAt, canExport).
- **SecurityQualityAuditReport**: Comprehensive audit record aggregating vulnerabilities, standards violations, code metrics, and Quality Gate verdict for a generation session.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Complete security and quality audit execution completes in under 15 seconds for microservices with up to 20 classes.
- **SC-002**: 100% of hardcoded secrets or API tokens matching common patterns (JWT, OpenAI, AWS, GitHub PATs) are detected prior to export.
- **SC-003**: 100% of Constitution Principle violations (DTOs as non-records, `@Data` usage, controller-to-repository calls) are identified with zero false negatives.
- **SC-004**: Quality Gate verdict correctly blocks 100% of microservices possessing `CRITICAL` security vulnerabilities from accidental export or Git publishing.
- **SC-005**: Users can inspect the full vulnerability breakdown, architectural violations, and remediation guidance in the Web Studio in under 2 clicks.
- **SC-006**: Automated security remediation resolves common standard violations (such as converting mutable DTOs to Java Records or removing `@Data`) with a single click.

---

## Assumptions

- **Pre-cached Vulnerability Database**: Dependency CVE auditing uses an embedded local database (e.g. curated list of known vulnerable Spring Boot / Maven dependencies) to comply with Constitution Principle IV (offline-first hermetic execution).
- **Standard Tool Parity**: Static code rules and security patterns emulate industry standards (SonarQube Java quality profile, SpotBugs, Checkstyle, and OWASP Top 10) implemented via native AST and regex parsers for deterministic execution.
- **Target Stack**: Analysis focuses on Java 21 LTS, Spring Boot 3.x, Maven, and Jakarta Validation.
- **Non-Destructive Auditing**: Security and quality scanning does not alter source files automatically unless an explicit user-initiated remediation action is triggered.

