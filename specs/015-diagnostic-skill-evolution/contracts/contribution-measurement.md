# Contract: Skill Contribution Measurement

**Guarantees**: FR-006 – FR-009, FR-012 · **Criteria**: SC-004, SC-005

## Interface

```python
measure_contribution(skill_id, task_set, run_with, run_without) -> ContributionMeasurement
```

`run_with` / `run_without` are injected runners, as in feature 014 — a parameter
and never a monkeypatch, so a refactor cannot silently stop injecting and leave
the suite executing real sessions.

## Contract

| Field | Guarantee |
| --- | --- |
| `delta` | the observed difference in the conformance measure |
| `distinct_tasks` | **distinct** tasks behind it — repeats add nothing |
| `min_detectable_effect` | smallest effect detectable at `distinct_tasks` |
| `sufficient` | whether the evidence supports any conclusion |
| `floor` | the stated evidence floor used by the removal decision |

## Rules

1. **Repeats are not evidence.** Measuring one task N times yields
   `distinct_tasks = 1`. Reporting N would let a round manufacture significance by
   repeating itself.
2. **Insufficiency is a result.** When `sufficient=false`, the measurement MUST
   report that the evidence cannot support a conclusion and MUST NOT present
   `delta` as an improvement.
3. **No removal without sufficiency.** A removal may follow only from a
   measurement that is both sufficient and below the floor. "We could not show it
   helps" is explicitly **not** grounds for removal.
4. **Both arms on the same tasks.** The with/without arms MUST run the identical
   task set; otherwise the comparison is meaningless while still producing a
   number.

*Verified by*: separating a known-load-bearing skill from an inert one on an
adequate task set; reporting insufficiency on an inadequate one; and confirming
that a sufficient-but-above-floor measurement causes no removal.

## Failure behaviour

- A runner raising: the measurement is abandoned and the round records the error.
- A task evaluable in one arm but not the other: excluded from both, and counted
  in neither — an asymmetric task set is not a comparison.
