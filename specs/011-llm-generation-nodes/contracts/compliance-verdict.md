# Contract: Compliance Verdict

**Feature**: LLM-Driven Generation Stages
**Date**: 2026-09-28

Defines the normalized result the stage execution boundary consumes, and how it is derived from the two existing validator families.

---

## 1. The problem this contract solves

The platform contains two independent implementations of overlapping constitutional checks. They disagree on both shape and severity:

| | Family A — test-analysis service | Family B — security service |
|---|---|---|
| Returns | `(bool, list of findings)` | `list of violations` |
| Finding fields | id, category, severity, file path, summary, suggested fix, raw trace | id, principle, severity, file path, offending element, rule description, suggested fix, auto-fix flag |
| Severity vocabulary | `BLOCKING`, `HIGH`, `MEDIUM`, `LOW` | `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` |
| Principle I | `BLOCKING` | `HIGH` |
| Principle II | `HIGH` | `HIGH` |
| Lombok prohibition | `MEDIUM` | `HIGH` |
| Whole-project rules | none | global error-handler presence |
| Additional scope | — | also consumes security findings and a quality-gate verdict |

Consuming both without normalization would mean the same violation is blocking through one path and advisory through the other. Consuming only one would drop either layer isolation's blocking severity (Family A) or the whole-project rules (Family B), both of which FR-005 requires.

---

## 2. Normalized verdict

```text
ComplianceVerdict
├── passed                     : boolean
├── violations                 : ComplianceViolation[]
├── evaluated_artifact_count   : integer
└── sources                    : string[]     # which families contributed

ComplianceViolation
├── artifact_path              : string
├── rule_id                    : string
├── severity                   : CRITICAL | BLOCKING | HIGH | MEDIUM | LOW
├── blocking                   : boolean      # derived from severity
├── message                    : string
├── suggested_fix              : string?
├── attribution                : LOCAL | ACCUMULATED
└── contributing_sources       : string[]
```

Blocking threshold: `CRITICAL`, `BLOCKING`, and `HIGH` are blocking; `MEDIUM` and `LOW` are advisory.

---

## 3. Derivation rules

| # | Rule |
|---|---|
| 1 | Both families are invoked; the verdict unions their findings. `sources` records which contributed. |
| 2 | Findings are deduplicated by `(artifact_path, rule_id)`. |
| 3 | On collision, the **most severe** severity is retained. |
| 4 | `contributing_sources` unions all reporters of a deduplicated finding, so the disagreement stays visible rather than being silently resolved. |
| 5 | `suggested_fix` is carried through so it can be fed back into a correction request. |
| 6 | `passed` is true only when no blocking violation remains. |
| 7 | The accumulated artifact set is evaluated, not the current response alone. |

---

## 4. Attribution — `LOCAL` vs `ACCUMULATED`

This is what makes FR-006 implementable.

| Attribution | Meaning | Effect |
|---|---|---|
| `LOCAL` | The violation points at an artifact path inside the current stage's `artifact_scope`. | Blocks; consumes a correction attempt. |
| `ACCUMULATED` | The violation concerns the project as a whole, or an artifact owned by a different stage. | Recorded; **does not** reject the current stage or consume an attempt. |

Without this distinction, a whole-project rule would fire against every stage that does not happen to produce the artifact it looks for. The concrete case: the global error-handler rule is satisfied only once the API-layer stage has run, so a naive application of Family B's rule would reject the scaffolding, domain, service, and test stages for an omission none of them is responsible for.

`ACCUMULATED` violations are not discarded. They are recorded on the stage journal entry and surface at session level so that a genuinely absent project-wide artifact is still detected — while a stage is not blamed for it.

---

## 5. Deliberate behavior change

The conservative severity merge **tightens** the gate relative to Family A alone. A Lombok `@Data` violation is MEDIUM in Family A and HIGH in Family B, so under rule 3 it becomes blocking.

This is intended — a prohibited annotation should not pass a gate — but it is a real behavior change: sessions that previously completed with such a violation present may now block, which moves the intervention rate in the wrong direction for SC-011.

**Consequences to carry into tasks and measurement**:
- This is a plausible partial explanation for any SC-011 regression and must be checked before attributing a regression to the model-driven stages.
- The tightening is recorded in the migration notes, not discovered in Phase 4.

---

## 6. Boundaries

- The validators are **not modified** (spec assumption, research D4). This contract adapts their output only.
- Inconsistency *inside* the validators (for example, differing regexes for the same rule) is not repaired here.
- The quality-gate verdict is consumed only to determine whether an artifact set is acceptable for persistence; export and publish gating remain where they are today.
- Security-severity findings participate in the verdict, but this contract does not extend what the security scanner detects.
