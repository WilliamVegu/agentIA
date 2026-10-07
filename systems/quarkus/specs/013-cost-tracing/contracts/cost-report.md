# Contract — Cost Report

**Feature**: 013-cost-tracing · **Implements**: FR-004, FR-006, FR-007, FR-008, FR-009, SC-002, SC-003, SC-004

The report is the artifact a stakeholder reads. This contract defines what it must print, what it must exclude, and what makes it reproducible.

---

## 1. Required output

Running the report MUST print all of the following:

| # | Line | Requirement |
| --- | --- | --- |
| 1 | Total sessions | FR-004 |
| 2 | Count completed | FR-004 |
| 3 | Count blocked | FR-004 |
| 4 | Count unverifiable | FR-004 |
| 5 | **Average cost per COMPLETED session** | FR-004, SC-002 — the headline number |
| 6 | Average cost per session, regardless of status | FR-004 |
| 7 | p50 cost | FR-004 |
| 8 | p90 cost | FR-004 |
| 9 | Maximum cost | FR-004 |
| 10 | Cost breakdown by stage | FR-004 |
| 11 | The most expensive stage, named | FR-004 |
| 12 | **Population statement** | FR-008, SC-002 |
| 13 | **Exclusion count** | FR-007, SC-004 |
| 14 | **Pricing basis statement** | FR-003a, SC-008 |

"Unverifiable" is the count of sessions whose verification used a synthetic fallback (feature 012). It is the same population FR-007 excludes, reported rather than merely dropped.

Lines 12–14 are not decoration. A cost figure without its population, its exclusions, and its pricing basis cannot be checked by the reader and cannot be reconciled against an invoice — which is the whole purpose of publishing it.

---

## 2. Population statement (line 12)

MUST state, for the headline figure:

- how many sessions it was computed over,
- how many model calls those sessions made,
- how many calls had **unknown token usage** (contributed nothing to any total),
- how many calls were **unpriced** (their model was absent from the table).

All four numbers are required. An average over a population that silently omits unknown-usage or unpriced calls is an average over an unstated denominator.

---

## 3. Exclusion rule (lines 5 vs 6)

The headline "average cost per completed session" MUST be computed over:

```
terminal_status == "COMPLETED"
and model_mode == "MODEL"
and verification_fallback_used == False
and total_cost_usd is not NULL
```

Every clause is load-bearing:

| Clause | Excludes | Why |
| --- | --- | --- |
| `terminal_status == "COMPLETED"` | Blocked sessions | Not successful generations |
| `model_mode == "MODEL"` | Offline/deterministic sessions | Zero model spend would drag the average toward zero and misstate the unit economics |
| `verification_fallback_used == False` | Sessions whose verification was synthetic | **FR-007.** A session whose verification was synthetic cannot be claimed as a successful generation, so it cannot be priced as one |
| `total_cost_usd is not NULL` | Sessions with no known cost | An unpriced session entering a money average would count as free |

The "average per session regardless of status" (line 6) uses a **wider or equal** population, never a narrower one. Where the two differ, the exclusion count on line 13 explains the gap.

**A fallback-marked session may alternatively be shown on its own line** (FR-007 permits either), but it MUST NOT be inside the headline figure without being named. The default is exclusion plus a visible count.

---

## 4. Determinism (FR-006, SC-003)

Running the report twice over unchanged data MUST print byte-identical figures.

Required for that:

- **No live call.** The report reads the persisted store only. It MUST NOT contact the provider, and it MUST NOT require the telemetry destination to be reachable.
- **Deterministic ordering.** Rows are ordered by session identifier before aggregation and percentile selection, so insertion order cannot influence a result.
- **Fixed precision.** Currency is printed at a fixed number of decimal places with fixed rounding. Accumulating floats in an arbitrary order is a known source of last-digit drift between runs.
- **A stated percentile method.** Nearest-rank over the sorted filtered population, stated in the output. Interpolated percentiles would make the figure depend on an unstated convention.

---

## 5. Empty and degenerate input

| Case | Required behaviour |
| --- | --- |
| No persisted sessions at all | Exit cleanly stating there is nothing to report. MUST NOT print zeroes, which read as a real measurement of zero cost |
| Sessions exist but none is completed-for-costing | Print the counts, then state that the headline figure has no eligible population. MUST NOT print `0.00` as the average |
| Every call unknown-usage | Print token totals as unknown, not zero, and say so in the population statement |
| Every call unpriced | Print cost as unknown, not zero, and surface the unpriced count |

The rule behind all four: **an unknown quantity is reported as unknown, never as zero.** A zero is a claim; an absence is not.

---

## 6. What the report must not do

- Make any live model call (FR-006).
- Require the telemetry destination to be reachable (FR-005, SC-006).
- Present a cost figure without its population, exclusions, and pricing basis (FR-008, FR-003a).
- Fold fallback-marked sessions into the completed-session average without naming them (FR-007).
- Print a cost of zero for a call whose model was missing from the pricing table (FR-009).
- Attribute cost to a user, team, or project — out of scope.

---

## 7. Relationship to the other measurement artifacts

Feature 011's measurement harness writes to `reports/measurements/`. This report is a different artifact with a different audience: the harness measures **intervention rate and compliance**, this measures **cost**. They share the population-honesty discipline — state the population, exclude what cannot be claimed, never substitute zero for unknown — and the exclusion key is the same field feature 012 introduced.
