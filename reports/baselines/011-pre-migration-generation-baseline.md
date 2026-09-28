# Pre-Migration Generation Baseline

**Feature**: 011-llm-generation-nodes (LLM-Driven Generation Stages)
**Captured**: 2026-09-28T21:01:22.505387+00:00
**By**: `backend/scripts/capture_generation_baseline.py`
**Generation mode**: `DETERMINISTIC` — implemented as pre-migration deterministic f-string stage emitters

> **Immutability.** This baseline is frozen for the duration of the migration. It is capturable only while the deterministic implementation is the only implementation. Re-capturing after any stage is migrated invalidates SC-001, SC-010 and SC-011 at once.

---

## 1. Capture conditions

| Condition | Value |
| --- | --- |
| Generation mode | `DETERMINISTIC` |
| Credentials required | `False` |
| Network access used | `False` |
| Stages invoked | `SCAFFOLDER, DOMAIN, SERVICE, CONTROLLER, TEST` |
| Sandbox verifier invoked | `False` |
| Repair loop invoked | `False` |
| Python | `3.12.14` |
| Platform | `Linux-6.12.0-211.55.1.el10_2.x86_64-x86_64-with-glibc2.39` |

**Implementation fingerprint** (SHA-256 of the retained stage modules — this is what pins the capture to the pre-migration implementation):

| Stage | Module digest |
| --- | --- |
| `SCAFFOLDER` | `04b450633462bea2…` |
| `DOMAIN` | `113bfb1d19558789…` |
| `SERVICE` | `ae515365e89f1af6…` |
| `CONTROLLER` | `883cf9c1162d2c56…` |
| `TEST` | `62805e04d6975742…` |

## 2. Frozen corpus

Directory: `backend/tests/fixtures/baseline_blueprints` — 5 blueprints.

| Category | Files |
| --- | --- |
| paired set | `pair-a.json`, `pair-b.json` |
| minimal single entity | `minimal.json` |
| multi entity differing types | `multi-entity.json` |
| constrained non nullable and format | `constrained.json` |

## 3. Per-blueprint results

| Blueprint | Status | Artifacts | Duration (ms) | Declared rules | Untraced rules | Declared scenarios | Observed test methods |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `constrained` | COMPLETED | 15 | 1.2 | 5 | 5 | 6 | 5 |
| `minimal` | COMPLETED | 15 | 1.1 | 0 | 0 | 1 | 5 |
| `multi-entity` | COMPLETED | 23 | 1.6 | 0 | 0 | 4 | 10 |
| `pair-a` | COMPLETED | 15 | 1.1 | 0 | 0 | 1 | 5 |
| `pair-b` | COMPLETED | 15 | 1.1 | 4 | 4 | 4 | 5 |

## 4. Constraint and scenario trace — the SC-001 signature

This is the core measurement. It is reported in two categories rather than as a single "no trace" claim, because the pre-migration stages **do** honour one class of constraint while ignoring the rest. Collapsing them would overstate the finding.

### 4.1 `constrained`

- Declared format constraints: `@Email`, `@Min`, `@Max`, `@Pattern`, `@Size`
- **Traced in output**: **none**
- **Untraced**: `@Email`, `@Min`, `@Max`, `@Pattern`, `@Size`
- Required (non-nullable) attributes declared: `displayName`
- Required-attribute annotation observed anywhere in output: `True`
- Declared acceptance scenarios: **6**; observed test methods: **5**; counts match: `False` → tests ignore declared scenarios: `True`

> Pre-migration signature: 5/5 declared format constraints leave no trace; required-attribute annotation observed=True; declared scenarios=6, observed test methods=5, counts match=False (tests ignore declared scenarios=True).

### 4.2 `minimal`

- Declared format constraints: _none_
- **Traced in output**: **none**
- **Untraced**: _none_
- Required (non-nullable) attributes declared: _none_
- Required-attribute annotation observed anywhere in output: `False`
- Declared acceptance scenarios: **1**; observed test methods: **5**; counts match: `False` → tests ignore declared scenarios: `True`

> Pre-migration signature: 0/0 declared format constraints leave no trace; required-attribute annotation observed=False; declared scenarios=1, observed test methods=5, counts match=False (tests ignore declared scenarios=True).

### 4.3 `multi-entity`

- Declared format constraints: _none_
- **Traced in output**: **none**
- **Untraced**: _none_
- Required (non-nullable) attributes declared: _none_
- Required-attribute annotation observed anywhere in output: `False`
- Declared acceptance scenarios: **4**; observed test methods: **10**; counts match: `False` → tests ignore declared scenarios: `True`

> Pre-migration signature: 0/0 declared format constraints leave no trace; required-attribute annotation observed=False; declared scenarios=4, observed test methods=10, counts match=False (tests ignore declared scenarios=True).

### 4.4 `pair-a`

- Declared format constraints: _none_
- **Traced in output**: **none**
- **Untraced**: _none_
- Required (non-nullable) attributes declared: _none_
- Required-attribute annotation observed anywhere in output: `False`
- Declared acceptance scenarios: **1**; observed test methods: **5**; counts match: `False` → tests ignore declared scenarios: `True`

> Pre-migration signature: 0/0 declared format constraints leave no trace; required-attribute annotation observed=False; declared scenarios=1, observed test methods=5, counts match=False (tests ignore declared scenarios=True).

### 4.5 `pair-b`

- Declared format constraints: `@Email`, `@NotBlank`, `@Positive`, `@DecimalMin`
- **Traced in output**: **none**
- **Untraced**: `@Email`, `@NotBlank`, `@Positive`, `@DecimalMin`
- Required (non-nullable) attributes declared: _none_
- Required-attribute annotation observed anywhere in output: `False`
- Declared acceptance scenarios: **4**; observed test methods: **5**; counts match: `False` → tests ignore declared scenarios: `True`

> Pre-migration signature: 4/4 declared format constraints leave no trace; required-attribute annotation observed=False; declared scenarios=4, observed test methods=5, counts match=False (tests ignore declared scenarios=True).

## 5. Twin (paired) comparison — the SC-002 signature

Blueprints sharing a structural signature differ **only** in declared constraints and acceptance scenarios. Since the pre-migration stages read neither, their output must be byte-identical. That identity is precisely what the migration is expected to break.

| Left | Right | Declared rules L→R | Scenarios L→R | Byte-identical | Differing artifacts |
| --- | --- | --- | --- | --- | --- |
| `pair-a` | `pair-b` | 0→4 | 1→4 | **True** | 0 |

**Interpretation**: byte-identical=`True` confirms that declared constraints and acceptance scenarios had **zero** effect on pre-migration output. The migrated implementation must make this comparison differ in exactly the corresponding artifacts.

## 6. Aggregate

| Metric | Value |
| --- | ---: |
| Blueprints captured | 5 |
| Completed | 5 |
| Failed | 0 |
| Human intervention (generation-stage) | 0 |
| Total artifacts generated | 83 |
| Duration median (ms) | 1.134 |
| Duration mean (ms) | 1.222 |
| Duration min / max (ms) | 1.108 / 1.564 |
| Duration stdev (ms) | 0.194 |

## 7. Limitations — read before using this artifact

- Generation-stage capture only. No sandbox verification, no self-repair, no session-level intervention rate.
- The blocked/intervention count is structurally zero here and must not be used as SC-011's baseline.
- Duration figures cover the five generation stages, not end-to-end session time. SC-010's comparison must use a like-for-like end-to-end measurement or state the difference.
- The sandbox verifier's synthetic-success fallback is out of scope for feature 011 and is not exercised or repaired by this script.

**Specifically on SC-011**: the intervention count above is structurally zero because this capture never reaches the stages that produce interventions. It is not a session-level rate and must not be used as SC-011's baseline. That baseline requires a separate session-level capture.

---

*Generated by `backend/scripts/capture_generation_baseline.py` (task T008) for feature 011-llm-generation-nodes. See `specs/011-llm-generation-nodes/contracts/baseline-artifact.md`.*
