# Specification Quality Checklist: Diagnostic-Driven Skill Evolution

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

**All items pass.** Two observations recorded rather than silently resolved.

**FR-017 (bounded skill count)** is a constraint rather than a user-facing
behaviour, so it has no acceptance scenario of its own; it is verified directly
against the documented limit during implementation. Every other functional
requirement maps to at least one acceptance scenario or success criterion:
FR-001–FR-005 and FR-018 to User Story 1 and SC-001–SC-003/SC-006/SC-011,
FR-006–FR-009 and FR-019 to User Story 2 and SC-004/SC-005/SC-012,
FR-010–FR-013 and FR-015/FR-016 to User Story 3 and SC-007–SC-009, and FR-014 to
SC-010.

**FR-018 and FR-019 were added after the first review pass**, both prompted by an
operator question about measuring per request rather than per session:

- **FR-018 (per-stage attribution)** — the platform already computes a
  conformance verdict per generation stage and stores it on the stage entry. It
  was never persisted or surfaced, so the origin of a violation was lost when the
  session ended. Recording it costs almost nothing and converts a session total
  into an attributable profile: which stage introduced the defect. Note this does
  **not** increase the evidence size — re-checking the same tasks repeatedly is
  still the same number of distinct tasks (FR-009).
- **FR-019 (comparability across sizes)** — the conformance measure was a raw
  weighted count, so a larger service would score worse for being larger, and a
  round pointed at it could improve the measure merely by generating less code.
  That is a low-distinguishability verifier failure mode, and normalisation is
  the guard against it.

**On the oracle's own limits**, now recorded in the spec's Assumptions: it is a
fixed, hand-written rule set, so a defect class nobody encoded scores clean; it
measures conformance rather than correctness, so a well-layered but broken
service scores full marks; and its use as an optimisation objective has no
precedent in the reviewed literature, which gates on test execution or a language
model's judgement instead. Its behaviour as an objective is to be measured.

**The conformance-target decision is documented as a flagged assumption, not a
clarification marker.** The scope of this feature turns on one question — whether
the loop optimizes *conformance* or *build success* — and the two lead to
different features. It was resolved from evidence rather than escalated, because
the evidence is one-sided: build success is a binary whole-corpus outcome, and at
the available task count the smallest detectable effect is far larger than any
improvement a skill edit could plausibly produce, so a loop gated on it cannot
demonstrate anything. Feature 014's own planning already conceded this. The
assumption is marked in the spec with an instruction to confirm it before
planning, so it is easy to overturn.

**Deliberately excluded from scope**: authoring new task fixtures, training any
model, changing what conformance means, and any UI surface for the records. Each
is a separate feature; this one is the evidence layer plus the loop that consumes
it.
