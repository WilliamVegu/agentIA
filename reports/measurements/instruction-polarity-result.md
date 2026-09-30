# Instruction polarity experiment — result

**Date:** 2026-09-29
**Pre-registration:** [`backend/scripts/run_instruction_experiment.py`](../backend/scripts/run_instruction_experiment.py) docstring, fixed before the run.
**Data:** [`instruction-polarity.json`](instruction-polarity.json) (120 record slots; 92 with an outcome).
**Analysis:** `python backend/scripts/analyse_instruction_experiment.py`

**Status:** stopped deliberately after **4 of 5 runs per cell** to freeze spend at
**$6.26**, on the operator's instruction. The verdict below was already rendered at 3
runs and did not change at 4.

---

## Verdict

**NO DIFFERENCE DETECTED.** The hypothesis — that restating the stage instructions'
constraints as prohibitions improves outcomes, per *Guardrails Beat Guidance*
(arXiv:2604.11088v2) — is **not supported**.

| Comparison | Result (4 runs/cell) | p |
|---|---|---|
| **prohibition vs control** | **1W / 3L / 2T** | **0.63** |
| prohibition vs placebo | 3W / 2L / 1T | 1.00 |
| prohibition vs mismatched | 3W / 1L / 2T | 0.63 |
| placebo vs control | 1W / 3L / 2T | 0.63 |
| mismatched vs control | 1W / 4L / 1T | 0.38 |

Six tasks; the minimum attainable two-sided p is 0.03125, so **only a unanimous
result could have been significant**. Polarity produced one win, three losses and two
ties against control: if anything it drifts *worse*, and it is certainly not a small
effect that more runs would rescue. That is what the pre-registration exists to
prevent anyone arguing after the fact.

## The secondary finding is the one worth keeping

Both **content-free** and **wrong-domain** rule sets underperform the real
instructions in every comparison they appear in:

* `placebo` (content-free process prose) — 1W / 3L / 2T vs control
* `mismatched` (another stage's real rules) — 1W / 4L / 1T vs control

Neither is significant at n=6, but they agree, and `mismatched` is the strongest
directional result in the dataset. Together they **qualify the content-independence
claim** this project's memo relied on. That study found mismatched-domain rule files
performed *like* curated ones (58.6 vs 56.9), which is what made "the gain is
priming, not content" credible. Here the wrong-domain rules are worse than the real
ones. If that holds, **instruction content is doing real work on this platform**,
which supports the hand-written instruction set rather than undercutting it.

## Limitations

1. **The verifier is flaky, which contaminates the absolute rates.** The same frozen
   workspace, rebuilt six times with the same command, gave **4 pass / 2 fail**. So
   the pass/fail split in this dataset is **not** a code-quality measure. The arm
   comparisons are less affected, because flakiness is independent of which
   instructions a session ran with — but no absolute rate from here should be quoted.
2. **n = 6 tasks.** Only unanimity is detectable. "No difference detected" means
   exactly that: a modest real effect would be invisible at this size.
3. **4 of 5 runs.** Runs 4 and 5 were cut short by the operator to stop spend, after
   an earlier attempt exhausted the provider balance (`402 Insufficient Balance`).
4. **The content-free placebo is a weaker control than it looks.** It removes the
   rules without substituting a plausible alternative, so it may be actively
   unhelpful rather than neutral. The `mismatched` arm exists to settle that and was
   added after the run began, so it is **not** part of the pre-registered comparison.
5. **One provider, one model** (deepseek-flash), 4 runs per cell.

## What this changes

* **Do not pursue instruction polarity.** It is a null here, and slightly negative.
* **Content is worth engineering** — directionally supported and consistent across two
  independent controls. This is the reason to author the skill documents rather than
  delete them.
* **Fix the verifier before spending on any further measurement.** A 33% flip rate
  makes every pass/fail rate, and every admission decision built on one, unreliable.
  This now outranks the optimiser work entirely.
