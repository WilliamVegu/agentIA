# Phase 1 Data Model — SkillOpt Compact

Four shapes: the skill document being optimised, the edits proposed against it, the evidence on each side of the gate, and the run record. Nothing existing is removed or retyped.

---

## 1. Skill Document

A markdown file at `backend/app/resources/skills/<name>.md`. The unit being optimised.

| Section | Required | Editable | Notes |
| --- | --- | --- | --- |
| `# Title` | yes | yes | One H1, the skill's name. |
| `## Granularity` | yes | yes | `task-level` or `event-driven`. |
| `## When to apply` | yes | yes | The applicability condition. |
| `## Rules` | yes | yes | Numbered rules. Append / insert-after / replace / delete all target here in practice. |
| `<!-- SLOW_UPDATE_START -->` … `<!-- SLOW_UPDATE_END -->` | yes | **NO** | The protected region. |

**Validation**

- The protected markers MUST both be present, and `START` MUST precede `END`. A document missing either marker is **not a valid skill** and MUST be rejected at load rather than treated as having an empty protected region — otherwise a typo would silently unprotect the region, and the applier would happily edit it.
- Content between the markers is **never** editable by this feature. Nothing writes there in v1 (that is the deferred slow/meta update); it is honoured so that adding one later does not require changing the edit contract.
- The document MUST be non-empty. An empty file is a load error, not a skill with no rules ([research.md](research.md) D7).

**The active pointer** is a separate file, `active.md`, whose *content* names the skill in use. Its **absence is a no-op**, not an error. An unreadable or empty pointer is likewise a no-op.

**Recorded state**: `layer_architecture.md` already exists as a **0-byte placeholder** created by an earlier feature. FR-001 authors its content; it does not create the file. Its content is explicitly a placeholder for the loop's benefit ([spec.md](spec.md) Assumptions).

---

## 2. Proposed Edit

Produced by the reflector, consumed by the applier.

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `op` | enum | yes | `append` \| `insert_after` \| `replace` \| `delete` |
| `target` | text | conditional | Required for `insert_after`, `replace`, `delete`. **Text that must exist in the document.** |
| `content` | text | conditional | Required for `append`, `insert_after`, `replace`. Forbidden for `delete`. |

**Per-operation validation**

| `op` | `target` | `content` | Effect |
| --- | --- | --- | --- |
| `append` | ignored | required | Insert at the end of the editable region. |
| `insert_after` | required, must be found | required | Insert immediately after the first exact match. |
| `replace` | required, must be found | required | Replace the first exact match. |
| `delete` | required, must be found | forbidden | Remove the first exact match. |
| anything else | — | — | Rejected as an unknown operation. |

**Rejection rules** (each rejects the **individual edit**; the batch continues):

| Rule | Reason |
| --- | --- |
| Target lies in the protected region | The region is reserved for slow consolidation; a fast local edit must not overwrite it. |
| Target text not found in the document | The document may have changed, or the model paraphrased. Applying a fuzzy match would make the candidate differ from the proposed edit set, so the logged edits would no longer describe what was tested. |
| Unknown operation, or a missing required field | Malformed proposal. |
| `content` supplied for `delete` | Ambiguous intent; rejected rather than guessed. |

**Budget**: the reflector returns at most **L_t = 4** edits. The applier applies at most that many. If every edit is rejected, the candidate is byte-identical to the current skill — and the gate must then reject on a tie, which the strict comparison gives for free.

**Apply target**: a **copy**. The original skill file MUST NOT be modified by application. This is what makes a rejection meaningful: editing in place would mean the skill had already changed before it was rejected.

---

## 3. Collected Session Outcome

One per recorded session, produced by the collector. The **training** evidence.

| Field | Type | Notes |
| --- | --- | --- |
| `spec_id` | text | Identifies the specification the session generated from |
| `artifact_paths` | list[text] | What the session produced |
| `build_exit_code` | int \| null | `null` when no build ran |
| `terminal_status` | text | `COMPLETED` \| `BLOCKED` \| … |
| `verification_fallback_used` | bool | Feature 012's marking |

**Selection**: the most recent **N** sessions (default 12), ordered deterministically by session identifier so a re-run collects the same set.

**Failure classification** (what the reflector receives): a session is a **failure** when it did not reach the completed state, or its build exit code was non-zero, or its verification was fallback-marked. That last clause matters: a session whose verification was synthetic did not succeed, however its status reads ([research.md](research.md) D5).

**Validation**

- **No failures collected is a distinct condition from no sessions collected**, and the two MUST be reported differently. The first means the skill is working; the second means there is nothing to learn from. Both stop the iteration before a model is called.
- Recorded outcomes are **never** used as gate evidence. They were produced under a different skill and cannot be attributed to a candidate ([research.md](research.md) D2).

---

## 4. Gate Evidence

Two sets, per iteration, both derived from **fresh execution**.

| Set | Skill under test | Purpose |
| --- | --- | --- |
| Held-out executions | the **current** skill | `current_score` |
| Held-out executions | the **candidate** skill | `candidate_score` |

Both sets use the **identical** held-out blueprint selection within an iteration, and the same scoring function. **2×M fresh executions per iteration** (default M=4, so 8).

**The held-out blueprint set** is the five existing baseline blueprints — `pair-a`, `pair-b`, `minimal`, `multi-entity`, `constrained`. **No new fixtures.** M=4 of the 5 are selected per iteration; the remaining one is the rotation buffer. Rotation is **deterministic from the iteration's identity**, not from the clock or process randomness, so a re-run reproduces the selection.

**A pass** is an execution whose **offline build/test exit code is zero**. An execution whose verification used the **hermetic fallback is not a pass, even at exit code zero**: permissive mode returns success without compiling, so scoring on the exit code alone would reward a skill for making the verifier give up ([research.md](research.md) D5).

**An unscorable execution** — no build ran, no workspace materialised — is counted and reported **separately** from failures, so an infrastructure problem cannot masquerade as a skill regression.

**The score** is the pass rate over the M executions.

**The disjointness assertion**: the gate MUST assert that no session identifier in the held-out executions appears in the collected training outcomes, and MUST fail loudly rather than score if it does. The two sets are disjoint for a structural reason — recorded sessions predate the candidate — and the assertion is what keeps that reason true as the code changes.

---

## 5. SkillOpt Run

One row per iteration, in a new `skillopt_runs` table.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | pk | |
| `started_at` | timestamp | |
| `completed_at` | timestamp \| null | Null while running, and on a hard crash |
| `n_training` | int | Sessions collected |
| `n_held_out` | int | Blueprints selected (M) |
| `current_score` | real \| null | Scored this iteration, on this iteration's held-out set |
| `candidate_score` | real \| null | Same set, same scoring function |
| `decision` | text | `ACCEPTED` \| `REJECTED` \| `NO_FAILURES` \| `NO_SESSIONS` \| `ERROR` |
| `edits_json` | text | The proposed edits, whether or not they were applied |
| `error` | text \| null | Populated when the iteration failed |

**Validation**

- **Exactly one row per iteration, on every exit path, including failure.** A crashed iteration that left no row is indistinguishable from one that never ran (SC-006).
- `decision = ACCEPTED` implies `candidate_score > current_score`, strictly, with both non-null.
- `current_score` and `candidate_score` are both non-null together or both null: they are produced by the same gate run on the same sample.
- `edits_json` is recorded even when the decision is `REJECTED` — a rejected proposal is the only evidence of what the reflector tried, and v1 has no other memory of it.

**Table creation**: a new ORM model, so the table comes from `Base.metadata.create_all`. Unlike 011/012/013, which added columns to the existing table through an idempotent `ALTER TABLE` shim, no migration shim is needed ([research.md](research.md) D9).

---

## Entity relationships

```text
Skill Document ──(copy)──▶ Candidate Skill
      │                          │
      │ edited by                │ scored by
      ▼                          ▼
 Proposed Edit            Held-out Execution ──┬── current_score
      ▲                          │             └── candidate_score
      │ derived from             │
      │                          │  MUST be disjoint from
 Collected Session Outcome ◀────┘
   (training, recorded)              SkillOpt Run (one row, every exit path)
```

**No entity is removed and no cardinality changes.** The skill is read and copied; the edits transform the copy; the outcomes are read; the gate executes fresh sessions on both skills; the run record is written unconditionally.
