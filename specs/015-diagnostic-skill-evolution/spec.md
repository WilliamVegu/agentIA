# Feature Specification: Diagnostic-Driven Skill Evolution

**Feature Branch**: `015-diagnostic-skill-evolution`

**Created**: 2026-09-29

**Status**: Draft

**Input**: User description: "record the traces of sessions to get more insights into the candidate optimizer — is the optimization loop already implemented?"

## Context

Feature 014 delivered a working optimization loop: it collects recorded session
outcomes, reflects them into bounded edits, applies them to a copy, gates the
candidate against the current skill on fresh executions, and accepts only on a
strict improvement.

Two facts about that loop motivate this feature.

**It has never run.** Its run record is empty, and no session has ever produced
measured evidence. The loop is machinery that has not been fed.

**It is fed the wrong signal.** The reflector receives terminal status, a derived
build exit code, artifact paths, and a verification-fallback marker. It does not
receive the structured, rule-level findings the platform already computes when it
evaluates a generated artifact set. So the loop's only lever is a whole-document
edit judged by a whole-corpus pass rate — a binary comparison on a handful of
tasks, which cannot separate a real improvement from run-to-run variance, and
which cannot say *which* rule was responsible for anything.

This feature supplies the missing evidence layer and retargets the loop onto it.
The instrument comes first, deliberately: independent work on reflective skill
evolution reports that a loop fed only an opaque pass/fail verdict performs no
better than no loop at all, while the same loop with a channel that carries the
*structure* of a failure improves substantially.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A failed session explains itself (Priority: P1)

An operator runs a generation session that ends in a human-intervention state.
Today they can see that it failed, and read an error, but they cannot see which
rules the generated artifacts violated, on which files, or how severely — that
detail is computed during the run and then lost. They must re-run the session to
see it again, and re-running is not guaranteed to reproduce it.

After this feature, every completed session carries a durable, structured record
of what was found wrong with its artifacts. The operator opens the session and
reads the findings: which rule, which artifact, which severity. No re-run.

**Why this priority**: This is the evidence everything else depends on. Without
it, no measurement is possible, no failure is attributable, and the optimizer has
nothing to consume. It is also independently valuable on its own — diagnosing a
failure is the operator's first need, and it is the prerequisite for the rest.

**Independent Test**: Run a session whose artifacts contain a known, deliberate
defect. Read the session record and confirm the specific rule that fired is named,
along with the artifact it fired on and its severity. Then confirm the same
record is produced for identical artifacts on a repeat run.

**Acceptance Scenarios**:

1. **Given** a completed session whose artifacts violated a known rule, **When**
   the operator inspects the session record, **Then** the record names the rule,
   the artifact path, and the severity, and the operator can identify the defect
   without re-running the session.
2. **Given** two evaluation runs over byte-identical artifacts, **When** both
   records are compared, **Then** they are identical, so a later improvement
   cannot be confused with the instrument drifting.
3. **Given** a session whose verification could not be performed, **When** the
   operator inspects the record, **Then** the record states this explicitly and
   the session is excluded from any optimization evidence, rather than being
   treated as a clean or a failed run.
4. **Given** a session that produced no artifacts at all, **When** the record is
   inspected, **Then** it distinguishes "nothing to evaluate" from "evaluated and
   clean".

---

### User Story 2 - Each skill's contribution is measured (Priority: P2)

An operator wants to know whether a particular skill in the active set actually
earns its place. Today this is unanswerable: skills are applied to every request
and nothing isolates the effect of any one of them.

After this feature, the operator can measure the contribution of an individual
skill by comparing outcomes with and without it, and receives that measurement
together with the number of observations behind it and the smallest effect it
could have detected. When the evidence is too thin to support a conclusion, the
result says so instead of reporting a number.

**Why this priority**: This is what converts "the generated code got better" into
"this rule was responsible". It is the difference between a plausible edit and
attributable evidence, and it is the input any pruning decision requires.

**Independent Test**: Measure the contribution of a skill that is known to be
load-bearing and of one that is inert with respect to the task set. The
measurement must separate them, and must report insufficient evidence when given
too few observations to do so.

**Acceptance Scenarios**:

1. **Given** a skill known to change outcomes and a skill known not to, **When**
   both contributions are measured against the same task set, **Then** the
   measurement separates them.
2. **Given** a task set too small to detect the effect being looked for, **When**
   a contribution is measured, **Then** the result reports that the evidence is
   insufficient and does not present the difference as an improvement.
3. **Given** a measurement, **When** it is reported, **Then** it states the number
   of observations and the smallest effect it could have detected at that size.

---

### User Story 3 - The loop evolves and prunes against that evidence (Priority: P3)

An operator runs an optimization round. Today the round can only add or rewrite
content in a single document, it decides by comparing whole-corpus pass rates that
cannot separate signal from noise at the available scale, and it can never remove
anything — a change that made things worse is logged and then forgotten, and may
be proposed again indefinitely.

After this feature, a round is driven by the recorded evidence, attributes its
effect per skill, and is able to **remove** a skill that does not earn its place.
A round that cannot demonstrate an improvement says so rather than reporting one.

**Why this priority**: This is the payoff, and it depends entirely on P1 and P2.
It is last because building it before the evidence layer would produce exactly the
unenforceable loop this feature exists to replace.

**Independent Test**: Run a round in which one skill measurably degrades outcomes.
Confirm the round removes it and records why. Then confirm a round with no
demonstrable improvement reports no improvement.

**Acceptance Scenarios**:

1. **Given** a skill whose measured contribution is below the stated evidence
   floor, **When** a round runs, **Then** the skill is removed and the reason is
   recorded.
2. **Given** a round whose candidate does not measurably improve on the current
   skill, **When** it completes, **Then** the round reports no improvement and the
   active skill set is unchanged.
3. **Given** any round outcome, successful or not, **When** it completes, **Then**
   exactly one record exists describing what was attempted and what was decided.
4. **Given** a round in which every skill is removed, **When** it completes,
   **Then** the result is a valid empty configuration that a subsequent session
   can run under.

### Edge Cases

- **The instrument is the thing under test.** If a round could alter the rules by
  which findings are counted, it could manufacture an improvement by degrading the
  judge. The diagnostic channel must be outside the optimizer's reach.
- **Unverified sessions as evidence.** A session whose build fell back to a
  synthetic result must not contribute to any measurement. Counting it would
  reward changes that make verification less likely to run.
- **Ties and near-ties.** A skill whose measured contribution is indistinguishable
  from zero is *not* evidence of harm. Removal must require evidence of a
  vanishing contribution, not merely the absence of a proven benefit.
- **Empty skill set.** No skill active is a legitimate state, not an error, and
  must remain available as an outcome.
- **Repeat observations are not independent observations.** Measuring the same
  task repeatedly does not increase the number of distinct tasks; the reported
  evidence size must reflect distinct tasks, or a round could manufacture
  significance by repeating itself.
- **A round that changes nothing.** A proposal set that is entirely rejected must
  leave the active skill set byte-identical.
- **Concurrent sessions.** A session completing while a round is running must not
  contribute partial evidence to that round.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every session that reaches a terminal state MUST persist a durable
  structured record of the findings produced while evaluating its artifacts.
- **FR-002**: Each recorded finding MUST identify the rule that fired, the
  artifact it fired on, and its severity.
- **FR-003**: The record MUST be deterministic: identical inputs MUST produce an
  identical record, with no dependence on time, ordering, or randomness.
- **FR-004**: The record MUST distinguish three states — evaluated and clean,
  evaluated with findings, and not evaluable — and MUST NOT conflate the third
  with either of the first two.
- **FR-005**: A session whose verification could not be performed MUST be excluded
  from optimization evidence, and this exclusion MUST be visible in the record.
- **FR-006**: The system MUST be able to measure the contribution of an individual
  skill to outcomes on a held-out task set, by comparing results with and without
  that skill.
- **FR-007**: A contribution measurement MUST report the number of distinct tasks
  supporting it, and the smallest effect detectable at that size.
- **FR-008**: A contribution measurement MUST report when the available evidence
  cannot support a conclusion, rather than reporting a point estimate as a result.
- **FR-009**: Repeated observations of the same task MUST NOT be counted as
  independent evidence when reporting a measurement's size.
- **FR-010**: An optimization round MUST decide using recorded evidence and MUST
  NOT rely solely on a whole-corpus pass-rate comparison.
- **FR-011**: An optimization round MUST be able to remove a skill.
- **FR-012**: Removal MUST require the skill's measured contribution to fall below
  a stated, documented floor, and MUST NOT occur merely because a benefit was not
  demonstrated.
- **FR-013**: Every optimization round MUST persist exactly one record, on every
  exit path including failure, describing what was proposed and what was decided.
- **FR-014**: The rules by which findings are counted MUST NOT be modifiable by an
  optimization round.
- **FR-015**: An empty active skill set MUST be a valid configuration.
- **FR-016**: The system MUST NOT report an improvement that the available
  evidence cannot support.
- **FR-017**: The number of skills considered in a single round MUST be bounded by
  a documented limit.
- **FR-018**: Each recorded finding MUST be attributed to the generation stage that
  introduced it, so the origin of a violation is identifiable without re-running
  the session.
- **FR-019**: The conformance measure MUST be comparable across artifact sets of
  different sizes, so that a larger service is not penalised for its size and no
  round can improve the measure merely by generating less.

### Key Entities *(include if feature involves data)*

- **Session diagnostic record**: the durable account of what was found wrong with
  one session's artifacts. Holds the findings, the counts by rule and severity, an
  overall conformance value, the number of artifacts evaluated, and whether the
  session was evaluable at all. Associated with exactly one session.
- **Finding**: one identified defect. Holds the rule identity, the artifact it
  occurred in, the severity, and a human-readable description.
- **Skill contribution measurement**: the result of comparing outcomes with and
  without one skill. Holds the skill identity, the observed difference, the number
  of distinct tasks supporting it, the minimum detectable effect at that size, and
  whether the evidence is sufficient to conclude anything.
- **Optimization round record**: one attempt to change the active skill set. Holds
  what was proposed, what was measured, what was decided, and why — including the
  removal decisions and the evidence that justified them.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of sessions reaching a terminal state carry an inspectable
  diagnostic record.
- **SC-002**: For any recorded session, an operator can identify every rule that
  fired and the artifact it fired on, without re-running the session.
- **SC-003**: Re-evaluating identical artifacts yields a byte-identical record in
  100% of trials.
- **SC-004**: Given one skill that changes outcomes and one that does not, the
  contribution measurement separates them on a task set large enough to detect the
  difference, and reports insufficiency on one that is not.
- **SC-005**: Every reported contribution states the number of distinct tasks and
  the minimum detectable effect at that size.
- **SC-006**: Zero sessions with unverified builds contribute to any measurement.
- **SC-007**: A skill whose measured contribution falls below the stated floor is
  removed within one optimization round, and the removal cites the measurement.
- **SC-008**: A round that cannot demonstrate an improvement reports none, and
  leaves the active skill set unchanged.
- **SC-009**: Exactly one record exists per optimization round, on every exit path.
- **SC-010**: No optimization round can alter the rules by which findings are
  counted, verified by attempting it and confirming the attempt has no effect.
- **SC-011**: For any recorded session, the stage that introduced each finding is
  identifiable from the record alone.
- **SC-012**: Two artifact sets differing only in size, carrying findings in the
  same proportion, yield the same conformance measure.

## Assumptions

- **The optimization target is conformance, not build success.** Build success is
  a binary whole-corpus outcome, and the available task set is far too small to
  separate a real change in it from run-to-run variance — a limitation already
  documented in feature 014's own planning. Conformance is continuous, is measured
  deterministically at no cost, and is the outcome that independent work reports
  skill documents can actually move. Build success is retained as a guardrail
  rather than as the objective. **This choice defines the feature's scope and
  should be confirmed before planning.**
- **The existing held-out task corpus is reused.** No new fixtures are authored;
  the corpus is the one already frozen. Growing it is a separate concern, and this
  feature is designed to report honestly at whatever size exists rather than to
  assume a size it does not have.
- **Verification remains free and offline.** Measurements involve repeated
  comparison, which is affordable because evaluation costs no model calls;
  generation does, and the feature must not assume unlimited generation.
- **The optimizer's proposals stay bounded.** The existing limit on how much may
  change in one round is retained.
- **Skills are evaluated against a task set that is disjoint from the evidence
  used to propose changes.** The separation already established in feature 014 is
  preserved.
- **The existing conformance gates and their rule vocabulary are authoritative.**
  This feature records and measures against them; it does not redefine what
  compliance means.
- **This feature does not train any model.** It consumes the existing
  deterministic evaluation and a proposal mechanism; no weights change, and no
  training infrastructure is required or assumed.
- **The conformance measure is an artifact-level instrument, and that is what
  makes it reusable beyond this platform.** It reads a set of files and returns
  findings, so it can score output from this generator or from any other agent,
  and the same instrument can serve both. Three limits are accepted with it. It
  is a **fixed, hand-written rule set**, so its coverage is bounded by the rules
  authored: a defect class nobody encoded scores clean. It measures
  **conformance, not correctness** — a well-layered service that does not work
  scores full marks, which is why build success remains a guardrail. And its use
  as an optimisation objective is, as far as the reviewed literature shows,
  **without precedent**: comparable work gates on test execution or on a language
  model's judgement, not on a static rule scan. Its behaviour as an objective is
  therefore to be measured, not assumed.
