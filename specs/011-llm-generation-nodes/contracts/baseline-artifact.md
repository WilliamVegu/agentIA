# Contract: Pre-Migration Baseline Artifact

**Feature**: LLM-Driven Generation Stages
**Date**: 2026-09-28

---

## 1. Why this artifact exists

SC-001 and SC-002 are defined relative to a pre-migration baseline. Without a captured baseline they are unmeasurable, and the window in which it can be captured closes the moment the first stage is migrated — because the deterministic implementation stops being the only implementation. SC-010 was retired and SC-011 reframed as an absolute threshold, so neither is baseline-dependent any longer (see [research.md](../research.md) D14); the gate stands for SC-001 and SC-002.

**Sequencing is therefore a hard gate**: the baseline is captured before any stage migration begins.

---

## 2. Artifacts

| Path | Purpose |
|---|---|
| `reports/baselines/011-pre-migration-generation-baseline.json` | Machine-readable. The artifact SC-001 and SC-002 are evaluated against. |
| `reports/baselines/011-pre-migration-generation-baseline.md` | Human-readable summary for reviewers. |
| `backend/tests/fixtures/baseline_blueprints/` | The frozen blueprint corpus, committed. |
| `backend/scripts/capture_generation_baseline.py` | The capture script. Standalone, following the existing `backend/scripts/` convention. |

---

## 3. Capture conditions

| Condition | Value | Reason |
|---|---|---|
| Generation mode | `DETERMINISTIC`, explicitly selected | The baseline must measure the pre-migration implementation, not whatever a credential-less environment happens to do. |
| Credentials | Absent or explicitly disabled | Today's default; makes the capture purely additive and unable to destabilize the running platform. |
| Instruction set | Not required | The deterministic path does not read instructions. |
| Corpus | Frozen and committed | SC-002 compares paired blueprints; an ad-hoc set makes the comparison irreproducible. |

---

## 4. Recorded content

### Per blueprint

| Field | Why |
|---|---|
| Blueprint identifier and content hash | Ties the record to a frozen input. |
| Generated artifact path set | Detection of path-contract drift; supports FR-021. |
| Content digest per artifact | Fast difference detection across the whole set. |
| **Full content** of a designated comparison subset | SC-001 requires *behavior-level traceability*, which digests cannot show. Hashes prove two outputs differ; they cannot show that an output reflects a declared constraint. |
| Wall-clock generation duration | Retained as **diagnostic context** only. It no longer backs a success criterion: SC-010 was retired as unmeasurable ([research.md](../research.md) D14). |
| Terminal status | Distinguishes completed from failed generation *for this capture*. It is **not** a session-level intervention signal, because this capture never runs the verifier or the repair loop. |

### Aggregate

| Field | Why |
|---|---|
| Completed vs. failed counts | Sample integrity for this capture. **Not** SC-011's baseline — the intervention count is structurally zero here ([research.md](../research.md) D14). |
| Median and spread of durations | Diagnostic context only; SC-010 was retired, so this backs no criterion. |
| Session count | Records the sample size the baseline claims rest on. |
| Environment fingerprint (platform, provider configuration, container image identity) | A baseline measured under a different environment is not comparable; this makes the comparison auditable. |

---

## 5. Corpus requirements

The frozen blueprint corpus MUST contain at least:

1. **A paired set** — two blueprints identical except for declared attribute constraints and acceptance scenarios. SC-002 requires this pairing specifically.
2. **A minimal blueprint** — one entity, one story. Catches stages that assume multiplicity.
3. **A multi-entity blueprint** — several entities with differing attribute types. Exercises the entity-iteration paths.
4. **A constrained blueprint** — attributes carrying non-nullable and format constraints. This is the SC-001 primary case: the baseline is expected to produce the same annotations regardless of declared constraints, and the migrated implementation is expected not to.

The corpus is committed and is **not modified during the migration**. Adding blueprints mid-migration would invalidate the comparison; new blueprints belong to the post-migration evaluation corpus.

---

## 6. Immutability rule

Once captured, the baseline is frozen for the duration of the migration.

If the capture script is found defective, the baseline is **re-captured before any stage migration begins** — never after. A post-migration re-capture would measure the migrated implementation and silently destroy the SC-001 and SC-002 comparison it exists to support.

Any re-capture must be recorded in this feature's documentation with its reason, so a reviewer can tell which baseline the eventual measurements were taken against.

---

## 7. How the baseline is used

| Criterion | Use |
|---|---|
| **SC-001** | Compare content of the comparison subset: for the constrained blueprint, the migrated output must exhibit behavior traceable to the declared constraints, which the baseline output cannot. |
| **SC-002** | Compare paired blueprints against the baseline pairing to confirm the migrated implementation's *differences* now track the declared differences. |
| ~~**SC-010**~~ | **Retired.** The duration bound was withdrawn as unmeasurable once this capture showed the pre-migration median at 1.134 ms of in-process string assembly ([research.md](../research.md) D14). Duration is retained here as diagnostic context only. |
| ~~**SC-011**~~ | **Reframed and no longer baseline-relative.** Now an absolute post-migration ceiling of ≤ 15% over at least 30 sessions. This artifact cannot supply that rate, because it records no session-level interventions ([research.md](../research.md) D14). |

---

## 8. Measurement caveat

The baseline is a **content and timing** artifact, not a correctness artifact. It records what the pre-migration implementation produced and how long it took; it does not establish that output as correct.

For correctness claims about migrated output, build and test the generated workspace **directly**, outside the platform's sandbox wrapper — which can report synthetic success and is explicitly out of scope for this feature (plan Constraint 5, research D11). Reusing the baseline as a correctness oracle would propagate that flaw into every measurement.
