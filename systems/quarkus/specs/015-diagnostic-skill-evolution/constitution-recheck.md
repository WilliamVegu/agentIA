# Constitution Recheck: Feature 015

**Constitution version**: 1.1.0 | **Ratified**: 2026-09-13 | **Last amended**: 2026-09-13

**Feature**: 015-diagnostic-skill-evolution

**Verdict**: **No violation.** One **gap** is recorded for a ratification
decision. Two pre-existing disclosures are repeated.

---

## 1. Principle-by-principle

| Principle | Result |
| --- | --- |
| I. Strict layering | **PASS** — a read-only service over existing validators; no layer bypassed |
| II. Immutable contracts, early validation | **PASS** — frozen dataclasses, validated at construction |
| III. Centralized error handling | **PASS** — not applicable to a diagnostic service |
| IV. Offline-first determinism | **PASS for the instrument** — zero network, byte-deterministic. Measurement requires generation, which is orchestrator-side |
| V. Quality gates and bounded repair | **GAP — see §2** |
| VI. Secrets and orchestrator boundary | **PASS** — existing factory and key handling; the default suite makes no provider call; no key persisted |

---

## 2. The gap: nothing bounds self-modification of the generator

Principle V caps *autonomous correction of generated code* at **three
iterations** and requires a transition to human intervention beyond that. It
governs the platform changing **the artifact it produces**.

This feature enables the platform to change **its own operating instructions** —
the skill document prepended to every generation request. Principle V does not
reach that. There is no clause in the constitution stating:

- how many times the platform may rewrite its own instructions;
- what evidence is required before it may do so;
- when a self-modification must be surfaced to a human before taking effect;
- what prevents a self-modification from weakening the instrument that judges it.

### Why this is a gap and not a violation

The capability did not exist when the constitution was ratified. The constitution
is silent, not contradictory: no existing clause is breached. Recording it as a
violation would misstate the position; recording it as compliant would be worse.
It is a rule that does not yet exist for a capability that does.

### What the feature does about it, pending ratification

- **FR-012** bounds removal behind a stated evidence floor, so a self-modification
  cannot be triggered by noise.
- **FR-016** forbids reporting an improvement the evidence cannot support.
- **FR-014 / SC-010** keeps the counting rules outside a round's reach, so a round
  cannot manufacture an improvement by degrading its own judge. This is the
  Principle V *intent* — bounded, auditable autonomy — applied to a new surface.
- **FR-013** requires exactly one record per round on every path, so every
  self-modification is auditable after the fact.
- **FR-017** bounds how much may be considered in one round.

### Recommended amendment, for a future ratification

Add to Principle V, or as a new Principle VII:

> Autonomous modification of the platform's own generation instructions is
> permitted only within a bounded number of skills, only when supported by
> evidence at or above a stated floor, only when the instrument that measures the
> outcome cannot be modified by the modification itself, and always with exactly
> one durable record of what was proposed and what was decided.

This is a **recommendation**. It is not self-ratified by this feature, and the
feature does not depend on its adoption — the requirements above already
implement its substance.

---

## 3. Pre-existing disclosures, repeated

**Repair-cap drift.** Principle V specifies three repair iterations; `config.py`
sets **five**. Not caused by this feature and not depended on by it, but this
feature touches the same bounded-autonomy area, so the discrepancy is repeated
here as in features 011–014.

**Four features stacked on one branch.** Like 012, 013 and 014, this feature is
developed on `feature/011-llm-generation-nodes` rather than a branch of its own.
The rationale is unchanged: the features share the generation seam, and separating
them would require either duplicating the seam or sequencing merges that cannot be
tested independently. The feature is additive — with no active skill, and with no
round run, generation behaviour is byte-identical to before it.

---

## 4. Post-design re-evaluation

Re-checked after Phase 1 design (data model, contracts, quickstart). No new
constitutional surface was introduced by the design:

- No generated Java artifact changes; no template changes.
- No new network access on any default path.
- No secret is read, persisted or logged.
- The only new persistence is two records and one measure, all local SQLite.
- The frontend is untouched.

**Verdict unchanged: no violation; one gap recorded for ratification.**
