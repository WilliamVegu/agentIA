# Contract: Stage Execution Boundary

**Feature**: LLM-Driven Generation Stages
**Date**: 2026-09-28

This is the load-bearing interface of the feature. It is the single entry point through which both execution paths invoke a generation stage, and the single place where mode selection, budgeting, gating, provenance, and journaling are enforced.

---

## 1. Why this contract exists

Five concerns are identical across all five stages and both execution paths:

1. **Mode selection** — model-driven or deterministic (research D2).
2. **Request and correction budgeting** — bounded, separate from the repair loop's counter (FR-008, FR-009, FR-015).
3. **Compliance gating** — nothing reaches disk unvalidated (FR-004, FR-007).
4. **Provenance recording** — per artifact (FR-019).
5. **Correction-journal retention** — including on exhaustion (FR-011).

Duplicating any of these per stage or per path produces copies that drift. There is precedent in this codebase for exactly that failure: two constitutional validators implementing overlapping rules with incompatible severities.

---

## 2. Contract

### 2.1 Entry point

A single callable that executes one named stage against session state and returns updated session state.

**Inputs**

| Input | Required | Notes |
|---|---|---|
| Session state | yes | Must carry `generation_mode`. A missing mode is a defect, not a default. |
| Stage name | yes | One of the five. |
| Workspace path | yes | Destination root for persistence. |
| Blueprint | yes | Source of the task payload. |

**Outputs**: updated session state containing the persisted-artifact map, log lines, the updated generation journal, and provenance records for artifacts persisted by this call.

**Return contract — the part that must not be violated**: the boundary returns **updated state**. Callers MUST consume the returned value. Callers MUST NOT rely on the boundary mutating dictionaries retrieved from the input state, even though the deterministic implementations happen to do so today. This is a deliberate breaking change for the sequential path (research D8) and it is what makes that path safe.

### 2.2 Behavior

For a given stage invocation:

1. Resolve `generation_mode` from state. Fail loudly if absent.
2. **`DETERMINISTIC`** — invoke the retained implementation, persist, append a `StageJournalEntry` with `outcome = SUCCEEDED` and `request_count = 0`. No validation gate is applied, matching the pre-migration behavior exactly; the deterministic output is known-compliant by construction.
   - *Deliberate asymmetry*: the gate exists to constrain a non-deterministic generator. Applying it to the deterministic path would change offline behavior, which FR-013 forbids. This asymmetry is intentional and must be documented in the code.
3. **`MODEL`** — issue a request built from the instruction set and the task payload; extract artifacts; validate against the accumulated set; on a blocking `LOCAL` violation, re-request with the violations fed back, up to two correction attempts; persist only on pass; on exhaustion, block the session.
4. Append journal entries and provenance records on **every** exit path.

---

## 3. Invariants

| # | Invariant | Source |
|---|---|---|
| 1 | Only this boundary writes generation-stage artifacts to the workspace. | FR-004 |
| 2 | Nothing is persisted from a response that failed validation. | FR-007 |
| 3 | Persistence is all-or-nothing per response. | FR-004 |
| 4 | Correction attempts ≤ 2 per stage; session requests ≤ 15. | FR-008, FR-015 |
| 5 | The correction counter is independent of the repair-attempt counter. | FR-009 |
| 6 | `ACCUMULATED`-attribution violations never cause artifacts to be rejected. | FR-006 |
| 7 | A `MODEL` session never transitions to `DETERMINISTIC`. | FR-008, research D2 |
| 8 | The journal is written on every exit path, including exhaustion. | FR-011 |
| 9 | Every persisted artifact in a `MODEL` session has exactly one provenance record. | FR-019 |
| 10 | No credential appears in state, journal, provenance, or artifacts. | FR-018, Principle VI |
| 11 | A missing instruction document is a startup failure, never a silent fallback to deterministic mode. | research D3 |

Invariant 11 deserves emphasis: if a missing instruction silently degraded to the deterministic implementation, a session would report success while producing pre-migration output, and every SC-001 measurement would be corrupted without any error being raised.

---

## 4. Coexistence of the two implementations

```text
                     ┌──────────────────────────────────────┐
   Path A (graph) ──►│                                      │
                     │      Stage Execution Boundary        │
   Path B (seq.) ───►│  mode · budget · gate · provenance    │
                     │                                      │
                     └───────────────┬──────────────────────┘
                                     │
                        generation_mode ?
                                     │
                  ┌──────────────────┴──────────────────┐
                  ▼                                     ▼
        MODEL implementation               DETERMINISTIC implementation
        (new; requests + validate)         (retained verbatim; no gate)
                  │                                     │
                  └──────────────────┬──────────────────┘
                                     ▼
                            updated session state
```

Both implementations satisfy the same interface, so both paths are agnostic to which is active. The deterministic implementations are retained, not reimplemented; they must remain behaviorally identical to their pre-migration form so that the baseline captured in Phase 0 stays a valid comparison target.

---

## 5. Failure semantics

| Condition | Outcome | Rationale |
|---|---|---|
| Mode absent from state | Raise; do not default | A wrong guess runs an entire session in the wrong mode. |
| Instruction set incomplete | Raise at startup | Prevents silent degradation to the deterministic path (invariant 11). |
| No model client constructible | Session runs `DETERMINISTIC` | FR-013; decided at session start, not here. |
| Response not extractable | Attempt consumed; counts toward budget | FR-014. |
| Blocking `LOCAL` violation | Attempt consumed; re-request with feedback | FR-008. |
| Blocking `ACCUMULATED` violation | Record; do not reject | FR-006. |
| Budget exhausted | Block session, same terminal status as repair exhaustion | FR-010. |
| Persistence fails mid-write | Surface as an error; do not continue | FR-021's index contract assumes persisted artifacts match state. |

---

## 6. What this contract deliberately does not do

- Does not decide the mode (that is session-start policy, upstream).
- Does not modify, consolidate, or bypass the compliance validators; it adapts their results (see `compliance-verdict.md`).
- Does not touch the sandbox verifier or the repair loop (FR-023, plan Constraint 5).
- Does not change graph topology, node names, or conditional edges — the graph keeps dispatching exactly as it does today, and the node callables delegate here.
