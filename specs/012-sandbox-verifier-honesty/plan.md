# Implementation Plan: Sandbox Verifier Honesty

**Branch**: `feature/011-llm-generation-nodes` (see Branch Note) | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/012-sandbox-verifier-honesty/spec.md`

## Summary

The sandbox verifier currently substitutes a synthetic `BUILD SUCCESS` (with fabricated 5/5 test counts) whenever it cannot actually build — daemon unreachable, docker binary missing, a runtime communication failure, or a build failure whose output matches an environment-looking pattern. Sessions therefore reach `VERIFIED` for workspaces that were never compiled, and every downstream measurement inherits that lie.

The approach: make the substitution an explicit, recorded event rather than a silent success. `DockerExecutionResult` gains a `fallback_used` marking plus the reason and the matched pattern; a single config switch (`ALLOW_HERMETIC_FALLBACK`, default **false**) decides whether the substitution is permitted; `sandbox_node` carries the marking into `VerificationMetrics` and, when the substitution was not permitted, terminates the session in `BLOCKED` **without entering the repair loop** (you cannot patch code to fix a missing daemon). The marking is then exposed through the metrics payload, the session detail endpoint, and the live stream.

Two design discoveries shape this plan and are recorded in [research.md](research.md):

1. **`graph.py` does not need to change.** `_route_after_sandbox` already returns `END` when `status == "BLOCKED"`, so a `BLOCKED` sandbox result already short-circuits the repair loop. This keeps feature 011's FR-023 boundary (repair loop out of scope) intact for free.
2. **`backend/tests/test_docker_runner.py` asserts the bug.** Three pre-existing tests require `exit_code == 0` and `"BUILD SUCCESS"` under exactly the conditions FR-001 says must now fail. They must be re-pointed at permissive mode. This is the one place the "pre-existing suite passes unchanged" expectation cannot hold, and it is called out explicitly rather than discovered during implementation.

## Technical Context

**Language/Version**: Python 3.12 (backend); generated artifacts are Java 21 / Spring Boot 3.2.3

**Primary Dependencies**: FastAPI, LangGraph, LangChain, pydantic-settings, SQLAlchemy + SQLite, pytest, anyio; `docker` CLI via `asyncio.create_subprocess_exec`

**Storage**: SQLite (`backend/studio.db`); new field persisted through the existing idempotent additive-column mechanism in `app/models/session.py` (`_ensure_generation_columns`), mirroring feature 011's T013

**Testing**: pytest (`backend/tests/`), run with `.venv/bin/python -m pytest`. Docker-dependent paths are faked with `monkeypatch` on `check_docker_daemon` and `asyncio.create_subprocess_exec` — no real daemon or network is required, satisfying Constitution Principle VI

**Target Platform**: Linux server; the verifier targets hermetic offline container execution (`mvn test -o`, `--network none`)

**Project Type**: Web service (FastAPI backend + web frontend) — this feature touches the backend verification path only

**Performance Goals**: No perf target. The change adds no I/O to the hot path; fallback detection reuses output already captured

**Constraints**: Offline-first (Principle IV) — the change must not introduce a network probe to detect a missing image or a cold cache, so detection stays derived from the build attempt's own output. No new network calls in tests (Principle VI). Existing offline generation path must be untouched (FR-004)

**Scale/Scope**: 1 config flag, 4 result fields, 1 metrics field, 1 session field, ~5 fallback call sites unified, 1 pre-existing test file updated, 2 new test files/cases. Small, surgical change

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

This feature is a **restoration** of two existing principles rather than a new obligation. The current behavior violates both.

| Principle | Bearing | Verdict |
| --- | --- | --- |
| **I. Arquitectura en Capas Estricta** | No effect. Layering is a property of generated code, untouched here. | **PASS** |
| **II. Contratos Inmutables y Validación Temprana** | No effect. DTO shape and validation are untouched. | **PASS** |
| **III. Manejo Centralizado de Excepciones y Limpieza de Código** | Requires no dead code and no unused bindings. The unified fallback factory removes duplicated substitution blocks rather than adding one. The synthetic-stdout constant stays in use (permissive mode still emits it). | **PASS** |
| **IV. Determinismo Offline-First y Aislamiento en Sandbox** | **Directly implicated — currently violated.** The Principle requires builds and tests to actually run offline inside isolated containers. A synthetic success reports that this happened when it did not, so the Principle's guarantee is unverifiable today. Making the failure honest is what allows Principle IV to be *checked* at all. Detection must stay offline (no image-manifest probe), which this plan does. | **PASS (restored)** |
| **V. Quality Gates y Ciclo Acotado de Auto-Reparación** | **Directly implicated — currently violated.** The Principle requires 100% Maven test passage as the approval gate, with zero failures permitted. The hardcoded 5/5 synthetic count satisfies that gate with no tests executed. This feature stops the synthetic *outcome*; the hardcoded counts remain (explicitly out of scope) but can no longer be attached to a build that did not run. The repair cap (constitution 3 vs configured 5) is pre-existing drift, tracked separately and **not** changed here. | **PASS (partially restored; count hardcoding deferred)** |
| **VI. Seguridad de Secretos y Frontera del Orchestrator** | Tests must make no network calls; none added (the daemon and subprocess are faked). No credential is introduced. The change stays in the orchestrator/verification layer and does not enter the generated artifact's dependency surface. | **PASS** |

**Gate verdict**: all six principles satisfied, two of them by repairing a pre-existing violation. **No Complexity Tracking entries required** — no violation is introduced and no new complexity is added; the change removes four duplicated substitution blocks in favour of one.

## Project Structure

### Documentation (this feature)

```text
specs/012-sandbox-verifier-honesty/
├── plan.md                          # This file
├── spec.md                          # Feature specification
├── research.md                      # Phase 0 output
├── data-model.md                    # Phase 1 output
├── quickstart.md                    # Phase 1 output
├── contracts/
│   ├── verification-result.md       # The result contract consumers branch on
│   └── verification-observability.md# Session detail + live stream exposure
├── checklists/
│   └── requirements.md              # Spec quality checklist (16/16)
└── tasks.md                         # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── config.py                          # + ALLOW_HERMETIC_FALLBACK flag
│   ├── sandbox/
│   │   └── docker_runner.py               # core change: unified fallback policy
│   ├── models/
│   │   ├── artifact.py                    # + VerificationMetrics.fallback_used
│   │   └── session.py                     # + additive column; detail exposes flag
│   ├── orchestrator/
│   │   ├── state.py                       # + verification_fallback_used key
│   │   └── nodes/
│   │       └── sandbox_node.py            # + propagate flag; BLOCKED on disallowed fallback
│   └── api/
│       └── routes_session.py              # + expose flag in detail and stream
└── tests/
    ├── test_docker_runner.py              # UPDATED: 3 tests re-pointed at permissive mode
    ├── test_sandbox_verifier_honesty.py   # NEW: default-config honest failure
    └── test_generation_stage_measurement.py  # UPDATED: filter on fallback_used=False (FR-008)

backend/app/orchestrator/graph.py          # UNCHANGED — see research.md D4
```

**Structure Decision**: The change is confined to the backend verification path. The existing `backend/app/sandbox/` package owns the subprocess/Docker concern, `backend/app/orchestrator/nodes/sandbox_node.py` owns the state transition, and `backend/app/models/` owns the two response contracts. No new package is introduced; no frontend change is required (the detail endpoint's new field is additive and optional).

**Branch Note — deliberate exception, recorded**: feature 012 stays on `feature/011-llm-generation-nodes`. Both features are a stacked change in one arc and neither has merged to `main`. No `before_specify` hook ran (`.specify/extensions.yml` is absent), so no branch was created. The isolation requirement that motivated per-feature branching — that `main` stays untouched until review — is preserved by the stack never merging partially. See [constitution-recheck.md](constitution-recheck.md) for the recorded exception.

## Phase 0 — Research

See [research.md](research.md). All Technical Context unknowns were resolved by direct inspection; there are no open `NEEDS CLARIFICATION` items. Key decisions: D1 config flag shape, D2 result field set, D3 unified fallback policy, D4 no `graph.py` change, D5 the `error` state key, D6 metrics field, D7 persistence mechanism, D8 measurement filtering, D9 the pre-existing test conflict.

## Phase 1 — Design

- [data-model.md](data-model.md) — the result, metrics, session, and state entities, with the field-level changes and the permitted state transitions.
- [contracts/verification-result.md](contracts/verification-result.md) — what a verification result must report, and the four substitution conditions that must honor it.
- [contracts/verification-observability.md](contracts/verification-observability.md) — how the marking reaches the metrics payload, the session detail endpoint, and the live stream.
- [quickstart.md](quickstart.md) — runnable validation for each success criterion, including the explicit SC-003 environment caveat.

### Post-Design Constitution Re-Check

*Re-evaluated after Phase 1 design.*

The gate verdict is **unchanged: all six principles satisfied**, with Principle IV and Principle V now *actually* enforceable rather than nominally satisfied.

| Design decision | Constitutional bearing | Assessment |
| --- | --- | --- |
| **`ALLOW_HERMETIC_FALLBACK` defaults to false** | Principle IV — honest offline verification | Correct. The safe behavior is the default and the unsafe behavior is an explicit operator opt-in, so no environment silently inherits synthetic verification. |
| **Detection stays output-derived; no image/cache probe** | Principle IV — offline-first, no network | Required. Probing a registry for image existence would introduce network dependence into a step the Principle requires to run with `--network none`. |
| **An unverifiable session goes straight to `BLOCKED`, bypassing repair** | Principle V — bounded self-repair | Correct and necessary. Entering the repair loop would spend repair attempts on an environment fault that no code patch can fix, and would misattribute the cause in the diagnostics. The route already exists (`_route_after_sandbox` returns `END` on `BLOCKED`), so the repair loop's behavior is untouched. |
| **The hardcoded 5/5 test counts remain** | Principle V — 100% test passage | **Deliberate, recorded.** Out of scope per the spec. The counts can no longer be attached to a build that did not run, which removes the false *gate passage*; correcting the counts themselves is a separate change. This is the one place the feature leaves a Principle V gap, and it is tracked as an explicit residual rather than silently accepted. |
| **The marking is recorded even in permissive mode** | Principles IV/V — auditability | Correct. Without it, permissive mode would be an audit blind spot, and FR-008's filtering would be impossible. |
| **Additive column reuse (no new table, no migration tool)** | Principle III — clean code; repo convention | Follows feature 011's T013 precedent exactly: purely additive, idempotent, and the existing mechanism already handles a missing column. |

**No new violations. No Complexity Tracking entries added.** One Principle V residual (hardcoded counts) is recorded above as explicitly deferred.

---

## SC-003 outcome (recorded 2026-09-28, task T026)

SC-003 requires a real build to run when a real runtime is present, with
`fallback_used = False`. Four cases were specified. **The outcome is recorded
below with the observer for each, because the observer matters.**

| # | Case | Expected | Observed | Observed by |
| --- | --- | --- | --- | --- |
| 1 | Real runtime, passing test | `exit=0`, `fallback_used=False` | `exit=0`, `fallback_used=False`, real Maven output | **Operator, manually from a capable shell** |
| 2 | Real runtime, failing test | `exit != 0`, `fallback_used=False` | `exit=1`, `fallback_used=False`, real Maven output | **Operator, manually from a capable shell** |
| 3 | Runtime mocked unreachable, default | `exit != 0`, `fallback_used=True`, reason = "the container runtime is not reachable..." | as expected | **Verified by the automated suite** |
| 4 | Runtime mocked unreachable, permissive | `exit=0`, `fallback_used=True` | as expected | **Verified by the automated suite** |

**Cases 3 and 4 are independently reproduced** by
`backend/tests/test_sandbox_verifier_honesty.py` (`test_trigger1_...`,
`test_permissive_mode_restores_the_legacy_outcome`,
`test_permissive_mode_still_records_the_marking`), which run in the default suite.

**Cases 1 and 2 were NOT independently observed by the implementer.** Their shell
could not reach the container runtime (the sandbox makes the runtime's state
directory read-only), so `docker info` failed and `check_docker_daemon()` returned
false. The evidence for those two cases is the operator's manual run, which is
recorded here as theirs rather than presented as an observation this feature made.
An opt-in test (`AGENTIA_RUN_REAL_SANDBOX=1`) encodes both cases so a capable
shell can reproduce them; in the implementer's shell it skips with that reason
stated in the skip message.

**SC-003 status: satisfied on the operator's evidence for the real-runtime half,
and independently verified for the mocked half.** The pass/fail pair in cases 1-2
is the substance of SC-003 -- it demonstrates the verifier still distinguishes a
real pass from a real fail once the synthetic path is closed -- and that is exactly
the half this environment could not observe directly.

