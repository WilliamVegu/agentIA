# Specification Quality Checklist: Cost Tracing

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-28
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- **All 16 items pass.** The two clarifications were raised and resolved on 2026-09-28; both are folded into the requirements. Zero markers remain.

## Validation Detail

### Verified during specification (not guessed)

The pricing source was fetched, not recalled. The official page is
<https://api-docs.deepseek.com/quick_start/pricing> (HTTP 200). What it says:

| | `deepseek-flash` | `deepseek-v4-pro` |
| --- | --- | --- |
| Input, cache **hit**, off-peak | $0.003 | $0.022 |
| Input, cache **hit**, peak | $0.006 | $0.044 |
| Input, cache **miss**, off-peak | $0.15 | $0.66 |
| Input, cache **miss**, peak | $0.30 | $1.32 |
| Output, off-peak | $0.60 | $1.98 |
| Output, peak | $1.20 | $3.96 |

All per 1M tokens. Peak hours are 01:00–04:00 and 06:00–10:00 UTC, Monday–Friday,
excluding Chinese public holidays; off-peak is half of peak. The page also confirms
that the two model names the platform already configures (`deepseek-flash`,
`deepseek-v4-pro`) are the **current** names, and that the legacy
`deepseek-v4-flash` aliases are billed at the Flash price — which the platform
already normalises. **No model-name guesswork is required.**

### Open marker 1 — FR-003: which pricing basis?

The published rates are not two numbers per model. They vary by peak/off-peak
(2×) and by cache hit/miss (up to 50× on input for Flash: $0.003 vs $0.15). The
requirement asks for `{input_per_million, output_per_million}`. That schema
cannot reproduce the provider's billing, so a basis must be chosen deliberately
rather than by accident. See Q1.

### Open marker 2 — FR-001: which choke point records the call?

The requirement says "every LLM call through `LLMFactory`", but `LLMFactory`
only constructs a client (verified in `backend/app/services/llm_factory.py`); the
call is made by the generation stage at `backend/app/orchestrator/stages/runner.py:869`
via `client.invoke(request)`. A recorder placed only in the factory would record
zero calls. Two choke points are defensible with different failure modes. See Q2.

### Findings recorded, no marker needed

- **No token data is captured anywhere today.** A grep for `usage_metadata`,
  `response_metadata`, `token_usage`, `input_tokens` and `output_tokens` across
  the backend returns nothing. This is instrumentation added from scratch, and the
  test doubles do not currently report usage — FR-001's edge case and Principle VI
  together mean the fake client must gain usage reporting.
- **The telemetry client is not a current dependency.** It is absent from the
  environment and from `backend/requirements.txt`, so FR-005's durability
  requirement is load-bearing rather than a nicety: the platform must work when
  the primary destination is missing entirely.
- **FR-002's outcome fields already exist.** `spec_name` and `status` are session
  columns, `generation_mode` comes from feature 011, and
  `verification_fallback_used` comes from feature 012. No new session state is
  needed for the outcome half of the aggregate.
- **Feature 011's journal already holds per-stage durations and request counts**,
  so FR-004's per-stage breakdown has an existing source for the non-token
  dimensions; only the token/cost dimension is new.

### Deliberate scope boundary

Currency, the command-line nature of the report, and the treatment of offline
sessions and unpriced models are recorded as assumptions rather than asked about,
because each has a clearly better default. Only the two markers above lack one.

## Resolved Clarifications

### Q1 — Which pricing basis? → **Option A: expanded schema, priced per call**

FR-003 now requires the table to carry **both peak and off-peak** rates **and** both
**cache-hit and cache-miss** input rates. The basis is computed **per call** from
that call's timestamp, and cache-hit input tokens are read from the response's
usage metadata.

- Cache-miss input = prompt tokens − cache-hit input tokens.
- If cache fields are absent, the call is priced as **cache-miss (upper bound)**
  and the count of such calls is surfaced on the report (FR-003a, SC-008).
- FR-003a requires the report to state its basis, the peak window, and the
  upper-bound count.

**Recorded limitation**: the platform does not model the provider's public-holiday
calendar, so a holiday call the provider prices off-peak is priced at peak here.
It overstates rather than understates, and is disclosed in the basis statement.

### Q2 — Which choke point records the call? → **Option A: recording proxy**

FR-001 now requires a **wrapper around the client the factory returns**, recording
on every invocation (sync and async) before returning. Stage name and session
identifier reach the wrapper through a **context set by feature 011's stage
execution boundary**, because the factory constructs clients before any stage is
known. Recording at the call site was rejected as a convention rather than a
guarantee.

**Test-seam guardrail folded in**: the wrapper must not break the existing
fake-client seam. The fake must remain usable with recording inert, and the
wrapper must present the same interface the tests already use. If it interferes
with the fake path, the fix is a bypass condition that preserves the tests — never
a weakening of the tests or of the recording guarantee. Captured as **SC-009**.
