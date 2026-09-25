# CLI Interface Contract: Historical Baseline Analyzer

**Script Path**: `backend/scripts/analyze_historical_baseline.py`  
**Execution Environment**: Python 3.10+ (standard library only)  

---

## 1. Command Syntax

```bash
python3 backend/scripts/analyze_historical_baseline.py [OPTIONS]
```

---

## 2. Command Options

| Flag | Short | Default | Description |
| :--- | :---: | :--- | :--- |
| `--db-path` | `-d` | `backend/studio.db` | Path to the source SQLite database file. |
| `--output` | `-o` | `reports/009-historical-baseline.md` | Path where the markdown report will be written. |
| `--json` | `-j` | `false` | When set, emits structured JSON metrics to `stdout` in addition to writing the report. |
| `--verbose` | `-v` | `false` | Enables verbose debug logging during log parsing. |
| `--help` | `-h` | N/A | Displays CLI usage instructions and exits with code 0. |

---

## 3. Environment Variable Fallbacks

If CLI options are omitted, the script checks the following environment variables:
- `AGENTIA_STUDIO_DB`: Overrides default `--db-path`.
- `DATABASE_URL`: If begins with `sqlite:///`, extracts the path component for `--db-path`.
- `BASELINE_REPORT_OUTPUT`: Overrides default `--output`.

---

## 4. Exit Codes

| Exit Code | Name | Condition |
| :---: | :--- | :--- |
| `0` | `SUCCESS` | Analysis executed successfully, metrics computed, report written. |
| `1` | `DB_NOT_FOUND` | Specified SQLite database file does not exist. |
| `2` | `DB_CORRUPTED` | SQLite file is locked, unreadable, or missing required `generation_sessions` table. |
| `3` | `IO_ERROR` | Unable to write report file to output path (e.g. permission error). |

---

## 5. Standard Output & Error Contracts

### Standard Output (`stdout` on normal run)
```text
[INFO] Opening database in read-only mode: backend/studio.db
[INFO] Found 142 total sessions (135 terminal, 7 in-flight)
[INFO] Pass/Fail Distribution: 82 Verified (60.7%), 41 Blocked (30.4%), 12 Failed (8.9%)
[INFO] Repair Loop Analysis: 51 sessions repaired, 18 exhausted (35.3% exhaustion rate)
[INFO] Evaluated 5 candidate failure domains
[INFO] Baseline report successfully written to: reports/009-historical-baseline.md
```

### JSON Output Mode (`--json`)
When `--json` is supplied, `stdout` outputs a pure, parseable JSON payload:
```json
{
  "total_sessions": 142,
  "terminal_sessions": 135,
  "verified_count": 82,
  "verified_percentage": 60.7,
  "blocked_count": 41,
  "blocked_percentage": 30.4,
  "failed_count": 12,
  "failed_percentage": 8.9,
  "repair_loop": {
    "sessions_with_repairs": 51,
    "exhausted_count": 18,
    "exhaustion_rate": 35.3
  },
  "candidate_domains": {
    "jakarta_namespace": {
      "count": 14,
      "verdict": "deterministic-fixer appropriate"
    },
    "layer_architecture": {
      "count": 22,
      "verdict": "skill-layer appropriate"
    },
    "exception_handling": {
      "count": 9,
      "verdict": "skill-layer appropriate"
    },
    "maven_pom": {
      "count": 11,
      "verdict": "deterministic-fixer appropriate"
    },
    "mockito_tests": {
      "count": 31,
      "verdict": "skill-layer appropriate"
    }
  }
}
```
