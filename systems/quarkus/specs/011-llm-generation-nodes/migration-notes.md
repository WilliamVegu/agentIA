# Migration notes — feature 011 (LLM-driven generation stages)

Task: T042. These are deliberate behavior changes made by this migration. They are
recorded here so they are **not** rediscovered in a later phase and misattributed.

---

## 1. Conservative severity merge: a Lombok prohibition becomes blocking

### What changed

The platform contains two independent constitutional validator families with
overlapping rule sets that disagree on severity for the same violation. The
feature-011 compliance adapter normalizes both verdicts and keeps the **strictest**
severity per violation (see [contracts/compliance-verdict.md](contracts/compliance-verdict.md) §5).

The concrete case:

| | Family A | Family B | Adapter keeps |
| --- | --- | --- | --- |
| Lombok `@Data` on a JPA entity | MEDIUM | HIGH | **HIGH → blocking** |

Before this migration that violation was non-blocking under Family A's rating
alone. It now rejects the candidate set, which consumes a correction attempt and —
if the model does not comply within two corrections — terminates the session in
the human-intervention state.

### Why it is intended

A prohibited annotation should not pass a compliance gate. The lenient severity
was **under-reporting a real violation**; the adapter did not invent a new rule, it
stopped hiding one. [research.md](research.md) D13 states the change is caused by
the gate becoming honest, not by the migration.

### Why it still needs to be on the record

This is a real behavior change with a measurable cost:

* **Sessions that previously completed may now block.** They are not new failures;
  they are pre-existing violations that no longer pass unnoticed.
* **It counts directly against SC-011's absolute 15% intervention ceiling.** Any
  intervention-rate regression must be checked against this effect **before** being
  attributed to the model-driven stages. It is the single most likely source of a
  false SC-011 attribution: the metric moves for a reason that has nothing to do
  with model output quality.
* The effect is largest for projects that use Lombok heavily, which is exactly the
  population where the pre-migration gate was most lenient.

### Substitute mitigation (D13)

Direct A/B measurement is not available: the pre-migration path emitted
non-compliant artifacts and no verdict at all, so there is no historical verdict
to diff against. The substitute is recorded in [research.md](research.md) D13:

> Run this adapter **post hoc** over the baseline's retained comparison-subset
> content to isolate the lenient-to-strict delta.

The frozen baseline retains the generated content of its comparison subset, so the
adapter can be replayed over it offline. That yields the set of violations the old
gate would have let through and the subset that is newly blocking, separating the
severity-merge effect from any model-quality effect. This is the **primary
attribution tool** for an SC-011 rate above the ceiling and should be run before
any claim that the model-driven stages caused a regression.

### Operational note

Because the merge is severity-strict, adding a rule to either validator family
cannot silently loosen the gate. It can, however, tighten it — so a new rule in
either family is an SC-011-relevant event and belongs in these notes.

---

## 2. The compliance gate applies to the MODEL path only

The stage execution boundary enforces the compliance gate for `MODEL` sessions
only. `DETERMINISTIC` sessions run with **no gate** and `request_count = 0`.

This asymmetry is deliberate and is documented at the point of use in
`backend/app/orchestrator/stages/runner.py` (module docstring) with its FR-013
rationale: deterministic output is compliant by construction, and gating it would
change offline behavior.

**Do not "fix" this as an oversight.** It is a recorded design decision, not a
missing branch. See task T043.

---

## 3. Scope of this migration

Unchanged by feature 011, and verified as such:

* The sandbox verifier and the self-repair stage (`sandbox_node.py`,
  `repair_node.py`) are **behaviorally unchanged** — byte-identical to the
  pre-migration commit `89a900b` (T046).
* Path B (auto-pilot, `pipeline_runner.py`) still performs **no sandbox
  verification and no repair**. That is a pre-existing gap, out of scope per
  FR-023, and it was **not** closed as a side effect of this work.
* The generated artifact path set and index contract are unchanged (T045).
