# Contract: Session Diagnostic Record

**Guarantees**: FR-001 – FR-005, FR-018, FR-019 · **Criteria**: SC-001 – SC-003, SC-006, SC-011, SC-012

## Interface

```python
diagnose(artifacts: Mapping[str, str]) -> ConformanceReport        # exists
record_session_diagnostics(session_id, report, stages) -> None     # new
```

## Determinism contract

For byte-identical `artifacts`, two calls MUST return equal reports. No dependence
on wall-clock time, dict ordering, or randomness. This is what makes a later
improvement attributable to the change rather than to the instrument drifting.

*Verified by*: re-running the diagnosis over identical input and comparing the
serialised reports.

## Three-state contract

The record MUST distinguish, and never conflate:

| State | Condition | Consequence |
| --- | --- | --- |
| **Evaluated, clean** | verdict produced, no findings | usable as evidence |
| **Evaluated, findings** | verdict produced, findings present | usable as evidence |
| **Not evaluable** | no verdict could be produced | **excluded** from evidence |

A fourth condition is tracked separately: `unverified`, meaning the build fell back
to a synthetic result. Such a session is **excluded from evidence** regardless of
its terminal status — counting it would reward changes that make verification less
likely to run.

*Verified by*: a session with no artifacts must record `evaluable=false` and must
not be reported as clean; an unverified session must record `unverified=true` and
must not appear in any measurement's supporting evidence.

## Size-comparability contract

The reported `score` MUST be comparable across artifact sets of different sizes:
two sets carrying findings in the same proportion, differing only in artifact
count, MUST yield the same score. The unnormalised `raw_penalty` is retained
alongside so no existing consumer's meaning changes silently.

*Verified by*: constructing two sets differing only in size with equal finding
proportions, and asserting equal scores.

## Per-stage attribution contract

Each finding MUST be attributable to the stage that introduced it, read from the
verdict already carried on the stage journal entry. Attribution MUST NOT alter the
distinct-task count (FR-009): it adds resolution, not evidence.

*Verified by*: a session with a known stage-local defect records the finding
against that stage.

## Failure behaviour

- Artifacts containing a non-string value: skipped, not raised on.
- An unknown severity: scored with a non-zero penalty, so a gap in the severity
  table cannot read as harmless.
- No exception from `diagnose` may prevent the session's own terminal-state record
  from being written.
