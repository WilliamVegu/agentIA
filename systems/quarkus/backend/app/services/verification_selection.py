"""Verification-guided selection: best-of-k, stopping at the first verified candidate.

**Why this is the highest-ranked affordable lever.** Both this repository's own
readiness analysis and the 2026 literature put verification-guided selection above
every text-space alternative, and the reason is statistical rather than stylistic:
selection moves a **binary per-task outcome**, so it is measurable at a handful of
tasks, where a conformance nudge of a few points is buried in a 2.2-6.0pp run-to-run
swing. Reported gains are large and consistent:

* R2E-Gym: pass@1 34.4% -> 49.4% with a best-of-16 hybrid verifier.
* CodeT: HumanEval pass@1 47.0% -> 65.8% from generated tests plus execution agreement.
* SWE-bench Lite: 15.9% -> 29.62% at k=5 (DeepSeek-Coder-V2), at a cost per solved
  task below GPT-4o and Claude 3.5 Sonnet at the time.

**Why it is affordable here.** Generation costs ~$0.065 per hard service and the
verifier is the platform's own hermetic sandbox, which is free and deterministic. At
k=4 that is ~$0.26 per accepted service -- two orders of magnitude below published
research-agent costs per task -- and it buys reliability **without trusting the
model**.

**Why it stops early.** Uniform budgets are strictly suboptimal: in one 123-issue
study roughly half the tasks were solved by a single rollout while the baseline spent
five on every task. Early stopping at the first verified candidate captures the gain
at the cost of the attempts actually needed, at the price of latency. The same study
warns that self-confidence is too weak a stopping signal -- which is why the stop
condition here is the *verifier*, never the model's own opinion of its work.

**What this is not.** It is not a correctness oracle. It selects on whatever the
verifier measures, so a weak verifier selects weak candidates with more confidence --
which is why the platform contract test exists and why a substituted verification
must never count as a pass. ``verify`` is injected precisely so the caller owns that
contract, and the tests below pin that a fallback-shaped result cannot be selected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class SelectionOutcome:
    """What selection did, and what it cost in attempts."""

    #: Index of the selected candidate, or ``None`` when none verified.
    selected_index: Optional[int]
    #: How many candidates were generated and verified before stopping.
    attempts: int
    #: Whether a verified candidate was found.
    verified: bool
    #: Reason the outcome is what it is, for the record. A report that cannot say
    #: why it selected nothing is indistinguishable from one that never ran.
    reason: str
    #: Per-candidate verifier results, in order, for diagnosis.
    verifier_results: Tuple[bool, ...] = field(default_factory=tuple)

    @property
    def attempts_spent(self) -> int:
        return self.attempts


def select_first_verified(
    candidates: Iterable[Any],
    verify: Callable[[Any], bool],
    *,
    max_candidates: Optional[int] = None,
) -> SelectionOutcome:
    """Generate up to ``max_candidates`` and return the first that ``verify`` passes.

    ``candidates`` is consumed lazily, so a caller can generate on demand and the
    cost is the number of attempts actually made -- not the budget. Stops at the
    first verification pass.

    **Never selects an unverified candidate.** If none passes, the outcome reports
    ``verified=False`` with ``selected_index=None``. Returning the "best" failing
    candidate would report a success the verifier explicitly denied, which is the
    conflation feature 012 exists to prevent.
    """
    results: List[bool] = []
    generated = 0

    for index, candidate in enumerate(candidates):
        if max_candidates is not None and generated >= max_candidates:
            break
        generated += 1

        try:
            passed = bool(verify(candidate))
        except Exception as exc:  # noqa: BLE001
            # A verifier that raises has NOT verified anything. Treating an
            # exception as a pass would let an environment fault masquerade as a
            # verified service -- the exact substitution the honest sandbox refuses
            # to make. Treating it as a plain failure would hide the fault, so it is
            # recorded as a non-pass and the reason names it.
            results.append(False)
            return SelectionOutcome(
                selected_index=None,
                attempts=generated,
                verified=False,
                reason=(
                    f"the verifier raised {type(exc).__name__} on candidate {index}: "
                    f"{exc}. Nothing was verified."
                ),
                verifier_results=tuple(results),
            )

        results.append(passed)
        if passed:
            return SelectionOutcome(
                selected_index=index,
                attempts=generated,
                verified=True,
                reason=(
                    f"candidate {index} verified after {generated} attempt(s); "
                    f"stopped early rather than spending the full budget"
                ),
                verifier_results=tuple(results),
            )

    if generated == 0:
        reason = "no candidate was generated; nothing was verified"
    else:
        reason = (
            f"none of {generated} candidate(s) verified; no candidate was selected. "
            f"This is a capability finding, not a selection success."
        )
    return SelectionOutcome(
        selected_index=None,
        attempts=generated,
        verified=False,
        reason=reason,
        verifier_results=tuple(results),
    )
