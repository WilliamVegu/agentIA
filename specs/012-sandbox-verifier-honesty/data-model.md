# Phase 1 Data Model — Sandbox Verifier Honesty

The feature changes four existing entities and adds no new one. Every change is additive; no field is removed, retyped, or repurposed.

---

## 1. Verification Result

The outcome of attempting to build and test a workspace. Represented by `DockerExecutionResult` in `backend/app/sandbox/docker_runner.py`.

| Field | Type | Default | Change | Notes |
| --- | --- | --- | --- | --- |
| `exit_code` | `int` | — | unchanged | Authoritative success/failure signal. `0` only when a build genuinely ran and passed. |
| `stdout` | `str` | `""` | unchanged | Captured build output. Empty when a substitution occurred and the substitution was not permitted. |
| `stderr` | `str` | `""` | unchanged | Captured error output. |
| `duration_ms` | `int` | `0` | unchanged | Wall-clock duration of the attempt. |
| `fallback_used` | `bool` | `False` | **NEW** | Whether a synthetic result was substituted for a real build. The discriminator every consumer branches on. |
| `fallback_reason` | `Optional[str]` | `None` | **NEW** | Why the substitution happened. Carried into the session's recorded reason. |
| `matched_pattern` | `Optional[str]` | `None` | **NEW** | The recognised output pattern that triggered an environment classification. Set only for trigger 4. |
| `attribution_ambiguous` | `bool` | `False` | **NEW** | Whether the cause could be an environment fault *or* a project-authoring error. Set only for trigger 4. |

**Derived predicate** (existing, unchanged): `is_success == (exit_code == 0)`.

**Validation rules**

- `exit_code == 0` implies the build ran. If `fallback_used` is `True` and the substitution was **not** permitted, `exit_code` MUST be non-zero — a substitution may never report success in honest mode.
- `fallback_used == True` implies `fallback_reason` is set.
- `matched_pattern` is set only when `attribution_ambiguous` is `True`, and vice versa. Both are unset for triggers 1–3, which are unambiguous environment faults.
- `stderr`/`stdout` MUST NOT contain the synthetic `BUILD SUCCESS` text when `fallback_used == True` and the substitution was not permitted.

**State transitions**

```text
attempt verification
├── daemon reachable + build runs
│   ├── exit 0                      → verified and passed        (fallback_used=False)
│   └── exit != 0, no env pattern   → verified and FAILED        (fallback_used=False)  → repair
└── cannot verify (any of 4 triggers)
    ├── fallback PERMITTED          → synthetic success          (fallback_used=True, exit 0)
    └── fallback NOT permitted      → could not verify           (fallback_used=True, exit != 0) → BLOCKED
```

The three outcomes the specification requires — "verified and passed", "verified and failed", "could not verify" — map to the three terminal leaves. The first two are distinguished by `exit_code` with `fallback_used == False`; the third by `fallback_used == True`.

---

## 2. Verification Metrics

The summarised test outcome attached to a session. Represented by `VerificationMetrics` in `backend/app/models/artifact.py`.

| Field | Type | Default | Change |
| --- | --- | --- | --- |
| `totalTests` | `int` | `0` | unchanged |
| `passedTests` | `int` | `0` | unchanged |
| `failedTests` | `int` | `0` | unchanged |
| `executionDurationMs` | `int` | `0` | unchanged |
| `allPassed` | `bool` | `False` | unchanged |
| `surefireReport` | `Optional[dict]` | `None` | unchanged |
| `fallback_used` | `bool` | `False` | **NEW** — mirrors the result so consumers can branch on the payload alone |
| `fallback_reason` | `Optional[str]` | `None` | **NEW** — lets an operator diagnose without reading logs |

**Validation rules**

- `allPassed == True` **and** `fallback_used == True` is a legal combination, but only in permissive mode. It means "reported as passing without verification", and FR-008 requires such records be excluded from figures.
- The test counts remain the pre-existing hardcoded values when `fallback_used == True` (explicitly out of scope to correct). After this feature they can only ever be attached to a substitution that was **permitted**, never to a build that did not run.

---

## 3. Session Record

Represented by `GenerationSessionDB` in `backend/app/models/session.py`.

| Field | Change |
| --- | --- |
| `verification_metrics_json` | **NEW** — `Text`, nullable. Holds the serialized `VerificationMetrics`, including `fallback_used`. |

**Migration**: registered through the existing idempotent `_ensure_generation_columns()` helper, which runs `PRAGMA table_info`, issues `ALTER TABLE ... ADD COLUMN` only when absent, and swallows exceptions. Purely additive, so an existing `studio.db` picks up the column with no migration tool — the pattern established by feature 011's T013.

**Why a column rather than a derived value**: `test_metrics` currently lives only in the in-process agent state and is lost when the process ends. The session detail endpoint reads from the database, so the marking must be persisted for FR-005's detail-endpoint exposure to survive a restart.

---

## 4. Session Detail Response

Represented by `GenerationSessionDetail` in `backend/app/models/session.py`, consumed by `GET /api/v1/sessions/{session_id}`.

| Field | Type | Alias | Change |
| --- | --- | --- | --- |
| `verification_fallback_used` | `bool` | `verificationFallbackUsed` | **NEW** — defaults to `False` when no metrics were persisted |

The field is optional-with-default so every existing client keeps working and no response becomes invalid. The alias follows the model's established `camelCase` convention.

---

## 5. Agent State

Represented by `GenerationAgentState` in `backend/app/orchestrator/state.py`.

| Key | Type | Change | Purpose |
| --- | --- | --- | --- |
| `verification_fallback_used` | `bool` | **NEW (optional)** | Lets downstream nodes and the API see the marking without re-reading metrics |
| `error` | `str` | unchanged key | **Set by `sandbox_node`** when a substitution was not permitted. This is the key `routes_session` persists into `error_message`. |

---

## 6. Measurement Figure

Not a stored entity, but the contract FR-008 governs. Every published compliance, quality, intervention-rate, or cost figure is computed over a **filtered** session set:

```text
eligible(sessions) = { s | s.verification_fallback_used == False }
```

**Validation rules**

- A fallback-marked session is excluded **whether or not** it reached the verified state. This is the point of the filter: permissive mode lets such sessions reach `VERIFIED` (Q1), so the terminal state cannot be the discriminator.
- The excluded count MUST be recorded alongside any published figure, so the filter is auditable rather than invisible.

---

## Entity relationship summary

```text
DockerExecutionResult ──(1:1)──▶ VerificationMetrics ──(persisted)──▶ SessionRecord
        │                                  │                                │
        │ fallback_used                    │ fallback_used                  │ verification_fallback_used
        │                                  ▼                                ▼
        └──▶ AgentState.error        measurement figures            Session detail response
             (BLOCKED reason)        (excluded when True)           (exposed to client)
```

No entity is removed. No relationship changes cardinality. The four `fallback_used` occurrences are the *same fact* propagated along the verification path, and each surface exists because a distinct consumer cannot reach the previous one — a design constraint, not duplication.
