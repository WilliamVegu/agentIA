# Feature Specification: Cost Tracing

**Feature Branch**: `feature/011-llm-generation-nodes` (see Branch Note)

**Created**: 2026-09-28

**Status**: Draft

**Input**: User description: "emit per-session token and cost telemetry to MLflow so the average cost of a completed microservice generation is measurable and reportable. This is the number a stakeholder will see."

## Context

The platform generates microservices by calling a language model. Today it records **nothing** about what those calls cost: no token counts, no latency, no per-session totals. The consequence is that the platform's unit economics are unknown. No one can answer "what does one generated microservice cost us?" — which is the number a stakeholder will ask for first.

Two facts about the current system shape this feature:

1. **No token data is captured at all.** Nothing in the platform reads the token usage that model responses carry. Instrumentation has to be added, not extended.
2. **The call site is not where the requirement says it is.** The requirement asks that "every LLM call through `LLMFactory`" be recorded, but `LLMFactory` only *constructs* a client. The actual call is made by the generation stage. Recording at the factory alone would record nothing.

A third fact makes the headline number harder than it looks: the provider's published pricing is **not two numbers per model**. It varies by time of day (peak vs off-peak, a factor of two) and by whether the input was a cache hit (up to a factor of one hundred on the input side). The design therefore prices each call against the rate that applied *to that call* — its own timestamp and its own cache outcome — rather than picking one basis for the whole report. See FR-003.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every model call is recorded with its tokens and latency (Priority: P1)

An engineer runs a generation session. Each time the platform calls the model, a record is written capturing which session, which stage, which provider and model, how many input and output tokens the response reported, and how long the call took. No call is missed, including calls made during correction attempts.

**Why this priority**: Without this, nothing downstream is possible. A per-session total is a sum of these records; a defensible average is an average of those totals. It is also independently valuable — even before any cost figure exists, the token and latency data is real telemetry that answers "how many tokens does a generation actually take?".

**Independent Test**: Run a session that makes several model calls, then read the recorded call data back. Assert there is one record per call, each carrying a session identifier, stage name, provider, model, both token counts, and a latency.

**Acceptance Scenarios**:

1. **Given** a session in model mode, **When** a stage calls the model, **Then** a call record is written carrying session, stage, provider, model, input tokens, output tokens, and latency.
2. **Given** a stage that needs a correction attempt, **When** the retry calls the model, **Then** that call is recorded too and is distinguishable from the first.
3. **Given** a response that reports no token usage, **When** the call is recorded, **Then** the record exists and is explicitly marked as having unknown usage, rather than being dropped or silently recorded as zero.
4. **Given** a session in the deterministic (offline) mode, **When** it runs, **Then** no call records are written, because no model was called.

---

### User Story 2 - Each session aggregates to a cost and a status (Priority: P2)

After a session finishes, a single per-session record exists stating what it cost: total tokens in and out, a total cost derived from a pricing table, the wall-clock duration, how many model calls it made, and the session's outcome — including whether its verification was real or synthetic.

**Why this priority**: This is what turns call records into the answer a stakeholder wants. It depends on User Story 1 and on a pricing table, so it cannot come first.

**Independent Test**: Complete a session with a known number of calls, then read its per-session record and check the totals equal the sum of its calls, the cost matches the pricing table applied to those tokens, and the outcome fields match the session.

**Acceptance Scenarios**:

1. **Given** a completed session, **When** its aggregate is read, **Then** it carries the session identifier, specification name, terminal status, generation mode, and verification-fallback marking.
2. **Given** a session whose calls reported usage, **When** its aggregate is read, **Then** total input and output tokens equal the sum over its calls, and total cost equals those tokens priced by the table.
3. **Given** the same session, **When** its aggregate is read, **Then** the call count and duration are present and non-zero.
4. **Given** a session whose verification used a synthetic fallback, **When** its aggregate is read, **Then** that fact is carried on the record so it can be separated from genuine completions.

---

### User Story 3 - The cost report is durable and reproducible (Priority: P3)

An analyst runs a single command and gets the cost figures: how many sessions, how many completed, blocked, and unverifiable; the average cost of a **completed** session; the average across all sessions; the 50th, 90th, and maximum cost; and which stage consumes the most. Running it again on the same data prints identical numbers.

**Why this priority**: It is the deliverable a stakeholder actually reads, but it is worthless if the underlying records are missing or wrong, so it ranks below both. It is also the piece that makes the data trustworthy: reproducibility is what allows the figure to be defended.

**Independent Test**: Run the report twice against the same persisted data and diff the output. Then run it against data containing a fallback-marked session and confirm that session is excluded from (or reported separately from) the completed-session average.

**Acceptance Scenarios**:

1. **Given** persisted session records, **When** the report runs, **Then** it prints session counts by outcome, the average cost per completed session, the average across all sessions, p50/p90/max, and a per-stage cost breakdown.
2. **Given** the same data, **When** the report runs a second time, **Then** every printed figure is identical.
3. **Given** a fallback-marked session, **When** the report runs, **Then** it is excluded from the completed-session average and its exclusion is visible in the output.
4. **Given** no persisted data, **When** the report runs, **Then** it exits cleanly stating that there is nothing to report, rather than printing zeroes that look like a real measurement.
5. **Given** the telemetry backend is unreachable, **When** sessions run and the report is executed, **Then** the data is still readable and the report still produces the same figures.

---

### Edge Cases

- **A response that reports no usage.** Some responses, and every test double, may not carry token counts. A missing count must be recorded as unknown and must not silently become zero, or the average will be pulled down by calls that were never counted. The report must state how many calls had unknown usage.
- **A pricing entry that does not exist for a provider/model pair.** Cost must not be silently zero. An unpriced pair must be marked unpriced so the total is not understated, and the report must surface it.
- **Peak vs off-peak, and cache hits.** The provider's published rates differ by time of day and by whether input was cached; a flat two-number table cannot reproduce them. Resolved by pricing every call against its own timestamp and cache outcome (FR-003). The residual is the **provider's holiday calendar**: the platform does not model it, so a call the provider prices off-peak on a holiday is priced at peak here. That overstates rather than understates, and is disclosed in the report's basis statement.
- **A response that reports prompt tokens but no cache breakdown.** Treated as a cache miss — the upper bound — and counted on the report. Guessing a hit would understate cost, which is the more dangerous error for a figure used to justify spend.
- **A session that crashes mid-run.** Partial call records must survive and the session must not be counted as completed.
- **Sessions that never call a model.** Offline/deterministic sessions must not appear as zero-cost model sessions, which would drag the average toward zero.
- **Re-running the report while a session is in flight.** The report reads persisted data only and must not be affected by an in-progress session, nor make any live call.
- **Cost of correction attempts.** Retries within a stage are real spend and must be counted, not folded away. A session that needed corrections genuinely cost more.
- **A client that implements only one of the two invocation forms.** The wrapper must not turn a working synchronous client into a client that raises when called asynchronously. Whichever fallback is chosen, the recording consequence must be documented rather than left to be discovered: a delegated call is recorded, a pass-through is not.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every model call made during a session MUST be recorded with: timestamp, stage name, provider, model, input token count, output token count, latency, and the session it belongs to.
  - The recording point MUST be a **wrapper around the client the factory returns**, so a call cannot be made without being recorded. Recording at the stage's call site was rejected: it is a convention, not a guarantee, and the first future call site that forgets it silently under-reports cost.
  - The wrapper MUST record on **every** invocation, including asynchronous ones, before returning the response.
  - The stage name and session identifier MUST reach the wrapper through a **context established by the stage execution boundary** (feature 011's seam), because the factory constructs clients before any stage is known.
  - **Test-seam guardrail**: the wrapper MUST NOT break the existing fake-client seam. The fake client must remain usable with recording inert, and the wrapper must present the same interface the tests already use. If the wrapper interferes with the fake path, the fix is a bypass condition that preserves the tests — never a weakening of the tests or of the recording guarantee.
  - **Partial-interface guardrail**: a client may implement only synchronous invocation, only asynchronous invocation, or both. The existing fake client implements **only** the synchronous form. The wrapper MUST NOT raise when an asynchronous call is made against a client that does not implement it. It MUST either delegate the asynchronous call to the synchronous implementation or pass it through cleanly on an explicit no-recording path — and whichever it does MUST be documented, because the two have different recording semantics (a delegated call can be recorded; a pass-through cannot).
- **FR-001a**: A model call whose response reports no token usage MUST still produce a record, marked as usage-unknown. It MUST NOT be dropped, and MUST NOT be recorded as zero, because a silent zero pulls the average down and is indistinguishable from a genuinely cheap call.
- **FR-002**: Each session MUST aggregate to one record carrying: session identifier, specification name, terminal status, generation mode, verification-fallback marking, total input tokens, total output tokens, total cost, duration, and model-call count.
- **FR-003**: The pricing table MUST map each supported provider/model pair to rates that reproduce the provider's published billing, and MUST cite the source it was seeded from. The table MUST be **seeded from the published page, verified by fetching it — never recalled or estimated**.
  - The schema MUST carry **both peak and off-peak** rates **and** both **cache-hit and cache-miss** input rates, plus the output rate. A flat two-number-per-model table was rejected because it cannot represent the published rates: on the Flash model, input ranges from $0.003 (cache hit, off-peak) to $0.30 (cache miss, peak) per million tokens — a factor of one hundred — and peak/off-peak alone differs by two.
  - Cache-hit input tokens MUST be read from the response's usage metadata (the provider reports a prompt-cache-hit token count alongside the total prompt tokens). Cache-miss input tokens are the remainder of the prompt tokens.
  - The peak/off-peak basis MUST be computed **per call from that call's timestamp**, not chosen once per session or per report.
  - If a response does not report cache fields, the call MUST be priced as **cache-miss** — the upper bound — and the count of calls priced this way MUST be surfaced on the report. Guessing a cache hit would understate cost, which is the more dangerous direction for a figure used to justify spend.
- **FR-003a**: The report MUST state the pricing basis it used, including the peak window definition and how many calls were priced on the cache-miss upper bound. A cost figure whose basis is unstated cannot be reconciled against an invoice.
- **FR-004**: A reporting script MUST print: the number of sessions; the count completed, blocked, and unverifiable; the average cost per completed session; the average cost per session regardless of status; the 50th, 90th and maximum cost; and a cost breakdown by stage identifying the most expensive stage.
- **FR-005**: Cost records MUST be written to a **durable local store that is the authoritative system of record**, so cost data is never lost and the report never depends on an external service being up.
  - A telemetry destination MAY additionally receive mirrored records when it is reachable. Its **absence MUST be a non-event**: no error surfaced, no retry storm, no difference in session behaviour, and no difference in the report.
  - The report reads the local store **only**. The telemetry destination is a visualization layer, not a source of truth.
  - **Rationale, recorded because it inverts an earlier reading**: "never lost" and "a deterministic report" are both properties of having exactly one authoritative store. If the destination were authoritative, the report's determinism would depend on its availability — the very failure this requirement exists to prevent. Mirroring makes the destination optional by construction; a primary/fallback pair would make it load-bearing.
- **FR-006**: The report MUST be deterministic and re-runnable over persisted data. It MUST NOT make any live model call.
- **FR-007**: Sessions whose verification used a synthetic fallback MUST be excluded from the average cost per completed session, or reported in a clearly separate line. They MUST NOT be counted as successful generations.
- **FR-008**: The report MUST state, alongside the headline figure, how many sessions and how many calls it was computed over, how many were excluded, and how many calls had unknown token usage. A cost figure without its population is not defensible.
- **FR-009**: A model call whose provider/model pair is absent from the pricing table MUST be marked unpriced rather than priced at zero, and the count of unpriced calls MUST appear on the report.

### Key Entities

- **Model Call Record**: one call to a model. Carries the session it belongs to, the stage that made it, the provider and model, the token counts reported by the response (or an explicit unknown marker), the latency, and a timestamp.
- **Session Cost Record**: the per-session aggregate. Carries the session identifiers and outcome, the summed tokens and cost, duration, and call count.
- **Pricing Table**: the mapping from provider/model to rates, with the source of those rates recorded alongside them.
- **Cost Report**: the printed output. Not stored, but its contents are a contract: counts by outcome, the averages, the percentiles, the per-stage breakdown, and the population statement.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Running ten sessions against DeepSeek produces ten session cost records, each with non-zero token counts.
- **SC-002**: The report prints an average cost per completed session, and the figure is accompanied by the population it was computed over.
- **SC-003**: Running the report twice over unchanged data produces byte-identical numbers.
- **SC-004**: Sessions whose verification used a synthetic fallback are excluded from the completed-session average, or shown on their own line, and the exclusion count is visible.
- **SC-005**: Zero calls are recorded as costing zero because their model was missing from the pricing table; the unpriced count is instead reported.
- **SC-007**: A call made inside the peak window and an otherwise identical call made outside it are priced differently, in the ratio the published rates specify, proving the peak/off-peak basis is computed per call.
- **SC-008**: The report states its pricing basis, the peak window, and the number of calls priced on the cache-miss upper bound; 100% of reports with at least one call carry these fields.
- **SC-009**: The existing fake-client seam still works: the recording wrapper is inert for the fake path and every pre-existing test that uses the fake passes unmodified.
- **SC-010**: Calling the asynchronous entry point on a client that implements only the synchronous one does **not** raise. A test exercises exactly that combination — the fake client, wrapped, called asynchronously — and asserts it completes and that the documented behaviour (delegated-and-recorded, or passed-through-and-not-recorded) is what actually happens.
- **SC-006**: With the telemetry destination unreachable, the same ten sessions still produce ten readable records and the report still prints the same figures.

## Assumptions

- **The offline generation mode costs nothing and is not a cost record.** A session that never calls a model is not a zero-cost model session; including it would drag the average toward zero and misrepresent the unit economics. Such sessions are excluded from the averages and counted separately.
- **Correction attempts are counted.** A retry is real spend. The platform's correction loop issues real calls, and those calls are recorded like any other.
- **"Completed" means the session reached its verified terminal state, and its verification was real.** A session that was blocked, or whose verification was synthetic, is not a completed generation for costing purposes.
- **The local store is authoritative; the telemetry destination is a mirror.** Recorded as a deliberate decision that inverted the earlier reading of FR-005. The consequence to keep in view: the report's figures are a property of the local store alone, so a telemetry destination that was down for some sessions changes nothing, and one that receives partial data cannot make the report wrong.
- **Token counts come from the provider's response, not from an estimate.** No tokenizer is run locally to guess; if the response does not report usage, the call is marked unknown. Estimating would make the headline figure less defensible, not more.
- **The cache-hit field path is taken as stated and must be confirmed against a real response during implementation.** The platform has captured no real provider responses, so the exact location of the prompt-cache-hit count in the response metadata cannot be verified from anything in this repository. FR-003's cache-miss default is the safety net: if the field is absent or named differently, the call is priced at the upper bound and counted on the report rather than silently mispriced. A real response must be inspected before the figure is presented as exact.
- **Peak windows are defined by the provider, not by the platform.** Peak is the published weekday window; off-peak is everything else, including weekends and the provider's public holidays. The platform does not attempt to model the provider's holiday calendar — a call the provider prices off-peak on a Chinese public holiday would be priced at peak here, which overstates. This is recorded rather than hidden, and the report's basis statement is where it belongs.
- **The recording wrapper is part of the platform, not of the generated artifact.** It wraps the orchestration-side client only; nothing is added to the generated microservice's dependency surface (Constitution Principle VI).
- **The report is a command-line artifact, not a service.** It is run by a person or a job and prints to standard output.
- **Currency is US dollars**, matching the provider's published rates.
- **Constitution Principle VI still holds.** The automated test suite must not make network calls to a model provider, so telemetry tests use the existing fake client. Recording must therefore be tested against a response double that reports usage, which does not exist today and must be added.

## Dependencies

- The model factory and the generation stage's call site, which is where calls are made and where the stage name is known.
- Feature 012's verification-fallback marking, which FR-007 depends on to separate synthetic completions.
- Feature 011's generation journal, which already records per-stage durations and request counts and is the natural place to read a session's stage breakdown from.
- A telemetry client, which the platform does not currently depend on and which must be added.
- The provider's published pricing page, cited by the pricing table.

## Out of Scope

- A web dashboard.
- Per-user attribution.
- Cost alerts and budgets.
- Model comparison.

## Branch Note

The working branch is still `feature/011-llm-generation-nodes`, carrying the stacked 011 + 012 arc. Feature 013 would extend that stack to a third feature. No branch was created (no `before_specify` hook is registered). This is worth a deliberate decision at planning time rather than inheriting it by default: the isolation requirement (nothing merges to the main line until review) still holds, but three features on one branch is a materially larger review surface than two.
