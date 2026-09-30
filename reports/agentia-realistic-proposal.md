# AgentIA: a realistic proposal, after the measurements

**Date:** 2026-09-29
**Supersedes:** [`agentia-sota-pathways.md`](agentia-sota-pathways.md) — that memo was
written from the literature and the code; this one is written from the literature and
the *measured behaviour* of the platform. Where they disagree, the measurement wins.
**Status:** Proposal. Nothing here is executed until a gate is passed, and every gate
is stated in advance.

---

## 0. The answer in one sentence

**Skill optimisation is not the next step — the measurements collapsed three of the
original proposal's assumptions, and they point at a different, more valuable target:
a trustworthy verification oracle.**

The original proposal (`docs/agentia_optimization_proposal.tex`) assumed three things
that are now known to be false on this platform:

| Original assumption | What the measurement showed |
|---|---|
| The optimiser is "deferred" and must be built | It is **built** (014 + 015). It cannot run, and could not run even if pointed at data |
| The conformance measure can be made to *vary*, and that variance is the signal | The measure is **flat at 0 on every session, including the ones that fail to build** — the instrument is blind to the failure it is supposed to explain |
| The build is a usable admission oracle | The build is **~33% nondeterministic** — the same frozen workspace, rebuilt six times, gave 4 pass / 2 fail |

The third one is the load-bearing discovery, and it is absent from every paper cited
in the proposal.

---

## 1. The measured state that a proposal must respect

These are facts, read from the running platform over the last day, not from the
literature:

1. **First verified build achieved.** For months the platform reported "0 of 15
   sessions verified". The cause was a one-character Docker mount defect —
   `:ro` + `:Z` concatenated as `:ro:Z`, which Docker rejects (`too many colons`) and
   exits 125 *before Maven runs*. Fixed; builds now run. The "0/15" was an
   environment bug, never a capability finding.
2. **The verifier is flaky at ~33%.** Same workspace, same command: 4/6 pass.
   Re-verifying all 12 recorded failures: 8 now pass. The failures are a
   `surefire` plugin-realm crash (`PluginContainerException`, a `surefire-shared-utils`
   foreign import), often *after* all tests pass. Root cause not yet established;
   the read-only Maven cache was ruled out (a read-write cache made it worse).
3. **The instrument is blind to build failure.** `new_penalty` is 0 on every session.
   The accumulated channel holds two consistency rules (schema↔entity table,
   schema↔entity column); a compilation or test failure trips neither.
4. **The optimiser's target is empty.** `exception_handling.md` and `mockito_tests.md`
   are 0 bytes; `active.md` is absent; injection is a byte-identical no-op. The
   injection point is a **single slot** — one document, no library, no retrieval.
5. **Instruction polarity is a null.** The pre-registered experiment gave
   prohibition-vs-control = 1 win / 3 losses / 2 ties. Instruction *content*,
   by contrast, directionally matters: a wrong-domain rule set was worse than the real
   instructions on 4 of 6 tasks.
6. **014's admission gate cannot conclude.** M=4 of 5 rotated blueprints has a
   two-sided p-floor of 0.0625 — it cannot reach significance under any outcome, even
   with a perfect verifier. With a flaky verifier it is a noise amplifier.

---

## 2. The papers, re-read against this state

The literature was reviewed once already; the point of re-reading it *now* is to ask
one question per paper: **does it transfer to a greenfield spec→Spring-Boot
synthesizer with a flaky hermetic build?** Most of the celebrated results do not.

| Paper | Claim | Transfers? | Why |
|---|---|---|---|
| [SkillOpt](https://arxiv.org/abs/2605.23904) | text-space skill optimizer, best-or-tied 52/52 cells | **No** | measured on tool-use/issue-resolution; single-slot document is *compatible* but the harness assumes a stable held-out score |
| [CODESKILL](https://arxiv.org/abs/2605.25430) | RL skill-bank policy +11.03 | **No** | needs training compute (no GPUs here) and a *skill bank* (none exists) |
| [Skill Issue](https://arxiv.org/abs/2609.12742) | repo-level skill opt is null (+0.1pp) | **Yes — the most relevant paper** | it is the one honest test of "optimize the skill doc on real code", and it is null, at *lower* noise than ours |
| [CoEvoSkills](https://arxiv.org/abs/2604.01687) | structured verifier ≫ opaque verdict | **Yes, as a principle** | re-derived empirically here: the channel is built and worth more than the loop; the build oracle is the broken half |
| [Ratchet](https://arxiv.org/abs/2605.22148) | eviction is impossible below a judge-quality floor; LLM skills +0.0pp vs human +16.2pp | **Yes, and it is decisive** | our "judge" flips ~33%, far above the floor → any loop would retire nothing or retire randomly |
| [Guardrails Beat Guidance](https://arxiv.org/abs/2604.11088) | prohibitions beat directives; content-independent priming | **No** | P4 nulled the polarity half, and our content result is *opposite* to their content-independence claim |
| [Scaffold, Not Vocabulary](https://arxiv.org/abs/2606.06454) | gains track scaffold, not skill text | **Yes** | consistent with the platform's own differentiator being the harness, not the prose |
| [Trautsch et al.](https://ar5iv.labs.arxiv.org/html/2111.09188) | static rule density ≈ orthogonal to bugs | **Yes** | undermines the conformance score as a correctness proxy; our own data confirms it (0 findings on failing builds) |
| [Architecture as Capability Equalizer](https://arxiv.org/abs/2608.21747) | structured specs help cheap models most | **Yes** | the platform's actual bet; a *reason* to keep the instruction set, not the skills |
| [SpecFirst](https://arxiv.org/abs/2607.27167) | spec-elicitation-first +6.9–21.3% | **Yes** | validates the spec-first architecture; a lever, not a skill-optimization lever |
| [On Randomness in Agentic Evals](https://arxiv.org/abs/2602.07150) | single-run pass@1 varies 2.2–6.0pp | **Yes — and we are worse** | our run-to-run variance is ~33%, five times the top of their range; every effect size in the field is below our noise floor |

**The re-read lands on one sentence:** the papers that transfer all say the same
thing — *the verifier is worth more than the loop, the scaffold beats the skill text,
and a noisy judge destroys any closed loop.* The papers that do **not** transfer are
the ones the original proposal leaned on for optimism.

---

## 3. Why skill optimisation is off the table — three arithmetic facts

Not pessimism; arithmetic.

**Fact A — the effect is below the noise floor.** The best prompt-based result
CODESKILL reports is ~+5.9pp; the best text-space result SkillOpt reports is ~+5.4pp
over its nearest competitor. Our verifier flips ~33% of runs. An effect five times
smaller than the label noise cannot be separated from it at any affordable sample
size. *Skill Issue* reached the same conclusion at **2.2–6.0pp** noise — and we are
five times noisier.

**Fact B — eviction is provably impossible.** Ratchet's theorem: a judge that scores
failures as passes at rate ρ ≥ (1−τ)/2 retires nothing at *any* sample size. Our
build oracle's flip rate is an order of magnitude above that threshold. The loop's
one "repair" operation — removing a bad skill — is therefore either inert or random.

**Fact C — the admission gate cannot detect anything.** M=4/5 has p-floor 0.0625.
Even a *perfect* verifier and a *perfect* effect cannot reach p<0.05 at that size.

A loop with a target that doesn't exist (Fact 0), an objective that doesn't move
(Fact 1), and a judge that can neither admit (Fact C) nor evict (Fact B) is not
"closer to skill optimisation" — it is three independent reasons it cannot work yet.

---

## 4. The realistic proposal

The ordering is new. Verification is first because everything else is downstream of
it; the optimiser is last, and may turn out to be unnecessary.

### Phase 0 — make the oracle deterministic *(blocking; no API spend)*

The verifier must agree with itself before it can be trusted to judge anything.

1. **Root-cause the surefire flake.** Hypotheses, in order of cheapness:
   (a) surefire fork/realm config (`forkCount`, plugin classloading), (b) Maven 3.9
   classworlds interaction, (c) container memory limits killing the forked JVM,
   (d) the `:Z` relabel on a shared read-only repo. The read-only cache has already
   been ruled out.
2. **Score repeats, not single builds.** Rerun-on-fail, or majority-of-k; a lone
   build is not an observation.
3. **Add a repeatability gate.** N rebuilds of one frozen workspace must agree. This
   becomes a CI check, so the flake cannot silently return.

*Go/no-go:* a frozen workspace builds identically ≥ 9/10 times.

### Phase 1 — make the measure able to move *(no API spend)*

An instrument that reads 0 on a failing build cannot attribute anything.

1. **Mine the real failures into deterministic checks.** The repair parser already
   classifies `COMPILATION_ERROR`, `ASSERTION_FAILURE`, `RUNTIME_EXCEPTION`; surface
   those as accumulated findings rather than discarding them.
2. **Prove discrimination.** On a frozen corpus, the measure must (i) vary across
   sessions and (ii) correlate with the (now-stable) build outcome. If a static rule
   cannot be made to correlate, that is itself the finding — Trautsch et al. suggest
   it may not be possible.
3. **Replace 014's 4-of-5 gate** with repeats-per-task + majority-of-k and a task
   count that can actually detect the target effect.

*Go/no-go:* `check_optimizer_gate.py` reports both "outcome varies" and "measure
varies" on a stable verifier.

### Phase 2 — the decisive, cheap measurement *(bounded API spend, pre-registered)*

With a stable oracle and a moving measure, one experiment decides whether a skill
document is a lever *at all* on this platform — the question the original proposal
skipped.

* **No-skill vs skill**, one variable, ≥6 tasks × ≥5 runs, pre-registered, majority-of-k
  verification.
* This is ~$3–5 of API spend, and it is the honest floor: if a *human-written* skill
  document does not move the (stable) measure beyond noise, no optimizer can.

*Go/no-go:* a skill document shows a measurable, correctly-attributed effect.

### Phase 3 — only then, the loop *(conditional)*

If — and only if — Phase 2 shows content matters on this platform, run the loop in
its correct shape:

* **Single document, single slot**, matching the platform.
* **Leave-one-rule-out** contribution, not leave-one-skill-out.
* **Deterministic instrument** as the objective (D2 stands); **build as guardrail**.
* Judged on **defects found**, never on a score improved.

---

## 5. What should stop, explicitly

* **Instruction polarity.** Nulled. Do not re-run it.
* **A skill *library* / RL curator.** There is no library and no compute, and the one
  repo-level test of the whole idea is null.
* **Conformance score as an acceptance criterion.** It is orthogonal to correctness
  (Trautsch, and our own 0-on-failure data) and gameable by padding (P3).

---

## 6. The reframe: the oracle is both the bottleneck and the product

This is the thing worth saying plainly, because it changes what "ahead of SOTA"
means for this project.

The papers that transfer — CoEvoSkills, Scaffold-Not-Vocabulary, Ratchet, Guardrails'
negatives, SpecFirst, Capability-Equalizer — all point the same way: **the verifier
and the harness are the value; the prose skill is the tail, not the dog.** AgentIA's
actual defensible asset is the trio of

1. a machine-checkable specification format,
2. a hermetic, deterministic oracle, and
3. a bounded repair loop that fails closed.

The measurements show items 2 and 3 are currently the *broken* parts, not the
strengths. Fixing them is not a detour from the roadmap — it is the roadmap. A
platform whose generated code provably compiles and passes an independent,
*reproducible* test is a rarer and more valuable thing than one that optimizes a
prompt document.

**So the realistic proposal is not "make the skills self-improve." It is "make the
verification trustworthy, mine its failures into checks, and only then ask whether a
skill document adds anything."** The optimiser stays closed until Phase 1's gate
passes, and the original proposal's own gate — *a loop fed a bad signal is no better
than no loop* — now has a measured reason: the signal is 33% noise.

---

## 7. What this does and does not cost

* Phase 0 and 1: engineering only, no API spend, and both pay for themselves whether
  or not an optimiser ever runs.
* Phase 2: ~$3–5, pre-registered, and it is the last spend before a loop is justified.
* Phase 3: only after Phase 2, and only if the evidence supports it.

The ~$6.26 spent so far bought, in exchange: the first verified build, the mount
defect, the product-path gap, the metric fix, a nulled lever, and — most valuable —
the discovery that the oracle itself is the problem. That last fact was invisible to
every paper cited and could not have been found without running the thing.
