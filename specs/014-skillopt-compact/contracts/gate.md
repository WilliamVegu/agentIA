# Contract — Gate

**Feature**: 014-skillopt-compact · **Implements**: FR-006, FR-006a, FR-007

The gate decides whether anything is learned. This contract defines what a pass is, why the two evidence sets are disjoint, and when a candidate is accepted.

---

## 1. Two evidence sources, disjoint by construction

| | Source | Disjointness |
| --- | --- | --- |
| **Training** | Recorded sessions read from the database | Already happened, produced under the **previous** skill, so it cannot encode the candidate |
| **Held-out** | **Fresh execution** with the skill under test active | Exists only after the candidate does |

**The gate MUST assert that no session identifier in the held-out executions appears in the training evidence, and MUST fail loudly rather than score if it does.**

The disjointness is structural, not sampled. That is a stronger guarantee than a correct random split — and it is exactly why the assertion is required: the structural argument holds today, and the assertion is what keeps it holding when the code changes. A future edit could make the prose true while the code was false.

**Recorded outcomes are never gate evidence.** A recorded verdict describes what happened under a **different** skill. It cannot be re-attributed to the candidate, so using it would compare two numbers that do not both describe the thing under test.

## 2. What counts as a pass

**A pass is an execution whose offline build/test exit code is zero.**

Two exclusions, both load-bearing:

| Case | Counts as | Why |
| --- | --- | --- |
| Verification used the **hermetic fallback** | **Not a pass**, even at exit code zero | Under permissive mode a substitution returns success **without compiling anything**. Scoring on exit code alone would reward a skill for making the verifier give up — and a text optimiser will find that exploit, because "improve the score" is exactly what it is asked to do. Feature 012 established that a synthetic verification is not a successful generation; the same rule must hold here. |
| Execution **could not be scored** (no build ran, no workspace) | Reported **separately** from failures | Folding it into the failure count would make an infrastructure problem look like a skill regression. |

## 3. The held-out set

The five existing baseline blueprints — `pair-a`, `pair-b`, `minimal`, `multi-entity`, `constrained`. **No new fixtures**: a task set authored alongside the thing it evaluates measures the author, not the skill.

**M = 4** of the 5 per iteration, leaving one as a **rotation buffer**. Successive iterations are therefore not scored on an identical fixed exam — a five-item exam scored repeatedly would eventually be memorised by the loop.

**Rotation is deterministic**, derived from the iteration's identity rather than from the clock or process randomness, so re-running an iteration selects the same blueprints (SC-010).

**Recorded limitation**: five tasks is a small exam, and one task moves the pass rate by 25 points. The gate is therefore coarse, and a single execution's noise can decide an acceptance. Acceptable for a loop-validation feature; **not** acceptable for a production optimiser, where it belongs with the deferred statistical validation.

## 4. Scoring both skills

```
current_score   = score(current skill,   held_out_blueprints)
candidate_score = score(candidate skill, held_out_blueprints)
accept iff candidate_score > current_score          # STRICT
```

**Both scores are computed in the same iteration, on the identical held-out set, by the same scoring function.** Scoring them on different samples would produce a comparison that is meaningless while still yielding a number.

**Cost: 2×M fresh executions per iteration** (default 8), accepted deliberately. Carrying the previous run's score forward would be cheaper but compares a number measured on one sample against a number measured on another, is absent on the first iteration, and silently breaks whenever the held-out set rotates — which §3 makes routine.

## 5. Acceptance

| Comparison | Decision |
| --- | --- |
| candidate **>** current | **ACCEPTED** |
| candidate **=** current | **REJECTED** |
| candidate **<** current | **REJECTED** |

**A tie is rejected because it is not evidence of improvement.** Accepting ties would let a skill drift on noise while every step looked successful. An iteration that changes nothing is a *rejected* iteration — which is the honest reading, and is the common case on an exam this small.

## 6. Injectable runner

Fresh execution MUST go through a runner supplied as a parameter. Production passes the real session runner; the test passes one backed by the scripted model client.

**Why a parameter rather than a monkeypatch**: the seam is explicit, so a refactor cannot silently stop injecting and leave the suite calling a provider. Constitution Principle VI forbids provider calls in the automated suite, and the success criteria require a full iteration to be demonstrable — an untested gate would report acceptances nobody had ever checked.
