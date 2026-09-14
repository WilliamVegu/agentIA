# Research & Technical Decisions: Security Vulnerability Auditing & Code Quality Standards

**Feature**: `006-security-quality-audit`  
**Date**: 2026-09-13  
**Status**: Completed  

---

## 1. Static Application Security Testing (SAST) Engine

### Decision
Implement a native, deterministic Static Application Security Testing (SAST) rule engine inside the FastAPI backend (`backend/app/services/security_service.py`), leveraging regex pattern matching and Java syntax tokenization.

### Rationale
- **Sub-Second Latency**: Executing inside the Python backend achieves full codebase scanning in under 500ms, eliminating the 10–20 second JVM cold-start latency of external Java analysis tools.
- **Hermetic & Self-Contained**: Operates without external binary dependencies or network calls, perfectly adhering to Constitution Principle IV (`--network none`).
- **Targeted OWASP Top 10 Coverage**: Custom-tailored rules specifically tuned to Spring Boot 3.x and Java 21 LTS:
  - SQL Injection (string concatenation in `@Query`, raw `EntityManager.createNativeQuery`).
  - Command / Path Traversal Injection (unsanitized `File`, `Paths.get`, `ProcessBuilder`).
  - Sensitive Data Exposure in Logs / Error Handlers (logging passwords, credit cards, or throwing raw stack traces).
  - Insecure Deserialization (use of Java native serialization or unrestricted ObjectInputStreams).
  - Missing Jakarta Validation (`@Valid` omitted in controller request body arguments).

### Alternatives Considered
- **SpotBugs / SonarQube CLI in Docker Sandbox**: Heavyweight; requires downloading and caching large analyzer plugins in the Docker image, increasing build times and disk footprint by >300MB.
- **LLM-Only Security Review**: Non-deterministic, expensive in tokens, potential hallucinations, and violates offline-first guarantees when external keys are unavailable.

---

## 2. Dependency Vulnerability Auditing (SCA) in Hermetic Mode

### Decision
Bundle a local, curated CVE dictionary (`backend/app/resources/cve_database.json`) containing known vulnerable Maven artifacts, version ranges, CVSS scores, and safe upgrade targets.

### Rationale
- **Constitution Principle IV Compliance**: External network queries to NVD, OSS Index, or GitHub Advisory Database are impossible under `--network none`.
- **Zero-Latency Auditing**: Parsing `pom.xml` dependencies and comparing against an indexed in-memory dictionary takes <50ms.
- **Actionable Upgrades**: Each CVE finding includes the exact safe version tag to recommend for immediate remediation.

### Alternatives Considered
- **OWASP Dependency-Check Maven Plugin**: Requires downloading 200MB+ NVD database dumps at build time or mounting a persistent volume, which breaks hermetic reproducible sandboxing.
- **Online CVE Lookup API**: Rejected per user clarification (Option A: 100% offline hermetic database).

---

## 3. Secret Leak Detection & Hardcoded Credential Scanner

### Decision
Deploy high-entropy pattern matching for sensitive credentials and API keys across source code, configuration files (`application.yml`, `application.properties`), Dockerfiles, and scripts.

### Rationale
- **Enforces Constitution Principle VI**: Zero secrets in repositories or configuration.
- **Comprehensive Pattern Signatures**:
  - JWT tokens (`eyJ...`).
  - OpenAI / Anthropic / AI API Keys (`sk-...`).
  - AWS Access Keys & Secrets (`AKIA...`).
  - GitHub Personal Access Tokens (`ghp_...`, `github_pat_...`).
  - Generic private keys (`-----BEGIN PRIVATE KEY-----`).
  - Database connection passwords in plaintext.

### Alternatives Considered
- **TruffleHog / GitGuardian CLI Integration**: External binary requirement with high overhead for microservices created dynamically in memory.

---

## 4. Architectural & Code Quality Standards Evaluation

### Decision
Implement an automated architectural compliance checker enforcing Constitution Principles I, II, III and Clean Code / SonarQube quality benchmarks.

### Rationale
- **Principle I: Layer Isolation**: Confirms `controller` ➔ `service` ➔ `repository` ➔ `model`. Detects illegal controller imports of repositories or JPA entities.
- **Principle II: DTO Immutability**: Verifies all classes in `dto/` packages are Java Records. Flags mutable classes or JPA entities used in controllers.
- **Principle III: Centralized Errors**: Asserts presence of `@RestControllerAdvice` handling `MethodArgumentNotValidException`, `ResourceNotFoundException`, and generic exceptions with `ProblemDetails` (RFC 7807) format.
- **Stack Rules: Lombok Restraints**: Flags prohibited `@Data`, `@Value`, or `@SneakyThrows` annotations.
- **Quality Metrics Thresholds**:
  - Cyclomatic Complexity: $\le 10$ per method (SonarQube standard).
  - Method Length: $\le 50$ lines of code per method.
  - Code Duplication: $\le 3\%$ across service and controller implementations.
  - Class Coupling: $\le 15$ efferent dependencies.

### Alternatives Considered
- **Checkstyle / PMD Maven Plugins**: Require maintaining complex XML configs and can produce hundreds of stylistic false positives. Native AST tokenization focuses strictly on architectural and security rules.

---

## 5. Quality Gate Enforcement & Export Blocking

### Decision
A composite Quality Gate algorithm computes an overall status:
- **`BLOCKED`**: Triggered if any `CRITICAL` or `HIGH` security vulnerability, secret leak, or Constitution Principle violation is detected. **Blocks artifact export (ZIP) and Git publication**.
- **`WARNING`**: Triggered if only `MEDIUM` or `LOW` code smells or minor metric threshold exceedances exist. Allows export with visible notification.
- **`PASS`**: Code has zero security flaws, complies with all constitutional rules, and respects quality thresholds.

### Rationale
- Guarantees that defective or insecure microservices cannot accidentally be packaged or published to production repositories.

### Alternatives Considered
- **Non-Blocking Advisory Mode**: Rejected per user clarification (Option A: Strict blocking enforcement).

---

## 6. Hybrid Remediation Mechanism

### Decision
Provide two complementary remediation pathways:
1. **1-Click Surgical Auto-Fix**: Deterministic code patches for known patterns:
   - Converting class DTOs to Java Records.
   - Replacing prohibited `@Data` with `@Getter @Setter @Builder @NoArgsConstructor @AllArgsConstructor`.
   - Adding missing `@Valid` to controller parameters.
   - Parameterizing concatenated SQL queries.
2. **In-Browser Code Editor with AI Assistance**: Embedded in the Streamlit Web Studio (Tab 5) for complex logical or architectural modifications.

### Rationale
- Automates tedious boilerplate fixes while allowing developers full control over business logic refactoring.

