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

**APPROVED — sign-off received, and FR-005 has been updated to match.** The requirement now states directly that the local store is authoritative and the telemetry destination is optional. The inversion is no longer a reading of ambiguous wording; it is the specification.

The rationale as approved:

- "Never lost" and "a deterministic report" are both properties obtained from *one* authoritative store.
- If the telemetry destination were authoritative, the report's determinism would depend on the tracking server's availability — the exact failure mode FR-005 exists to prevent.
- With the local store authoritative, the destination becomes a visualization layer that can be absent without affecting anything.

**Consequence to keep in view during implementation**: because the report reads only the local store, a destination that was down for some sessions changes nothing, and one holding partial data cannot make the report wrong. There is no union, no de-duplication, and no health check in the report path.

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

## D10 — Branch: three features on one branch (DECIDED)

**Decision**: Feature 013 stays on `feature/011-llm-generation-nodes`. Recorded in [constitution-recheck.md](constitution-recheck.md) §2 as the third stacked feature in the same arc, with the same exception rationale as 012.

**Rationale, as decided**:

- `main` is untouched, so the isolation requirement the branching convention protects is preserved.
- Three features in the same arc, none merged to the main line.
- Splitting now would require rebasing three features' commits for **zero** isolation benefit.
- Splitting would also yield branches that are not independently green: 013 depends on 011's stage boundary for the recording context and on 012's fallback marking for the report's exclusion rule. Neither 011 nor 012 alone would carry a passing 013.

**Alternatives considered**: a dedicated branch for 013. Rejected: it buys no isolation (nothing merges either way) and costs a rebase across the stack.

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
| D10 | Three-feature branch, recorded in constitution-recheck.md | — |
| D11 | Attribute-probing wrapper; async delegates to sync and is recorded | FR-001, SC-010 |
| D12 | The usage-reporting fake is the first task, because nothing downstream is verifiable without it | SC-001, FR-001 |

No open `NEEDS CLARIFICATION` items remain.

---

## D11 — A client may implement only one invocation form

**Decision**: The wrapper probes the wrapped client for the asynchronous entry point at construction time. If the client has it, the wrapper defines an asynchronous path that records and delegates. If it does not, the wrapper defines an asynchronous path that **delegates to the client's synchronous entry point** (run off the event loop) and records the call, rather than raising.

**Evidence the constraint is real**: `backend/tests/fixtures/fake_model.py` defines `ScriptedChatModel.invoke` (line 48) and **no `ainvoke`**. Confirmed by inspection: the file contains no `ainvoke` at all. A wrapper that unconditionally defines `ainvoke` and forwards to `self._inner.ainvoke(...)` would raise `AttributeError` the moment anything called the wrapped fake asynchronously. Nothing calls it today (`graph.py`'s `ainvoke` is the graph's own entry point, not a chat client's), so the gap is **latent** — which is exactly why it needs a test rather than a fix discovered later.

**Why delegate rather than pass through silently**: both options are defensible, and the two differ in recording semantics, so the choice must be explicit and documented:

| Option | Behaviour | Recording |
| --- | --- | --- |
| **Delegate to sync** (chosen) | The async call runs the sync implementation off the event loop and returns its result | **Recorded** — the call happened, so it cost money and must be counted |
| Pass through, no recording | The async call is forwarded without recording | **Not recorded** — silent spend, the failure this feature exists to prevent |

Delegation is chosen because a call that happens is a call that costs, and a pass-through would create a second, quieter version of the silent-zero problem. The cost is that the wrapper must run the sync call without blocking the loop.

**Alternatives considered**:
- *Define `ainvoke` only when the client has it; otherwise leave it undefined.* Rejected: the attribute error just moves to the caller, which is the failure the requirement forbids.
- *Require every client to implement both.* Rejected: it would mean changing the existing fake, which the guardrail forbids — the fake is extended, never reshaped, and the wrapper must cope with what exists.

---

## D12 — The usage-reporting fake is the first task

**Decision**: The first implementation task is adding usage metadata to the fake response and confirming the synchronous path records end-to-end through the wrapper into the local store.

**Rationale**: The fake currently reports no usage, so every recording assertion written before it would exercise only the unknown-usage path. That means SC-001's literal claim — that ten sessions produce records with **non-zero** token counts — is untestable, and every downstream task that depends on a recorded token count cannot be verified. Sequencing it first means each later task can be checked against a real recorded value rather than against an absence.

**Constraint on the task itself**: the fake is **extended, not reshaped**. Existing tests assert on `.content` and `.calls`, so usage metadata must be additive and defaulted, and no existing assertion may be weakened to accommodate it. If a later task finds itself wanting to relax a pre-existing test, that is a signal the extension was done wrong.

**Alternatives considered**:
- *Add a second, separate usage-reporting fake alongside the existing one.* Rejected: two fakes would let the recording tests drift away from the client the rest of the suite actually uses, and the seam being protected is precisely the existing fake's.
- *Hand-write response objects in each recording test.* Rejected for the same reason, plus duplication.
