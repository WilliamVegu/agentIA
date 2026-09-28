# Specification Quality Checklist: LLM-Driven Generation Stages

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

**Validation iteration 1 — 2026-09-28.** One item failed: *"No [NEEDS CLARIFICATION] markers remain"*. A single marker was open at `FR-008` — the recovery behaviour required when compliance validation rejects a stage's artifacts. The three viable policies (bounded correction, immediate block, deterministic fallback) differ substantially in scope and in their effect on SC-001 and SC-009, so no reasonable default could be assumed. Presented to the user as Q1.

**Validation iteration 2 — 2026-09-28.** All 16 items pass. The marker was resolved by user decision — **bounded correction attempts, then block** — with four explicit constraints, all now encoded:

| User constraint | Encoded as |
|---|---|
| Separate correction counter from the sandbox repair counter; do not share the cap | `FR-009`, and verified by `SC-009` |
| Cap generation-stage corrections at 2 attempts | `FR-008`, `Assumptions` (rationale for the lower cap), `FR-015` (budget arithmetic) |
| On exhaustion, transition to BLOCKED — the same terminal state as the sandbox repair loop's exhaustion | `FR-010`, plus the `Dependencies` entry reusing the existing unlock path |
| Record the violation set, each correction attempt, and the model's response into session state; retain on exhaustion | `FR-011`, `FR-012`, `SC-008`, and the `Correction Attempt Record` / `Correction History` entities |
| Do not implement the hybrid policy in this spec | `Assumptions` — "A hybrid rejection policy is out of scope" |

Two edge cases were added as a direct consequence of the decision, because they are the failure modes the new budget introduces: *correction attempts oscillate*, and *correction budget is exhausted while sandbox repair budget remains*.

**Deliberate justifications recorded for transparency.**

- *No implementation details* — The requirement and success-criteria sections name no language, framework, product, or API. The only such tokens appear in the verbatim `Input` field, which preserves the user's original wording as the template requires, and in the `Context` section, which describes pre-migration behaviour in behavioural terms. Integration boundaries are expressed as capabilities ("the configured language model", "the platform's constitutional compliance validation", "the offline build environment") rather than as named components. This is a deliberate departure from sibling specs in this repository — for example `specs/010-skill-injection/spec.md`, whose requirements name exact artifact paths and file names; that spec was an authoring task over named files, whereas this one is a behaviour change.
- *Written for non-technical stakeholders* — User stories, edge cases, and success criteria are user- and operator-framed. FR-019 and FR-020 are necessarily platform-internal, since the feature concerns platform internals; they state obligations, not designs.

**Baseline expectations to establish during planning.** Three success criteria are stated relative to a "pre-migration baseline" (SC-001, SC-010, SC-011). That baseline does not yet exist as recorded data. Planning must include capturing it — generated output for a fixed set of blueprints, plus session duration and intervention-rate figures — before the migration lands, or these criteria cannot be evaluated.

**Scope boundaries asserted.** FR-023 excludes the self-repair stage; the Assumptions section excludes sandbox verification, validator consolidation, and the hybrid rejection policy. These are recorded explicitly because the reconnaissance report `reports/agentia-state-map.md` documents that the repair stage also produces code, that two overlapping validator implementations exist, and that the legacy deterministic output must be retained for offline operation — all of which could otherwise be absorbed into this feature by accident.

**Known implementation risk carried forward, not resolved here.** The reconnaissance report records that the self-repair stage contains no model call and that the sandbox verifier returns a synthetic success result when the container environment is unavailable. FR-013 and FR-023 preserve both behaviours deliberately. Consequence for this feature: SC-010 and SC-011 measure a pipeline whose terminal verification may be simulated, and SC-003's fault injection must therefore be performed at the model boundary rather than by observing end-to-end session outcomes. Planning should treat the verifier's fidelity as a dependency risk, not as something this spec fixes.
