# Specification Quality Checklist: Sandbox Verifier Honesty

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

- **All 16 items pass.** Two clarifications were raised and resolved on 2026-09-28; both are folded into the requirements below. Zero markers remain.

## Resolved Clarifications

### Q1 — Does permissive mode relax the verified-state guard? → **Yes (Option A)**

FR-002 now states that enabling the switch relaxes FR-003, so a fallback-marked result may reach the verified terminal state. FR-007 was strengthened: the marking is recorded in **both** modes.

**Consequence folded in as FR-008**: because a session can now be verified without verification having occurred, the terminal state alone no longer proves verification was real. Measurement, reporting, and comparison consumers MUST exclude fallback-marked results from any compliance, quality, intervention-rate, or cost figure. This is what keeps feature 011's SC-001/SC-010/SC-011 figures sound. Captured as **SC-006** and recorded in Assumptions as an accepted, explicit cost.

### Q2 — How is an environment-looking build failure with a project-authoring cause classified? → **Record the ambiguity (Option C)**

The existing pattern set is retained, not narrowed. FR-009 requires the matched pattern and the fact that attribution is ambiguous to be recorded on the result. Captured as **SC-007**.

Rationale recorded in Assumptions: narrowing the pattern set was rejected because misclassifying a real environment problem as a project error yields a false *failure*, which is worse than a false "could not verify". The ambiguity is recorded so it stays recoverable, and resolving it remains a human judgement.

## Validation Detail

### Resolved during specification (no clarification needed)

| Question | Resolution | Basis |
| --- | --- | --- |
| Is there a distinct unverifiable session state to use? | No. The status set is `QUEUED, RUNNING, PAUSED, COMPLETED, BLOCKED, CANCELLED`; the blocked state is reused. | FR-003 explicitly permits this ("or a distinct UNVERIFIABLE state **if SessionStatus supports it**"). It does not, so the permitted fallback applies. |
| How are a missing build image and an insufficient cache detected — probe or infer? | Inferred from the build attempt's own output, not from a new runtime/network probe. | A probe would reintroduce network dependence into a step designed to run offline. Recorded as an assumption. |
| Does permissive mode suppress the fallback marking? | No — recorded in both modes. | Prevents "permissive" from silently becoming an audit blind spot; now FR-007. |
| How many substitution paths must honor the new policy? | Four, not the three named in the input. | Inspection found four call sites: runtime unavailable, runtime executable missing, a runtime communication failure, and environment-looking build errors. Captured as FR-006 so no silent-success path survives. |

### Deliberate scope boundary recorded, not a marker

The input's success criteria note that the third ("container runtime present with warmed cache") is testable on this host. **It is not, as the host is currently configured**: the container CLI shim is present but its runtime refuses to initialise (a read-only runtime directory), and the platform's reachability check therefore reports the daemon unavailable. This is recorded in Assumptions rather than as a clarification, because it is an environment fact rather than a design choice — but **SC-003 must not be claimed on that host**.

### Also recorded for a separate change

The verification step attaches a fixed synthetic test count (5 of 5) to a successful result. This specification stops the synthetic *outcome*; those counts, and the verifier's correctness when a runtime is genuinely available, remain out of scope and are noted so they are not lost.
