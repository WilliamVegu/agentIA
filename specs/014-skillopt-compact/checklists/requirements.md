# Specification Quality Checklist: SkillOpt Compact

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

- **All 16 items pass.** Two clarifications were raised and resolved on 2026-09-28; both are folded into the requirements. Zero markers remain.

## Validation Detail

### Source verification (fetched, not recalled)

The source paper exists and its citation is accurate:

- **<https://arxiv.org/abs/2605.23904>** — "SkillOpt: Executive Strategy for Self-Evolving Agent Skills", v2, 25 May 2026. Fetched HTTP 200.
- **Appendix C.2 is "Optimizer Prompt Contracts"**, and its first entry, **C.2.1, is `analyst_error.md`** — the failure-analysis contract FR-004 names. The other seven (`analyst_success`, `merge_failure`, `merge_success`, `merge_final`, `ranking`, `slow_update`, `meta_skill`) belong to the machinery this feature defers.
- The abstract independently confirms the two design choices already baked into the requirements: edits are **bounded** add/delete/replace operations on **a single skill document**, and an edit is accepted **only when it strictly improves a held-out validation score**.
- It also confirms the scope boundary is principled rather than arbitrary: the deferred items (rejected-edit buffer, textual learning-rate schedule, epoch-wise slow/meta update) are exactly the mechanisms the paper names as what makes skill training *stable*.

**Recorded constraint**: the paper's contract text is **not** reproduced. FR-004 requires the prompt to be written for this platform's inputs and to record which contract it was adapted from, so nobody later mistakes a platform-specific prompt for the paper's.

### Findings recorded, no marker needed

- **The seed skill file already exists, at zero bytes.** `backend/app/resources/skills/` contains `layer_architecture.md`, `exception_handling.md` and `mockito_tests.md`, all created as empty placeholders by an earlier feature that classified the domains but never authored content. FR-001 therefore authors an existing file rather than creating one, and the spec says so.
- **Nothing reads that directory today.** The instruction loader documents the skills directory as "deliberately distinct" from its own instructions directory, and owns a different one. Injection is a new consumer, not an extension — which is why FR-002's no-op requirement matters: this is the first code to read a directory that may be empty.
- **The injection point is a single function.** The stage boundary renders each request as *instruction + payload + owned paths* in one place, so injection has exactly one natural seam and cannot be forgotten at a call site. SC-005 (byte-identical request when no skill is active) is testable against it directly.
- **The database has no run-log table.** It currently holds only the session table. A new model is created by the ORM's metadata, so FR-008 needs no migration tool — unlike 011/012/013, which added columns to an existing table.
- **Every deferral maps to a paper mechanism.** See the Out of Scope section; each omitted item is named, so the omissions read as a deliberate v1 boundary rather than an incomplete implementation.

### Deliberate scope boundary

The seed skill's *content* is explicitly a placeholder. The specification says so in FR-001 and in Assumptions, because the temptation otherwise is to treat a plausible-looking layering document as validated advice. Nothing here validates it; the loop does not care whether its seed is good, only whether it can be improved on.

## Open markers

### Marker 1 — FR-006: what is the held-out set, and where do its sessions come from?

The collector reads **existing** sessions; the gate is specified to **run** sessions. Those are different acts with very different costs.

### Marker 2 — FR-007: is the current skill scored too?

FR-006 compares a candidate against "the current score", but nothing else in the loop produces that number.

## Resolved Clarifications

### Q1 — Held-out evidence → **Option C: hybrid, with an injectable runner**

FR-006 now separates the two evidence sources **by construction**:

| | Source | Disjointness |
| --- | --- | --- |
| **Training** | Recorded sessions read from the database | Already happened, produced under the **previous** skill, so it cannot encode the candidate |
| **Held-out** | **Fresh execution** with the skill under test active | Exists only after the candidate does |

The held-out task set is the **five existing baseline blueprints** (`pair-a`, `pair-b`, `minimal`, `multi-entity`, `constrained`) — **no new fixtures**, because a task set authored alongside the thing it evaluates measures the author. **M defaults to 4**, leaving one blueprint as a rotation buffer so successive iterations are not scored on an identical exam. Rotation is deterministic (FR-006a, SC-010).

Fresh execution goes through an **injectable runner** so the unit test substitutes a scripted client and makes no real model call (SC-001, Principle VI). Disjointness is **asserted in code**, not assumed (SC-008).

**Also resolved while folding this in**: "pass" needed defining, and it interacts with feature 012. A pass is a zero build/test exit code, but an execution whose verification used the **hermetic fallback does not count as a pass even when its exit code is zero** — otherwise the gate would reward a skill for making the verifier give up, since permissive mode returns success without compiling anything. Executions that could not be scored at all are reported separately rather than folded into failures.

### Q2 — Is the current skill scored too? → **Option A: score both**

FR-007 now computes both scores in the same iteration, on the identical held-out set, with the same scoring function:

```
current_score   = score(current skill,   held_out_blueprints)
candidate_score = score(candidate skill, held_out_blueprints)
accept iff candidate_score > current_score          # strict
```

**Cost: 2×M fresh executions per iteration** (default 8), accepted deliberately. Carrying the previous run's score forward would be cheaper but compares a number measured on one sample against a number measured on another, is absent on the first iteration, and silently breaks whenever the held-out set rotates. Scoring both on the same sample needs no persisted prior state and is never stale.
