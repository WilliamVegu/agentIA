# Phase 0 Research: Diagnostic-Driven Skill Evolution

Every decision below resolves an unknown from the spec or the plan's Technical
Context. Sources are the three reports already in this repository, each of which
cites its own primary literature:

- [reports/agent-skill-optimization-sota.md](../../reports/agent-skill-optimization-sota.md)
- [reports/skillopt-for-coding-deep-dive.md](../../reports/skillopt-for-coding-deep-dive.md)
- [reports/codeskill-ablation-analysis.md](../../reports/codeskill-ablation-analysis.md)

---

## D1 — The objective is conformance, not build success

**Decision**: an optimization round optimises the conformance measure. Build
success is retained as a guardrail that can veto, never as the objective.

**Rationale**: build success is a binary whole-corpus outcome. At five held-out
blueprints the smallest effect separable from run-to-run variance is far larger
than any skill edit produces, so a loop gated on it cannot demonstrate anything —
a limitation feature 014's own planning already recorded. Conformance is
continuous, is measured deterministically at zero cost, and is the outcome the
literature reports skill documents can move.

**Alternatives considered**:
- *Build pass rate* — rejected: unmeasurable at this scale, and gameable by
  emitting less code.
- *Token or cost reduction* — deferred: a legitimate secondary objective (skill
  documents reliably reduce tokens), but it is not what the operator asked to
  improve, and selecting on it could reward generating less.

---

## D2 — The instrument is the existing deterministic channel, not a language model

**Decision**: use `services/conformance_diagnostics.diagnose` as the evaluation
signal. Do not introduce an LLM judge for scoring.

**Rationale**: the instrument is deterministic, therefore a measured improvement
cannot be the judge drifting (FR-003). It performs zero model calls, so
measurement is free and can run on every session. And an LLM judge is the
instrument the literature most distrusts: the controlled study of a
code-generation skill exists specifically because such gains are *"almost always
read off an LLM-as-a-judge, an instrument with documented positional,
self-preference, and stylistic biases"* ([arXiv:2606.06454](https://arxiv.org/abs/2606.06454)).

**Alternatives considered**:
- *LLM-as-judge scoring* — rejected: non-deterministic, biased, and it would let a
  round improve its score by changing how it is judged.
- *Test execution as the only signal* — rejected as the sole signal: 11.3% of
  SWE-bench Lite problems have non-deterministic suites, and SWE-bench+ measured
  31.08% weak-test suspicious passes. Retained instead as the guardrail.

---

## D3 — Contribution is measured per skill by leave-one-out

**Decision**: attribute contribution by comparing outcomes with a skill present
against outcomes with it absent, per skill, rather than comparing whole-corpus
pass rates.

**Rationale**: this is the primitive that converts "the output got better" into
"this rule was responsible", and it is available **training-free** — the method
that formalises it is explicitly *"training-free"* and computes exactly
`Δ(τ,s) = r(τ,s) − r(τ,∅)` by replaying with the skill removed. It also addresses
the credit-assignment problem that makes a single monolithic document
unattributable: with one document, an edit set cannot be traced to an effect,
because co-applied rules confound one another.

**Cost note**: attribution is multiplicative — skills × tasks — and therefore the
per-round skill bound (FR-017) is what keeps it affordable on this platform. A
large set and a usable task count cannot both be had.

**Alternatives considered**:
- *Whole-document pass-rate comparison* — the feature-014 gate; rejected as the
  objective because it cannot attribute and cannot reach significance at this
  scale.
- *Trained attribution policy* — rejected: requires weight updates and a training
  environment, which this platform does not have.

---

## D4 — Removal requires an evidence floor, and "no proven benefit" is not enough

**Decision**: prune a skill only when its measured contribution is below a stated
floor. Absence of a demonstrated benefit is not grounds for removal.

**Rationale**: with noisy measurement, "we could not prove it helps" and "it
hurts" are different findings, and conflating them converts measurement noise into
removals. The maintenance operation is also the one that decides whether the set
stays usable at all — an unmaintained skill library has been measured to degrade
until *"injecting a skill scores worse than injecting nothing"*, and
contribution-based eviction with a floor is the repair
([arXiv:2605.22148](https://arxiv.org/abs/2605.22148)). Independent work agrees on
the direction: add-only editing reaches 47.0 where all three operations reach
59.0.

**Alternatives considered**:
- *No removal (feature 014's behaviour)* — rejected: rejected edits are discarded
  and may be reproposed indefinitely, and nothing ever leaves the set.
- *Remove on any non-improvement* — rejected: noise would drive removal.

---

## D5 — The proposal mechanism is reflection, with no weight updates

**Decision**: proposals come from a language model reflecting over recorded
evidence, as feature 014 already does. No training, no fine-tuning, no
reinforcement learning.

**Rationale**: the platform has no compute for weight updates. Within that
constraint the evidence is favourable but bounded. Training a curator is out of
reach, but a **prompt-based curator on the identical pipeline, with no training,
no iteration and no verifier feedback, captures roughly half the gain** that the
trained version achieves on real coding benchmarks — so reflection starts from a
measured floor, not from zero. Reflection is also the mechanism the best-reported
training-free result uses, and it is the mechanism that reaches that result
*without* the diagnostic channel this feature supplies.

**Honest bound**: how much of the trained curator's additional gain reflection
recovers is **unmeasured**. The plan does not promise to match a trained policy;
it promises to measure what reflection achieves here.

**Alternatives considered**:
- *Reinforcement learning over a skill-management policy* — the strongest reported
  results on real coding benchmarks use it; rejected for cost, not efficacy.
- *No proposal mechanism at all* — rejected: the operator asked for a
  self-improvement loop.

---

## D6 — The conformance measure is normalised for artifact-set size

**Decision**: the measure is comparable across artifact sets of different sizes.

**Rationale**: a raw weighted count grows with the number of files, so a larger
service scores worse for being larger, and a round pointed at it could improve the
measure by generating less code. That is the low-distinguishability verifier
failure mode the literature warns about, and it is the one an optimiser will
exploit if given the opportunity.

**Alternatives considered**:
- *Raw finding count* — rejected: size-correlated, therefore exploitable.
- *Per-rule presence/absence* — rejected: discards severity, which is the part
  that carries the cost information.

---

## D7 — Per-stage attribution comes from the existing journal

**Decision**: persist the conformance verdict already carried on each stage entry,
so the record attributes findings to the stage that introduced them.

**Rationale**: the platform already computes a verdict per stage and stores it on
the stage entry; it is simply never persisted or surfaced. Reading what already
exists costs almost nothing and converts a session total into an attributable
profile — which stage introduced the defect.

**Important limit**: this adds *resolution*, not *evidence*. Re-checking the same
tasks repeatedly is still the same number of distinct tasks (FR-009). Per-request
measurement does not address the small-sample problem, and the plan must not
imply that it does.

**Alternatives considered**:
- *Session-level total only* — rejected: loses the attribution that is already
  computed and free to keep.
- *Sampling more requests to raise the count* — rejected: repeated observations of
  the same task are not independent evidence.

---

## D8 — Insufficiency is a reportable outcome

**Decision**: a measurement reports the number of distinct tasks behind it, the
smallest effect detectable at that size, and explicitly states when the evidence
cannot support a conclusion.

**Rationale**: the arithmetic floor for any paired comparison at five tasks cannot
reach significance under any outcome, so a feature that reported a point estimate
without its power would be reporting noise as a result. Reporting insufficiency is
the honest output and, at this scale, the expected one. A round must never present
an unmeasurable difference as an improvement (FR-016).

**Alternatives considered**:
- *Report the difference and let the reader judge* — rejected: the reader will not
  re-derive the power, and the number will be quoted out of context.
- *Refuse to report anything below a threshold* — rejected: it would hide the
  evidence size, which is the thing that tells an operator whether to gather more.

---

## D9 — The feature-014 gate is demoted to a guardrail

**Decision**: the existing strict-improvement gate is retained as a veto against
regression, not as the acceptance criterion for a round.

**Rationale**: the gate's guarantee — accept only on a strict improvement over
fresh executions — is genuinely valuable as a regression filter, and it is already
implemented and tested. What it cannot do is serve as the *objective*, because a
binary comparison on a handful of tasks cannot separate a real change from
variance. Splitting the roles keeps the useful half and stops the unusable half
from being the thing that decides.

**Alternatives considered**:
- *Remove the gate* — rejected: it is a working regression filter with real tests
  behind it.
- *Keep the gate as the acceptance criterion* — rejected: it is the defect this
  feature exists to correct.

---

## D10 — The per-round skill bound is fixed and documented

**Decision**: a round considers a bounded number of skills, documented in code.

**Rationale**: attribution cost is skills × tasks, so an unbounded set makes
measurement unaffordable, and a compact set is also what keeps the undertaking
measurable at all. The bound is a deliberate trade of breadth for the ability to
attribute.

**Alternatives considered**:
- *Unbounded set* — rejected: attribution becomes unaffordable, and the measurement
  stops being runnable, which is worse than a smaller set that is measured.

---

## Open question carried into implementation

**Does a static, hand-written rule scan discriminate well enough to select on?**
The channel's separation has been measured over the fixture vocabulary and it
detects every rule kind, but the fixture matrix is degenerate — every blueprint
yields an identical row — so it demonstrates that the channel *functions* without
demonstrating that it discriminates on real variation. It also says nothing about
whether conformance separation predicts build outcomes. Both require diagnostics
recorded from real sessions, which is this feature's first deliverable, and the
discrimination measurement must be re-run once real records exist.
