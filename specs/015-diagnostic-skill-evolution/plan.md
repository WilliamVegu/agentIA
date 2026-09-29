# Implementation Plan: Session Diagnostics and Corpus Baseline

> **Scope note (post-review).** The plan below was written for the original,
> wider feature. Review split it: the **instrument and the corpus baseline are
> built now**, and the **optimizer half is deferred** until the baseline exists
> and shows that the conformance measure varies across real sessions. Everything
> after "Implementation Posture" that concerns contribution measurement, loop
> retargeting or pruning is therefore **queued, not scheduled**. The research,
> data model and contracts remain valid and are retained deliberately, so the
> deferred decision can be made quickly and against data.

**Branch**: `feature/011-llm-generation-nodes` | **Date**: 2026-09-29 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/015-diagnostic-skill-evolution/spec.md`

## Summary

**In scope now**: make what the platform already computes about a session's
conformance durable and attributable, then measure the corpus — how often
generation succeeds, how often it blocks, what conformance its output achieves,
how much correction effort it spends, and what it costs.

**Deferred**: per-skill contribution measurement, retargeting the optimization
loop, and skill removal. The deferred half is fully specified here but is not
built until the baseline exists.

Three things already exist and are reused rather than rebuilt: a deterministic
conformance channel over both validator families (`conformance_diagnostics.diagnose`,
shipped ahead of this plan), per-stage conformance verdicts already carried on
every stage journal entry, and the feature-014 loop (retained, unused for now).
What is missing for the in-scope half is persistence, attribution, a batch driver,
and a report.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: SQLAlchemy + SQLite (existing session store);
the two existing validator families via `orchestrator/stages/compliance.py`; the
existing feature-014 loop modules (`scripts/skillopt/{collect,reflect,apply,gate}`);
`LLMFactory.get_chat_model` for the proposal call, called directly as in feature 014

**Storage**: SQLite, alongside the existing session store and the feature-014
`skillopt_runs` table. Diagnostic records are per session; round records are per
optimization round.

**Testing**: pytest (`.venv/bin/python -m pytest`); all tests deterministic and
offline, with real-model paths behind an explicit opt-in flag as established in
features 012, 013 and 014

**Target Platform**: Linux server (the FastAPI orchestrator). The React frontend
is untouched by this feature.

**Project Type**: web-service backend (existing `backend/` tree)

**Performance Goals**: the diagnostic pass is static analysis over an artifact set
and performs **zero model calls**, so it costs nothing per measurement and can run
on every session. This is the property that makes measurement affordable at all.

**Constraints**:
- The two validator families and the existing conformance gate MUST NOT be
  modified; this feature records and measures against them
- The diagnostic record MUST be deterministic, with no dependence on time,
  ordering or randomness (FR-003)
- No model call may occur in the default test suite
- The counting rules MUST be outside the reach of any optimization round (FR-014)

**Scale/Scope**: the held-out corpus is the five existing baseline blueprints. No
new fixtures are authored. The per-round skill bound is fixed and documented
(FR-017). The available evidence is deliberately reported honestly at whatever
size exists rather than assumed.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
| --- | --- |
| **I. Strict layering** | PASS. The channel is a read-only service over existing validators; no layer is bypassed and no generated artifact is affected. |
| **II. Immutable contracts, early validation** | PASS. Reports are frozen dataclasses; the diagnostic verdict is rejected at construction when malformed, matching the existing `ComplianceVerdict` pattern. |
| **III. Centralized error handling** | PASS (not applicable to a diagnostic service). Repository-layer DB errors remain surfaced through the existing session error path. |
| **IV. Offline-first determinism** | PASS **for the instrument**; the diagnostic channel performs no network access and is byte-deterministic. The measurement requires generation, which is orchestrator-side and governed by VI. |
| **V. Quality gates and bounded repair** | **CONFLICT — see below.** |
| **VI. Secrets and orchestrator boundary** | PASS. The proposal call uses the existing factory and key handling; the default suite makes no provider call. Keys are never persisted. |

### The Principle V conflict, stated plainly

Principle V caps *autonomous correction of generated code* at **three iterations**,
and requires the task to be aborted into human intervention beyond that. This
feature introduces a different kind of autonomy: a loop that modifies **the
generator's own instructions** — the skill — rather than the code it produces.
The constitution does not currently bound that. There is no clause saying how many
times the platform may rewrite its own operating instructions, what evidence is
required before it does, or when a self-modification must be surfaced to a human.

This is not a violation of an existing rule; it is a rule that does not yet exist
for a capability that does not yet exist. It is recorded and carried into
`constitution-recheck.md` rather than silently treated as permitted.

Two further disclosures:

- **Pre-existing drift, not introduced here.** Principle V specifies three repair
  iterations; `config.py` sets five. This feature neither causes nor depends on
  that discrepancy, but it touches the same bounded-autonomy area and so repeats
  the disclosure made in features 011–014.
- **The optimizer cannot be allowed to weaken its own judge.** Principle V's
  intent is bounded, auditable autonomy. FR-014 keeps the counting rules outside
  the round's reach so a round cannot manufacture an improvement by degrading the
  instrument that judges it.

## Project Structure

### Documentation (this feature)

```text
specs/015-diagnostic-skill-evolution/
├── plan.md                  # This file
├── spec.md                  # Feature specification
├── research.md              # Phase 0 output
├── data-model.md            # Phase 1 output
├── quickstart.md            # Phase 1 output
├── constitution-recheck.md  # Governance assessment of the Principle V gap
├── contracts/               # Phase 1 output
│   ├── diagnostic-record.md
│   ├── contribution-measurement.md
│   └── evolution-round.md
├── checklists/
│   └── requirements.md
└── tasks.md                 # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── models/
│   │   ├── session.py                    # existing — unchanged
│   │   └── skillopt.py                   # existing — extended with the records
│   └── services/
│       ├── conformance_diagnostics.py    # EXISTS — the channel, shipped pre-plan
│       └── corpus_report.py              # NEW — the baseline report
├── scripts/
│   ├── measure_conformance_discrimination.py   # EXISTS
│   ├── run_corpus_baseline.py            # NEW — batch driver (FR-008)
│   └── skillopt/
│       ├── collect.py                    # existing — retargeted onto diagnostics
│       ├── reflect.py                    # existing — unchanged call path
│       ├── apply.py                      # existing — extended for removal
│       ├── gate.py                       # existing — demoted to a guardrail
│       └── currency.py                   # NEW — evidence floor and pruning rule
└── tests/
    ├── test_conformance_diagnostics.py   # EXISTS
    ├── test_diagnostic_record.py         # NEW — persistence + per-stage attribution
    └── test_corpus_report.py             # NEW — population, exclusions, no-data
```

**Structure Decision**: extends the existing `backend/` web-service tree. The
channel already exists as `services/conformance_diagnostics.py` and is not
rebuilt. The corpus report sits beside it in `services/`, since it summarises the
same instrument's output. The batch driver is a script, not an orchestrator
concern — it drives existing sessions and adds no node. The contribution measurement belongs in `services/` beside it, since it
is a measurement over the same instrument rather than a stage concern. The
pruning rule lives in `scripts/skillopt/` with the rest of the loop, because it
is policy about rounds and not about the platform's runtime behaviour. Nothing is
added to the orchestrator graph, no node changes, and the frontend is untouched.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| None — the Constitution Check raises a **gap**, not a violation | Principle V does not bound self-modification of the generator because no such capability existed when it was ratified | Not applicable. The gap is recorded in `constitution-recheck.md` for a ratification decision rather than worked around in code. |

## Implementation Posture

Three constraints from the evidence base shape the implementation and are
restated here because they are easy to lose once tasks are written:

1. **The instrument precedes the loop.** A reflective loop gated on an opaque
   pass/fail verdict has been measured at parity with no loop at all. The
   diagnostic channel is therefore implemented and measured before anything
   consumes it, and its discrimination is re-measured after every change.
2. **The loop must be able to remove.** A loop that can only add or rewrite
   accumulates until injecting a skill scores worse than injecting nothing. The
   removal operation is not optional polish; it is what keeps the set usable.
3. **The honest result may be "not measurable".** At the available asset count,
   several of this feature's own success criteria will report insufficiency. That
   is the feature working, not failing, and the plan must not be read as
   promising a demonstrated improvement.
