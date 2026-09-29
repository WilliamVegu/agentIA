# Quickstart — SkillOpt Compact

Validation guide for feature 014. Each scenario maps to a success criterion. **Only scenario 7 makes a real model call**, and it is opt-in.

---

## Prerequisites

| Requirement | Check | Expected |
| --- | --- | --- |
| Virtualenv | `ls .venv/bin/python` | exists |
| Test runner | `.venv/bin/python -m pytest --version` | prints a version |
| Skill directory | `ls backend/app/resources/skills/` | the seed document plus the three placeholders |
| Active pointer | `cat backend/app/resources/skills/active.md` | may be **absent** — that is the default and it is not an error |
| Baseline blueprints | `ls backend/tests/fixtures/baseline_blueprints/` | exactly five: `pair-a`, `pair-b`, `minimal`, `multi-entity`, `constrained` |

**Run all commands from the repository root.**

The loop uses **no new fixtures**. If a sixth blueprint appears, that is a change to this feature's contract, not an addition to it.

---

## Scenario 1 — Injection is real, and its absence is a no-op (SC-005)

**Purpose**: prove the skill reaches the request, and that removing it changes nothing.

**Action**:

```bash
.venv/bin/python -m pytest backend/tests/test_skillopt_iteration.py -k inject -v
```

**Expected**:

1. **With** an active skill naming the seed document, a rendered request **contains** the skill's text alongside the stage's own instructions.
2. **Without** the active pointer, the rendered request is **byte-identical** to the pre-feature request. This is the regression guard for the whole feature.
3. An **empty** or **unreadable** pointer behaves as absent — no-op, no error.
4. A pointer naming a **non-existent** skill is a no-op, and the condition is recorded rather than raised.

**Failure looks like**: an exception when the pointer is absent; or a request that differs from the pre-feature rendering when no skill is active.

---

## Scenario 2 — The seed document is valid and protected (FR-001)

**Action**:

```bash
.venv/bin/python -m pytest backend/tests/test_skillopt_apply.py -k load -v
```

**Expected**:

- The seed document loads: title, granularity, "when to apply", numbered rules, and **both** slow-update markers with `START` before `END`.
- A document **missing** a marker is **rejected at load**, not treated as having an empty protected region.
- An **empty** file is a load error, not a skill with no rules.

---

## Scenario 3 — Edits apply atomically, and both rejection rules fire (SC-003, SC-004)

**Action**:

```bash
.venv/bin/python -m pytest backend/tests/test_skillopt_apply.py -v
```

**Expected**:

| Case | Result |
| --- | --- |
| `append` | Content added at the end of the editable region |
| `insert_after` with a present target | Inserted immediately after the first match |
| `replace` with a present target | First match replaced |
| `delete` with a present target | First match removed |
| **Target inside the protected region** | **Rejected**; document unchanged |
| **Target text not found** | **Rejected**; document unchanged |
| Unknown operation / missing field | Rejected |
| `content` supplied for `delete` | Rejected |
| One bad edit among several good ones | The bad one is rejected, **the others still apply** |

**And**: after any application, the **original skill file is unchanged** — edits apply to a copy.

**Failure looks like**: a protected-region edit succeeding; a not-found target being fuzzily matched; or the original file being modified by application.

---

## Scenario 4 — The gate accepts strictly, rejects ties (SC-002)

**Purpose**: the three outcomes, deterministically, with no real model call.

**Action**:

```bash
.venv/bin/python -m pytest backend/tests/test_skillopt_gate.py -v
```

**Expected**:

| Comparison | Decision |
| --- | --- |
| candidate `>` current | **ACCEPTED** |
| candidate `=` current | **REJECTED** |
| candidate `<` current | **REJECTED** |

Plus:

- Both scores are computed on the **identical** held-out blueprint selection.
- An iteration performs exactly **2×M** fresh executions (default 8).
- An execution whose verification used the **hermetic fallback does not count as a pass**, even at exit code zero.
- An **unscorable** execution is reported separately from a failure.

**Failure looks like**: a tie being accepted; the two skills scored on different blueprints; or a fallback-marked execution counting as a pass — the last would let a candidate raise its score by making the verifier give up.

---

## Scenario 5 — Training and held-out evidence are provably disjoint (SC-008)

**Action**:

```bash
.venv/bin/python -m pytest backend/tests/test_skillopt_gate.py -k disjoint -v
```

**Expected**:

- No session identifier appears in both the collected training outcomes and the held-out executions.
- When the assertion is violated — forced in the test — the gate **fails loudly** rather than scoring.

**Failure looks like**: a silent pass when the sets overlap. The overlap is the failure the gate exists to prevent, and it is invisible in the score.

---

## Scenario 6 — One full iteration, end to end (SC-001, SC-006)

**Purpose**: the whole loop with a scripted client and an injected runner.

**Action**:

```bash
.venv/bin/python -m pytest backend/tests/test_skillopt_iteration.py -v
```

**Expected**:

- The iteration completes and prints **current score, candidate score, decision, edit count**.
- **Exactly one** `skillopt_runs` row exists with both scores, the decision, the proposed edits, and the sample sizes.
- A **failing** iteration also leaves exactly one row, carrying the error.
- **No failures collected** and **no sessions collected** are reported as **distinct** outcomes, and neither calls a model.
- The held-out rotation is deterministic: running the same iteration identity twice selects the same blueprints (SC-010).

**Failure looks like**: zero rows after a failure; two rows after one iteration; or a model call when there is nothing to learn from.

---

## Scenario 7 — A real iteration (SC-007) — opt-in, needs a provider key

**Purpose**: one genuine iteration against a live model.

**This is the only scenario that calls a provider and spends money.** It MUST NOT run in the default suite (Constitution Principle VI).

```bash
AGENTIA_RUN_REAL_SKILLOPT=1 DEEPSEEK_API_KEY=... \
  .venv/bin/python backend/scripts/run_skillopt.py
```

**Expected**:

- One iteration runs, one `skillopt_runs` row is written, and the summary is printed.
- The reflector's prompt is the one in `backend/scripts/skillopt/prompts/analyst_error.md`, which records its adaptation source and does not reproduce the paper's text.

**If the key is absent it skips.** Report it as *not verified by me* rather than inferred from the scripted path — the same discipline features 012 and 013 required for their opt-in criteria.

**Note on cost**: a real iteration is 2×M fresh sessions (default 8) plus one reflection call. That is the deliberate price of scoring both skills on the same sample ([contracts/gate.md](contracts/gate.md) §4).

---

## Definition of Done

- [ ] Scenario 1 passes (SC-005: injection works; absence is byte-identically a no-op)
- [ ] Scenario 2 passes (FR-001: the seed document is valid and the protected region is enforced)
- [ ] Scenario 3 passes (SC-003, SC-004: both rejection rules; the original is never modified)
- [ ] Scenario 4 passes (SC-002, SC-009: strict acceptance; 2×M; no fallback-marked pass)
- [ ] Scenario 5 passes (SC-008: disjointness asserted, not assumed)
- [ ] Scenario 6 passes (SC-001, SC-006, SC-010: one iteration, one row, deterministic rotation)
- [ ] Scenario 7 **run with a key, or explicitly recorded as not verified** (SC-007)
- [ ] The full pre-existing suite passes **unmodified**
- [ ] No new fixtures were added under `baseline_blueprints/`
- [ ] The seed skill's content is recorded as a placeholder, not as validated advice
