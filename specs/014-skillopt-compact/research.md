# Phase 0 Research — SkillOpt Compact

All Technical Context unknowns were resolved by inspecting the repository and by fetching one primary source. No `NEEDS CLARIFICATION` item remains.

---

## D1 — The source is real, and the citation is precise

**Decision**: Treat [arXiv:2605.23904](https://arxiv.org/abs/2605.23904), "SkillOpt: Executive Strategy for Self-Evolving Agent Skills", as the method source, and cite **Appendix C.2.1 (`analyst_error.md`)** specifically for the reflector prompt.

**Rationale**: Fetched, not recalled. The abstract page (HTTP 200, v2, 25 May 2026) and the full HTML both confirm:

- **Appendix C.2 is "Optimizer Prompt Contracts"**, with eight entries. **C.2.1 is `analyst_error.md`** — the failure-analysis contract. The other seven (`analyst_success`, `merge_failure`, `merge_success`, `merge_final`, `ranking`, `slow_update`, `meta_skill`) map onto machinery this feature defers.
- The abstract independently confirms the two design choices already in the requirements: edits are **bounded** add/delete/replace operations on **a single skill document**, and an edit is accepted **only when it strictly improves a held-out validation score**.
- It also confirms that the deferred items are exactly the mechanisms the paper names as what makes skill training *stable* — so the v1/v2 boundary is the paper's own stability boundary, not an arbitrary cut.

**Constraint carried into the plan**: the paper's prompt text is **not reproduced**. FR-004 requires a prompt written for this platform's inputs and a file that records which contract it was adapted from.

**Alternatives considered**: writing a generic reflection prompt without a source. Rejected: the citation is the reason the prompt's shape is defensible, and a rewritten prompt presented as the paper's would be a false provenance claim.

---

## D2 — Two evidence sources, disjoint by construction

**Decision**: Training evidence is **recorded sessions read from the database**; held-out evidence is **fresh execution** with the skill under test active. Disjointness is **asserted in code** at gate time.

**Rationale**: This is stronger than sampling a split. Recorded sessions were produced under the **previous** skill, before the candidate existed, so they cannot contain it. Fresh executions exist only after it. The two sets are disjoint for a structural reason rather than because a random split was drawn correctly — which matters, because the failure mode it prevents is silent: a candidate tuned to the sessions it was derived from scores better on exactly those sessions.

The assertion is required because the structural argument depends on an implementation fact. If a future change made the gate read recorded sessions, the structural argument would still *read* as true while being false. The assertion converts that into a loud failure.

**Alternatives considered**:
- *Hold out a slice of recorded sessions.* Rejected: a recorded verdict describes what happened under a **different** skill. It cannot be re-attributed to the candidate, so the gate would compare two numbers that do not both describe the thing under test.
- *Trust the design and skip the assertion.* Rejected: the whole feature exists to stop measurements being trusted without being checked.

---

## D3 — The held-out task set is the five existing blueprints; M=4 of 5

**Decision**: Reuse `backend/tests/fixtures/baseline_blueprints/` — `pair-a`, `pair-b`, `minimal`, `multi-entity`, `constrained`. **No new fixtures.** Hold out **M=4** per iteration, leaving one as a rotation buffer, rotated deterministically.

**Rationale**: A gate whose task set was authored alongside the thing it evaluates measures the author. These five already exist, were frozen by feature 011 as a baseline corpus, and were not written with this loop in mind — which is exactly the property that makes them usable as an exam.

With five tasks and M=4, one is always excluded, so successive iterations are not scored on an identical fixed exam. That bounds a specific overfitting mode: a five-item exam scored repeatedly eventually gets memorised by the loop.

**Recorded limitation**: five tasks is a small exam. One task's outcome moves the pass rate by 25 percentage points, so the gate is coarse and a single execution's noise can decide an acceptance. This is acceptable for a loop-validation feature and is **not** acceptable for a production optimiser — it belongs with the deferred statistical validation. Recorded rather than hidden.

**Alternatives considered**:
- *Author purpose-built held-out fixtures.* Rejected explicitly by the requirement, and correctly: it would let the gate be tuned.
- *Use all five every iteration.* Rejected: a fixed exam invites memorisation.
- *Random rotation.* Rejected: the comparison must reproduce, so rotation is derived from the iteration's identity rather than from a random seed or the clock.

---

## D4 — The gate scores both skills, on the identical sample

**Decision**: `current_score` and `candidate_score` are computed in the same iteration, on the same blueprints, by the same scoring function. **2×M fresh executions per iteration** (default 8).

**Rationale**: The cheap alternative — carrying the previous run's accepted score forward — compares a number measured on one sample against a number measured on another. It is absent on the first iteration and silently wrong whenever the held-out set rotates, which D3 makes routine. Persisting a prior score would also introduce state into a feature whose entire premise is that it has no memory between runs.

Doubling execution cost buys a comparison that is always valid, needs no persisted state, and is trivially testable with a scripted runner.

**Alternatives considered**:
- *Carry the previous score.* Rejected: stale, absent on iteration one, and silently wrong under rotation.
- *Scoring the current skill once and caching it.* Rejected for v1: it needs a held-out-set identity to know when reuse is safe, which is more machinery than the cost it saves.

---

## D5 — A pass is a real build, never a synthetic one

**Decision**: A pass means the offline build/test exit code is zero. **An execution whose verification used the hermetic fallback does not count as a pass, even when its exit code is zero.** Executions that could not be scored at all are reported separately.

**Rationale**: This is the interaction between the gate and features 012/013, and it is a genuine trap. Under `ALLOW_HERMETIC_FALLBACK=true` a substitution returns **exit code zero without compiling anything**. A gate that scored on exit code alone would therefore reward a skill for making the verifier give up — the candidate would score higher precisely because verification stopped happening.

Feature 012 established that a synthetic verification is not a successful generation. The same rule has to hold here, or the optimiser will discover the loophole and exploit it, because exploiting it is exactly what "improve the score" means to a text optimiser.

**Alternatives considered**:
- *Score on the build exit code alone.* Rejected: it is the loophole above.
- *Score on terminal status alone.* Rejected: a session can reach a terminal status without its build having been verified, which is the same problem in a different field.

---

## D6 — The runner is injectable

**Decision**: The fresh-execution function takes the runner as a parameter. Production passes the real session runner; the test passes one backed by the scripted model client.

**Rationale**: Constitution Principle VI forbids provider calls in the automated suite, and the success criteria require a full iteration to be testable. Without injection the loop is untestable in CI, and an untested gate is worse than no gate — it would report acceptances nobody had ever checked.

Injection is also what makes SC-002 testable at all: the three gate outcomes (strictly better, equal, worse) must be demonstrable deterministically, which requires a runner whose score is controlled by the test rather than by a model.

**Alternatives considered**:
- *Monkeypatch the model factory globally.* Rejected as the primary mechanism: it makes the test depend on where the call happens rather than on an explicit seam, so a refactor could silently stop injecting. The parameter is the contract; a monkeypatch would be an implementation detail.

---

## D7 — Injection into generation is a no-op when no skill is active

**Decision**: The stage boundary prepends the active skill's content when the active-skill file is present and readable; otherwise it renders exactly what it renders today.

**Rationale**: This is the first code to read a directory that is currently **empty** — three zero-byte placeholder files. An injection point that errors on absence, or that treats an empty file as content, would break every existing session the moment it shipped. Feature 013 established the pattern for this kind of side-channel: the side effect must be incapable of breaking the thing it observes.

SC-005 makes it checkable: with no active skill, the rendered request must be byte-identical to the pre-feature request.

**Alternatives considered**:
- *Fail loudly when the active file is missing.* Rejected: absence is the normal state, not an error.
- *Treat an empty skill as a skill with no rules.* Rejected as the default: it makes an accidentally-truncated file indistinguishable from a deliberate no-op.

---

## D8 — Bounded edits, with the protected region honoured

**Decision**: Four operations (`append`, `insert_after`, `replace`, `delete`), capped at **L_t = 4** edits, applied to a copy. Edits targeting the protected region or absent text are rejected **individually** — a rejected edit does not abort the batch.

**Rationale**: The cap is the paper's textual learning-rate analogue and is what keeps a candidate comparable to its predecessor. Individual rejection matters because one malformed proposal from a model should not discard three good ones, and because the rejection reason is the only signal an operator gets about why an iteration underperformed.

Applying to a copy is what makes acceptance meaningful: if the original were edited in place, a rejected candidate would already have changed the skill, and the "rejection" would be a lie.

**Alternatives considered**:
- *Reject the whole batch on one bad edit.* Rejected: brittle, and it discards usable proposals.
- *Clamp rather than reject an out-of-range target.* Rejected: silently relocating an edit makes the applied candidate differ from the proposed one, so the logged edits would no longer describe what was tested.

---

## D9 — The run record is a new table

**Decision**: `skillopt_runs`, created by the ORM's metadata.

**Rationale**: The database currently holds only the session table. Unlike 011/012/013 — which added columns to an existing table through an idempotent `ALTER TABLE` shim — a new model gets its table from `Base.metadata.create_all`, so no migration shim is needed. The row is written on **every** exit path, including failure, so a crashed iteration is visible rather than indistinguishable from one that never ran.

**Alternatives considered**:
- *Log to a file.* Rejected: the requirement names the database, and a run log that lives elsewhere cannot be joined against sessions.

---

## D10 — Branch: a fourth stacked feature

**Decision**: Stay on `feature/011-llm-generation-nodes`; record the exception.

**Rationale**: `main` is untouched, nothing has merged, and all four features are one arc. Splitting now would mean rebasing four features' commits for no isolation benefit, and would produce branches that are not independently green — 014 reads 011's sessions, honours 012's fallback marking in its pass rule (D5), and reuses 013's side-channel-with-best-effort-write pattern.

014 is the most self-contained of the four in one respect worth noting: with no active skill it does not change generation behaviour at all, so it cannot regress the earlier features' behaviour by being present.

**Alternatives considered**: a dedicated branch. Rejected for the same reasons recorded for 012 and 013.

---

## Summary of decisions

| ID | Decision | Primary requirement |
| --- | --- | --- |
| D1 | Source verified; cite Appendix C.2.1 precisely; do not reproduce its text | FR-004 |
| D2 | Two evidence sources, disjoint by construction, asserted in code | FR-006, SC-008 |
| D3 | Reuse the five existing blueprints; M=4 of 5; deterministic rotation | FR-006, FR-006a |
| D4 | Score both skills on the identical sample; 2×M executions | FR-007, SC-009 |
| D5 | A pass is a real build; a fallback-marked execution never passes | FR-006 |
| D6 | Injectable runner | FR-006, SC-001 |
| D7 | No-op when no skill is active | FR-002, SC-005 |
| D8 | Four operations, cap 4, individual rejection, apply to a copy | FR-005 |
| D9 | New `skillopt_runs` table, written on every exit path | FR-008, SC-006 |
| D10 | Fourth stacked feature, exception recorded | — |

No open `NEEDS CLARIFICATION` items remain.
