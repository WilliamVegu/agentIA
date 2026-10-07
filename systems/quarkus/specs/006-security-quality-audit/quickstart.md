# Quickstart Validation Guide: Security Vulnerability Auditing & Code Quality Standards

**Feature**: `006-security-quality-audit`  
**Date**: 2026-09-13  
**Status**: Ready for Validation  

This guide provides end-to-end runnable validation scenarios demonstrating Static Application Security Testing (SAST), secret leak detection, hermetic dependency CVE scanning, architectural compliance checks, Quality Gate enforcement, and 1-click surgical remediation.

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
- **Hermetic execution environment**: Zero external network calls required (`--network none` compliant).

---

## 2. Validation Scenarios

### Scenario 1: Clean Microservice Security & Quality Audit
**Goal**: Verify that a correctly synthesized microservice passes all security and constitutional standards with a `PASS` Quality Gate verdict and high quality score.

1. Submit a valid microservice codebase with immutable Java Records, parameterized queries, and `@RestControllerAdvice`.
2. Call `POST /api/v1/security/audit`.
3. **Expected Outcome**:
   - HTTP 200 OK.
   - `qualityGate.status` equals `PASS`.
   - `qualityGate.canExport` is `true`.
   - `vulnerabilities` count is 0.
   - `violations` count is 0.
   - `metrics.averageCyclomaticComplexity` is $\le 3.0$.

---

### Scenario 2: Detection & Blocking of SQL Injection and Hardcoded Secrets
**Goal**: Verify that deliberate security vulnerabilities and secret leaks are detected and immediately transition the Quality Gate to `BLOCKED`.

1. Submit source files containing:
   - A hardcoded OpenAI key `sk-proj-abc12345678901234567890` in `application.yml`.
   - Dynamic SQL string concatenation `@Query("SELECT o FROM Order o WHERE o.name = '" + name + "'")` in a repository.
2. Call `POST /api/v1/security/audit`.
3. **Expected Outcome**:
   - HTTP 200 OK.
   - `qualityGate.status` equals `BLOCKED`.
   - `qualityGate.canExport` is `false`.
   - `vulnerabilities` contains:
     - `SECRET_LEAK` finding with severity `CRITICAL` (Principle VI violation).
     - `SAST_INJECTION` finding with severity `HIGH` (CWE-89).

---

### Scenario 3: Hermetic Dependency CVE Auditing
**Goal**: Verify that vulnerable dependencies in `pom.xml` are flagged using the local pre-cached CVE database without network access.

1. Submit a `pom.xml` containing a vulnerable dependency coordinate (e.g. `org.yaml:snakeyaml:1.30` affected by CVE-2022-25857).
2. Call `POST /api/v1/security/audit`.
3. **Expected Outcome**:
   - `vulnerabilities` contains a `CVE_DEPENDENCY` entry detailing the CVE, CVSS score (7.5+), and safe remediation version (`snakeyaml:2.0+`).
   - Zero outbound HTTP network calls are made.

---

### Scenario 4: Quality Gate Enforcement Blocking Export
**Goal**: Verify that sessions with a `BLOCKED` Quality Gate verdict are prevented from downloading ZIP artifacts or publishing to Git.

1. Trigger an export request for a blocked session: `GET /api/v1/sessions/{blockedSessionId}/export`.
2. **Expected Outcome**:
   - HTTP 403 Forbidden or 422 Unprocessable Entity.
   - Error response states: `Cannot export artifact: Quality Gate is BLOCKED due to unresolved critical security or constitutional violations.`

---

### Scenario 5: 1-Click Surgical Remediation & Quality Gate Clearance
**Goal**: Verify that auto-fixable violations are corrected with surgical patches, successfully clearing the Quality Gate.

1. Call `POST /api/v1/security/remediate` with:
   - `findingId`: `CONST-VIOL-LOMBOK` (or DTO record violation).
   - `filePath`: `src/main/java/com/corp/order/model/Order.java`.
2. **Expected Outcome**:
   - HTTP 200 OK.
   - Prohibited `@Data` is replaced with `@Getter @Setter @Builder @NoArgsConstructor @AllArgsConstructor`.
   - Unified diff returned.
   - Re-evaluating the audit transitions `qualityGate.status` to `PASS`, enabling export.

