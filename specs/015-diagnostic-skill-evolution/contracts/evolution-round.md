# Contract: Evolution Round

**Guarantees**: FR-010 – FR-017 · **Criteria**: SC-007 – SC-010, SC-012

## Interface

```python
run_round(*, skills, task_set, runner, ...) -> RoundRecord
```

## One record, always

Exactly one record per round, on **every** exit path:

| Terminal state | Meaning |
| --- | --- |
| `NO_SESSIONS` | nothing recorded to learn from |
| `NO_FAILURES` | sessions recorded and all clean — the set is working |
| `NO_MEASURABLE_CHANGE` | evidence too thin to conclude (the expected outcome at this scale) |
| `REMOVED` | at least one skill fell below the floor |
| `ACCEPTED` / `REJECTED` | the regression guardrail's verdict |
| `ERROR` | the round failed; the record carries the exception |

A round that crashed without a record is indistinguishable from one that never
ran, which is why the record is written on the failure path too.

## Decision rules

1. The round decides using recorded evidence, not a whole-corpus pass-rate
   comparison (FR-010).
2. Removal requires a **sufficient** measurement below the floor (FR-012). Silent
   removal on a non-improvement is forbidden.
3. An empty skill set is a **valid** outcome, not an error (FR-015).
4. A round MUST NOT report an improvement the evidence cannot support (FR-016).
5. The number of skills considered is bounded by a documented constant (FR-017).

## The judge is out of reach

A round MUST NOT be able to alter the rules by which findings are counted, nor the
severity weights, nor the evidence floor (FR-014). This is the constraint that
stops a round manufacturing an improvement by degrading the instrument that judges
it — the failure mode the whole diagnostic channel exists to prevent.

*Verified by*: attempting to modify each of those from within a round and
confirming the attempt has no effect (SC-010).

## Guardrail, not objective

Feature 014's strict-improvement gate is retained as a **regression veto**. It is
no longer the acceptance criterion, because a binary comparison over a handful of
tasks cannot separate a real change from variance. A round may therefore record
`NO_MEASURABLE_CHANGE` while the guardrail reports no regression — that is the
expected outcome, not a contradiction.
