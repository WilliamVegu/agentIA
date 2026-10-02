# Contract — Verification Observability

**Feature**: 012-sandbox-verifier-honesty · **Implements**: FR-003, FR-005, FR-008

The honest outcome is only actionable if it is observable. This contract defines the three surfaces that must expose the fallback marking, and why each is needed.

---

## 1. Why three surfaces

The marking is one fact, but no single surface can serve all three consumers:

| Consumer | Surface | Why this surface and not another |
| --- | --- | --- |
| Internal branch logic, measurement harness | **Metrics payload** (`VerificationMetrics`) | Travels with the session through the agent state; available before any persistence |
| Human investigating a finished session | **Session detail endpoint** | Survives process restart; reads from the database |
| Operator watching a session live | **Live event stream** | The session may not be finished, so no database row is yet trustworthy |

Duplicating the fact across three surfaces is deliberate. Each exists because its consumer cannot reach the previous one.

---

## 2. Surface 1 — Verification metrics payload

`VerificationMetrics` MUST carry:

| Field | Type | Default |
| --- | --- | --- |
| `fallback_used` | `bool` | `False` |
| `fallback_reason` | `Optional[str]` | `None` |

**Contract**

- The values MUST mirror the verification result that produced them. A metrics payload claiming `fallback_used = False` for a result that substituted MUST NOT be constructible by the normal path.
- `allPassed = True` together with `fallback_used = True` is legal **only** in permissive mode. It means "reported passing without verification".
- The field is optional-with-default so every existing construction remains valid.

---

## 3. Surface 2 — Session detail endpoint

`GET /api/v1/sessions/{session_id}` → `GenerationSessionDetail` MUST expose:

| Field | Type | Alias | Default when unknown |
| --- | --- | --- | --- |
| `verification_fallback_used` | `bool` | `verificationFallbackUsed` | `False` |

**Contract**

- The value MUST be readable after a process restart. It is persisted through the additive `verification_metrics_json` column, not held only in memory — the in-process state is lost on restart, and an operator investigating a suspicious past session is exactly the case that must work.
- Absent or unparseable persisted metrics MUST degrade to `False` **without raising**. A detail request must never fail because verification metadata is missing; a missing marking is a data gap, not a server error.
- The response shape stays backward compatible: the field is additive and optional, so no existing client breaks.

**Deliberately not included**: the `fallback_reason` free text is carried in `error_message` for blocked sessions rather than duplicated into the detail response. The detail view answers "was this verified?"; the recorded reason answers "why not?" and already has a home.

---

## 4. Surface 3 — Live event stream

The session event stream MUST include the fallback marking for the verification step.

**Contract**

- The marking MUST be observable **before** the session reaches a terminal state, because the whole point of a live surface is the session that has not finished.
- In default mode, a substitution is accompanied by a `BLOCKED` terminal state, so a client watching the stream learns both that verification could not run and that human intervention is required.
- In permissive mode the session may proceed to `VERIFIED`; the stream is then the **only** place a watcher can learn that the verification was synthetic. This is precisely why the stream cannot be omitted from FR-005.
- The marking MUST NOT be inferable only from free-text log lines. A structured field is required, so a machine consumer can branch without parsing.

---

## 5. Surface 4 — Session terminal state (FR-003)

Not an observability surface, but it is the outcome the surfaces report.

| Condition | Terminal status | Phase | Recorded reason |
| --- | --- | --- | --- |
| Substitution fired, **default** mode | `BLOCKED` | `FAILED` | set — states verification could not be performed |
| Substitution fired, **permissive** mode | `COMPLETED` (existing behavior) | `VERIFIED` | not required (no failure) |
| Real build passed | `COMPLETED` | `VERIFIED` | — |
| Real build failed | unchanged — enters the repair loop | — | — |

**Contract**

- A session MUST NOT reach the verified state with a fallback-marked result **in default mode**. This is FR-003.
- In permissive mode the session MAY reach the verified state (Q1, Option A). The terminal state therefore no longer proves verification occurred, which is why **the marking — not the status — is load-bearing** for every downstream figure.
- Reason wording MUST identify that verification could not be performed. It MUST NOT read as a test or compilation failure, which would misattribute an environment fault to the generated code.
- For an ambiguous condition-4 substitution, the recorded reason MUST NOT assert a container problem as fact. It states that the build did not complete verifiably and records the matched pattern; deciding whether the cause was the environment or the project remains a human judgement.

---

## 6. Surface 5 — Measurement figures (FR-008)

Every published compliance, quality, intervention-rate, or cost figure MUST be computed over sessions whose verification did **not** use a fallback.

**Contract**

- The filter is `verification_fallback_used == False`, applied **regardless of terminal state**. A permissive-mode session that reached `VERIFIED` via substitution MUST be excluded — the status cannot be the discriminator precisely because permissive mode allows it.
- Every published figure MUST record how many sessions were excluded. A silent filter is its own honesty problem: the reader must be able to see that the population was trimmed and by how much.
- This obligation applies to any consumer publishing such a figure, not only to the measurement harness that implements it first.

---

## 7. Summary of required surfaces

| # | Surface | Field | Requirement |
| --- | --- | --- | --- |
| 1 | Metrics payload | `fallback_used` | FR-005 |
| 2 | Session detail endpoint | `verification_fallback_used` | FR-005 |
| 3 | Live event stream | fallback marking, structured | FR-005 |
| 4 | Terminal state + recorded reason | `BLOCKED` / `FAILED` | FR-003 |
| 5 | Published figures | exclusion filter + excluded count | FR-008 |
