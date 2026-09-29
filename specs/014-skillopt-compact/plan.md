# Implementation Plan: SkillOpt Compact

**Branch**: `feature/011-llm-generation-nodes` (fourth stacked feature — see Branch Note) | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/014-skillopt-compact/spec.md`

## Summary

Close the smallest possible loop around a single skill document: prepend the active skill to every generation request, collect recent session outcomes, ask a model what the skill got wrong, apply **bounded** edits to a **copy**, and accept the result only on a **strict** improvement over a **held-out** score — with both the current and candidate skills scored in the same iteration on the same fresh executions.

Everything the source method uses to make skill training *stable* is deliberately absent: no rejected-edit buffer, no learning-rate schedule, no epoch-wise slow/meta update, no multi-skill bank, no significance test. [arXiv:2605.23904](https://arxiv.org/abs/2605.23904)'s abstract names those mechanisms as exactly what stability is made of, so the v1/v2 boundary is the paper's own stability boundary rather than an arbitrary cut ([research.md](research.md) D1).

Four findings shape the plan:

1. **The seed skill already exists at zero bytes.** `resources/skills/` holds three empty placeholders from an earlier feature that classified the domains but never authored content. FR-001 authors a file that exists.
2. **Nothing reads that directory today**, and it is the first thing this feature touches on the generation path. Injection must be a no-op on absence, or every existing session breaks the moment this ships.
3. **The gate has a loophole that a text optimiser will find.** Under permissive mode a hermetic fallback returns **exit code zero without compiling anything**, so a gate scored on exit code alone would reward a skill for making the verifier give up. Feature 012's rule has to hold here ([research.md](research.md) D5).
4. **Training and held-out evidence are disjoint for a structural reason**, not by sampling — the recorded sessions predate the candidate. That argument is asserted in code, because a future change could make it read as true while being false.

## Technical Context

**Language/Version**: Python 3.12 (backend). Generated artifacts are Java 21 / Spring Boot 3.2.3 and are **not** modified by this feature.

**Primary Dependencies**: The model factory (called directly by the reflector, mirroring the generation stages' `build_client`: no wrapper, no conditional, no shared helper), SQLAlchemy + SQLite, pytest. No new dependency.

**Storage**: One new table, `skillopt_runs`, created from the ORM metadata (`Base.metadata.create_all`), since the database currently holds only the session table. Unlike 011/012/013 — which added columns to an existing table through an idempotent shim — a new model needs no migration shim.

**Testing**: pytest, `.venv/bin/python -m pytest`. The loop is exercised through an **injected runner** backed by feature 011's scripted client, so no test calls a provider (Constitution Principle VI). The real iteration is opt-in behind an environment variable plus a provider key.

**Target Platform**: Linux server. The loop is a command-line operation run by a person or a job.

**Performance Goals**: None material. An iteration is 2×M fresh executions (default 8) plus one reflection call. Cost is bounded and known, and doubled deliberately in exchange for a comparison that is never stale ([research.md](research.md) D4).

**Constraints**: Must not change generation behaviour when no active skill is present (SC-005). Must not modify any file the earlier features' guardrails protect. Must not let a fallback-marked execution count as a pass, or the optimiser will exploit that. Must not introduce new held-out fixtures.

**Scale/Scope**: One skill, one iteration, no memory between runs. 5 modules under `backend/scripts/skillopt/`, 1 orchestrator, 1 new table, 1 seed document, 2 injection edits. Small surface, high correctness bar — the gate is what decides whether anything is learned.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Bearing | Verdict |
| --- | --- | --- |
| **I. Arquitectura en Capas Estricta** | None directly — but note the subject matter *is* this principle: the seed skill documents controller → service → repository → model layering. The feature optimises a document about layering; it does not generate code. | **PASS** |
| **II. Contratos Inmutables y Validación Temprana** | None. No DTO or API contract changes. | **PASS** |
| **III. Manejo Centralizado de Excepciones y Limpieza de Código** | One applier, one gate, one collector — the alternative (each caller doing its own edit application) is the duplication this principle discourages. Every branch is exercised by a test: each edit operation, each rejection reason, each gate outcome, and the failure path that still writes a run record. | **PASS** |
| **IV. Determinismo Offline-First y Aislamiento en Sandbox** | The gate's pass rule **depends** on this principle holding: it reads a real offline build result, not a terminal status. Held-out rotation is deterministic from the iteration's identity, so a re-run selects the same blueprints (SC-010). The loop itself makes no network call except the reflector's model call, which the test replaces. | **PASS** |
| **V. Quality Gates y Ciclo Acotado de Auto-Reparación** | **Directly implicated.** This feature *is* a gate — for a document rather than for code — and it borrows the principle's discipline: accept only on a strict improvement, and never accept a result that was not genuinely verified. D5 is this principle applied to the gate's own scoring rule: a synthetic verification is not a pass. The bounded edit cap is the same instinct as the bounded repair cap. | **PASS** |
| **VI. Seguridad de Secretos y Frontera del Orchestrator** | The reflector calls the model factory directly, so the same credential path as generation applies and no key is written to the skill, a run record, or a log. The loop operates on the **orchestration** side and adds nothing to the generated artifact's dependency surface. The automated suite makes zero provider calls (D6). | **PASS** |

**Gate verdict**: all six principles satisfied. **No Complexity Tracking entries required.**

**Note on Principle V**, worth recording because it is unusual: the feature extends the principle's *spirit* to a new object without changing the principle's *scope*. Principle V governs generated code passing Maven tests; this governs a skill document passing a held-out score. No amendment is required and none is proposed.

## Project Structure

### Documentation (this feature)

```text
specs/014-skillopt-compact/
├── plan.md                  # This file
├── spec.md                  # Feature specification
├── research.md              # Phase 0 output
├── data-model.md            # Phase 1 output
├── quickstart.md            # Phase 1 output
├── constitution-recheck.md  # Gate + branch exception
├── contracts/
│   ├── skill-document.md    # The skill format and the protected region
│   ├── edits.md             # The edit contract and its rejection rules
│   └── gate.md              # Scoring, disjointness, and acceptance
├── checklists/
│   └── requirements.md      # Spec quality checklist (16/16)
└── tasks.md                 # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── orchestrator/stages/
│   │   └── runner.py                      # + prepend the active skill to the request (no-op on absence)
│   └── resources/skills/
│       ├── layer_architecture.md          # AUTHORED (exists as a 0-byte placeholder)
│       └── active.md                      # The active-skill pointer (absent by default)
├── scripts/
│   ├── skillopt/
│   │   ├── __init__.py
│   │   ├── collect.py                     # recorded sessions -> outcome records
│   │   ├── reflect.py                     # one direct model call -> bounded edits
│   │   ├── apply.py                       # atomic edits to a COPY; rejects protected/absent targets
│   │   ├── gate.py                        # fresh executions, both scores, strict comparison
│   │   ├── prompts/
│   │   │   └── analyst_error.md           # the reflector prompt, adapted from C.2.1
│   │   └── store.py                       # skillopt_runs table read/write
│   └── run_skillopt.py                    # the single-iteration orchestrator
└── tests/
    ├── test_skillopt_apply.py             # edit operations + both rejection rules
    ├── test_skillopt_gate.py              # strict acceptance, disjointness, both scores
    ├── test_skillopt_reflect.py           # bounded, well-formed edits from a scripted client
    └── test_skillopt_iteration.py         # one full iteration end to end; the run record
```

**Structure Decision**: `backend/scripts/skillopt/` holds the loop's stages as separate modules because each is separately testable and separately rejectable — the applier must be testable without a model, and the gate without a real session. The prompt is a **file**, not a string constant, so that the requirement to record its provenance has an obvious home and so it can be reviewed as text the way a skill is.

Two files outside that package change: the stage boundary (injection) and the skills directory (the seed document and the pointer). Those are the only places this feature touches the generation path, which is what keeps the blast radius small.

**Branch Note**: this is the **fourth** feature on `feature/011-llm-generation-nodes`. Recorded in [constitution-recheck.md](constitution-recheck.md) §2 with the same rationale as 012 and 013, plus one specific to 014: with no active skill it does not change generation behaviour at all, so it cannot regress the earlier features by being present.

## Phase 0 — Research

See [research.md](research.md). Ten decisions, all resolved by inspection plus one fetched primary source. No open `NEEDS CLARIFICATION` items.

## Phase 1 — Design

- [data-model.md](data-model.md) — the skill document, the edits, the collected outcome, the gate's evidence sets, and the run record.
- [contracts/skill-document.md](contracts/skill-document.md) — the required structure and the protected region.
- [contracts/edits.md](contracts/edits.md) — the four operations, the bounded budget, and the two rejection rules.
- [contracts/gate.md](contracts/gate.md) — what a pass is, the disjointness assertion, the rotation, and the strict acceptance rule.
- [quickstart.md](quickstart.md) — runnable validation for each success criterion, including the opt-in real iteration.

### Post-Design Constitution Re-Check

*Re-evaluated after Phase 1 design. Verdict unchanged: all six principles satisfied.*

| Design decision | Constitutional bearing | Assessment |
| --- | --- | --- |
| **A fallback-marked execution never counts as a pass** | Principle V, and 012's honesty rule | Required. Without it the optimiser has a trivial exploit: make the verifier give up and the score rises. A gate that can be improved by degrading verification is worse than no gate, because it will be improved that way. |
| **Disjointness asserted in code, not argued in prose** | Principle V | Correct. The structural argument holds today; the assertion is what keeps it holding when the code changes. Same reasoning as 013's decision to test the through-the-seam path rather than trust the design. |
| **The reflector calls the model factory directly** | Principle VI | Required by the specification, and consistent with the generation stages. No wrapper, so a reader can see the call. No key reaches the skill or a run record. |
| **The runner is a parameter, not a monkeypatch** | Principle VI | The seam is explicit, so a refactor cannot silently stop injecting and leave the suite calling a provider. |
| **Injection is a no-op on absence** | Principles III and IV | Required. This is the first reader of a currently-empty directory, on the generation path. Absence is the normal state. |
| **No statistical validation** | Principle V — gate rigour | **Deliberate, recorded residual.** The gate compares two pass rates with no significance test, on a five-task exam where one task moves the rate 25 points. Acceptable for validating the loop; not acceptable for a production optimiser. Named in the spec's Out of Scope and in [research.md](research.md) D3. |
| **No rejected-edit buffer or epoch state** | Principle V — bounded iteration | Deliberate: this feature has no memory between runs. A rejected edit is logged and lost. Recorded as a known v1 limitation. |

**No new violations. No Complexity Tracking entries added.** Two residuals are recorded above as explicit v1 boundaries rather than silently accepted.
