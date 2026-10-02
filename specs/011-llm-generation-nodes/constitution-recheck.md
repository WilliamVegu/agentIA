# Post-implementation Constitution Check — feature 011

Task: T044. This is the **re-evaluation** required by the last item of Phase 4 in
[plan.md](plan.md) ("Re-evaluate the Constitution Check post-implementation,
confirming that the Principle V scope recorded in research.md D12 still holds and
that no new principle is implicated").

It **confirms** the recorded decision. It does **not** re-open it.

---

## 1. Principle V scope — settled by D12, re-confirmed here

**Decision: Principle V's autonomous-correction cap is build-repair-scoped, not
session-wide. No amendment is required.**

The citation is [research.md](research.md) **D12 — "Principle V scope: build-repair
loop only"**. Its reasoning, restated for the record:

Principle V specifies its autonomous correction budget with two binding
constraints:

| D12 element | Constitution's wording | Generation-stage correction loop |
| --- | --- | --- |
| Trigger | "fallos de compilación o aserción en pruebas" | a **compliance verdict** |
| Guidance source | "exclusivamente el stack trace emitido por Maven" | the **constitutional violation set** |

Neither condition matches. The generation-stage correction loop is therefore not
an *"iteración de corrección automática"* in Principle V's sense: it sits outside
the Principle's scope **by construction**, from the Principle's own wording rather
than from an interpretation placed on it.

**This question is closed.** Do not re-open it, and do not read the presence of a
second counter as an unamended Principle V conflict.

### What the implementation must show for D12 to keep holding

D12 is a scoping argument; it only stays true if the two budgets remain genuinely
separate. That is enforced by FR-009/FR-010 and was verified:

| Claim | Evidence |
| --- | --- |
| The generation correction cap is **2** per stage, distinct from the repair cap | `journal.MAX_CORRECTION_ATTEMPTS == 2`, enforced and tested |
| The generation loop never reads or writes `repair_attempts` | `runner.py` contains no reference to it; T035 drives the repair loop *after* a generation exhaustion and shows it still takes its first attempt on a full budget |
| Budget exhaustion and repair exhaustion reach the **same** terminal state | Both use `SessionStatus.BLOCKED` / `SessionPhase.FAILED`; T035 reads those from the live enum and from `repair_node` itself |
| The two counters have different triggers and units | Repair = one Maven stack trace → one surgical patch; generation = one compliance verdict → one stage's artifact set |

The pre-existing **repair-cap drift** (the constitution says 3; `config.py` says 5)
is a measurement confound for SC-011, not a Principle V conflict, and is recorded
as such in the risks table in [plan.md](plan.md) and in
[reports/measurements/011-sc011-intervention-rate.md](../../reports/measurements/011-sc011-intervention-rate.md).

---

## 2. All six principles — post-implementation assessment

| # | Principle | Post-implementation assessment | Verdict |
| --- | --- | --- | --- |
| I | Arquitectura en Capas Estricta | Layering is enforced at the gate (Family A/B), not merely by prompt instruction. Fault injection at the model boundary proves a controller importing a repository is rejected with zero artifacts persisted. | **PASS** |
| II | Contratos Inmutables y Validación Temprana | DTOs are records; a request contract emitted as a class is rejected. Declared validation constraints now reach the generated entity, which is the SC-001 gain. | **PASS** |
| III | Manejo Centralizado de Excepciones y Limpieza de Código | The whole-project error-handler rule is **ACCUMULATED**: it is recorded against the stage but never charges a correction attempt, because no single stage can satisfy it (FR-006). It is still surfaced at session level by the project audit, so the omission is not lost. | **PASS** |
| IV | Determinismo Offline-First y Aislamiento en Sandbox | Offline behavior is unchanged: the `DETERMINISTIC` path runs with no gate and `request_count = 0` (FR-013), and the pre-existing suite passes unchanged. The gate asymmetry is deliberate and documented at the point of use (T043). | **PASS** |
| V | Quality Gates y Ciclo Acotado de Auto-Reparación | Satisfied **by construction** under [research.md](research.md) D12 — see §1. The generation budget is bounded at 15 requests/session and the counters are independent. | **PASS (by construction — D12)** |
| VI | Seguridad de Secretos y Frontera del Orchestrator | No credential appears in the journal, provenance, or generated artifacts; the session key stays confined to the field that carries it to the client. The seam lives under `backend/app/orchestrator/` and does not enter the generated artifact's dependency surface. No network call to a model provider occurs in the test suite. | **PASS** |

---

## 3. New principles implicated?

**None.** Nothing discovered during implementation raises a principle that the
pre-design or post-design gates did not already consider. The two Complexity
Tracking entries recorded at the pre-design gate remain the only ones; no entry was
added at either the post-design or this post-implementation re-check.

---

## 4. Verdict

**Gate verdict unchanged: all six principles satisfied.** Principle IV's
justification is recorded, Principle V is satisfied by construction under the scope
settled in [research.md](research.md) D12, and no amendment is required.

The Principle V scope question is **settled**. It is cited, not re-opened.
