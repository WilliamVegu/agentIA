# Phase 1 Data Model — Cost Tracing

Three new persisted shapes and one addition to an existing row. Nothing existing is removed, retyped, or repurposed.

---

## 1. Model Call Record

One row per model call. The atomic unit of cost.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `call_id` | text | yes | Stable unique identifier; the report's dedup key |
| `session_id` | text | yes | Correlates the call to a session. From the recording context |
| `stage` | text | yes | The generation stage that made the call. From the recording context |
| `provider` | text | yes | e.g. `deepseek`. **Identifier only — never a credential** |
| `model` | text | yes | e.g. `deepseek-flash` |
| `timestamp` | timestamp (UTC) | yes | When the call was made. **Also the input to the peak/off-peak basis** |
| `latency_ms` | integer | yes | Wall-clock duration of the call |
| `input_tokens` | integer | nullable | Prompt tokens reported by the response |
| `cache_hit_input_tokens` | integer | nullable | The subset of `input_tokens` served from cache |
| `output_tokens` | integer | nullable | Completion tokens reported by the response |
| `usage_known` | boolean | yes | `False` when the response reported no usage |
| `cache_basis_known` | boolean | yes | `False` when the response reported no cache breakdown. Priced as cache-miss |
| `peak` | boolean | yes | Whether the call's timestamp fell in the peak window |
| `priced` | boolean | yes | `False` when the provider/model pair is absent from the table |
| `cost_usd` | decimal | nullable | `NULL` when unpriced or usage-unknown. **Never `0` as a substitute for unknown** |
| `pricing_basis` | text | yes | Which rate set was applied, e.g. `peak/cache-miss` |

**Validation rules**

- `usage_known = False` ⟹ `input_tokens`, `output_tokens` and `cost_usd` are `NULL`. Not zero.
- `usage_known = True` ⟹ both token counts are non-null and `input_tokens >= 0`, `output_tokens >= 0`.
- `cache_hit_input_tokens` is non-null only when `cache_basis_known`; otherwise cache-miss is assumed and `pricing_basis` says so.
- `cache_basis_known = True` ⟹ `0 <= cache_hit_input_tokens <= input_tokens`.
- `priced = False` ⟹ `cost_usd` is `NULL` and `pricing_basis` is `unpriced`.
- `priced = True and usage_known = True` ⟹ `cost_usd` is non-null.
- No field may contain a credential. Tested, not assumed.

**Cost derivation** (the only permitted formula):

```
cache_miss_input = input_tokens - (cache_hit_input_tokens or 0)     # 0 when unknown -> all miss
input_cost  = (cache_hit_input_tokens or 0) / 1e6 * rate.input_cache_hit
            + cache_miss_input              / 1e6 * rate.input_cache_miss
output_cost = output_tokens                 / 1e6 * rate.output
cost_usd    = input_cost + output_cost
```

`rate` is selected by `(provider, model)` **and** by `peak`, where `peak` is derived from `timestamp`.

---

## 2. Pricing Entry

One entry per supported provider/model pair, in `backend/app/resources/model_pricing.json`.

| Field | Type | Notes |
| --- | --- | --- |
| `provider` | text | Key part |
| `model` | text | Key part |
| `peak.input_cache_hit` | decimal | USD per 1M tokens |
| `peak.input_cache_miss` | decimal | USD per 1M tokens |
| `peak.output` | decimal | USD per 1M tokens |
| `off_peak.*` | decimal | Same three fields. The source states off-peak is exactly half of peak, which is asserted as a load-time consistency check |
| `source` | text | **Required.** The URL the rates were read from |
| `retrieved_at` | date | When the rates were read |
| `peak_window` | object | The peak definition, in UTC, with the weekday restriction and the excluded-holiday caveat |

**Validation rules**

- `source` is mandatory. A pricing entry without a cited source fails to load — the specification forbids recalled or estimated rates.
- `off_peak == peak / 2` for every field. A table violating this fails to load, because it contradicts the cited source.
- Unknown keys are ignored; a malformed entry is a load error rather than a silent skip, so a typo cannot silently drop a model into the unpriced bucket.

**Recorded limitation**: the table does not model the provider's public-holiday calendar, so a holiday call is priced at peak. Overstates, never understates. Disclosed in the report's basis statement.

---

## 3. Session Cost Record

One row per session. The report's unit of analysis.

| Field | Type | Notes |
| --- | --- | --- |
| `session_id` | text | Primary key |
| `spec_name` | text | From the session row |
| `terminal_status` | text | `COMPLETED` / `BLOCKED` / other |
| `model_mode` | text | `MODEL` or `DETERMINISTIC` (feature 011) |
| `verification_fallback_used` | boolean | **From feature 012.** The exclusion key for FR-007 |
| `total_input_tokens` | integer | Sum over priced-or-known calls |
| `total_output_tokens` | integer | Sum over priced-or-known calls |
| `total_cost_usd` | decimal | Sum of known call costs. `NULL` only when no call had a known cost |
| `duration_seconds` | decimal | Session wall-clock duration |
| `model_calls_count` | integer | Number of call records |
| `usage_unknown_calls` | integer | Calls whose usage was unknown — the report's honesty counter |
| `unpriced_calls` | integer | Calls whose model was absent from the table (FR-009) |
| `cache_miss_assumed_calls` | integer | Calls priced on the cache-miss upper bound |
| `updated_at` | timestamp | Last aggregation |

**Validation rules**

- `model_calls_count == 0` ⟹ the session is a **deterministic** session, not a zero-cost model session. It is recorded with `model_mode = DETERMINISTIC` and excluded from the cost averages (see the report contract §3).
- `total_cost_usd` is `NULL` rather than `0` when every call was unpriced or usage-unknown.
- `verification_fallback_used` is copied from the session's persisted verification metrics, so FR-007's exclusion is a property of the record rather than a join the report has to perform.

**"Completed for costing"** — the predicate the headline figure uses:

```
completed_for_costing(s) = s.terminal_status == "COMPLETED"
                       and s.model_mode == "MODEL"
                       and s.verification_fallback_used == False
                       and s.total_cost_usd is not NULL
```

Every clause earns its place: `COMPLETED` excludes blocked sessions; `MODEL` excludes offline sessions (which would drag the average toward zero); the fallback clause implements FR-007 (a synthetic verification is not a successful generation); and the last clause keeps unpriced sessions from entering a money average as if they were free.

---

## 4. Session Row Addition

Represented by `GenerationSessionDB` in `backend/app/models/session.py`.

| Field | Change |
| --- | --- |
| `cost_record_json` | **NEW** — `Text`, nullable. The session's cost aggregate, so the session detail surface can report it without reading the cost store |

**Migration**: through the existing idempotent `_ensure_generation_columns()` helper — `PRAGMA table_info`, then `ALTER TABLE ... ADD COLUMN` only when absent. The same mechanism 011's T013 introduced and 012 reused. Purely additive; no migration tool, and an existing `studio.db` picks it up.

---

## Entity relationships

```text
Model Call Record ──(N:1)──▶ Session Cost Record ──(1:1)──▶ Session Row
        │                            │
        │ priced by                  │ excluded from the headline when
        ▼                            ▼
   Pricing Entry              verification_fallback_used = True   (FR-007)
   (peak/off-peak × cache)
```

**No entity is removed and no cardinality changes.** The call record is written by the recording proxy at call time; the session record is aggregated at session end from the call records; the session row addition is a convenience copy for the detail surface.
