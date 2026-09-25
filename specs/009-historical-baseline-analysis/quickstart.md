# Quickstart & Validation Guide: Historical Baseline Analysis

**Feature**: Historical Baseline Analysis for AgentIA Skill Injection Pilot  
**Branch**: `009-historical-baseline-analysis`  

This guide provides step-by-step instructions to validate the baseline analysis script against both local historical databases and synthetic fixture databases.

---

## 1. Prerequisites

- Python 3.10+ installed on the host.
- Optional: Virtual environment if running with project pytest (`backend/tests`).
- Read-only access to SQLite database.

---

## 2. Running Against Local Database

### Standard Execution
```bash
python3 backend/scripts/analyze_historical_baseline.py
```
*Expected Outcome*:
- Scans `backend/studio.db` (or `./studio.db`).
- Generates `reports/009-historical-baseline.md`.
- Prints summary to terminal.

### Custom Database or Output Path
```bash
python3 backend/scripts/analyze_historical_baseline.py \
  --db-path /path/to/custom_studio.db \
  --output reports/009-historical-baseline.md \
  --verbose
```

### JSON Mode (for CI/CD or automation)
```bash
python3 backend/scripts/analyze_historical_baseline.py --json
```

---

## 3. Running Unit & Integration Tests

The test suite validates:
1. Strict read-only connection behavior (confirming write operations raise `sqlite3.OperationalError`).
2. Correct parsing of compiler errors and Surefire assertion logs.
3. Correct domain classification across all 5 candidate categories.
4. Handling edge cases (empty DB, missing tables, corrupted records).
5. Output report formatting and dual number/percentage presence.

Run the test suite with:
```bash
python3 -m pytest backend/tests/test_historical_baseline.py -v
```

---

## 4. Verification Checklist

- [ ] Script executes with zero Python errors.
- [ ] Report is generated at `reports/009-historical-baseline.md`.
- [ ] Report contains all 5 required deliverables:
  - [ ] 1. Pass/Fail/Blocked distribution
  - [ ] 2. Repair-loop attempt distribution & exhaustion
  - [ ] 3. Granular error classification
  - [ ] 4. Constitutional validator frequencies
  - [ ] 5. Candidate domain triage scorecard
- [ ] Every metric has both raw counts and percentages.
- [ ] No write operations or modifications occurred on the SQLite database.
