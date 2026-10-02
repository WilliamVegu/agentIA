# Constitution Check — feature 014 (SkillOpt Compact)

Companion to [plan.md](plan.md) § Constitution Check. Records the gate evaluation, the branch exception for a **fourth** stacked feature, and the two v1 residuals.

---

## 1. Gate evaluation

All six principles are satisfied. **No Complexity Tracking entries are required.**

| Principle | Bearing | Verdict |
| --- | --- | --- |
| I. Arquitectura en Capas Estricta | None directly. Worth noting the coincidence: the seed skill *documents* this principle. The feature optimises a document about layering; it does not generate code and does not enforce layering itself. | **PASS** |
| II. Contratos Inmutables y Validación Temprana | None. No DTO or API contract changes. | **PASS** |
| III. Manejo Centralizado de Excepciones y Limpieza de Código | One applier, one gate, one collector. Every branch is exercised: each edit operation, each rejection reason, each gate outcome, and the failure path that still writes a run record. | **PASS** |
| IV. Determinismo Offline-First y Aislamiento en Sandbox | The gate's pass rule **depends** on this principle: it reads a real offline build result, never a terminal status. Held-out rotation is deterministic from the iteration's identity, so a re-run reproduces the selection. | **PASS** |
| V. Quality Gates y Ciclo Acotado de Auto-Reparación | **Directly implicated.** This feature *is* a gate — for a document rather than for code. It borrows the principle's discipline: accept only on a strict improvement, never accept a result that was not genuinely verified, and bound the size of an update. | **PASS** |
| VI. Seguridad de Secretos y Frontera del Orchestrator | The reflector calls the model factory directly, so the credential path is the same one generation already uses; no key reaches a skill, a run record, or a log. The loop runs on the orchestration side and adds nothing to the generated artifact's dependency surface. The automated suite makes zero provider calls. | **PASS** |

### A note on Principle V, recorded because it is unusual

The feature extends the principle's **spirit** to a new object without changing its **scope**. Principle V governs generated code passing Maven tests; this governs a skill document passing a held-out score. No amendment is required and none is proposed. The two mechanisms that make the analogy exact are both in the design:

- **Strict acceptance.** A tie is rejected, exactly as "cero pruebas fallidas permitidas" admits no partial pass.
- **A bounded update.** The four-edit cap is the same instinct as the three-iteration repair cap: an unbounded change cannot be attributed to anything, and cannot be reasoned about afterwards.

---

## 2. Deliberate exception — branch isolation, fourth stacked feature

**Decision**: feature 014 is implemented on `feature/011-llm-generation-nodes`, which already carries 011, 012 and 013. **No dedicated branch.**

**Convention being departed from**: each feature normally gets its own branch so review and merge boundaries align with feature boundaries.

**Rationale — the requirement the convention protects is preserved.** That requirement is that the integration branch (`main`) is never modified by in-progress work, and it holds:

- **`main` is untouched.** None of the four features has merged.
- **One arc.** 011 built the generation stages and the stage execution boundary; 012 made the sandbox verifier honest; 013 measures what the generation calls cost; 014 improves the skill those calls are made with. Each is a direct consequence of the one before.
- **The isolation benefit of splitting is zero.** Nothing merges either way. Branching now would mean rebasing four features' commits to buy nothing.
- **Splitting would yield branches that are not independently green.** 014 reads 011's sessions, honours 012's verification-fallback marking in its pass rule, and reuses 013's side-channel-with-best-effort-write pattern for its run record. A branch carrying 014 alone would not have a passing suite, which makes it a worse review unit, not a better one.

**One property specific to 014, in the other direction**: it is the most self-contained of the four. With no active skill present it does not change generation behaviour **at all** — the request is byte-identical to the pre-feature rendering (SC-005). So unlike 011–013, its presence cannot regress the earlier features' behaviour.

**Risk accepted, and its mitigation**: one branch now carries four features' worth of review surface. Mitigation is that the commits remain separable and ordered by feature — 011 culminates at `a7ef45d`, 012 at `fbe39d6`, 013 at `e9bb8dd`, and 014's specification and plan follow — so the stack can still be reviewed commit-by-commit, and the features can be split retroactively if required.

**Reversal**: a dedicated branch can still be created before 014's implementation begins. Nothing in the feature depends on the branch name.

This follows [012's exception](../../012-sandbox-verifier-honesty/constitution-recheck.md) §2 and [013's](../../013-cost-tracing/constitution-recheck.md) §2 for the first three features of the arc.

---

## 3. Two residuals, recorded rather than accepted

Both are deliberate v1 boundaries, named in the specification's Out of Scope and here so that neither reads as an oversight.

### 3.1 No statistical validation

The gate compares two pass rates with no significance test, on a **five-task exam where a single task moves the rate by 25 percentage points**. The gate is therefore coarse, and one execution's noise can decide an acceptance.

This is acceptable for a feature whose purpose is to validate the *loop*. It is **not** acceptable for a production optimiser, and the requirement to add significance testing travels with the deferred v2 work. Recorded in [contracts/gate.md](contracts/gate.md) §3.

### 3.2 No memory between runs

No rejected-edit buffer and no epoch state. A rejected edit is logged in the run record and then lost; the next iteration cannot learn from what was already tried and failed.

The source method treats that buffer as negative feedback that makes skill training converge rather than oscillate. Removing it is the point of the reduction — the loop is validated before the stability machinery is added — but the consequence is real: **v1 can repeat a failed edit indefinitely**, and nothing in the feature notices.

### 3.3 The one thing that is *not* a residual

Worth stating because it is the trap this feature was most likely to fall into: **a fallback-marked execution never counts as a pass**, even at exit code zero.

Under permissive mode a hermetic substitution returns success without compiling anything, so a gate scored on the exit code alone would reward a skill for making the verifier give up. A text optimiser will find that exploit, because "improve the score" is exactly what it is asked to do. Feature 012 established that a synthetic verification is not a successful generation; the same rule is enforced here ([research.md](research.md) D5, [contracts/gate.md](contracts/gate.md) §2). This is not deferred — it is a v1 requirement.

---

## 4. Post-design re-check

Re-evaluated after Phase 1 design. **Verdict unchanged: all six principles satisfied.**

The decisions carrying the most constitutional weight:

- **Disjointness is asserted in code, not argued in prose.** The structural argument — recorded sessions predate the candidate — holds today. The assertion is what keeps it holding when the code changes, because a future edit could leave the prose true while the code was false. Same reasoning as 013's decision to test the through-the-seam path rather than trust the design.
- **The runner is a parameter, not a monkeypatch.** The seam is explicit, so a refactor cannot silently stop injecting and leave the suite calling a provider.
- **Injection is a no-op on absence.** This is the first reader of a currently-empty directory, on the generation path. Absence is the normal state, not an error.
- **The paper's prompt text is not reproduced.** The prompt is written for this platform and records which contract it was adapted from, so nobody later mistakes a platform-specific prompt for the source's.

**No new violations. No Complexity Tracking entries added.**
