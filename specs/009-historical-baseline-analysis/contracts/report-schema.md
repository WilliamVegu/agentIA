# Report Schema Contract: Historical Baseline Distribution Report

**Target Output File**: `reports/009-historical-baseline.md`  
**Audience**: Platform Engineers, AI Architects, and Executive Stakeholders  

---

## 1. Markdown Document Sections

The generated report MUST strictly adhere to the following section order and header levels:

```markdown
# AgentIA Historical Baseline Analysis: Failure Mode Distribution & Skill Pilot Triage

> **Executive Digest**: [1-2 sentences summarizing sample size, verification rate, and final domain survival count].

---

## 1. Metadata & Dataset Overview
- Tables listing: Date of Analysis, Database File, Total Historical Sessions, Terminal Sessions Analyzed, Active/In-Flight Sessions.

---

## 2. Executive Scorecard: Candidate Domain Triage
- Markdown table containing columns:
  | Candidate Domain | Historical Incidents | Error Share (%) | Recommended Remediation | Strategic Justification | Survives in Pilot? |
- Unambiguous classification verdicts:
  - `skill-layer appropriate`
  - `deterministic-fixer appropriate`
  - `not observed`

---

## 3. Session Terminal State Distribution
- Markdown table and summary metrics:
  - `VERIFIED` (Count & Percentage)
  - `BLOCKED` (Count & Percentage)
  - `FAILED` (Count & Percentage)
  - `CANCELLED` (Count & Percentage)
- Analysis notes discussing the primary drivers of `BLOCKED` vs `VERIFIED`.

---

## 4. Autonomous Self-Repair Loop Behavior
- Attempt distribution table:
  - Sessions requiring 0 repairs (Clean first-pass runs)
  - Sessions requiring 1 repair attempt
  - Sessions requiring 2 repair attempts
  - Sessions requiring 3 repair attempts (Max limit)
- Loop exhaustion metrics:
  - Sessions exhausted without verification
  - Exhaustion rate (%)
  - First-pass repair recovery efficiency (%)

---

## 5. Failure Mode Taxonomy & Diagnostic Breakdown
- Granular breakdown table:
  - Compilation Errors (javac)
  - Test Assertion Failures (Surefire / Mockito)
  - Constitutional Quality Gate Violations
  - Runtime Exceptions / General Build Failures
- Recurring error signatures observed in logs.

---

## 6. Constitutional Validator Violation Frequency
- Table of platform principles triggered:
  - Principle I: Layer Isolation (Controller -> Service -> Repository)
  - Principle II: Immutable DTOs & Jakarta Validation
  - Principle III: Centralized Exception Handling & ProblemDetails
  - Principle IV: Offline Determinism & Sandbox
  - Principle V: Quality Gates & 3-Repair Cap
  - Principle VI: Zero Secrets & Isolation

---

## 7. Pilot Scope Recommendations & Next Actions
- Explicit list of survived domains for the Skill Injection Pilot.
- Explicit list of redirected domains for Deterministic Fixers.
- Architectural guidance for the upcoming pilot specification.
```

---

## 2. Quantitative Format Invariant

**Rule**: Every numerical finding MUST include the raw count followed by the percentage in parentheses:
- Example: `82 (60.7%)`
- Never report raw counts without percentages, and never report bare percentages without raw numbers.
