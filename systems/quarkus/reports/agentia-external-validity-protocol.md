# External validity protocol for AgentIA

**Date:** 2026-09-29
**Status:** Protocol proposal. Defines what a claim about this platform would have to
report to be checkable from outside it.
**Companion:** [agentia-sota-pathways.md](agentia-sota-pathways.md) §3.8.

---

## 1. The problem this solves

AgentIA currently has **no external validity check**. Every number it reports --
conformance score, correction effort, cost -- is measured by instruments it also
built, on tasks it authored, and compared against nothing.

That is not a criticism of the instruments; the deterministic gate and the hermetic
build are the platform's best assets. It is a statement about what a number can
support. And it is not a niche problem: no existing benchmark ingests this artifact
class.

| Benchmark | Unit | Why it does not fit |
|---|---|---|
| [Commit0](https://arxiv.org/abs/2412.01769) | library from scratch, **tests supplied** | Python libraries; no architecture contract; no prescribed layering |
| [RepoZero](https://arxiv.org/abs/2605.07122) | repo reproduced in another language | reproduction, not novel-spec synthesis; the source repo is the oracle |
| [NL2Repo-Bench](https://arxiv.org/abs/2512.12730) | NL requirements -> installable library | Python only; prose requirements rather than a formal blueprint |
| [ScarfBench](https://arxiv.org/abs/2605.06754) | compile + container deploy + behavioural tests | **closest fit** (34 Java apps, 204 tasks) but it is migration, not greenfield |
| Multi-SWE-bench / SWE-bench-java | issue resolution | a different task class entirely |

The nearest neighbours put the frontier at **under 55%, mostly under 40%**, and
nothing there is saturated -- which is the opportunity. Defining the benchmark for
this white space is a stronger position than reporting another internal score.

---

## 2. Two routes, in order of effort

### Route A (cheap, weeks): report on a recognised protocol

Take an existing protocol's *shape* and report AgentIA's numbers on it, stating
plainly which parts are borrowed and which are not comparable.

**Recommended shape: ScarfBench's.** It is Java, it compiles in a container, it
deploys, and it scores **behavioural tests over the observable interface** rather
than implementation details -- which is the right oracle for a generator that is
allowed to choose its own internals. Borrow:

* the **container-deploy** requirement (the service must actually start, not merely
  compile), and
* the **behavioural-over-interface** oracle (HTTP requests and responses), never a
  structural diff against a reference implementation.

Do **not** claim comparability with ScarfBench's numbers: its tasks are framework
migrations of existing applications, and AgentIA's are greenfield services from a
blueprint. State the difference in the same table as the number.

### Route B (the leadership position): publish the benchmark

Define and release the benchmark this class does not have. Concretely:

**B1. Task format.** A frozen blueprint: domain entities with attributes and
validation rules, BDD Given/When/Then acceptance scenarios, and a prescribed
architecture contract. That is AgentIA's input today, and it is the artifact no
public benchmark accepts.

**B2. The oracle — and this is the part that must be got right.** Acceptance tests
are derived from the **frozen BDD scenarios**, by an instrument the generator cannot
author or edit. The two existing approaches both work and both are instructive:

* Commit0 **supplies** its unit tests up front.
* ProgramBench **generates** them by *agent-driven fuzzing* against a reference
  executable, "enabling evaluation without prescribing implementation structure".

A suite the candidate writes is not an oracle; this repository has already proved
that locally -- the generated tests mock the repository, and the one real defect
found lived in exactly that mocked-away seam, invisible to all six of them.

**B3. Scoring.** Report all four, every time:

| Figure | Why it is required |
|---|---|
| **pass@1** | the honest single-attempt rate |
| **pass@k** | the optimistic bound (best-of-k) |
| **pasŝk** | the pessimistic bound; pass@5 − pass@1 reaches **24.9pp** on SWE-bench Verified, so reporting only the optimistic bound overstates by ~19pp in one measured case |
| **cost per solved task** | the platform's actual claim; it is 2–3 orders of magnitude below published research-agent runs |

**B4. Repetitions and power.** At least **5 independent runs per task**, because
single-run pass@1 varies **2.2–6.0pp** and temperature 0 is *not* deterministic
(sd > 1.5pp at T=0 in a 60,000-trajectory study). Six tasks is the arithmetic
minimum at which a paired two-sided test can reach p<0.05 at all (0.03125, and then
only unanimously); a benchmark of this class should ship **tens** of tasks so that
modest effects are detectable at all.

**B5. Contamination controls.** No `.git` in the workspace; no network egress beyond
a package-registry allowlist; tasks authored once and frozen; and per-task reporting
so a memorised task cannot lift the aggregate. Leaked `.git` gave public SWE-bench
Pro images **100% exploit success**, and sealing history and network moved one model
from **87.1% to 73.0%**.

**B6. Report the hacking rate as a first-class result.** Attempts to edit or delete
tests, read history, or fetch an answer are scored as **failures** and reported
alongside the pass rate. METR measured hacking in **1–2% of all task attempts** --
enough, uncorrected, to push a model past human-expert level on RE-Bench.

---

## 3. Why this is worth doing rather than more internal measurement

1. **It makes every existing claim checkable.** A conformance score means nothing to
   anyone outside this repository; a pass rate on a published protocol with a
   specified oracle and stated repetitions is a claim someone else can falsify.
2. **It converts the differentiator into evidence.** The defensible asset is the trio
   -- a machine-checkable spec format, a hermetic deterministic oracle, and a bounded
   repair loop that fails closed. None of that is visible in an internal score.
3. **It addresses the strongest published result in this platform's favour.** The
   *Architecture as Capability Equalizer* finding -- structured specs are worth most
   to cheaper models, tripling API-route coverage for the weakest one -- is a claim
   about a *commodity-model* design. Testing it on a public benchmark is how it
   becomes a result rather than an intuition.

## 4. What must not be claimed

* **Do not present conformance as correctness.** The closest measured analogue to a
  static rule-density instrument is near-orthogonal to defects (23 Apache Java
  projects, 1,723 validated bug-inducing changes, negligible effect sizes).
* **Do not compare a greenfield pass rate to an issue-resolution pass rate.** Class A
  sits at 73–91%; class B at 12–55%. They are not the same task.
* **Do not quote a single run.** Report pass@1 with its CI, pass@k, pasŝk, n_runs,
  cost, and hacking rate -- or report "no difference detected at this resolution",
  which is what most 2–3pp claims in the literature actually support.
