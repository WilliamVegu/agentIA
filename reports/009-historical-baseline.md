# AgentIA Historical Baseline Analysis: Failure Mode Distribution & Skill Pilot Triage

> **Executive Digest**: Analysis of historical generation sessions demonstrates that **28 (58.3%)** of terminal sessions completed successfully, while **16 (33.3%)** terminated in blocked state and **4 (8.3%)** suffered unrecoverable failures. Out of 5 evaluated candidate failure domains, **3 domains** survive into the Skill Injection Pilot, **2 domains** are triaged to deterministic fixers, and **0 domains** were not observed.

---

## 1. Metadata & Dataset Overview

| Metric | Value |
| :--- | :--- |
| **Analysis Date** | `2026-09-25T13:11:48.578888+00:00` |
| **Database Source** | `backend/studio.db` |
| **Total Sessions Queried** | **50** |
| **Terminal Sessions Analyzed** | **48** |
| **In-Flight / Active Sessions** | **2** |

---

## 2. Executive Scorecard: Candidate Domain Triage

| Candidate Domain | Incidents | Error Share | Triage Verdict | Strategic Justification | Pilot Scope |
| :--- | :---: | :---: | :---: | :--- | :---: |
| **Jakarta EE 10 Namespace Migration** | 2 | 10.0% | `deterministic-fixer appropriate` | Mechanical, regular package import replacements (javax.* -> jakarta.*) best handled by AST/regex deterministic post-processor. | 🔧 **DETERMINISTIC** |
| **Architectural Layer Isolation (Principle I)** | 3 | 15.0% | `skill-layer appropriate` | Semantic architectural violations requiring service method extraction, business logic refactoring, and multi-file reasoning. | 🎯 **SURVIVES** |
| **Centralized Error Handling (Principle III)** | 2 | 10.0% | `skill-layer appropriate` | Domain-specific exception mapping requiring semantic definition of business exceptions, status codes, and @RestControllerAdvice handlers. | 🎯 **SURVIVES** |
| **Maven POM & Offline Dependency Management (Principle IV)** | 6 | 30.0% | `deterministic-fixer appropriate` | XML dependency verification and offline plugin fixes are mechanical and best handled by deterministic POM injectors. | 🔧 **DETERMINISTIC** |
| **Mockito Test Synthesis & Stubbing Correctness** | 3 | 15.0% | `skill-layer appropriate` | Complex test lifecycle, assertion logic, mock verification, and stubbing flow requiring deep semantic understanding of unit testing intentions. | 🎯 **SURVIVES** |

---

## 3. Session Terminal State Distribution

| Final Status | Session Count | Percentage Share (%) | Operational Significance |
| :--- | :---: | :---: | :--- |
| **`VERIFIED`** | **28** | **58.3%** | Microservice passed 100% tests & quality gates |
| **`BLOCKED`** | **16** | **33.3%** | Execution halted by Quality Gate or loop exhaustion |
| **`FAILED`** | **4** | **8.3%** | Unrecoverable build / infrastructure exception |

- **Verification Success Rate**: 28 of 48 terminal sessions (58.3%).
- **Intervention Overhead Rate**: 20 of 48 terminal sessions (41.7%) required human intervention or aborted.

---

## 4. Autonomous Self-Repair Loop Behavior

Under Constitution Principle V, the autonomous repair loop is bounded to a maximum of 3 iterations.

| Repair Attempts Required | Sessions | Percentage (%) | Efficiency Analysis |
| :---: | :---: | :---: | :--- |
| **0 Attempts** (First-Pass Clean) | **16** | **33.3%** | Code passed compilation & tests without repair |
| **1 Attempt** (Self-Repaired) | **12** | **25.0%** | Fixed on first automated repair cycle |
| **2 Attempts** (Complex Repair) | **4** | **8.3%** | Required secondary diagnostic repair |
| **3 Attempts** (Cap Exhausted) | **16** | **33.3%** | Hit boundary limit; triggered safety abort |

- **Total Sessions Involving Repair**: 32 sessions.
- **Loop Exhaustion Rate**: **16 (50.0%)** of repaired sessions exhausted the 3-attempt cap without reaching verified status.
- **First-Attempt Recovery Efficiency**: **12 (25.0%)** of failed runs were remediated on the very first repair cycle.

---

## 5. Failure Mode Taxonomy & Diagnostic Breakdown

Breakdown of errors parsed across compiler logs, surefire test executions, and sandbox traces:

| Diagnostic Category | Incident Count | Share (%) | Primary Root Causes |
| :--- | :---: | :---: | :--- |
| **`ASSERTION_FAILURE`** | 7 | 29.2% | Recurrent syntax, assertion, or architectural boundary failures |
| **`COMPILATION_ERROR`** | 6 | 25.0% | Recurrent syntax, assertion, or architectural boundary failures |
| **`BUILD_FAILURE`** | 6 | 25.0% | Recurrent syntax, assertion, or architectural boundary failures |
| **`CONSTITUTIONAL_VIOLATION`** | 5 | 20.8% | Recurrent syntax, assertion, or architectural boundary failures |

---

## 6. Constitutional Validator Violation Frequency

Frequency of automated quality gate violations flagged by platform validators:

| Constitutional Principle | Violations Observed | Enforcement Action |
| :--- | :---: | :--- |
| **Principle I: Layer Isolation** | **5** | Gate BLOCKED - Human Review Required |
| **Principle II: Immutable DTOs** | **2** | Gate BLOCKED - Human Review Required |
| **Principle III: Centralized Exception Handling** | **2** | Gate BLOCKED - Human Review Required |
| **Principle IV: Offline Determinism** | **6** | Gate BLOCKED - Human Review Required |
| **Principle V: Quality Gates & 3-Repair Cap** | **0** | Compliant (0 violations) |
| **Principle VI: Zero Secrets & Isolation** | **0** | Compliant (0 violations) |

---

## 7. Pilot Scope Recommendations & Next Actions

### A. Domains Surviving into Skill Injection Pilot
1. **`layer_architecture`** (Architectural Layer Isolation (Principle I)): 3 incidents (15.0% failure share). *Justification*: Semantic architectural violations requiring service method extraction, business logic refactoring, and multi-file reasoning.
1. **`exception_handling`** (Centralized Error Handling (Principle III)): 2 incidents (10.0% failure share). *Justification*: Domain-specific exception mapping requiring semantic definition of business exceptions, status codes, and @RestControllerAdvice handlers.
1. **`mockito_tests`** (Mockito Test Synthesis & Stubbing Correctness): 3 incidents (15.0% failure share). *Justification*: Complex test lifecycle, assertion logic, mock verification, and stubbing flow requiring deep semantic understanding of unit testing intentions.

### B. Domains Triaged to Deterministic Fixers (AST/Regex)
1. **`jakarta_namespace`** (Jakarta EE 10 Namespace Migration): 2 incidents (10.0% failure share). *Justification*: Mechanical, regular package import replacements (javax.* -> jakarta.*) best handled by AST/regex deterministic post-processor.
1. **`maven_pom`** (Maven POM & Offline Dependency Management (Principle IV)): 6 incidents (30.0% failure share). *Justification*: XML dependency verification and offline plugin fixes are mechanical and best handled by deterministic POM injectors.

### D. Architectural Roadmap for Skill Injection Pilot
- **Zero Code Changes to Core Runtime**: Implement skill injection as a pre-generation prompt layer, preserving AgentIA core stability.
- **Targeted Focus**: Prioritize skill authoring for surviving semantic domains (`layer_architecture` and `mockito_tests`).
- **Deterministic Interceptor**: Implement a lightweight post-processing pass for `jakarta_namespace` and `maven_pom` before invoking the 3-attempt repair loop.

---
*Report auto-generated by `backend/scripts/analyze_historical_baseline.py` on 2026-09-25T13:11:48.578888+00:00.*