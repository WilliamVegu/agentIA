# Implementation Plan: Cost Tracing

**Branch**: `feature/011-llm-generation-nodes` (stacked 011 + 012 + 013 — see Branch Note) | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/013-cost-tracing/spec.md`

## Summary

The platform calls a language model to generate microservices and records nothing about what those calls cost. This feature instruments the call path, prices each call against the provider's **actual** published rates (which vary by peak/off-peak and by cache hit/miss), aggregates per session, and produces a deterministic re-runnable report whose headline number is the average cost of a completed — and genuinely verified — generation.

Three findings from reconnaissance shape the plan, and each is recorded as a decision in [research.md](research.md):

1. **An unconditional recording proxy breaks seven existing test assertions.** `backend/tests/test_llm_factory.py` asserts `isinstance(model, ChatOpenAI)` (and the Gemini/Groq equivalents) in seven places, and reads `model.model`, `model.model_name`, `model.openai_api_base`. A wrapper around every returned client fails all of them. Because construction happens at `runner.py:812` — **inside** the stage boundary — the proxy can be applied only while a recording context is active. Tests that call the factory directly see exactly what they see today.
2. **The test double cannot report token usage.** `FakeResponse` in `backend/tests/fixtures/fake_model.py` is a plain dataclass carrying only `content` — no `usage_metadata`, no `response_metadata`. So FR-001's unknown-usage path is not a corner case, it is the *default* path for the entire existing test suite, and a usage-reporting double has to be added for the token path to be testable at all.
3. **The pricing is not two numbers per model.** Fetched from the provider's published page: Flash input ranges from $0.003 (cache hit, off-peak) to $0.30 (cache miss, peak) per million tokens. The schema has to carry peak/off-peak × cache hit/miss, and the basis is computed per call.

## Technical Context

**Language/Version**: Python 3.12 (backend); generated artifacts are Java 21 / Spring Boot 3.2.3 and are **not** touched by this feature

**Primary Dependencies**: MLflow (new — the tracking client), LangChain (already present; `AIMessage.usage_metadata` and `response_metadata` are the token/cache sources), pydantic-settings, SQLAlchemy + SQLite, pytest

**Storage**: two stores, deliberately. A dedicated local SQLite file is the durable system of record for cost records; MLflow receives the same records as telemetry when its tracking URI is reachable. Session-level costing metadata also lands on the existing session row via the additive-column mechanism established by 011 (T013) and reused by 012.

**Testing**: pytest, `.venv/bin/python -m pytest`. No test may call a real provider (Constitution Principle VI) — the existing fake client is used, extended with a usage-reporting double. Peak/off-peak is tested by controlling the call timestamp, not by waiting.

**Target Platform**: Linux server; the report is a command-line artifact run by a person or a job

**Project Type**: Web service (FastAPI backend) + analysis scripts. This feature touches the orchestration-side call path, the session record, and adds one script under `backend/scripts/`

**Performance Goals**: None material. Recording is one row per model call, and calls are already network-bound by three orders of magnitude. The report runs over persisted rows.

**Constraints**: Must not break the fake-client test seam or the seven `isinstance` assertions (spec SC-009). Must not add anything to the generated microservice's dependency surface (Principle VI). The report must make no live call and must be byte-identical across runs (FR-006). Cost must never be silently zero (FR-009).

**Scale/Scope**: 1 recording proxy + context, 1 pricing table, 2 persisted record types, 1 report script, 1 new dependency. Small surface, high correctness bar — the output is a stakeholder-facing number.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Bearing | Verdict |
| --- | --- | --- |
| **I. Arquitectura en Capas Estricta** | None. Layering is a property of generated Java; this feature touches orchestration only. | **PASS** |
| **II. Contratos Inmutables y Validación Temprana** | None. No DTO or generated contract changes. | **PASS** |
| **III. Manejo Centralizado de Excepciones y Limpieza de Código** | The recording proxy and the pricing lookup are single, shared code paths — the alternative (recording at each call site) is the duplication this Principle discourages. Recording must not introduce dead code: every branch (usage-known, usage-unknown, priced, unpriced, cache-hit, cache-miss) is exercised by a test. | **PASS** |
| **IV. Determinismo Offline-First y Aislamiento en Sandbox** | The report is explicitly offline and deterministic over persisted rows, and makes no live call (FR-006). Recording adds no network dependency to the *build* path — it writes locally first. The peak/off-peak basis is computed from a timestamp already present on the call, not fetched. | **PASS** |
| **V. Quality Gates y Ciclo Acotado de Auto-Reparación** | Relevant in a way worth stating: FR-007 excludes sessions whose verification was synthetic from the completed-session cost average. That is the same honesty constraint 012 established, now applied to money. A session that was not genuinely verified is not a completed generation, and must not be priced as one. The bounded-repair cap is untouched; correction attempts are recorded as real spend, which is what "bounded" is for. | **PASS** |
| **VI. Seguridad de Secretos y Frontera del Orchestrator** | Two hard requirements, both testable: (a) no API key may appear in any recorded row, the report, or MLflow parameters — only provider and model identifiers, mirroring 011's provenance rule; (b) the recording wrapper wraps the **orchestration-side** client only and must not enter the generated artifact's dependency surface. Additionally, the test suite must make zero provider calls, so the token path is exercised against a local double. | **PASS** |

**Gate verdict**: all six principles satisfied. **No Complexity Tracking entries required** — the design removes duplication (one proxy, one pricing lookup) rather than adding it.

## Project Structure

### Documentation (this feature)

```text
specs/013-cost-tracing/
├── plan.md                  # This file
├── spec.md                  # Feature specification
├── research.md              # Phase 0 output
├── data-model.md            # Phase 1 output
├── quickstart.md            # Phase 1 output
├── contracts/
│   ├── cost-record.md       # The per-call and per-session record contracts
│   └── cost-report.md       # The report's required contents and determinism rules
├── checklists/
│   └── requirements.md      # Spec quality checklist (16/16)
└── tasks.md                 # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── config.py                          # + MLFLOW_TRACKING_URI, cost store path
│   ├── services/
│   │   └── llm_factory.py                 # wrap the returned client when recording is active
│   ├── cost/                              # NEW package
│   │   ├── __init__.py
│   │   ├── recording.py                   # the proxy + the recording context (contextvars)
│   │   ├── store.py                       # durable local SQLite store (system of record)
│   │   ├── mlflow_sink.py                 # best-effort MLflow mirror; failure is non-fatal
│   │   └── pricing.py                     # table loading + per-call peak/off-peak + cache pricing
│   ├── resources/
│   │   └── model_pricing.json             # NEW — expanded schema, source cited in-file
│   ├── orchestrator/stages/runner.py      # establish the recording context around build_client
│   └── models/session.py                  # + additive session cost column (mechanism from 011/012)
├── scripts/
│   └── report_session_costs.py            # NEW — FR-004 report
└── tests/
    ├── fixtures/fake_model.py             # UPDATED: usage-reporting double (additive)
    ├── test_cost_recording.py             # NEW — proxy, context, unknown usage, seam guardrail
    ├── test_cost_pricing.py               # NEW — peak/off-peak, cache hit/miss, unpriced
    └── test_cost_report.py                # NEW — report contents, determinism, exclusions
```

**Structure Decision**: A new `app/cost/` package owns the concern end to end — recording, storage, MLflow mirroring, and pricing — so the call path only has to *establish a context* and the report only has to *read a store*. Pricing lives in the package rather than in the script because both the recorder (to price at write time) and the report (to re-price or verify) need it, and duplicating it would let the two drift.

**Branch Note**: this is the **third** feature on `feature/011-llm-generation-nodes`. The isolation requirement (nothing merges until review) still holds, but 013 adds an MLflow dependency and a new package, which is a materially larger review surface than 011 + 012. [012's constitution-recheck.md](../012-sandbox-verifier-honesty/constitution-recheck.md) §2 records the two-feature exception; extending it to three deserves an explicit decision at planning time rather than by default. Recorded, not assumed.

## Phase 0 — Research

See [research.md](research.md). All Technical Context unknowns were resolved by inspection and one fetched primary source; there are no open `NEEDS CLARIFICATION` items. Decisions: D1 conditional proxy, D2 recording context, D3 three storage decisions, D4 expanded pricing schema, D5 cache extraction and its upper-bound default, D6 peak window, D7 usage-reporting test double, D8 report determinism, D9 secret containment, D10 the branch question.

## Sequencing Constraint

**The first implementation task is extending the fake client to report usage, and confirming the synchronous path records end to end through the wrapper into the local store.**

The existing fake reports no usage, so any recording assertion written before it exercises only the unknown-usage path. SC-001 claims ten sessions produce records with **non-zero** token counts; without the extended fake that claim is untestable, and every downstream task that reads a recorded token count is unverifiable. See [research.md](research.md) D12.

The constraint on the task itself: **extend the fake, do not reshape it.** Existing tests assert on `.content` and `.calls`, so usage metadata is additive and defaulted, and no pre-existing assertion may be weakened to accommodate it.

## Phase 1 — Design

- [data-model.md](data-model.md) — the model-call record, the session cost record, the pricing entry, and the session-row addition.
- [contracts/cost-record.md](contracts/cost-record.md) — what must be recorded per call and per session, including the unknown-usage and unpriced rules.
- [contracts/cost-report.md](contracts/cost-report.md) — the report's required lines, the population statement, the exclusion rule, and the determinism requirement.
- [quickstart.md](quickstart.md) — runnable validation for each success criterion, including the offline/the-fake path and the peak/off-peak check.

### Post-Design Constitution Re-Check

*Re-evaluated after Phase 1 design.*

The gate verdict is **unchanged: all six principles satisfied**. The design decisions that carry constitutional weight:

| Design decision | Constitutional bearing | Assessment |
| --- | --- | --- |
| **The proxy is applied only while a recording context is active** | Principle III — no dead code; and the spec's SC-009 seam guarantee | Correct and required. It keeps seven existing assertions valid *and* keeps the recording guarantee undiluted in production, because production construction always happens inside the stage boundary that establishes the context. It is a bypass scoped by *when recording is on*, not by *which tests exist* — the distinction matters, since a test-shaped bypass would leave production unprotected. |
| **The local SQLite store is the system of record; MLflow is a mirror** | Principles IV and VI | **Approved, and FR-005 has been updated to state it directly** — it is no longer a reading of ambiguous wording. "Cost data is never lost" and "the report is deterministic" are both properties of one authoritative store; a primary/fallback pair would make the report's determinism depend on the tracking server, the exact failure FR-005 prevents. The destination is now a visualization layer whose absence is a non-event, and SC-006 holds by construction. |
| **A client implementing only sync invocation must not break when called async** | Principle III — no latent breakage | Required by D11. The existing fake implements only the sync form, so a wrapper that unconditionally forwards an async call would raise. The wrapper delegates async to sync and records it; a non-recording pass-through was rejected because it would create a second, quieter form of silent spend. |
| **Unknown usage is recorded, never zero** | Principle III — no silent fallbacks | A zero would be indistinguishable from a genuinely cheap call and would bias the headline figure downward. An explicit marker plus a report count is the honest form. |
| **An unpriced model is marked, never priced at zero** | Principle V — gate honesty | Same failure mode as 012's synthetic success, in money: a missing price silently becoming zero would understate spend. |
| **Cache-miss is the default when cache fields are absent** | Principle V | The conservative direction for a figure used to justify spend. Guessing a cache *hit* would understate cost. Recorded and counted on the report rather than hidden. |
| **No credential may appear in a cost record** | Principle VI | The record carries provider and model identifiers only. Tested, not assumed — the same invariant 011's provenance records carry. |

**No new violations. No Complexity Tracking entries added.**


---

## Implementation outcomes (T022)

All 22 tasks complete. Suite: **306 passed, 1 skipped** (baseline before this
feature: 263 passed, 1 skipped — the increase is this feature's tests only).

### The defect the red anchor caught

The recording context was first established around **client construction only**.
That is wrong, and only an end-to-end test could see it: the wrapper is applied
during construction, but the record is assembled when the call is actually
*invoked*, at which point the context had already closed. The result was records
with `session_id = None` and `stage = None` — written, but unattributable.

The fix is to span the **whole model stage** with the context: construction *and*
every invocation, including correction attempts. This is exactly why T001 wrote
the through-the-seam test first rather than unit-testing the wrapper in isolation
([research.md](research.md) D2, [constitution-recheck.md](constitution-recheck.md) §3.3).

### Verified

| Criterion | Result |
| --- | --- |
| SC-001 (fake path) | A call through the stage boundary records one priced row with non-zero tokens |
| SC-002 | The report prints the headline figure with its population |
| SC-003 | Two runs over unchanged data are **byte-identical** |
| SC-004 | A fallback-marked session is excluded from the headline and the exclusion count is printed |
| SC-005 | Unknown model and unknown usage both yield `NULL` cost, never zero; the report counts them |
| SC-006 | With `MLFLOW_TRACKING_URI` pointed at an unreachable port, both runs exit 0 and are byte-identical |
| SC-007 | Identical calls inside and outside the peak window differ by exactly 2.0× |
| SC-008 | The report states its basis, the peak window, and the cache-miss-assumed count |
| SC-009 | `test_llm_factory.py`'s seven `isinstance` assertions pass unmodified; the fake path is never wrapped |
| SC-010 | An async call on the sync-only fake does not raise **and is recorded** |

### Sample session (through the real seam)

| Field | Value |
| --- | --- |
| session / stage | `sample-session` / `DOMAIN` |
| provider / model | `deepseek` / `deepseek-flash` |
| input / output tokens | 4180 / 962 |
| cache-hit input tokens | 3200 (`peak = False`) |
| pricing basis | `off_peak/cache-aware` |
| **cost** | **$0.0007338000** |
| credential present | **no** |

Reconciles by hand: 3200 × $0.003 + 980 × $0.15 + 962 × $0.60, per million tokens.

### NOT verified

**SC-001's literal form — ten sessions against the real provider with non-zero
token counts — was not run.** It requires a provider key and spends real money, so
the test skips unless `AGENTIA_RUN_REAL_COST_TRACING=1` and `DEEPSEEK_API_KEY` are
both set. Recorded here as *not verified* rather than inferred from the fake path:
inferring it would be the same substitution feature 012 refused for its own
success criterion.

### Deviations from the plan worth recording

- **Pricing basis strings** are `peak/cache-aware`, `off_peak/cache-aware`,
  `peak/cache-miss-assumed` and `off_peak/cache-miss-assumed` — more specific than
  the `peak/cache-miss` example in [contracts/cost-record.md](contracts/cost-record.md)
  §2.1, because the report's cache-miss-assumed count needs to be derivable from
  the same field.
- **The store rejects a call record with no `call_id`.** Discovered while testing
  insertion-order determinism: a malformed write produced a junk row that changed
  the reported call count. A record without an identity cannot be de-duplicated on
  re-run, so it is refused and counted rather than stored.

