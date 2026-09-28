# Contract — Verification Result

**Feature**: 012-sandbox-verifier-honesty · **Implements**: FR-001, FR-006, FR-009

This contract defines what a verification attempt must report. It is a behavioural contract, not an API schema — the result is an internal value object consumed by `sandbox_node`, the metrics model, and the measurement harness.

---

## 1. The three outcomes

Every verification attempt MUST terminate in exactly one of three outcomes, and consumers MUST be able to tell them apart without reading logs.

| Outcome | `exit_code` | `fallback_used` | Meaning |
| --- | --- | --- | --- |
| **Verified and passed** | `0` | `False` | A real build ran and succeeded. |
| **Verified and failed** | non-zero | `False` | A real build ran and failed. Repairable. |
| **Could not verify** | non-zero | `True` | No build ran. **Not** repairable. |

The first two are distinguished from each other by `exit_code` alone; both are distinguished from the third by `fallback_used`. There is no fourth combination: `exit_code == 0` with `fallback_used == True` is legal **only** in permissive mode, and means "reported as passing without verification".

---

## 2. Substitution conditions

A substitution occurs — `fallback_used = True` — under exactly these four conditions. All four MUST honor this contract; none may report a silent success.

| # | Condition | Trigger | `attribution_ambiguous` | `matched_pattern` |
| --- | --- | --- | --- | --- |
| 1 | Daemon unreachable | reachability check returns false | `False` | unset |
| 2 | Runtime executable absent | `FileNotFoundError` on spawn | `False` | unset |
| 3 | Runtime communication failure | daemon/pipe/connection error during execution | `False` | unset |
| 4 | Build failed with environment-looking output | non-zero exit **and** a recognised pattern matched | `True` | the pattern that matched |

Conditions 1–3 are unambiguous environment faults. Condition 4 is **ambiguous by construction**: its recognised patterns include signatures that Maven also emits for genuinely broken build files, so the cause may be the environment or the project. Per FR-009 the ambiguity is recorded, never resolved by guesswork.

**Condition 4 is the most severe and must not be overlooked.** It converts a real build *failure* into a synthetic *success* — a false pass, not merely a missing verification. It is the only condition that can turn a failure into a pass.

---

## 3. Behaviour by mode

| Mode | Condition fires | `exit_code` | stdout | Marking |
| --- | --- | --- | --- | --- |
| **Default** (`ALLOW_HERMETIC_FALLBACK` unset/false) | any of 1–4 | **non-zero** | **no** synthetic output | `fallback_used = True`, reason set |
| **Permissive** (`ALLOW_HERMETIC_FALLBACK = true`) | any of 1–4 | `0` | legacy synthetic output | `fallback_used = True`, reason set |

Requirements this encodes:

- **FR-001** — default mode reports non-success and sets the marking.
- **FR-002** — permissive mode restores the pre-change outcome.
- **FR-006** — all four conditions obey the same policy.
- **FR-007** — the marking is set in **both** modes. Permissive mode changes what is permitted, not what is recorded.

---

## 4. Required invariants

1. `fallback_used == True` ⟹ `fallback_reason` is non-empty.
2. Default mode **and** a substitution fired ⟹ `exit_code != 0`.
3. Default mode **and** a substitution fired ⟹ the captured output does not contain the synthetic success text.
4. `attribution_ambiguous == True` ⟺ `matched_pattern` is set.
5. `attribution_ambiguous == True` ⟹ condition 4 fired.
6. Condition 4 firing in **permissive** mode MUST still record `matched_pattern` and `attribution_ambiguous`. The permissive switch governs whether a false pass is *permitted*, never whether the ambiguity is *recorded*.
7. No substitution changes the four-condition set. The existing recognised-pattern list is retained, not narrowed (Q2).

---

## 5. Consumer obligations

| Consumer | Obligation |
| --- | --- |
| `sandbox_node` | Propagate `fallback_used` into the metrics. When a substitution fired in **default** mode, terminate in `BLOCKED` **without entering the repair loop** and record the reason. |
| Repair loop | MUST NOT be entered for a "could not verify" outcome. No code patch fixes a missing daemon. |
| Measurement harness | Exclude fallback-marked results from every published figure (FR-008) and record how many were excluded. |
| Any figure publisher | MUST NOT present a figure computed over fallback-marked results as though verification occurred. |

---

## 6. Non-goals

Explicitly **not** governed by this contract, per the specification's scope:

- The verifier's correctness when a real build does run.
- The hardcoded synthetic test counts (5/5) attached in permissive mode. They remain, and remain wrong; this contract only ensures they can no longer be attached to a build that did not run.
- Repair-loop behavior. The loop is untouched; what changes is which outcomes reach it.
- How daemon reachability itself is determined.
