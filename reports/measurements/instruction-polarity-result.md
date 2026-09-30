# Instruction polarity experiment — result

**Date:** 2026-09-29
**Pre-registration:** [`backend/scripts/run_instruction_experiment.py`](../backend/scripts/run_instruction_experiment.py) docstring, fixed before the run.
**Data:** [`instruction-polarity.json`](instruction-polarity.json) (120 records).
**Analysis:** `python backend/scripts/analyse_instruction_experiment.py`

---

## Verdict

**NO DIFFERENCE DETECTED.** The hypothesis — that restating the stage instructions'
constraints as prohibitions improves outcomes, per *Guardrails Beat Guidance*
(arXiv:2604.11088v2) — is **not supported**.

| Comparison | Result | p |
|---|---|---|
| **prohibition vs control** | **1W / 2L / 3T** | **1.00** |
| prohibition vs placebo | 3W / 0L / 3T | 0.25 |
| prohibition vs mismatched | 3W / 1L / 2T | 0.63 |
| placebo vs control | 1W / 4L / 1T | 0.38 |
| mismatched vs control | 1W / 3L / 2T | 0.63 |

Six tasks; the minimum attainable two-sided p is 0.03125, so **only a unanimous
result could have been significant**. Polarity produced one win, two losses and three
ties against control — not a trend, and not a small effect that more runs would
rescue.

## The secondary finding is the interesting one

Both **content-free** and **wrong-domain** rule sets underperform the real
instructions in every comparison they appear in:

* `placebo` (content-free process prose) — 1W / 4L / 1T vs control
* `mismatched` (another stage's real rules) — 1W / 3L / 2T vs control

Neither is significant, but both point the same way, and together they **qualify the
content-independence claim** this project's memo relied on. That study found
mismatched-domain rule files performed *like* curated ones (58.6 vs 56.9), which is
what made "the gain is priming, not content" credible. Here the mismatched rules are
worse than the real ones. If that holds, **instruction content is doing real work on
this platform**, which supports the hand-written instruction set rather than
undercutting it.

## Coverage and why it stopped at 3 runs

Pre-registered at 5 runs/task. Delivered **3 runs/task** — every one of the 24 cells
has exactly 3 outcomes. The remaining 48 cells (runs 4 and 5) failed with:

```
APIStatusError: Error code: 402 - Insufficient Balance
```

The provider account ran out of credit. This is a resource limit, not a design
choice, and it is the only thing standing between this and the pre-registered design.
Total spend: **$5.27** over 91 sessions.

## Limitations

1. **The verifier is flaky, which contaminates the absolute rates.** The same frozen
   workspace, rebuilt six times with the same command: **4 pass / 2 fail**. See
   `agentia-sota-pathways.md` and the follow-up analysis. The 48-pass / 24-fail split
   in this dataset is therefore **not** a code-quality measure. The arm comparisons
   are less affected, because flakiness is independent of which instructions a
   session ran with — but the absolute numbers should not be quoted.
2. **n = 6 tasks.** Only unanimity is detectable. A modest real effect would be
   invisible here, and "no difference detected" means exactly that.
3. **The content-free placebo is a weaker control than it looks.** It removes the
   rules without substituting a plausible alternative, so it may be actively
   unhelpful rather than neutral. The `mismatched` arm exists to settle that and was
   added after the run began, so it is **not** part of the pre-registered comparison.
4. **One provider, one model** (deepseek-flash), three runs per cell.

## What this changes

* **Do not pursue instruction polarity.** It is a null here, and the pre-registered
  rule forbids reading it as a trend.
* **Content is worth engineering** — weakly supported, and the reason to author the
  skill documents rather than delete them.
* **Fix the verifier before spending on any further measurement.** A 33% flip rate
  makes every pass/fail rate, and every admission decision built on one, unreliable.
* **runs 4–5 have low expected value for the polarity question.** The result is
  1W/2L/3T; reaching significance requires prohibition to win all six tasks, and no
  amount of additional runs changes a completed task's verdict.
