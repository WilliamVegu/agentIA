# CODESKILL — Ablation Forensics and "Can Reflection Replace the RL Policy?"

**Paper under analysis:** *CODESKILL: Learning Self-Evolving Skills for Coding Agents* — Yanzhou Li, Yiran Zhang, Xiaoyu Zhang, Xiaoxia Liu, Yang Liu (NTU / Zhejiang). arXiv:2605.25430. v1 25 May 2026; **v2 25 Sep 2026** (the version analysed here unless stated).

- Abstract: https://arxiv.org/abs/2605.25430
- Full text (HTML): https://arxiv.org/html/2605.25430v2
- PDF: https://arxiv.org/pdf/2605.25430v2 · v1 PDF: https://arxiv.org/pdf/2605.25430v1

**Relationship to the two predecessor reports.** [`skillopt-for-coding-deep-dive.md`](./skillopt-for-coding-deep-dive.md) and [`agent-skill-optimization-sota.md`](./agent-skill-optimization-sota.md) established that (a) text-space/skill-document optimization has never been tested on repo-level codegen in the SkillOpt/GEPA/Trace2Skill/EvoSkill family, and (b) the direct 2026 tests of rule/skill documents in front of coding agents were null or content-independent. **CODESKILL is the paper that most directly contradicts that framing** — a repo-level codegen skill-bank method with a positive result and an ablation table — so this report interrogates it rather than restating the predecessors. Where the predecessors already covered a system (GEPA, Trace2Skill, ExpeL, Voyager, AWM, AutoRefine, EvoSkill, SkillRL, TextGrad), this report adds only the "trained or reflective? repo-level codegen?" verdict needed for the tables below, and says so.

**Retrieval status (stated up front).** I read the **complete v2 full text**, not the abstract: the HTML body (Sections 1–5 + appendices), and the **PDF text layer**, which additionally contains the entire appendix D–E content that the HTML drops — Figures 4–5 (real skill examples), Figures 6–9 (all four prompt templates), and **Figures 10–14, the verbatim judge rubrics**. The HTML rendering contains only three images (`iclr-frame.png`, `training_pipe_crop.png`, `ablation_croped.png`) and omits the appendix figures; if you read only the HTML you will wrongly conclude the rubric is unpublished. I also read **v1** in full to compare. ⚠️ The three figure *images themselves* are not machine-readable in this environment (the sandbox exposes only the session workspace as writable, so I could not persist and view the PNGs), so **all Figure 1/2/3 numbers below are the ones the paper states in prose, not values I read off a plot**. No claim here depends on a plot I could not read.

---

## 0. The one-paragraph answer

CODESKILL's own numbers show that **roughly half of the +11.03 is architecture-and-bank, not RL**. A fixed-prompt curator on the *identical* pipeline, action space, retrieval procedure, prompts and decoding settings — with **no feedback loop and no training** — scores **+5.93** (54% of the total) when given a strong LLM (GPT-5.4-mini), and **+0.40** (4%) when given CODESKILL's own 4B backbone. A gradient-trained-but-not-RL curator (SFT only, 4B) scores **+5.22** (47%). The RL-trained 4B policy scores **+11.03**. So the "learned policy" increment is ≈ **+5.1 to +5.8** points. **The paper contains no ablation that isolates the RL training method, and no ablation of the hybrid reward's components** — the two experiments that would settle the developer's question do not exist. What the paper *does* publish is a verbatim, transferable rubric (Appendix B/Figures 10–14) and a complete operation schema (Appendix D), i.e. everything a reflective optimizer needs except evidence that it works. Verdict in §9: **YES, reflection should recover most of the architecture half with moderate confidence; whether it recovers the RL half is untested, and two independent 2026 results show naive reflective skill authoring for coding agents is *negative* (−8.1 to −11.5 pp) unless paired with a maintenance/attribution rule.**

---

## 1. What I actually retrieved (so the tags can be audited)

| Artifact | Status | Notes |
|---|---|---|
| v2 HTML body, §1–§5 | ✅ read in full | Sections 3.1–3.3, 4.1–4.3 |
| v2 PDF text layer, Appendix A (training details, Tables 3–5) | ✅ read in full | includes SFT/RL config, 3-stage curriculum |
| v2 PDF, Appendix B (reward design) | ✅ read in full | includes the λ weight and the judge-template pointers |
| v2 PDF, Appendix C (retrieval, baselines) | ✅ read in full | |
| v2 PDF, Appendix D (Figures 4–5 skill examples) | ✅ read in full | both examples are Maven/Java skills |
| v2 PDF, Appendix E (Figures 6–14: prompts + **rubrics**) | ✅ read in full | **the rubric is published; quoted verbatim in §5** |
| v2 Table 1 and Table 2 as *rendered HTML tables* | ✅ parsed directly from HTML `<table>` elements | numbers cross-checked against the PDF text layer; no OCR, no guessing |
| Figure 1 (pipeline), Figure 2 (training), Figure 3 (dynamics) | ⚠️ **images only** | prose numbers reported; plot values not read |
| v1 PDF (full) | ✅ read | used for the version-diff in §4 |
| CODESKILL code / data / appendix "Experimental support" | ❌ **not released / no link found** | the HTML footer reads "Experimental support, please view the build logs for errors" |

Two retrieval notes that matter for anyone re-deriving this: **`pdftotext -layout` recovers the appendix figures because they are vector text, not raster images**; and the HTML `<table>` count is 11, of which 6 are inline math tables for the loss/objective equations — **only 5 are real result/config tables**.

---

## 2. Full text of every ablation-bearing sentence (v2)

> *"Lifecycle Ablation. To understand how each component of the skill-bank lifecycle affects downstream coding agents, we conduct the ablation study in Table 2. We fix Qwen3.5-35B-A3B as the downstream coding policy and compare variants that progressively enable different skill granularities and lifecycle operations. The event-driven-only and task-level-only variants use a single skill granularity, while extraction only combines both. Event-driven and task-level skills each improve over the no-skill baseline on different tasks, and their combination further improves average performance, suggesting that local execution guidance and high-level task strategies capture complementary knowledge. Adding skill evolution improves the average pass rate from 37.88 to 39.53 over extraction only. Full lifecycle maintenance further improves the average pass rate to 40.35 while shrinking the skill bank from 1252 to 676 skills, a reduction of approximately 46%. These results suggest that maintenance improves the compactness of the skill bank without sacrificing aggregate performance. The additional performance gain may partly arise from reducing redundant or conflicting skills, making retrieved guidance less repetitive and more consistent."* — [PRIMARY, §4.3](https://arxiv.org/html/2605.25430v2)

> *"Reward Optimization Dynamics. The right panel of Figure 3 shows reward dynamics during phase-3 RL training. … Still, its 20-step trend increases from 0.004 in steps 1–20 to 0.158 in steps 180–200, suggesting that CODESKILL gradually learns management decisions that improve the downstream agent over its no-skill baseline. The quality reward, provided by rubric-based LLM-as-judge feedback, is more stable and rises before stabilizing after roughly 100 steps. The overall reward follows the same upward pattern, indicating that the hybrid objective improves both executable utility and skill quality during RL training."* — [PRIMARY, §4.3](https://arxiv.org/html/2605.25430v2)

> *"Skill-Bank Maintenance Dynamics. Figure 3 visualizes skill-bank maintenance during test-time skill construction. … Add decisions dominate early, when the bank is small and most candidates provide uncovered knowledge. As the bank grows, merge and drop decisions become more frequent, indicating that CODESKILL identifies overlapping, redundant, or low-value candidates rather than adding every candidate to the bank."* — [PRIMARY, §4.3](https://arxiv.org/html/2605.25430v2)

**That is the entire ablation section.** There is one ablation table (Table 2) and two dynamics paragraphs referencing one figure (Figure 3). Everything else is main results (Table 1).

---

## 3. Every ablation condition found, with scores

### 3.1 Table 1 — main results (the source of the −5.10 headline) [PRIMARY]

Frozen downstream policy **Qwen3.5-35B-A3B**. Pass rate (%). `Skill Backbone` = the model that does the skill management, *not* the solver.

| # | Method | Skill Backbone | EnvBench-Py | EnvBench-Java | SWE-Bench Verified | Terminal-Bench 2 | **Average** | Avg steps |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| 1 | No-skill baseline | – | 6.98 | 27.10 | 57.33 | 25.88 | **29.32** | 44.12 |
| 2 | Subtask Memory | GPT-5.4-mini | 9.30 | 32.71 | 61.33 | 30.59 | **33.48** | 39.76 |
| 3 | **Prompt Skill Mgmt.** | Qwen3.5-4B | 4.65 | 30.84 | 58.67 | 24.71 | **29.72** | 39.08 |
| 4 | **Prompt Skill Mgmt.** | **GPT-5.4-mini** | 11.63 | 36.45 | **64.67** | 28.24 | **35.25** | 37.02 |
| 5 | SFT-CODESKILL | Qwen3.5-4B | 13.95 | 35.51 | 64.00 | 24.71 | **34.54** | 38.04 |
| 6 | **CODESKILL (RL)** | Qwen3.5-4B | 18.60 | 38.32 | 68.00 | 36.47 | **40.35** | 35.99 |

Same table, frozen downstream policy **GPT-5.4-mini**:

| # | Method | Skill Backbone | EnvBench-Py | EnvBench-Java | SWE-Bench Verified | Terminal-Bench 2 | **Average** |
|---|---|---|---|---:|---:|---:|---:|---:|
| 7 | No-skill baseline | – | 4.65 | 15.89 | 46.67 | 20.00 | **21.80** |
| 8 | Subtask Memory | GPT-5.4-mini | 9.30 | 25.23 | 52.67 | 22.35 | **27.39** |
| 9 | Prompt Skill Mgmt. | Qwen3.5-4B | 6.98 | 22.43 | 50.67 | 23.53 | **25.90** |
| 10 | **Prompt Skill Mgmt.** | **GPT-5.4-mini** | 9.30 | 24.30 | **56.67** | 21.18 | **27.86** |
| 11 | SFT-CODESKILL | Qwen3.5-4B | 6.98 | 23.36 | 54.67 | 23.53 | **27.14** |
| 12 | **CODESKILL (RL)** | Qwen3.5-4B | 13.95 | 27.10 | 56.00 | 29.41 | **31.62** |

### 3.2 Every delta that matters (computed from Table 1; arithmetic verified)

| Comparison | Δ avg pass rate | Share of the +11.03 |
|---|---:|---:|
| CODESKILL − no-skill (headline) | **+11.03** | 100% |
| CODESKILL − **strongest baseline** = Prompt Skill Mgmt (GPT-5.4-mini), row 4 | **+5.10** | — |
| **Prompt Skill Mgmt (GPT-5.4-mini) − no-skill** | **+5.93** | **54%** |
| SFT-CODESKILL − no-skill | **+5.22** | **47%** |
| Prompt Skill Mgmt (**Qwen3.5-4B**, same backbone as CODESKILL) − no-skill | **+0.40** | 4% |
| Subtask Memory − no-skill | +4.16 | 38% |
| **CODESKILL − SFT-CODESKILL (the RL increment over its own warmup)** | **+5.81** | — |
| CODESKILL − Prompt Skill Mgmt (4B, same backbone, no training) | **+10.63** | — |
| 2nd downstream policy: CODESKILL − no-skill | +9.82 | — |
| 2nd downstream policy: CODESKILL − best baseline (row 10) | +3.76 | — |

**Per-benchmark decomposition of the +11.03** (this is where the story gets more interesting than the average):

| Benchmark | No-skill | Prompt Mgmt (GPT-5.4-mini) | SFT-CODESKILL | CODESKILL (RL) | Prompt Δ | SFT Δ | RL Δ | Is Terminal-Bench OOD? |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| EnvBench-Python | 6.98 | 11.63 | 13.95 | 18.60 | +4.65 | +6.97 | +11.62 | in-domain |
| EnvBench-Java | 27.10 | 36.45 | 35.51 | 38.32 | +9.35 | +8.41 | +11.22 | in-domain |
| SWE-Bench Verified | 57.33 | 64.67 | 64.00 | 68.00 | +7.34 | +6.67 | **+10.67** | in-domain |
| **Terminal-Bench 2** | 25.88 | 28.24 | 24.71 | 36.47 | **+2.36** | **−1.17** | **+10.59** | **held out** |

Read the last row twice. On the **only held-out, out-of-distribution benchmark**, the fixed-prompt strong-model curator buys **+2.36**, SFT alone is **negative (−1.17)**, and the RL policy buys **+10.59**. On in-domain benchmarks, RL's increment over the strong prompt baseline is +3.3 to +7.0. The authors' own reading: *"SFT-CODESKILL does not improve over no-skill on Terminal-Bench 2. This suggests that supervised warmup alone may not generalize reliably to unseen SWE task types, while RL with downstream feedback helps CODESKILL learn more transferable skill-management behavior."* [PRIMARY, §4.2] This is the single strongest piece of evidence **for** the RL policy doing something a fixed prompt cannot.

### 3.3 Table 2 — lifecycle ablation [PRIMARY, §4.3]

Frozen downstream policy Qwen3.5-35B-A3B. `Avg` in **bold** is the paper's stated average; the parenthetical is my arithmetic from the four benchmark columns (they agree in all three rows where the paper states an average).

| Variant | EnvBench-Py | EnvBench-Java | SWE-Bench Verified | Terminal-Bench 2 | Avg (paper) | Avg (my arithmetic) | Δ vs no-skill | Skill Num. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| No-skill baseline | 6.98 | 27.10 | 57.33 | 25.88 | — | 29.32 | 0 | **0** |
| Event-driven only | 16.28 | 32.71 | 62.00 | 29.41 | — | 35.10 | +5.78 | **916** |
| Task-level only | 11.63 | 30.84 | 58.67 | 28.24 | — | 32.35 | +3.03 | **336** |
| Extraction only | 13.95 | 41.12 | 64.67 | 31.76 | **37.88** | 37.88 | +8.56 | **1252** |
| Extraction + Evolution | 18.60 | 39.25 | 67.33 | 32.94 | **39.53** | 39.53 | +10.21 | **1252** |
| Full lifecycle | 18.60 | 38.32 | 68.00 | 36.47 | **40.35** | 40.35 | +11.03 | **676** |

Component deltas implied: task-level alone **+3.03**, event-driven alone **+5.78**, both granularities **+8.56**, +evolution **+10.21**, +maintenance **+11.03**. Each of the four lifecycle additions is positive in v2. **There are no error bars, no seeds, and no statement of how many runs any Table 2 row is.** [PRIMARY — the omission is verifiable: a case-insensitive grep of the **entire v2 PDF text** for `seed|std|standard deviation|signific|confidence interval|±|error bar` returns **exactly one hit**, and it is the GRPO advantage definition (`σ_R` "is the standard deviation of rewards within the group"), not a results statistic. The same grep over v1 returns the same single non-result hit.]

**Ambiguity I could not resolve (UNVERIFIED).** Table 2's rows are not labelled as separate trained checkpoints or as test-time restrictions of the final policy. The 3-stage RL curriculum (Phase 1 extraction → Phase 2 +evolution → Phase 3 +maintenance, Appendix A.2) maps onto rows 4/5/6 exactly, and the fact that **rows 4 and 5 both end with 1252 skills** is only coherent if they are the **phase-1 and phase-2 checkpoints** run under the same test-time protocol. I therefore *infer* that Table 2 is a curriculum-stage ablation, but the paper never says so, and Table 2's caption calls it a "skill-bank lifecycle" ablation. Anyone citing the +1.63 for "evolution" or the +0.82 for "maintenance" should carry this ambiguity.

### 3.4 Table 3 — SFT data statistics by output action [PRIMARY, Appendix A.1]

This table doubles as the **operation-type inventory** that §3.1 of the paper points to ("the full list of operation types in Appendix Table 3").

| Action | SFT examples |
|---|---:|
| task-level generate | 2419 |
| event-driven generate | 4485 |
| skip | 1344 |
| evolve | 1718 |
| merge | 1500 |
| add | 790 |
| drop | 600 |
| **Total** | **12856** |

### 3.5 Table 4 — training settings [PRIMARY, Appendix A]

| Setting | Value |
|---|---|
| Backbone model | Qwen3.5-4B-Instruct |
| Training method | LoRA fine-tuning |
| Prompt template | `qwen3_nothink` |
| Max sequence length | 14k tokens |
| Precision | bf16 |
| Hardware | **4×H100 80GB** |
| SFT: epochs / batch / grad-accum / lr / scheduler | 2 / 4 / 8 / 1e-4 / cosine |
| **SFT training time** | **~20 hours** |
| RL: group size | **6 generations per prompt** |
| RL: gradient accumulation | 2 |
| **RL: quality reward weight λ** | **0.25** |
| RL: KL coefficient | 0.02 |
| RL: learning rate | 2e-6 |
| RL: training steps | 500 (130 / 120 / 250 for phases 1 / 2 / 3) |
| RL: rollout temperature | 0.7 |
| Judge model | GPT-5.4-mini |
| Frozen coding policy | Qwen3.5-35B-A3B |
| **RL training time** | **~210 hours** |

### 3.6 Table 5 — RL training data [PRIMARY, Appendix A.2]

| Phase | Instances | Task-level prompts | Event-driven prompts | Evolve prompts | Maintain prompts |
|---|---:|---:|---:|---:|---:|
| Phase 1 | 335 | 335 | 506 | 0 | 0 |
| Phase 2 | 513 | 199 | 302 | 487 | 0 |
| Phase 3 | 632 | 222 | 223 | 384 | 500 |
| **All phases** | **660 unique** | **756** | **1031** | **871** | **500** |

### 3.7 What is **not** ablated — the decisive negative finding

| Ablation the developer needs | Exists? | Evidence |
|---|---|---|
| **RL vs no-RL on the same architecture** | ❌ **No dedicated table.** Only Table 1's cross-table comparison of SFT-CODESKILL (34.54) vs CODESKILL (40.35). | [PRIMARY] |
| **Hybrid reward: remove R_Q (dense rubric) only** | ❌ **Absent.** | grep over both v1 and v2 PDF text for `w/o`, `without`, `remove … reward` returns only the λ formula itself. |
| **Hybrid reward: remove R_E (execution) only** | ❌ **Absent.** | as above |
| **Hybrid reward: remove R_A (alignment gate) only** | ❌ **Absent.** | as above |
| **λ sweep (0.25 vs 0 vs 1)** | ❌ **Absent.** λ=0.25 is stated once, never varied. | [PRIMARY, Table 4] |
| **3-stage curriculum: each stage's contribution** | ⚠️ **Only implicitly**, via Table 2's "Extraction only / +Evolution / Full lifecycle" rows — and the mapping is my inference (§3.3). | [PRIMARY + inference] |
| **Bank size / capacity sweep or compaction ablation** | ⚠️ **Only the by-product** 1252 → 676 in Table 2. No capacity hyperparameter, no sweep, no curve. | [PRIMARY] |
| **Seeds / error bars on any result** | ❌ **None anywhere in the paper.** | [PRIMARY] |
| **Retrieval k (how many skills are injected)** | ❌ **Never stated** — not in §3.2, not in Appendix C. | [PRIMARY] |

This is the crux: **the paper's headline mechanism is a hybrid reward, and the paper never ablates the hybrid reward.** It also never ablates the training method against a strong-model reflective curator. The −5.10 number is a *baseline comparison*, not an ablation of RL.

---

## 4. Version forensics: the maintenance ablation **changed sign** between v1 and v2

This is new information that neither predecessor report contains, and it materially changes how much weight Table 2 can bear.

**v1 Table 2** [PRIMARY — [arXiv:2605.25430v1](https://arxiv.org/pdf/2605.25430v1), p. 8]:

| Variant | EnvBench-Py | EnvBench-Java | SWE-Bench Verified | Terminal-Bench 2 | Avg (my arithmetic) | Skill Num |
|---|---:|---:|---:|---:|---:|---:|
| No-skill baseline | 6.98 | 27.10 | 57.33 | 25.88 | 29.32 | 0 |
| Event-driven only | 16.28 | 32.71 | 62.00 | 29.41 | 35.10 | 916 |
| Task-level only | 11.63 | 30.84 | 58.67 | 28.24 | 32.35 | 336 |
| Extraction only | 13.95 | 41.12 | **65.33** | **34.12** | **38.63** | 1252 |
| Extraction + Evolution | 18.60 | 39.25 | **68.67** | **36.47** | **40.75** | 1252 |
| **Full lifecycle** | 18.60 | 38.32 | **66.00** | **34.12** | **39.26** | 676 |

v1's own prose: *"Adding skill evolution improves the average pass rate from 38.63 to 40.75 over extraction only. **Full lifecycle maintenance slightly reduces the average pass rate by about 2%**, but shrinks the skill bank from 1252 to 676 skills, nearly halving its size. This suggests that maintenance controls redundancy and prevents skill-bank growth during iterative self-improvement while preserving most downstream utility."* [PRIMARY, v1 §4.3]

v2's prose: *"Adding skill evolution improves the average pass rate from 37.88 to 39.53 over extraction only. **Full lifecycle maintenance further improves the average pass rate to 40.35** while shrinking the skill bank from 1252 to 676 skills, a reduction of approximately 46%. These results suggest that maintenance improves the compactness of the skill bank **without sacrificing aggregate performance**."* [PRIMARY, v2 §4.3]

So between v1 and v2, the four lifecycle variants' per-benchmark numbers changed for **three of the four rows** (Extraction-only: SWE 65.33→64.67, TB2 34.12→31.76; Ext+Evo: SWE 68.67→67.33, TB2 36.47→32.94; Full lifecycle: SWE 66.00→68.00, TB2 34.12→36.47), and the **sign of the maintenance ablation flipped from −1.49 to +0.82 points**.

Also changed, in Table 1: no-skill average **29.57 (v1) → 29.32 (v2)** — v2's value is the arithmetically correct mean of the four benchmark columns, so v1 contained an arithmetic error that v2 corrected; v1's headline was therefore "+9.69" on its own stated baseline (or +9.94 against the true mean), and v2's is **+11.03**. CODESKILL under the GPT-5.4-mini downstream policy went 30.73 (v1) → 31.62 (v2), driven by Terminal-Bench 25.88 → 29.41.

**Why this matters for the decision:** CODESKILL's compact-bank-maintenance story — the component a zero-compute developer most needs to reimplement — is the component whose measured benefit **reversed sign in a revision that publishes no seeds, no error bars, no run counts, and no changelog**. Both versions report the same bank size (1252 → 676), so the mechanism was identical; only the measured effect moved. A +0.82-point difference with no variance estimate is far inside the 2.2–6.0 pp single-run agentic-eval variance documented in the predecessor report ([arXiv:2602.07150](https://arxiv.org/abs/2602.07150)). Treat "maintenance pays for itself" as **v2-version-specific and unpowered**, not as a robust finding. ⚠️ I did not check whether the v1→v2 change is documented in an arXiv comment; the v2 arXiv page shows no comment field and the paper text reports no revision note.

---

## 5. The architecture, precisely enough to reimplement without RL

[PRIMARY — §3.1, §3.2, §4.1, Appendix C, Appendix D]

### 5.1 The learnable policy M_θ is a function of exactly this

`u = M_θ(q)` where **`q = (τ, s̃, C)`**:

| Symbol | Meaning |
|---|---|
| `τ` | **trajectory evidence** — "ranging from a single trajectory to a small set of related trajectories," normalised into a unified **reasoning–action–observation** format (task context + interleaved steps + final outcome). Task-level extraction takes **2–3 related trajectories**; event-driven extraction takes **one full trajectory**; evolution takes **one trajectory** plus one or more candidate/existing skills. |
| `s̃` | optional candidate or existing skill (markdown text) |
| `C ⊆ B` | retrieved similar skills from the bank (for maintenance, "the candidate prior knowledge item and the existing prior knowledge entries") |

Output **`u = (a, z)`** where `a` is the operation and `z` the content. At test time, this is a **single forward pass of Qwen3.5-4B-Instruct emitting a JSON object**; every op is defined by a prompt template (Figures 6–9) and a JSON schema.

### 5.2 Operation types — the complete set (7 actions)

| Op | Granularity | Input | Output | Skip condition |
|---|---|---|---|---|
| `generate` | task-level (`"granularity": "general"`) | 2–3 related trajectories + optional result summaries | one skill | evidence weak / contradictory / accidental / too local / collapses to an event reaction |
| `generate` | event-driven | one full trajectory | one skill | no strong reusable local event; lesson too task-specific or workflow-level |
| `skip` | either | trajectory evidence | `{action, reason}` | as above |
| `evolve` | preserves the target's granularity | one skill + one trajectory + result summary | `{target_skill_id, reason, skill}` | evidence weak/contradictory/too local, or the trajectory is better described as a new skill |
| `add` | — | candidate + retrieved similar skills | `{action, reason}` | — |
| `merge` | — | candidate + retrieved similar skills | `{action, merge_target_skill_id, reason, skill}` | — |
| `drop` | — | candidate + retrieved similar skills | `{action, reason}` | — |

Note the **asymmetry that matters for a reflective reimplementation**: `evolve` revises **exactly one** existing skill; `merge` targets **exactly one** retrieved skill; there is no "split" operation, no "reorder", no "retire-by-id" outside `drop`-on-candidate. **The policy can only ever drop a *newly proposed* candidate, never an already-admitted bank entry.** This is precisely the failure mode Ratchet/`Library Drift` identifies (see §8) — CODESKILL's maintenance has no eviction of admitted skills, only admission control. [PRIMARY for the schema; **inference** for the consequence]

### 5.3 Skill representation

"Each skill file contains a **short title**, a **granularity label**, an **applicability condition `when_to_apply`**, and a set of **actionable `rules`**." Natural-language instruction files only — no scripts, APIs, or tools ("since the coding-agent environments already provide fixed tools and execution interfaces"). **Provenance** (source instance ids) is tracked through evolution and merging and is used to exclude same-instance leakage at eval. Two granularities: **task-level** ("High-level strategies for a task or family of related tasks … inspect the repository, localize the issue, validate a fix") and **event-driven** ("local guidance for recurring execution events, such as command failures, error messages, test-output patterns, or repeated failure modes after specific actions").

Appendix D gives two full worked examples, both Maven/Java and both marked *"produced by a merge operation"*: a task-level skill *"Diagnose Maven build failures via environment, config, and dependency resolution"* (8 rules) and an event-driven skill *"Handle missing Maven test-jar dependencies"* (8 rules). These are the best available templates for a reimplementation. [PRIMARY]

### 5.4 Retrieval

| Aspect | Spec |
|---|---|
| Encoder | `sentence-transformers/all-MiniLM-L6-v2` |
| Index | **dense**, built separately **(a) per benchmark and (b) per skill type** |
| Retrieval document | `title + when_to_apply + rules` |
| Task-level query | task goal + problem statement + available repository/benchmark context; retrieved **once**, before solving; appended to the **initial user prompt** |
| Event-driven query | constructed **online** from "current task context, recent reasoning, executed actions, observations, error messages, command outputs, and test-output snippets" |
| Scope constraint | "Retrieval is scoped to the same benchmark and same granularity" |
| Leakage control | "skills generated from the same evaluation instance are filtered out" |
| **k (number injected)** | **NOT STATED** |

### 5.5 Bank sizes and lifecycle

Final bank **676 skills** (full lifecycle, v2); 1252 for extraction-only and extraction+evolution; 916 for event-driven-only; 336 for task-level-only. Test-time construction is **two passes** over the test set: pass 1 extracts skills from **no-skill** rollouts; pass 2 evolves skills using **skill-conditioned** rollouts. Every candidate passes through maintenance. No cap, budget, or capacity hyperparameter is reported.

### 5.6 What the policy is trained on

SFT: 12,856 teacher-generated examples (GPT-5.4-mini teacher) over the seven actions (Table 3), LoRA, 2 epochs, ~20 h on 4×H100. RL: GRPO from the SFT checkpoint, 500 steps, G=6, λ=0.25, KL 0.02, ~210 h on 4×H100.

---

## 6. The rubric — published, verbatim, and directly reusable

[PRIMARY — Appendix B + Figures 10–14 in the **PDF text layer** of [arXiv:2605.25430v2](https://arxiv.org/pdf/2605.25430v2). The HTML drops these figures. Quotes below are from the PDF and are verbatim apart from LaTeX-to-ASCII field-name normalisation.]

**Scoring rule (Appendix B, verbatim):** *"Each rubric consists of multiple dimensions, and each dimension is further decomposed into binary yes/no questions. The final rubric reward is computed as the number of satisfied yes/no questions divided by the total number of yes/no questions in the rubric. Thus, the relative weight of each dimension is determined by the number of questions assigned to it, while the final reward remains normalized to [0, 1]."*

Every judge opens with: *"You are an expert judge for skill-manager outputs. **You are strict and critical by default. When in doubt, give a lower score.**"*

**Figure 10 — Task-level skill quality judge** (max score 16):

- `groundedness, 0–3` — Q1: every rule is directly traceable to observable trajectory behavior or outcome. Q2: `when_to_apply` is directly supported by trajectory signals. Q3: no rule is contradicted, absent, or weakly hinted.
- `reusability, 0–3` — Q1: rules avoid repository names, file paths, versions, or identifiers. Q2: rules transfer to at least two distinct project types. Q3: applicability is broad enough for unseen repositories but not nearly every coding task.
- `specificity, 0–3` — Q1: each rule gives a concrete executable action or check. Q2: rules add value beyond common engineering practice. Q3: rules would not equally apply to most unrelated coding tasks.
- `format validity, 0–1` — The output is valid and complete.
- `when to apply quality, 0–3` — Q1: applicability contains discriminating conditions. Q2: it would not trigger on clearly different tasks. Q3: it is narrow enough to avoid applying to most SWE tasks.
- `task level granularity, 0–3` — Q1: the output is a multi-step workflow-level pattern. Q2: it can guide a new agent from the start of a similar task. Q3: it is not primarily a local reactive rule.

**Figure 11 — Event-driven skill quality judge** (max 16): same skeleton with `when_to_apply quality` Q1 = "the trigger is specific and recognizable", and `event level granularity` Q1–Q3 = "focuses on one local trigger-response pattern" / "local and reactive rather than workflow-level" / "the trigger is distinguishable from other common events"; `reusability` Q1 forbids "exact error text."

**Figure 12 — Skill evolution quality judge** (max 16): `groundedness 0–3`, `reusability 0–3`, `specificity 0–3`, `format validity 0–1`, **`failure responsiveness, 0–3`** (Q1: new evidence reveals a failure, limitation, contradiction, missing case, or caution. Q2: the update directly addresses it. Q3: the update would change a future concrete decision), **`update quality, 0–3`** (Q1: preserves skill identity. Q2: adds, corrects, narrows, or sharpens non-redundant content. Q3: the final skill is coherent and focused).

**Figure 13 — Skill-bank maintenance **merge** judge** (max 22, 8 dimensions): `target_choice_correct 0–3`, `target_overlap_substantive 0–3` (**"candidate and target have at least 30% conceptual rule overlap"**), `merge_integration_quality 0–3`, `identity_preserved 0–3`, `no_critical_loss_target 0–3`, `no_critical_loss_candidate 0–3`, `merged_when_to_apply_tightness 0–3` (Q3: "contains no over-generalized trigger such as 'any build issue' or 'any failure with logs'"), `format_validity 0–1`. Prefaced by: *"maintain decisions are made without a trajectory. … Judge the merge purely on the textual evidence of the two sides and the merged result."*

**Figure 14 — Behavior alignment judge** (max 8): `when_to_apply_match 0–2`, `rule_specificity 0–3`, `trajectory_evidence 0–3`. With the key instruction: *"**Do not reward task success, trajectory length, or apparent competence.** Generic exploration does not earn credit unless the prior knowledge is specific and distinctive."*

**Two gaps worth flagging for a reimplementation.** (i) Figure 13 judges **`merge` only** — there is **no published rubric for `add` or `drop`**, even though the paper says rubric weights are "action-specific" for five judges (§A.2 → Figures 10–14). (ii) The paper never says what `merge` does with `drop`-like decisions on skills already in the bank, because it cannot (§5.2).

**Reward composition** [PRIMARY, §3.3.2 + Appendix B]:

```
R(u, q) = λ·R_Q(u, q) + R_A(u, τ_u)·R_E(u, x_u, π)      with λ = 0.25
R_E(u, x_u, π) = V(τ_π^u) − b_π(x_u)                    V ∈ [0,1] verifier score
b_π(x_u) = (1/n) Σ_i V(τ_{π,i}^0),  n = 4               pre-computed no-skill baseline
R_Q, R_A ∈ [0,1]                                        rubric / alignment judge scores
```
For `skip`, `add`, `drop`: *"we use only the quality reward with a higher weight."* Reverse retrieval picks the rollout task: `x_u ∼ TopK(s_u, D_task)`, reported without a k.

**Design-level implication (not an ablation).** Because λ = 0.25 and R_E ∈ [−1, 1], the **execution term can move the reward 4× further than the rubric term** — the authors deliberately weight execution feedback over skill quality. Figure 3's prose is consistent: *"The quality reward … is more stable and rises before stabilizing after roughly 100 steps,"* while the execution trend is still climbing at steps 180–200 (0.004 → 0.158). But **the paper never removes either term**, so this is a design statement, not a measured decomposition.

---

## 7. Per-skill vs global optimisation, and credit assignment across co-retrieved skills

[PRIMARY + inference]

- **Per-skill, not bank-global.** Every operation in the schema targets **one** skill: `generate` produces one skill, `evolve` revises exactly one `target_skill_id`, `merge` combines the candidate with exactly one `merge_target_skill_id`. There is no operation over a *set* of skills. By contrast, SkillBrew explicitly formulates **bank-level** curation with a bank-level utility/diversity/coverage objective and a Pareto selector over **candidate banks** (§8) — CODESKILL's action space cannot express that.
- **Skill-level credit assignment is explicitly attempted, and only as a proxy.** *"This attribution-aware design combines dense quality supervision with baseline-relative execution feedback, gated by behavioral evidence of skill use. **It provides a practical proxy for skill-level credit assignment** by discounting execution feedback when the rollout does not reflect the skill's trigger conditions or prescribed behavior."* The mechanism: `R_E` is a **baseline-relative** improvement (skill-conditioned rollout minus the same instance's 4-rollout no-skill mean) and it is **multiplied by `R_A`**, an LLM judge asking whether the trajectory actually followed the skill. If the agent succeeded without using the skill, `R_A → 0` and the execution credit is zeroed.
- **Credit assignment across *co-retrieved* skills is never discussed.** Retrieval injects task-level and event-driven skills together (k unstated), and the RL reward is computed for **one candidate skill at a time** by reverse-retrieving a *matched* task and running it with that skill. There is no experiment where two candidate skills are co-injected and credit is split. So CODESKILL's "attribution-aware" reward solves *skill-vs-no-skill* attribution, **not** *which of the k retrieved skills caused the outcome*. This is a genuine gap and is the same gap Ratchet attacks with leave-one-out / contribution-based eviction (§8).
- **`R_A` is a text-space device that does not require training.** It is an LLM-as-judge prompt (Figure 14). Nothing about computing `R_A` (or `R_Q`) needs gradients; only the GRPO *update* does. [**Inference**, but a strong one — the judge templates are pure prompts.]

---

## 8. Compute cost, and what it implies for a reflective loop

[PRIMARY, Appendix A]

| Component | Cost |
|---|---|
| SFT | ~20 h × 4×H100 = **~80 H100-GPU-hours** |
| RL (GRPO, 500 steps) | ~210 h × 4×H100 = **~840 H100-GPU-hours** |
| **Total reported training** | **~230 h wall-clock / ~920 H100-GPU-hours** |
| **Not counted in the above** | the *inference* cost of the reward loop |

The inference cost is the expensive part and the paper does not price it. Reconstructing it from Tables 4–5:

- **RL prompt pool: 756 + 1031 + 871 + 500 = 3,158 prompts** across all phases, over **660 unique task instances**.
- Group size **G = 6** ⇒ **~18,950 sampled operations** during training.
- **Every** operation that yields an injectable skill (`extract`, `evolve`, `merge`) triggers a **full long-horizon agent rollout of Qwen3.5-35B-A3B on a real SWE task**, plus **two GPT-5.4-mini judge calls** (`R_Q`, `R_A`).
- **Plus 4 baseline rollouts × 660 instances = 2,640 rollouts** of the same 35B policy, pre-computed (Appendix B).
- **Plus** SFT trajectory collection (mini-SWE-agent on SWE-smith + a ReAct agent on EnvBench) and **two full test-time construction passes** with rollouts.
- Rollout temperature 0.7; judge = GPT-5.4-mini (a closed frontier model).

**Order of magnitude: ~10⁴ long-horizon 35B SWE-agent rollouts plus ~10⁴ frontier-model judge calls, on top of ~920 H100-GPU-hours.** [PRIMARY numbers; **arithmetic is mine** and labelled as such]

**Can a reflective loop plausibly reach a similar place with far fewer rollouts?** The published comparators say the *rollout count* is not the barrier — the *feedback quality* is:

| Method | Frozen? | Rollouts | Result | Source |
|---|---|---|---|---|
| **GEPA** | weights frozen, prompt-only | "up to **35× fewer** than GRPO's 24,000" | +6% avg / up to +20% **over GRPO** | [PRIMARY, arXiv:2507.19457](https://arxiv.org/abs/2507.19457) (predecessor §1.2) |
| **gskill** (GEPA + SWE-smith, repo-specific `SKILL.md`) | weights frozen | **"under 300 rollouts"**; ~300 SWE-smith tasks, ~200/50/60 split | Mini-SWE-Agent (gpt-5-mini) **Jinja 55→82, Bleve 24→93**; transfers to Claude Code (Haiku 4.5: Bleve 79.3%→98.3%, **173 s→142 s**) | [PRIMARY — author post, [gepa-ai/gepa blog 2026-02-18](https://raw.githubusercontent.com/gepa-ai/gepa/refs/heads/main/docs/docs/blog/posts/2026-02-18-automatically-learning-skills-for-coding-agents/index.md); ⚠️ blog, not peer-reviewed, SWE-smith tasks are "on the simpler side" by the authors' own admission] |
| **CoEvoSkills** | no weight updates; LLM generator + verifier | 85 tasks, **4.1 verification cycles/task**, mean **2.4** ground-truth-oracle rounds; K=5, M=15 budget | SkillsBench: 30.6% → **71.1% (+40.5 pp)** | [PRIMARY, arXiv:2604.01687](https://arxiv.org/abs/2604.01687) |
| **Ratchet** | frozen Opus 4.7 | 100 rounds, 3 seeds (+ 150 SWE-V instances) | MBPP+/100 **+0.328**; **SWE-V/150 no-skill 0.65 → 0.87 peak** | [PRIMARY, arXiv:2605.22148](https://arxiv.org/abs/2605.22148) |
| **SWE-Exp** | no weight updates; experience bank | bank saturates near **~300 experiences** | **73.0% Pass@1 SWE-Bench Verified** (Claude 4 Sonnet) | [PRIMARY, arXiv:2507.23361](https://arxiv.org/abs/2507.23361) |
| **CODESKILL** | downstream policy frozen, **manager trained by RL** | **~19k sampled ops ⇒ ~10⁴ 35B rollouts + 2,640 baseline rollouts**, 920 H100-GPU-h | +11.03 avg | [PRIMARY] |

So: the zero-compute methods operate at **10²–10³ rollouts**, CODESKILL at **~10⁴**. gskill is the single closest precedent to the developer's exact proposal (GEPA reflective evolution of a `SKILL.md` for a *repository*, verified by executable SWE-smith tests, <300 rollouts), and it reports the largest single-repository codegen gains in this literature. That is encouraging for the plan. **But the predecessor report's caveats apply and should not be dropped: gskill is a vendor blog, on SWE-smith (tasks the "Skill Issue" study argues are too easy to be informative), and no peer-reviewed replication exists.**

---

## 9. Has anyone already tried this? — reflective/no-training curators over skill banks

**Answer: yes for skill banks in general; almost none on repo-level codegen; the two that are on coding harnesses disagree sharply.** No paper I found runs a reflective, per-skill loop over CODESKILL's multi-granularity shared bank on SWE-Bench Verified with a free verifier. The nearest are CoEvoSkills (reflective, coding harnesses, but **per-task** skill bundles, not a shared cross-task bank), Ratchet (training-free maintained library, **shared bank**, repo-level, but no reflection over skill *text* — it evicts, it does not rewrite), and SWE-Exp (training-free shared experience bank on SWE-Bench Verified, but memory items are distilled *subtask summaries*, not evolved procedural skills).

Legend: **R** = reflective / prompt-based / training-free curator. **T** = trained (RL, gradient, or fine-tuning). **Repo-level?** = SWE-Bench-family repo-level code generation (as opposed to spreadsheet/QA/embodied/web).

| System | Curator | Trained or reflective? | Bank shape / size | Benchmarks | Repo-level codegen? | Headline vs its no-skill control | Ablation isolating the curator? |
|---|---|---|---|---|---|---|---|
| **CODESKILL** (2605.25430) | LLM policy M_θ | **T** — SFT + GRPO | 2 granularities, shared bank, 676–1252 skills | EnvBench, SWE-Bench V, Terminal-Bench 2 | ✅ | **+11.03** avg; +10.67 SWE-Bench V; +10.59 TB2 | ⚠️ lifecycle only; **no reward or RL-method ablation** |
| **Prompt Skill Mgmt** *(CODESKILL's own baseline)* | fixed prompts + heuristics | **R** — no loop, no feedback | same schema, same bank machinery | same | ✅ | **+5.93** (GPT-5.4-mini) / **+0.40** (Qwen3.5-4B) | — |
| **SFT-CODESKILL** *(CODESKILL's own baseline)* | LoRA-tuned 4B | **T** — SFT only, no RL | same | same | ✅ | **+5.22** | — |
| **CoEvoSkills** (2604.01687, COLM 2026) | Skill Generator + co-evolving Surrogate Verifier | **R** — no weight updates | **per-task** multi-file skill bundles | **SkillsBench** (Claude Code + Codex harnesses) | ⚠️ coding-agent harnesses, 85 expertise-heavy tasks — **not SWE-Bench** | **+40.5 pp** (30.6→71.1) | ✅ **yes** — `w/o surrogate verifier` **41.1 (−30.0)**; `w/o evolution (context only)` **42.4 (−28.7)** |
| **SkillsBench self-generated** (2602.12670) | one-pass skill authoring (Anthropic skill-creator) | **R** — no loop | packs authored per task, no bank | SkillsBench (87 tasks, 8 domains incl. SWE n=16) | ⚠️ harness-level, deterministic verifiers | **−8.1 pp** (Claude Code+Opus 4.7), **−11.3** (Codex+GPT-5.5), **−11.5** (Gemini CLI) — **negative** | ✅ vs curated (+18.2 to +24.8) |
| **Ratchet / "Library Drift"** (2605.22148) | contribution-based eviction + capacity cap + constrained synthesis | **R** — frozen model, no skill-text reflection | **shared library**, cap C | **MBPP+/100**, **SWE-V/150**, report-composition | ✅ (SWE-V/150) | **+0.328** MBPP+/100; **+0.22** SWE-V/150 (peak, 3 seeds) | ✅ A1–A6; 4 mechanisms load-bearing incl. eviction with an evidence floor |
| **SWE-Exp** (2507.23361) | multi-faceted experience bank, LLM reranking | **R** — no weight updates | shared bank, hierarchical, **saturates ~300 items** | **SWE-Bench Verified** | ✅ | **73.0% Pass@1** (Claude 4 Sonnet) | ✅ comprehension −3.2, modification −2.6, dual-agent −2.2, **exp. extraction −6.0**, **LLM reranking −3.8**; exp. count 0→37.8%, 1→42.0% peak |
| **gskill / GEPA** (gepa blog 2026-02-18; [CAIS 2026 demo](https://dlnext.acm.org/doi/10.1145/3786335.3813196)) | GEPA reflective proposer + Pareto pool | **R** — no weight updates | **one `SKILL.md` per repository** | SWE-smith tasks (Jinja, Bleve) | ✅ per-repository | **24→93 (Bleve), 55→82 (Jinja)**; transfers to Claude Code | ❌ not published |
| **SkillBrew** (2605.29440) | bi-level propose-then-verify, Pareto over **candidate banks** | **R** — "training-free"; explicitly *excludes* training-based baselines (SkillRL) | shared bank, **bank-level** utility/diversity/coverage | ALFWorld, WebShop | ❌ | ALFWorld 59.0 avg; GPT-4o 46.4→88.1 | ✅ objectives (Jutil 45.8 → +Jdiv+Jcov 59.0); **edit ops: ADD 47.0 / ADD+REMOVE 48.3 / ADD+REWRITE 53.5 / all three 59.0** |
| **Skill-Pro** (2602.01869, ICML 2026 Spotlight) | "non-parametric PPO": semantic gradients + **PPO Gate** + score pruning | **R** — "does not modify a single LLM parameter" | skill pool, capacity K, **~816 tokens total** | ALFWorld, Mastermind | ❌ | ALFWorld OOD 0.909; reuse rate 0.925 | ✅ w/o semantic gradient; **w/o PPO Gate (hallucinated skills enter)**; w/o online pruning | 
| **SLIM** (2605.10923) | per-skill marginal contribution by **leave-one-skill-out**, then retain/retire/expand | **T** — joint with RL policy | dynamic active skill set | ALFWorld, SearchQA | ❌ | +7.1 pts over best baseline | ✅ retain/retire/expand |
| **SkillForge** (2604.08618) | Failure Analyzer → Skill Diagnostician → Skill Optimizer, iterative | **R** — no training reported | skill files, cloud-support domain | 5 cloud-support scenarios, 1,883 tickets | ❌ (support tickets) | evolution surpasses expert-authored skills over 3 cycles | ⚠️ partial |
| **SkillClaw** (2604.08377) | autonomous agentic evolver over a shared repo | **R** | shared cross-user repository | WildClawBench | ❌ | +42.1% avg on custom queries (1 round) | ⚠️ partial |
| **SkillNet** (2603.04448) | ontology + multi-dim evaluation (Safety/Completeness/Executability/Maintainability/Cost) | **R** | ~600k skills | ALFWorld, WebShop, ScienceWorld | ❌ | +40% avg reward, −30% steps | infrastructure, not an ablation |
| **ExpeL** (AAAI 2024) | reflective insight extraction from success/failure | **R** | insight list | HotpotQA, ALFWorld, WebShop, FEVER-family | ❌ | — | — |
| **Voyager** (2305.16291) | iterative prompting + self-verification | **R** ("bypasses the need for model parameter fine-tuning") | **executable code** skill library, ever-growing | Minecraft | ❌ | 3.3× items, 2.3× distance, up to 15.3× faster | — |
| **Agent Workflow Memory** (ICML 2025) | workflow induction from trajectories | **R** | workflow bank | Mind2Web, WebArena | ❌ | — | — |
| **AutoRefine** (2601.22758) | typed Rule/Skill/Subagent + contract gate + **replay gate** | **R** | typed artifacts | ALFWorld, ScienceWorld, TravelPlanner, SpreadsheetBench, SkillCraft | ❌ (SpreadsheetBench = spreadsheet code) | TravelPlanner 80.56% vs 50.0% | ✅ boundary closure −15.00, **replay validation −16.11** |
| **Trace2Skill** (2603.25158) | parallel trajectory consolidation into a skill directory | **R** | skill directory | SpreadsheetBench-Verified (+ math, VQA) | ❌ | up to +57.65 pp transfer to a larger model | ✅ per-seed std; **"each addition simultaneously fixes and breaks tasks"** |
| **EvoSkill** (2603.02766) | failure analysis + Pareto selection | **R** ("the underlying model remains frozen") | skill folders | OfficeQA, SealQA, BrowseComp | ❌ | +7.3 / +12.1 | — |
| **SkillRL** (2602.08234) | recursive skill-bank co-evolution during RL | **T** | hierarchical SkillBank | ALFWorld, WebShop, 7 search QA | ❌ | 89.9% ALFWorld, +12.3 over its own GRPO base | ✅ vs prompt/memory baselines |
| **AutoSkill** (2603.01145) | extract → maintain → retrieve, skill repository | **R** — "*training-free, prompt-driven*"; no parameters updated | skill repository, model-agnostic plug-in | dialogue/personalisation (not codegen) | ❌ | — | — |

**Decisive observations from this table.**

1. **Nobody has run the developer's exact experiment.** The closest single artifact is **gskill** (GEPA + SWE-smith + repo `SKILL.md`): reflective, <300 rollouts, repo-level, large gains — but a blog, unrefereed, and per-repository rather than a shared cross-task bank.
2. **The two coding-harness reflective results are opposites.** CoEvoSkills: **+40.5 pp** from iterative co-evolution. SkillsBench self-generated: **−8.1 to −11.5 pp** from one-pass authoring. The difference CoEvoSkills itself identifies is the loop and the diagnostic feedback — its own ablation shows a loop with only an opaque pass/fail signal scores **41.1**, statistically the same as **not evolving at all (42.4)**. That is a 30-point cliff between "iterating with a binary verifier" and "iterating with a synthesised diagnostic verifier."
3. **No published system replaces CODESKILL's RL policy with reflection.** SkillBrew comes closest conceptually (training-free, bank-level, Pareto) but never touches code; Skill-Pro comes closest mechanically (a *formal* no-gradient PPO analogue with a PPO Gate) but never touches code; SkillForge and SkillClaw are reflective but in support/assistant domains.
4. **The maintenance operation that CODESKILL's RL policy learns is available training-free, and is load-bearing.** Ratchet's four load-bearing mechanisms include **eviction with an evidence floor**, and its abstract states the unaudited alternative plainly: *"LLM-written skills are worth +0.0 percentage points (pp) against a no-skill control, human-written ones +16.2pp. Unmaintained, a library enters library drift, growing until injecting a skill scores worse than injecting nothing."* [PRIMARY, [arXiv:2605.22148](https://arxiv.org/abs/2605.22148)] SkillBrew's edit-operation ablation agrees on the direction: **ADD-only 47.0 → all three ops 59.0** on ALFWorld. And Ratchet's judge-reliability result is a hard constraint on any free-verifier loop: *"a judge scoring failures as passes at rate (1−τ)/2 or above retires nothing, at any sample size."*

---

## CAN REFLECTION REPLACE THE RL POLICY?

### Evidence-based answer

**Yes for the larger half — the architecture, the bank, and the retrieval — with moderate-to-high confidence. No for the specific +5.1-to-+5.8 increment, where the evidence is absent, not negative, and where two 2026 results show that a *naive* reflective loop over coding agents is actively harmful.**

Decomposed, because "how much" has three separable answers:

| Component of CODESKILL | Is it available without RL? | Measured or inferred value | Confidence |
|---|---|---|---|
| Multi-granularity extraction + retrieval + bank **existing at all** | ✅ yes, by construction | **at least +5.22 to +5.93** of the +11.03 (Table 1 rows 4 & 5) | **High** — direct, same-pipeline baselines, PRIMARY |
| **Compact bank maintenance** (add/merge/drop) | ✅ yes — several training-free mechanisms exist (Ratchet eviction, SkillBrew multi-objective, Skill-Pro pruning) | v2 says **+0.82** over extraction+evolution; v1 said **−1.49**. Treat as **0 ± 2** | **Low** — sign flipped between versions, no seeds, inside known single-run variance |
| **The RL-trained policy itself** (the "learned management policy") | ❓ untested | **+5.10** vs the strong fixed-prompt curator; **+5.81** vs SFT; **+10.59 on the held-out OOD benchmark vs +2.36 for the fixed prompt** | **Low** — no ablation isolates the training method from the reward design or the backbone |

### Justification, from the numbers

1. **The −5.10 baseline is a reflective curator on the same architecture with a *stronger* model, and it has no feedback loop.** Verbatim: *"We therefore keep the same pipeline, action space, prompts, retrieval procedure, downstream policy, and decoding settings as CODESKILL, while replacing the learned skill-management policy with fixed prompt-based decisions."* [PRIMARY, Appendix C] And: *"This baseline follows the common design of prior automatic skill-bank management methods, such as SkillRL and AutoSkill."* [PRIMARY, §4.1] **It is not ExpeL, Voyager, or AWM.** This matters enormously in the developer's favour: the thing that scored **+5.93** is a *zero-shot, fixed-prompt, no-iteration, no-verifier-feedback* curator. A reflective optimizer with the free verifier is a strict superset of that baseline's capabilities. So **+5.93 is a floor, not an estimate**, for "same architecture, strong LLM, no training."
2. **The authors themselves attribute the 4B prompt baseline's failure to model strength, not to the absence of RL.** *"Prompt-based skill management with the small Qwen3.5-4B backbone brings little improvement over no-skill, indicating that **a weak model is insufficient for the same skill-management pipeline**."* And *"SFT-CODESKILL improves average pass rate over no-skill, but **remains weaker than prompt-based management with a stronger closed-source model**."* [PRIMARY, §4.2] The paper's own causal story is *capability of the manager*, not *presence of gradients*. That is the single most encouraging sentence in the paper for the developer's plan.
3. **The hidden driver of the "+5.1" may be reward design, not gradient descent — and reward design is a text artifact.** `R_Q` and `R_A` are LLM-judge prompts (Figures 10–14, published verbatim). `R_E` is a baseline-relative execution delta computed from a free verifier — computable offline with no gradients. A reflective loop can import **all three** verbatim, and can use `R_A·R_E > 0` as a candidate-acceptance filter in exactly the way GRPO uses it as a reward signal. GRPO's contribution on top of that is: sample G=6, normalise advantages, do a policy-gradient step. **The paper provides no experiment separating "the reward design did the work" from "the 4B parameters learned something."** Since λ = 0.25 puts the rubric at only 20% of the reward range while the execution term spans [−1, 1], the design says the *execution* signal dominates — and the execution signal is free. [PRIMARY for all the components; **inference** for the conclusion]
4. **The counter-evidence is real and specific, and it is about feedback quality, not about RL.** CoEvoSkills' own ablation is the sharpest warning available: on coding harnesses, a reflective loop with **only an opaque binary verifier** scores 41.1 (−30.0 vs full), indistinguishable from **not running the loop at all** (42.4). The loop that scores 71.1 has a *co-evolving surrogate verifier that synthesises structured failure diagnostics*. SkillsBench is the second warning: one-pass LLM-authored skills for coding agents land at −8.1 to −11.5 pp, with the audit blaming "generated packs the solver never discovers, creator-side authoring that displaces solver work, and confidently wrong pack content." **A developer whose loop is "reflect on the trajectory, rewrite the skill, keep it if the build passes" is running the 41.1 condition, not the 71.1 condition** — unless they build the diagnostic-feedback half (which, in a local dev setting with visible test output, they partially have for free).
5. **The OOD result argues against a clean substitution on transfer.** Terminal-Bench 2 is the only benchmark not used in training. There: fixed-prompt strong-model curator **+2.36**, SFT **−1.17**, RL **+10.59**. If the RL gain were mostly "the reward design", you would expect the fixed-prompt curator (which shares the prompts) to capture some of it on OOD. It captures almost none. Conversely, this is a single number with no seeds on a benchmark where the same model's in-domain numbers moved by 2+ points between paper versions. [PRIMARY numbers; **the interpretation is mine and it cuts against substitution**]
6. **Two training-free systems show the RL increment is not necessary for large repo-level coding gains.** Ratchet: a *frozen* Opus 4.7 with a training-free maintained library, **SWE-V/150 no-skill 0.65 → 0.87 peak**. SWE-Exp: a training-free experience bank reaching **73.0% Pass@1 on SWE-Bench Verified**. gskill: reflective GEPA over a repo `SKILL.md`, **<300 rollouts**, Bleve 24→93. Each exceeds CODESKILL's +5.1 RL increment in its own setting. **None is a controlled comparison** — different models, different splits, different benchmarks, and the predecessor report's leakage and variance caveats apply ([arXiv:2410.06992](https://arxiv.org/abs/2410.06992), [arXiv:2602.07150](https://arxiv.org/abs/2602.07150)) — but collectively they establish that the *ceiling* is not RL-gated.

### What the evidence cannot support

- It **cannot** give a number for "reflective per-skill optimization on CODESKILL's architecture with a free verifier." The correct cell (strong model + improvement loop + verifier feedback) is **measured nowhere**: Table 1 has strong-model-no-loop (35.25) and weak-model-with-RL (40.35), and the paper has no third cell.
- It **cannot** say how much of `+11.03` comes from the dense rubric vs the sparse execution reward vs the alignment gate. **That ablation does not exist in either version.**
- It **cannot** say how much the 3-stage curriculum buys, because Table 2's rows are not labelled as curriculum checkpoints ("extraction only" / "+evolution" / "full lifecycle" match phases 1/2/3, but this is my inference).
- It **cannot** support the maintenance result at all confidently, because the sign reversed between v1 and v2 with no seeds and no variance.
- It **cannot** say whether the upstream results are stable: **zero seeds, zero error bars, zero significance tests anywhere in the paper**, against a documented 2.2–6.0 pp single-run agentic-eval σ.

### Confidence

| Claim | Confidence |
|---|---|
| CODESKILL's own prompt-based curator on the *same* architecture gets **+5.93 of +11.03 (54%)** with a strong LLM, **+0.40** with a 4B LLM | **HIGH** — PRIMARY, Table 1, same-pipeline baseline explicitly described in Appendix C |
| The −5.10 baseline is a same-architecture fixed-prompt curator adapted from SkillRL/AutoSkill, **not** ExpeL/Voyager/AWM | **HIGH** — PRIMARY, §4.1 + Appendix C |
| CODESKILL has **no reward-component ablation and no RL-method ablation** | **HIGH** — exhaustive table inventory + grep over both versions |
| A reflective, strong-model, verifier-fed per-skill loop would recover **at least the +5.9 architecture half** | **MODERATE-HIGH** — the baseline it must beat is weaker than it in every respect |
| It would recover **most** of the RL increment (i.e. land ≥ +9) | **LOW-MODERATE** — plausible from Ratchet/SWE-Exp/gskill/CoEvoSkills magnitudes; unsupported by any controlled comparison |
| A *naive* reflective append-and-keep loop would **fail or regress** on coding agents | **MODERATE-HIGH** — SkillsBench −8.1/−11.3/−11.5 pp across three harnesses; CoEvoSkills' binary-feedback arm ≈ no-evolution |
| The specific mechanism that decides success is **maintenance/attribution + diagnostic feedback**, neither of which requires gradients | **MODERATE** — convergent across Ratchet (eviction with an evidence floor), SkillBrew (REMOVE and REWRITE both matter), Skill-Pro (PPO Gate and pruning both matter), CoEvoSkills (surrogate verifier), AutoRefine (replay gate −16.11); but all in non-SWE domains except Ratchet |

### The falsifiable prediction (and its honest error bars)

Given CODESKILL's architecture, a strong reflective optimizer, per-skill evolution, and a working free execution verifier:

- **Predicted outcome: roughly 6 to 9 of the 11.03 points**, i.e. **55–80%** of the headline, with the architecture half (+5.9) essentially assured and the RL half partially recovered. Point estimate **~+7.5**.
- **The prediction is conditional on three things the developer must build, all of which are the *substitute* for the training loop:** (i) **per-skill contribution estimation from the verifier** (leave-one-out or baseline-relative, as in CODESKILL's own `R_E` and Ratchet's eviction statistic), not just pass-rate-of-the-bank; (ii) **eviction with an evidence floor**, since CODESKILL's action space cannot drop admitted skills and SkillsBench shows unmaintained reflective libraries go negative; (iii) **diagnostic feedback richer than pass/fail** — CoEvoSkills' 30-point cliff between an opaque bit and synthesised diagnostics is the largest single effect in this entire evidence base.
- **If the developer skips (i)–(iii)**: predicted **0 to +6**, with a non-trivial probability of negative, based on SkillsBench and Ratchet's library-drift result.
- **Honest caveat:** the evidence **cannot** distinguish "reflection recovers the RL half" from "reflection recovers only the architecture half," because **no one has run the experiment** — the closest attempts are in different domains (Ratchet/SWE-Exp use different models and splits; CoEvoSkills uses per-task bundles, not a shared bank; gskill is a blog with a per-repository artifact). Anyone who reports a confident single number here is extrapolating.

---

## 10. What I could not verify (stated plainly)

1. **Figure 1/2/3 plot values.** The three PNGs are not text and the sandbox refused writes outside the session workspace (`/home/gjanampa/.cache` → `Read-only file system`), and `/tmp` is per-command ephemeral in this harness, so I could not persist and view them. All Figure 3 numbers above are the paper's prose (0.004 → 0.158; quality reward stabilising after ~100 steps). The underlying data table for Figure 3 is not published.
2. **Retrieval k.** Never stated in v2 main text or Appendix C. A reimplementation must choose this.
3. **Whether Table 2's rows are curriculum checkpoints or test-time restrictions.** My inference (based on the identical 1252-skill counts in rows 4–5 and the phase-1/2/3 structure) is stated as inference, not fact.
4. **CODESKILL's code, data, and the footnote'd "Experimental support … build logs."** No repository link, no artifact, no appendix with raw numbers; the HTML footer carries a LaTeX "Experimental support" placeholder. Every number here is from the paper's own tables.
5. **Any v1→v2 changelog or reviewer response explaining the sign flip in the maintenance ablation.** The arXiv listing shows no comment field; the paper text is silent.
6. **Whether the Table 1/Table 2 runs are single-run.** The paper never says. I report the omission, not a run count.
7. **`add` and `drop` rubrics.** Figure 13 covers `merge` only, despite the paper stating action-specific judges for maintenance.
8. **SkillForge's and SkillClaw's training status.** Both read as reflective (no fine-tuning or RL described in what I retrieved), but neither states "training-free" as explicitly as AutoSkill/SkillBrew/Skill-Pro do. Tagged accordingly in §9.
9. **"Automatically Learning Skills for Coding Agents" (ACM CAIS 2026, DOI 10.1145/3786335.3813196).** `dl.acm.org` returned **HTTP 403 (Cloudflare)**, so I could only read the **GEPA-project version** of the same work (the gskill blog), which is an author artifact rather than the refereed paper. The demo page exists at [caisconf.org](https://www.caisconf.org/program/2026/demos/learning-skills-coding-agents/); I did not read it.
10. **Skill-Pro's numbers** come from a **third-party paper-notes repository** ([zhaoyang97/Paper-Notes-en](https://github.com/zhaoyang97/Paper-Notes-en/blob/main/docs/ICML2026/llm_agent/skill-pro_learning_reusable_skills_from_experience_via_non-parametric_ppo_for_ll.md)) rather than the primary PDF — **SECONDARY**. I verified only that arXiv:2602.01869 exists, is ICML 2026, and is titled as stated via that note; the ablation numbers in §9's Skill-Pro row are **not** independently confirmed.
11. **Ratchet's SWE-V/150 figure is explicitly self-labelled preliminary** ("We label this preliminary and report the peak only, since under twenty rounds, at roughly 50 minutes each, leaves no stable late window") and is 3 seeds on a 150-instance slice. Do not treat +0.22 as a stable estimate.
12. **No paper found** that ablates a reflective curator against an RL curator on the same multi-granularity skill bank for repo-level codegen. The predecessor report reached the same conclusion for the skill-document family; this dive extends that to the skill-*bank* family and adds gskill, CoEvoSkills, Ratchet, SWE-Exp, SkillBrew, Skill-Pro, SLIM, SkillForge, SkillNet and SkillClaw to the search space.

---

## 11. One-paragraph handoff

CODESKILL's +11.03 is **roughly half architecture and half policy**. A zero-training, fixed-prompt curator on the identical pipeline and action space gets **+5.93 (54%)** with a strong LLM and **+0.40** with a 4B one; an SFT-only (non-RL) curator gets **+5.22 (47%)**. So the learned-policy increment is **≈+5.1 to +5.8** — and the paper **never ablates it**: there is no reward-component ablation, no λ sweep, no curriculum ablation, no seeds, and the one maintenance ablation it does publish **changed sign between v1 (−1.49) and v2 (+0.82)** on numbers that moved without explanation. The good news for a reflective reimplementation is that CODESKILL's rubric (Figures 10–14), its complete 7-operation schema, its retrieval recipe, and its `R_A`/`R_E` attribution design are **all published, all in text space, and none of them requires gradients** — the RL is only the update rule. The bad news is the two coding-harness datapoints that bracket the plan: **CoEvoSkills +40.5 pp** when the loop has a co-evolving diagnostic verifier, and **SkillsBench −8.1 to −11.5 pp** when it does not — with CoEvoSkills' own ablation putting a binary-verifier-only loop at **+10.5 pp, i.e. the same as not evolving at all**. Prediction: **+6 to +9 of the 11.03 (point estimate ~+7.5), conditional on building per-skill contribution estimation, eviction with an evidence floor, and diagnostic-rich feedback** — and that conditionality is the actual engineering work, not the reflection prompt.
