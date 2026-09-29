# Contract — Cost Records

**Feature**: 013-cost-tracing · **Implements**: FR-001, FR-001a, FR-002, FR-003, FR-007, FR-009

Behavioural contract for what must be recorded, per call and per session. Field-level shapes are in [data-model.md](../data-model.md).

---

## 1. Per-call recording

### 1.1 The recording point

Recording happens in a **wrapper around the client the factory returns**, established only while a recording context is active (research D1). The wrapper records on **every** invocation — synchronous and asynchronous — **before** returning the response.

Two properties must hold:

- **Unbypassable in production.** Any code path that constructs a client inside the stage boundary is wrapped, including a future call site that knows nothing about recording. Recording at the call site was rejected precisely because it is a convention rather than a guarantee.
- **Invisible outside production.** Direct factory calls — including all of `test_llm_factory.py`, which asserts `isinstance(model, ChatOpenAI)` and the Gemini/Groq equivalents in seven places — MUST receive the unwrapped client. The condition is *"is recording active"*, never *"is this a test"*. A bypass keyed on test presence would leave production unprotected.

### 1.1a Clients that implement only one invocation form

A client may provide the synchronous entry point, the asynchronous one, or both. The existing fake client provides **only** the synchronous one (verified: `backend/tests/fixtures/fake_model.py` defines `invoke` and no `ainvoke`).

**Contract**

- Calling the asynchronous entry point on the wrapper MUST NOT raise when the wrapped client lacks it.
- The wrapper MUST probe the client at construction and choose a path accordingly.
- The chosen fallback MUST be **documented**, because the options differ in recording semantics:

| Fallback | Recording | Verdict |
| --- | --- | --- |
| Delegate the async call to the client's sync entry point, run off the event loop | **Recorded** — the call happened and cost money | **Chosen** |
| Pass the async call through without recording | **Not recorded** — silent spend | Rejected |

- A test MUST exercise the exact combination — the fake client, wrapped, invoked asynchronously — and assert both that it does not raise and that the documented behaviour is what occurs (SC-010). Asserting only "does not raise" would let the recording silently change later.

### 1.2 Required fields

Every recorded call carries: session identifier, stage name, provider, model, timestamp, latency, input tokens, output tokens, and — where reported — cache-hit input tokens. Plus the derived `usage_known`, `cache_basis_known`, `peak`, `priced`, `cost_usd`, and `pricing_basis`.

The session identifier and stage come from the **recording context set by the stage execution boundary** (feature 011's seam). The factory constructs clients before any stage is known, so they cannot come from the factory's own arguments.

### 1.3 Unknown usage

A response that reports no token usage MUST still produce a record, marked `usage_known = False`.

- It MUST NOT be dropped: an unrecorded call is invisible spend.
- It MUST NOT be recorded as zero: zero is indistinguishable from a genuinely cheap call and biases the average downward.
- The count of such calls MUST appear on the report (FR-008), because an average computed over a population with unknown members is only defensible if the reader knows how many.

The existing test double reports no usage, so **this is the default path in the current suite**, not an edge case. That is correct behaviour and it is exactly why the token path needs its own usage-reporting double to be testable at all.

### 1.4 Unpriced models

A call whose `(provider, model)` pair is absent from the pricing table MUST be marked `priced = False` with a `NULL` cost.

- It MUST NOT be priced at zero. A missing price silently becoming zero understates spend — the same failure mode as a synthetic verification success, expressed in money.
- The count of unpriced calls MUST appear on the report (FR-009).

### 1.5 Credentials

No API key may appear in a call record. The wrapper sits directly beside the credential — it wraps a client constructed *with* a key — so the key is in scope at the recording site, which is where leaking it is easiest. Only provider and model identifiers are recorded. Tested.

### 1.6 Deterministic sessions

A session in the deterministic (offline) generation mode calls no model and therefore records **no call rows**. It must not appear as a zero-cost model session.

---

## 2. Per-call pricing

### 2.1 Basis selection

The rate set applied to a call is chosen by `(provider, model)` **and** by two properties of that call:

| Dimension | Source | Values |
| --- | --- | --- |
| Peak / off-peak | The call's **own timestamp** | Peak is 01:00–04:00 and 06:00–10:00 UTC, Monday–Friday; everything else is off-peak |
| Cache hit / miss | The response's usage metadata | Per-token split; see 2.2 |

`pricing_basis` records what was applied (e.g. `peak/cache-miss`) so a figure can be reconciled later.

**The basis is per call, not per session and not per report.** A session spanning the peak boundary, or mixing cached and uncached prompts, is genuinely priced at more than one rate.

### 2.2 Cache handling

Cache-hit input tokens are read from the response's usage metadata; cache-miss input is the remainder of the prompt tokens:

```
cache_miss_input = input_tokens - cache_hit_input_tokens
```

**When the response reports no cache breakdown, the call is priced as a full cache miss** — the upper bound — and counted as `cache_miss_assumed_calls`.

Guessing a cache *hit* would understate cost. For a figure used to justify spend, overstating is the safer error, and it is visible on the report rather than hidden in the arithmetic.

### 2.3 Verification limitation

The platform has captured **no real provider responses**, so the exact metadata path for the cache-hit count cannot be confirmed from this repository. It is taken as given by the specification's author and **must be confirmed against a real response before any figure is presented as exact**.

The cache-miss default in 2.2 is the safety net: if the path is wrong or absent, calls are priced at the upper bound and counted, rather than silently mispriced as cache hits. This is a limitation to disclose, not a detail to bury.

### 2.4 Peak-window limitation

The platform does not model the provider's public-holiday calendar, so a call the provider prices off-peak on a holiday is priced at peak here. Overstates, never understates. Disclosed in the report's basis statement (FR-003a).

---

## 3. Per-session aggregation

Each session aggregates to one record carrying: session identifier, specification name, terminal status, generation mode, verification-fallback marking, total input tokens, total output tokens, total cost, duration, and call count. Plus three honesty counters: `usage_unknown_calls`, `unpriced_calls`, `cache_miss_assumed_calls`.

**Contract**

- Totals are sums over the session's call rows. `usage_known = False` calls contribute to no total and are counted separately — they are not zeros.
- `total_cost_usd` is `NULL` when no call had a known cost, never `0`.
- `verification_fallback_used` is copied from the session's persisted verification metrics (feature 012), so FR-007's exclusion is a property of the record rather than a join.
- A session with zero call rows is recorded as a deterministic session, not as a zero-cost model session.
- Aggregation is idempotent: re-aggregating a session overwrites its row, so a re-run does not double-count.

---

## 4. Consumer obligations

| Consumer | Obligation |
| --- | --- |
| The recording wrapper | Record every invocation before returning; never drop a call; never write a credential |
| The pricing lookup | Never price an unpriced model at zero; never assume a cache hit |
| The aggregator | Sum only known values; count the unknown ones; keep the fallback marking |
| The report | Apply the exclusion rule in [cost-report.md](cost-report.md) §3 and print the population statement |
| Any future consumer | A cost figure without its population, its basis, and its unknown/unpriced counts is not defensible and must not be published |

---

## 5. Non-goals

- The accuracy of the provider's reported token counts. The platform records what the response says and does not re-tokenize to second-guess it.
- The provider's holiday calendar (see 2.4).
- Cost attribution to users, teams, or projects.
- Budget enforcement or alerting.
