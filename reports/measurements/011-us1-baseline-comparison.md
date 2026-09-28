# SC-001 / SC-002 measurement — User Story 1

**Feature**: 011-llm-generation-nodes · **Task**: T041
**Model**: payload-aware fake client (T017) — **no live model calls**
**Baseline**: `reports/baselines/011-pre-migration-generation-baseline.json` (frozen, real recorded data)

> **What is real here.** The stage execution boundary, the payload builder, the
> compliance gate and the journal are the production implementations. Only the
> model is fake. The SC-001/SC-002 contrasts are therefore about what the payload
> *carries*, not about a model's semantic quality — that needs a live model.

## SC-001 — declared constraints reach the generated entity

| | |
| --- | --- |
| Declared format constraints | `@Email`, `@Min`, `@Max`, `@Pattern`, `@Size` |
| Present in the MODEL-path entity | `@Email`, `@Min`, `@Max`, `@Pattern`, `@Size` |
| Absent from the baseline entity | `@Email`, `@Min`, `@Max`, `@Pattern`, `@Size` |

Verdict: **PASS** — every declared constraint reaches the model in the payload and appears in the generated artifact, where the baseline carried none.

## SC-002 — paired blueprints

The paired blueprints differ only in declared constraints and acceptance
scenarios. Pre-migration they produced byte-identical output (baseline outputs byte-identical: `True`).

| | |
| --- | --- |
| MODEL-path pair-a entity | `161` chars |
| MODEL-path pair-b entity | `216` chars |
| Outputs differ | `True` |

Verdict: **PASS** — the outputs now track the declared differences.

## SC-005 — request budget

Single measured session: **5** of
`15` requests permitted.

Verdict: **PASS**
