# SkillOpt for a Code-Generating Agent Under Zero Compute — Deep Dive

**Date:** 2026-09-28
**Predecessor (read first, not repeated):** [agent-skill-optimization-sota.md](agent-skill-optimization-sota.md)
**System under design:** [specs/014-skillopt-compact/spec.md](../specs/014-skillopt-compact/spec.md), [plan.md](../specs/014-skillopt-compact/plan.md)
**Question:** *"Can SkillOpt (text-space skill-document optimization, arXiv:2605.23904) be extended to improve a code-generating agent, given zero compute?"*
**Answer shape:** CLOSED / OPEN / CONDITIONALLY OPEN, with conditions enumerated (§12).

**Method.** Primary sources preferred: arXiv HTML full text, author repos, vendor docs. Where a full text exceeded the fetch limit I say so and tag the claim accordingly. Every claim carries **PRIMARY** (I read it in the owning source) / **SECONDARY** (aggregator or third-party report) / **UNVERIFIED**.

**Scope note on "now".** The parent said treat *mid-2026* as now. The predecessor used an access date of 2026-09-28, so I used the same date and included sources up to it. One source is decisive and postdates mid-2026 — **arXiv:2609.12742 (11 Sep 2026)**, the first study to run GEPA *and* SkillOpt on repository-level codegen — and I say so wherever it carries the argument. Excluding it would have produced a materially wrong verdict.

---

## 0. What is new in this dive (the six things that changed the picture)

1. **There is now a direct test of skill-document optimization for codegen, and it is a near-null for SkillOpt specifically.** "Skill Issue" ([arXiv:2609.12742](https://arxiv.org/abs/2609.12742)) optimizes one `.md` SKILL per repository on three Kotlin repos: *GEPA* documents raise a seed-relative score by **+4.9 pp**; *SkillOpt* documents by **+0.1 pp**. Neither is statistically significant. **PRIMARY.** §2.3, §6.
2. **The prior report's "one positive codegen datapoint" is one of two, and the other one is much bigger and is about *skills*, not kernels.** The GEPA team's `gskill` pipeline lifts Mini-SWE-Agent (gpt-5-mini) from **24% → 93%** resolve rate on `bleve` and **55% → 82%** on `jinja`, under **300 rollouts**, with transfer to Claude Code. **PRIMARY** ([gepa-ai/gepa blog, 2026-02-18](https://github.com/gepa-ai/gepa/blob/234970ac898b1c22a9012a15c72948f498994ebd/docs/docs/blog/posts/2026-02-18-automatically-learning-skills-for-coding-agents/index.md)). §2.2.
3. **Guardrails Beat Guidance does test *procedural rules about how to write code* — and the closest category to the platform's seed skill scores worst.** Tool/process rules 63.8%, **architecture rules 53.4%** (vs a 50.0% no-rule baseline), a 10.4 pp spread that does not reach significance. The platform's seed skill is *controller → service → repository → model layering*, i.e. an architecture rule. **PRIMARY.** §1.3.
4. **A second 2026 negative for codegen "skills" is pre-registered and calibrated:** "Scaffold, Not Vocabulary?" ablates a code-generation skill against a length-matched placebo and a **labels-only scaffold**, and finds the skill's procedural content adds **no separable execution-correctness benefit** — the gain tracks scaffold structure. **PRIMARY (abstract; full text not read).** §6.
5. **The strongest zero-compute lever is not the skill document, it is the free verifier.** With unit-test selection, 5 samples of a cheap model (DeepSeek-Coder-V2) resolve **29.62%** of SWE-bench Lite vs **15.9%** pass@1, at **1× cost** where one GPT-4o sample costs 3.6× and resolves 24.00%. **PRIMARY** ([arXiv:2407.21787](https://ar5iv.labs.arxiv.org/html/2407.21787)). §4.
6. **The platform already owns a deterministic conformance instrument, which is the only instrument that can possibly work at 5 assets.** `security_service.scan_architecture_compliance` + `test_analysis_service.analyze_code_compliance`, merged by [compliance.py](../backend/app/orchestrator/stages/compliance.py) into a graded score `100 − (critical·30 + high·15 + medium·5 + low·2)`. **PRIMARY (repo).** §7.

---

## 1. The exact boundary of the null results

### 1.1 Gloaguen et al. — and a version discrepancy the prior report did not record

**PRIMARY.** The predecessor quoted the **v2** abstract ([arXiv:2602.11988v2](https://arxiv.org/html/2602.11988v2)):

> *"we find that providing context files does not generally improve task success rates, while increasing inference cost by over 20% on average. This observation holds across different LLMs, coding agents, and for both LLM-generated and developer-committed context files. Specifically, we find that while instructions in the context files are well followed by coding agents, repository overviews, although popular and recommended by model providers, are not helpful. We conclude that while context files are useful for specifying non-standard coding practices, any attempts to improve performance should be rigorously evaluated before deployment."*

I also read the **v1 full text** via the ar5iv mirror ([ar5iv 2602.11988](https://ar5iv.labs.arxiv.org/html/2602.11988)) — and this matters, because the two versions report **different numbers and a different framing**:

| | v1 (ar5iv; "AGENTbench") | v2 (arXiv HTML; "CTXbench") |
|---|---|---|
| LLM-generated files | **−3%** success on average | "does not generally improve"; drops in 5 of 8 settings |
| Developer files | **+4%** on average | "outperform the LLM-generated ones by a significant margin of **7%** on average" |
| SWE-bench Lite | −0.5% success, **+20% cost** | same cost claim |
| Dataset | 138 instances / 12 repos | 138 instances / 12 repos, 300-task SWE-bench Lite |

**PRIMARY** for both rows; the v1 numbers are quotes from the ar5iv full text ("*developer-provided files only marginally improve performance compared to omitting them entirely (an increase of 4% on average), while LLM-generated context files have a small negative effect on agent performance (a decrease of 3% on average)*"). The v2 "7%" is a quote from its introduction. **Anyone citing "Gloaguen says +4%" is citing v1; anyone citing "Gloaguen says context files don't generally help" is citing v2.** Both are the same paper, different revisions. Treat the effect as small, sign-unstable, and cost-negative.

**What was actually in the files.** v1 §3.2 Table 1 gives the statistics: mean **641.0 words**, min 24, max **2003**, mean **9.7 sections**. Content is headline-classified by the authors as *repository overview* + *developer tooling* + *style guides and design patterns*. So **yes — style guides and design patterns were among the tested content**, but as *part of a mixed document*, not as an isolated procedural-rule condition. That distinction is the whole of §1.4.

**Effect sizes and statistics, quoted (v1, ar5iv):**

> *"LLM-generated context files cause performance drops in 5 out of 8 settings … the average resolution rate is reduced by 0.5% and 2% on average on SWE-bench Lite and AGENTbench, respectively. Meanwhile, the context files increase the # steps in every setting on average by 2.45 and 3.92 steps, respectively, which leads to a cost increase of 20% and 23% on average."*

> *"We observe that the developer-provided context files outperform the LLM-generated ones for all four agents … and improve the performance compared to no context files for all agents but Claude Code."*

> *"developer-provided context files also increase the average number of steps and costs required to solve the task, on average by 3.34 steps and at most 19%."*

**The one sub-condition with a real positive gain — and what defines it (this is the answer to the parent's "any sub-condition?" question):**

> *"we manually remove all documentation (files ending with .md, example code, and the folder docs/) after generating the context file, and before evaluating the coding agents … In this setting, where context files are the only source of documentation available, LLM-generated context files not only consistently improve performance by **2.7%** on average, but also outperform developer-written documentation."*

**PRIMARY.** This is the cleanest statement in the literature of the knowledge hypothesis: *the file helps exactly when it is the only carrier of the information*. It is small (+2.7%), it is a single condition, and it is confounded with removing documentation that might otherwise mislead the agent. But it is a real, directional positive.

**The instruction-following numbers, quoted:**

> *"uv is used 1.6 times per instance on average when mentioned in the context files, compared to fewer than 0.01 times when it is not mentioned, and repository-specific tools are used 2.5 times per instance on average when mentioned, compared to fewer than 0.05 times when they are not mentioned."*

> *"this result implies that the absence of improvements with context files is not due to a lack of instruction-following."*

**PRIMARY.** Reasoning-token cost: **+22%** (GPT-5.2) and **+14%** (GPT-5.1 mini) on SWE-bench Lite; +20% / +2% for human files — i.e. compliance is purchased with thinking tokens, not with correctness.

**What v2 adds that I could only partially verify:** the v2 HTML table of contents contains two headings that are the most on-point claims in the paper for this question:

- §4.4 *"Neither context file length nor specific instruction categories have a strong effect on performance"*
- Appendix B *"No specific categories in LLM-generated context files help significantly"*

**PRIMARY for the headings** (I read them in the v2 HTML TOC); **UNVERIFIED for the body** — the v2 full text exceeded the fetch limit at §4.1, the PDF is not fetchable in this environment, and the r.jina.ai proxy returned an SVG for this URL. **I therefore cannot report the instruction categories tested, the per-category coefficients, or the v2 statistical appendix (A.5).** The predecessor's claim that instructions are followed while task success does not move is confirmed; the stronger claim that *specific instruction categories were tested and none helped* is **supported by section headings only**.

### 1.2 The two-agent ablation (Khatri, arXiv:2607.27250) — the tightest design and the tightest null

**PRIMARY** — read in full ([arxiv.org/html/2607.27250v1](https://arxiv.org/html/2607.27250v1)). Verified design:

- 2 agents (Claude Code / `claude-sonnet-4-6`; Codex CLI / `gpt-5.5`), **17 tasks for Codex, 15 for Claude**, from 3 repositories (pdm, firebase-admin-python, opshin), **3 repeats**, **288 evaluated cells** (291 runs minus 3 invalid).
- Three strategies, and — critically — **in every condition the workspace `AGENTS.md` is removed**, so the injection channel is the only channel: `none`, `always_on` (full file in system prompt), `selective` (topic wiki + retrieval hint).
- Gold-test (Tier-C) evaluation; git history pruned so the agent cannot read the solution.

Results, quoted:

| Strategy | Claude (15 tasks) | Codex (17 tasks) |
|---|---|---|
| none | 53.3% (24/45) | 58.8% (30/51) |
| always_on | 55.6% (25/45) | 56.9% (29/51) |
| selective | 55.6% (25/45) | 52.9% (27/51) |
| Omnibus p | 1.000 | 0.66 |

> *"For Claude, all pairwise strategy differences are ≤2.3pp. For Codex, the largest difference is 5.9pp (none vs. selective) … The omnibus permutation test shows no detectable strategy effect (p=1.00 Claude; p=0.66 Codex … this test is intrinsically low-power here)."*

> *"Descriptive equivalence testing (TOST on the task-clustered bootstrap) bounds every pairwise strategy difference to <10pp for Claude and <15pp for Codex."*

**The dynamic-range subset is the sub-condition that matters:**

> *"on 4 Codex-borderline tasks (17–67% baseline pass rate), none achieves 58% vs. always_on 42% and selective 42%—context injection does not help even where the design has power to detect an effect."*

**The mechanism, quoted:** *"agents fail on implementation skill—feature design, pattern selection, exact wiring—not missing repository knowledge that a context file could supply; a manipulation probe confirms the real AGENTS.md never converts a near-miss to a pass on either agent."*

**Its own power analysis, quoted:** *"MDE at n=17, reps=3: even a large Δ=30pp effect is caught only 57% of the time"*; *"Detecting Δ=10pp at 80% power requires ~120–200 tasks."* **This is the single most useful number for §7** — it is a *paired, repeated* design and it still needs 120–200 clusters.

**And a concrete instance of a plausible real effect that 5 units cannot certify** (the platform's exact problem in miniature): on opshin, Claude's wall-clock was **2689 s → 2066 s → 2032 s** across none/always_on/selective (−24%), with *"faster-with-context on 4/5 tasks, sign-flip p=0.125, underpowered at n=5"*, plus a dose-ordered mechanism (blind full-suite pytest runs per cell **3.67 → 2.44 → 1.67**). The authors report it as *exploratory*, *"not fold it into the Holm-corrected confirmatory tests"*. **PRIMARY.** A ~24% efficiency effect, a monotone dose-response, n=5, p=0.125. That is what a 5-asset experiment looks like when a real effect is present.

### 1.3 Guardrails Beat Guidance — procedural rules about *how to write code* were tested, and architecture rules scored worst

**PRIMARY** — read the full experimental sections ([arxiv.org/html/2604.11088v2](https://arxiv.org/html/2604.11088v2)).

- 679 rule files, **25,532 rules** scraped from GitHub, classified into six categories. Distribution: *project-specific 64.9%, behavior/persona 10.8%, tool/process 8.9%, **code style 6.5%, architecture 5.8%**, safety 3.0%*. Experiments use the five transferable categories (i.e. **including code style and architecture**).
- 500 SWE-bench Verified tasks screened with 3 baseline reps (**1,500 screening runs**) → **58 discriminative tasks** (solved 1–2 of 3). 3,544 experiment runs + screening ≈ **>5,000 runs, ~$2,000**.
- **Experiment 1 (8 conditions × 58 tasks = 464 runs):** baseline 50.0%; all seven rule conditions **+6.9–13.8 pp**; **"no condition is significantly different from any other (Cochran's Q=4.70, p=0.697)"**; closest pairwise contrast is random vs baseline **p=0.077**; **random rules tie curated rules at 63.8%**; mismatched (wrong-domain) rules **slightly outperform** matched (58.6% vs 56.9%); shuffling sentences changes nothing (56.9% vs 60.3%). *"No individual McNemar comparison reaches p<0.05 at n=58; the headline rests on direction, not magnitude."*
- **Experiment 3 (rule types, 5 conditions × 58 = 290 runs): the direct answer to the parent's question.**

> *"Tool/process rules (state-dependent …) achieve the highest pass rate (63.8%), while **architecture rules (state-independent) score lowest (53.4%)**, a 10.4pp spread … The spread does not reach statistical significance at n=58, so we frame this as directional rather than confirmatory evidence."*

Code style (6.5% of the corpus) is a transferable category in the taxonomy but is reported within the five-type comparison; architecture is the explicitly *worst* type. **So: procedural rules about how to write code were tested, as a distinct condition, and the architecture/structural family is the weakest of the five.** The platform's seed skill (layering) is that family.

- **Experiment 4 (18 curated rules, 35 tasks):** 3 *shaping* (removal hurts), 4 *distorting* (removal helps), 11 inert. **All 3 shaping rules are negative constraints; all 4 distorting rules are positive directives** (Fisher exact 2×2 **p=0.029**). Threshold sensitivity: identical partition at 3 pp and 5 pp (p=0.029), weakens at 7 pp (p=0.067), dissolves at 10 pp (p=0.25); threshold-free Mann–Whitney **p≈0.13**. The one individually significant rule, *"do not refactor unrelated code"*, shows a **20 pp drop when removed (McNemar p=0.016)** but *"would not survive a strict multiple-comparison correction across all 18 rules."*
- **Ensemble resilience:** pass rates stay 59–67% from 0 to 50 rules; **50 rules 66.7% vs 0 rules 60.3%**; Cochran's Q=22.12, p=0.227; *"the dominant source of variance is which rules are sampled (seed variance up to 17pp at count=1), not how many."*
- **The authors' own implication for an optimizer, quoted:** *"This implies that automated rule optimizers should target structural properties rather than semantic content."*

**Synthesis for §1.** The three papers do not say "documents are inert". They say:

| Channel | Measured effect | Status |
|---|---|---|
| Presence of *any* structured rule file | +6.9–13.8 pp over a 50.0% baseline on *discriminative* tasks | Real in direction, not significant per-condition, **content-independent** |
| Repository overviews | no reduction in file-discovery steps | Null (Gloaguen v1 §4.2; two-agent §4.1) |
| Architecture / structural rules ("use the repository pattern", layering) | **53.4%**, lowest of five types | Directional **negative** vs tool/process |
| Code style rules (positive directives) | every individually *distorting* rule is of this kind | Negative |
| Negative constraints ("do not X") | every individually *shaping* rule is of this kind; −20 pp when removed | The only individually beneficial class |
| Tool/process / state-dependent rules ("if tests fail, find the root cause") | **63.8%**, highest | Best-supported class |
| Context file when it is the *only* documentation | **+2.7%** | Positive (small) |
| Instructions followed? | uv 1.6 calls vs <0.01; tools 2.5 vs <0.05 | **Yes, robustly** |

### 1.4 What was never tested (the exact boundary the parent asked for)

Across Gloaguen v2 (as far as I could read it), the two-agent ablation, and Guardrails:

1. **A skill document optimized *against a pass-rate objective* for a *house-standard* generator, with the document as the only variable, on a *fixed, pre-registered* asset set.** Not tested anywhere before arXiv:2609.12742 (§2.3).
2. **Architecture/layering rules as a standalone condition with adequate power.** Guardrails has the type (n=58, 10 rules, directional only); Gloaguen has style/pattern *inside* a mixed 641-word document; the two-agent study has no architecture-only arm. **Nobody has run a powered architecture-rule-only experiment.**
3. **Conformance to a named house standard as the outcome.** Gloaguen v1 §5 says so itself: *"We evaluate the impact of context files on task resolution rate. However, there are many other relevant aspects of coding agents, such as code efficiency and security."* **SECONDARY** (this quote is from a third-party analysis of v1, [agent-engineering-toolkit analysis](https://raw.githubusercontent.com/rodrigorjsf/agent-engineering-toolkit/refs/heads/development/docs/analysis/analysis-evaluating-agents-paper.md), which quotes the paper; I did not locate it in the sections I fetched). The two-agent paper measures tool calls, wall-clock, tokens — not conformance to a written standard.
4. **A non-Python, less training-saturated language.** Gloaguen's own limitation (v1): *"The current evaluation is focused heavily on Python … much detailed knowledge about tooling, dependencies, and other repository specifics might be present in the models' parametric knowledge, nullifying the effect of context files."* **SECONDARY** (same analysis source). Java/Spring Boot is closer to Python than to Kotlin-in-2026, but this is the exact mechanism the user's platform bets on.
5. **Optimizing a skill document with a *free, deterministic* verifier.** Every study above uses either paid gold tests (SWE-bench) or an LLM judge. Nobody has run the loop where verification is a local build + static conformance scan at zero marginal cost.

---

## 2. The positive codegen datapoints (and the numbers behind them)

### 2.1 GEPA on kernels — what I can and cannot verify

**PRIMARY (abstract, from [arxiv.org/abs/2507.19457](https://arxiv.org/abs/2507.19457) and the ar5iv full text):**

> *"Across six tasks, GEPA outperforms GRPO by 6% on average and by up to 20%, while using up to 35x fewer rollouts … GEPA also outperforms the leading prompt optimizer, MIPROv2, by over 10% (e.g., +12% accuracy on AIME-2025), and demonstrates promising results as an inference-time search strategy for code optimization."*

**PRIMARY (§1 of the v2 full text, via the r.jina.ai proxy of `arxiv.org/html/2507.19457v2`):**

> *"We also demonstrate GEPA as an inference-time search strategy for code optimization on NPUEval (Kalade and Schelle, 2025) & KernelBench (Ouyang et al., 2025) in Sec 5.1"* … and the discussion of evaluation traces: *"code evaluation may involve compilation, execution, and profiling, producing natural language traces before computing a scalar reward."*

**SECONDARY — the numbers themselves.** I could **not** read §5.1. The arXiv HTML exceeds the 5 MB fetch cap, the ICLR 2026 camera-ready is a PDF (unsupported content type), and the r.jina.ai rendering truncated before §5. What I have:

- A conference-talk report of the GEPA author's presentation ([StartupHub.ai, 2026-09-27](https://www.startuphub.ai/ai-news/ai-research/2026/gepa-squeezes-7x-gains-from-three-examples)): *"For AMD's new NPU XDNA2 accelerator, where GPT-4 failed for lack of public docs, GEPA lifted an agent from 4.25% to 30.52%, a 7x jump, and even learned to avoid including ADF.h, a library that ships but does not work on that generation."* The same report says *"GEPA hit twice the gain of GRPO using just three examples and one round of reflection, versus 25,000 rollouts for the RL baseline."* **SECONDARY.**
- The predecessor's numbers (RAG 16.33%, MIPROv2+RAG 19.03%, single GEPA prompt 26.85%, GEPA prompt 30.52%, KernelBench `fast_1` ~0% → >20%) — **PRIMARY in the predecessor**, not independently confirmed here.

**Why it worked — the mechanism, and it is the knowledge hypothesis, not a procedure hypothesis.** The talk report's framing is *"where GPT-4 failed for lack of public docs"*, plus a concrete learned fact (`ADF.h` ships but does not work on that generation). That is **non-public, version-specific API knowledge** distilled into text. The predecessor's reading was right and should now be stated harder: GEPA's kernel win is best understood as *knowledge distillation into a portable artifact*, not as "procedures beat knowledge".

### 2.2 `gskill` — the largest reported skill-document codegen gain, and its catch

**PRIMARY** — the GEPA team's own write-up, [gepa-ai/gepa blog, 2026-02-18](https://github.com/gepa-ai/gepa/blob/234970ac898b1c22a9012a15c72948f498994ebd/docs/docs/blog/posts/2026-02-18-automatically-learning-skills-for-coding-agents/index.md). Verified numbers, quoted:

> *"Using gskill, we learn repository-specific skills for jinja and bleve with a simple agent (Mini-SWE-Agent, gpt-5-mini), boosting its resolve rate from **55% to 82%** on Jinja and from **24% to 93%** on Bleve. These skills also transfer directly to Claude Code: on Bleve, Claude Haiku 4.5 jumps from **79.3% to 100%** pass rate while running faster; on Jinja, Claude Haiku 4.5 improves from 93.9% to 98.5%."*
> *"On Bleve with Claude Haiku 4.5, average duration dropped from 173s to 142s while pass rate jumped from 79.3% to 98.3%."*
> *"Generate ~300 SWE-smith tasks per repository … Create train (~200), validation (~50), and test (~60) splits … **Under 300 rollouts**, the Mini-SWE-Agent with GEPA-evolved skills achieves a resolve rate of 82% on Jinja and 93% on Bleve, compared to the baseline of 55% and 24% respectively."*

Its stated mechanism, quoted:

> *"The most striking gains come when the baseline agent struggles. On Bleve, Mini-SWE-Agent went from a 24% resolve rate to 93% — a nearly 4x improvement. This suggests that learned skills are especially valuable when the model lacks prior familiarity with a repository's conventions and patterns."*

**Three caveats, all from the report itself plus the follow-up paper:**

1. The gains are largest on a **weak agent + small model** (Mini-SWE-Agent, gpt-5-mini, 24% baseline).
2. On the strongest configuration the instrument saturates: *"For Claude Sonnet 4.5, although the pass rate saturated, we still observe significant task duration reduction"* ([Skill Issue §1](https://arxiv.org/html/2609.12742v1), **PRIMARY**).
3. The tasks are **SWE-smith synthetic**, which Skill Issue argues are *"small enough that a capable agent saturates them with no document at all"* (**PRIMARY**, §2.3 below).

**Budget: ~300 rollouts for the whole optimization, on ~300 mined tasks.** That is the smallest credible text-space-optimization budget I found for codegen and it is squarely inside the "tens-to-hundreds, not thousands" regime the parent asked about.

### 2.3 "Skill Issue" — the direct test, and a near-null for SkillOpt

**PRIMARY** — read the full text via the r.jina.ai proxy of [arxiv.org/html/2609.12742v1](https://arxiv.org/html/2609.12742v1). This is the most important source in this report.

**Setup.** Three Kotlin repositories (`kotest/kotest`, `ktorio/ktor`, `JetBrains/koog`); tasks mined by **reverse-applying merged PRs at a single frozen base commit** so a SKILL describes the repository *as it is*; grading by the tests that switch from pass → fail; a Claude Code agent (Sonnet 4.6) is the fixed agent, **the `.md` document is the only optimized parameter**; both proposers are instrumented **against the same validation score** *"to separate the effect of the metric from the effect of the optimizer."*

**The headline numbers, quoted:**

> *"On three Kotlin repositories, the documents GEPA finds raise this score by **4.9 pp** on average, and the ones SkillOpt finds leave it where it started, **0.1 pp** above the seed."*
> *"Neither gain is statistically significant on splits of this size, **20 to 26 held-out tasks per repository**, and GEPA's is of the same order as what gskill reports with the same optimizer on its strongest configuration, and as the share of passes a binary verdict mislabels."*

**The instrumentation insight — the seed-relative objective.** Instead of a pass rate they compare each variant's rollout with **the seed SKILL's rollout on the same task**, *"so a variant gains nothing from tasks the agent already solves without it."* They explicitly rejected token-price, tool-call-effort, LLM-judge, gold-match, file-facts and "ideal-document" objectives — and report the failure mode that makes this matter:

> *"A judge that sees only the patch and the problem statement never reads the SKILL, so there is no document to ship. On one confirmation run the held-out score rose while the file was empty, because the judge was scoring the agent's writing."*
> *"Two files look like something a maintainer might ship. The score is a property of the file, not of the agent. **Grounding can rise on held-out tasks while the agent does not improve.**"*

**Why the score barely moves — their own attribution:**

> *"the variance of the score compounds the run-to-run variance of the agent, so a difference of this size sits inside the spread the agent produces on its own, and the reflector is asked to choose between candidates separated by less than that. Converging under such a signal would, in practice, take more tasks than a repository supplies."*

**The economics, quoted (directly relevant to the zero-compute user):**

> *"mining and validation leave **119 tasks out of koog's 660 merged pull requests**. Scoring one candidate on one task is a full agent rollout, **$0.84 on average** in our runs, so a **200-attempt optimization run costs hundreds of dollars**; the repository's history and the budget both run out before the split is large enough."*

Reverse-apply yield: *"only 25 of koog's 119 graded tasks reverse-apply cleanly, 56 of 100 on kotest and 65 of 131 on ktor"* — i.e. ~21–65% clean.

**The qualitative finding that keeps the door open, quoted:**

> *"both documents contain knowledge one only gets by working in the project, and both pad it with general advice the agent does not need. On the live issues, with either document the agent finished in **under half the wall-clock time** and at lower cost."*
> *"a maintainer of one repository found in them knowledge one only gets by working in the project."*

**And the metric-validity bomb, quoted:**

> *"Sahoo et al. (2026) report that **10.7% of passing agent trajectories** reach that verdict through blind retries or unverified edits rather than a principled solution. **A gain of a few points is thus of the same magnitude as the share of passes the metric itself mislabels.**"*

**Read this precisely.** Skill Issue is (a) a **null for the SkillOpt proposer on repo-level codegen** (+0.1 pp), (b) an **unpowered positive for GEPA** (+4.9 pp, not significant, 20–26 clusters), (c) a **positive for the *artifacts* on the dimensions the pass rate cannot see** (wall-clock more than halved, lower cost, maintainer-recognized project knowledge), and (d) a demonstration that **the chosen metric is the binding constraint**, not the optimizer.

### 2.4 Other codegen-optimization numbers (function-level and selection)

| Method | Artifact optimized | Benchmark | Verified numbers | Tag / source |
|---|---|---|---|---|
| **CodeT** | generated tests (for *selection*, not for the generator's prompt) | HumanEval (164 problems, n=100 samples) | code-davinci-002: pass@1 **47.0 → 65.8** with dual execution agreement (pass@10 baseline 74.9 → 86.6); code-cushman-001 33.5 → 44.5; InCoder-6B 16.4 → 20.6; CodeGen-Mono-16B 29.7 → 36.7. Also *"Codex … pass@100 of 77.4% … but pass@1 of only 33.5%"* | ✅ PRIMARY [ar5iv 2207.10397](https://ar5iv.labs.arxiv.org/html/2207.10397) |
| **R2E-Gym hybrid** | nothing optimized in text — candidate *selection* | SWE-bench Verified | Pass@1 **34.4%** (32B) → **Best@16 w/ Hybrid 49.4%**; *"each approach individually saturates around 42-43%"* | ✅ PRIMARY [ar5iv 2504.07164](https://ar5iv.labs.arxiv.org/html/2504.07164) |
| **SWE-Gym** | verifiers trained on trajectories | SWE-bench Verified | Best@16 w/ verifier **32.0%** | ✅ PRIMARY (reported in R2E-Gym Table 4) |
| **Large Language Monkeys** | nothing — repeated sampling + unit-test selection | SWE-bench Lite | DeepSeek-Coder-V2 **15.9% pass@1 → 29.62% at 5 attempts → 56% at 250**; *"sampling five times from the weaker and cheaper DeepSeek model solves more issues than single samples from Claude or GPT while also being over 3x cheaper"* | ✅ PRIMARY [ar5iv 2407.21787](https://ar5iv.labs.arxiv.org/html/2407.21787) |
| **TextGrad** | free-text gradients into any variable | LeetCode-Hard | *"20% relative gain on LeetCode-Hard solutions"* | ⚠️ SECONDARY (carried from the predecessor; not re-verified) |
| **Scaffold, Not Vocabulary?** | a code-generation "skill" (Popperian) | HumanEval+ (execution oracle) | frontier model N=163: *"all conditions sit near the benchmark ceiling and do not separate, so the pre-registered +5-point improvement is not supported (a ceiling-limited non-detection)"*; small model N=164: structured arms lift best-of-8 by **20–22 points** but *"the full skill shows no separable benefit over a labels-only scaffold (aggregate F@8=L@8 vs V@8=34.8%), and the placebo trails by only 2.4 points"* | ✅ PRIMARY (abstract) [arXiv:2606.06454](https://arxiv.org/abs/2606.06454) |
| **gskill** | a `SKILL.md` doc, GEPA-optimized | SWE-smith tasks (Jinja, Bleve) | 24 → 93, 55 → 82; transfer to Claude Code; <300 rollouts | ✅ PRIMARY (author blog) |
| **GEPA NPUEval** | a kernel-generation prompt | NPUEval (AMD XDNA2) | 4.25% → **30.52%** (secondary); *"preliminary"* (primary) | ⚠️ SECONDARY for the number |

**The picture:** every *large, verified* codegen gain in this table comes from either **selection among samples with a verifier** (CodeT, R2E-Gym, LLM) or **transferring a weak agent to a domain it does not know** (gskill). No table row shows a large gain from **procedural-advice optimization against a strong agent with headroom.**

---

## 3. Methods by compute cost (zero weight updates only)

Sorted cheapest-first within each tier. "Needs weights?" is the first cut, because it is disqualifying.

| Tier | Method | Needs weight updates? | Rollouts / samples required (as reported) | Wall-clock / money | Reported gain | Source & tag |
|---|---|---|---|---|---|---|
| **0. Free** | **Deterministic conformance scoring** (`scan_architecture_compliance` + `analyze_code_compliance`) | No | 0 model calls | ~0 | Not a gain — it is the *instrument*; makes any effect measurable | ✅ PRIMARY (repo) [compliance.py](../backend/app/orchestrator/stages/compliance.py) |
| **0. Free** | **Negative-constraint rules as hooks/gates** rather than prose | No | 0 | 0 | Polarity: all shaping rules are negative constraints; −20 pp when the top one is removed; ensemble stable 0→50 rules | ✅ PRIMARY [Guardrails](https://arxiv.org/html/2604.11088v2) |
| **1. Generation-only** | **Best-of-k + execution verification** (the user's free verifier) | No | **k=5** → 15.9 → **29.62%** (SWE-bench Lite, DeepSeek-Coder-V2); k=16 → 34.4 → 49.4% (R2E-Gym hybrid) | 5× cheap-model generation ≈ **1/3** the price of 1 GPT-4o sample; k=16 = 16 generations | +13.7 pp at k=5; +15 pp at k=16 | ✅ PRIMARY [LLM](https://ar5iv.labs.arxiv.org/html/2407.21787), [R2E-Gym](https://ar5iv.labs.arxiv.org/html/2504.07164) |
| **1. Generation-only** | **Best-of-k + *generated*-test selection** (CodeT) | No | n=100 samples/prob.; select top-1 | 100 generations | 47.0 → 65.8 pass@1 on HumanEval | ✅ PRIMARY [CodeT](https://ar5iv.labs.arxiv.org/html/2207.10397) |
| **1. Generation-only** | **Agentless-style pipeline** (localize → repair → validate; *no agent loop*) | No | 4 LLM calls per task reported ($0.70/task Lite) | $0.70/task | **32.00%** SWE-bench Lite (its-era SOTA among open agents); Agentless-1.5 GPT-4o **34.0%** Verified | ✅ PRIMARY (32.00/$0.70 carried from predecessor; 34.0 from R2E-Gym Table 4) |
| **1. Generation-only** | **Bounded self-repair with external feedback** | No | 1–3 repair rounds | linear in rounds | *"often modest, vary a lot … sometimes not present at all"*; gains improve with stronger *external* feedback | ✅ PRIMARY (predecessor: Olausson 2306.09896) |
| **2. Tens of rollouts** | **gskill (GEPA + SWE-smith)** | No | **"Under 300 rollouts"**; ~300 tasks (200/50/60) | Hundreds of generations; $ per repo not stated | **24 → 93** (Bleve), **55 → 82** (Jinja); transfer to Claude Code | ✅ PRIMARY (author blog) |
| **2. Tens of rollouts** | **GEPA (general)** | No | explicit rollout budget `B`; headline *"up to 35× fewer"* than GRPO's 24,000; *"can often turn even just a few rollouts into a large quality gain"*; *"even a single reflective prompt update can give large improvements"* | offline, amortized | +6% avg / up to +20% over GRPO; +13% over MIPROv2 | ✅ PRIMARY (abstract + ar5iv intro) |
| **2. Tens of rollouts** | **RoboPhD** (Elo tournament, **validation-free**) | No | **fixed 1,500 evaluations** for the whole comparison | 1,500 evaluations | Beats GEPA and greedy hill-climbing on **3 of 4** benchmarks; ARC-AGI 27.8 → 65.8% | ✅ PRIMARY (abstract) [arXiv:2604.04347](https://arxiv.org/abs/2604.04347) |
| **3. Hundreds** | **SkillOpt** | No | 4 epochs × rollout batch 40 (≈160/epoch) + reflection minibatches; **0.6M–46.4M training tokens per absolute test point** | offline; amortized | +23.5 / +24.8 / +19.1 (GPT-5.5, three harnesses); **0 codegen benchmarks** | ✅ PRIMARY (predecessor §1.1; §4.2 ablations) |
| **3. Hundreds** | **Trace2Skill** | No | 400 samples → 200 evolution / 200 test | offline | up to +57.65 pp on WikiTableQuestions; per-seed std ≤3.4 | ✅ PRIMARY (predecessor §1.3) |
| **3. Hundreds** | **EvoSkill / AutoRefine** | No | not extracted | offline | OfficeQA +7.3; SealQA +12.1; TravelPlanner 80.56% vs 50.0% | ✅ PRIMARY (predecessor §1.4) |
| **3. Hundreds** | **DSPy MIPROv2 / BootstrapFewShot** | No | docs: *"a few training inputs. This may be very small (i.e., only 5 or 10 examples)"* | offline | framework, no headline | ✅ PRIMARY (predecessor §1.4) |
| **4. Per-task inference** | **Self-consistency / majority vote** | No | plateaus beyond ~100 samples on math; *"the biggest performance increase is only from 40.50% to 41.41%"* (100 → 10,000 samples) | large | **weak** without an execution verifier | ✅ PRIMARY [LLM](https://ar5iv.labs.arxiv.org/html/2407.21787) |
| **5. Disqualified** | **RL skill libraries (SkillRL, SAGE), SWE-RL, SWE-Gym/R2E-Gym *training*** | **Yes** | 10⁴–10⁵ rollouts; 8.7K tasks for R2E-Gym | GPU cluster | SWE-RL 41.0% Verified; SWE-Gym +19%; R2E-Gym 34.4% pass@1 | ✅ PRIMARY (predecessor §2) |

**Two structural readings of the table.**

- The **zero-compute frontier is at tiers 0–2**. Everything at tier 3+ assumes paid rollouts at a scale this user cannot fund (Skill Issue: *$0.84/rollout*, *200-attempt run = hundreds of dollars*).
- **Selection beats optimization at equal budget.** Best-of-5 with an execution oracle (+13.7 pp, 5 generations) is cheaper *and* better-evidenced than any text-space optimization result on repo-level code in this table.

---

## 4. The free-verifier asymmetry

### 4.1 What small n actually buys with a free verifier — the published curves

| Datapoint | n | Metric | Value | Tag / source |
|---|---|---|---|---|
| DeepSeek-Coder-V2, SWE-bench Lite | 1 | resolved | 15.9% | ✅ PRIMARY [LLM §2.1](https://ar5iv.labs.arxiv.org/html/2407.21787) |
| same | **5** | resolved (unit-test verified) | **29.62%** | ✅ PRIMARY (Table 1) |
| same | 250 | coverage | **56%** (vs single-sample SOTA 43%) | ✅ PRIMARY |
| Cost, same task set | 5×$0.0072 | — | **$10.8 total, 1× relative** | ✅ PRIMARY (Table 1) |
| GPT-4o | 1 | resolved | 24.00% | ✅ PRIMARY |
| GPT-4o | 1 | cost | **$39, 3.6×** | ✅ PRIMARY |
| Claude 3.5 Sonnet | 1 | resolved / cost | 26.70% / **$51, 4.7×** | ✅ PRIMARY |
| R2E-Gym-32B | 16 | Best@16 w/ hybrid verifier | **49.4%** (pass@1 34.4%) | ✅ PRIMARY |
| R2E-Gym, each axis alone | — | — | *"each approach individually saturates around 42-43%"* | ✅ PRIMARY |
| SWE-Gym-32B | 16 | Best@16 w/ verifier | 32.0% | ✅ PRIMARY (R2E-Gym Table 4) |
| CodeT, code-davinci-002 HumanEval | 100 sampled, top-1 selected | pass@1-after-selection | 47.0 → **65.8%** | ✅ PRIMARY |

**The n=2–8 answer, stated plainly.** The empirical small-n datapoint that exists is **n=5 → +13.7 pp** on SWE-bench Lite, with an execution verifier, at ~1/3 the cost of a single frontier sample. There is **no published accuracy-vs-n curve that isolates n ∈ {2,3,4,6,7,8}**; the LLM paper's own model is a **coverage power law** `log(c) ≈ a·k^b` (`c ≈ exp(a k^b)`, fitted over orders of magnitude), which is *sub-linear in k*, so naive `1−(1−p)^n` arithmetic **overstates** small-n gains. For a user with a free verifier, the defensible claim is: **n=5 is the smallest published setting with a measured, non-trivial gain; the marginal gain per extra sample is largest in the first few samples and decays.**

### 4.2 The verifier is the weak link, and the user's verifier is the weakest kind

The parent asked specifically about gaming and low distinguishability. Verified evidence:

| Failure mode | Verified number | Tag / source |
|---|---|---|
| **Solution leakage** in the *task statement* | **32.67%** of successful patches; filtering drops SWE-Agent+GPT-4 from **12.47% → 3.97%**, and on leakage-free SWE-bench+ to **0.55%** | ✅ PRIMARY [ar5iv 2410.06992](https://ar5iv.labs.arxiv.org/html/2410.06992) |
| **Weak tests** admitting wrong patches | **31.08%** of passed patches suspicious (incorrect 12.75%, incomplete 14.74%, wrong files 3.59%) | ✅ PRIMARY (same) |
| On SWE-bench Lite / Verified, suspicious fixes | **48.14% / 55.36%**; resolution halves (18 → 9.33%; 22.4 → 10.0%) | ✅ PRIMARY (same) |
| On the leak-free SWE-bench+ | **67.72%** of "resolved" instances did not truly resolve the issue | ✅ PRIMARY (same) |
| **Flaky tests** | **11.3%** of SWE-bench Lite problems have test suites that are not deterministic on the same candidate | ✅ PRIMARY [LLM §4.2.1](https://ar5iv.labs.arxiv.org/html/2407.21787) |
| **False negatives** | **35 of 122** CodeContests problems have "correct" solutions that fail the tests | ✅ PRIMARY (same) |
| **Low distinguishability of test-based verifiers** | *"Test-based verifiers suffer from low distinguishability, while execution-free verifiers are biased and often rely on stylistic features"*; individually saturating at 42–43% | ✅ PRIMARY [R2E-Gym abstract](https://ar5iv.labs.arxiv.org/html/2504.07164) |
| **Passes reached for the wrong reason** | **10.7%** of passing agent trajectories via blind retries/unverified edits | ✅ PRIMARY (via Skill Issue, citing Sahoo et al. 2026) |

**Why this is the user's exact risk, in their own terms.** Their gate's pass criterion is *"the offline build/test exit code is zero"* ([specs/014-skillopt-compact/contracts/gate.md](../specs/014-skillopt-compact/contracts/gate.md)), with fallback-marked executions excluded. A compile-and-run exit code is the *test-based verifier of the weakest kind*. An optimizer rewarded by `exit_code == 0` can raise the score by **emitting less code, fewer tests, or trivially satisfiable tests** — and the spec already names a variant of this exploit (making the verifier give up). **The 31.08% weak-test figure is empirical proof that this exploit is not hypothetical; it is the modal failure of the most widely used agentic code benchmark.** The spec's fallback exclusion closes one hole; it does not close assertion weakness, and it does not close "the generated tests never exercise the generated code".

### 4.3 The one place the user's asymmetry is genuinely better than everyone else's

Every paper above pays for verification (gold tests, a testing-agent, a reward model). The user's verification is **a local Maven run: zero marginal API cost.** That means:

- **k-sampling is nearly free to *verify*** — the binding cost is generation only. Best-of-k is therefore the highest-EV zero-compute lever (§8), and it is the only lever whose published gains are large, verified, and measured at small n.
- Rollout budgets are no longer the constraint they are in Skill Issue (*$0.84/rollout*). The constraint becomes **generation dollars and wall-clock**, which is exactly the regime where `gskill`'s "under 300 rollouts" and GEPA's budgeted loop become affordable.
- But the free verifier is also the *same* verifier used by the optimizer's gate, which is why the two must be *separated*: score with the architecture-compliance verdict (deterministic, hard to game by emitting less code) and keep the build exit code as a guardrail only.

---

## 5. The "make the skill carry knowledge the model lacks" hypothesis

**The hypothesis:** injecting genuinely non-obvious, non-public domain knowledge into context improves codegen even when generic procedural rules do not.

**Verdict: SUPPORTED for *non-discoverable* knowledge, but the supporting evidence is mostly about retrieval and distillation, not about a standing skill document; and the strongest counter-evidence is that domain-*mismatched* rules perform as well as matched ones.**

| Evidence | What it shows | Tag / source |
|---|---|---|
| Gloaguen v1, documentation removed: LLM-generated context files *"consistently improve performance by 2.7% on average, but also outperform developer-written documentation"* | Files help **when they are the only carrier of the information** | ✅ PRIMARY |
| Gloaguen v2 intro: *"Human-written context files should only include instructions required for coding agents that are not already present in the README (e.g., specific conventions or non-functional requirements)"* | The paper's own prescription is "only non-discoverable content" | ✅ PRIMARY |
| Gloaguen v2 abstract: *"context files are useful for specifying non-standard coding practices"* | The one acknowledged positive use case — **but I could not find the experiment behind it** (see §13) | ✅ PRIMARY (abstract) / ❌ UNVERIFIED (supporting experiment) |
| gskill: *"especially valuable when the model lacks prior familiarity with a repository's conventions and patterns"*; 24 → 93 on Bleve (Go) | Knowledge transfer to an unfamiliar codebase is where the big gain lives | ✅ PRIMARY |
| Skill Issue: *"a maintainer of one repository found in them knowledge one only gets by working in the project"*; both documents halved wall-clock and cut cost | The documents **did** carry real project knowledge — the pass-rate instrument just could not see it | ✅ PRIMARY |
| GEPA NPUEval: 4.25% → 30.52% "where GPT-4 failed for lack of public docs", learning to avoid `ADF.h` | Non-public, version-specific API knowledge distilled into text | ⚠️ SECONDARY for numbers; ✅ PRIMARY for the paper's claim that it is *"preliminary"* |
| **Guardrails, mismatched vs matched domain:** wrong-domain rules **58.6%** vs same-domain **56.9%** | **Direct counter-evidence:** domain *relevance of content* barely mattered | ✅ PRIMARY |
| **Guardrails, architecture rules 53.4%** | The "house standard / layering" family is the worst type | ✅ PRIMARY |
| [RepoCoder](https://arxiv.org/abs/2303.12570) similarity + iterative retrieval: *"significantly improves the In-File completion baseline by over 10% in all settings"* | Retrieval of real repository context is a measured lever | ✅ PRIMARY (predecessor) |

**Honest synthesis.** The knowledge hypothesis survives in a **narrow** form: *if the information is (a) not discoverable from the repository, (b) not in the model's weights, and (c) actually required to complete the task, then supplying it in context helps.* The platform clears (a) trivially (an in-house Spring Boot standard is not public) and probably clears (c) for conformance but **not** for build success — and it may fail (b): Spring Boot layering is extremely well represented in training data, which is the same confound Gloaguen flags about Python. This is why Guardrails can find mismatched rules equal to matched ones: **the model already knows generic advice**. The differentiator is not "better advice", it is "advice the model cannot have".

---

## 6. Has anyone explicitly falsified skill-document optimization for codegen?

**Short answer: nobody has published a clean falsification; but the specific combination "SkillOpt-style proposer + repository-level codegen" has now been tested once and produced a null (+0.1 pp), and three other 2026 results are negative or content-independent for *procedural* skill content.** The difference between **refuted** and **untested** matters, and it is mostly the latter.

**Search protocol (queries run, and what came back):**

- `evidence prompt optimization does not work code generation negative result survey 2026` → surfaced "Scaffold, Not Vocabulary?" and the GEPA/Autoresearch comparison literature; **no position paper** claiming prompt optimization is useless for code.
- `position paper 2026 prompt optimization limits coding agents does not transfer` → returned harness/scaffold-optimization work and surveys on agent-system design; **no falsification position paper**.
- `survey context engineering agents 2026 verdict code tasks` → returned context-engineering pattern literature mostly restating Gloaguen/Guardrails; **no survey that adjudicates the question**.
- `GEPA replications code` / `skill documents ineffective coding agents` → the finds below.

**What I found that counts as near-falsification:**

1. **Skill Issue (arXiv:2609.12742), §2.3.** SkillOpt's documents *"leave it where it started, 0.1 pp above the seed."* One study, three repositories, 20–26 held-out tasks, **not significant in either direction**. This is a **null, not a refutation** — and the authors are unusually explicit that the constraint is the instrument: *"We attribute the difficulty to the measurement rather than to the optimizers."* ✅ PRIMARY.
2. **Scaffold, Not Vocabulary? (arXiv:2606.06454).** A **pre-registered, two-tier** ablation with *"a length-matched placebo, a labels-only scaffold that keeps the Popperian headers but strips the procedure, and an execution oracle (HumanEval+ unit tests)"*. Result: *"In the two settings tested, the skill's Popperian procedural content adds no separable execution-correctness benefit beyond a labels-only scaffold, so the gains track scaffold structure. We contribute a calibrated negative result and a reusable disambiguation protocol."* ✅ PRIMARY (abstract). **This is the closest thing to a deliberate falsification of "a code-generation skill's procedural content causes the gain" — and it is scoped by its own authors to "an engineering claim about one prompt-skill family".**
3. **Guardrails Beat Guidance, content-independence.** Random, shuffled, mismatched-domain and unconverted-format rule files all match curated rules; *"no condition is significantly different from any other"*. If content is not the variable, then **optimizing the content of a rule file is optimizing the wrong variable** — the authors say exactly this: *"automated rule optimizers should target structural properties rather than semantic content."* ✅ PRIMARY.
4. **Gloaguen v1/v2.** No general task-success improvement, +20% cost, both LLM-generated and developer-committed files, four agents. ✅ PRIMARY.

**What nobody has falsified, and the user should treat as genuinely open:**

- That a skill document optimized against a **deterministic conformance instrument** (rather than a binary pass rate) improves **conformance**.
- That a skill document improves **cost/latency** — the one axis where positives are consistent across gskill (173 s → 142 s), Skill Issue (wall-clock halved), the two-agent ablation (opshin 2689 → 2032 s), and Lulla et al. (predecessor: −28.64% runtime, −16.58% output tokens). Conformance-and-efficiency is the surviving positive claim.
- That the medium fails on **non-saturated, non-Python, genuinely-unfamiliar** codebases. Every null above is on Python/well-represented ecosystems (Gloaguen's own stated limitation) or on tasks the strong agent already solves.

**So: the right label is "tested and null once for the exact proposer; content effects null or content-independent three more times; no falsification of the medium on conformance, cost, or unfamiliar codebases."**

---

## 7. A concrete zero-compute experiment design

### 7.1 What the user actually has (verified from the repo)

| Asset | Fact | Source |
|---|---|---|
| Blueprints | exactly 5: `pair-a`, `pair-b`, `minimal`, `multi-entity`, `constrained` | ✅ PRIMARY [baseline report](baselines/011-pre-migration-generation-baseline.md), [spec.md FR-006](../specs/014-skillopt-compact/spec.md) |
| Gate | M=4 of 5, both arms on the identical set, **2×M = 8** fresh executions/iteration, strict improvement, fallback excluded | ✅ PRIMARY [spec.md FR-006/007](../specs/014-skillopt-compact/spec.md) |
| Pass rule | *"the offline build/test exit code is zero"* | ✅ PRIMARY [contracts/gate.md](../specs/014-skillopt-compact/contracts/gate.md) |
| Seed skill | controller → service → repository → model layering, ~250 tokens, protected region | ✅ PRIMARY [spec.md FR-001](../specs/014-skillopt-compact/spec.md) |
| **Deterministic conformance instrument (unused as a metric)** | `scan_architecture_compliance` (family B) + `analyze_code_compliance` (family A), deduplicated by `(artifact_path, rule_id)` keeping the more severe rating, producing a graded score `100 − (critical·30 + high·15 + medium·5 + low·2)` and a blocking flag | ✅ PRIMARY [compliance.py](../backend/app/orchestrator/stages/compliance.py), [security_service.py](../backend/app/services/security_service.py) |
| **Deterministic constraint-trace instrument (unused as a metric)** | `_constraint_trace()`: `format_constraints_traced` / `format_constraints_untraced`, declared vs observed test-method counts, required-attribute annotation presence | ✅ PRIMARY [capture_generation_baseline.py](../backend/scripts/capture_generation_baseline.py) |
| Twin design already present | `pair-a` vs `pair-b` are byte-identical pre-migration *"confirm[ing] that declared constraints and acceptance scenarios had **zero** effect on pre-migration output"* | ✅ PRIMARY [baseline report §5](baselines/011-pre-migration-generation-baseline.md) |
| Real evidence stream | session records with spec id, artifact paths, build exit code, terminal status, fallback marking | ✅ PRIMARY [spec.md FR-003](../specs/014-skillopt-compact/spec.md) |

### 7.2 The design: paired seed-relative conformance optimization

**The single most important change: optimize against a deterministic conformance score, not the build exit code.** Rationale is §4.2 — a binary compile gate is a low-distinguishability verifier (R2E-Gym) whose weak-test failure rate is 31% on the best-known benchmark (SWE-bench+), and it is gameable by emitting less code.

**Metrics.**

- **M1 (primary): conformance score**, `100 − penalty` from the merged compliance verdict, **excluding fallback-marked executions**, aggregated per generated service. Deterministic, graded, zero model noise, and it is *the house standard made numeric* — the exact thing the seed skill claims to influence.
- **M1b (primary, secondary readout): constraint-trace rate** = `|format_constraints_traced| / |declared_validation_rules|` per blueprint (from `_constraint_trace`). Also deterministic.
- **M2 (secondary): cost** — output tokens and wall-clock per session (the axis on which every positive in this literature lives).
- **M3 (guardrail, not a metric): build/test exit code zero.** A candidate that regresses M3 is rejected regardless of M1.
- **Explicitly not the metric:** an LLM judge. Skill Issue's empty-file incident (*"the held-out score rose while the file was empty, because the judge was scoring the agent's writing"*) is the reason.

**Objective.** Follow Skill Issue: score each candidate rollout **against the seed's rollout on the same asset**, so a variant gains nothing from assets the agent already passes. Their rejected-objectives appendix is a map of dead ends: token-price alone, tool-call effort alone, judge-based, file-facts, "ideal-document" — *"Grounding can rise on held-out tasks while the agent does not improve."*

**Proposer.** GEPA-style: fixed rollout budget, Pareto (or Elo) selection over candidates, **free rewrite** of the document, no strict-improvement gate on fewer than ~20 items. RoboPhD's result is directly on point for a tiny asset pool: **validation-free evolution** via Elo competition on the *training* data avoids spending budget on a validation split it cannot afford, and beat both GEPA and greedy hill-climbing on 3 of 4 benchmarks at a fixed 1,500 evaluations. **If the strict gate is kept, demote it from "evidence of improvement" to "regression filter".**

**Skill content rules (both have published support).**

- **Negative constraints only** — every individually shaping rule found is a "do not X"; every distorting one is a "do X".
- **Never the architecture family as positive directives** — 53.4%, the worst of five types. Express layering as *prohibitions* ("do not put business logic in the controller", "do not bypass the repository from the service") rather than prescriptions ("use the repository pattern").
- **Prefer state-dependent/tool-process rules** — 63.8%, the best type.
- **Anything mechanically checkable should become a build-time gate, not prose.** The platform already has the scanner; the highest-value single change is to make the *build* fail on architecture violations instead of asking the model to comply.

### 7.3 Sample-size math — explicit, and honest

**Notation.** Unit of analysis = **asset** (a blueprint or a replayed held-out spec). Paired design: every asset is run under both arms. α = 0.05 two-sided, power = 0.80, so z_{α/2} = 1.96, z_β = 0.8416.

**(a) The arithmetic floor — binary metric.**

Exact McNemar (binomial on discordant pairs), two-sided, with `b` pairs favouring the candidate and `c` the baseline, and `c = 0` (best possible case):

`p = 2 · 0.5^(b+c) = 2^(1−(b+c))`

| Discordant pairs (all favourable) | Two-sided p | Significant? |
|---|---|---|
| 4 | 0.125 | **No** |
| **5** | **0.0625** | **No** |
| 6 | 0.03125 | Yes |

The platform's rotation gives **M = 4** scored assets per iteration → best attainable p = **0.125**; the whole pool of **5** → best attainable p = **0.0625**. **A 5-asset binary gate can never reach p < 0.05, even if the candidate flips every single asset.** Minimum for the floor: **6 assets, all six flipping**.

**(b) Same wall for a continuous metric.** A two-sided **sign-flip permutation test** on n paired differences has exactly 2ⁿ sign vectors, so the smallest attainable two-sided p is `2/2ⁿ`:

| n (clusters) | min two-sided p | Significant? |
|---|---|---|
| 4 | 0.125 | No |
| **5** | **0.0625** | **No** |
| 6 | 0.03125 | Yes |

**So the wall is not about the metric being binary. It is about having five clusters.** (Student's *t* can in principle reach p < 0.05 at n = 5 if the paired differences are almost perfectly consistent — but with any blueprint-level heterogeneity in the effect that is not credible, and a zero-variance difference yields a degenerate interval rather than evidence.)

**(c) Power — binary, paired (discordant-pair formulation).**

Required discordant pairs for a one-sample binomial test against q = 0.5, where q = (share of flips favouring the candidate):

`n_d = [ z_{α/2}·0.5 + z_β·√(q(1−q)) ]² / (q − 0.5)²`

| q (flips favouring candidate) | n_d | Total assets if 20% of assets flip | if 30% flip |
|---|---|---|---|
| 0.60 | 194 | 969 | 646 |
| 0.65 | **85** | 424 | 283 |
| **0.75** | **29** | **145** | **96** |
| 0.85 | 14 | 67 | 45 |

**(d) Power — binary, unpaired two-proportion** (cross-check; `n = 7.849·[p₁(1−p₁)+p₂(1−p₂)]/(p₁−p₂)²`):

| Improvement | n per arm |
|---|---|
| 0.50 → 0.75 (+25 pp) | **≈55** |
| 0.50 → 0.65 (+15 pp) | ≈167 |
| 0.50 → 0.60 (+10 pp) | ≈385 |
| 0.30 → 0.40 (+10 pp) | ≈353 |
| 0.30 → 0.35 (+5 pp) | ≈1,374 |

**Independent confirmation from the literature:** the two-agent ablation's Monte Carlo — *"Detecting Δ=10pp at 80% power requires ~120–200 tasks"* — is the **paired, 3-repeat** version of the ≈385 unpaired number. Both are in the same regime; the paired design is ~2–3× cheaper. Guardrails' 58 discriminative tasks was enough only for a **direction** (binomial sign test p=0.008, no per-condition significance).

**(e) Power — continuous metric, paired t-test.** `n = (z_{α/2}+z_β)²/d² = 7.849/d²`, where `d` = |mean paired difference| / SD of the paired differences.

| d | n required | What n=5 can detect |
|---|---|---|
| 0.5 (small) | 32 | — |
| 0.8 (medium) | 13 | — |
| 1.0 | 8 | — |
| **1.253** | **5** | ← **MDE at exactly 5 clusters** |
| 1.5 (large) | 4 | — |

**So with 5 blueprints, the minimum detectable paired effect is d = 1.25.** That is: *the mean change must exceed 1.25× the standard deviation of the per-blueprint changes.*

**(f) The one lever that makes 5 work — and its limit.** Repeating runs per blueprint does **not** create new clusters. With 5 blueprints × R repeats you get 5R observations but still **5 independent units**; treating runs as units is pseudo-replication and inflates significance. What repeats *do* buy is a **better estimate of each blueprint's mean**, which reduces the *measurement* component of the paired-difference SD. If the instrument is deterministic (M1, M1b) and the only noise is generation sampling, R repeats can push the paired-difference SD down until it is dominated by **effect heterogeneity across blueprints**. Then:

- If the effect is **consistent** across blueprints (SD → 0), d is large and n = 5 suffices.
- If the effect is **heterogeneous** (likely — a layering rule bites on `multi-entity`, does nothing on `minimal`), d is small and **no amount of repetition rescues it**, because the SD is real signal dispersion, not noise.

The two-agent ablation's opshin result is the empirical warning: a **−24 % wall-clock effect with a monotone dose-response was still p = 0.125 at n = 5.**

**The honest answer, stated plainly.**

> **You cannot reach significance with 5 blueprints** — not for a binary pass-rate metric (arithmetic floor p = 0.0625 with all five flipping; you need ≥6 flips), and not for a robust paired test on the continuous conformance score (sign-flip floor p = 0.0625 at n = 5; t-test MDE d = 1.25).
>
> **Minimum viable asset count:**
> - **6** — the arithmetic floor, and practically useless (requires all six to flip in the same direction).
> - **~55 per arm** — to detect a *huge* effect (+25 pp on a binary metric).
> - **~120–200 paired assets** — to detect +10 pp with 80% power (literature-confirmed).
> - **~385 per arm** — the same +10 pp unpaired.
> - **For the continuous conformance score: 5 clusters if and only if you pre-register the effect as uniform and d ≥ 1.25.** Otherwise 32 clusters for d = 0.5.

**How to get more assets without authoring new fixtures.** The spec's *"no new fixtures may be introduced"* rule exists so the gate cannot measure its author; it also permanently caps power at 5. The resolution is not to write fixtures — it is to **mine assets from the session store and from repository history**: the platform already records specification identifiers and artifact paths per session ([spec.md FR-003](../specs/014-skillopt-compact/spec.md)), and Skill Issue demonstrates the exact recipe for turning a repository's own history into a graded asset set by reverse-applying merged changes at a frozen base (**~21–65% clean reverse-apply yield**, verified). Those assets were not authored alongside the optimizer, so they satisfy the rule's intent. **Target: ≥120 mined assets before making any claim stronger than "directionally positive on five blueprints".**

### 7.4 The smallest defensible experiment, concretely

| Element | Choice | Why |
|---|---|---|
| **Optimize** | the seed skill's layering *prohibitions*, never its positive directives | polarity evidence |
| **Metric (primary)** | M1 conformance score (deterministic); M1b constraint-trace rate | low noise; measures the house standard directly; not gameable by emitting less code |
| **Metric (guardrail)** | M3 build exit code zero; fallback-marked executions excluded | spec constitutionality + doesn't reward verifier surrender |
| **Metrics (report-only)** | output tokens, wall-clock | the axis with consistent published positives |
| **Assets** | 5 blueprints for the pilot; **mine ≥120 held-out specs from recorded sessions** before any inferential claim | power math §7.3 |
| **Repeats** | R = 3 per (asset, arm) | separates generation noise from deterministic instrument; keeps the asset as the unit |
| **Budget** | 1 reflection call + 2·k·R generations per iteration; k=5, R=3 → **30 generations/iteration** | finite, known, no training |
| **Proposer** | GEPA-style free rewrite + Pareto/Elo selection under a fixed budget | gskill (works, <300 rollouts); RoboPhD (better than GEPA under tight budgets); Skill Issue (the strict gate + tiny split is what failed) |
| **Decision rule** | pre-register the MDE; paired sign-flip test over clusters; accept only if the lower CI bound exceeds the MDE; **with 5 clusters report descriptively only** | §7.3 |
| **Kill criterion** | if the pilot's paired-difference SD implies MDE > the largest plausible effect, **report "not measurable at this asset count"** | "not rejected" ≠ "null". The predecessor's gate reports ties as rejections, which silently converts underpower into a negative finding. |

**Scientific point that matters more than the design:** a 5-asset experiment that returns "no difference" is **not** evidence of no effect. It is evidence that the question was asked with an instrument that cannot answer it. Reporting it as a negative result would be the same error as reporting the 61–76% spurious "strict improvement" rate as a positive.

---

## 8. What to do instead (ranked no-compute levers, with evidence)

Ranked by **expected value per inference dollar**, given zero weight updates and a free offline verifier.

**1. Verification-guided selection — best-of-k against the free offline verifier, ranked by a *composite* of build success and the deterministic conformance score.**
*Evidence:* 15.9% → **29.62%** at k=5 with unit-test selection, at **1× cost** vs GPT-4o's 24.00% at 3.6× and Claude's 26.70% at 4.7× (✅ PRIMARY, LLM Table 1); R2E-Gym **Best@16 hybrid 49.4%** vs pass@1 34.4% (✅ PRIMARY); CodeT selection 47.0 → 65.8 (✅ PRIMARY).
*Caveat that makes it the *first* lever rather than a magic one:* execution-only verification saturates at **42–43%** and is *"low distinguishability"* (R2E-Gym). The user's edge is that they also own a **second, complementary, deterministic verifier** — the architecture-compliance scanner. Ranking by `(build_passed, conformance_score, token_cost)` is a **free two-verifier hybrid**, which is exactly the configuration R2E-Gym found beats either verifier alone.
*Cost:* k× generation, zero verification cost. **Cheapest large, verified gain available.**
*Risk:* verifier gaming (SWE-bench+: 31.08% weak-test passes). Mitigate by (a) counting generated-test assertions, (b) requiring generated tests to fail against a mutated service, (c) excluding fallback-marked runs (already in the spec), (d) preferring the static conformance score over the exit code.

**2. Make the house standard executable instead of instructional.**
*Evidence:* Guardrails — all individually beneficial rules are negative constraints; all harmful ones are positive directives; the architecture family scores **53.4%** as a positive-directive type; *"automated rule optimizers should target structural properties rather than semantic content."* Gloaguen — every instruction is faithfully executed, and every executed instruction costs **+20%** and **+22% reasoning tokens**. *"If an instruction can be transformed into a hook, always prefer the hook"* (⚠️ SECONDARY, the toolkit analysis of Gloaguen). The platform **already has** `scan_architecture_compliance` and a blocking severity set. Raising layering from prose to a build-time gate converts a probabilistic, cost-inflating instruction into a deterministic check.
*Cost:* zero model calls.

**3. Adopt the deterministic conformance score as a first-class metric.**
This is not a "lever" in the sense of raising quality — it is the precondition for *ever knowing* whether anything helped, and it is the only instrument that can possibly function at 5 clusters (§7.3f). It already exists.
*Cost:* zero.

**4. Harness / output-format and pipeline design, with Agentless as the null-result baseline.**
*Evidence:* Agentless — *"a simplistic three-phase process"* with **no agent loop**, **32.00%** on SWE-bench Lite at **$0.70/task** (✅ PRIMARY, predecessor; 34.0% Verified for Agentless-1.5/GPT-4o via R2E-Gym Table 4). CodeAct: executable actions beat text/JSON action space by *"up to 20% higher success rate"* (✅ PRIMARY, predecessor). SWE-agent: interface design, 12.5% SWE-bench / 87.7% HumanEvalFix (✅ PRIMARY, predecessor).
*What Agentless implies for this platform:* the pipeline already **is** Agentless-shaped — fixed stages (SCAFFOLDER → DOMAIN → SERVICE → CONTROLLER → TEST), one artifact family per stage, and a repair loop. The lesson is **not** "add an agent loop"; it is *"make each stage's output verifiable and independently retried"*. The measurable consequence is that the fix for a bad generated service should be a **per-stage regression and retry**, not a better global skill document.

**5. Retrieval of house knowledge, just-in-time, instead of a standing skill document.**
*Evidence:* Gloaguen's only positive condition is when the file is the sole documentation (+2.7%); Gloaguen v2's prescription is non-discoverable content only; RepoCoder +10% (✅ PRIMARY, predecessor); gskill's big gains are on a repository the model does not know.
*Concrete form:* key the retrieved fragment by *(artifact type, blueprint feature)* — e.g. the repository/JPA fragment only for `multi-entity`; the validation-annotation fragment only for `constrained`. Do **not** prepend the whole standard to every stage call; that is the +20%-cost, no-gain configuration. This is also the mechanism that makes the "skill carries non-obvious knowledge" hypothesis *testable*: an ablation where the retrieved fragment is replaced by a length-matched irrelevant fragment (the two-agent study's equivalence design + Scaffold's placebo) is the correct control.

**6. Bounded self-repair against external feedback (already built — keep it, and keep the cap).**
*Evidence:* self-repair gains are *"often modest, vary a lot … sometimes not present at all"* and improve when feedback is stronger/external (✅ PRIMARY, predecessor); self-correction without external feedback can degrade (✅ PRIMARY). The constitution's cap of 3 (the measurement report found an effective cap of 5) is the right instinct: more repair attempts lower the intervention floor and can flatter the metric.
*Cost:* linear in attempts; verification free. Cheap enough to keep, not strong enough to lead with.

**7. Model routing / sample allocation.**
*Evidence:* LLM Table 1 is a pure routing result — a cheaper model sampled 5× beats a frontier model sampled 1× **at a third of the price**. For blueprint work: route `minimal`/`pair-a` to the cheap model with k=1, and spend the saved budget on k=5 for `multi-entity`/`constrained`.
*Cost:* reallocation, not new spend.

**8. Skill-document optimization — last, and only in the conditional form of §12.**
*Evidence against as a *capability* lever:* SkillOpt +0.1 pp on repo-level codegen (✅ PRIMARY); no repo-level benchmark in SkillOpt/GEPA/Trace2Skill/EvoSkill (✅ PRIMARY, predecessor); content-independence at scale (✅ PRIMARY, Guardrails); architecture rules lowest of five types (✅ PRIMARY); pre-registered null for procedural skill content vs a labels-only scaffold (✅ PRIMARY); the 4–5-item gate cannot reach significance, ever (§7.3a).
*Evidence for as a *conformance/efficiency* lever:* maintainer-recognized project knowledge and halved wall-clock in Skill Issue; 173 s → 142 s in gskill; −28.64% runtime in Lulla et al.; −24% wall-clock on opshin (p = 0.125, n = 5 — i.e. real but unproven).
*Cost:* one reflection call + one gate per iteration. **Cheaper than best-of-k, so it is not "too expensive" — it is *unproven on the outcome the platform cares about*.**

---

## 9. Compute-cost table (all methods, one view)

| Method | Weight updates? | Rollouts / samples | Compute / money | Reported gain | Source & tag |
|---|---|---|---|---|---|
| Deterministic compliance scoring | No | 0 | ~0 | Instrument, not a gain | ✅ [compliance.py](../backend/app/orchestrator/stages/compliance.py) |
| Negative constraints as gates/hooks | No | 0 | 0 | Polarity result; −20 pp if top rule removed | ✅ [Guardrails](https://arxiv.org/html/2604.11088v2) |
| Best-of-k + execution verification | No | k=5 → 15.9→29.62%; k=16 → +15 pp | 5× cheap gen = 1/3 of 1 frontier sample; 16 gen | +13.7 pp (k=5); +15 pp (k=16) | ✅ [LLM](https://ar5iv.labs.arxiv.org/html/2407.21787), [R2E-Gym](https://ar5iv.labs.arxiv.org/html/2504.07164) |
| CodeT (generated-test selection) | No | 100 samples/problem | 100 gen | 47.0 → 65.8 pass@1 HumanEval | ✅ [CodeT](https://ar5iv.labs.arxiv.org/html/2207.10397) |
| Self-consistency / majority vote | No | plateaus ~100 | large | 40.50 → 41.41 (100→10k) | ✅ [LLM](https://ar5iv.labs.arxiv.org/html/2407.21787) |
| Agentless | No | 4 calls/task | $0.70/task | 32.00% Lite; 34.0% Verified (1.5) | ✅ predecessor / R2E-Gym Table 4 |
| Self-repair / Reflexion-style | No | 1–3 rounds | linear | *"modest … sometimes not present at all"* | ✅ predecessor |
| **gskill (GEPA + SWE-smith)** | No | **<300 rollouts**, ~300 tasks | hundreds of gen | **24→93, 55→82**; transfer | ✅ author blog |
| **GEPA** | No | budget `B`; "a few rollouts"; up to 35× fewer than 24k | offline, amortized | +6% avg over GRPO; +13% over MIPROv2; NPUEval 4.25→30.52 | ✅ primary (abstract) / ⚠️ secondary (NPUEval numbers) |
| **RoboPhD** | No | **1,500 evaluations total**, validation-free Elo | 1,500 evals | beats GEPA on 3/4; ARC 27.8→65.8 | ✅ [2604.04347](https://arxiv.org/abs/2604.04347) |
| **SkillOpt** | No | 4 epochs × batch 40; 0.6M–46.4M tok/point | offline | +19…+25 (no codegen benchmark) | ✅ predecessor §1.1 |
| DSPy MIPROv2 / BootstrapFewShot | No | docs: *"only 5 or 10 examples"* | offline | framework | ✅ predecessor §1.4 |
| Trace2Skill | No | 400 samples (200/200) | offline | +57.65 pp transfer | ✅ predecessor §1.3 |
| EvoSkill / AutoRefine | No | not extracted | offline | +7.3 / +12.1; 80.56% vs 50.0% | ✅ predecessor §1.4 |
| TextGrad | No | iterations | offline | 20% relative LeetCode-Hard | ⚠️ secondary (carried) |
| Voyager | No | many GPT-4 iterations | API calls | 3.3× items; library transfers | ✅ predecessor §2.4 |
| **RL: SWE-RL / SWE-Gym / R2E-Gym / SkillRL / SAGE** | **Yes** | 10⁴–10⁵ rollouts; 8.7K tasks | GPUs | 41.0% Verified; +19%; 34.4% | ✅ predecessor §2 |

---

## 10. What I would tell the platform (short)

1. **Keep the loop; change the metric.** The conformance score (`100 − penalty`) and the constraint-trace rate are already implemented, deterministic, and about the thing the seed skill actually claims to control. The build exit code is a low-distinguishability, gameable verifier (R2E-Gym; SWE-bench+ 31.08% weak-test passes).
2. **Accept that the 5-blueprint gate cannot produce evidence.** Arithmetic floor: p = 0.0625 with all five flipping; sign-flip floor identical. Mine ≥120 held-out specs from recorded sessions before any inferential claim.
3. **Do not expect a resolve-rate gain from a skill document.** The one direct test of SkillOpt on repo-level codegen returned +0.1 pp. Expect, at most, **conformance and cost** — where the positives are consistent (wall-clock halved / −24% / 173 s→142 s) but individually underpowered.
4. **Flip the polarity of the whole artifact.** Every individually beneficial rule ever measured is a "do not". The seed skill's layering content should be prohibitions.
5. **Do not add positive architecture directives.** Architecture is the *worst* of five rule types (53.4%). Encode layering as a build-time gate plus prohibitions.
6. **Spend the next dollar on best-of-k, not on skill optimization.** Five cheap samples through the free verifier is +13.7 pp at 1/3 the price of one frontier sample. That is the largest, most verified, smallest-n result in this entire literature, and it uses exactly the asymmetry the platform has.
7. **Run the ablation that has never been run.** A skill document optimized against a *deterministic conformance instrument*, with a length-matched irrelevant-fragment placebo, is the missing experiment in the literature and the only version of this idea that is both untested and plausibly positive.

---

## 11. What I could not verify

1. **GEPA §5.1 in full (NPUEval/KernelBench).** The arXiv HTML exceeds the 5 MB fetch cap; the ICLR 2026 camera-ready is a PDF (`unsupported content type "application/pdf"`); the r.jina.ai rendering truncated before §5. The 4.25% → 30.52% figures, the condition table, GEPA's rollout count on NPUEval, the train/val split sizes, and the text of the optimized kernel prompt are therefore **⚠️ SECONDARY** (a 2026-09-27 conference-talk report) or carried from the predecessor. **PRIMARY-only claims about GEPA's code work: that it is called *"preliminary"*; that it is framed as *"an inference-time search strategy for code optimization"*; and that it exists at all.**
2. **Gloaguen v2 §4.2–§5, Appendix A.5 (statistics) and Appendix B (instruction categories).** Same fetch limitation; the r.jina.ai proxy returned an SVG for that URL. I verified the v2 **abstract, introduction, §3 and §4.1**, and the **section headings** *"Neither context file length nor specific instruction categories have a strong effect on performance"* and *"No specific categories in LLM-generated context files help significantly"*. **The list of categories tested, per-category effects, and the v2 significance appendix are UNVERIFIED.** I read the **v1** full text instead, via ar5iv, and record the v1↔v2 numeric divergence explicitly.
3. **Guardrails §6.4 (4b, 4c) and §7 beyond the quoted passage, and Appendix A's 18-rule list.** Truncated at §6.4. The polarity, priming, ensemble and architecture-type numbers above are from the sections I did read.
4. **The evidence behind Gloaguen's "useful for specifying non-standard coding practices".** It appears in the v2 abstract and introduction as a conclusion; **I could not locate a dedicated experiment for it** in the text I could read. The predecessor treats it as a finding; I would treat it as the authors' prescription, supported indirectly by the documentation-removed condition (+2.7%) and the "only include what is not in the README" recommendation. **Flagging this is a correction to the predecessor's framing.**
5. **SkillOpt's released code** (`aka.ms/skillopt`) and Skill Issue's supplementary material — not inspected.
6. **Anthropic's "5–15 samples per task" Terminal-Bench methodology** — carried from the predecessor as PRIMARY there; not re-verified here.
7. **No falsification of the *medium*.** The searches listed in §6 returned no paper, position paper, or survey concluding that skill/context-document optimization cannot work for code generation. Absence of falsification is not support.
8. **No study exists of skill-document optimization for a framework-specific *enterprise* standard** (Spring Boot layering, microservice conventions), nor of any setup with a free local verifier and a zero-marginal-cost gate.
9. **CodeT's small-n selection curve.** I verified pass@1/pass@2/pass@10 *after selection from 100 samples*; I did not obtain a curve for selection from n ∈ {2…8}.
10. **RoboPhD** — abstract only; its per-benchmark tables and the GEPA/Autoresearch head-to-head numbers were not read.
11. **gskill** — an author blog post, not peer-reviewed; its task suite (SWE-smith) is exactly what Skill Issue argues is too easy to be informative. I report it as PRIMARY (the authors' own artifact) but with that validity caveat attached.
12. **Trace2Skill / EvoSkill / AutoRefine / TextGrad / Voyager / SkillOpt mechanism numbers** — carried from the predecessor, not independently re-read in this dive.

---

## 12. VERDICT

# CONDITIONALLY OPEN

**with a hard sub-verdict: for the goal "raise the resolve rate of this generator by optimizing a skill document, measured on the five existing blueprints", the answer is effectively CLOSED — it is both evidentially null and arithmetically unmeasurable.**

### Why not CLOSED outright

- The question has been asked exactly once for this exact combination, and it returned a **null, not a refutation**: SkillOpt **+0.1 pp**, GEPA **+4.9 pp**, *neither statistically significant*, on 20–26 held-out tasks per repository, with the authors explicitly attributing the difficulty to the instrument rather than the method. **PRIMARY.**
- **The artifacts did carry real value the pass rate could not see**: a maintainer found *"knowledge one only gets by working in the project"*, and both documents **halved wall-clock time** and cut cost. **PRIMARY.**
- The **largest** reported skill-document codegen gain (24 → 93 on Bleve, <300 rollouts, transferable to Claude Code) came from the *same family of methods*, on an unfamiliar repository with a weak agent. **PRIMARY.**
- **Nobody has tested the version of the idea that this platform could actually win with**: a deterministic conformance instrument, a free verifier, negative-constraint content, a seed-relative objective, and enough mined assets.

### Why not OPEN outright

- The only direct test of the SkillOpt proposer on repository-level codegen is a null (§2.3).
- Three independent large-N studies find **procedural/context content is not the causal variable**: random = curated at 63.8%, mismatched > matched, shuffled ≈ unshuffled, *"no condition is significantly different from any other"*, and *"automated rule optimizers should target structural properties rather than semantic content."* **PRIMARY.**
- A **pre-registered** ablation found a code-generation skill's procedural content adds **no separable execution-correctness benefit over a labels-only scaffold**. **PRIMARY.**
- The platform's seed skill is an **architecture** skill, and architecture rules scored **53.4% — the lowest of five types** against a 50.0% baseline. **PRIMARY.**
- SkillOpt has **zero** repo-level codegen benchmarks and **zero** significance tests in its own paper (predecessor, PRIMARY).
- The 5-asset gate **cannot reach significance under any outcome** (§7.3a–b).

### The conditions (all of them must hold for the lever to be worth pulling)

| # | Condition | Evidence |
|---|---|---|
| **C1** | The target is **conformance and/or cost**, not resolve rate on tasks the model can already do | Skill Issue (halved wall-clock, +0.1 pp score); gskill (173→142 s); opshin (−24 %, p=0.125); Lulla (−28.64 % runtime) |
| **C2** | The edited content is **non-discoverable house knowledge**, not generic advice | Gloaguen (docs-removed +2.7 %); Guardrails (mismatched > matched; content-independent) |
| **C3** | Edits are **negative constraints** | Guardrails (all shaping = "do not"; all distorting = "do") |
| **C4** | Layering is encoded as a **build-time gate**, with the document only reinforcing it | Guardrails (architecture 53.4 %); Gloaguen (+20 % cost, followed faithfully) |
| **C5** | The metric is the **deterministic conformance score**, not the build exit code | R2E-Gym (low distinguishability); SWE-bench+ (31.08 % weak-test passes); Gameability |
| **C6** | Scoring is **seed-relative on the same asset** | Skill Issue (their core methodological contribution) |
| **C7** | The proposer is **GEPA-style budgeted rewrite with Pareto/Elo selection**; the strict-improvement gate is removed or demoted to a regression filter | gskill (<300 rollouts); RoboPhD (validation-free Elo beats GEPA at 1,500 evals); Skill Issue (the strict gate on a tiny split is what stalled) |
| **C8** | **≥ 6 assets** to clear the arithmetic floor; **≥ 55** for a large effect; **~120–200 paired** for a 10 pp effect; **≥ 32** for a small continuous effect | §7.3 |
| **C9** | The optimizer is **not** measured on a saturated target (agent already ≈ 100 %) | Skill Issue (Sonnet 4.5 at 100 % leaves nothing to move); two-agent (floor/ceiling) |
| **C10** | The verifier is **adversarially guarded** (assertion strength, mutation checks, fallback exclusion) | SWE-bench+ (31.08 %); LLM (11.3 % flaky); R2E-Gym (low distinguishability) |
| **C11** | Optimization is done **against the shipped agent and harness**, with no transfer assumption | Skill Issue (*"we drop the transfer assumption and optimize directly against the agent we intend to ship"*) |
| **C12** | Success is defined as a **pre-registered MDE**, and "not measurable" is an allowed outcome | §7.3; two-agent opshin |

### The honest expected-value statement

**Skill-document optimization is a cheap, low-ceiling, largely unproven lever on the axis this platform most wants to move (does the generated service work), and a cheap, plausible lever on the axis it can actually measure (does the generated service follow the house standard, and how much does it cost to produce).** The adjacent evidence on *procedural content* is null or content-independent in four independent 2026 studies; the one study that ran this exact loop on repository code returned +0.1 pp for SkillOpt. There is **no falsification** of the medium, but there is also **no powered positive**, and under the current 5-blueprint instrument the question **cannot be answered at all**. The highest-expected-value zero-compute action is **best-of-k selection through the free verifier, ranked by a composite of the deterministic compliance score and the build result** — that is the only lever in this literature with a large, verified, *small-n* gain (15.9 % → **29.62 % at k = 5**, at **one third** the cost of a single frontier sample), and it uses the platform's free-verification asymmetry exactly as it should be used. Skill optimization should be kept, demoted to a **conformance-and-cost** device with negative constraints, measured by the deterministic score, and honestly reported as directionally positive at best until ≥120 mined assets exist.

If the honest answer is required in one sentence: **this is untested in the setting that matters, the adjacent evidence is null-to-content-independent, so the expected value of optimizing the skill document is low; the expected value of spending the same inference budget on verified best-of-k through the free verifier is high.**
