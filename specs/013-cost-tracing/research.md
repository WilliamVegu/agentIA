# Phase 0 Research — Cost Tracing

Every Technical Context unknown was resolved by inspecting the repository and by fetching one primary source. No `NEEDS CLARIFICATION` item remains.

---

## D1 — The recording proxy is applied conditionally, not unconditionally

**Decision**: Wrap the client returned by the model factory **only while a recording context is active**. The stage execution boundary establishes that context around client construction; when it is absent, the factory returns exactly what it returns today.

**Rationale — measured, not assumed.** `backend/tests/test_llm_factory.py` contains **seven** `isinstance(model, ...)` assertions (ChatGoogleGenerativeAI, ChatGroq, ChatOpenAI) plus attribute reads (`model.model`, `model.model_name`, `model.openai_api_base`). An unconditional wrapper fails every one of them, because `isinstance(proxy, ChatOpenAI)` is false and a generic proxy has none of those attributes. The spec's SC-009 forbids breaking the seam.

The conditional form works because construction happens **inside** the stage boundary:

```
backend/app/orchestrator/stages/runner.py:812   client = implementation.build_client(state, api_key)
```

`build_client` calls `LLMFactory.get_chat_model(...)`. So the seam can open a recording context immediately before, and every production construction is wrapped. Tests that call the factory directly — which is all of `test_llm_factory.py` — never open that context and see the raw client.

**Why this is not a test-shaped bypass.** The condition is *"is recording active"*, which is true for every real session and false for direct factory calls. A bypass keyed on test presence would leave production unprotected; this one does not. This distinction is the single most important thing to preserve during implementation, and it is called out in the plan's post-design re-check.

**Alternatives considered**:
- *Always wrap; make the proxy transparent.* Rejected: `isinstance` cannot be delegated. Subclassing each provider class is not possible generically, and a `BaseChatModel` subclass still fails `isinstance(x, ChatOpenAI)`.
- *Wrap at the call site instead.* Rejected by the spec (FR-001): a convention, not a guarantee.
- *Wrap only the fake client's calls.* Rejected: inverts the requirement — it would record tests and not production.

---

## D2 — The recording context is a context variable

**Decision**: Propagate stage name and session identifier with `contextvars.ContextVar`, set by the stage boundary for the duration of a stage's execution.

**Rationale**: The factory runs deep inside `build_request`/`build_client` call chains and knows nothing about stages; threading two more parameters through every `build_client` signature would touch all five model stage modules (which the 011/012 guardrails treated as stable) and would still be forgettable. A context variable is ambient, needs no signature changes, and is correct across the sync/async boundary used by the seam. Calls made with no context — direct factory use, tests — record nothing, which is exactly D1's condition.

**Alternatives considered**:
- *Explicit parameters through `build_client`.* Rejected: five signature changes and a new way to forget.
- *A module-level global.* Rejected: not safe across concurrent sessions. The platform runs sessions concurrently (`MAX_CONCURRENT_SESSIONS`), so a global would cross-attribute sessions.

---

## D3 — Storage: three decisions, one of them worth your attention

**Decision**: (a) A dedicated local SQLite file is the **durable system of record**; MLflow receives the same records as telemetry when its tracking URI is reachable. (b) The report reads the local store only. (c) Session-level costing metadata is also written to the session row through the additive-column mechanism 011/012 established.

**Rationale**: FR-005 requires that cost data is never lost and FR-006 that the report is deterministic. Both are easier to guarantee with one authoritative store than with a primary/fallback pair, because a pair forces the report to union two sources and de-duplicate, and makes the numbers depend on which store a given session happened to land in. With a local system of record, SC-006 ("destination unreachable → same figures") holds **by construction** rather than by luck, and the report needs no health check.

MLflow is still written on every call when reachable, so FR-001's "records to MLflow" is satisfied in normal operation.

**This is the one decision in this plan worth your explicit sign-off.** FR-005 reads as "MLflow primary, SQLite fallback"; the design is "SQLite primary, MLflow mirror". If MLflow was intended as the system of record, say so — the change is contained (the report reads the tracking URI instead of the local file, and the local store becomes the fallback), but it also means the report's determinism and offline behaviour depend on the tracking server's availability, which is the trade the design avoids.

**Why a separate SQLite file rather than the platform's existing database**: cost records have a different retention and growth profile from session rows (one row per model call, forever), and keeping them out of `studio.db` avoids coupling the report to the session schema and its threading.

**Alternatives considered**:
- *MLflow primary, local fallback, report unions both.* Rejected: dedup complexity, and a report whose population depends on incidental store availability.
- *Write cost rows into `studio.db`.* Rejected: mixes a high-volume append-only log into the session store and makes the report depend on the session schema.
- *Use MLflow's SQLite backend as the local store.* Considered: it would give one client API for both. Rejected because it makes the durable store's format a function of the MLflow version, so a future MLflow upgrade could jeopardise the records that are supposed to be never-lost.

---

## D4 — Expanded pricing schema

**Decision**: `backend/app/resources/model_pricing.json` maps each `(provider, model)` to peak and off-peak, each with cache-hit and cache-miss input rates plus an output rate, and records the source URL and the peak window definition in-file.

**Rationale**: Fetched from <https://api-docs.deepseek.com/quick_start/pricing> (HTTP 200). Published rates per 1M tokens:

| | `deepseek-flash` | `deepseek-v4-pro` |
| --- | --- | --- |
| Input cache **hit**, off-peak | $0.003 | $0.022 |
| Input cache **hit**, peak | $0.006 | $0.044 |
| Input cache **miss**, off-peak | $0.15 | $0.66 |
| Input cache **miss**, peak | $0.30 | $1.32 |
| Output, off-peak | $0.60 | $1.98 |
| Output, peak | $1.20 | $3.96 |

A flat two-number table cannot represent this: Flash input spans a factor of 100. The page also confirms the two model names the platform already configures are current, and that the legacy `deepseek-v4-flash` aliases bill at the Flash price — which `llm_factory.py` already normalises. **No model-name guesswork is needed.**

**Alternatives considered**:
- *Flat peak/cache-miss with a documented overstatement.* Rejected: knowingly wrong by up to 2× on a number a stakeholder reads.
- *Flat off-peak.* Rejected: understates, the more dangerous direction.
- *Fetch rates at run time.* Rejected: violates FR-006 (no live calls) and Principle IV (offline determinism).

---

## D5 — Cache extraction, and the conservative default

**Decision**: Read the cache-hit input token count from the response's usage metadata (the provider reports a prompt-cache-hit count alongside the total prompt tokens). Cache-miss input = prompt tokens − cache-hit tokens. If the response reports no cache fields, price the call as **cache-miss** and count it.

**Rationale**: This is the only reading that yields a real cost rather than a guess. Cache-miss is the upper bound, and overstating is the safer error for a figure used to justify spend — the same reasoning that makes the peak/off-peak basis per-call.

**Verification limitation, recorded**: the platform has captured **no real provider responses**, so the exact field path cannot be confirmed from anything in this repository. The field path is taken as given by the specification's author and **must be confirmed against a real response before the figure is presented as exact**. FR-003's cache-miss default is the safety net: if the path is wrong, calls are priced at the upper bound and counted, rather than silently mispriced as cache hits.

**Alternatives considered**:
- *Assume cache-hit when absent.* Rejected: understates cost.
- *Skip ambiguous calls.* Rejected: drops spend from the total entirely, which is worse than overstating it.

---

## D6 — Peak window

**Decision**: Peak is 01:00–04:00 and 06:00–10:00 UTC, Monday–Friday; everything else is off-peak. Computed per call from the call's own timestamp.

**Rationale**: The provider's published definition. Off-peak is half of peak, which is also published and is asserted as a consistency check on the seeded table.

**Recorded limitation**: the platform does **not** model the provider's public-holiday calendar, so a call the provider prices off-peak on a Chinese public holiday is priced at peak here. That overstates rather than understates, and is disclosed in the report's basis statement. Modelling a third-party holiday calendar was rejected as out of scope and a maintenance burden that would itself go stale.

**Alternatives considered**:
- *Treat everything as peak.* Rejected: overstates off-peak runs by 2× for no reason, when the timestamp is already recorded.
- *Fetch the provider's holiday calendar.* Rejected: live dependency in a deterministic report.

---

## D7 — The test double must be extended to report usage

**Decision**: Additively extend `backend/tests/fixtures/fake_model.py` with a response double that reports token usage (and optionally cache tokens), leaving the existing behaviour untouched as the default.

**Rationale**: `FakeResponse` is a dataclass carrying only `content` — no `usage_metadata`, no `response_metadata`. So the *existing* suite exercises only the unknown-usage path. Without a usage-reporting double, FR-001's token capture is untestable, and SC-001/SC-002 (non-zero token counts, a defensible average) could never be demonstrated. The extension must be additive so the existing tests, which assert `.content` and `.calls`, keep working unchanged.

**Consequence worth stating plainly**: because the double does not report usage by default, **the entire existing suite runs with recording effectively inert**. That is the correct behaviour and it is also why the recording tests must be explicit about enabling usage — a suite that only ever sees unknown usage would pass while recording nothing real.

**Alternatives considered**:
- *Use a real provider response fixture.* Rejected: no captured responses exist, and inventing them would be the guesswork the specification forbids.

---

## D8 — Report determinism

**Decision**: The report reads the local store, orders deterministically (by session identifier), formats fixed-precision currency, and prints percentiles by a stated method (nearest-rank over the sorted, filtered population). No floats in output without fixed rounding.

**Rationale**: SC-003 requires two runs to produce byte-identical numbers. Two subtle ways to break that: floating-point accumulation order, and percentile interpolation conventions. Fixed rounding to six decimal places for currency and a stated nearest-rank percentile both make the output reproducible across runs and machines. Sorting by session identifier removes any dependence on insertion order.

**Alternatives considered**:
- *Interpolated percentiles.* Rejected: more conventional in analytics, but the interpolation convention becomes a source of cross-run difference and needs a library to pin.

---

## D9 — Secret containment

**Decision**: A cost record carries provider and model identifiers only. API keys must never appear in a cost row, a report line, or MLflow parameters. Tested.

**Rationale**: The invariant 011 established for provenance, applied to a new sink. It is worth restating because the recording proxy sits directly beside the credential — it wraps a client constructed *with* an API key — so the key is in scope at the recording site, which is precisely where leaking it is easiest.

**Alternatives considered**: none. This is a standing constitutional requirement, not a design choice.

---

## D10 — Branch: three features on one branch

**Decision**: Recorded as an open decision for the user rather than resolved here. The plan proceeds on `feature/011-llm-generation-nodes`, consistent with 012, but flags that a third feature materially enlarges the review surface — and that 013 adds a new runtime dependency (MLflow) and a new package, unlike 012 which was a contained correctness fix.

**Rationale**: The isolation requirement (nothing merges until review) is unaffected either way, and no `before_specify` hook is registered to create a branch. But 012's recorded exception was explicitly about a *two*-feature stack where 012 fixed a defect in 011. A third feature is a different proposition, and deciding it by default would be exactly the kind of silent inheritance this project's specifications have been careful to avoid.

**Alternatives considered**: none — this is a decision for the requester, not a technical trade-off.

---

## Summary of decisions

| ID | Decision | Primary requirement |
| --- | --- | --- |
| D1 | Recording proxy applied only while a recording context is active | FR-001, SC-009 |
| D2 | Context propagated via `contextvars` | FR-001 |
| D3 | Local SQLite is the system of record; MLflow is a mirror | FR-005, FR-006 |
| D4 | Expanded pricing schema (peak/off-peak × cache hit/miss) | FR-003 |
| D5 | Cache-miss default when cache fields are absent | FR-003, FR-009 |
| D6 | Peak = 01:00–04:00 and 06:00–10:00 UTC Mon–Fri, per call | FR-003, SC-007 |
| D7 | Add a usage-reporting test double | FR-001, FR-001a |
| D8 | Nearest-rank percentiles, fixed precision, deterministic ordering | FR-006, SC-003 |
| D9 | No credential in any cost record | Principle VI |
| D10 | Three-feature branch recorded as an open decision | — |

No open `NEEDS CLARIFICATION` items remain.
