# Feature Specification: Session Diagnostics and Corpus Baseline

**Feature Branch**: `015-diagnostic-skill-evolution`

**Created**: 2026-09-29

**Status**: Draft (rescoped — the optimizer half is deferred, see below)

**Input**: User description: "record the traces of sessions to get more insights into the candidate optimizer"

## Why this feature was rescoped

The original feature bundled two things: an **instrument** and an **optimizer**.
Review split them, for three reasons that are about evidence rather than taste.

**The optimizer has nothing to optimize against yet.** No session has ever
produced a measured outcome: the platform's verification metrics, cost
aggregates, and optimization records are all empty. A baseline does not exist, so
no improvement can be stated, and the failure modes an optimizer would target have
never been observed.

**The conformance signal is narrower than the original spec assumed.** The
platform's compliance gate *blocks* stage-local violations, so those never reach a
persisted artifact set. Only whole-project findings survive into saved output. In
the current fixture set that is a single rule, which makes the graded objective
closer to near-binary than the original six requirements implied. Whether real
sessions vary at all on it is **unknown and must be measured before anything is
built to exploit it.**

**The optimizer targets a low-return lever.** The available evidence ranks
reliability levers as: model capability, then harness and interface design, then
verification-guided selection among samples, then post-training, then learned
skill banks, then optimized text skills. The original feature sat at the bottom of
that list while a better-evidenced and cheaper option — selecting among samples
with the platform's own free verifier — remains untouched. That comparison should
be made **with data in hand**, not in advance.

So this feature now delivers the instrument and the baseline. The optimizer is
specified at the end as an explicitly deferred proposal.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A failed session explains itself (Priority: P1)

An operator runs a generation session that ends in a human-intervention state.
Today they can see that it failed and read an error, but not which rules the
generated artifacts violated, on which files, in which stage, or how severely —
that detail is computed during the run and then lost. To see it again they must
re-run, and a re-run is not guaranteed to reproduce it.

After this feature, every session that reaches a terminal state carries a durable,
structured record of what was found wrong with its artifacts. The operator opens
the session and reads the findings: rule, artifact, stage, severity. No re-run.

**Why this priority**: it is the evidence everything downstream depends on, and it
is independently valuable on its own — diagnosing a failure is the operator's
first need, and it is what makes the corpus measurable at all.

**Independent Test**: run a session whose artifacts contain a known defect, read
the record, confirm the rule, artifact, stage and severity are named; run it again
and confirm the record is identical.

**Acceptance Scenarios**:

1. **Given** a completed session whose artifacts violated a known rule, **When**
   the operator inspects the record, **Then** the rule, the artifact path, the
   stage that introduced it, and the severity are all named, and the defect is
   identifiable without re-running.
2. **Given** two evaluations of byte-identical artifacts, **When** the records are
   compared, **Then** they are identical.
3. **Given** a session whose verification could not be performed, **When** the
   record is inspected, **Then** it says so explicitly and the session is marked
   as excluded from evidence, rather than being reported as clean or as failed.
4. **Given** a session that produced no artifacts, **When** the record is
   inspected, **Then** it is recorded as *not evaluable*, which is distinguishable
   from *evaluated and clean*.

---

### User Story 2 - The corpus can be measured (Priority: P2)

An operator wants to know how the generator actually performs: how often it
succeeds, how often it blocks, how many correction attempts it spends, what
conformance its output achieves, and what it costs. Today none of this is
answerable — no session has ever been recorded in a form that supports it.

After this feature, the operator can run a batch of sessions against the held-out
task set and receive a single report describing the population: how many ran, how
many were verified, how many were excluded and why, the conformance distribution,
the block rate, the correction effort, and the cost — with cost reported only when
data exists to support it.

**Why this priority**: this produces the number the platform currently cannot
state, and it is the input to every decision that follows — including whether to
build the deferred optimizer at all.

**Independent Test**: run a batch over the held-out task set and confirm the
report states the population, the exclusions with reasons, the conformance
distribution and the correction effort; then confirm that with an empty store it
reports *no data* rather than zero.

**Acceptance Scenarios**:

1. **Given** a batch of sessions run over the held-out task set, **When** the
   report is produced, **Then** it states how many sessions ran, how many were
   verified, and how many were excluded and for what reason.
2. **Given** sessions whose builds fell back to synthetic results, **When** the
   report is produced, **Then** those sessions are excluded from every rate and
   their exclusion is stated, so no figure silently includes them.
3. **Given** an empty or insufficient store, **When** the report is produced,
   **Then** it reports that no data exists and does **not** report zero, because
   "no data" and "measured zero" are different findings.
4. **Given** recorded sessions, **When** the report is produced, **Then** it
   states the conformance distribution and the correction effort as well as the
   success rate.

### Edge Cases

- **Unverified sessions.** A session whose build fell back to a synthetic result
  must be excluded from every rate and named as excluded. Counting it would
  report a success the platform did not achieve — the failure feature 012 exists
  to prevent.
- **"No data" is not zero.** An empty store must produce "no data", never a rate
  of zero and never a cost of zero.
- **Repeats are not independent observations.** Running the same task repeatedly
  raises the session count but not the number of distinct tasks. Reports must not
  present repeated runs as a larger sample than they are.
- **A session with no artifacts.** Distinguishable from a clean session, and
  excluded from conformance figures rather than scored as perfect.
- **Partial batches.** A batch interrupted partway must leave the sessions that
  did complete fully recorded, and must not report the batch as complete.
- **Concurrency.** A session completing while a batch runs must not corrupt a
  record already written.
- **Findings must not vanish on failure.** A session that fails *after* producing
  artifacts still records what was found; a diagnostic is not discarded because
  the run ended badly.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every session reaching a terminal state MUST persist a durable
  structured record of the findings produced while evaluating its artifacts.
- **FR-002**: Each recorded finding MUST identify the rule that fired, the
  artifact it fired on, and its severity.
- **FR-003**: The record MUST be deterministic: identical inputs MUST produce an
  identical record, with no dependence on time, ordering or randomness.
- **FR-004**: The record MUST distinguish three states — *evaluated and clean*,
  *evaluated with findings*, and *not evaluable* — and MUST NOT conflate the
  third with either of the first two.
- **FR-005**: A session whose verification could not be performed MUST be marked
  as excluded from evidence, and this MUST be visible in the record.
- **FR-006**: Each recorded finding MUST be attributed to the generation stage
  that introduced it.
- **FR-007**: The conformance measure MUST be comparable across artifact sets of
  different sizes, so that a larger service is not reported as worse for its size.
- **FR-008**: The system MUST be able to run a batch of sessions over the held-out
  task set and record every outcome.
- **FR-009**: The system MUST produce a report over the recorded corpus stating
  the number of sessions, the number verified, and the number excluded with
  reasons.
- **FR-010**: The report MUST state the conformance distribution and the
  correction effort alongside the success rate.
- **FR-011**: The report MUST NOT report a rate or a cost derived from no data;
  absence of data MUST be reported as absence, not as zero.
- **FR-012**: Excluded sessions MUST NOT contribute to any reported rate or
  distribution.
- **FR-013**: The report MUST distinguish the number of sessions from the number
  of distinct tasks, and MUST NOT present repeated runs of one task as a larger
  sample.
- **FR-014**: A session that fails after producing artifacts MUST still record the
  findings produced before the failure.
- **FR-015**: The count of distinct tasks available MUST be reported alongside any
  figure derived from it, so a reader can judge whether the evidence supports the
  claim being made.

### Key Entities *(include if feature involves data)*

- **Session diagnostic record**: the durable account of what was found wrong with
  one session's artifacts. Holds the findings, counts by rule and severity, the
  conformance measure, the artifact count, whether the session was evaluable, and
  whether it was verified. Exactly one per session.
- **Finding**: one identified defect — the rule, the artifact, the stage that
  introduced it, the severity, and a description.
- **Stage attribution**: the per-stage portion of a record, identifying which
  stage introduced which findings.
- **Corpus report**: the summary over recorded sessions — population, exclusions
  with reasons, conformance distribution, correction effort, and cost where data
  exists.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of sessions reaching a terminal state carry an inspectable
  diagnostic record.
- **SC-002**: For any recorded session, an operator can identify every rule that
  fired, the artifact it fired on, and the stage that introduced it, without
  re-running the session.
- **SC-003**: Re-evaluating identical artifacts yields a byte-identical record in
  100% of trials.
- **SC-004**: Zero sessions with unverified builds contribute to any reported rate
  or distribution, and their exclusion is stated in the report.
- **SC-005**: With an empty store, the report states that no data exists and
  reports neither a zero rate nor a zero cost.
- **SC-006**: A batch over the held-out task set completes and every session's
  outcome is recorded, including sessions that fail.
- **SC-007**: The report states the session count, the verified count, the
  excluded count with reasons, the conformance distribution, and the correction
  effort.
- **SC-008**: The report states the number of distinct tasks separately from the
  number of sessions.
- **SC-009**: Two artifact sets differing only in size, carrying findings in the
  same proportion, yield the same conformance measure.

## Assumptions

- **The existing held-out corpus is reused.** No new fixtures are authored. If the
  corpus proves too small to state anything, the report must say so — that is a
  finding, not a defect — and growing it is a separate feature.
- **Verification remains free and offline**, so a batch costs generation only.
- **The existing conformance gates and their rule vocabulary are authoritative.**
  This feature records against them; it does not redefine compliance.
- **The conformance measure is an artifact-level instrument.** It reads files and
  returns findings, so it can score output from any agent — a property of reading
  files, not a virtue. Three limits are accepted with it: it is a **fixed,
  hand-written rule set**, so a defect class nobody encoded reads clean; it
  measures **conformance, not correctness**, so a well-layered but broken service
  scores full marks; and because stage-local violations are **blocked before
  persistence**, the findings that survive into a saved artifact set come from
  whole-project rules only, which is a **narrow** signal whose real-world variance
  is unmeasured.
- **This feature does not train any model** and does not modify the generator's
  behaviour. It records what happens. With no active skill and no batch run,
  generation is byte-identical to before it.

## Deferred: the optimizer (originally part of this feature)

The following were specified, planned and are now **deliberately deferred** until
the corpus report exists. They are recorded here so the reasoning is not lost and
so the decision to build them can be made against data.

**Deferred requirements**: per-skill contribution measurement by leave-one-out;
retargeting an optimization round onto recorded evidence rather than a whole-corpus
pass rate; removal of a skill that falls below an evidence floor; requiring exactly
one record per optimization round; keeping the counting rules out of a round's
reach; and bounding the number of skills per round.

**Why deferred**: the measurement cannot conclude anything at the current task
count, the signal it would measure is narrower than assumed, and a cheaper
better-evidenced option exists.

**What must be true before building it**: the corpus report must show that the
conformance measure **varies** across real sessions. If every recorded session
scores identically, there is nothing for an optimizer to move, and the effort
belongs on a different lever instead.

**The artifacts for the deferred half remain in this directory** — `research.md`,
`data-model.md` and `contracts/` still describe it, and remain valid. They are
simply not being built yet.
