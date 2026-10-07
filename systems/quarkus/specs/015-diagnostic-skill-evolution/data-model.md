# Phase 1 Data Model: Diagnostic-Driven Skill Evolution

Two entities already exist and are reused unchanged in shape: the **conformance
verdict** and its **violations** (both frozen dataclasses in
`orchestrator/stages/compliance.py`), surfaced by `conformance_diagnostics.diagnose`.
This feature adds persistence around them and three new records.

---

## 1. Conformance report *(exists — `services/conformance_diagnostics.py`)*

| Field | Meaning |
| --- | --- |
| `score` | 0–100, floored. Weighted `100 − (critical·30 + high·15 + medium·5 + low·2)` |
| `blocking` | whether any finding is stopping-severity |
| `violations` | the findings, deduplicated across both validator families |
| `counts_by_severity` | severity → count |
| `rule_histogram` | rule identity → count |
| `evaluated_artifact_count` | how many artifacts were examined |

**Validation rules**
- Deterministic: identical input → identical report (FR-003)
- Must distinguish *evaluated and clean*, *evaluated with findings*, and *not
  evaluable* (FR-004)

**Change required by this feature**: `score` is a raw weighted count today and is
**not** comparable across artifact-set sizes (D6). It is replaced by a normalised
measure. The raw count is retained alongside it, so nothing that already consumes
the score changes meaning silently.

---

## 2. Session diagnostic record *(new — persisted)*

One per session that reaches a terminal state (FR-001).

| Field | Meaning |
| --- | --- |
| `session_id` | the session it describes |
| `score` | the normalised conformance measure |
| `raw_penalty` | the unnormalised weighted count, retained for comparison |
| `evaluable` | `false` when no verdict could be produced (FR-004) |
| `unverified` | `true` when the build fell back to a synthetic result (FR-005) |
| `artifact_count` | the denominator the measure was normalised against |
| `counts_by_severity` | severity → count |
| `rule_histogram` | rule identity → count |
| `findings` | the individual findings, each rule + artifact + severity (FR-002) |
| `stages` | per-stage attribution (below) |
| `recorded_at` | when it was persisted |

**Validation rules**
- An `unverified` session is **excluded from optimization evidence** and says so
- `evaluable=false` must never be recorded as clean and never as failed
- `findings` must be reproducible from the same artifacts

**State**: a record is written once, at terminal state, and is immutable after.

---

## 3. Stage attribution *(new — part of the diagnostic record)*

| Field | Meaning |
| --- | --- |
| `stage` | scaffolder / domain / service / controller / test |
| `rule_histogram` | rules first observed at this stage |
| `score` | conformance measure for the accumulated set at this stage |

**Source**: the `initial_verdict` already carried on every stage journal entry.
This is read and persisted, not recomputed.

**Why**: it identifies *which stage introduced* a violation (FR-018, SC-011),
which is attribution and not extra evidence — the distinct-task count is
unchanged by it (FR-009).

---

## 4. Skill contribution measurement *(new)*

One per (skill, task set) pair measured.

| Field | Meaning |
| --- | --- |
| `skill_id` | which skill was removed |
| `with_skill` | outcome with the skill present |
| `without_skill` | outcome with it removed |
| `delta` | the observed difference |
| `distinct_tasks` | **distinct** tasks behind the delta, not observations (FR-009) |
| `min_detectable_effect` | smallest effect detectable at that size (FR-007) |
| `sufficient` | whether the evidence supports a conclusion (FR-008) |
| `floor` | the evidence floor used for the removal decision |

**Validation rules**
- `sufficient=false` must not be presented as an improvement (FR-008, FR-016)
- `distinct_tasks` counts distinct tasks; repeated observations of one task add
  nothing
- When `sufficient=false`, no removal may follow (FR-012)

---

## 5. Evolution round record *(new — extends feature 014's run record)*

One per round, on **every** exit path including failure (FR-013).

| Field | Meaning |
| --- | --- |
| `started_at` / `completed_at` | timing |
| `n_training` / `n_held_out` | evidence sizes used |
| `proposed` | what the reflection step proposed |
| `applied` / `rejected` | which edits were applied, and why others were not |
| `measurements` | the contribution measurements taken |
| `removed` | skills removed, each citing its measurement |
| `decision` | accepted / rejected / no-failures / no-sessions / error / **no-measurable-change** |
| `error` | populated on the failure path |

**State transitions**

```text
collect ──no sessions──────────────► NO_SESSIONS      (recorded)
        └─no failures──────────────► NO_FAILURES      (recorded)
        └─failures──► propose ─────► measure ──insufficient──► NO_MEASURABLE_CHANGE
                                          ├─below floor──► REMOVED
                                          └─above floor──► guardrail ─► ACCEPTED / REJECTED
```

Every terminal state writes exactly one record. `ERROR` carries the exception.

---

## Relationship to existing entities

| Existing | Relationship |
| --- | --- |
| `generation_sessions` | one diagnostic record per session |
| `skillopt_runs` (feature 014) | extended, not replaced; the round record is the same row grown |
| stage journal entries | read for per-stage attribution; not modified |
| skill documents (`app/skills/`) | the round's input and, on acceptance, its output |
