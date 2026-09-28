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

**Validation iteration 3 — 2026-09-28 (post-T010).** All 16 items still pass. Two success criteria were reformulated now that the frozen baseline exists and its limitations are known. Recorded in [research.md](../research.md) D14.

| Criterion | Before | After | Why |
|---|---|---|---|
| `SC-010` | Median end-to-end duration within 3× the pre-migration median, over ≥ 20 sessions each side | **Retired**; identifier retained as a pointer to `SC-005` | The baseline's pre-migration median is **1.134 ms** of in-process f-string assembly — no I/O, no model call. The migrated path is network-bound. The ratio spans ~4 orders of magnitude, would be trivially satisfied, and measures nothing about the feature. The request-budget bound is owned by `SC-005`; restating it as `SC-010` would put two criteria on one measurement, which a future reader would over-count as independent evidence. |
| `SC-011` | Intervention rate must not increase by more than 10 percentage points vs. the pre-migration baseline, over ≥ 30 sessions | **Absolute ceiling**: intervention rate ≤ **15%**, over ≥ 30 sessions, baseline-independent | The baseline captures only the generation stages, never the sandbox verifier or repair loop, so its intervention count is **structurally zero** and cannot supply a session-level comparison. A relative bound against a structurally-zero baseline degrades to an arbitrary "+10pp". The reformulation also removes `SC-011`'s dependency on the baseline entirely. |

Both changes are cross-referenced to the baseline artifact's limitations section — `reports/baselines/011-pre-migration-generation-baseline.md` §7 and the machine-readable `limitations` / `aggregate.human_intervention_note` fields — which is the authoritative record of why these two criteria were unmeasurable as originally written.

Two consequences were carried into the other documents rather than left implicit: the compliance-verdict severity merge now counts *directly* against an absolute ceiling with no baseline slack to absorb it (so the D13 post-hoc mitigation becomes the primary attribution tool), and the sandbox verifier's leniency now biases `SC-011` in the **permissive** direction — the opposite of the original relative bound, where leniency would have made the target harder. Meeting the 15% ceiling therefore does not by itself demonstrate generation quality.

The frozen baseline artifact was **not** modified. Its duration and intervention figures are retained as diagnostic context, and its limitations section is left intact as the historical record it was written to be.

**Deliberate justifications recorded for transparency.**

- *No implementation details* — The requirement and success-criteria sections name no language, framework, product, or API. The only such tokens appear in the verbatim `Input` field, which preserves the user's original wording as the template requires, and in the `Context` section, which describes pre-migration behaviour in behavioural terms. Integration boundaries are expressed as capabilities ("the configured language model", "the platform's constitutional compliance validation", "the offline build environment") rather than as named components. This is a deliberate departure from sibling specs in this repository — for example `specs/010-skill-injection/spec.md`, whose requirements name exact artifact paths and file names; that spec was an authoring task over named files, whereas this one is a behaviour change.
- *Written for non-technical stakeholders* — User stories, edge cases, and success criteria are user- and operator-framed. FR-019 and FR-020 are necessarily platform-internal, since the feature concerns platform internals; they state obligations, not designs.

**Baseline dependency — resolved.** Two success criteria are relative to a pre-migration baseline (SC-001, SC-002). That baseline was captured and frozen at `reports/baselines/011-pre-migration-generation-baseline.{json,md}` (task T010), which retains full artifact content for the designated comparison subset so SC-001's behavior-level traceability is verifiable.

**Two criteria were reformulated once the baseline existed** (see [research.md](../research.md) D14). SC-010's duration bound was retired as unmeasurable: the baseline's pre-migration median is 1.134 ms of in-process string assembly with no I/O, which is not comparable to network-bound generation, so the ratio measured nothing; the request budget is owned by SC-005. SC-011 was reframed from a +10pp relative bound to an absolute post-migration ceiling of 15% over at least 30 sessions, because the baseline records no session-level interventions — its count is structurally zero and cannot supply the comparison.

**Scope boundaries asserted.** FR-023 excludes the self-repair stage; the Assumptions section excludes sandbox verification, validator consolidation, and the hybrid rejection policy. These are recorded explicitly because the reconnaissance report `reports/agentia-state-map.md` documents that the repair stage also produces code, that two overlapping validator implementations exist, and that the legacy deterministic output must be retained for offline operation — all of which could otherwise be absorbed into this feature by accident.

**Known implementation risk carried forward, not resolved here.** The reconnaissance report records that the self-repair stage contains no model call and that the sandbox verifier returns a synthetic success result when the container environment is unavailable. FR-013 and FR-023 preserve both behaviours deliberately. Consequence for this feature: SC-011 measures a pipeline whose terminal verification may be simulated, and because SC-011 is now an absolute ceiling a lenient verifier makes it *easier* to pass — so meeting SC-011 does not by itself demonstrate generation quality. SC-003's fault injection must therefore be performed at the model boundary rather than by observing end-to-end session outcomes. Planning should treat the verifier's fidelity as a dependency risk, not as something this spec fixes.
