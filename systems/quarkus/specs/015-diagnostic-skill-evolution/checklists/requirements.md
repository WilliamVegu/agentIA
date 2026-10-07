# Specification Quality Checklist: Session Diagnostics and Corpus Baseline

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-29
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

**All items pass.** The specification was rescoped after review, and the
rescoping is the most important thing recorded here.

**What changed and why.** The original feature bundled an instrument with an
optimizer. Review separated them for three evidence-based reasons, all recorded in
the spec's opening section: the optimizer has no baseline to improve on because no
session has ever been measured; the conformance signal is narrower than assumed
because stage-local violations are blocked before persistence; and the optimizer
targets a lever the evidence ranks near the bottom while a cheaper, better-evidenced
option is untouched.

A fourth reason was found by measurement rather than argument. An artifact set
that the compliance gate **accepts** was shown to score **85 rather than 100** only
when a whole-project rule is violated — evidence that the graded objective has
some dynamic range, but from the whole-project rules alone. Whether real sessions
vary at all on it is unmeasured, and the spec now makes measuring that the
precondition for building the optimizer rather than an assumption behind it.

**FR coverage.** FR-001–FR-005 and FR-014 to User Story 1 and SC-001–SC-004;
FR-006 and FR-007 to SC-002 and SC-009; FR-008–FR-013 and FR-015 to User Story 2
and SC-005–SC-008.

**Deliberately excluded from scope**: per-skill contribution measurement, loop
retargeting, skill removal, and the round record. All are specified in the plan,
data model and contracts and are marked deferred in the spec, so the work is not
lost — it is queued behind data. Also excluded: authoring new task fixtures,
training any model, and any UI surface for the records.
