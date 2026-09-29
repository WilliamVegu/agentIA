# Agent Skill Optimization — State of the Art (mid-2026)

**Date:** 2026-09-28
**Subject:** Is "skill optimization as a layer for creating code-generating agents" a state-of-the-art premise?
**Method:** Primary sources only — arXiv abstracts and full HTML, official vendor docs and repos. Every claim carries a source link and a verification tag. All URLs accessed **2026-09-28**.
**Scope note:** Read-only literature analysis. No source file was modified except this report. Raw fetched copies of the cited pages were kept in a temporary scratch directory and deleted.

**Verification legend**

| Tag | Meaning |
|---|---|
| ✅ **PRIMARY** | I read the claim in the paper's own abstract/full text, or the project's official docs/repo. |
| ⚠️ **SECONDARY** | The number comes from an aggregator/blog, not the owning source. Treat as indicative only. |
| ❌ **UNVERIFIED** | I could not confirm this. Stated as unverified, never as fact. |

**Access caveats (declared up front)**

- `swebench.com` is a client-side application; its leaderboard did not render to text for me. All frontier-repo-benchmark numbers below are therefore either vendor-published or explicitly marked ⚠️ SECONDARY. I did **not** verify the official leaderboard directly.
- `morphllm.com/swe-bench-pro` was behind a Vercel bot checkpoint — **not retrieved**.
- I did not read any paper's PDF-only appendix where an HTML version existed; HTML views are labelled. The one place this matters (GEPA's "Criticisms and Limitations") I checked and could not locate in the HTML rendering — see §7.

---

## 0. Bottom line

The premise — *"apply SkillOpt as an optimization layer for just creating agents that do code"* — is **half right, and the half that is wrong is the half that matters.**

What is genuinely state of the art:

- **Text-space optimization of *procedural* artifacts is a real, active 2026 research line**, and SkillOpt is a legitimate member of it with strong reported numbers on its own benchmarks (§1).
- **The gate is the load-bearing idea**, and the platform's implementation gets that right (§1.4, §5).
- **RL on skill libraries is also real and is *not* the same thing as text-space optimization** — it requires weight updates, and where it has been compared head-to-head with prompt/memory baselines it wins (§2, §3).

What is not supported by the evidence:

1. **There is no evidence that optimizing a skill *document* improves repo-level code generation.** SkillOpt — the paper the design is drawn from — evaluates **zero** repo-level coding benchmarks. Its one code-adjacent benchmark is SpreadsheetBench (spreadsheet code via `openpyxl`/`pandas`), and its own §4.2 conclusion is that "the gains are largest on **procedural** benchmarks, where reusable rules about tool use and output formatting matter most" ([SkillOpt §4.2](https://arxiv.org/html/2605.23904v2)). Not one of Trace2Skill, EvoSkill, or GEPA's six headline tasks is a SWE-bench-style task (§1).
2. **The strongest 2026 controlled evidence on exactly this intervention — putting a rule/skill document in front of a coding agent — is negative or content-independent** (§4.2). Two independent 2026 studies find context files do not move task success ([Gloaguen et al.](https://arxiv.org/abs/2602.11988), [two-agent ablation](https://arxiv.org/abs/2607.27250)); a third finds random rule files match expert-curated ones ([Guardrails Beat Guidance](https://arxiv.org/html/2604.11088v2)).
3. **The gate as implemented cannot detect the effect it is gating.** With 4 or 5 tasks per iteration, the *most favourable possible* two-sided exact test gives p = 0.0625 (n=5) or p = 0.125 (n=4); with identical configurations, a paired re-run shows a spurious "strict improvement" 61–76% of the time (§5.2). The repo's own spec already says this — it is recorded as an accepted residual "acceptable for validating the loop; not acceptable for a production optimiser" ([specs/014-skillopt-compact/plan.md:133](../specs/014-skillopt-compact/plan.md)).
4. **The mechanisms omitted from the "minimal" loop are the ones SkillOpt's own ablations say matter most.** Removing the epoch-wise meta+slow update costs **−22.5 points** on SpreadsheetBench in SkillOpt's own component ablation; removing the rejected-edit buffer costs −1.6/−4.6/−2.4 points (§1.4). The minimal loop keeps the edit budget and the gate and drops the stabilisers.

The requester's instinct that "some of this is done numerically with RL, in the same style" is **correct** — SkillRL and SAGE are exactly that, and they beat prompt-based skill libraries (§2.1, §3.2). But that comparison also shows the price: those methods train the policy.

**Honest one-line answer to the premise:** as a *layer for creating code-generating agents*, text-space skill optimization is a **reasonable engineering bet under specific conditions** (verifiable per-step procedures, a compliance gap rather than a knowledge gap, and an evaluation set big enough to measure), and it is **not** the state of the art for raising a coding agent's resolve rate on real repositories. For that, the evidence points to model capability, then harness/test-time compute with execution verification, then RL post-training — with skill documents somewhere below, mostly as a *consistency* device rather than a *capability* device.

---

## 1. Text-space / prompt-space optimization of agent procedures

### 1.1 SkillOpt — the paper the design is drawn from

✅ **PRIMARY** — [arXiv:2605.23904](https://arxiv.org/abs/2605.23904) (v2, 25 May 2026), read in full at [arxiv.org/html/2605.23904v2](https://arxiv.org/html/2605.23904v2).

**What is optimized:** a single natural-language skill document inserted into the agent's context. Quoting the paper: *"We argue the skill should instead be trained as the external state of a frozen agent"* and *"a separate optimizer model turns scored rollouts into bounded add/delete/replace edits on a single skill document, and an edit is accepted only when it strictly improves a held-out validation score."* The deployed artifact is `best_skill.md`, **379–1,995 tokens** (median ≈920) after **1–4 accepted edits** (median 2.5).

**What is frozen:** the target model, the harness, and the evaluator. *"the adapted model and execution harness remaining fixed"*; *"adding zero inference-time model calls at deployment."* A separate frontier optimizer model does the editing offline.

**Full mechanism (defaults, §4.1):** 4 epochs; rollout batch 40; reflection minibatch 8 with 16 parallel analysts and merge batch 8; textual learning rate `L_t = 4` with cosine decay to floor 2 (constant/linear/cosine/autonomous schedules supported); held-out validation gate that accepts **only strict improvement (ties rejected)**; slow update sampling 20 tasks per epoch; optimizer-side meta skill; rejected-edit buffer of recent failed proposals; `patch` edit mode; up to 3 teacher refinement rounds per minibatch.

**Reported gains (abstract + §4.1):**
- Best-or-tied on **52/52** (model, benchmark, harness) cells.
- GPT-5.5 average lift over no-skill: **+23.5** (direct chat), **+24.8** (Codex), **+19.1** (Claude Code).
- Beats the strongest per-cell competitor (human skill, one-shot LLM skill, Trace2Skill, TextGrad, GEPA, EvoSkill) by **+5.4** points on average (82.3 vs an oracle baseline of 76.9).
- Average per-model improvement ≈**+17.6** points across seven direct-chat target models.

**Benchmarks (§4.1):** SearchQA, SpreadsheetBench, OfficeQA, DocVQA, LiveMathematicianBench, ALFWorld. **This is the critical fact for the premise:** the suite is *"single-round QA … multi-turn tool loops with up to 24 tool calls (OfficeQA), multi-round codegen with up to 30 turns and a real openpyxl/pandas runtime (SpreadsheetBench), and persistent embodied interaction … (ALFWorld)."* **There is no SWE-bench, no repository-level task, no test-suite-verified patch generation.** The only code-producing benchmark is spreadsheet manipulation.

**Splits (§4.1 and Appendix C):** dataset-backed benchmarks use deterministic train/selection/test splits, `split_seed=42`; 4:1:5 in Table 2's ablations and a default **2:1:7** split in Appendix C. The selection split is *"used only to accept or reject candidate skill edits"*, and all headline scores are on the disjoint test split. ALFWorld is the one benchmark whose split sizes are stated: **39 train / 140 selection / 134 test** environments. LiveMathematicianBench has 35 training items per epoch.

**Cost (§4.4):** 0.6M–46.4M training tokens per absolute test point, paid offline and amortised across reuse.

**Component ablations (§4.2, Table 3) — directly relevant to the platform's "minimal loop":**
- Removing the **rejected-edit buffer** costs **1.6 / 4.6 / 2.4** points on SearchQA / SpreadsheetBench / LiveMath.
- Removing **both meta skill and slow update** drops SpreadsheetBench from **77.5 → 55.0 (−22.5 points)**, *"the largest degradation in the ablation suite."*
- Unbounded rewriting without a learning-rate budget scores **84.6 / 75.7 / 57.3** vs the default **86.5 / 78.2 / 56.5** — i.e. the budget helps on 2 of 3.
- SearchQA L_t sweep: *"the lowest score across all five settings is still only 85.5"*; schedules constant/cosine/linear score 87.3 / 87.1 / 87.2 — the specific scheduler does not matter much.
- **Data-scale ablation (Table 2a):** SpreadsheetBench climbs **47.5 → 78.0** and LiveMath **59.1 → 70.5** as the optimizer sees 1% → 100% of the training partition; SearchQA saturates at ~84–86 after 20%. The paper's own reading: *"procedural benchmarks reward more training evidence"* and the gains are *"a genuine effect of having enough scored evidence per update."* **This is a data-quantity result for the *reflection* input, not for the *gate*** — the paper does **not** ablate the size of the selection split.

**Transfer (§4.3):** cross-model positive on all 4 genuine transfers (+9.4, +3.0, +4.5, +5.6); cross-harness Codex→Claude Code +59.7 on SpreadsheetBench (22.1→81.8) and Claude Code→Codex +43.6 (27.5→71.1); cross-benchmark OlympiadBench→Omni-MATH +3.7/+1.8/+1.3.

**Limitations, quoted verbatim from Appendix B:**

> *"the optimization loop relies on scored trajectories and a held-out selection split, so it is most directly applicable when the target task has automatic verifiers, exact-match metrics, executable checks, or otherwise reliable feedback signals. For open-ended domains where success is subjective, multi-dimensional, or costly to judge, the validation gate may require stronger human or model-based evaluation."*
>
> *"although the deployed artifact is only a compact best_skill.md, training the skill requires additional rollout computation and calls to an optimizer model; this cost is amortized when the same skill is reused, but may be less attractive for one-off tasks."*
>
> *"SkillOpt intentionally optimizes a single portable skill rather than growing a large skill library or changing model weights … a single skill may be insufficient for highly heterogeneous domains that require many disjoint procedures."*
>
> *"optimized skills can encode domain-specific heuristics from the training distribution, so careful held-out evaluation remains necessary before transferring them to substantially different models, harnesses, or task settings."*

**Statistical reporting — a verified absence.** I searched the full text for `signific` and found **0 occurrences**. There is no p-value, confidence interval, hypothesis test, bootstrap, or error bar anywhere in the paper. Per-cell results are single numbers; seeds are not varied for the main table (a fixed `split_seed=42`). See §5.

### 1.2 GEPA — the paper that actually beat RL

✅ **PRIMARY** — [arXiv:2507.19457](https://arxiv.org/abs/2507.19457) "GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning", read at [arxiv.org/html/2507.19457](https://arxiv.org/html/2507.19457).

**What is optimized:** the *prompts* of a compound AI system (including multi-module systems), via reflective mutation + Pareto-frontier evolutionary search. **Frozen:** *"GEPA evolves only the set of prompts, denoted as Π_Φ, whereas the underlying LLM weights, denoted by Θ_Φ remains fixed."*

**The exact claim (abstract, verbatim):** *"Across six tasks, GEPA outperforms GRPO by 6% on average and by up to 20%, while using up to 35x fewer rollouts. GEPA also outperforms the leading prompt optimizer, MIPROv2, by over 10% (e.g., +12% accuracy on AIME-2025), and demonstrates promising results as an inference-time search strategy for code optimization."*

**The six tasks (§4):** AIME-2025, LiveBench-Math, HotpotQA, IFBench, HoVer, PUPA. Models: Qwen3 8B and GPT-4.1 Mini. **None of the six is a coding task.**

**Caveats the paper itself states:**
- The GRPO baseline is *"GRPO (24,000 rollouts)"* on Qwen3 8B.
- Table 1's own caption: *"GEPA and GEPA+Merge achieve better performance than GRPO with far fewer rollouts on **all benchmarks except AIME**."*
- Per-task margins: *"exceeds GRPO on 5 out of 6 tasks by 19.0%, 2.73%, 13.66%, 5.19% and 0.7%."* So the "up to 20%" is a single-task maximum; the "6% average" includes one loss.
- LiveBench-Math is n=368, *"split equally into train/val/test."*
- The code results are explicitly preliminary: NPUEval (AMD XDNA2 kernels) and KernelBench (CUDA) with GPT-4o, and *"these are early results and warrant further systematic study."* Even so, they are striking and directly relevant to the knowledge-vs-procedure question: GPT-4o + 10 sequential refinements reaches **4.25%** mean vector utilization; adding RAG from technical manuals raises it to **16.33%**; adding MIPROv2 to that reaches **19.03%**; **GEPA's optimized prompt (no RAG at runtime) reaches a mean of 30.52%**, and a single GEPA prompt gives **26.85%**. On KernelBench's 35-task representative subset, GEPA lifts GPT-4o's near-0% `fast_1` to **above 20%**.
- One honest read of that NPUEval result: GEPA's optimizer had retrieval in its *feedback loop*, so its prompt plausibly **encodes** the manual knowledge. It is not a clean "procedure beat knowledge" result — it is evidence that *text-space optimization can distil domain knowledge into a portable procedural artifact*. That is a more interesting and more defensible claim than the naive one.

❌ **Could not verify:** GEPA's own "Limitations" section. The HTML rendering I retrieved did not contain it; what I found under a "Criticisms and Limitations" heading was appendix example text about a political-science question, not the paper's limitations. I therefore report no GEPA limitations of my own.

### 1.3 Trace2Skill — **two different papers with the same name**

✅ **PRIMARY** — both verified as distinct:

1. **Trace2Skill: Distill Trajectory-Local Lessons into Transferable Agent Skills** — [arXiv:2603.25158](https://arxiv.org/abs/2603.25158), code at [github.com/Qwen-Applications/Trace2Skill](https://github.com/Qwen-Applications/Trace2Skill).
   - **What is optimized:** a *skill directory*, consolidating broad execution trajectories *in parallel* by inductive reasoning; supports deepening a human-written skill or creating one from a weak LLM draft.
   - **Frozen:** no parameter updates, no test-time retrieval.
   - **Benchmarks:** SpreadsheetBench-Verified (400 samples → **200 evolution / 200 held-out test**), plus OOD table-QA transfer to WikiTableQuestions and HiTab; the abstract also lists math reasoning and vision QA.
   - **Headline gain (abstract):** *"skills evolved from Qwen3.5-35B trajectories improve a Qwen3.5-122B agent by up to 57.65 percentage points on WikiTableQuestions."*
   - **Rigour — better than SkillOpt on this axis:** *"All spreadsheet results are averaged over three random seeds"* (41, 42, 43), with a **per-seed standard-deviation table** (Table 7). The paper reports *"The summary metric Avg is stable (standard deviation ≤ 3.4 in every row)"* and notes higher variance in individual columns because *"each score aggregates long agentic rollouts that often exceed 30 turns."* Std ranges for other results: DAPO-Test 1.1–2.4, AIME'26 1.8–3.4, DocVQA ANLS 0.034–0.139.
   - **The most useful negative result in the skill literature (Appendix C.2, verbatim):** *"each addition simultaneously fixes and breaks tasks"* — one materialised step recorded **57 fail-to-pass against 21 pass-to-fail**, another **26 against 46**. *"Because each greedy step both fixes and breaks tasks, the net accuracy plateaus instead of rising. A locally best single patch therefore does not compose into a global gain: patch value depends on how additions interact."*

2. **Trace2Skill: Verifier-Guided Skill Evolution for Long-Context EDA Agents** — [arXiv:2605.21810](https://arxiv.org/abs/2605.21810). Electronic-design-automation / RTL-Verilog context. ✅ exists as a separate paper; **not** the one cited by SkillOpt. Not a repo-level codegen benchmark.

### 1.4 The rest of the family

| Method | What it optimizes | Frozen | Reported gain | Benchmark | Source |
|---|---|---|---|---|---|
| **TextGrad** | free-text "gradients" into any variable in a computation graph (prompts, code, molecules) | the model | GPQA zero-shot 51%→55%; **20% relative gain on LeetCode-Hard solutions** | GPQA, LeetCode-Hard, molecule design, radiotherapy | ✅ [arXiv:2406.07496](https://arxiv.org/abs/2406.07496) |
| **EvoSkill** | skill *folders* (workflows + code), via iterative failure analysis, Pareto-frontier selection on held-out validation | *"the underlying model remains frozen"* | OfficeQA **60.6%→67.9% (+7.3)**; SealQA **26.6%→38.7% (+12.1)**; zero-shot SealQA→BrowseComp **+5.3** | OfficeQA, SealQA, BrowseComp | ✅ [arXiv:2603.02766](https://arxiv.org/abs/2603.02766), repo [sentient-agi/EvoSkill](https://github.com/sentient-agi/EvoSkill) |
| **AutoRefine** | *typed* artifacts — Rule, Skill, or bounded Subagent — compiled from failed-vs-successful trajectory contrast, with a **type-specific contract gate + a replay gate** | not stated explicitly; GPT-5.6-terra as backbone | TravelPlanner **80.56% vs 50.0%** strongest baseline; removing **boundary closure** costs **15.00 pts**, removing **replay validation** costs **16.11 pts** | ALFWorld, ScienceWorld, TravelPlanner, SpreadsheetBench, SkillCraft | ✅ [arXiv:2601.22758](https://arxiv.org/abs/2601.22758) |
| **DSPy optimizers (MIPROv2, BootstrapFewShot, GEPA, BootstrapFinetune)** | "the prompts **and/or** the LM weights" — one framework spans both spaces | varies by optimizer | not a single headline number; the docs position these as composable | framework | ✅ [dspy.ai optimizers docs](https://dspy.ai/learn/optimization/optimizers/) |
| **SkillClaw** | skills evolving collectively via an agentic evolver | — | not read | — | ✅ exists: [arXiv:2604.08377](https://arxiv.org/abs/2604.08377), cited as [21] in SkillOpt |

**Two things worth extracting from this table.**

First, **AutoRefine is a direct argument against the minimal loop.** It reports that removing the *replay gate* — an admission check that the edit does not regress already-solved cases — costs **16.11 points**, the second-largest loss among its policies. SkillOpt's rejected-edit buffer and Trace2Skill's flips analysis point the same way (§1.3). A single forward-only gate with no regression memory is the weakest form of the idea.

Second, **the DSPy docs contradict the "you need a big held-out set" intuition — but only for a different mechanism.** The official docs state an optimizer takes *"a few training inputs. This may be very small (i.e., only 5 or 10 examples) and incomplete (only inputs to your program, without any labels)."* ✅ [dspy.ai](https://dspy.ai/learn/optimization/optimizers/). That is a claim about *few-shot example synthesis / instruction proposal*, where a handful of traces can be enough to propose a good prompt. It is **not** a claim that a 4-task accept/reject gate can *detect* a real improvement. The two things are routinely conflated and should not be.

---

## 2. RL-based approaches to the same problem

The requester is right that this exists and is the "same style". It splits into two very different families.

### 2.1 RL that trains a skill library (requires weight updates)

✅ **PRIMARY** — **SkillRL: Evolving Agents via Recursive Skill-Augmented Reinforcement Learning**, [arXiv:2602.08234](https://arxiv.org/abs/2602.08234) (Feb 2026), code [aiming-lab/SkillRL](https://github.com/aiming-lab/SkillRL).
- Builds a hierarchical **SkillBank** by distilling trajectories, with adaptive retrieval, and *"a recursive evolution mechanism that allows the skill library to co-evolve with the agent's policy during reinforcement learning."*
- **Requires weight updates** (it is an RL training method; GRPO-based).
- Results: **89.9% ALFWorld**, **72.7% WebShop**; *"outperforming strong baselines over 15.3%"*; **+12.3 absolute over its own GRPO base on ALFWorld (77.6 → 89.9)**; search-augmented QA average 47.1% vs Search-R1 38.5% and EvolveR 43.1%.
- Crucially, it benchmarks **against text-space methods**: *"Prompt-based Agentic or Memory-based Methods … ReAct, Reflexion, Mem0, ExpeL, MemP, which utilize external memory or experience pools to guide behavior **without parameter updates**."* Its own reading: *"while in-context learning can leverage past experiences, it often fails to distill actionable knowledge from verbose trajectories or fundamentally adapt the agent's policy."*
- Also notable: **MemRL**, which *"uses RL solely to update its memory bank while keeping the policy frozen"*, reaches only **21.4%** on ALFWorld — i.e. RL on a frozen policy underperforms substantially.
- ⚠️ **Benchmarks are ALFWorld/WebShop/search QA — not code generation.**

✅ **PRIMARY** — **Reinforcement Learning for Self-Improving Agent with Skill Library (SAGE)**, [arXiv:2512.17102](https://arxiv.org/abs/2512.17102) (Dec 2025, v2 Mar 2026; also [ACL 2026 long paper](https://aclanthology.org/2026.acl-long.69.pdf)).
- *"Skill Augmented GRPO for self-Evolution"* — Sequential Rollout across a chain of similar tasks so skills accumulate; a skill-integrated reward.
- Results on AppWorld: **+8.9% Scenario Goal Completion**, **−26% interaction steps**, **−59% tokens**.
- **Requires weight updates.**

### 2.2 RL fine-tuning for tool use and procedure following (requires weight updates)

✅ **PRIMARY** — **ToolRL: Reward is All Tool Learning Needs**, [arXiv:2504.13958](https://arxiv.org/abs/2504.13958): *"the first comprehensive study on reward design for tool selection and application tasks within the RL paradigm"*; GRPO-trained; **+17% improvement over base models and +15% gain over SFT models** on tool-use benchmarks. Requires weight updates.

### 2.3 RL for software engineering specifically (requires weight updates, and it works)

✅ **PRIMARY** — these are the strongest *measured* interventions for real repo-level coding:

| Method | Base model | Training | SWE-bench result | Source |
|---|---|---|---|---|
| **SWE-RL** | Llama 3 70B | GRPO on open-source software-evolution data, rule-based reward (patch similarity) | **41.0% solve rate on SWE-bench Verified** — *"the best performance reported for medium-sized (<100B) LLMs to date"*; also improves 5 OOD tasks whereas an SFT baseline *"even leads to performance degradation on average"* | ✅ [arXiv:2502.18449](https://arxiv.org/abs/2502.18449) |
| **SWE-Gym** | — | 2,438 executable Python task instances; trains agents, then trains verifiers on agent trajectories | **up to 19% absolute gains** in resolve rate; combined with inference-time verifiers, **32.0% Verified / 26.0% Lite** — *"a new state-of-the-art for open-weight SWE agents"* | ✅ [arXiv:2412.21139](https://arxiv.org/abs/2412.21139) |
| **R2E-Gym / AgentGym** | 32B | 8.7K procedurally curated executable tasks; pass@1 **34.4%** on Verified | **51% on SWE-bench Verified** when combined with hybrid test-time scaling (execution-based + execution-free verifiers) | ✅ [arXiv:2504.07164](https://arxiv.org/abs/2504.07164) |

Note the R2E-Gym detail that matters for any gate design: *"Test-based verifiers suffer from low distinguishability, while execution-free verifiers are biased and often rely on stylistic features. Surprisingly … while each approach individually saturates around 42–43%, significantly higher gains can be obtained by leveraging their complementary strengths."* A build-exit-code gate is a *test-based verifier of the weakest kind*, and this paper says test-based verifiers have low distinguishability.

### 2.4 RL-free skill libraries (text/code artifacts, no weight updates)

✅ **PRIMARY** — **Voyager**, [arXiv:2305.16291](https://arxiv.org/abs/2305.16291): *"an ever-growing skill library of executable code"* plus automatic curriculum and iterative prompting with environment feedback and self-verification. **Explicitly no fine-tuning:** *"Voyager interacts with GPT-4 via blackbox queries, which bypasses the need for model parameter fine-tuning."* Results: **3.3× more unique items, 2.3× longer distances, up to 15.3× faster tech-tree milestones** than prior SOTA in Minecraft; library transfers to a new world. The skills here are **executable code**, not prose — which is a meaningfully stronger and more verifiable artifact than a markdown rule.

### 2.5 The limits of RL, from RL's own critics

✅ **PRIMARY** — **[Yue et al., arXiv:2504.13837](https://arxiv.org/abs/2504.13837)**: *"as RLVR training progresses, the average performance (i.e., pass@1) improves, but the coverage of solvable problems (i.e., pass@256) decreases, indicating a reduction in LLM's reasoning boundary."* And: *"RLVR does not introduce fundamentally new reasoning capabilities and that the reasoning capacity of current RLVR models remains bounded by that of its base model."* So RL is best understood as **sampling-efficiency / distribution-sharpening**, not capability addition.

✅ **PRIMARY** — **[arXiv:2410.19920](https://arxiv.org/abs/2410.19920)**: *"LLMs fine-tuned with reinforcement learning tend to overfit to the specific prompts they have been trained on"*; *"the performance of LLMs degrades when faced with prompt formulations different from those used during the RL training phase."* RL is not immune to the same brittleness one might attribute to prompt-level methods — it has its own form of it.

❌ **Not verified / not found:** I did not find any 2026 primary source that directly compares RL fine-tuning against *skill-document* optimization on a repo-level code-generation benchmark. See §3.3.

---

## 3. The direct comparison: text-space vs RL

### 3.1 GEPA vs GRPO — verified, with the caveats the abstract omits

✅ **PRIMARY.** Yes, the belief is correct: GEPA claims to beat GRPO. The exact claim is *"Across six tasks, GEPA outperforms GRPO by 6% on average and by up to 20%, while using up to 35x fewer rollouts"* ([arXiv:2507.19457](https://arxiv.org/abs/2507.19457)).

Caveats, all from the same paper:
- The comparison is on **Qwen3 8B** (plus GPT-4.1 Mini for prompt-optimizer baselines), not a frontier model, and the GRPO baseline is 24,000 rollouts.
- **GRPO wins on AIME-2025** (Table 1 caption).
- The six tasks are reasoning/QA/instruction-following/privacy/verification. **No coding task in the headline comparison.**
- Per-task margins range from **+19.0% to +0.7%** — the "+6% average / up to 20%" framing hides a near-tie on one task and a loss on another.
- Coding appears only in the *inference-time search* section, on kernel generation, and the authors call it preliminary.

### 3.2 SkillRL vs prompt/memory skill libraries — a head-to-head that favours RL

✅ **PRIMARY.** SkillRL explicitly benchmarks against *"prompt-based agentic or memory-based methods … without parameter updates"* and reports large margins (89.9% vs the best prompt-based baseline on ALFWorld; the paper reports the loss of the best prompt-based baseline as large, and reports Mem0+GRPO at 54.7% vs SkillRL's 89.9%). It also reports that **RL on a frozen policy** (MemRL, memory-only RL) underperforms at 21.4%. Its conclusion is worth quoting because it is the strongest counter-argument to the premise:

> *"effective experience transfer requires high-level skill abstraction and a co-evolving library rather than simple trajectory compression or prompt-based memory retrieval."* — [arXiv:2602.08234](https://arxiv.org/abs/2602.08234)

Read carefully: this says *skill abstraction* matters, and that the abstraction should **co-evolve with a trained policy**. It does not say text skills are useless; it says text skills that are not coupled to a training loop underperform.

### 3.3 SkillOpt's own position on RL

✅ **PRIMARY — and this is the honest answer to "does SkillOpt compare against RL?"** It does not. There is **no RL/GRPO/PPO baseline or experiment anywhere in SkillOpt**. Its only engagement with RL is a related-work sentence and a citation:

> *"GEPA demonstrates that trajectory feedback can guide reflective prompt evolution and **outperform reinforcement learning** on several language-agent tasks [13]."* — [SkillOpt §2](https://arxiv.org/html/2605.23904v2)

It also footnotes that prior skill work refines skills *"through failure analysis, creation-evaluation-revision loops, co-evolving generators and verifiers, collective updates, or **reinforcement learning**"* — i.e. it positions RL as prior art for skill discovery, not as a baseline to beat. And its future work explicitly frames text-space optimization as a *stepping stone* toward weights: *"self-distillation of optimized skills back into the target model as a stepping stone toward weight-level adaptation."*

**So: a SkillOpt-style loop's published evidence does not establish that it beats, or even matches, RL on anything — including on the tasks where RL has been strongest (repo-level coding). The inheritance is indirect: SkillOpt borrows GEPA's credibility on a different task suite.**

### 3.4 Where a text-space claim looks overstated

Three, stated plainly:

1. **"Best or tied on all 52/52 cells and beats every competitor"** ✅ is true *as measured*, but every competitor is a single-run point estimate with no seed variation and no significance test (verified: 0 occurrences of `signific`). With per-cell gaps as small as ~1 point in some tables and known agentic variance of 2–6 pp (§5.1), a substantial number of those 52 wins are not distinguishable from ties. The claim is not false; it is **under-powered**.
2. **"+23.5 points over no-skill"** is an average across six benchmarks, at least two of which are nothing like coding (ALFWorld, SearchQA). It is not a coding-agent number and should not be read as one.
3. **The GEPA "+6% average, up to 35× fewer rollouts"** framing is accurate but omits that GRPO wins on one of six tasks and that the largest margin comes from a single task. The abstract-level summary is more favourable than the table.

---

## 4. Code generation specifically: procedure vs capability

This is the centre of the question, so it gets the most space. The distinction requested is:

- **(a) procedural gain** — the agent does the right *steps*;
- **(b) capability/knowledge gain** — the model knows more about the domain (Spring Boot layering, a house convention, a private API).

### 4.1 What the procedural-optimization papers actually measure

✅ **PRIMARY.** Across SkillOpt, GEPA, Trace2Skill, EvoSkill, AutoRefine:

| Paper | Any repo-level codegen benchmark? | What the benchmarks actually are |
|---|---|---|
| SkillOpt | **No** | SearchQA, SpreadsheetBench, OfficeQA, DocVQA, LiveMath, ALFWorld |
| GEPA | **No** (kernels only, preliminary) | AIME-2025, LiveBench-Math, HotpotQA, IFBench, HoVer, PUPA + NPUEval/KernelBench |
| Trace2Skill (2603.25158) | **No** | SpreadsheetBench-Verified, WikiTQ, HiTab, math, VQA |
| EvoSkill | **No** | OfficeQA, SealQA, BrowseComp |
| AutoRefine | Partly | ALFWorld, ScienceWorld, TravelPlanner, **SpreadsheetBench**, SkillCraft |

So the honest statement is: **there is no published evidence that optimizing a prose skill document improves repository-level code generation on a SWE-bench-style task.** What exists is evidence on spreadsheet code, kernels, and QA/tool-use procedures. That is a real gap, and it is exactly the gap the premise assumes away. **This is not "the premise is refuted" — it is "the premise is untested in the setting it is being applied to."**

And where SkillOpt does look at its one code-adjacent benchmark, its own causal attribution is procedural: *"The gains are largest on **procedural** benchmarks, where reusable rules about tool use and output formatting matter most."* Its learned rules are described as *"answer-format constraints … evidence binding to a specific visual region … workbook-structure-first reasoning … search-frontier discipline"* and *"the discipline that frontier models lack zero-shot."* That is **a consistency gap, not a knowledge gap** — the model knows how to inspect a workbook; it doesn't reliably do it. Also of note: the *"human skills are already 145–516 tokens long and often exceed the one-shot LLM skill, yet they are beaten in every direct-chat model row"* — so it is not the mere presence of experienced prose that helps.

### 4.2 The decisive 2026 evidence: rule/skill files in front of coding agents

This is the literature that most directly answers the question, and it is **not** the skill-optimization literature — it is the agent-context literature. Three papers, all 2026, all large-N, all with explicit statistics.

✅ **PRIMARY — Gloaguen et al., "Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?"**, [arXiv:2602.11988](https://arxiv.org/abs/2602.11988) (v2 Jun 2026):

> *"providing context files does not generally improve task success rates, **while increasing inference cost by over 20% on average**. This observation holds across different LLMs, coding agents, and for both LLM-generated and developer-committed context files. Specifically, we find that while **instructions in the context files are well followed** by coding agents, **repository overviews**, although popular and recommended by model providers, **are not helpful**. We conclude that while context files are useful for specifying **non-standard coding practices**, any attempts to improve performance should be rigorously evaluated before deployment."*

That last clause is the single most important sentence in this report for the premise. **Instructions are followed; task success does not follow.** The measurable effect of the document is *compliance*, not *correctness*. For a platform that generates Spring Boot microservices to a house standard, compliance may itself be the goal — which is a legitimate reason to keep the skill — but it is **not** the same as making the agent "do code" better.

✅ **PRIMARY — "Do Context Files Help Coding Agents? A Two-Agent Ablation Study on Real Repositories"**, [arXiv:2607.27250](https://arxiv.org/abs/2607.27250):
- Design: 2 frontier agents (Claude Code, Codex), 17 real tasks from 3 repositories, **288 evaluated runs**, gold-test evaluation, three strategies (none / always-on full AGENTS.md / selective wiki retrieval).
- Result: *"Context strategy does not measurably move correctness on either agent (bounded to ≤10–15 pp via **equivalence testing**)."*
- **The mechanism, which is the direct answer to "procedure vs capability":** *"agents fail on implementation skill — feature design, pattern selection, exact wiring — not missing repository knowledge that a context file could supply; a manipulation probe confirms the real AGENTS.md never converts a near-miss to a pass on either agent."*
- Also: *"borderline task difficulty is agent-specific (Spearman ρ = 0.75), offering a candidate explanation for prior contradictions."*

Read that against SkillOpt's framing: SkillOpt's genuine wins are on tasks where the model **knows what to do but doesn't do it**. This paper finds that on real repo tasks, the binding constraint is the opposite — **the model cannot do the implementation at all**, and no amount of text about the repository fixes that. These are not contradictory findings; they are the two sides of the exact distinction requested. **Procedural text addresses inconsistency; it does not address incapacity.**

✅ **PRIMARY — "Guardrails Beat Guidance: A Large-Scale Study of Rules, Skills, and Persistent Configuration for Coding Agents"**, [arXiv:2604.11088v2](https://arxiv.org/html/2604.11088v2):
- Scale: **679 rule files (25,532 rules)** scraped from GitHub; **>5,000 agent runs** of Claude Code with Claude Opus 4.6 on SWE-bench Verified.
- Design: screened all 500 Verified tasks with 3 baseline repetitions each (1,500 runs) and kept **58 discriminative tasks** (solved 1 or 2 of 3 times; 30–70% baseline pass rate). Eight conditions compared on those 58 tasks.
- Result: *"Every rule condition outperforms the 50.0% no-rule baseline by 6.9–13.8 pp … yet **no condition is significantly different from any other** (Cochran's Q = 4.70, p = 0.697)."* The closest pairwise contrast is random vs baseline (McNemar p = 0.077; 12 tasks helped, 4 hurt). A binomial sign test on the seven directions gives p = 0.008.
- Result 2 — the content-independence finding: *"Performance gains are largely content-independent: random, shuffled, mismatched-domain, and unconverted-format rule files all match curated rules, pointing to a **context priming** mechanism."* Concretely: **random rules tie with curated rules at 63.8%**.
- Result 3 — polarity: *"every individually beneficial rule is a negative constraint ('do not refactor unrelated code'), while every individually harmful one is a positive directive ('follow code style')."* The most impactful single rule, *"do not refactor unrelated code"*, shows a **20 pp drop when removed** (McNemar p = 0.016) — though the authors note this *"would not survive a strict multiple-comparison correction across all 18 rules."*
- Result 4 — ensemble resilience: *"the 18-rule ensemble holds at 65.7%"*; pass rates stay stable from 0 to 50 rules.
- The authors' own implication for exactly the platform's loop: *"This implies that automated rule optimizers should target **structural properties rather than semantic content**."*

**This is the strongest challenge to the premise.** If a large part of the gain from a rule file is *priming* and not *content*, then reflecting on failures to improve the *content* of a skill document is optimising the wrong variable. And the polarity result says a skill document full of positive directives ("always annotate with @Service", "always write a DTO") is, rule-for-rule, the *harmful* kind — while the beneficial kind is negative constraints ("do not put business logic in the controller").

### 4.3 Knowledge vs procedure: the mechanism-level evidence

✅ **PRIMARY** — several independent lines converge:

1. **Information in the task dominates.** [SWE-bench+](https://arxiv.org/abs/2410.06992): *"32.67% of the successful patches involve 'cheating' as the solutions were directly provided in the issue report or the comments"* (solution leakage), and *"31.08% of the passed patches are suspicious patches due to weak test cases."* After filtering, SWE-Agent+GPT-4's resolution rate **drops from 12.47% to 3.97%**, and on the leakage-free SWE-bench+ it drops to **0.55%**. When the *information* is removed, most of the apparent capability disappears. That is a knowledge/context effect, not a procedural one.
2. **Benchmark-level memorisation.** [SWE-bench Illusion](https://arxiv.org/abs/2506.12286): *"SoTA models achieve up to 76% accuracy in identifying buggy file paths using only issue descriptions, without access to repository structure. This performance is merely up to 53% on tasks from repositories not included in SWE-Bench, pointing to possible data contamination or memorization."* Verbatim 5-gram overlap: *"up to 35% … on SWE-Bench Verified and Full, but only up to 18% for tasks in other benchmarks."*
3. **Retrieved repository context helps repo-level completion.** [RepoCoder](https://arxiv.org/abs/2303.12570): similarity-based retrieval + iterative retrieval-generation *"significantly improves the In-File completion baseline by over 10% in all settings."* Knowledge injection from the codebase itself is a measurable lever.
4. **Text-space optimization can *distil* knowledge into a procedure.** GEPA's NPUEval result (RAG 16.33% → GEPA prompt 30.52%, §1.2) is the clearest example: retrieval-derived domain knowledge, once absorbed into a prompt, outperformed runtime retrieval. If the platform's reflection has access to the failures *and* the domain docs, the skill document can legitimately carry knowledge — but then the gain is a **knowledge** gain delivered through text, not a procedure gain.
5. **External verification, not self-critique, is what makes iterative code repair work.** [Olausson et al., "Is Self-Repair a Silver Bullet for Code Generation?"](https://arxiv.org/abs/2306.09896) (ICLR 2024): *"when the cost of carrying out repair is taken into account, performance gains are often modest, vary a lot between subsets of the data, and are sometimes not present at all. We hypothesize that this is because self-repair is bottlenecked by the model's ability to provide feedback on its own code; using a stronger model to artificially boost the quality of the feedback, we observe substantially larger performance gains."* And [Huang et al.](https://arxiv.org/abs/2310.01798): *"LLMs struggle to self-correct their responses without external feedback, and at times, their performance even degrades after self-correction."* The gate in the platform is therefore doing the right thing by insisting on **external** execution — this is the part of the design most supported by evidence.

**Synthesis for the requested distinction:**

| Situation | Does a procedural skill document help? | Evidence |
|---|---|---|
| Model **lacks the domain knowledge** (unfamiliar framework, private conventions, novel architecture) | Weakly, unless the document itself carries the missing knowledge. Runtime retrieval of real docs is the better-validated lever. | GEPA NPUEval (RAG 16.33% vs GEPA prompt 30.52% — but GEPA's prompt embeds retrieved knowledge); Gloaguen (overviews "not helpful"); RepoCoder (+10%) |
| Model **knows the domain but is inconsistent** (formatting, verification discipline, loop-breaking, tool-order) | **Yes — this is where the measured gains are.** | SkillOpt's own attribution ("procedural benchmarks", "discipline that frontier models lack zero-shot"); ALFWorld skill evolution into a finite-state execution policy (49.3→74.6); Guardrails' polarity result |
| Model **cannot implement the feature at all** | **No.** | Two-agent ablation: failures are "implementation skill — feature design, pattern selection, exact wiring — not missing repository knowledge"; real AGENTS.md "never converts a near-miss to a pass" |
| The platform generates Spring Boot services to a **house standard** | Plausibly yes for *compliance*, and this is the best-supported use case: Gloaguen explicitly finds context files *"useful for specifying non-standard coding practices."* But expect the benefit in *conformance*, not in *does-it-work*. | [arXiv:2602.11988](https://arxiv.org/abs/2602.11988) |

⚠️ **Not found / UNVERIFIED:** no study I could locate measures skill-document optimization for framework-specific enterprise code generation (Spring Boot layering, microservice conventions). The closest evidence is Gloaguen's "non-standard coding practices" finding and the Guardrails polarity result. **Anyone claiming a measured, general improvement in this exact setting is going beyond the literature.**

---

## 5. Negative results, null results, and the sample-size problem

### 5.1 Agentic evaluation is noisy — quantified

✅ **PRIMARY — "On Randomness in Agentic Evals"**, [arXiv:2602.07150](https://arxiv.org/abs/2602.07150) (v3 Mar 2026). This is the paper that should be read before shipping any gate.

- Scale: **60,000 agentic trajectories on SWE-bench Verified**, 3 models × 2 scaffolds, **10 independent runs** each, **N = 500 tasks**, 25.58B tokens, 1.88M tool calls.
- *"single-run pass@1 estimates vary by **2.2 to 6.0 percentage points** depending on which run is selected, with **standard deviations exceeding 1.5 percentage points even at temperature 0**."*
- *"reported improvements of **2–3 percentage points may reflect evaluation noise** rather than genuine algorithmic progress."*
- *"A reported one-run improvement from, say, 31% to 33% could reflect sampling a favorable run from the same underlying distribution rather than genuine algorithmic progress."*
- Optimistic vs pessimistic bounds: *"gaps up to **24.9 percentage points** between best-case and worst-case performance."*
- Recommendation, verbatim: *"(1) estimate pass@1 from multiple independent runs per task, especially when measuring small improvements, (2) use statistical power analysis to determine the number of runs needed to detect expected effect sizes, and (3) consider metrics like pass@k (optimistic bound) and pasŝk (pessimistic bound) with k > 1."*
- Their power analysis (Table 2, Figure 5): *"Detecting a 2% improvement at p < 0.05 with 80% power requires approximately **9 runs** per agent under test, while detecting a 1% improvement requires **36 runs**."* At the lowest observed variance (σ = 0.7%) a 1% effect needs 8 runs; at the maximum variance (σ = 1.8%) the requirement is exponential in the effect size.
- ⚠️ **Important scope caveat:** these are *runs on the same 500 tasks*. That is a **more favourable** design than sampling fresh task instances, because the task set is fixed and only sampling noise varies. A 4-task fresh exam is far weaker than this. Their σ = 1.5% is the std dev of a pass@1 estimate computed over 500 tasks, not over 4.

✅ **PRIMARY** — related variance findings in the same paper's related work, which I cite as reported there rather than read directly: *"Prompt sensitivity represents another major source of variance. Zhuo et al. (2024); Sclar et al. (2024); Andersson et al. (2025) show that meaning-preserving changes (spacing, punctuation, example ordering, case) cause substantial performance shifts."* And ⚠️ SECONDARY/PRIMARY-on-abstract: [Within-Model vs Between-Prompt Variability](https://arxiv.org/abs/2601.21339) (Jan 2026): 12 LLMs × 10 prompts × 100 samples (N=12,000); *"prompts explain 36.43% of variance"* for output quality, *"but for output quantity … prompts explain only 4.22%"*, with *"within-LLM variance (10–34%)"*; *"single-sample evaluations risk conflating sampling noise with genuine prompt or model effects."*

### 5.2 The gate arithmetic for a 4–5 task exam

The platform's gate: pool of **five** baseline blueprints, **M = 4** selected per iteration, the current and candidate skills each scored on the same 4 fresh executions, accept iff `candidate_score > current_score` (strict) — ✅ read from the repo's own contract at [specs/014-skillopt-compact/contracts/gate.md](../specs/014-skillopt-compact/contracts/gate.md) and [data-model.md](../specs/014-skillopt-compact/data-model.md). One task therefore moves the pass rate by **25 percentage points**.

There is no statistical test. Below is what a test would say. **Method:** exact binomial/McNemar for the small-n results; the standard normal-approximation sample-size formula for two proportions, `n = (z_{α/2}+z_β)² · [p₁(1−p₁)+p₂(1−p₂)] / (p₁−p₂)²`, with α = 0.05 two-sided and power 0.80. I computed these directly (no citation needed for arithmetic; the formula is the standard one documented for [`statsmodels.stats.power.zt_ind_solve_power`](https://www.statsmodels.org/stable/generated/statsmodels.stats.power.zt_ind_solve_power.html) and consistent with the power analysis in arXiv:2602.07150).

**a) The best case that a 4–5 task exam can ever produce.** If *every* task flips in the candidate's favour, the exact two-sided McNemar p-value is:

| Tasks per iteration | Best attainable two-sided p (all favourable) | Significant at α = 0.05? |
|---|---|---|
| 4 | **0.125** | No, never |
| 5 | **0.0625** | No, never |

**A 4- or 5-task gate can never reach statistical significance, even in the best possible case.** The "strict improvement" rule is not a weak test that occasionally works — for a binary per-task outcome it is arithmetically incapable of significance. (It can still be *right*; it just cannot be *evidence*.)

**b) False-accept rate when nothing has changed.** If the current and candidate skills are identical and each execution is a fresh Bernoulli draw at the same true per-task success rate `p`, what is `P(candidate > current)`?

| True per-task rate | Unpaired (two independent 4/5-task samples) | Paired (same 4/5 tasks, re-run) |
|---|---|---|
| p = 0.3 | 0.35 (n=4) / 0.36 (n=5) | 0.61 (n=4) / 0.69 (n=5) |
| p = 0.5 | 0.36 / 0.38 | **0.68 (n=4) / 0.76 (n=5)** |
| p = 0.7 | 0.35 / 0.36 | 0.61 / 0.69 |

The platform scores **both arms on the same executions** (paired), so the relevant column is the right-hand one: even when the skill document is unchanged, a paired 4-task gate reports a "strict improvement" roughly **two times in three**. This is the single most important number in this report for the platform's design, and it is a consequence of the revision's design (2×M fresh executions, identical set) rather than a hypothetical.

**c) Power to detect a real effect.** With 4–5 tasks per arm, power at α = 0.05 to detect a genuine improvement:

| True improvement | Power (n = 5/arm) |
|---|---|
| 30% → 40% | 0.05 |
| 30% → 50% | 0.10 |
| 50% → 70% | 0.10 |
| 50% → 90% | 0.34 |

**d) How many tasks are actually needed** (unpaired, 80% power, α = 0.05 two-sided):

| Improvement | n per arm | With continuity correction |
|---|---|---|
| 30% → 40% | **≈353** | ≈373 |
| 50% → 60% | **≈385** | ≈404 |
| 30% → 50% | ≈90 | ≈100 |
| 30% → 35% | ≈1,374 | — |
| 50% → 55% | ≈1,562 | — |

This is consistent in spirit with arXiv:2602.07150's own numbers (2% effect → ~9 runs *on a fixed 500-task set*); their design is cheaper because it repeats runs on the same large task set rather than drawing new tasks. **Both point the same way: a 4–5 item exam can only detect an enormous effect, and cannot certify a small one.**

### 5.3 Skill optimization's own nulls, regressions, and overfitting

- ✅ **Regressions from editing skills.** Trace2Skill, quoted in §1.3: *"each addition simultaneously fixes and breaks tasks"* (57 fail-to-pass vs 21 pass-to-fail; then 26 vs 46); *"the net accuracy plateaus instead of rising."* This is the strongest published argument that a single accept/reject gate on aggregate pass rate is insufficient — the aggregate can be flat while the edit is both fixing and breaking. [arXiv:2603.25158](https://arxiv.org/abs/2603.25158).
- ✅ **Plausible diagnoses can hurt.** SkillOpt itself: *"plausible textual diagnoses can still hurt the actual target model"* — the justification it gives for the gate. [arXiv:2605.23904v2](https://arxiv.org/html/2605.23904v2).
- ✅ **Transfer is not guaranteed.** SkillOpt Appendix B: *"optimized skills can encode domain-specific heuristics from the training distribution, so careful held-out evaluation remains necessary before transferring them to substantially different models, harnesses, or task settings."* Its cross-benchmark transfers are also much smaller (+3.7/+1.8/+1.3) than in-domain gains.
- ✅ **Cost without benefit.** Gloaguen et al.: context files *"increase inference cost by over 20% on average"* with no general improvement in task success. [arXiv:2602.11988](https://arxiv.org/abs/2602.11988).
- ✅ **Null result for context files on real repos, with equivalence testing.** Two-agent ablation: bounded null ≤10–15 pp; the mechanism is implementation skill, not missing knowledge. [arXiv:2607.27250](https://arxiv.org/abs/2607.27250).
- ✅ **Content-independence.** Random rules match curated rules (63.8% each); *"no condition is significantly different from any other."* [arXiv:2604.11088v2](https://arxiv.org/html/2604.11088v2).
- ✅ **Self-repair gains are fragile.** Olausson et al.: gains *"often modest, vary a lot between subsets of the data, and are sometimes not present at all."* [arXiv:2306.09896](https://arxiv.org/abs/2306.09896).
- ✅ **Self-correction can degrade.** [arXiv:2310.01798](https://arxiv.org/abs/2310.01798).
- ⚠️ **Secondary, and a caution about benchmarks:** BenchLM's SWE-bench Verified page for **2026-09-28** lists Claude Opus 5 at **96%**, Claude Mythos 5 at **95.5%**, Claude Fable 5 at **95%**, compiled from provider self-reports, and states plainly: *"most rows are provider self-reports; the benchmark is not marked current."* [benchlm.ai](https://benchlm.ai/benchmarks/swe-bench-verified). I could **not** verify these against the official leaderboard (it would not render), so treat them as ⚠️ SECONDARY. The relevant point is structural, not numeric: **SWE-bench Verified appears saturated, so it is no longer a good measurement instrument for improvement.** Note also the contamination evidence in §4.3, which independently undermines it.

### 5.4 A caveat on the platform's pass criterion

✅ Read from the repo: *"A pass is an execution whose offline build/test exit code is zero"*, with the hermetic-fallback exclusion ([contracts/gate.md](../specs/014-skillopt-compact/contracts/gate.md)). Two observations grounded in §2.3 and [R2E-Gym](https://arxiv.org/abs/2504.07164): (i) test-based verifiers *"suffer from low distinguishability"*, and (ii) SkillOpt's own limitation requires *"automatic verifiers, exact-match metrics, executable checks, or otherwise reliable feedback signals."* A compile-and-run exit code is a **weak** verifier. Where the artifact is a generated microservice, the skill could raise the pass rate by emitting less code, fewer tests, or trivially-satisfiable tests, and the gate would reward it. Exercised-behaviour coverage (assertions that actually fail when the service is wrong) is a prerequisite for the gate to mean anything.

---

## 6. What is actually SOTA (mid-2026) for making a coding agent reliable

Honest ranking, from the evidence above. "Reliability" here means high resolve rate on real repo tasks with low run-to-run variance — not "does the agent do what my document says".

**1. Model capability.** Every other axis is a modifier on this. The two-agent ablation attributes real-task failures to implementation skill — *"feature design, pattern selection, exact wiring"* — and finds the context channel cannot move correctness ([arXiv:2607.27250](https://arxiv.org/abs/2607.27250)). Anthropic's own published practice for its frontier model is to average SWE-bench Verified *"over 25 trials"* and it notes *"With a prompt modification, we saw a score of 81.42%"* — i.e. the vendor treats the score as a distribution and prompt tweaks as a smaller-order effect ([anthropic.com/news/claude-opus-4-6](https://www.anthropic.com/news/claude-opus-4-6)). ✅ PRIMARY.

**2. Harness and agent-computer interface + execution-verified test-time compute.** This is the best-supported *engineering* lever after the model.
- [SWE-agent](https://arxiv.org/abs/2405.15793): a custom agent-computer interface gives **12.5% pass@1 on SWE-bench and 87.7% on HumanEvalFix**, *"far exceeding the previous state-of-the-art achieved with non-interactive LMs"* — and the paper's contribution is *interface design*, not prompts.
- [CodeAct](https://arxiv.org/abs/2402.01030): executable Python as the unified action space gives *"up to 20% higher success rate"* than JSON/text action formats.
- [SWE-Gym](https://arxiv.org/abs/2412.21139): inference-time scaling through **verifiers trained on agent trajectories** reaches 32.0% on Verified.
- [R2E-Gym](https://arxiv.org/abs/2504.07164): **hybrid test-time scaling takes 34.4% → 51%**, and the paper's finding that execution-based and execution-free verifiers are complementary is directly actionable.
- [Agentless](https://arxiv.org/abs/2407.01489), the null result that reframes this axis: a *"simplistic three-phase process"* with **no** agent loop reached **32.00% on SWE-bench Lite at $0.70** — *"the highest performance … compared with all existing open-source software agents"* at the time. The lesson is that **verification and iteration structure beat agentic freedom**, not that agents are useless.
- Vendor practice confirms the multi-sample norm: Anthropic's Terminal-Bench 2.0 methodology uses **5–15 samples per task across staggered batches** with 1×/3× resource allocation ([anthropic.com/news/claude-opus-4-6](https://www.anthropic.com/news/claude-opus-4-6)). ✅ PRIMARY.

**3. RL post-training on executable SWE environments.** Proven, expensive, and it works: SWE-RL **41.0%** with a 70B model ([arXiv:2502.18449](https://arxiv.org/abs/2502.18449)); SWE-Gym **+19% absolute** ([arXiv:2412.21139](https://arxiv.org/abs/2412.21139)); R2E-Gym **34.4% pass@1** at 32B ([arXiv:2504.07164](https://arxiv.org/abs/2504.07164)). Ranked below #2 only because of cost and infrastructure, not efficacy — and because [Yue et al.](https://arxiv.org/abs/2504.13837) show it sharpens sampling rather than adding capability, which is exactly the regime where better harnesses also pay.

**4. RL/augmented training that co-evolves a *skill bank* with the policy.** Real, measured, and it beats prompt-based skill libraries in the one head-to-head I found: SkillRL **+12.3 absolute over its own GRPO base** on ALFWorld, 89.9% overall ([arXiv:2602.08234](https://arxiv.org/abs/2602.08234)); SAGE **+8.9% SGC, −26% steps, −59% tokens** on AppWorld ([arXiv:2512.17102](https://arxiv.org/abs/2512.17102)). Costs a training loop and a policy to update. Not validated on repo-level codegen.

**5. Text-space optimization of a procedural skill/prompt document.** Justified, cheap at deployment, genuinely effective *on the class of tasks where the model is inconsistent rather than incapable* — and unevidenced for repo-level code generation. SkillOpt's own numbers are large **but on QA/tool/embodied benchmarks** ([arXiv:2605.23904](https://arxiv.org/abs/2605.23904)); GEPA's are on reasoning/QA ([arXiv:2507.19457](https://arxiv.org/abs/2507.19457)); and the direct 2026 evidence on rule/skill documents in front of coding agents is null or content-independent ([arXiv:2602.11988](https://arxiv.org/abs/2602.11988), [arXiv:2607.27250](https://arxiv.org/abs/2607.27250), [arXiv:2604.11088v2](https://arxiv.org/html/2604.11088v2)).

**6. Hand-written skill/rule documents.** Actively contested. `+6.9–13.8 pp` over a 50.0% no-rule baseline on a *discriminative* subset in one study — with no significant difference between any two conditions and random rules tying curated ones ([arXiv:2604.11088v2](https://arxiv.org/html/2604.11088v2)) — and no improvement in task success with +20% cost in another ([arXiv:2602.11988](https://arxiv.org/abs/2602.11988)). The one consistently positive result is *efficiency*, not correctness: lower median runtime **(−28.64%)** and reduced output tokens **(−16.58%)** with *"comparable task completion behavior"* ([Lulla et al., arXiv:2601.20404](https://arxiv.org/abs/2601.20404)).

**Ranking summary:** for *correctness on repo-level code*, the order is model → harness + verified test-time compute → RL post-training → RL-trained skill banks → optimized text skills → hand-written rules. For *cost efficiency and conformance to a house standard*, rule/skill documents move up, and the Gloaguen "non-standard coding practices" finding is the best evidence for that use.

---

## 7. Does the premise hold?

**The premise is "apply SkillOpt as an optimization layer for just creating agents that do code."**

**Answer: partly. It holds as a *conformance* layer and as a *consistency* layer. It does not hold as a way to make a coding agent more capable, and it has never been tested in the setting it is being applied to.**

Break it into the four claims the premise implicitly makes, and score each against the evidence:

**(1) "SkillOpt is a strong, validated method." — TRUE, with a major asterisk.**
✅ Verified: 52/52 best-or-tied cells, +23.5/+24.8/+19.1 on GPT-5.5 across three harnesses, positive transfer across models, harnesses, and a nearby benchmark, and mechanisms whose contribution is demonstrated by ablation. It is a real, well-constructed method.
⚠️ The asterisk: **zero significance testing** (verified: 0 occurrences of `signific` in the full text), a fixed split seed, single-run point estimates for all 52 cells, and benchmarks chosen from QA/tool/embodied families. The per-cell margins over the best competitor average +5.4 points across six benchmarks — which is inside or near the 2.2–6.0 pp single-run variance measured for agentic evals ([arXiv:2602.07150](https://arxiv.org/abs/2602.07150)). The headline is likely directionally right and numerically optimistic.

**(2) "It transfers to code generation." — UNSUPPORTED.**
❌ There is **no** repo-level coding benchmark in SkillOpt, GEPA, Trace2Skill, or EvoSkill. The nearest proxies are SpreadsheetBench (spreadsheet code) and kernel generation. The direct 2026 evidence on injecting rule/skill documents into coding agents is a bounded null ([arXiv:2607.27250](https://arxiv.org/abs/2607.27250)), a no-improvement-with-+20%-cost result ([arXiv:2602.11988](https://arxiv.org/abs/2602.11988)), and a content-independence result where random rules match curated ones ([arXiv:2604.11088v2](https://arxiv.org/html/2604.11088v2)). Treating "spreadsheet codegen improves +38 points" as evidence that "Spring Boot microservice generation improves" is an unlicensed extrapolation.

**(3) "The minimal loop is an acceptable implementation." — FALSE as an optimizer; acceptable as loop plumbing.**
❌ SkillOpt's own ablations say the omitted machinery is where much of the stability comes from: no rejected-edit buffer costs 1.6–4.6 points; no meta+slow update costs **22.5 points on SpreadsheetBench**. AutoRefine puts a **replay/regression gate at 16.11 points**. Trace2Skill shows edits that fix 57 tasks while breaking 21 — invisible to an aggregate pass-rate gate.
❌ And the gate itself, at 4–5 tasks with no test, cannot reach significance even in the best case, and fires a false "strict improvement" ~61–76% of the time on paired identical configs (§5.2). This is not a subtle criticism; it means a single iteration's accept/reject decision is close to a coin flip.
✅ To the platform's credit, this is *already recorded in its own docs* as a deliberate residual: *"The gate compares two pass rates with no significance test, on a five-task exam where a single task moves the rate by 25 percentage points … Acceptable for validating the loop; not acceptable for a production optimiser."* ([specs/014-skillopt-compact/plan.md:133](../specs/014-skillopt-compact/plan.md), [constitution-recheck.md:58](../specs/014-skillopt-compact/constitution-recheck.md)).

**(4) "Text-space optimization is the state of the art for this problem." — NO, and the requester's own instinct about RL is the better lead.**
❌ Where text-space and RL have been compared on the same task, results are mixed and the one skill-library head-to-head favours RL coupled to a trained policy (SkillRL, §3.2). GEPA's win over GRPO is real but confined to six non-coding tasks and one model, with GRPO winning AIME.
❌ For repo-level code specifically, the measured SOTA levers are model capability, harness/interface design, verified test-time compute, and RL post-training on executable environments (§6) — none of which is a skill document.

### Under what conditions does it work?

| Condition | Verdict |
|---|---|
| The failure mode is **inconsistency** (the model knows the right procedure and skips it) | ✅ Works. This is SkillOpt's demonstrated regime. |
| The failure mode is **incapacity** (the model can't design the feature or wire it) | ❌ Does not work. [arXiv:2607.27250](https://arxiv.org/abs/2607.27250). |
| The target is **conformance to non-standard conventions** | ✅ Best-supported use. "context files are useful for specifying non-standard coding practices" — [arXiv:2602.11988](https://arxiv.org/abs/2602.11988). Measured as compliance, not as task success. |
| The knowledge is **missing from the model** | ⚠️ Only if the reflection step can inject the knowledge into the text (GEPA's NPUEval pattern). Runtime retrieval of real docs is the better-validated lever. |
| The evaluation set is **≥ a few hundred tasks**, or **many repeated runs on a fixed large set** | ✅ Then an accept/reject gate can be sound. Below that, it cannot. |
| The evaluation set is **4–5 tasks, single run, no test** | ❌ The gate is noise. §5.2. |
| The skill is written as **negative constraints** ("do not X") | ✅ The only individually beneficial rule class found. [arXiv:2604.11088v2](https://arxiv.org/html/2604.11088v2). |
| The skill is written as **positive directives** ("always X") | ❌ "every individually harmful one is a positive directive." Same source. |
| The gain must show up in **does-the-service-work**, not **does-it-follow-the-house-style** | ❌ Unsupported. |

### What I'd tell the platform (short, evidence-linked)

1. **Keep the loop; stop treating its verdict as evidence.** The plumbing (collect → reflect → bounded edits → apply to a copy → externally verified gate) is a sound skeleton. The gate needs either a much larger held-out set (~90–400 tasks for the effect sizes in §5.2d), repeated runs on a fixed set (arXiv:2602.07150 recommends power analysis explicitly), or it should be demoted to a *regression filter* ("did this make anything worse?") rather than an *evidence of improvement*.
2. **Reinstate the omitted stabilisers before extending anything else.** In order of published effect size: the epoch-wise meta/slow update (**−22.5** if removed), a rejected-edit buffer (**−1.6 to −4.6**), and a replay/regression check (**−16.11** in AutoRefine). The current v2 backlog is pointed at the right target.
3. **Prefer negative constraints in the skill document.** It is the cheapest change with the clearest published support, and it flips the polarity of the entire artifact.
4. **Measure conformance separately from capability.** Gloaguen's core finding is that instructions are followed but task success does not move. If the platform's actual goal is "generated services follow the house layering", measure that directly (structural assertions on the generated tree) rather than inferring it from a build-pass rate — and do not report a build-pass improvement as if it were a capability improvement.
5. **Strengthen the verifier before strengthening the optimizer.** R2E-Gym's finding that test-based verifiers have *low distinguishability*, plus SkillOpt's stated precondition of *"automatic verifiers … or otherwise reliable feedback signals"*, means the gate can only be as good as its pass criterion. Build-exit-code is weak.
6. **If the goal is genuinely to make the code-generating agent better, skill optimization is not the top lever.** Ranked: better model → harness/interface + verified test-time compute (multiple candidates with execution feedback) → RL post-training. The honest version of the requester's instinct — "numeric/RL, same style" — exists (SkillRL, SAGE, SWE-RL, SWE-Gym, R2E-Gym), it works, and it costs a training loop and a policy you control. That is a bigger project than a skill markdown file, and it is the one with measured repo-level results.

---

## 8. Methods table

| Name | What is optimized | Needs weight updates? | Reported gain | Benchmark | Frozen component | Source |
|---|---|---|---|---|---|---|
| **SkillOpt** | one skill document (`best_skill.md`, 379–1,995 tok) via bounded add/delete/replace + strict held-out gate | **No** | 52/52 cells best-or-tied; GPT-5.5 **+23.5** chat / **+24.8** Codex / **+19.1** Claude Code; **+5.4** over best per-cell competitor | SearchQA, SpreadsheetBench, OfficeQA, DocVQA, LiveMath, ALFWorld | target model, harness, evaluator | ✅ [arXiv:2605.23904](https://arxiv.org/abs/2605.23904) |
| **GEPA** | prompts of compound AI systems (reflective mutation + Pareto search) | **No** | **+6% avg / up to +20%** over GRPO (24k rollouts) with up to **35× fewer rollouts**; MIPROv2 +10%; NPUEval 4.25%→**30.52%** | AIME-2025, LiveBench-Math, HotpotQA, IFBench, HoVer, PUPA; NPUEval, KernelBench | LLM weights | ✅ [arXiv:2507.19457](https://arxiv.org/abs/2507.19457) |
| **TextGrad** | any text variable in a computation graph (prompts, code, molecules) | **No** | GPQA 51%→**55%**; **20% relative** on LeetCode-Hard | GPQA, LeetCode-Hard, molecule/radiotherapy design | the model | ✅ [arXiv:2406.07496](https://arxiv.org/abs/2406.07496) |
| **Trace2Skill** (2603.25158) | a skill *directory*, via parallel trajectory consolidation | **No** | up to **+57.65 pp** transfer to a larger model on WikiTableQuestions; 3 seeds, per-seed std devs reported | SpreadsheetBench-Verified (400 → 200/200), WikiTQ, HiTab, math, VQA | weights; no test-time retrieval | ✅ [arXiv:2603.25158](https://arxiv.org/abs/2603.25158) |
| **Trace2Skill** (2605.21810) | skills for long-context EDA agents (verifier-guided) | No | not extracted | RTL/Verilog EDA | — | ✅ exists: [arXiv:2605.21810](https://arxiv.org/abs/2605.21810) |
| **EvoSkill** | skill *folders* via failure analysis + Pareto selection on held-out validation | **No** | OfficeQA **60.6→67.9**; SealQA **26.6→38.7**; SealQA→BrowseComp **+5.3** zero-shot | OfficeQA, SealQA, BrowseComp | *"the underlying model remains frozen"* | ✅ [arXiv:2603.02766](https://arxiv.org/abs/2603.02766) |
| **AutoRefine** | typed artifacts: Rule / Skill / bounded Subagent, with contract + **replay** gates | **No** | TravelPlanner **80.56%** vs 50.0%; removing boundary closure **−15.00**, removing replay validation **−16.11** | ALFWorld, ScienceWorld, TravelPlanner, SpreadsheetBench, SkillCraft | backbone GPT-5.6-terra | ✅ [arXiv:2601.22758](https://arxiv.org/abs/2601.22758) |
| **DSPy optimizers** | prompts and/or LM weights (MIPROv2, BootstrapFewShot, GEPA, BootstrapFinetune) | **Both available** | no single headline; documented as composable | framework-level | varies | ✅ [dspy.ai](https://dspy.ai/learn/optimization/optimizers/) |
| **SkillRL** | hierarchical **SkillBank** co-evolving with the policy during RL | **Yes** | **89.9%** ALFWorld, **72.7%** WebShop, **+12.3** over its own GRPO base, "over 15.3%" over baselines; search QA 47.1% | ALFWorld, WebShop, 7 search QA | — | ✅ [arXiv:2602.08234](https://arxiv.org/abs/2602.08234) |
| **SAGE** | skill library inside GRPO (Sequential Rollout + skill-integrated reward) | **Yes** | AppWorld **+8.9%** SGC, **−26%** steps, **−59%** tokens | AppWorld | — | ✅ [arXiv:2512.17102](https://arxiv.org/abs/2512.17102) |
| **ToolRL** | tool-selection/use policy via GRPO with designed rewards | **Yes** | **+17%** over base, **+15%** over SFT | tool-use benchmarks | — | ✅ [arXiv:2504.13958](https://arxiv.org/abs/2504.13958) |
| **SWE-RL** | 70B policy on software-evolution data (GRPO, patch-similarity reward) | **Yes** | **41.0%** SWE-bench Verified; improves 5 OOD tasks where SFT degrades | SWE-bench Verified | — | ✅ [arXiv:2502.18449](https://arxiv.org/abs/2502.18449) |
| **SWE-Gym** | SWE agents + trajectory-trained verifiers on 2,438 executable tasks | **Yes** | up to **+19%** absolute resolve rate; **32.0%** Verified / **26.0%** Lite | SWE-bench Verified/Lite | — | ✅ [arXiv:2412.21139](https://arxiv.org/abs/2412.21139) |
| **R2E-Gym** | 8.7K procedurally curated tasks + hybrid verifiers | **Yes** | **34.4%** pass@1 (32B); **51%** Verified with hybrid test-time scaling | SWE-bench Verified | — | ✅ [arXiv:2504.07164](https://arxiv.org/abs/2504.07164) |
| **Voyager** | a library of **executable code** skills + curriculum + self-verification | **No** | **3.3×** items, **2.3×** distance, up to **15.3×** faster milestones; library transfers | Minecraft | GPT-4 (blackbox) | ✅ [arXiv:2305.16291](https://arxiv.org/abs/2305.16291) |
| **MemRL** (as baseline) | RL updates a memory bank, **policy frozen** | policy frozen | only **21.4%** ALFWorld | ALFWorld | policy | ✅ reported in [arXiv:2602.08234](https://arxiv.org/abs/2602.08234) |
| **AGENTS.md / rule files** | hand-written repository context documents | **No** | **no general task-success improvement**, **+20% inference cost**; instructions *are* followed | SWE-bench + dev-committed files | — | ✅ [arXiv:2602.11988](https://arxiv.org/abs/2602.11988) |
| **Rule files, controlled** | 679 files / 25,532 rules, 58 discriminative tasks | **No** | all conditions **+6.9–13.8 pp** over a 50.0% baseline, **but no condition differs significantly from another**; random = curated at 63.8% | SWE-bench Verified (discriminative subset) | — | ✅ [arXiv:2604.11088v2](https://arxiv.org/html/2604.11088v2) |
| **Context injection, two-agent** | none / always-on AGENTS.md / selective wiki | **No** | **bounded null ≤10–15 pp** (equivalence testing); real AGENTS.md never converts a near-miss to a pass | 17 real repo tasks, 288 runs | — | ✅ [arXiv:2607.27250](https://arxiv.org/abs/2607.27250) |
| **AGENTS.md efficiency** | hand-written context file, efficiency axis only | **No** | median runtime **−28.64%**, output tokens **−16.58%**, comparable completion | 10 repos, 124 PRs | — | ✅ [arXiv:2601.20404](https://arxiv.org/abs/2601.20404) |
| **Agentless** | no agent loop: localize → repair → validate | No | **32.00%** SWE-bench Lite, **$0.70** | SWE-bench Lite | — | ✅ [arXiv:2407.01489](https://arxiv.org/abs/2407.01489) |
| **SWE-agent** | agent-computer interface design | No | **12.5%** SWE-bench, **87.7%** HumanEvalFix | SWE-bench, HumanEvalFix | — | ✅ [arXiv:2405.15793](https://arxiv.org/abs/2405.15793) |
| **Self-repair** | model repairs its own code | No | gains *"often modest, vary a lot … sometimes not present at all"*; better feedback → larger gains | HumanEval, APPS | — | ✅ [arXiv:2306.09896](https://arxiv.org/abs/2306.09896) |
| **Self-correction critique** | intrinsic self-correction without external feedback | No | *"performance even degrades after self-correction"* | reasoning | — | ✅ [arXiv:2310.01798](https://arxiv.org/abs/2310.01798) |
| **RLVR critique** | RL with verifiable rewards | Yes | pass@1 ↑ but **pass@256 coverage ↓**; no new capability beyond base | reasoning benchmarks | — | ✅ [arXiv:2504.13837](https://arxiv.org/abs/2504.13837) |
| **Agentic eval randomness** | — (measurement study) | n/a | single-run pass@1 varies **2.2–6.0 pp**; σ > **1.5 pp at temp 0**; pass@k vs pasŝk gap up to **24.9 pp**; 2% effect → **~9 runs**, 1% → **36 runs** | SWE-bench Verified, 60,000 trajectories | — | ✅ [arXiv:2602.07150](https://arxiv.org/abs/2602.07150) |
| **SWE-bench+** | — (benchmark validity) | n/a | **32.67%** solution leakage; filtering drops 12.47% → **3.97%**, and **0.55%** on SWE-bench+ | SWE-bench family | — | ✅ [arXiv:2410.06992](https://arxiv.org/abs/2410.06992) |
| **SWE-bench Illusion** | — (benchmark validity) | n/a | **76%** file-path ID from issue text alone vs **53%** off-benchmark; 5-gram overlap 35% vs 18% | SWE-bench Verified | — | ✅ [arXiv:2506.12286](https://arxiv.org/abs/2506.12286) |

---

## 9. What I could not verify (stated plainly)

1. **The official SWE-bench / Terminal-Bench leaderboards.** `swebench.com` and `tbench.ai` are client-side apps that returned no usable text. All frontier scores in §6 are vendor-published or ⚠️ SECONDARY. The BenchLM aggregator's "Claude Opus 5 = 96%" figure is **explicitly labelled** as provider self-reports on a page that says the benchmark "is not marked current" — I am reporting it as ⚠️ SECONDARY, not as fact.
2. **GEPA's limitations section.** Not present in the HTML rendering I fetched; the heading I found belonged to appendix example content. I report no GEPA limitations.
3. **Any paper comparing RL fine-tuning against skill-*document* optimization on a repo-level code benchmark.** I searched and found none. GEPA vs GRPO (non-coding) and SkillRL vs prompt-based memory (non-coding) are the closest. **This is the specific experiment the premise needs and does not have.**
4. **Any measurement of skill-document optimization for framework-specific enterprise codegen** (Spring Boot layering, microservice conventions). Not found.
5. **SkillOpt's selection-split-size sensitivity.** SkillOpt ablates training-set size (Table 2a) but **not** the size of the held-out selection set, even though the gate is the paper's central mechanism. Its selection split is 10% of each dataset (2:1:7 default in Appendix C), i.e. far larger than 4–5 items — but the paper never reports what happens as that shrinks.
6. **SkillOpt's released code.** I did not fetch or run [aka.ms/skillopt](https://aka.ms/skillopt); my claims are from the paper text only. Likewise I did not execute [gepa-ai/gepa](https://github.com/gepa-ai/gepa) or any other repo.
7. **EvoSkill's own evaluation of SpreadsheetBench.** EvoSkill's paper (grep-verified) contains no mention of SpreadsheetBench or SWE-bench; SkillOpt reports EvoSkill on the Codex SpreadsheetBench cell (27.5 → 67.5), which appears to be SkillOpt's own re-run under its aligned protocol, not EvoSkill's published result.

---

## 10. One-paragraph summary for someone who reads only this

Skill optimization over prose skills is a real 2026 research line with strong reported numbers — SkillOpt claims 52/52 best-or-tied cells and +19 to +25 points over no-skill on GPT-5.5 — but those numbers come from **no significance testing** on a benchmark suite that contains **no repo-level coding task**, and the papers that do test rule/skill documents against coding agents find **null or content-independent effects** (a bounded null of ≤10–15 pp across 288 real-repo runs; random rules matching curated ones; +20% inference cost with no success improvement). Meanwhile the mechanisms the platform's "minimal" loop drops are the ones SkillOpt's own ablations price highest (‑22.5 points for meta+slow update, ‑16.11 for a replay gate in AutoRefine), and the 4–5-task gate **cannot reach significance even in the best case** (min two-sided p = 0.125 at n=4) while reporting a spurious "strict improvement" ~61–76% of the time on paired identical configurations. The premise holds as a **conformance/consistency layer**, best served by **negative constraints** and measured by **structural conformance**, and it does not hold as a way to raise a coding agent's resolve rate — where the evidence ranks model capability, harness/interface design, verified test-time compute, and RL post-training (SWE-RL 41.0%, SWE-Gym +19%, R2E-Gym 34.4%→51%) above it. The requester's intuition about RL was directionally correct: SkillRL and SAGE are precisely "the same style, done numerically", they beat prompt-based skill libraries in the one head-to-head found, and they cost a trained policy — which is the real trade.
