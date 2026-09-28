# Feature Specification: Sandbox Verifier Honesty

**Feature Branch**: `012-sandbox-verifier-honesty`

**Created**: 2026-09-28

**Status**: Draft

**Input**: User description: "backend/app/sandbox/docker_runner.py returns exit_code=0 with hardcoded 'BUILD SUCCESS' when Docker is unreachable, or the maven image is missing, or the .m2 cache is cold. Sessions therefore report VERIFIED for workspaces that were never compiled or tested. Every downstream measurement (SC-001, SC-010, SC-011, cost-per-completion) depends on an honest verifier, and currently cannot be trusted."

## Context

The platform's verification step is trusted by everything downstream. When it cannot actually run a build, it does not say so — it reports a **successful** build with fabricated test counts. A workspace that was never compiled is therefore indistinguishable from one that compiled and passed.

This has two consequences:

1. **False confidence.** A session reaches the verified terminal state on the strength of a build that never happened.
2. **Unusable measurement.** Intervention rate, first-pass compliance, and cost-per-completion (feature 011's SC-011, SC-001, and SC-010) are computed over sessions whose verification outcome is unknown. Any figure derived from them is unsound until this is fixed.

The fix is to make "we could not verify this" a first-class, honestly-reported outcome — distinct from both "verified and passed" and "verified and failed".

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An unverified workspace is never reported as verified (Priority: P1)

A platform operator runs a session to completion on a machine where the container runtime is not available. The verification step cannot run. Today the session reports verified with fabricated passing test counts. After this change, the session reports that verification could not be performed, does not claim the verified terminal state, and records why.

**Why this priority**: This is the entire point of the feature. Until it holds, every session outcome and every downstream metric is untrustworthy. It is also the smallest independently valuable slice: enforcing it alone converts the platform from silently-lying to honestly-failing.

**Independent Test**: On a host with no reachable container runtime, run a session to the verification step with the permissive switch absent. Assert the verification result reports a non-success outcome, that it is marked as having used a fallback, and that the session does not reach the verified terminal state.

**Acceptance Scenarios**:

1. **Given** no reachable container runtime and default configuration, **When** a session reaches the verification step, **Then** the verification result reports a non-success outcome and is marked as fallback-used, and the session does not reach the verified terminal state.
2. **Given** the same conditions, **When** the session terminates, **Then** the recorded failure reason identifies that verification could not be performed, rather than reporting a test or compilation failure.
3. **Given** a container runtime that is reachable but whose required build environment is unavailable (missing build image, or an insufficient local dependency cache), **When** verification runs, **Then** the outcome is the same as scenario 1 — a non-success fallback result — and never a synthetic success.
4. **Given** a build that genuinely fails for a project-authoring reason, **When** verification runs, **Then** the outcome is reported as a failure to verify rather than as a success, and the distinction between "could not verify" and "verified and failed" is preserved in the result.

---

### User Story 2 - Local development can opt into permissive verification (Priority: P2)

A developer working offline wants to exercise the full pipeline without a container runtime. They enable an explicit opt-in switch. Verification then behaves as it did before this change, so the pipeline can proceed — and the fact that no real verification occurred is still recorded.

**Why this priority**: Without an escape hatch, the honest default makes the platform unusable for offline development and for any environment that cannot run containers. It ranks below P1 because the safe behavior must exist before the unsafe one is re-enabled, and because the switch is meaningless until the honest default does.

**Independent Test**: On a host with no reachable container runtime, run the same session as User Story 1 with the opt-in switch enabled. Assert the outcome matches the pre-change behavior and that the fallback marking is nevertheless present.

**Acceptance Scenarios**:

1. **Given** no reachable container runtime and the opt-in switch enabled, **When** a session reaches the verification step, **Then** the outcome matches the pre-change synthetic behavior and the pipeline can proceed.
2. **Given** the same conditions, **When** the verification result is inspected, **Then** it is still marked as fallback-used, so permissive mode changes what is permitted, not what is recorded.
3. **Given** the opt-in switch is absent or disabled, **When** verification runs, **Then** User Story 1's honest behavior applies — the switch is opt-in only and is never inferred from the environment.

---

### User Story 3 - Verification source is visible to every consumer (Priority: P3)

An operator investigating a suspicious session needs to know whether its verification was real. They inspect the session's metrics, its live progress stream, and its detail view, and find the fallback marking in all three.

**Why this priority**: The honest outcome is only actionable if it is observable. It ranks below P2 because the correctness of the outcome matters more than its presentation, and it depends on both earlier stories to have something truthful to show.

**Independent Test**: Complete a session under fallback conditions and confirm the fallback marking appears in the verification metrics payload, in the live progress stream, and in the session detail view.

**Acceptance Scenarios**:

1. **Given** a session whose verification used a fallback, **When** its verification metrics are read, **Then** the fallback marking is present.
2. **Given** the same session, **When** its live progress stream and its detail view are read, **Then** both expose the fallback marking.

---

### Edge Cases

- **A build failure misclassified as an environment problem.** The fallback triggers on output patterns that also occur for genuine project-authoring errors: a malformed build file produces an environment-looking error, and today that is reported as a synthetic success. After this change it is reported honestly as "could not verify" (FR-001) — but the operator would still be sent to inspect the container runtime when the real problem is their build file. FR-009 therefore requires the matched pattern and the ambiguity to be recorded, so the two cases can be told apart after the fact. Deciding which case it actually was remains a human judgement, deliberately.
- **Partial environment degradation.** The runtime is reachable at the start of the step but the build image is absent, or the dependency cache is insufficient. Any of these must produce a fallback result, not a success.
- **The opt-in switch set to an unexpected value.** Only an explicit affirmative value enables permissive mode; anything unrecognized is treated as disabled, so a typo fails safe.
- **The runtime becomes unavailable mid-execution.** The result must still be a fallback result, never a success.
- **The offline generation path.** A session that never contacts a model provider and uses the deterministic generation path must be entirely unaffected: the switch governs whether a build may be substituted, not which generation mode is in use.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When verification cannot be performed — because the container runtime is unavailable, the required build image is missing, or the local dependency cache is insufficient — the verification result MUST report a non-success outcome and MUST set a fallback-used marking. The result MUST distinguish "could not verify" from "verified and failed".
- **FR-002**: An opt-in configuration switch, defaulting to disabled, MUST preserve the pre-change synthetic-success behavior for local development. When enabled, permissive mode MUST also relax FR-003, so a fallback-marked verification result may reach the verified terminal state. The default MUST be honest failure.
- **FR-003**: A session MUST NOT reach the verified terminal state when its verification result is marked fallback-used, **unless permissive mode (FR-002) is enabled**. Otherwise the existing blocked terminal state MUST be used, and the reason MUST be recorded on the session.
  - *Resolved during specification*: the platform's session status set is `QUEUED, RUNNING, PAUSED, COMPLETED, BLOCKED, CANCELLED`. There is no distinct unverifiable state, so the blocked state is used, as the requirement permits.
- **FR-004**: The existing offline generation path (deterministic mode, no provider credentials) MUST continue to behave exactly as before. The fallback policy governs whether a build may be substituted, not which generation mode is in use.
- **FR-005**: The verification metrics MUST carry the fallback marking so that callers can branch on it. The live progress stream and the session detail view MUST both expose it.
- **FR-006**: Every substitution path MUST be governed by the same policy. The existing implementation substitutes a synthetic success in four distinct situations (runtime unavailable, runtime executable missing, a runtime communication failure, and environment-looking build errors). All four MUST honor FR-001 through FR-003; none may remain a silent success.
- **FR-007**: The fallback marking MUST be recorded in **both** modes. Permissive mode changes what is permitted, not what is recorded, so a session verified under permissive mode remains identifiable as never having been verified.
- **FR-008**: Measurement, reporting, and comparison consumers MUST exclude fallback-marked verification results from any compliance, quality, intervention-rate, or cost figure. A figure computed over sessions whose verification used a fallback MUST NOT be presented as though verification occurred. Because FR-002 permits such sessions to reach the verified state, this filter — not the terminal state — is what keeps those figures sound.
- **FR-009**: When a substitution occurs because a build failed with environment-looking output, the result MUST record the pattern that matched and MUST record that the attribution is **ambiguous** — the cause may be an environment problem or a genuine project-authoring error. The existing set of recognised patterns MUST be retained rather than narrowed; the ambiguity is recorded, not resolved by guesswork.

### Key Entities

- **Verification Result**: The outcome of attempting to build and test a generated workspace. Carries a success/failure outcome, captured output, a duration, and the fallback marking that distinguishes "could not verify" from a real failure.
- **Verification Metrics**: The summarised test outcome attached to a session. Must carry the fallback marking so downstream consumers can branch on it.
- **Session Status**: The session's terminal state. The verified state must be unreachable while the fallback marking is set; the blocked state carries the reason.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With no reachable container runtime and default configuration, 100% of verification attempts report a non-success outcome marked fallback-used, and 0% of those sessions reach the verified terminal state.
- **SC-002**: With no reachable container runtime and the opt-in switch enabled, verification outcomes are identical to the pre-change behavior, and 100% of those results still carry the fallback marking.
- **SC-003**: With a reachable container runtime and a warmed local dependency cache, verification executes the real build-and-test path, reports the fallback marking as unset, and substitutes no synthetic result.
- **SC-004**: The offline generation path shows zero behavioral change: the pre-existing test suite passes unmodified, and no offline session's terminal state or metrics differ from before.
- **SC-005**: 100% of verification results expose the fallback marking to all three consumers — the metrics payload, the live progress stream, and the session detail view.
- **SC-006**: 0% of fallback-marked verification results are included in any published compliance, quality, intervention-rate, or cost figure. A result marked fallback-used is excluded whether or not its session reached the verified terminal state.
- **SC-007**: 100% of substitutions caused by an environment-looking build failure record both the matched pattern and the fact that the attribution is ambiguous.

## Assumptions

- **The blocked terminal state is the right outcome for an unverifiable session.** It already means "human intervention required", which is accurate: a human must supply a working container runtime or explicitly enable permissive mode. No new session state is introduced.
- **Fallback detection is derived from observed failure, not from a new probe.** Determining whether a build image exists or a dependency cache is warm could be done by probing the runtime, but that reintroduces network and runtime dependence into a step designed to run offline. The existing detection — the build attempt's own output — is reused and extended instead.
- **Permissive mode is an explicit operator action.** It is never auto-detected from the environment (for example, from a development mode flag or a missing credential). A failure to set it fails safe.
- **Permissive mode permits a session to be verified without verification having occurred.** This is accepted deliberately so local development can run end to end. The cost is that a session's terminal state alone no longer proves its verification was real, so the fallback marking becomes load-bearing for every downstream figure (FR-008). Any consumer that ignores the marking will silently over-count verified sessions.
- **Ambiguous attribution is recorded rather than resolved.** A build failure matching an environment pattern is classified as "could not verify", which is safe in the sense that it never reports a false success, but it can attribute a project-authoring error to the environment. Narrowing the pattern set was considered and rejected: misclassifying a real environment problem as a project error would produce a false failure, which is a worse outcome than a false "could not verify". The matched pattern is recorded so the distinction remains recoverable.
- **"Container runtime unavailable" is defined by the platform's existing daemon reachability check.** This specification does not change how reachability is determined.
- **Docker reachability on the development host is not guaranteed.** The host used for development currently has a container CLI shim present but non-functional: the runtime refuses to initialise, and the platform's reachability check reports the daemon as unavailable. SC-001, SC-002, SC-004, and SC-005 are testable under that condition; **SC-003 requires a host where the runtime actually starts.** SC-003 must be verified on such a host, or deferred and explicitly recorded as unverified — it must not be claimed on the basis of a shim that fails.
- **The dependency cache is being warmed** (approximately 178 MB and 372 artifacts at the time of writing). This is a precondition for SC-003, not for SC-001/SC-002.
- **Out of scope, recorded for a separate change**: the synthetic test counts (a fixed 5 of 5) that the verification step attaches to a successful result. This specification stops the synthetic *outcome*; it does not correct those counts, and it does not address the verifier's correctness when a container runtime is genuinely available.

## Dependencies

- The platform's existing session status set and terminal-state handling, including the human-intervention path that already consumes the blocked state.
- The existing verification metrics structure and the consumers that read it (session detail, live progress stream, measurement harness).
- The platform's existing daemon reachability check.

## Out of Scope

- Repair-loop behavior (separate specification).
- Container health checks at process start.
- Multi-tenant container isolation.
- The hardcoded synthetic test counts attached to a successful result (separate change; noted here so it is not lost).
- The verifier's own correctness when a container runtime is genuinely available.
