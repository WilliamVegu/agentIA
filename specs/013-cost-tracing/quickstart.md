# Quickstart — Cost Tracing

Validation guide for feature 013. Each scenario maps to a success criterion. **Nothing here requires a live model provider** except scenario 7, which is opt-in and separate.

---

## Prerequisites

| Requirement | Check | Expected |
| --- | --- | --- |
| Virtualenv | `ls .venv/bin/python` | exists |
| Test runner | `.venv/bin/python -m pytest --version` | prints a version |
| Tracking destination | `echo "${MLFLOW_TRACKING_URI:-<unset>}"` | `<unset>` is fine — the default is `http://localhost:5000`, and absence is handled by design |
| Pricing table | `cat backend/app/resources/model_pricing.json` | contains a `source` URL and both rate sets |

**Run all commands from the repository root.**

A note on the telemetry destination: it is **expected to be unreachable** during most of this validation. That is the point of scenario 6, not a failure. The design writes to a durable local store first, so every other scenario works with no tracking server at all.

---

## Scenario 1 — Calls are recorded with tokens and latency (SC-001)

**Purpose**: prove every model call produces a record carrying real token counts.

**Action**:

```bash
.venv/bin/python -m pytest backend/tests/test_cost_recording.py -v
```

**Expected**:

- One record per model invocation, including correction attempts.
- Each carries session identifier, stage name, provider, model, timestamp, latency, and both token counts.
- A usage-reporting double produces non-zero counts; the default double (which reports none) produces records marked `usage_known = False`, not dropped and not zero.
- A deterministic (offline) session produces **no** call records.

**Failure looks like**: a call with no record; a call silently recorded as zero tokens; a wrapped client reaching `test_llm_factory.py` and failing its `isinstance` assertions.

---

## Scenario 2 — Pricing is per call, by peak/off-peak and cache (SC-007, SC-008)

**Purpose**: prove a call is priced against the rate that applied to *that call*.

**Action**:

```bash
.venv/bin/python -m pytest backend/tests/test_cost_pricing.py -v
```

**Expected**:

- Two otherwise identical calls whose timestamps fall inside and outside the peak window are priced in the published ratio (peak is 2× off-peak).
- A cache-hit call on Flash input is priced at $0.003–0.006 per 1M tokens, not $0.15–0.30; a cache-miss call at the higher rate.
- `pricing_basis` names the basis applied (e.g. `peak/cache-miss`).
- The seeded table's off-peak values are exactly half its peak values for every field — the published relationship, asserted as a load-time check.
- The table's `source` field points at the published pricing page.

**Failure looks like**: identical prices inside and outside peak; a cache-hit call priced as a miss; an off-peak value that is not half of peak.

---

## Scenario 3 — Unknown usage and unpriced models are never zero (SC-005)

**Purpose**: prove the two silent-zero failure modes are closed.

**Action**: included in scenario 2's suite, or run directly:

```bash
.venv/bin/python -m pytest backend/tests/test_cost_pricing.py -k "unknown or unpriced" -v
```

**Expected**:

- A call whose response reports no usage has `usage_known = False` and a `NULL` cost — **not** `0`.
- A call whose model is absent from the table has `priced = False` and a `NULL` cost — **not** `0`.
- Both counts appear on the report.

---

## Scenario 4 — Per-session aggregation (SC-001, SC-002)

**Purpose**: prove the per-session record sums correctly and carries the outcome.

**Action**:

```bash
.venv/bin/python -m pytest backend/tests/test_cost_report.py -v
```

**Expected**:

- Totals equal the sum over the session's calls.
- `session_id`, `spec_name`, `terminal_status`, `model_mode`, `verification_fallback_used`, duration and call count are all present.
- Re-aggregating a session overwrites its row rather than double-counting.

---

## Scenario 5 — The report prints the required figures (SC-002)

**Action**:

```bash
.venv/bin/python backend/scripts/report_session_costs.py
```

**Expected**: every line from [contracts/cost-report.md](contracts/cost-report.md) §1, including:

- session counts (total, completed, blocked, unverifiable),
- the **average cost per completed session**,
- the average per session regardless of status,
- p50 / p90 / max,
- the cost breakdown by stage and the most expensive stage named,
- the population statement (sessions, calls, unknown-usage calls, unpriced calls),
- the exclusion count,
- the pricing basis statement (basis, peak window, cache-miss-assumed count).

**Failure looks like**: a headline number with no population line; a stage breakdown without naming the most expensive stage.

---

## Scenario 6 — Determinism and durability (SC-003, SC-006)

**Purpose**: prove the report is re-runnable and survives an unreachable destination.

**Action**:

```bash
# with the tracking destination deliberately unreachable
MLFLOW_TRACKING_URI=http://127.0.0.1:1 .venv/bin/python backend/scripts/report_session_costs.py > /tmp/run1.txt
MLFLOW_TRACKING_URI=http://127.0.0.1:1 .venv/bin/python backend/scripts/report_session_costs.py > /tmp/run2.txt
diff /tmp/run1.txt /tmp/run2.txt && echo "IDENTICAL"
```

**Expected**:

- The two runs are byte-identical.
- Both succeed despite the destination being unreachable.
- Sessions run while the destination was down are still present with non-zero token counts.

**Failure looks like**: a diff; an exception from the report; missing records for sessions that ran while the destination was down.

---

## Scenario 7 — Ten real sessions (SC-001) — opt-in, needs a provider key

**Purpose**: the success criterion's literal form — ten DeepSeek sessions produce ten records with non-zero token counts.

**This is the only scenario that spends money and the only one that makes a live call.** It is opt-in and MUST NOT run in the default suite (Constitution Principle VI).

```bash
AGENTIA_RUN_REAL_COST_TRACING=1 DEEPSEEK_API_KEY=... \
  .venv/bin/python -m pytest backend/tests/test_cost_recording.py -k real_sessions -v
```

**Expected**:

- Ten session cost records, each with non-zero input and output token counts.
- Every call priced (no unpriced calls) and every call's `pricing_basis` naming a real basis.
- The report prints a defensible average per completed session over those ten.

**If the key is absent, this scenario skips.** Report it as *not verified by me* rather than inferred — the same discipline feature 012's SC-003 required.

---

## Scenario 7a — Async call on a sync-only client (SC-010)

**Purpose**: prove the wrapper does not turn a working client into one that raises.

**Action**:

```bash
.venv/bin/python -m pytest backend/tests/test_cost_recording.py -k ainvoke -v
```

**Expected**:

- Invoking the wrapped fake client asynchronously completes without raising, even though the fake implements only the synchronous entry point.
- The documented fallback is what happens: the call is delegated to the synchronous implementation and **is recorded** (a call that runs is a call that costs).
- The record carries the same fields as a synchronous call.

**Failure looks like**: `AttributeError` from the wrapper; or the call succeeding but producing no record, which would be silent spend.

---

## Scenario 8 — The existing suite is untouched by recording (SC-009)

**Purpose**: prove the recording wrapper does not break the seam it wraps.

**Action**:

```bash
.venv/bin/python -m pytest -q
```

**Expected**:

- All pre-existing tests pass **unmodified**, in particular `test_llm_factory.py`'s seven `isinstance(model, ChatOpenAI/Groq/GoogleGenerativeAI)` assertions and its attribute reads.
- Tests that monkeypatch the factory to return the fake client are unaffected — the fake never passes through the wrapper, by construction.

**Failure looks like**: any `isinstance` assertion failing, or the fake path requiring a change to accommodate recording.

If the wrapper does interfere with the fake path, the fix is a **bypass condition that preserves the tests** — never a weakening of the tests or of the recording guarantee.

---

## Definition of Done

- [ ] Scenario 1 passes (SC-001: one record per call, real token counts)
- [ ] Scenario 2 passes (SC-007, SC-008: per-call peak/off-peak and cache pricing; basis stated)
- [ ] Scenario 3 passes (SC-005: unknown usage and unpriced models are never zero)
- [ ] Scenario 4 passes (SC-001, SC-002: aggregation sums correctly)
- [ ] Scenario 5 passes (SC-002: headline figure with its population)
- [ ] Scenario 6 passes (SC-003, SC-006: byte-identical re-runs, durable when the destination is down)
- [ ] Scenario 7 **run with a key, or explicitly recorded as not verified** (SC-001's literal form)
- [ ] Scenario 7a passes (SC-010: async call on a sync-only client does not raise, and is recorded)
- [ ] Scenario 8 passes (SC-009: pre-existing suite unmodified)
- [ ] No credential appears in any cost record, report line, or telemetry parameter
- [ ] `reports/measurements/` and `reports/baselines/` are untouched by this feature
