# Tasks: Session Diagnostics and Corpus Baseline

**Feature**: 015-diagnostic-skill-evolution (rescoped) | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Scope**: the instrument and the baseline. The optimizer half is deferred and its tasks are listed at the end, **not scheduled**.

## Implementation Strategy

Two user stories. **US1 is the MVP**: it makes what the platform already computes
durable and attributable, and it is independently valuable with no report at all.
**US2 is the payoff**: it produces the number the platform currently cannot state.

TDD throughout, per the project convention: each implementation task is preceded by
the test that fails without it. Test tasks and implementation tasks are paired in
vertical slices rather than writing all tests first.

The instrument already exists (`services/conformance_diagnostics.py`, shipped
ahead of this plan) and is not rebuilt. It is extended, not replaced.

---

## Phase 1: Setup

- [X] T001 Run the existing instrument baseline and record the result: `PYTHONPATH=backend .venv/bin/python backend/scripts/measure_conformance_discrimination.py`. Confirm clean sets score 100 on every blueprint, all six rule kinds are detected, and **blind to nothing**. If a rule is blind, stop — everything below depends on the instrument.

- [X] T002 [P] Establish the normalization rule in `backend/app/services/conformance_diagnostics.py`: the reported `score` must be comparable across artifact sets of different sizes (FR-007), while `raw_penalty` is retained unchanged so no existing consumer's meaning shifts.

---

## Phase 2: Foundational

*Blocking. Both user stories report the normalized measure and persist a record.*

- [X] T003 Test the normalization property in `backend/tests/test_conformance_diagnostics.py`: two artifact sets differing **only in size**, carrying findings in the same proportion, MUST yield the same score (SC-009). Include the degenerate case of an empty set.

- [X] T004 Implement normalization in `backend/app/services/conformance_diagnostics.py` to pass T003. Keep `raw_penalty` on the report alongside the normalized `score`.

- [X] T005 Add the session diagnostic record to `backend/app/models/skillopt.py`: `session_id`, `score`, `raw_penalty`, `evaluable`, `unverified`, `artifact_count`, `counts_by_severity_json`, `rule_histogram_json`, `findings_json`, `stages_json`, `recorded_at`. Follow the existing `ensure_schema(bind)` pattern so the table is created on the engine actually in use, not the one resolved at import.

- [X] T006 Test the schema binding in `backend/tests/test_diagnostic_record.py`: a write must succeed after `SessionLocal` is rebound to a different engine. This is the failure that silently swallowed feature 014's writes — the best-effort write path reported success while logging nothing.

---

## Phase 3: User Story 1 — A failed session explains itself (P1) 🎯 MVP

**Goal**: every session reaching a terminal state carries a durable, structured,
deterministic record of what was found wrong with its artifacts, attributable to
the stage that introduced each finding.

**Independent test**: run a session with a known defect; the record names rule,
artifact, stage and severity; a repeat run produces an identical record.

- [X] T007 [P] [US1] Test in `backend/tests/test_diagnostic_record.py` that a terminal session persists a record naming the rule, artifact path and severity (FR-001, FR-002, SC-001, SC-002).

- [X] T008 [P] [US1] Test determinism in `backend/tests/test_diagnostic_record.py`: two evaluations of byte-identical artifacts produce equal records, with no dependence on time, dict ordering or randomness (FR-003, SC-003).

- [X] T009 [P] [US1] Test the three states in `backend/tests/test_diagnostic_record.py`: *evaluated and clean*, *evaluated with findings*, and *not evaluable* are all distinguishable, and **none is conflated with another** (FR-004). A session with no artifacts must record `evaluable=false` and must NOT read as clean.

- [X] T010 [P] [US1] Test exclusion of unverified sessions in `backend/tests/test_diagnostic_record.py`: a session whose build fell back to a synthetic result records `unverified=true` regardless of terminal status (FR-005, SC-004).

- [X] T011 [US1] Implement the record writer in `backend/app/services/conformance_diagnostics.py` to pass T007–T010. Must never raise into the caller: a diagnostics failure must not prevent the session's own terminal-state record from being written.

- [X] T012 [US1] Implement per-stage attribution in `backend/app/services/conformance_diagnostics.py`, reading `initial_verdict` from the existing stage journal entries (FR-006, SC-002). Do **not** recompute the verdict; it is already there.

- [X] T013 [US1] Wire the writer into the session terminal path in `backend/app/api/routes_session.py`, on **both** completion paths, alongside the existing `_persist_verification_metrics` calls at lines 253 and 277.

- [X] T014 [US1] Test in `backend/tests/test_diagnostic_record.py` that a session which fails *after* producing artifacts still records the findings produced before the failure (FR-014, edge case).

---

## Phase 4: User Story 2 — The corpus can be measured (P2)

**Goal**: run a batch of sessions over the held-out task set and produce one report
stating population, exclusions with reasons, conformance distribution, correction
effort and cost — with absent data reported as absent.

**Independent test**: run a batch; the report states population and exclusions;
with an empty store it reports no data rather than zero.

- [X] T015 [P] [US2] Test the corpus report in `backend/tests/test_corpus_report.py`: the report states session count, verified count, and excluded count **with reasons** (FR-009, SC-007).

- [X] T016 [P] [US2] Test the no-data contract in `backend/tests/test_corpus_report.py`: with an empty store the report states that no data exists and reports **neither a zero rate nor a zero cost** (FR-011, SC-005). "No data" and "measured zero" are different findings and must not render the same.

- [X] T017 [P] [US2] Test the sample contract in `backend/tests/test_corpus_report.py`: the report states the number of **distinct tasks** separately from the number of **sessions**, so repeated runs of one task are never presented as a larger sample (FR-013, SC-008).

- [X] T018 [P] [US2] Test exclusion arithmetic in `backend/tests/test_corpus_report.py`: unverified sessions contribute to **no** reported rate or distribution, and their exclusion is stated (FR-012, SC-004).

- [X] T019 [US2] Implement the corpus report in `backend/app/services/corpus_report.py` to pass T015–T018. Include the conformance distribution and correction effort alongside the success rate (FR-010), and report the distinct-task count beside every derived figure (FR-015).

- [X] T020 [US2] Implement the batch driver in `backend/scripts/run_corpus_baseline.py`: run sessions over the held-out blueprints and record every outcome (FR-008, SC-006). Cost must be reported only where the cost store has data.

- [X] T021 [US2] Test in `backend/tests/test_corpus_report.py` that a batch records every outcome **including sessions that fail**, and that a batch interrupted partway leaves completed sessions fully recorded without reporting the batch as complete (SC-006, edge case).

---

## Phase 5: Polish & Cross-Cutting

- [X] T022 Run the full suite (`timeout 900 .venv/bin/python -m pytest -q`) and record before/after counts. Confirm the pre-existing validator families, the conformance gate, `runner.py` and every test file from features 011–014 are byte-identical.

- [X] T023 [P] Run the report against an empty store and against any real sessions recorded, and record both outputs verbatim in `specs/015-diagnostic-skill-evolution/quickstart.md`. The empty-store output is a deliverable: it demonstrates the no-data contract.

- [ ] T024 [P] Update `docs/agentia_current_state.tex` with the measured baseline, and mark all tasks complete in this file.

---

## Dependencies

```text
Phase 1 (T001-T002)
   └── Phase 2 (T003-T006)          both stories report the normalized measure
         ├── Phase 3 US1 (T007-T014)   MVP — instrument made durable
         └── Phase 4 US2 (T015-T021)   needs US1's records to summarise
               └── Phase 5 (T022-T024)
```

US1 and US2 are sequential rather than parallel: the report in US2 summarises the
records US1 produces, so there is nothing for it to summarise until US1 lands.

## Parallel opportunities

Within each phase, the `[P]` tasks touch different files or different test
functions and can be written together:

- **Phase 3**: T007–T010 (four independent test cases), then T011–T014 in sequence.
- **Phase 4**: T015–T018 (four independent test cases) can be written together; T019–T021 follow.
- **Phase 5**: T023 and T024 are independent.

## MVP scope

**US1 alone (T001–T014)** is a viable deliverable: an operator can diagnose any
failed session from its record without re-running, and every session becomes
measurable. US2 turns that into a corpus number.

## Format validation

All tasks use `- [ ] Tnnn [P?] [USn?] description with file path`. Setup and
Polish phases carry no story label; Phase 3 tasks carry `[US1]`; Phase 4 carry
`[US2]`.

---

## Deferred — NOT scheduled

These are specified in [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md) and [contracts/](contracts/) and are **deliberately
not built yet**. They are listed so the decision is not lost.

**Gate before scheduling any of them**: the corpus report must show that the
conformance measure **varies** across real sessions. If every recorded session
scores identically there is nothing for an optimizer to move, and the effort
belongs on a different lever — most plausibly verifying and then implementing
selection among samples with the platform's own free verifier, which the evidence
ranks well above text-space skill optimization and which needs no training.

- Per-skill contribution measurement by leave-one-out (FR-006–FR-009 of the original spec)
- Retargeting an optimization round onto recorded evidence (original FR-010)
- Skill removal below an evidence floor (original FR-011, FR-012)
- One record per optimization round on every exit path (original FR-013)
- Keeping the counting rules outside a round's reach (original FR-014)
- Bounding skills per round (original FR-017)
- `backend/app/services/skill_contribution.py`, `backend/scripts/skillopt/currency.py`, `backend/tests/test_skill_contribution.py`, `backend/tests/test_skillopt_pruning.py`
