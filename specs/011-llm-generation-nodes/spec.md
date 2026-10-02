# Feature Specification: LLM-Driven Generation Stages

**Feature Branch**: `feature/011-llm-generation-nodes`

**Created**: 2026-09-28

**Status**: Draft

**Input**: User description: "Migrate the five deterministic generation nodes to LLM-driven generation. The scaffolder, domain, service, controller, and test nodes currently emit Java from hardcoded Python f-strings. Each node SHALL instead invoke LLMFactory.get_chat_model() with a mechanism-explicit system prompt and SHALL pass the LLM response through the existing constitutional validators before writing files to disk."

**Terminology**: this specification calls the five steps **stages**. They are implemented as the graph's `scaffolder`, `domain`, `service`, `controller`, and `test` node callables under `backend/app/orchestrator/nodes/`; the word "node" is used only when naming those callables. The `Input` field above preserves the requester's verbatim wording, which uses "nodes".

## Context

The platform currently synthesizes a microservice in two halves. A language model produces the *specification* half — the requirements draft, the user stories, and the architecture blueprint — and then five deterministic stages turn that blueprint into Java source by emitting fixed text templates whose only variables are blueprint field values. The result is that two blueprints differing in domain semantics (validation constraints, attribute types, acceptance scenarios) produce byte-identical Java apart from identifier substitution.

This feature moves the *synthesis* half onto the language model as well, so that the blueprint's meaning survives into the generated source, while keeping the platform's constitutional guarantees intact by refusing to persist any artifact that fails compliance validation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Blueprint semantics reach the generated service (Priority: P1)

A platform user submits a blueprint describing a domain with specific attribute constraints and acceptance scenarios. Instead of receiving boilerplate whose field names are substituted from the blueprint, they receive a service whose generated source demonstrably reflects those constraints — the validation annotations match the declared constraints, the acceptance scenarios have corresponding tests, and the code is organized around the meaning of the declared entities.

**Why this priority**: This is the entire reason for the migration. Without it, the other stories describe a safer version of an unchanged product. It is the minimum viable slice: a user can judge this outcome by reading the generated code.

**Independent Test**: Run two sessions from two blueprints that declare the same entity names but different attribute constraints and different acceptance scenarios, then compare the generated sources. The two outputs must differ in ways that track the differing constraints and scenarios. A second, independent check compares output against the frozen pre-migration baseline for one blueprint and confirms the generated source is no longer simply the template with identifiers substituted.

**Acceptance Scenarios**:

1. **Given** a blueprint declaring an entity attribute with a non-nullable constraint and an email-shaped constraint, **When** the generation session completes, **Then** the generated source for that entity carries validation annotations that correspond to those declared constraints, and they are not the same annotations that would be emitted for an unconstrained attribute of the same type.
2. **Given** two blueprints that differ only in the declared acceptance scenarios for one entity, **When** both sessions complete, **Then** the generated test source for that entity differs in the tests it defines, tracking the scenarios rather than a fixed set of test method names.
3. **Given** a blueprint declaring an entity relationship or naming convention that the pre-migration templates never expressed, **When** the session completes, **Then** the generated source reflects that relationship rather than treating the entity in isolation.

---

### User Story 2 - No non-compliant artifact is ever persisted (Priority: P2)

An engineering lead reviews a session workspace and finds only artifacts that satisfy the platform's constitutional rules — correct layering, immutable API contracts, centralized error handling, no prohibited annotation usage, no leaked credentials. Artifacts that would have violated those rules were never written, and the session reports what blocked them.

**Why this priority**: Moving generation onto a language model introduces a class of artifact the platform has never produced before: plausible-looking code that breaks the platform's own rules. The pre-write gate is what makes the migration safe to enable, and it is the second thing a reviewer will check.

**Independent Test**: Drive a generation stage with a model response that deliberately violates one constitutional rule (for example, a controller that reaches directly into persistence) and confirm that no file from that response reaches the workspace, that the session reports the violation with the offending artifact identified, and that the session either recovers within its correction budget or reaches a terminal state rather than looping. Repeat per constitutional rule.

**Acceptance Scenarios**:

1. **Given** a model response for the API layer that would violate layer isolation, **When** the stage attempts to persist it, **Then** no part of that response is written to the workspace and the violation is reported with the offending artifact identified.
2. **Given** a model response for a data-contract artifact that is not an immutable contract, **When** the stage attempts to persist it, **Then** the artifact is rejected before any file is written.
3. **Given** a model response that omits the artifact required by a whole-project rule, **When** the accumulated artifact set is validated, **Then** the omission is detected even though the individual response was internally well-formed.
4. **Given** a model response containing an embedded credential, **When** validation runs, **Then** the artifact is rejected and the session reports a security-category block.
5. **Given** a stage whose first two responses violate a rule and whose third response satisfies it, **When** the stage completes, **Then** only the third response is persisted and the two rejected attempts remain recorded in the session's correction history.

---

### User Story 3 - Generation is attributable and bounded (Priority: P3)

An operator investigating a quality regression can determine which provider, which model, and which instruction revision produced a given artifact, and can rely on a session never exceeding a documented number of model requests or running indefinitely. When a session does block, the operator can read the full trajectory of rejected attempts and the violations that caused them.

**Why this priority**: The migration multiplies per-session model consumption from near-zero to several requests, and makes output depend on an external, versioned dependency. Operability and auditability are needed before this runs unattended, but the platform is usable without them for a manual pilot.

**Independent Test**: Complete a session with a live model and inspect the recorded provenance for each generated artifact — provider, model, and instruction revision must all be present and must match the configured values. Then run a session under a fault-injection condition where every model response is non-compliant, and confirm the session terminates within the documented request budget, reports a human-intervention state, and retains the complete correction history without discarding it on exhaustion.

**Acceptance Scenarios**:

1. **Given** a session executed with provider and model explicitly configured, **When** the session completes, **Then** every generated artifact is associated with the provider, model identifier, and instruction revision that produced it.
2. **Given** a session in which no model response ever passes validation, **When** the session runs to completion, **Then** it terminates within the documented request budget, writes no non-compliant artifact, and reaches the human-intervention state rather than retrying indefinitely.
3. **Given** a session executed with no model credentials available, **When** the session completes, **Then** it produces a complete, buildable service using the established offline generation behavior.
4. **Given** a session that exhausted its correction budget, **When** an operator inspects the session, **Then** the violations identified at each attempt and the model's response at each attempt are all still available.

---

### Edge Cases

- **Model unavailable or credentials absent.** No model client can be constructed. The session must still produce a complete service using the established offline behavior; it must not fail the session or write partial output.
- **Model returns no content, or content truncated mid-artifact.** The response is unusable. No file is written from it; the stage either retries within budget or the session blocks.
- **Model wraps source in prose or a fenced block.** The artifact is extractable. Extraction must locate the source and discard surrounding commentary without corrupting the emitted file.
- **Model returns several artifacts when one was requested, or one artifact where several were required.** Ambiguous responses must not be persisted silently; the stage either resolves the mapping deterministically or rejects the response.
- **Correction attempts oscillate.** Attempt two introduces a different violation than attempt one, or reintroduces the original one. The budget is consumed regardless; the session must block on exhaustion rather than continue, and the history must show the oscillation.
- **Correction budget is exhausted while the session still has sandbox repair budget available.** The two budgets are independent. Generation-stage exhaustion blocks the session; it does not defer the failure to the sandbox repair loop, whose cap is neither shared nor decremented by generation corrections.
- **Model proposes a dependency not present in the offline build environment.** The generated build configuration must not be persisted with that dependency, since the hermetic offline build would fail or, worse, be silently satisfied by an environment fallback.
- **Whole-project rule satisfied only by accumulation.** A stage that produces no controller cannot itself satisfy "a centralized error handler exists"; its artifacts must not be rejected for a rule that only the accumulated set can satisfy.
- **Validation passes but the offline build later fails.** Out of scope for this feature's gate, but the session must still reach the existing sandbox verification and repair behavior unchanged.
- **Blueprint is large enough that the payload plus instruction approaches the model's context limit.** The stage must still produce a bounded response or block; it must not emit a truncated artifact.
- **Same blueprint generated twice.** Output differs across runs. The platform must not depend on byte-level reproducibility of generated source; provenance recording is what makes runs comparable.
- **Offline mode combined with a compliance violation.** There is no model to correct, so the offline behavior is used and existing validation semantics apply unchanged. The correction budget is not consumed, because no request was issued.

## Requirements *(mandatory)*

### Functional Requirements

**Generation mechanism**

- **FR-001**: Each of the five generation stages — project scaffolding, domain modeling, service layer, API layer, and test synthesis — MUST obtain the source artifacts it produces by requesting them from the configured language model, rather than from content embedded in the application's own source code.
- **FR-002**: Each stage MUST supply the model with a system instruction that explicitly states the technology contract the output must satisfy (language version and features, framework generation, namespace conventions, layering direction, contract immutability, declarative validation, and the required test approach), so the model is not left to infer the platform's conventions.
- **FR-003**: Each stage MUST supply the model with a task payload derived from the session blueprint — service identity, package, entities with their attributes, types and constraints, user stories, and acceptance scenarios — rather than a generic or identifier-only instruction.
- **FR-004**: The system MUST NOT write any artifact produced by a generation stage to the session workspace unless that artifact has passed the platform's constitutional compliance validation.
- **FR-005**: Compliance validation MUST be evaluated against the session's accumulated artifact set, not solely against the artifacts of the current stage, so that whole-project rules can be evaluated.
- **FR-006**: A stage MUST distinguish violations attributable to artifacts it produced from violations attributable to the accumulated set, and MUST NOT reject its own artifacts for a whole-project rule that only the accumulated set can satisfy.
- **FR-007**: When validation reports a blocking violation attributable to a stage's artifacts, the artifacts in that response MUST NOT be persisted.

**Recovery from rejection**

- **FR-008**: When validation rejects a stage's artifacts, the system MUST re-request that stage's artifacts from the model, supplying the identified violations back to it, up to a maximum of **two correction attempts per stage**. After the second correction attempt fails, the session MUST transition to the human-intervention terminal state.
- **FR-009**: The generation-stage correction budget MUST be tracked separately from the sandbox repair loop's attempt budget. The two MUST NOT share a counter, and exhausting one MUST NOT decrement or consume the other.
- **FR-010**: Exhausting the generation-stage correction budget MUST produce the same terminal session status as exhausting the sandbox repair budget, so that the existing human-intervention path and unlock console handle both uniformly.
- **FR-011**: The session state MUST record, for each generation stage, the violation set identified at each attempt and the model's response at each attempt. This correction history MUST be retained when the session terminates in the human-intervention state; it MUST NOT be discarded on exhaustion.
- **FR-012**: The correction history MUST be carried in the session's generation state so that it is available to downstream consumers, and MUST be persistable beyond the life of the process.

**Offline and degraded operation**

- **FR-013**: When no language model can be constructed for a session (no credentials, or offline mode requested), the system MUST complete the session using the established deterministic generation behavior, preserving complete end-to-end offline operation.
- **FR-014**: The system MUST treat an unusable model response — absent, truncated, non-extractable, or not mappable to the requested artifacts — as a failure of that request, never as content to persist.

**Boundedness and cost**

- **FR-015**: The system MUST enforce a documented maximum number of model requests per session — **5 initial requests + 5 stages × 2 correction attempts = 15 requests per session** — and MUST terminate the session in a human-intervention state when that budget is exhausted.
- **FR-016**: The system MUST NOT retry a stage indefinitely; every generation loop MUST be bounded and MUST surface a terminal state.

**Safety**

- **FR-017**: Generated build configuration MUST NOT be persisted if it declares a dependency outside the set pre-cached in the offline build environment, because the hermetic offline build depends on that set.
- **FR-018**: Generated artifacts MUST NOT contain model credentials, API keys, or other secrets.

**Traceability**

- **FR-019**: For every artifact a stage produces, the system MUST record the provider, the model identifier, and the instruction-set revision used to produce it.
- **FR-020**: The instruction set used by the stages MUST be versioned and stored in the repository, so that a recorded revision identifies the exact instructions that were in force.

**Compatibility**

- **FR-021**: The structural contract each stage exposes to the rest of the platform — the workspace-relative file paths it writes, the package layout, and the index of generated artifacts it contributes to session state — MUST remain stable, so that downstream verification, artifact listing, and export continue to function.
- **FR-022**: Both session execution entries (the graph-orchestrated path and the sequential auto-pilot path) MUST exhibit the migrated behavior, because the migration is applied to the generation stages themselves.
- **FR-023**: Migrating the generation stages MUST NOT change the behavior of the sandbox verification stage or the self-repair stage; the repair loop's own generation strategy is out of scope for this feature.

### Key Entities

- **Generation Stage**: One of the five synthesis steps. Each owns a set of workspace-relative artifact paths and a system instruction, consumes a task payload, and produces a candidate artifact set.
- **Instruction Set**: The versioned, repository-stored system instructions for the five stages. Carries a revision identifier that is recorded against every artifact produced under it.
- **Task Payload**: The blueprint projection handed to the model for a stage — service identity, package, entities and their attributes/types/constraints, user stories, acceptance scenarios, plus the artifacts already produced by earlier stages where the stage depends on them.
- **Candidate Artifact Set**: The in-memory map of workspace-relative path to content returned for a stage, prior to validation and persistence. Never partially persisted.
- **Compliance Verdict**: The outcome of validating a candidate artifact set — a pass/fail determination together with the identified violations, each carrying the offending artifact, the rule violated, and a severity.
- **Correction Attempt Record**: For one rejected attempt at one stage — the attempt ordinal, the violation set that caused the rejection, the request issued, and the response received. Retained in the session's correction history regardless of how the session terminates.
- **Correction History**: The ordered collection of Correction Attempt Records for a session, grouped by stage. Distinct from, and not counted against, the sandbox repair history.
- **Generation Request Budget**: The documented maximum number of model requests permitted for a single session: one initial request per generation stage, plus at most two correction requests per stage. Independent of the sandbox repair attempt budget.
- **Generation Provenance Record**: For one artifact, the provider, model identifier, instruction-set revision, stage, and timestamp that produced it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

> **Retired criterion — SC-010.** The session-duration bound is withdrawn as unmeasurable. It previously required post-migration duration within 3× the pre-migration median; that median is **1.134 ms** of in-process string assembly with no I/O and no model call, while the migrated path performs network-bound model requests, so the ratio spans roughly four orders of magnitude and carries no information about the feature. The request-budget bound is owned by **SC-005** and is not restated. Duration is retained by the frozen baseline as diagnostic context only. The identifier `SC-010` is kept in this note so that references to it in the frozen baseline artifact remain resolvable. See [research.md](research.md) D14.

- **SC-001**: For a blueprint declaring attribute-level constraints and acceptance scenarios, 100% of the generated entity and test artifacts exhibit at least one behavior traceable to the blueprint that the frozen pre-migration baseline could not produce for the same blueprint. Verified by comparing against the recorded baseline.
- **SC-002**: Two blueprints that differ in declared constraints and scenarios produce generated sources that differ in the corresponding artifacts, while two blueprints that are identical in those respects produce sources of equivalent semantic content. Verified over a corpus of paired blueprints.
- **SC-003**: Zero artifacts carrying a blocking compliance violation are written to a session workspace across a corpus of adversarial model responses covering every constitutional rule. Verified by fault injection at the model boundary.
- **SC-004**: 100% of sessions run without model credentials complete successfully and produce a service that passes a **direct workspace build** (`mvn test -o` run outside the platform's sandbox wrapper) **and the platform's own offline pytest suite**. The sandbox wrapper is deliberately not the pass criterion: it can report synthetic success without executing a build, so using it as the instrument would make this criterion unfalsifiable (plan.md Constraint 5, [research.md](research.md) D11).
- **SC-005**: No session observed over a 30-day window exceeds the generation request budget of **15 requests per session** (5 initial requests + 5 stages × 2 correction attempts = 15).
- **SC-006**: At least 99% of generated artifacts carry a complete provenance record (provider, model, instruction revision).
- **SC-007**: For a fault-injection condition in which every model response is non-compliant, 100% of sessions terminate within the budget in a human-intervention state, with zero non-compliant artifacts persisted and zero unbounded retries.
- **SC-008**: 100% of sessions that terminate in the human-intervention state retain the complete correction history for every stage that exhausted its correction budget — the violation set and model response for each of the two rejected attempts.
- **SC-009**: A generation-stage correction exhaustion never consumes or reduces the sandbox repair loop's available attempts, verified by a session that reproduces the condition and inspects both counters.
- **SC-011**: **Blocked terminal sessions divided by all terminal sessions** does not exceed **15%**, measured over at least 30 sessions. Numerator and denominator are stated explicitly so the rate is unambiguous: a session counts in the numerator only if it reaches a terminal state requiring human intervention, and in the denominator if it reaches any terminal state. Sessions that never terminate are excluded from both. This is an **absolute post-migration threshold**, deliberately not a comparison against a pre-migration baseline — the frozen baseline captures only the generation stages, so it cannot supply a session-level intervention rate (see the limitations section of [`reports/baselines/011-pre-migration-generation-baseline.md`](../../reports/baselines/011-pre-migration-generation-baseline.md)). See [research.md](research.md) D14.

## Assumptions

- **Offline fallback is retained.** The established deterministic behavior is preserved as the no-model path rather than deleted. This is required for offline operation and for the platform's hermetic-build principle; it is also why FR-013 exists.
- **The correction cap is two attempts.** This is deliberately lower than the sandbox repair cap and is a separate budget (FR-009). The rationale is that a stage reaching its third non-compliant response indicates a defective instruction or an unsuitable model for that stage, which correction attempts will not repair.
- **Correction history is unified in the generation state.** FR-012 requires the history to live in the session's generation state, with persistence to follow. Until persistence lands, the history survives for the life of the process only, matching the existing behavior of other in-memory session stores.
- **The existing constitutional validators are authoritative and reused as-is.** The platform currently contains more than one implementation of overlapping constitutional checks with differing interfaces and severities. This feature consumes the existing validators and does not consolidate them; inconsistency between them is pre-existing and is addressed by separate work.
- **User Story 3 assumes additive persistence.** Recording provenance and correction history is expected to require additional storage. The feature assumes additive, non-breaking storage changes are permitted; it does not assume the existing session schema changes meaning.
- **The self-repair loop is out of scope.** The repair stage's own strategy is unchanged, even though it also produces code. FR-023 makes this boundary explicit rather than leaving it implicit.
- **Sandbox verification is out of scope.** The existing build-and-test verification stage and its reporting are consumed unchanged. Known limitations in that stage's fallback behavior are pre-existing.
- **A hybrid rejection policy is out of scope.** A policy that selects between correction and immediate blocking per violation category (for example, bounding correction for locally checkable violations while blocking immediately on security-category violations) is deliberately deferred to a future specification. This feature implements a single uniform policy: bounded correction, then block.
- **Low-variance model settings.** Output is expected to be produced with settings chosen to minimize run-to-run variance. The feature does not require byte-level reproducibility of generated source; provenance recording is the substitute.
- **The instruction set is authored in-repository and version-controlled**, and is small enough to be reviewed in a pull request.
- **A model provider is optional at the deployment level.** Deployments without credentials remain fully functional; they simply take the offline path.
- **Blueprint payloads fit within model context limits** for the entity and scenario counts the platform is expected to handle; oversized blueprints degrade to the offline path or to a blocked session rather than to truncated artifacts.
- **Existing downstream consumers read artifacts by path and content** and do not parse them for template-specific structure; FR-021 constrains only the path and index contract.

## Dependencies

- A configured model provider with valid credentials, or the deliberate absence of one for offline operation. The platform's existing multi-provider routing and its offline mode are reused.
- The platform's existing constitutional compliance validators and the compliance report they produce.
- The platform's existing offline build environment and its pre-cached dependency set, which constrains FR-017.
- The platform's existing session orchestration, artifact listing and export surfaces, which constrain FR-021.
- The platform's existing human-intervention terminal state and unlock path, which FR-010 reuses rather than extending.
