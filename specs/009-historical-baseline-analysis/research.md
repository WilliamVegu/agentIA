# Research & Technical Decisions: Historical Baseline Analysis

**Feature**: Historical Baseline Analysis for AgentIA Skill Injection Pilot  
**Branch**: `009-historical-baseline-analysis`  
**Date**: 2026-09-25  

---

## 1. Database Access & Read-Only Safety

### Decision
Use Python's native `sqlite3` standard library with URI-based read-only mode (`mode=ro`) and `PRAGMA query_only = ON;`:
```python
conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
conn.execute("PRAGMA query_only = ON;")
conn.row_factory = sqlite3.Row
```

### Rationale
- **Filesystem & Engine Level Protection**: The SQLite C engine rejects any mutation attempt (`INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP`, `ALTER`) with `sqlite3.OperationalError: attempt to write a readonly database`.
- **Zero Third-Party Dependency Overhead**: Operates out-of-the-box on standard Python 3.10+ without requiring virtual environment activation, Pydantic, or SQLAlchemy.
- **Lock Contention Prevention**: Read-only connections do not obtain write locks (`EXCLUSIVE` or `RESERVED`), allowing the script to safely run concurrently alongside active studio sessions without blocking or deadlock.

### Alternatives Considered
- *SQLAlchemy Read-Only Session*: Requires `pydantic` and `sqlalchemy` installed in the active environment. Rejected to keep the standalone script fully runnable in environments without virtualenv activation.
- *File Copy to `/tmp` before reading*: Creates disk I/O overhead and potential security/stale data issues. Rejected because SQLite native read-only URI is completely safe.

---

## 2. Dynamic Schema Introspection & Graceful Fallbacks

### Decision
Introspect columns dynamically using `PRAGMA table_info(generation_sessions)` and access fields via `sqlite3.Row` dictionary semantics:
```python
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(generation_sessions)")
columns = {row["name"] for row in cursor.fetchall()}
```

### Rationale
- Different versions of `studio.db` across development branches may have optional columns (e.g. `current_lifecycle_phase`, `phase_progress_json`, `error_message`).
- Using dynamic column mapping avoids runtime `KeyError` or SQL syntax crashes on older database snapshots.

### Alternatives Considered
- *Static SQL query with fixed SELECT list*: Fails immediately if an older database lacks a column added in a later migration.

---

## 3. Log Parsing & Granular Error Taxonomy

### Decision
Combine regex extraction (aligned with `backend/app/services/repair_parser.py`) with domain-specific keyword scanners:
1. **Compilation Errors**:
   - Pattern: `r"\[ERROR\]\s+([^\s:]+\.java):\[(\d+),(\d+)\]\s+(.*)"`
   - Classifies missing symbols, package errors, syntax mismatches.
2. **Assertion & Test Failures**:
   - Pattern: `r"\[ERROR\]\s+([A-Za-z0-9_]+)\.([A-Za-z0-9_]+):(\d+)\s+(.*?)(?=\n\[|$)"`
   - Classifies test expectations vs. actual values.
3. **Candidate Domain Signatures**:
   - `jakarta_namespace`: `javax.persistence`, `javax.validation`, `javax.servlet`, `package javax.`
   - `layer_architecture`: `Repository.*Controller`, `Controller.*Repository`, `Entity.*Controller`, `Principle I`, `layer isolation`
   - `exception_handling`: `try-catch`, `@RestControllerAdvice`, `ProblemDetails`, `ApiErrorRecord`, `Principle III`
   - `maven_pom`: `pom.xml`, `Could not resolve dependencies`, `Non-resolvable parent POM`, `Plugin execution`, `Principle IV`
   - `mockito_tests`: `UnnecessaryStubbingException`, `ArgumentMismatch`, `Wanted but not invoked`, `Strictness.STRICT_STUBS`, `Cannot mock`

### Rationale
- Fast, fully deterministic, offline (conforming to Constitution Principle IV).
- Matches existing platform classifications while adding domain pattern isolation.

### Alternatives Considered
- *LLM-based log classifier*: Violates Constitution Principle IV (offline determinism) and Principle VI (zero external LLM API calls during verification), adds significant latency and token costs.

---

## 4. Candidate Domain Triage Decision Framework

### Decision
Classify each of the 5 candidate domains using an objective 3-tier empirical triage rubric:

| Triage Status | Criteria | Recommended Action |
| :--- | :--- | :--- |
| **`skill-layer appropriate`** | Failures observed (> 0 incidents); errors require semantic contextual reasoning, multi-method/multi-file refactoring, or nuanced test intent. | **Include in Skill Injection Pilot** |
| **`deterministic-fixer appropriate`** | Failures observed (> 0 incidents); errors are syntactic, regular, or mechanical (e.g. 1-to-1 import replacement, static XML injection). | **Delegate to AST / regex post-processor** |
| **`not observed`** | Zero recorded failure incidents across historical sessions. | **Exclude from Pilot (No current need)** |

### Specific Domain Hypotheses (to be verified against empirical data):
1. `jakarta_namespace`: Almost certainly a **deterministic fixer** (replacing `javax.*` with `jakarta.*` in Java 21 / Spring Boot 3 is mechanical).
2. `layer_architecture`: Prime candidate for **skill injection** (extracting logic from controller to service requires understanding business intent).
3. `exception_handling`: Hybrid, but semantic mapping of business exceptions to `@RestControllerAdvice` fits **skill injection** or pre-templated guidance.
4. `maven_pom`: Prime candidate for **deterministic fixer** (validating offline dependency cache and injecting fixed plugin configurations).
5. `mockito_tests`: Prime candidate for **skill injection** (mock behavior, stubbing, and assertions require deep context on Spring test lifecycle).

---

## 5. Report Layout & Executive Digest

### Decision
Structure `reports/009-historical-baseline.md` into 6 clear markdown sections:
1. **Metadata & Header**: Source DB path, session date range, total sample size.
2. **Executive Summary & Domain Triage Scorecard**: The single-page decision table displaying verdicts for all 5 domains.
3. **Session Outcome Distribution**: Total Verified, Blocked, Failed, Cancelled sessions (raw counts + percentages).
4. **Repair-Loop Efficiency Analysis**: Attempt distribution (0, 1, 2, 3) and exhaustion rate.
5. **Error Classification & Failure Mode Breakdown**: Granular diagnostic categorization.
6. **Constitutional Validator Impact**: Principles triggered and phase breakdown.
