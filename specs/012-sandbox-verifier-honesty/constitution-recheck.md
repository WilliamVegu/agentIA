# Constitution Check — feature 012 (Sandbox Verifier Honesty)

Companion to [plan.md](plan.md) § Constitution Check. Records the gate evaluation, the deliberate branch exception, and the status update to SC-003.

---

## 1. Gate evaluation

All six principles are satisfied. **Two of them are satisfied by repairing a pre-existing violation rather than by adding an obligation.**

| Principle | Bearing | Verdict |
| --- | --- | --- |
| I. Arquitectura en Capas Estricta | None. Layering is a property of generated code, untouched. | **PASS** |
| II. Contratos Inmutables y Validación Temprana | None. DTO shape and validation untouched. | **PASS** |
| III. Manejo Centralizado de Excepciones y Limpieza de Código | The unified fallback policy removes four duplicated substitution blocks in favour of one. Purely additive fields keep every existing construction valid, so no dead code is introduced. | **PASS** |
| IV. Determinismo Offline-First y Aislamiento en Sandbox | **Currently violated, repaired here.** The Principle requires builds and tests to actually run offline inside isolated containers. A synthetic success reports that this happened when it did not, so the guarantee is unverifiable. Honest failure is what makes the Principle checkable. Detection stays offline (no image-manifest probe), as the Principle requires. | **PASS (restored)** |
| V. Quality Gates y Ciclo Acotado de Auto-Reparación | **Currently violated, partially repaired.** The Principle requires 100% Maven test passage as the approval gate with zero failures permitted; the hardcoded 5/5 synthetic count satisfies it with no tests executed. This feature stops the synthetic *outcome*, so those counts can no longer be attached to a build that did not run. **Residual: the hardcoded counts themselves remain**, explicitly out of scope. The repair cap drift (constitution 3, configured 5) is pre-existing and untouched. | **PASS (partially restored; residual recorded)** |
| VI. Seguridad de Secretos y Frontera del Orchestrator | No network calls added; the daemon and subprocess are faked in every test. No credential introduced. The change stays in the verification layer and does not enter the generated artifact's dependency surface. | **PASS** |

**Gate verdict**: all six principles satisfied. **No Complexity Tracking entries required** — nothing is introduced that needs justifying; complexity is removed.

**Recorded residual**: the hardcoded synthetic test counts (5/5) survive this change. They are now reachable only through a permitted substitution, so they can no longer produce a false *gate passage* for a build that never ran. Correcting the counts is a separate change and was declared out of scope by the specification. This is recorded rather than silently accepted.

---

## 2. Deliberate exception — branch isolation

**Decision**: feature 012 is implemented on `feature/011-llm-generation-nodes`, **not** on its own branch.

**Convention being departed from**: each feature normally gets its own branch so that review and merge boundaries align with feature boundaries.

**Rationale — the requirement the convention protects is preserved.** The convention exists to guarantee that the integration branch (`main`) is never modified by in-progress work. That guarantee holds here:

- `main` is untouched. Neither feature has merged.
- Features 011 and 012 form a single stacked change in one arc. 012 fixes a defect that 011's own Phase 6 verification uncovered (`sandbox_node.py` and `docker_runner.py` were verified byte-identical during 011's T046, and the synthetic-success fallback was reported there as a HIGH-severity pre-existing finding).
- The two share a review boundary: 012's honesty fix is what makes 011's measurement claims (SC-005, SC-011) meaningful, so reviewing them separately would require reviewing 011's figures twice.
- Splitting the stack now would produce two branches whose individual test suites are not independently green: 012 changes `test_docker_runner.py`, and 011's measurement harness consumes the verifier's result. Neither is a self-contained merge unit at this point.

**Risk accepted, and its mitigation**: a single branch carries two features' worth of review surface. Mitigation is that the commits are already separable and ordered — 011's work is committed (culminating in `a7ef45d`) before 012's spec and plan (`c435dbb`) — so the two can still be reviewed commit-by-commit or split later if required.

**Reversal**: if a separate branch is preferred before implementation, create it now, before any 012 source change. Nothing in this feature depends on the branch name.

---

## 3. Status update — SC-003 is now testable

Recorded here because it changes a gate-relevant assumption, not just a convenience.

**Previous position**: SC-003 (runtime present, warmed cache → real build, `fallback_used = False`) was recorded as deferred, because the container runtime on the development host refused to initialise.

**Current position**: SC-003 is **testable on this host**. The runtime now works — the user socket is listening, `docker run` against the build image succeeds, an offline build with a passing test reports success and one with a failing test reports failure, and the cache contains `surefire-junit-platform-3.1.2.jar`. The passing/failing pair is the substance of SC-003: it proves the verifier can still distinguish a real pass from a real fail once the synthetic path is closed.

**The remaining variable is the invoking shell.** The runtime writes into its state directory before serving any request; under a restricted file sandbox that path is read-only, every `docker` invocation fails, and the reachability check reports the daemon as unavailable. That is a property of the sandbox, **not** of the host.

**Constitutional reading**: this is Principle IV's own standard applied reflexively. The feature exists because a result must not be asserted without being observed. The same holds for the feature's own verification — an implementer whose shell cannot reach the runtime must report SC-003 as **not verified by me** and have it verified from a capable shell. It must never be marked satisfied from a second-hand report.

No principle is implicated by this update; it changes what evidence is obtainable, not what the feature must do.

---

## 4. Post-design re-check

Re-evaluated after Phase 1 design. **Verdict unchanged: all six principles satisfied.** The design decisions that carry constitutional weight are assessed in [plan.md](plan.md) § Post-Design Constitution Re-Check. The two that matter most:

- **Detection stays output-derived** (no image/cache probe), because a probe would reintroduce network dependence into a step Principle IV requires to run with `--network none`.
- **An unverifiable session bypasses the repair loop**, because no code patch fixes a missing daemon and entering repair would spend Principle V's bounded budget on an environment fault. The route already exists, so the repair loop's behavior is untouched.
