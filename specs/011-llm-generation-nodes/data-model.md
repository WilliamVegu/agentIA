# Data Model: LLM-Driven Generation Stages

**Feature**: LLM-Driven Generation Stages
**Branch**: `skillopt_implementation`
**Date**: 2026-09-28

Entities are described at the design level: fields, types, validation rules, and relationships. Physical storage details are deliberately deferred to `/speckit-tasks`. Where an entity extends existing session state, the extension is marked **additive**.

---

## 1. Entity Overview

```text
GenerationSession (existing, extended)
├── generation_mode ──────────────► GenerationMode
├── generation_journal ──────────► GenerationJournal
│                                    └── StageJournalEntry (one per stage)
│                                          └── CorrectionAttemptRecord (0..2 per stage)
└── artifact_provenance ─────────► GenerationProvenanceRecord (0..n per artifact)

GenerationStage (5 fixed) ──uses──► InstructionDocument (1 per stage)
                          ──emits──► CandidateArtifactSet ──validated by──► ComplianceVerdict
                                                             └── yields ──► ComplianceViolation (0..n)
```

---

## 2. Enumerations

### `GenerationMode`

| Value | Meaning |
|---|---|
| `MODEL` | The session uses model-driven implementations for all five stages. |
| `DETERMINISTIC` | The session uses the retained template implementations for all five stages. |

Invariant: exactly one value per session. Decided once at session start (research D2) and immutable for the session's lifetime. A `MODEL` session never transitions to `DETERMINISTIC`.

### `StageName`

`SCAFFOLDER`, `DOMAIN`, `SERVICE`, `CONTROLLER`, `TEST` — fixed set, mirrors the five existing stage callables.

### `StageOutcome`

| Value | Meaning |
|---|---|
| `SUCCEEDED` | Artifacts passed validation and were persisted. |
| `CORRECTED` | At least one response was rejected; a later response passed and was persisted. |
| `EXHAUSTED` | Both correction attempts failed; the session transitioned to the human-intervention state. |
| `UNUSABLE_RESPONSE` | No extractable artifact could be obtained from the response; counted as a failed attempt. |

### `ViolationSeverity`

`CRITICAL`, `BLOCKING`, `HIGH`, `MEDIUM`, `LOW` — union of the two existing validator families' severity vocabularies.

Blocking rule: `CRITICAL`, `BLOCKING`, and `HIGH` are blocking; `MEDIUM` and `LOW` are advisory.

---

## 3. Entities

### 3.1 `GenerationStage`

| Field | Type | Notes |
|---|---|---|
| `name` | `StageName` | Identity. |
| `artifact_scope` | set of glob patterns | Which workspace-relative paths this stage owns. Used by FR-006 to separate local from accumulated violations. |
| `instruction` | `InstructionDocument` | The instruction in force for this stage. |
| `depends_on` | list of `StageName` | Prior stages whose artifacts this stage's payload includes. |

Validation rules:
- `artifact_scope` MUST be non-empty; a stage that owns no paths cannot attribute violations.
- `depends_on` MUST be acyclic.

Relationships: one `GenerationStage` to one `InstructionDocument`; one `GenerationStage` to zero-or-more `CorrectionAttemptRecord`s within a session.

### 3.2 `InstructionDocument`

| Field | Type | Notes |
|---|---|---|
| `stage` | `StageName` | |
| `content` | text | The system instruction. |
| `content_digest` | hex string | Digest of `content` after line-ending normalization. |
| `set_revision` | short hex string | Digest over the canonicalized map of all `stage → content_digest`. Shared by all five documents. |
| `version_label` | string | Human-readable label from the `VERSION` resource. Reporting only — never recorded in provenance. |

Validation rules:
- `set_revision` MUST be identical across all five documents in a set; a mismatch means a partially-loaded set, which MUST fail loudly rather than vend a mixed revision.
- All five stages MUST resolve. A missing instruction is a startup failure, not a runtime fallback — silently falling back to deterministic mode because one instruction file is absent would misattribute the cause.
- Content MUST NOT embed credentials.

### 3.3 `TaskPayload`

| Field | Type | Notes |
|---|---|---|
| `service_name` | string | |
| `package_name` | string | |
| `entities` | list of entity definitions | Name, attributes (name, type, constraints), relationships. |
| `user_stories` | list | With acceptance scenarios. |
| `prior_artifacts` | map path → content | Only those in the union of `depends_on` stages' `artifact_scope`. |

Validation rules:
- `prior_artifacts` MUST contain only artifacts already persisted (never rejected ones).
- Payload size is not silently truncated; if it exceeds the model's capacity the stage records `UNUSABLE_RESPONSE` and consumes an attempt (spec edge case).

### 3.4 `CandidateArtifactSet`

| Field | Type | Notes |
|---|---|---|
| `stage` | `StageName` | |
| `artifacts` | ordered map of path → content | Workspace-relative paths. |
| `extraction_ok` | boolean | Whether the response yielded well-formed, mappable artifacts. |
| `raw_response` | text, optional | Retained for the correction journal when extraction fails. |

Validation rules:
- MUST NOT be persisted in part. It is all-or-nothing (FR-004, FR-007).
- Every path MUST fall inside the stage's `artifact_scope`; out-of-scope artifacts are a rejection condition, since a stage inventing paths would break the index contract (FR-021).

### 3.5 `ComplianceVerdict`

| Field | Type | Notes |
|---|---|---|
| `passed` | boolean | True when no blocking violation exists. |
| `violations` | list of `ComplianceViolation` | Possibly empty. |
| `evaluated_artifact_count` | integer | Size of the accumulated set the verdict was computed over. |
| `sources` | set | Which validator families contributed — for auditability given research D4. |

### 3.6 `ComplianceViolation`

| Field | Type | Notes |
|---|---|---|
| `artifact_path` | string | Offending artifact. |
| `rule_id` | string | Stable rule identifier from the source validator. |
| `severity` | `ViolationSeverity` | |
| `blocking` | boolean | Derived from severity. |
| `message` | string | Human-readable description. |
| `suggested_fix` | string, optional | Carried through when the source provides it, so it can be fed back into a correction request. |
| `attribution` | enum `LOCAL` \| `ACCUMULATED` | Whether the violation is attributable to artifacts of the current stage or only to the accumulated set. Drives FR-006. |
| `contributing_sources` | list of strings | Every validator that reported this violation, after deduplication. |

Validation rules:
- Deduplicated by `(artifact_path, rule_id)`, retaining the **most severe** severity and unioning `contributing_sources` (research D4).
- A violation with `attribution = ACCUMULATED` MUST NOT cause the current stage's artifacts to be rejected (FR-006); it is recorded and surfaces at session level.

**Behavior-change note**: because of the conservative severity merge, a Lombok-prohibition violation is blocking under the merged verdict where the test-analysis validator alone would have rated it MEDIUM. This tightens the gate and can convert previously-completing sessions into blocked ones. It is intended, and it is why SC-011 must be read as an absolute ≤ 15% ceiling against which this merge counts directly ([research.md](research.md) D14).

### 3.7 `CorrectionAttemptRecord`

| Field | Type | Notes |
|---|---|---|
| `attempt_ordinal` | integer, 1 or 2 | 1-based. The initial request is not a correction attempt. |
| `request_digest` | hex string | Digest of the request issued, to detect duplicate identical retries. |
| `response` | text | The model's response, retained. |
| `verdict` | `ComplianceVerdict` | The verdict that rejected this attempt. |
| `outcome` | `StageOutcome` | |
| `timestamp` | datetime | |

Validation rules:
- `attempt_ordinal` MUST NOT exceed 2; a third record is a budget violation and MUST fail loudly rather than be appended.
- Records MUST be retained when the session terminates in the human-intervention state (FR-011).
- A record whose `request_digest` equals its predecessor's SHOULD be flagged: an identical request producing an identical rejection indicates the correction feedback was not actually incorporated.

### 3.8 `StageJournalEntry`

| Field | Type | Notes |
|---|---|---|
| `stage` | `StageName` | |
| `outcome` | `StageOutcome` | |
| `initial_verdict` | `ComplianceVerdict`, optional | Absent when the first response passed. |
| `correction_attempts` | ordered list of `CorrectionAttemptRecord` | 0..2. |
| `persisted_artifact_paths` | list of strings | Empty when the stage did not persist. |
| `request_count` | integer | 1 or 2 or 3. Feeds the session budget. |
| `duration_ms` | integer | |

### 3.9 `GenerationJournal`

| Field | Type | Notes |
|---|---|---|
| `session_id` | string | |
| `generation_mode` | `GenerationMode` | Duplicated here for export self-containment. |
| `instruction_set_revision` | short hex string | Denormalized for the same reason. |
| `provider` | string, optional | Absent in `DETERMINISTIC` mode. |
| `model` | string, optional | Absent in `DETERMINISTIC` mode. |
| `entries` | ordered list of `StageJournalEntry` | In execution order. |
| `total_requests` | integer | Sum of `request_count`. MUST be ≤ 15. |

Validation rules:
- `total_requests` MUST NOT exceed 15 (5 stages × (1 initial + 2 corrections)).
- MUST NOT contain credentials, tokens, or API keys. Provider and model identifiers only.
- MUST be retained in full on human-intervention termination.

### 3.10 `GenerationProvenanceRecord`

| Field | Type | Notes |
|---|---|---|
| `artifact_path` | string | |
| `stage` | `StageName` | |
| `generation_mode` | `GenerationMode` | |
| `provider` | string, optional | |
| `model` | string, optional | |
| `instruction_set_revision` | short hex string | |
| `attempt_ordinal` | integer | 0 for the initial request; 1–2 for a corrected one. Makes it visible when an artifact came from a corrected attempt. |
| `created_at` | datetime | |

Validation rules:
- For `MODEL` sessions, `provider`, `model`, and `instruction_set_revision` MUST all be present (SC-006).
- For `DETERMINISTIC` sessions, `instruction_set_revision` MAY be present for reference; `provider` and `model` MUST be absent rather than filled with placeholders, so that offline sessions are not miscounted as model-generated.
- MUST NOT contain credentials.

---

## 4. Session State Extensions (additive)

The existing generation state is extended — not restructured — with:

| Field | Type | Purpose |
|---|---|---|
| `generation_mode` | `GenerationMode` | Set once at session start; read by every stage invocation. |
| `instruction_set_revision` | short hex string | Denormalized for provenance stamping. |
| `generation_journal` | `GenerationJournal` | Correction history and per-stage outcomes. |
| `artifact_provenance` | list of `GenerationProvenanceRecord` | Per-artifact attribution. |

All four are optional in the state type so that states constructed by existing callers continue to type-check. The seam treats a missing `generation_mode` as a defect and fails loudly rather than guessing — guessing would risk silently running a session in the wrong mode.

**Explicitly unchanged**: the structural fields the rest of the platform depends on — the generated-artifact map, the log list, the workspace path, the repair-attempt counter, and the diagnostic field — keep their existing names and semantics (FR-021). The correction budget lives in the journal, **not** in the repair-attempt counter (FR-009).

---

## 5. State Transitions

### 5.1 Session start

```text
[credentials present, no explicit override]
        │
        ├── model client constructible? ──yes──► generation_mode = MODEL
        └── no ─────────────────────────────────► generation_mode = DETERMINISTIC

[explicit deterministic/offline selection] ─────► generation_mode = DETERMINISTIC
```

The mode is written to session state before the first stage runs, so it is available to every stage and to provenance recording.

### 5.2 Per-stage execution

```text
DETERMINISTIC ──► run retained implementation ──► persist ──► StageOutcome.SUCCEEDED

MODEL ──► request ──► extract
              │
              ├── extraction failed ──► attempt consumed ──┐
              │                                             │
              └── extracted ──► validate                     │
                     │                                      │
                     ├── passed ──► persist ──► SUCCEEDED    │
                     │                                      │
                     └── blocking LOCAL violation ──► attempt consumed
                                                                 │
                    ┌────────────────────────────────────────────┘
                    │
                    ├── attempts remaining (1st or 2nd) ──► re-request with
                    │                                        violations fed back
                    │
                    └── 2 attempts exhausted ──► StageOutcome.EXHAUSTED
                                                  ──► session BLOCKED
                                                      (same terminal state as
                                                       repair-loop exhaustion)
```

Critical invariants:
- `ACCUMULATED`-attribution violations never trigger a re-request (FR-006).
- The session never transitions from `MODEL` to `DETERMINISTIC`.
- Exhaustion sets the **same** terminal status the repair loop already sets (FR-010), so the existing human-intervention path applies unchanged.
- The journal is written on every exit path, including exhaustion (FR-011).

### 5.3 Terminal statuses

| Condition | Terminal status | Journal retained |
|---|---|---|
| All stages persisted, verification reached | Existing success status | Yes |
| Generation correction budget exhausted | Same status the repair loop sets on exhaustion | Yes, with all attempts |
| Repair loop exhausted (existing behavior) | Unchanged | Unchanged |
| Offline session, deterministic path | Unchanged from today | Yes, marked `DETERMINISTIC` |

---

## 6. Relationships Summary

| From | To | Cardinality | Notes |
|---|---|---|---|
| `GenerationSession` | `GenerationJournal` | 1 : 1 | Additive extension. |
| `GenerationJournal` | `StageJournalEntry` | 1 : 5 | One per stage, execution order. |
| `StageJournalEntry` | `CorrectionAttemptRecord` | 1 : 0..2 | Bounded by FR-008. |
| `StageJournalEntry` | `ComplianceVerdict` | 1 : 0..3 | One initial plus up to two rejection verdicts. |
| `ComplianceVerdict` | `ComplianceViolation` | 1 : 0..n | |
| `GenerationStage` | `InstructionDocument` | 1 : 1 | Five stages, five documents, one shared revision. |
| `GenerationSession` | `GenerationProvenanceRecord` | 1 : 0..n | One per persisted artifact. |
| `CorrectionAttemptRecord` | `GenerationProvenanceRecord` | 1 : 0..n | Only the accepted attempt produces provenance. |

---

## 7. Invariants to Enforce

1. A session's `generation_mode` never changes after session start.
2. `total_requests` ≤ 15 per session.
3. `correction_attempts` length ≤ 2 per stage.
4. A session in `MODEL` mode either persists artifacts that passed validation, or blocks. It never persists an unvalidated artifact and never falls back.
5. Every persisted artifact in a `MODEL` session has exactly one provenance record.
6. No journal, provenance record, instruction, or generated artifact contains a credential.
7. The correction budget and the repair-attempt counter are independent; neither is read or written by the other's logic.
8. A `DETERMINISTIC` session's artifact output is equivalent to the pre-migration baseline for the same blueprint.
