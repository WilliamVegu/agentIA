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
| **The local SQLite store is the system of record; MLflow is a mirror** | Principles IV and VI | Deliberate reading of FR-005, recorded in D3. "Cost data is never lost" and "the report is deterministic" are both easier to guarantee with one authoritative local store than with a primary/fallback pair that the report would have to union and de-duplicate. SC-006 then holds by construction rather than by luck. **If MLflow was intended as the system of record, this is the one decision to reverse**, and it is a contained change. |
| **Unknown usage is recorded, never zero** | Principle III — no silent fallbacks | A zero would be indistinguishable from a genuinely cheap call and would bias the headline figure downward. An explicit marker plus a report count is the honest form. |
| **An unpriced model is marked, never priced at zero** | Principle V — gate honesty | Same failure mode as 012's synthetic success, in money: a missing price silently becoming zero would understate spend. |
| **Cache-miss is the default when cache fields are absent** | Principle V | The conservative direction for a figure used to justify spend. Guessing a cache *hit* would understate cost. Recorded and counted on the report rather than hidden. |
| **No credential may appear in a cost record** | Principle VI | The record carries provider and model identifiers only. Tested, not assumed — the same invariant 011's provenance records carry. |

**No new violations. No Complexity Tracking entries added.**
