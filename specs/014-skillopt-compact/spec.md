# Feature Specification: SkillOpt Compact

**Feature Branch**: `feature/011-llm-generation-nodes` (see Branch Note)

**Created**: 2026-09-28

**Status**: Draft

**Input**: User description: "Implement the minimal SkillOpt loop over a single skill document. One iteration, one skill, no momentum, no buffer, no multi-skill coordination. Everything skipped is deferred to a v2 spec."

## Context

Agent skills in this platform are hand-authored markdown. Nothing improves them from observed outcomes: if a rule is missing, nobody finds out until someone reads a failed session and edits the file by hand. Meanwhile the platform now produces exactly the evidence needed to improve them — honest verification outcomes (012) and per-session records with real build results — so the input to skill improvement already exists and is simply unused.

This feature builds the **smallest closed loop** that turns that evidence into a better skill: collect outcomes, ask a model what the skill got wrong, apply bounded edits, and accept the result only if it measurably helps on data it was not trained on.

The full method this is drawn from — [SkillOpt](https://arxiv.org/abs/2605.23904) (arXiv:2605.23904) — includes a rejected-edit buffer, a textual learning-rate schedule, an epoch-wise slow/meta update, and multi-skill banks. **All of that is deliberately omitted here.** The paper's own abstract names those mechanisms as what makes training *stable*; this feature establishes the *loop* first, and stability machinery is deferred to v2. One iteration, one skill, no memory between runs.

Two facts about the current system shape this feature:

1. **The skill directory exists and is empty.** Three skill files were created as zero-byte placeholders by an earlier feature that classified the domains but never authored content. The seed skill is therefore authoring a file that already exists, not creating a new one.
2. **Nothing reads that directory today.** The instruction loader explicitly documents the skill directory as "deliberately distinct" from its own. So injection is a new consumer, not an extension of an existing one.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The skill is injected into generation (Priority: P1)

An operator places a skill document in the active slot. From then on, every model request made during generation carries that skill's content alongside the stage's own instructions. Removing the active slot returns generation to exactly its previous behaviour.

**Why this priority**: Without injection, editing a skill changes nothing, and the rest of the loop optimises a document that has no effect. It is also independently valuable and cheap: it is the one part of this feature that pays off on the very next session.

**Independent Test**: With an active skill present, make a model request and assert the skill's text appears in it. Remove the active slot, make the same request, and assert the request is byte-identical to what it was before this feature existed.

**Acceptance Scenarios**:

1. **Given** an active skill document, **When** a generation stage builds its model request, **Then** the skill's content is present in the request alongside the stage's own instructions.
2. **Given** no active skill, **When** a stage builds its request, **Then** the request is unchanged from the pre-feature behaviour — the absence is a no-op, not an error.
3. **Given** an active skill whose file is unreadable or empty, **When** a stage builds its request, **Then** generation proceeds without the skill rather than failing.

---

### User Story 2 - A failed outcome becomes a proposed skill edit (Priority: P1)

An operator collects the recent session outcomes, hands the failures and the current skill to a model, and gets back a small bounded set of concrete edits — add a rule, insert one after another, replace a rule, delete one — that the model believes would have prevented those failures.

**Why this priority**: This is the "learning" half: it turns evidence into a candidate. It ranks equal-first with injection because neither is useful alone, but it is listed second because a candidate cannot be evaluated without a skill to evaluate.

**Independent Test**: Given a set of recorded failures and a skill document, run the reflection step and assert it returns a bounded list of well-formed edits that reference text actually present in the skill.

**Acceptance Scenarios**:

1. **Given** collected session outcomes, **When** the collector runs, **Then** it returns one record per session carrying the specification identifier, the artifact paths, the build exit code, the terminal status, and whether verification used a fallback.
2. **Given** failed outcomes and the current skill, **When** reflection runs, **Then** it returns a list of structured edits, each naming an operation and its target.
3. **Given** more proposed edits than the budget allows, **When** reflection completes, **Then** the number of edits is capped at the budget.
4. **Given** a model response that is not valid structured output, **When** reflection runs, **Then** the iteration reports the failure rather than applying a partially parsed result.

---

### User Story 3 - An edit is applied only if it measurably helps (Priority: P2)

An operator applies the proposed edits to a copy of the skill, then runs the candidate against sessions the proposal was not derived from. The candidate is accepted only if it scores **strictly better** than the current skill. A tie is rejected.

**Why this priority**: This is what separates optimisation from self-editing. A plausible-sounding edit that does not help is the normal case, so the gate is what makes the loop trustworthy — but it is ranked below the two halves it sits between, because there is nothing to gate until they exist.

**Independent Test**: Apply a known set of edits, score the candidate, and assert acceptance happens only on a strict improvement — then repeat with an equal score and assert rejection.

**Acceptance Scenarios**:

1. **Given** a candidate skill and a set of held-out sessions, **When** the gate runs, **Then** the score is the pass rate over those sessions.
2. **Given** a candidate score strictly greater than the current score, **When** the gate decides, **Then** the candidate is accepted.
3. **Given** a candidate score equal to the current score, **When** the gate decides, **Then** the candidate is rejected.
4. **Given** a candidate score lower than the current score, **When** the gate decides, **Then** the candidate is rejected.
5. **Given** an edit targeting the protected section, or targeting text that does not exist in the skill, **When** the applier runs, **Then** the edit is rejected and the skill is left unchanged.
6. **Given** any candidate, **When** it is applied, **Then** the original skill file is never modified — the candidate is a copy until it is accepted.

---

### User Story 4 - One iteration is observable and reproducible (Priority: P3)

An operator runs a single command and sees the whole iteration: what the current skill scored, what the candidate scored, whether it was accepted, and how many edits were proposed. The run is recorded so it can be inspected afterwards.

**Why this priority**: It is how the feature is operated and audited. It ranks last because it observes a loop that must exist first.

**Independent Test**: Run one iteration end to end and assert it reports all five facts and writes exactly one run record.

**Acceptance Scenarios**:

1. **Given** a complete iteration, **When** it finishes, **Then** it prints the current score, the candidate score, the decision, and the edit count.
2. **Given** any iteration, terminal or failed, **When** it ends, **Then** exactly one run record exists carrying the timings, the sample sizes, both scores, the decision, the proposed edits, and any error.

---

### Edge Cases

- **No failures to learn from.** If every collected session succeeded, there is nothing to reflect on. The iteration must report that and stop, rather than calling a model with an empty failure set and applying whatever it invents.
- **No sessions at all.** The collector returning nothing is a distinct condition from returning successes; both must be distinguishable in the output.
- **A model proposes an edit to the protected section.** The protected region exists so that slow, deliberate consolidation cannot be overwritten by a fast local edit. An edit targeting it must be rejected, and the rejection must not abort the rest of the batch.
- **A model proposes an edit whose target text is absent.** The skill may have changed, or the model may have paraphrased. The edit is rejected; the others still apply.
- **Every proposed edit is rejected.** The candidate equals the current skill. The gate must then reject on a tie — which the strict comparison gives for free — and the iteration must say so rather than reporting a spurious acceptance.
- **The gate is scored on the training sessions.** This is the failure the gate exists to prevent, and it is silent: a candidate tuned to the sessions it was derived from will look better on them. Held-out data must be genuinely disjoint.
- **The iteration fails partway.** A run record must still exist, carrying the error, so a failure is visible rather than looking like a run that never happened.
- **A candidate is accepted and then the next iteration runs.** With no rejected-edit buffer and no epoch state, the next iteration starts from the newly accepted skill and knows nothing of what was tried before. This is intended for v1 and is a known limitation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A skill store MUST hold one markdown document per skill, following a fixed structure: a title, a granularity declaration (task-level or event-driven), a "when to apply" section, numbered rules, and a protected region delimited by explicit slow-update markers. A seed skill covering controller → service → repository → model layering MUST be authored, hand-written and short (of the order of 250 tokens).
  - *Resolved during specification*: the seed file **already exists as a zero-byte placeholder** created by an earlier feature. This requirement authors its content; it does not create the file.
  - The seed content is a **placeholder for the loop's benefit**, not a claim about good layering advice. This feature is about the loop.
- **FR-002**: The stage execution boundary MUST prepend the active skill's content to each model request, alongside the stage's existing instructions. The active skill MUST be read from a designated active-skill file. When that file is absent, empty, or unreadable, the behaviour MUST be exactly as it was before this feature — a no-op, never an error.
- **FR-003**: A collector MUST read the most recent N sessions (default 12) and, per session, return the specification identifier, the artifact paths, the build exit code, the terminal status, and the verification-fallback marking.
- **FR-004**: A reflector MUST make one model call, using a prompt adapted from the failure-analysis contract in [SkillOpt](https://arxiv.org/abs/2605.23904) Appendix C.2.1 (`analyst_error.md`), taking the failed trajectories and the current skill as input. It MUST return a structured list of edits, each naming an operation (append, insert-after, replace, delete) and a target. The number of edits MUST be capped at a configurable budget, **4** by default.
  - The model client MUST be obtained by a **direct call to the model factory**, in the same request-construction path as the generation stages: no wrapper, no conditional, no shared helper.
  - **The prompt MUST be recorded as an adaptation, not a reproduction.** The paper's contract text is not reproduced here; the prompt is written for this platform's inputs (build exit codes, terminal statuses, artifact paths) and the file it lives in MUST say which contract it was adapted from.
- **FR-005**: An applier MUST apply atomic edits. It MUST reject any edit whose target lies in the protected region between the slow-update markers, and any edit whose target text is not found in the document. It MUST apply edits to a **copy**; the original skill file MUST NOT be modified by application.
- **FR-006**: A gate MUST score a candidate skill over M held-out sessions (default 4), where the score is the pass rate. It MUST accept the candidate **only** when the candidate's score is **strictly greater** than the current skill's score; equal scores MUST be rejected. [NEEDS CLARIFICATION: what is the held-out set, and how are its M sessions produced? The collector reads *existing* sessions from the database, but the gate is specified to *run* sessions. Two readings with materially different scope: (a) the held-out set is a disjoint slice of already-recorded sessions, in which case the gate re-scores existing evidence and spends nothing; or (b) the gate executes M genuinely new sessions, which is the paper's meaning of a held-out split but requires a task source, a workspace, and real generation cost per iteration. The choice determines whether an iteration costs M model sessions or none, and whether the gate is meaningful at all.]
- **FR-007**: An orchestrator MUST run a single iteration: collect training sessions under the current skill, reflect into edits, apply them to a candidate copy, gate the candidate, accept or reject, log the run, and print the current score, the candidate score, the decision, and the edit count. [NEEDS CLARIFICATION: is the *current* skill also scored during the iteration? FR-006 compares against "the current score", but nothing else in the loop produces it. Either the gate scores both skills each iteration (2×M sessions), or the current score is carried over from the previous accepted run (free, but stale or absent on the first iteration). This determines the per-iteration cost and what the very first iteration can decide.]
- **FR-008**: Every iteration MUST persist exactly one run record carrying: start and completion times, the training and held-out sample sizes, both scores, the decision, the proposed edits, and any error. A run that fails partway MUST still leave a record.

### Key Entities

- **Skill Document**: a markdown file with a fixed structure and a protected region. The unit being optimised.
- **Active Skill Pointer**: the file naming which skill is currently injected. Its absence is meaningful — it means "no skill", not "error".
- **Session Outcome**: one collected record: specification, artifact paths, build exit code, terminal status, verification-fallback marking. The evidence.
- **Trajectory Outcome Record**: the collected list for one iteration.
- **Proposed Edit**: an operation plus a target plus content. Bounded in number.
- **Candidate Skill**: a copy of the skill with edits applied. Never the original.
- **Gate Score**: the pass rate over held-out sessions. The acceptance criterion.
- **SkillOpt Run**: the persisted record of one iteration.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: One full iteration completes with a scripted model and produces a decision, exactly one run record, and a printed edit count.
- **SC-002**: A candidate whose held-out score equals the current score is rejected; a strictly better one is accepted; a worse one is rejected. Three cases, three outcomes, no exceptions.
- **SC-003**: 100% of edits targeting the protected region are rejected, and 100% of edits whose target text is absent are rejected, with the document unchanged in both cases.
- **SC-004**: After any iteration, accepted or rejected, the original skill file's content is unchanged unless the candidate was accepted — and when accepted, the change is exactly the applied edit set.
- **SC-005**: With no active skill, a generated model request is byte-identical to the request produced before this feature existed.
- **SC-006**: Every iteration, including one that fails partway, leaves exactly one run record.
- **SC-007**: A real iteration is runnable by hand against a live model, gated behind an explicit opt-in environment variable plus a provider key, and skips cleanly when either is absent.

## Assumptions

- **"One iteration" means no memory between runs.** No rejected-edit buffer, no epoch state, no momentum, no carried-over history. Each iteration reads the current skill, proposes, gates, and stops. This is the paper's stability machinery deliberately removed so the loop itself can be validated first.
- **The gate's comparison is strict because a tie is not evidence of improvement.** Accepting ties would let the skill drift on noise while every step looked successful. Strict comparison means an iteration that changes nothing is a *rejected* iteration, which is the honest reading.
- **The reflector is a separate, stronger model call than the generation model.** This matches the paper's design, where an optimizer model is distinct from the frozen target model. The platform's model factory supports this already.
- **The seed skill is a placeholder.** Its content is plausible layering advice, but nothing in this feature validates its quality. The spec is about the loop.
- **Cost and latency of a real iteration are not constrained here.** One iteration makes one reflection call plus whatever the gate requires. The per-iteration figure is a v2 concern.
- **The run record is a new table.** The platform's database currently holds only the session table, created by the ORM's metadata; a new model gets its table created without a migration tool.
- **Constitution Principle VI still holds.** The automated suite must not call a provider, so the loop is tested against a scripted model client, and the real iteration is opt-in.

## Dependencies

- Feature 011's stage execution boundary, which is where injection happens and where the request is assembled.
- The session store, which the collector reads.
- Feature 012's verification-fallback marking and Feature 013's cost-store pattern — the former is one of the collected fields, the latter is the established precedent for a side-channel store with a best-effort write path.
- The model factory, called directly by the reflector in the same style as the generation stages.
- A live provider key for the opt-in real iteration only.

## Out of Scope (deferred to v2)

Named here so the omissions are deliberate rather than forgotten. Each is a mechanism the source paper identifies as contributing to stability:

- **Epoch loop / slow-meta update.** The protected region exists and is honoured, but nothing writes to it.
- **Rejected-edit buffer.** A rejected edit is logged and then lost; the next iteration cannot learn from it.
- **Multi-skill bank.** One skill, one active pointer.
- **Hierarchical merge.** The paper merges failure- and success-driven edits separately before combining them; this feature takes the reflector's output directly.
- **Statistical validation.** The gate compares two pass rates with no significance test, so a one-session difference is treated as real. Acceptable for a loop-validation feature, not for a production optimiser.
- **Multi-domain coordination.** No cross-skill interaction.

## Branch Note

The working branch remains `feature/011-llm-generation-nodes`, which now carries 011, 012 and 013. Feature 014 would make it a **fourth** stacked feature. The isolation requirement (nothing merges until review) still holds, and 014 is self-contained — it reads sessions and writes skills, and does not change generation behaviour when no active skill is present. But four features on one branch is worth a deliberate decision rather than another default inheritance. Recorded, not assumed.
