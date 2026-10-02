# AgentIA and the 2026 agentic-coding frontier: a decision memo

**Date:** 2026-09-29
**Scope:** What the self-improvement ("reflective skill optimisation") intent should do
next, which SOTA levers actually apply to AgentIA's task class, and which path to take.
**Status:** Decision memo, 2026-09-29. Evidence provenance is stated precisely because
this repo has already had to retract two claims: §2.1–§2.3 record what **I fetched and
checked at the primary source myself**; §3 draws additionally on five parallel evidence
reviews, and §6 items 10–20 list every claim that rests on those reviews rather than on my
own fetch, including the ones they flagged as unreachable. Every claim about the codebase
was read out of the working tree at HEAD `37b5853`.
**Companions:** [agentia_optimization_proposal.tex](docs/agentia_optimization_proposal.tex),
[agentia_measurement_and_readiness.tex](docs/agentia_measurement_and_readiness.tex),
[spec.md](specs/015-diagnostic-skill-evolution/spec.md).

---

## 0. The answer in one page

### 0.1 The finding that reorganises the question

**The self-improvement machinery is already built — all of it — and it cannot run,
for one reason that has nothing to do with self-improvement.**

| Component | File | State |
|---|---|---|
| Diagnostic channel (rules, severity, per-stage attribution) | `services/conformance_diagnostics.py` | built |
| Durable session record | `models/diagnostics.py` | built |
| Corpus report | `services/corpus_report.py` | built |
| Reflection loop (`collect`/`reflect`/`apply`/`gate`) | `scripts/skillopt/` | built (feature 014) |
| Per-skill contribution, leave-one-out (D3) | `services/skill_contribution.py` | **built** (feature 015) |
| Eviction with an evidence floor (D4) | `scripts/skillopt/currency.py` | **built** (feature 015) |
| The round orchestrator (D9 gate demoted to veto) | `scripts/skillopt/round.py` | **built** (feature 015) |

The proposal's "what exists vs what is deferred" table predates feature 015 and is
**stale**: it lists per-skill contribution and eviction as deferred, and both exist as of
commit `c273193` with tests. This is worth stating plainly because it changes the
question from "should we build the optimiser?" to "**why does the built optimiser return
nothing, and what is the one thing blocking it?**"

The answer is a single causal chain:

```
container runtime unreachable
   -> every build falls back to a synthetic exit code
   -> a fallback execution is NEVER scorable (014 contracts/gate.md)
   -> the gate has no scorable execution to compare
   -> every round returns REJECTED / NO_MEASURABLE_CHANGE
```

This is not a prediction. It is what happened: the only two real iterations that ever
ran "returned `REJECTED` with no scorable executions" (SC-007 in
[plan.md](specs/014-skillopt-compact/plan.md)). And 0 of 15 measured sessions were
verified, with `unverified = 1` on every real diagnostic record.

> **So the next step on the self-improvement intent is not more self-improvement. It is
> to make one build actually verify.** That single fix changes the optimiser from
> unrunnable to runnable, and simultaneously supplies the objective (build pass rate)
> that every reliability claim in this repo currently lacks.

### 0.2 The second finding: even once runnable, the built gate cannot conclude

Feature 014's gate compares `current_score` against `candidate_score` over **M = 4 of 5
rotated blueprints** and accepts on a strict improvement. With four or five paired
tasks, the minimum attainable two-sided p is **0.125** and **0.0625** respectively — such
a test *cannot reach p < 0.05 under any outcome*. The two research reports independently
computed the probability that this strict-improvement gate reports a gain between two
**identical** configurations and got **0.61 (n=4) / 0.76 (n=5)** at p=0.5 — a figure I could
not reproduce under a simple independent-Bernoulli model (§6 item 3), so treat it as their
computation rather than a settled constant. The power floor above is exact and is enough on
its own.

Whatever the precise figure, the direction is not in doubt: a 4-of-5 strict-improvement
gate is a **noise amplifier**, not an admission criterion. D9 already demoted it to a
regression veto — correct — but that means the round's *decision* currently rests on
leave-one-out contribution measured over a corpus whose builds are unverified. **The
optimiser is built on top of a verifier that has never returned a verdict.**

### 0.3 The recommendation

Dependency-ordered. P0–P2 are prerequisites; P3–P6 are cheap measurable experiments;
P7 is positioning; P8 stays closed.

| # | Action | Why now | Cost |
|---|---|---|---|
| **P0** | Make the container runtime verify one real build, end to end | The *sole* blocker on the built optimiser and on every reliability claim. 0/15 sessions verified | ops, not engineering |
| **P1** | Make both generation entry points run the model | `POST /sessions` silently emits templates while quick-start runs the model | one-line fix |
| **P2** | Give the system an **acceptance signal the generator cannot author**: persistence/integration test tier, mutation score, `.git` stripped, no egress | Generated tests mock the repository out — the one real defect found lived in exactly that seam. This is also what SOTA in this task class does (Commit0 supplies tests; ProgramBench fuzzes them) | days |
| **P3** | **Replace the density normalisation** with absolute *new* violations against a frozen baseline plus a size/coverage floor | Penalty-per-100-artifacts rewards emitting *more* files; the mirror image of the raw-count flaw D6 fixed. Both are gameable ratios (§3.9) | hours |
| **P4** | Rewrite stage instructions from **prescriptions to prohibitions**, against a length-matched placebo, ≥5 runs/task | `Guardrails Beat Guidance`: beneficial rules are negative constraints, harmful ones are positive directives. AgentIA's instructions are overwhelmingly prescriptive | days, $0.064/task |
| **P5** | Build verification-guided selection (best-of-$k$) | Highest-ranked affordable lever in the literature *and* this repo's readiness analysis; the only one measurable at $n{=}10$ because it moves a binary outcome | days; $k{=}4 \approx \$0.26$/task |
| **P6** | Widen the rule set **only with artifact-consistency invariants** | The closest Java study finds static style/architecture rules are near-orthogonal to bugs — possibly inverted. Consistency rules (schema↔entity) already have a demonstrated catch here | ongoing |
| **P7** | Establish **external validity**: report on a recognised protocol (ScarfBench-style container-deploy behavioural, or NL2Repo-Bench-style empty-workspace) or publish the benchmark for the white space | No benchmark ingests AgentIA's artifact class, so every current claim is unfalsifiable from outside. Being the first to define it is the leadership position | weeks |
| **P8** | Run the built optimiser **only after a measure varies** — and judge it on defects found, not score improved | It is already built; it needs a signal, not more code | — |

**Cross-cutting requirement — the honesty protocol.** Any claim of improvement must use a
paired design on a fixed task set with one variable changed, **≥5 independent runs per task**
(single-run pass@1 moves 2.2–6.0pp and temperature 0 is *not* deterministic), a
**pre-registered** primary metric and tie band, a power analysis sized *before* the run, and
a reported **hacking rate** with hacking attempts scored as failures
([2602.07150](https://arxiv.org/abs/2602.07150), [2411.00640](https://arxiv.org/abs/2411.00640)).
Feature 014's 4-of-5 gate cannot satisfy this and cannot reach p<0.05 at all.

**The one-sentence position.** The loop is finished and starving for a signal, and the signal
is not a better prompt — it is a working container, an acceptance signal the generator did not
write, and a metric that cannot be improved by generating more files.

---

## 1. What AgentIA is — and why the task class decides everything

**AgentIA is not a SWE-bench agent.**

| | SWE-bench-style agent | AgentIA |
|---|---|---|
| Input | a GitHub issue + an existing repo | a formal blueprint (entities, attributes, validation rules, BDD Given/When/Then, 4-layer architecture) |
| Output | a patch to existing code | a complete greenfield Java 21 / Spring Boot 3 Maven service |
| Task class | issue resolution / repo editing | **specification-driven whole-application synthesis** |
| Ground truth | the repo's human-written tests | the platform's own hermetic build (`mvn test -o --network none`) |
| Verification | repo test suite | *generated* test suite + architecture conformance rules |
| Success | binary: issue resolved | binary: does it build and pass? — **never measured** |

Task class determines which literature transfers. Nearly every loud 2026 result —
SkillOpt's 52/52 cells, CODESKILL's +11.03, the Skill Issue null — is measured on
**issue resolution or tool use** (SWE-bench Verified, Terminal-Bench 2, EnvBench,
SkillsBench). None is measured on "generate a correct multi-file Spring Boot service
from a formal specification". AgentIA is in a sparsely-benchmarked niche, which is both
its risk and its defensibility (§4).

### 1.1 Six structural facts that constrain the decision

Read out of the working tree, not inferred:

1. **The skill injection point is a single slot.** `app/skills/active.py` resolves one
   `active.md` pointer to one `SkillDocument`; `runner.py:546` prefixes exactly that one
   document. There is no library, no retrieval, no selection.
2. **No skill is active and two of three documents are empty.**
   `skills/layer_architecture.md` is 32 lines; `exception_handling.md` and
   `mockito_tests.md` are **0 bytes**; `active.md` **does not exist**. Injection is
   currently a byte-identical no-op.
3. **The one authored skill duplicates the gate.** `layer_architecture.md` restates rules
   `compliance.py` already enforces as `PRINCIPLE_I_LAYER_ISOLATION` and relatives. A
   loop that "improves" it can only make it agree harder with a check that already passes.
4. **The measure is at ceiling.** 21 `session_diagnostic_records`: 20 score 100; the one
   85 is the `corpus-constrained` fixture. Cause is structural and already diagnosed: the
   gate **blocks local violations before persistence**, so only *accumulated* whole-project
   findings survive into a saved artifact set — a channel that held one easily-satisfied
   rule (now two, after `37b5853` added `SCHEMA_ENTITY_MISMATCH`).
5. **The binary objective was never measured.** 0/15 sessions verified,
   `unverified = 1` on every real record.
6. **The optimiser is built and unrunnable** (§0.1).

Note the tension between 1 and the proposal's D3/D4: leave-one-out contribution and
eviction-with-a-floor both presuppose a *set* of skills, and the platform has a *single*
slot. This is incidentally aligned with SkillOpt itself, which also edits **one**
document ([2605.23904](https://arxiv.org/abs/2605.23904)) — but it means D3/D4 as written
do not describe this system.

### 1.2 A counter-consideration, stated fairly

The proposal's load-bearing decision — *build the diagnostic channel before the loop* —
was correct and was vindicated. The instrument is deterministic, model-free,
rule-attributed and free, and commit `37b5853` used exactly that channel to find a real
defect: the generated schema contradicted the generated entities. The instrument works.
This memo does not argue the instrument was a mistake. It argues that **the instrument's
value is demonstrated and the loop's is not**, and that the next increment of value is in
widening the instrument's *correctness* reach rather than in curating prose.

---

## 2. Due diligence: the evidence base, audited

This repository has already issued two corrections to its own reports
(`retract the first baseline's central finding`; `the conformance measure is NOT
structurally pinned`). The same standard applies to the literature it cites.

### 2.1 Confirmed at the primary source

| Source | Repo's claim | Primary source says | Verdict |
|---|---|---|---|
| [GEPA 2507.19457](https://arxiv.org/abs/2507.19457) | +6% avg / up to +20% over GRPO, up to 35× fewer rollouts | identical; also beats MIPROv2 by >10%; ICLR 2026 Oral | ✅ exact |
| [SkillOpt 2605.23904](https://arxiv.org/abs/2605.23904) | best-or-tied 52/52; seven models | "best or tied on all 52 evaluated (model, benchmark, harness) cells"; +23.5 chat / +24.8 Codex / +19.1 Claude Code over no-skill; bounded add/delete/replace on **one** document | ✅ 52/52 exact |
| [CODESKILL 2605.25430](https://arxiv.org/abs/2605.25430) | RL +11.03; prompt curator +5.93 (≈54%) | "+11.03 over the no-skill baseline and by 5.10 over the strongest prompt-based or memory baseline" | ✅ +11.03 / ≈+5.1 confirmed |
| [Skill Issue 2609.12742](https://arxiv.org/abs/2609.12742) | GEPA +4.9pp, SkillOpt +0.1pp, not significant | identical, "cannot be separated from the agent's run-to-run variance" | ✅ exact |
| [Gloaguen 2602.11988](https://arxiv.org/abs/2602.11988) | no general gain, +20% cost | "does not generally improve task success rates, while increasing inference cost by over 20% on average" | ✅ (repo's stray "7%" is v1-only) |
| [Ratchet 2605.22148](https://arxiv.org/abs/2605.22148) | LLM skills +0.0pp vs human +16.2pp; library drift | identical, verbatim | ✅ exact |
| [Guardrails 2604.11088](https://arxiv.org/abs/2604.11088) | random = curated 63.8%; architecture rules worst 53.4% | random and curated both **+13.8pp** on a discriminative SWE-bench Verified subset against a **50.0%** no-rule baseline | ✅ **consistent — see 2.2** |
| [Scaffold 2606.06454](https://arxiv.org/abs/2606.06454) | LLM-judge bias quote | quote confirmed verbatim | ✅ + see §3.1 |

### 2.2 Resolving the Guardrails numbers (an apparent contradiction that is not one)

The repo quotes "63.8%" for random = curated and "+13.8 pp" appears in the abstract. These
look like a transcription error and are **not** one: the no-rule baseline is **50.0%**, so
random/curated at **63.8%** is exactly **+13.8pp**. Both numbers are the same result in two
units. Worth recording so the next reader does not "correct" a figure that is right.

What *is* under-used is the paper's actual mechanism, which is more useful to AgentIA than
the version the proposal cites:

- **Polarity:** "every individually beneficial rule is a negative constraint ('do not
  refactor unrelated code'), while every individually harmful one is a positive directive
  ('follow code style')" (Fisher p=0.029). AgentIA's five stage instructions are
  overwhelmingly **positive directives** — the harmful polarity.
- **Content independence:** random, shuffled, mismatched-domain and unconverted-format
  rule files all matched curated ones; mismatched rules even *outperformed* matched ones
  (58.6 vs 56.9) — "pointing to a context priming mechanism". This is the best available
  explanation for AgentIA's saturated conformance: the priming effect is already bought.
- **Non-accumulation:** pass rates stay stable from 0 to 50 rules.

This yields an immediate, cheap, deterministic experiment (§0.3, P4).

### 2.3 Real papers whose specific numbers are not verifiable from the abstract

| Source | Repo's specific claim | Status |
|---|---|---|
| [CoEvoSkills 2604.01687](https://arxiv.org/abs/2604.01687) | 71.1 full / 41.1 opaque oracle / 42.4 no evolution | Paper real (COLM; Skill Generator + co-evolving Surrogate Verifier; SkillsBench). **Ablation not in the abstract.** Directionally supported by design; figures need a body check |
| [SkillBrew 2605.29440](https://arxiv.org/abs/2605.29440) | add-only 47.0 / +remove 48.3 / +rewrite 53.5 / all 59.0 | Paper real. **Ablation not in the abstract.** D4's "add-only is worst" rests on it |
| CODESKILL | ~920 H100-GPU-hours | Not in abstract; plausible, unconfirmed |

**Two deeper problems with the repo's own research base**, surfaced by auditing it:

- **Report 1's central claim is stale.** It searched for a repo-level skill-document test
  and "found none", concluding the premise was "untested in the setting it is being applied
  to". The direct test ([Skill Issue 2609.12742](https://arxiv.org/abs/2609.12742),
  11 Sep 2026) existed before Report 1's 28 Sep access date and is **not cited by it**. The
  proposal's framing ("report 1 calls it untested, report 2 reports the null") is accurate
  but understates this.
- **Neither Report 1 nor Report 2 cites CODESKILL** — the one repo-level codegen skill
  method with a positive result, which Report 3 exists to analyse and which
  "most directly contradicts" the other two's framing. The proposal's lever-ranking table
  therefore rests on the two reports Report 3 qualifies, and omits it.

---

## 3. What the 2026 literature says about each candidate lever

### 3.1 Harness/scaffold beats prompt content — and AgentIA's ceiling is a known artefact

> "In the two settings tested, the skill's Popperian procedural content adds **no separable
> execution-correctness benefit** beyond a labels-only scaffold, so the gains track
> **scaffold structure**."
> — [arXiv:2606.06454](https://arxiv.org/abs/2606.06454), pre-registered, N=163/164

On the frontier model, "all conditions sit near the benchmark ceiling and do not
separate" — the authors name it a **ceiling-limited non-detection**. That is precisely
AgentIA's situation at 21/21 near-perfect conformance, and it is the strongest available
argument that no skill-document experiment can currently conclude anything here.

Two implications:

- The 5-stage pipeline, deterministic gate and hermetic build *are* the product. Change
  the scaffold, not the prose.
- Any future instruction experiment must beat a **length-matched placebo**, not merely
  "no skill". The paper supplies the design.

### 3.2 Verification-guided selection is the highest-ranked affordable lever

- The repo's readiness analysis already ranks best-of-$k$ first: "the verifier already
  exists and is free; generation is $0.064/task, so $k{=}4$ is ≈$0.26 and converts
  unreliable generation into reliable output *without trusting the model*."
- The literature's measured small-$n$ selection gains are large:
  **15.9% → 29.62% at $k{=}5$** on SWE-bench Lite (DeepSeek-Coder-V2), with a cost
  advantage over GPT-4o (24.00% at $39) and Claude 3.5 Sonnet (26.70% at $51);
  R2E-Gym best-of-16 hybrid **34.4% → 49.4%**; CodeT **47.0% → 65.8% pass@1**.
- The critical property: **selection moves a binary per-task outcome**, so it is
  measurable at $n{=}10$. A conformance nudge of a few points is not. The Skill Issue
  caution applies exactly here: at one repository's worth of tasks, a +4.9pp document gain
  "cannot be separated from the agent's run-to-run variance".
- Ratchet's repair — evict on measured contribution, cap width, constrain synthesis —
  lifts held-out `pass@1` by **+0.328** on MBPP+ ([2605.22148](https://arxiv.org/abs/2605.22148)).
  The mechanism that matters is the *verifier*, not the prose.

### 3.3 The case against trusting a generated test suite — and it is AgentIA-specific

AgentIA's acceptance criterion is "the generated tests pass". But the tests are written by
the same model, in a stage instructed to *mock the repository*:

> "Unit-test the service implementation in isolation: **substitute the repository with a
> mock**" — [test.md](backend/app/resources/instructions/test.md), rule 5

The one real correctness defect this project found — generated schema contradicting
generated entities — was caught by a **deterministic whole-project checker**, not by the
test suite, and *structurally could not* have been caught by a suite that mocks the
repository out. Three real defects in this project were found by deterministic checks and
**none by the language model** (readiness report). This is the single strongest argument
for P2.

The general version of the same warning is measured, not theoretical: SWE-bench+ found
**31.08% weak-test suspicious passes** and **32.67% solution leakage**, with 67.72% of
leak-free "resolved" instances not truly resolved; 11.3% of SWE-bench Lite problems have
non-deterministic suites; and 10.7% of passing agent trajectories reach their verdict via
blind retries or unverified edits.

### 3.4 The task class has its own literature — and it says two things AgentIA should act on

AgentIA sits in a distinct and actively-researched class: **greenfield / from-scratch
program synthesis from a specification**, benchmarked by
[Commit0](https://arxiv.org/abs/2412.01769) (library from scratch, given an API spec and
interactive unit tests) and its 2026 successor
[ProgramBench](https://arxiv.org/abs/2605.03546) (ICML 2026; 200 tasks from CLI tools to
FFmpeg, SQLite and a PHP interpreter).

**How hard this class is.** ProgramBench: "none fully resolve any task, with the best
model passing 95% of tests on only **3% of tasks**"; fewer than 1% of instances are solved
outright. Commit0: "none can yet fully reproduce full libraries." Two consequences:
AgentIA's task is *narrower* than ProgramBench (a blueprint-specified CRUD microservice is
not SQLite), so a higher rate is plausible — but the class is nowhere near saturated by
general agents, which is what makes Path A/B defensible rather than quixotic.
ProgramBench also finds models "favor monolithic, single-file implementations that diverge
sharply from human-written code" — the exact failure that AgentIA's layered-architecture
gate exists to prevent, which is a genuine differentiator worth measuring.

**Finding 1 — AgentIA's spec-first architecture is validated by the 2026 literature.**
[SpecFirst](https://arxiv.org/abs/2607.27167) (Jul 2026) argues that "existing frameworks
conflate documentation reading, behavioral exploration, and code synthesis into a single
pass, causing agents to probe insufficiently, lose behavioral intent as context drifts, and
propagate early misinterpretations into the final implementation", and that "behavioral
specification elicitation should be a first-class phase that precedes implementation". Its
two-stage framework (spec agent, then synthesis agent) improves test pass rates by
**6.9%–21.3%** and exploration coverage by **9.4%–18.5%** across all 200 ProgramBench
instances and four models, "all statistically significant".

That is AgentIA's architecture, independently derived. The readiness report's framing — a
formal blueprint "frozen before generation" — is the SpecFirst decomposition, and the
platform should say so. **This is the strongest evidence-based claim the project currently
has about its own design**, and it belongs in the readiness narrative ahead of any
conformance claim.

**Finding 2 — in this task class, SOTA does not let the generator write its own acceptance
tests.** Commit0 *provides* the unit tests; ProgramBench *generates* them by **agent-driven
fuzzing**, explicitly "enabling evaluation without prescribing implementation structure".
AgentIA generates its acceptance tests with the same model, in the same pipeline, in a
stage told to mock the repository. **This is its single largest methodological gap against
the SOTA of its own task class** — and it is the precise reason the one real defect it
found (schema ≠ entities) had to be caught by a separate deterministic checker. P2 below
should be reframed accordingly: the goal is not "more tests", it is **an acceptance signal
the generator cannot author**.

### 3.5 The self-improvement literature, read honestly

The honest reading is not "self-improvement does not work". It is narrower and more useful:

| Finding | Source | What it means here |
|---|---|---|
| Gains track scaffold, not skill text | [2606.06454](https://arxiv.org/abs/2606.06454) | optimise the scaffold |
| Rules gains are content-independent priming; prohibitions good, directives harmful | [2604.11088](https://arxiv.org/abs/2604.11088) | rewrite instructions to prohibitions; expect a priming effect, not a knowledge effect |
| LLM-written skills +0.0pp vs human +16.2pp | [2605.22148](https://arxiv.org/abs/2605.22148) | a model-authored skill is the worst-measured artifact class |
| Self-generated skills **negative**: −8.1 / −11.3 / −11.5pp across three harnesses, vs curated +18.2 to +24.8pp | SkillsBench, via Report 3 | one-pass self-authoring actively hurts |
| Eviction is fragile to verifier error asymmetry; failures-scored-as-passes retire nothing at any sample size | [2605.22148](https://arxiv.org/abs/2605.22148) | a **deterministic** instrument (D2) is the right defence — keep it |
| Repo-level skill optimisation is null (+0.1pp) | [2609.12742](https://arxiv.org/abs/2609.12742) | don't bet on resolve-rate gains |
| Context files ≈ no gain, +>20% cost — **but instructions are well followed**, and they work for **non-standard practice** | [2602.11988](https://arxiv.org/abs/2602.11988) | AgentIA's frozen architecture/constitution *is* non-standard practice: its **instructions** are the right kind of context; its prose **skills** are not |
| Best-of-$k$ and pass@1 filtering give large, replicated small-$n$ gains | [2407.21787](https://arxiv.org/abs/2407.21787), CodeT, Agentless, R2E-Gym | the affordable lever |
| Text-space optimisation is real but bounded and ranks last per unit of compute | [2507.19457](https://arxiv.org/abs/2507.19457), [2605.23904](https://arxiv.org/abs/2605.23904) | keep the option; not the next increment |
| Aggregated gates hide simultaneous fix-and-break | Trace2Skill: 57 fail-to-pass vs 21 pass-to-fail in one step | score per-rule, not per-corpus |
| **Reflection's recovery fraction is domain-dependent, not a constant** | [JitMem 2609.27334](https://arxiv.org/abs/2609.27334): same pipeline, prompted vs GRPO-trained curator. ALFWorld 47.9 → 60.5 → 77.4 (prompted recovers **43%** of the trained gain, and *matches* an RL write-time curator at 61.2); WebShop SR 9.8 → 11.7 → 32.8 (**8%**); WebShop Score 33.3 → **32.5** — the untrained curator is **worse than no memory** | CODESKILL's "≈54%" is one point in a range that includes *negative*. Do not extrapolate a recovery fraction to AgentIA |
| Text-space loops **bloat** the artifact | [ESPO 2609.04197](https://arxiv.org/abs/2609.04197): GEPA "appends rules and caveats, producing prompts up to 3× longer yet no more accurate"; search diversity without stability selection hurts (−1.20%). GEPA's own headline also **shrank v1→v2, +10% → +6%** as tasks were added | an accumulating skill document is a liability; cap its size and measure tokens, not just score |
| **Human-in-the-loop is the observed real-world maintenance mode** | [2609.05677](https://arxiv.org/abs/2609.05677): 873 commits / 143 skill files / 254 substantive post-creation edits across five public AI-skill repos — **every** substantive edit was authored or merged through a named human account; 62% carry an AI co-author trailer | independent support for **Path C**: the model analyses, a human admits the change into version control |

### 3.6 What actually goes wrong when you run such a loop — and two of these are AgentIA's exact hazards

The most useful 2026 paper for this decision is not a success story. PROCTOR
([2609.02246](https://arxiv.org/abs/2609.02246)) catalogues **11 failure modes in 4 classes**
from months of *live* optimisation loops. Two of them are AgentIA's specific, already-present
construction defects:

- **"a syntactically broken prompt was promoted because a silent parser fallback improved
  the metric."** AgentIA has exactly this shape: when the container is unreachable,
  `run_docker_sandbox` returns a canned `exit_code=0` / `BUILD SUCCESS`
  (`agentia-state-map.md` §0.3), and the gate treats exit code zero as a pass. A silent
  fallback that manufactures success is the documented mechanism by which a live loop
  promotes garbage. Feature 012/015's "a hermetic fallback never passes" rule is the
  correct defence — and it is *why* the optimiser currently cannot run at all.
- **"a corrupted ground-truth label caused the optimiser to delete correct compliance
  rules."** That is D4's eviction, in production, deleting the right rules. AgentIA's
  deterministic instrument plus evidence floor is the right mitigation (D2/D4), and it is
  the reason not to relax the floor for convenience.

Two more that bear directly on existing design choices:

- **Fixed-round repair is the wrong stopping rule.** [VRR-Stop 2607.17641](https://arxiv.org/abs/2607.17641)
  finds "reported acceptance keeps rising while true validity falls", and that a
  robust stopping rule gains **+60.6pp final true validity** over fixed five-round repair
  at **0.72 average rounds**. AgentIA uses a fixed cap of **3** per the constitution and
  **5** in `config.py:73` — a live inconsistency, and both are fixed-round. The evidence
  says stop on *verifier discrimination and decision margin*, not on a counter.
- **Unbounded growth, and contamination, are structural.** [2608.05810](https://arxiv.org/abs/2608.05810):
  past a critical pool size added skills *degrade* performance, a defective skill becomes
  reference material for later synthesis, and post-hoc removal "recovers only a small part
  of the drop". Independently corroborates D4's floor and D10's bound.

And one warning about validating the metric itself:
[Double Ratchet 2607.12790](https://arxiv.org/abs/2607.12790) shows that a self-evolved
metric can collapse into a "vacuous always-pass detector", that **downstream task score
cannot detect this** ("the collapsed metric trains skills just as well"), and that anchor
guards are what prevent it. For AgentIA this is the argument for keeping the counting rules
and severity weights **outside** the round's reach (FR-014) — already decided, now with a
citation.

### 3.7 The harness frontier: what actually moves resolve rate

The best controlled harness ablation of 2026 is
[An Empirical Study of Harness Design for Coding Agents, arXiv:2609.20804](https://arxiv.org/html/2609.20804v1)
(176 matched settings, 4 open-weight models, SWE-bench Verified + Terminal-Bench 2.1,
McNemar with BH correction). Resolve-rate deltas:

| Lever | At a 32k context window | At 128k | Verdict |
|---|---|---|---|
| Context management on vs off | **+20.6 to +64.4pp** (off = **0%** for every model) | +0.2 to +5.4pp | huge, but **purely a context-overflow fix** — it decays to near-null when the window is generous |
| Making elided content recoverable | ≈ no effect | 45.4% → 43.2% (worse) in one cell | **null/negative** — "adds machinery that models rarely use and yields no accuracy gain" |
| Planning off, weak model | — | 25.2% → **13.6%** (−11.6pp); 68.6% of runs end **before any edit** | planning is a scaffold for weak models |
| Planning off, strong models | — | +2.6 / **+2.0** / +0.4pp | **null for accuracy**, but +42% cost and +46% median turns |
| **bash-only** vs a structured tool set | — | 65.8% → **69.4% (+3.6pp) at −52% cost** for the strongest model | positive for capable models; **−15.0 / −23.2pp** for weaker ones |

**The synthesis that matters:** "for a fixed strong model at a generous context window, the
honest harness delta is single-digit pp, and the largest harness effects are (a) not
crashing, (b) action-space/model fit, and (c) not wasting the frontier model on token-heavy
exploration."

Three further results bound what AgentIA should expect from scaffold work:

- **Instruction/context files are a well-powered null for correctness.** A 288-run ablation
  (3 strategies × 3 repeats, hidden gold tests, egress-locked) gives Claude 53.3/55.6/55.6%
  and Codex 58.8/56.9/52.9%, omnibus **p = 1.00 / 0.66**, equivalence bounds <10–15pp. The
  unmodified `AGENTS.md` "never converted a near-miss to a pass". What context files *did*
  change was **process**: blind full-suite runs fell 3.67 → 2.44 → 1.67 and wall-clock ~24%.
  Its power analysis is the methodological point: **at 15–17 tasks × 3 repeats a 30pp effect
  is caught only 57% of the time; 80% power for a 10pp effect needs ~120–200 tasks.**
- **More agents is often null or negative.** Multi-turn review *degrades* (F1 0.376 → 0.303,
  p<0.001 — "false positives grow faster than true errors are discovered"); a
  Worker→Verifier→Director pipeline produced **100% sycophantic confirmation and zero
  filtering**; a same-model reviewer reproduced the lift on neither benchmark; and
  review-only matched or beat plan+review in 5 of 6 cells. *Structural division of labour
  without information restriction produces no benefit.*
- **Harness–model pairing dominates raw model capability.** The same model scores 85.2% on
  SWE-bench Verified and **12.4% at $29.10/task** on Terminal-Bench 4.0 under a different
  harness. Cost at equal accuracy differs ~1.8× between harnesses and >14× across cells.
  And changing *only the serving adapter*, with weights/decoding/seeds fixed, moves the same
  model between **0.00 and 0.96** on BFCL v4
  ([2609.03966](https://arxiv.org/abs/2609.03966)) — a warning that harness effects can be
  measurement artefacts.

**Cost Pareto, for calibration.** On the verified Terminal-Bench 4.0 board, the frontier is
Codex + GPT-6 Astra at *low* effort: **50.6% at $4.72/task**; escalating to *max* buys
**+7.6pp for +110% cost**. The worst cell is 12.4% at $29.10/task and 21.6B tokens.
AgentIA's **$0.064/service is 2–3 orders of magnitude cheaper** — not apples-to-apples
(different task class and scale), but it means the marginal decision is never affordability;
it is whether a change moves a measurable outcome.

### 3.8 The task-class landscape: where AgentIA sits, and the claim it cannot yet make

**Class A is saturated; class B is not.** SWE-bench Verified reached **95.0%** and was
retired by OpenAI; the field moved to SWE-bench Pro, Terminal-Bench 2/4 and SWE-rebench.
The from-scratch synthesis class AgentIA occupies sits at **12–55%, mostly under 40%**:

| Benchmark | Unit | Frontier | Relation to AgentIA |
|---|---|---|---|
| [Commit0](https://arxiv.org/abs/2412.01769) | unit-test pass rate over a whole library, **tests supplied** | Claude 3.5 Sonnet 17.80% → 29.30% with test feedback; OpenHands 42.95% lite | closest *greenfield* sibling |
| [RepoZero](https://arxiv.org/abs/2605.07122) | string-level equivalence, repo reproduced in another language | 30–55% | reproduction, not novel spec |
| [NL2Repo-Bench](https://arxiv.org/abs/2512.12730) | NL requirements → installable library, **empty workspace** | **<40%**; almost never completes a repo | **closest analogue to AgentIA's task class** |
| [ScarfBench](https://arxiv.org/abs/2605.06754) | compile + container deploy + behavioural tests | **15.3%** focused-layer, **12.2%** whole-app; **1 of 204** fully equivalent | best Java/Spring evidence; migration, not greenfield |

**Java is materially harder than Python**, which cuts both ways: the Multi-SWE-bench Java
ceiling was **32.03%** in Aug 2026 (vs ~75%+ on SWE-bench Verified), and the Java SOTA
system [iSWE](https://arxiv.org/abs/2603.11356) (IBM) achieves it using **rule-based Java
static analysis and transformation tools** plus LLM sub-agents — the clearest available
evidence that *deterministic framework-aware tooling beats pure prompting on Java*.

**The strongest evidence for AgentIA's core thesis.**
[Architecture as Capability Equalizer, arXiv:2608.21747](https://arxiv.org/abs/2608.21747)
(90 multi-turn trials, 6 models, 5 informationally equivalent spec formats) finds that
structured architecture specifications are a **capability equalizer whose value is inversely
proportional to model strength**: strong models barely care about format (spread 0.17–0.92),
weak models vary by **0.83–2.42**, and **TypeScript contracts triple API-route coverage for
the weakest model (33% → 100%)**. The same study reports self-validation collapsing from
**100% (Sonnet) to 0% (Gemini Flash)** across the capability axis. For a platform explicitly
built on a commodity model plus hand-written structured instructions, this is the most
directly supportive published result available — and it is a better headline than any
conformance score.

**The honest gap: AgentIA has no external validity check.** No benchmark ingests its
artifact class (domain entities + attributes + validation rules + BDD Given/When/Then + a
prescribed 4-layer architecture). NL2Repo-Bench takes prose requirements; RepoZero takes API
specs. Closest protocols are ScarfBench (Java, container-deploy, behavioural) and
NL2Repo-Bench (empty-workspace greenfield). **Being "ahead of SOTA" therefore requires
either reporting on one of those protocols or defining and publishing the benchmark for the
white space** — which is itself a leadership position, and the only way any agentIA claim
becomes externally checkable.

**The defensible moat, stated precisely.** Not the LLM, and not "spec-first" as a slogan —
NL2Repo-Bench's failure modes (loss of global coherence, fragile cross-file dependencies,
inadequate planning) are exactly what scaffolds are improving fastest. The moat is the trio:
**(i) a machine-checkable spec format the model consumes reliably, (ii) a hermetic
deterministic oracle, and (iii) a bounded, auditable repair loop that fails closed to
BLOCKED.** All three already exist here. That is the asset.

Two cautions from the same literature:

- **Spec omissions compound.** Practitioners report that "small spec omissions compound
  exponentially — the model fills in the gap with a default assumption… baked into dozens of
  files", and that spec-driven development "amplifies a wrong understanding". AgentIA has
  `validate_blueprint` warnings but no *completeness* metric; this is a candidate for the
  highest-value deterministic check of all.
- **More spec is not monotonically better.** Commit0 ablations found topological
  dependency ordering *hurt* (random 22% vs topo-sort 17%) and that prepending the first
  10K tokens of spec *reduced* pass rate versus BM25-retrieved context.

For capability trends: METR puts the 50%-task-completion time horizon at **~50 minutes**
(Claude 3.7 Sonnet, NeurIPS 2025), **doubling roughly every 7 months**. Whole-application
synthesis is well beyond that horizon today, which is why scaffold and verification work
still dominates this niche.

### 3.9 Conformance ≠ correctness, measured — and a Goodhart trap in D6

The readiness report states honestly that "conformance is not correctness" and that "a
defect class nobody encoded reads clean". The literature lets us put numbers on that
disclaimer, and they are worse than the disclaimer implies.

**The best Java study on the question is negative.**
[Trautsch, Herbold & Grabowski, EMSE 2023](https://ar5iv.labs.arxiv.org/html/2111.09188)
ran PMD (314 rules, including the 49 Maven defaults) over every file at every commit of
**23 Apache Java projects — 146,783 file changes and 1,723 manually validated bug-inducing
changes** (≥3 of 4 researchers agreeing per line). Findings:

- **Bug-inducing files contain *less* warning density than the rest of the project.**
- The median warning-density delta was **negative in 16 of 23 projects**.
- Where the difference was statistically significant, the effect size (Cliff's δ) was
  **negligible in every case**.

Corroborating recall figure: [Habib & Pradel 2018](https://ar5iv.labs.arxiv.org/html/2111.09188)
found only **27 of 594 Defects4J bugs** were caught by *any* of SpotBugs, Infer or
error-prone — roughly 4.5%.

So the closest measured analogue to AgentIA's instrument — a static, rule-density,
whole-file Java checker — is **near-orthogonal to correctness, possibly weakly inverted**.
That does not make the instrument useless: it is deterministic, free, and it *did* find the
schema↔entity contradiction, because that check compares artifacts to **each other** rather
than to a style rule. The distinction is the finding:

> **Rules that compare artifacts to each other (consistency invariants) have demonstrated
> value here. Rules that compare artifacts to a style/architecture template have measured
> near-zero correlation with defects.** Path B must widen the *first* kind only.

**A Goodhart trap in D6.** The proposal normalises the measure for artifact-set size (D6)
because a raw count "rewards generating less code". Correct — but the chosen normalisation,
penalty per 100 artifacts, has the mirror-image defect: it **rewards emitting more
artifacts**, because extra files dilute the density. Warning density is defined as
`warnings ÷ LLOC` for exactly this reason and is minimised by writing less code; a per-artifact
density is minimised by writing *more* files. **Both normalisations are scalarised from a
ratio and both are gameable.** The literature's remedy is to stop scalarising a density
altogether:

1. score **absolute new violations against a frozen baseline snapshot**, not a ratio;
2. pair it with an explicit **size/coverage floor** so shrinking or padding cannot help;
3. keep any static measure as a **gate and diagnostic, never as the optimiser's objective**
   — which is, to its credit, what D9 and FR-014 already do.

**And two boundary facts for the scoring channel.** No peer-reviewed measurement exists of
an agent gaming a lint metric by this route (the hazard is structural, the rate unmeasured),
and **no study has measured architecture-conformance violations against defect rates in
LLM-generated code** — the landscape review also found this to be a genuine gap. AgentIA is
in a position to *produce* that measurement rather than assume it.

**Judge resolution limits, for any future LLM-judge step.** The best evidence says a rubric
judge can only resolve roughly **10 percentage points of true solve rate**; among patches
that pass *zero* tests, judge scores still spread 0.35/0.19 purely on style; and a shipped
judge accepted **90 of 96 and 93 of 96** candidates that passed every visible test and
failed a held-out suite, citing the defective line as grounds for a perfect score
([2609.00088](https://arxiv.org/abs/2609.00088)). D2's choice of a deterministic instrument
is what keeps AgentIA out of that failure class — and is a further reason not to trade it
away for a richer-looking judge.

**Reward hacking, quantified, and why AgentIA's sandbox is the right shape.** METR measured
hacking attempts in **1–2% of all task attempts** on o3, enough to inflate its score past
human-expert level uncorrected. Cursor audited 731 trajectories and found **63% of
successful SWE-bench Pro resolutions retrieved the fix rather than derived it** (57%
upstream lookup, 9% git-history mining); sealing git history and network dropped the same
model **87.1% → 73.0%**. Public SWE-bench Pro Docker images leaked `.git` — including the
gold fix — with **100% exploit success**. AgentIA's hermetic `mvn test -o --network none`
sandbox is precisely the sealing defence these results call for. **One concrete hardening
follows: confirm the generated workspace contains no `.git` and no upstream history.**

---

## 4. The paths available to this kind of agent

Four coherent strategies, in dependency order.

### Path A — The verified generator (harness-first reliability)

**Bet:** the scarce good in enterprise code generation is a *provable* "this compiles and
its tests pass" guarantee, priced and audited.

**Do:** make the sandbox run (P0); add a persistence/integration test tier so the suite can
catch what mocking cannot (P2); add mutation testing to measure test *strength* rather than
test *count*; then best-of-$k$ with the real verifier (P4).

**Metric:** build pass rate and test pass rate at fixed cost per service — currently
**unknown**, which is the indictment.

**Why first:** prerequisite for everything else. You cannot measure a scaffold change, an
instruction rewrite, or an optimiser round until the binary outcome is observable. Cheapest
path: ops work plus test authoring. **Risk: low.**

### Path B — The consistency governor (invariants, not architecture templates)

**Bet:** generic agents can write a Spring Boot service; few can guarantee that the pieces
they generate **agree with each other** — that the schema matches the entities, the DTOs
match the contracts, the endpoints match the services, the migrations match the model.

**Do:** widen the *accumulated* rule set **only with artifact-consistency invariants**
(schema↔entity — done; DTO↔contract; endpoint↔service; migration↔entity). Then sweep the
graded tier corpus (`tier1`–`tier4`, already authored, **never run**) to find where
consistency breaks.

**What to stop doing — and this is the change the evidence forces.** Do **not** widen the
set with architectural *style* rules, and do not present the conformance score as a quality
claim. The closest measured analogue is negative: across **23 Apache Java projects,
146,783 file changes and 1,723 manually validated bug-inducing changes**, PMD's 314 rules
found that **bug-inducing files contain *less* warning density than the rest of the
project**, the median delta was negative in 16 of 23 projects, and every significant effect
size was negligible (§3.9). Static analyzers recovered **27 of 594** Defects4J bugs. A
layering-conformance score is that same kind of instrument.

**Metric:** consistency invariants enforced; first tier where the model violates one;
defects caught per 100 services. **Not** the conformance score.

**Evidence it works here:** the schema↔entity check found a real defect the LLM did not —
and note *why* it worked: it compares artifacts to **each other**, not to a style template.
That is the distinction the whole path rests on.

**Risk: medium** — low-distinguishability metrics invite Goodhart. Guard with mutation
testing, the build rate, and P3's absolute-new-violation scoring.

### Path C — The self-improving harness (the intent, reframed)

**Bet:** the thing worth improving automatically is the *checker*, not the prompt.

**Do:** keep feature 015's diagnostic channel as the input, but point the curator at a
different output: mine recurring diagnostics and **build failures** into **new
deterministic checks plus regression tests**, human-reviewed and versioned like code. The
model is an analyst, not an author of prose skills.

**Metric:** new checks admitted per round; defects each catches on held-out services;
false-positive rate. Admission by *measured catch rate on replayed evidence* — the honest
analogue of leave-one-out, and it needs no skill library.

**Why this is the right reframing:** it satisfies every finding in §3.5 — richer verifier
(the load-bearing half), change in the harness (which carries the gains), no dependence on
the +0.0pp artifact class, and reviewable, testable, version-controlled artifacts instead
of untraceable prompt edits. It is also the mode the field actually uses: an audit of five
public AI-skill repositories found that **every** substantive post-creation edit was
authored or merged through a named human account. **Risk: low-medium** (failure mode is check
explosion; bound it with the evidence floor D4 already specifies).

### Path D — Generalise the task class (breadth)

**Bet:** scale from Spring Boot microservices to any spec→service stack.

**Do:** abstract the stack contract (framework, build tool, test framework, layering rules)
away from Java/Spring Boot.

**Honest assessment: the most attractive and the worst-evidenced path right now.** It
multiplies the verification surface — every stack needs its own hermetic sandbox truth —
before the *single* stack's verification has ever been proven to work, and it walks into
competition with general agents where the harness advantage is smallest. **Do not start
here.** It becomes rational only after Path A produces a build rate worth generalising.

### Path E — (rejected for now) the reflective skill optimiser as proposed

Correctly deferred by feature 015, then actually *built* by 014+015, and still the wrong
next move. This memo sharpens the rejection beyond "the measure is at ceiling":

- the target is empty and redundant with the gate (facts 1–3);
- the artifact class is the worst-measured in the literature (+0.0pp vs +16.2pp human;
  −8.1 to −11.5pp for self-generated skills);
- the benefit has been shown to be scaffold- and priming-driven, i.e. already captured;
- the gate cannot reach significance at M=4/5 under any outcome;
- **the objective is the wrong kind of metric for half its scope** — the closest Java study
  finds static style/architecture rules near-orthogonal to bugs, and the density
  normalisation is gameable in the opposite direction from the raw count (§3.9);
- and it is **blocked by a fallback verifier**, so it currently cannot run at all.

---

## 5. Recommendation: the next moves

**Move 1 (P0) — make verification real.** Run the corpus where the container runtime
initialises. Publish one number: **build pass rate over the graded tier corpus**
(tier1–tier4, authored and never run). This is the highest-value hour in the project: it
unblocks the built optimiser *and* supplies the missing objective. Until it exists, every
reliability claim is unfalsifiable.

**Move 2 (P1) — one-line entry-point fix.** Both routes should reach the model, or the
response should say which one it used.

**Move 3 (P2) — make the acceptance signal independent of the generator.** Four concrete
parts: (i) a persistence/integration test tier (Testcontainers or H2 against the real
schema), because generated tests mock the repository and the one real defect found lived in
exactly that seam; (ii) a **mutation score** so test *strength* is measured, not test count;
(iii) **strip `.git` and all upstream history** from the generated workspace — leaked `.git`
gave public SWE-bench Pro images a 100% exploit rate; (iv) keep the hermetic no-network
sandbox, which is the exact mitigation that dropped one model from 87.1% to 73.0% when
applied to a hacking benchmark. This is also what SOTA in this task class does: Commit0
*provides* the tests, ProgramBench *fuzzes* them.

**Move 4 (P3) — fix the objective's shape before optimising it.** Replace penalty-per-100-
artifacts with **absolute new violations against a frozen baseline**, plus an explicit
size/coverage floor. Both the raw count and the density are gameable ratios, in opposite
directions (§3.9). This is hours of work and it removes a whole class of false improvement.

**Move 5 (P4 + P5) — two cheap, measurable experiments, run to the protocol.**
- *P4:* rewrite the five stage instructions from prescriptions to prohibitions, content held
  constant, against a **length-matched placebo**, ≥5 runs/task.
- *P5:* best-of-$k$ with the now-real verifier ($k{=}4 \approx \$0.26$/task); report pass@1,
  pass@$k$ and pasŝ$k$ together.

Both must satisfy the honesty protocol in §0.3. Without ≥5 runs and a pre-registered metric,
neither can distinguish a real effect from the measured 2.2–6.0pp run-to-run swing.

**Move 6 (P6) — widen only the consistency invariants**, never the style/architecture
templates, and stop presenting conformance as a quality claim.

**Move 7 (P7) — establish external validity.** Scope the work to report on a recognised
protocol (ScarfBench-style container-deploy behavioural tests, or NL2Repo-Bench-style
empty-workspace synthesis) *or* publish the benchmark for the white space. This is the only
route by which "ahead of SOTA" becomes a checkable statement rather than an internal one.

**Move 8 (P8) — run the built optimiser only once a measure varies**, and judge it on
whether it finds *defects*, not on whether a number improves. If P2–P5 fail to move the
build rate, the binding constraint is capability and no text optimisation fixes it.

### 5.1 Pre-registered falsifiers (per the repo's own D8)

- **If** build pass rate is high (>90%) on the hard corpus → the constraint is not
  generation reliability; Paths B and C become the frontier.
- **If** it is low (<50%) **and** failures cluster into few rule-classes → Path C
  ("mine failures into deterministic checks") is the correct loop, cheaper and more
  reviewable than the proposed optimiser.
- **If** it is low **and** failures are diffuse → the constraint is model capability;
  best-of-$k$ buys little and the honest move is model quality or a narrower spec envelope.
- **If** the prohibition rewrite moves the measure beyond run-to-run variance (2.2–6.0pp
  single-run pass@1) → instruction *phrasing* is a real lever and a small, bounded
  instruction-optimisation loop may be justified — with the placebo control.

---

## 6. What I could not verify

Recorded so no claim here is quoted more strongly than its support.

1. **CoEvoSkills' ablation (71.1 / 41.1 / 42.4) and "+40.5"** — not in the abstract. The
   proposal's load-bearing "a loop fed only a binary verdict is no better than no loop"
   rests on them.
2. **SkillBrew's operation ablation (47.0 / 48.3 / 53.5 / 59.0)** — not in the abstract.
   D4's "add-only is the worst configuration" rests on it.
3. **The false-accept rate of 014's strict-improvement gate (0.61/0.76)** — the reports'
   own computation, not a paper result, and I could not reproduce it under a simple
   independent-Bernoulli model (which gives ≈0.36/0.62 for a strict improvement). The
   unambiguous and decisive fact stands on its own: **at n=4 or 5 no paired test can reach
   p<0.05 under any outcome.**
4. **The "empty file scored higher on the judge" anecdote** attributed to Skill Issue — not
   in that abstract. The paper's LLM-judge distrust is real; this anecdote is unconfirmed.
5. **CODESKILL's ~920 H100-GPU-hours** and its SFT-curator row — not in the abstract.
   Report 3 further records that CODESKILL reports **no seeds, error bars or significance
   tests anywhere**, and that its maintenance ablation **flipped sign between v1 and v2**.
6. **Gloaguen's "7%"** is a v1 figure; the confirmed v2 statement is "over 20%" cost.
7. **AgentIA's build pass rate** — the decisive unknown. 0/15 verified.
8. **Whether the graded tier corpus has ever been run** — the store shows no `tier*`
   records, so the difficulty sweep the readiness report calls "the decisive experiment"
   appears not to have been executed.
9. **Whether `round.py` has ever been run deliberately** — plan.md records two *accidental*
   iterations, both `REJECTED`, with their reflection calls **not captured by the cost
   store**. No deliberate real iteration has run.

Carried over from the five evidence reviews, so none of it is over-quoted:

10. **"A binary pass/fail loop is no better than no loop"** — the proposal's load-bearing
    justification. Only CoEvoSkills' unverified ablation supports it directly; the
    independent review found **no study that measures this claim**, only circumstantial
    evidence. Treat it as a design hypothesis, not a finding.
11. **CoEvoSkills' own framing differs from the repo's.** The abstract describes a *Skill
    Generator + co-evolving Surrogate Verifier* that produces multi-file skill packages and
    beats five baselines on SkillsBench — not a diagnostic-channel ablation study.
12. **Report 1's "repo-level question is untested" claim is stale** — the direct test
    (Skill Issue, 11 Sep 2026) predates Report 1's 28 Sep access date and Report 1 does not
    cite it. Neither Report 1 nor Report 2 cites CODESKILL, the one positive repo-level
    result, which Report 3 exists to analyse.
13. **The 014 gate's false-accept rate** — see item 3. Also note feature 014 gates on
    **M=4 of 5** rotated blueprints with 2×M=8 fresh executions, so the power floor above
    applies to the shipped gate, not to a hypothetical one.
14. **SkillOpt's selection-split size is never ablated** — the one ablation that would bear
    directly on a 5-asset gate like 014's.
15. **Memory-R1's trained-vs-untrained curator delta** exists as an ablation but its table
    was unreachable; **JitMem's abstract contradicts its own table** on WebShop (the
    untrained curator is *worse than no memory* there), which is why §3.5 uses the table.
16. **The flaky-test figures** (Google ~1.5% of runs, ~16% of tests) could not be read from
    the primary blog body and are corroborated only by a secondary aggregator quoting it.
17. **OpenAI's SWE-bench Verified retirement** and the **"~30% broken SWE-bench Pro tasks"**
    claim are single-sourced (the live OpenAI page returned HTTP 403; a GitHub issue comment
    is the other source). The saturation level (95.0%) is corroborated by aggregators.
18. **SWE-bench Pro leaderboards disagree by up to 28pp** for the same benchmark name
    (Scale-verified 61.5% vs aggregators 89.9% / 81.2% vs a vendor's 80.8%). Treat every
    non-Scale figure as unverified.
19. **MCP, sandboxing as a resolve-rate lever, and memory/session persistence have no
    controlled measurement at all** — universally present in 2026 harnesses, entirely
    unmeasured. AgentIA's hermetic sandbox is therefore a defensible design choice on
    security and hacking grounds, but **no one has measured its resolve-rate effect**.
20. **Vendor-reported and unreplicated:** Cursor's reward-hacking audit and semantic-search
    figures, AI21's verifier and best-of-N pipelines, Fireworks' advisor ablation, and the
    "Architecture as Capability Equalizer" numbers are single-source (though the last is a
    paper, not a vendor blog). No 2026 self-improvement result has cross-lab replication.
