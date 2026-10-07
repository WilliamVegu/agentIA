# Contract — Edits

**Feature**: 014-skillopt-compact · **Implements**: FR-004, FR-005

Defines the reflector's output shape and the applier's acceptance rules.

---

## 1. Operations

| `op` | `target` | `content` | Effect |
| --- | --- | --- | --- |
| `append` | ignored | required | Insert at the end of the editable region |
| `insert_after` | required, must exist | required | Insert immediately after the first exact match |
| `replace` | required, must exist | required | Replace the first exact match |
| `delete` | required, must exist | forbidden | Remove the first exact match |

## 2. Rejection rules

Each rule rejects the **individual edit**. A rejected edit MUST NOT abort the batch — one malformed proposal from a model should not discard the others, and the rejection reason is the only signal an operator gets about why an iteration underperformed.

| Rejection | Reason |
| --- | --- |
| **Target in the protected region** | The region is reserved for slow consolidation. A fast local edit overwriting it would collapse the distinction the region exists to preserve. |
| **Target text not found** | Applying a fuzzy match would make the candidate differ from the proposed edit set, so the logged edits would no longer describe what was tested. A rejected edit is honest; a relocated one is not. |
| Unknown operation, or a missing required field | Malformed proposal. |
| `content` supplied for `delete` | Ambiguous intent; rejected rather than guessed. |

## 3. Budget

At most **L_t = 4** edits. The cap is the textual analogue of a learning rate and is what keeps a candidate comparable to its predecessor: an unbounded rewrite can erase useful rules and cannot be attributed to any particular change.

If **every** edit is rejected, the candidate is byte-identical to the current skill. The gate then rejects on a tie — which the strict comparison gives for free — and the iteration MUST report that outcome rather than a spurious acceptance.

## 4. Application target

Edits are applied to a **copy**. The original skill file MUST NOT be modified by application.

This is what makes rejection meaningful: editing in place would mean the skill had already changed before the gate rejected it, and the "rejection" would be false. The original changes only when a candidate is **accepted**, and then by exactly the applied edit set (SC-004).

## 5. The reflector prompt

One model call, via a **direct call to the model factory** in the same request-construction path as the generation stages: no wrapper, no conditional, no shared helper.

The prompt lives in a file at `backend/scripts/skillopt/prompts/analyst_error.md` and:

- MUST record that it is **adapted from Appendix C.2.1 (`analyst_error.md`) of [arXiv:2605.23904](https://arxiv.org/abs/2605.23904)**.
- MUST NOT reproduce the paper's prompt text verbatim.
- MUST reference **this platform's** signals: build exit codes, terminal statuses, artifact paths, and the verification-fallback marking.
- MUST instruct the model to emit the structured edit list and nothing else, and the caller MUST treat an unparseable response as a failure of the iteration rather than applying a partially parsed result (FR-004 acceptance scenario 4).
