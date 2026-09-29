# Quickstart Validation: Diagnostic-Driven Skill Evolution

Each scenario is runnable and maps to success criteria. None requires a provider
key; nothing here spends money.

## Prerequisites

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/test_conformance_diagnostics.py -q
PYTHONPATH=backend .venv/bin/python backend/scripts/measure_conformance_discrimination.py
```

The second command is the baseline instrument check: it must report clean sets
scoring 100 on every blueprint, all rule kinds detected, and **blind to nothing**.
If it reports a blind rule, stop — every scenario below depends on the instrument.

---

## Scenario 1 — A failed session explains itself (US1, SC-001, SC-002)

Run a session whose artifacts contain a deliberate defect. Read the session record.

**Expected**: the record names the rule, the artifact path, its severity, and the
stage that introduced it — without re-running.

**Then**: run the same session again and compare records.
**Expected**: byte-identical. A non-identical record means the instrument drifts,
and no later improvement can be attributed to anything (SC-003).

---

## Scenario 2 — "Not evaluable" is not "clean" (US1, FR-004)

Run a session that produces no artifacts, and separately one whose build falls back
to a synthetic result.

**Expected**: the first records `evaluable=false`; the second records
`unverified=true`. **Neither** is reported as clean, and **neither** appears in any
measurement's supporting evidence (SC-006).

---

## Scenario 3 — The measure is size-comparable (FR-019, SC-012)

Diagnose two artifact sets differing only in artifact count, with findings in the
same proportion.

**Expected**: the same score. A different score means a round could improve the
measure by generating less code.

---

## Scenario 4 — Contribution separates a real skill from an inert one (US2, SC-004)

Measure a skill known to change outcomes and a skill known not to, on an adequate
task set. Then measure on a deliberately inadequate one.

**Expected**: the first pair separates; the second reports `sufficient=false`. A
point estimate reported without its power is the failure this scenario exists to
catch.

---

## Scenario 5 — Insufficiency is not an improvement (US2/US3, FR-008, FR-016)

Run a round where the measurement is insufficient.

**Expected**: the round records `NO_MEASURABLE_CHANGE`, changes nothing, and does
not report an improvement. **This is the expected outcome at the current asset
count, not a failure of the feature.**

---

## Scenario 6 — A skill that does not earn its place is removed (US3, SC-007)

Measure a skill whose contribution falls **below the floor**, then run a round.

**Expected**: the skill is removed and the record cites the measurement. Then run
the same round with a contribution that is merely *not proven positive* — above the
floor but inside the noise.

**Expected**: **no removal**. This is the distinction that stops noise from driving
the set (FR-012).

---

## Scenario 7 — The judge is out of reach (SC-010)

From within a round, attempt to modify the counting rules, the severity weights,
and the evidence floor.

**Expected**: all three attempts have no effect.

---

## Scenario 8 — One record, every path (SC-009)

Trigger each terminal state in turn: no sessions, no failures, insufficient
evidence, an accepted change, a rejected change, and an induced exception.

**Expected**: exactly one record each, and the failing path carries the exception.
No path leaves zero records.

---

## What this quickstart does not claim

Scenarios 4–6 depend on the task-set size. At the current five blueprints the
smallest detectable effect is large, so **Scenario 5 is the expected outcome of a
real round** and Scenario 6 requires a deliberately large effect to exercise. The
feature's honesty about that is part of its correctness, not a gap in it.
