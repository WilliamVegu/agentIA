# Research & Technical Decisions: LLM-Driven Generation Stages

**Feature**: LLM-Driven Generation Stages
**Branch**: `skillopt_implementation`
**Date**: 2026-09-28

This is the Phase 0 decision log. Every entry resolves an unknown that would otherwise have become an implementation-time guess. Each records what was chosen, why, and what was rejected.

---

## D1. Where the stage execution boundary lives, and what it owns

**Decision**: A new agent-side package under `backend/app/orchestrator/stages/`, exposing one entry point that executes a named generation stage against session state. It owns mode selection, request and correction budgeting, compliance gating, provenance recording, and correction-journal accumulation.

**Rationale**: Five concerns are identical across all five stages and all two execution paths. Implementing them per stage would produce five copies that drift. Implementing them per path would produce two copies that drift — which is precisely the failure the platform already exhibits with its two validator families. One seam, called by both paths, makes FR-022 true by construction rather than by discipline.

The package belongs under `orchestrator/` rather than `services/` because it owns session-scoped agent policy. That also keeps it on the orchestrator side of the constitutional LangGraph boundary (Principle VI): it must never become a dependency of the generated artifact.

**Alternatives considered**:
- *Implement inside each node callable.* Rejected: the correction-retry loop, budget accounting, and journal writing would be duplicated five times, and neither execution path could enforce policy independent of node behavior.
- *Implement in each caller.* Rejected: two copies, guaranteed to diverge; the graph path would get retry-and-journal and the auto-pilot path would not.
- *Put the seam in `services/`.* Rejected: it is agent control-plane logic, not a domain service, and placing it with the generation-adjacent services invites it into the generated artifact's dependency surface.

---

## D2. Session-level, not stage-level, generation-mode selection

**Decision**: The model-versus-deterministic decision is made once per session, at session start. The chosen mode is recorded in session state and in every provenance record. Once a session begins in model-driven mode, it never reverts to deterministic.

**Rationale**: Per-stage switching would yield hybrid output that makes three success criteria uninterpretable — a session could satisfy SC-001 by accident of which stages happened to get a model. Session-level selection also gives the baseline capture a clean comparison axis: one session is wholly one implementation, or wholly the other.

The "never reverts" rule is the load-bearing part. If a stage could fall back *after* a rejection, the platform would reproduce the discarded option C from `/speckit-clarify` — a defective instruction would manifest as silently emitting pre-migration boilerplate while the session reports success. That inverts the feature's purpose and makes SC-001 unmeasurable, since the baseline content would keep appearing in model-mode sessions.

The seam must therefore treat two conditions as categorically different:
- *No model available* → pre-request condition → deterministic implementation, decided before any request is issued.
- *Model responded, response rejected* → post-request condition → bounded correction, then block.

**Alternatives considered**:
- *Per-stage selection.* Rejected: hybrid output; uninterpretable metrics.
- *Per-stage fallback on rejection.* Rejected: silently masks prompt defects and defeats the pre-write gate's purpose.
- *Automatic fallback whenever credentials are missing, with no operator override.* Rejected: the baseline capture needs to force deterministic mode while credentials are present, and controlled before/after comparison requires an explicit switch rather than credential juggling.

---

## D3. Instruction revision scheme — content-addressed, with a human label

**Decision**: The authoritative instruction-set revision is a digest over the canonicalized map of stage name → instruction content. A separate `VERSION` file carries a human-readable label for reporting only.

**Rationale**: A content digest cannot drift from the content it names, changes on any edit without human discipline, and needs no runtime Git dependency. The last property matters concretely: session workspaces are exported and executed independently of the repository, and a provenance record must remain resolvable — or at least self-describing — outside a checkout.

**Alternatives considered**:
- *Git commit SHA of the instructions directory.* Rejected: requires a `.git` directory at runtime; also changes on unrelated commits that touch the directory, producing spurious revision churn that would make provenance comparisons noisy.
- *`VERSION` file as the authoritative identifier.* Rejected: a hand-maintained label can silently diverge from the content it claims to identify. Kept only as a human-facing convenience.
- *No versioning; embed the instruction text in each provenance record.* Rejected: provenance records would balloon; FR-020 asks for a revision identifier.

---

## D4. Validator normalization — adapter, not modification

**Decision**: An adapter at the seam projects both existing validator families into one normalized verdict. The validators themselves are not modified.

**Rationale**: The specification's assumptions section requires consuming the existing validators as-is, and consolidating them is separate work. But the two families disagree in ways that matter:

| | Family A (test-analysis service) | Family B (security service) |
|---|---|---|
| Return shape | `(bool, List[FailureDiagnostic])` | `List[StandardsComplianceViolation]` |
| Same-rule severity | Principle I → BLOCKING; Principle II → HIGH; Lombok → MEDIUM | All → HIGH |
| Whole-project rules | none | `@RestControllerAdvice` presence, evaluated across the file set |

The adapter must resolve the severity disagreement, because the same violation would otherwise be blocking via one path and non-blocking via the other. **Decision: deduplicate by (artifact path, rule identifier), keep the most severe classification, and record every contributing source.** This is deliberately conservative — it errs toward blocking.

**Consequence to carry into tasks and testing**: this conservative merge *tightens* the gate relative to Family A alone. A Lombok `@Data` violation is MEDIUM in Family A but HIGH in Family B, so it becomes blocking under the merged verdict where it previously might not have been. That is a deliberate behavior change and must be called out in the migration notes, because it can convert previously-completing sessions into blocked ones and therefore move SC-011 in the wrong direction. It is the correct trade — a prohibited annotation should not pass a gate — but it must be measured, not discovered.

**Alternatives considered**:
- *Use only Family B.* Rejected: discards Family A's BLOCKING classification for layer violations.
- *Use only Family A.* Rejected: discards Family B's whole-project rules, which FR-005 requires.
- *Merge the two validators into one implementation.* Rejected: out of scope per the spec's assumptions; it would expand this feature into a refactor of the security service and would delay the migration behind an unrelated cleanup.

---

## D5. Test strategy for the model path — a scripted fake client, distinct from mock

**Decision**: Add a scripted fake model client under the test fixtures, returning predetermined responses per stage. It is a distinct concept from the platform's existing mock/offline provider.

**Rationale**: Two hard constraints converge. Principle VI forbids network calls to model APIs from tests, so CI can never use a live model. And the existing mock provider returns *no client* — which is, by design, the trigger for the deterministic fallback (D2). Reusing mock to test the model path would therefore test the fallback path instead, silently. The fake must be capable of returning a *well-formed response*, which mock categorically is not.

The fake also enables the fault-injection scenarios the specification demands: SC-003 (every constitutional rule violated), SC-007 (every response non-compliant), and SC-008 (retain the full correction history) are all only testable by scripting responses, since a live model cannot be asked to violate a specific rule on demand.

**Alternatives considered**:
- *Reuse the mock provider.* Rejected: returns no client; exercises the fallback, not the model path.
- *Record real model responses and replay them.* Rejected as a primary mechanism: fixtures would bake in one provider's output shape and would need regeneration whenever instructions change (D3), which is exactly when coverage matters most. Retained as a possible supplement for realism testing.
- *Live calls in a nightly job.* Rejected: violates Principle VI for the unit suite, and produces non-reproducible pass/fail.

---

## D6. Correction-journal storage — additive, not overloaded

**Decision**: Extend session storage additively with a generation journal and provenance fields. Do not repurpose the existing free-form phase-progress JSON column.

**Rationale**: The specification states the feature "does not assume the existing session schema changes meaning". Writing a generation journal into the phase-progress column would change that column's meaning and couple two unrelated lifecycles — a schema-level ambiguity that would surface later as a confusing bug. An additive column keeps the meaning of every existing column intact and is reversible.

Volume is not a concern at the stated scale: at most 5 stages × 2 rejected attempts, each with a violation set and a model response. If journal volume later warrants a dedicated table, that migration is mechanical and non-breaking — but adopting a table now would be speculative complexity for a volume that does not exist.

**Alternatives considered**:
- *Reuse the phase-progress JSON column.* Rejected: changes an existing column's meaning; the spec forbids assuming that.
- *A new dedicated table immediately.* Rejected: premature; the bounded volume fits an additive column, and a table adds join and lifecycle complexity for no present benefit.
- *Log to the filesystem only.* Rejected: FR-012 requires the history to be carried in session state and persistable beyond process life; a filesystem side-channel would not survive export or be visible to API consumers.

---

## D7. Baseline capture design

**Decision**: A standalone script captures a frozen blueprint corpus through the deterministic path and writes a machine-readable artifact plus a human-readable summary. It is a blocking gate: no stage migration begins until it exists.

**Rationale**: Three success criteria are defined relative to the baseline and cannot be evaluated without it. The baseline is capturable only while the deterministic implementation is the only implementation, so the ordering is not a preference — it is the only window in which the artifact can be produced at all.

Design points that follow from how the criteria are written:
- SC-001 requires content-level traceability ("exhibit at least one behavior traceable to the blueprint"), so the artifact must retain artifact *content* for a comparison subset, not just hashes. Hashes alone can prove difference but not traceability.
- SC-002 compares paired blueprints, so the corpus must be frozen and committed; an ad-hoc blueprint set would make the comparison irreproducible.
- SC-010 and SC-011 need durations and intervention counts, so the capture must record per-session timing and terminal status, not just artifacts.

**Capture conditions**: no model credentials, which is today's default. The capture is therefore purely additive and cannot destabilize the running platform.

**Immutability rule**: once captured, the baseline is frozen for the duration of the migration. If the capture script proves defective, the baseline is re-captured before any migration begins — never after, since a post-migration re-capture would measure the migrated implementation.

**Alternatives considered**:
- *Capture from historical session data.* Rejected: the seeded database is synthetic fixture data (documented in `reports/agentia-state-map.md`), so it records no real generation behavior.
- *Skip the corpus and use a single blueprint.* Rejected: SC-002 requires paired blueprints differing only in declared constraints and scenarios.
- *Hashes only.* Rejected: insufficient for SC-001's traceability requirement.

---

## D8. Removing the auto-pilot path's aliasing hazard

**Decision**: The auto-pilot path is re-pointed at the seam and must consume returned state, rather than continuing to rely on in-place mutation of retrieved dicts.

**Rationale**: Today the sequential path calls the five stage callables and discards their return values; it works only because each stage retrieves the `generated_files` and `logs` dicts and mutates those same objects. A model-driven stage naturally builds a new dict, which would leave the sequential path with an empty workspace — and the failure would present as a downstream security-audit or DevOps anomaly, not as a generation defect. Removing the aliasing dependency is a prerequisite for migrating the stages at all, which is why it sits in Phase 2 and not in Phase 3.

**Alternatives considered**:
- *Preserve the aliasing contract and document it.* Rejected: it is an undocumented implicit contract that a future contributor would break without noticing, and it makes the model-driven stages responsible for maintaining a behavior they have no reason to know about.
- *Delete the sequential path and route everything through the graph.* Rejected: out of scope; it would merge two features' concerns, and the sequential path has distinct pause/resume/guided-mode behavior that the graph path does not provide.

---

## D9. Generated build-configuration constraint

**Decision**: The set of dependencies a model may declare in generated build configuration is bounded by an explicit allowlist, seeded from the dependency set of the current known-good template.

**Rationale**: FR-017 exists because a non-deterministic generator can invent a dependency that the offline build environment cannot resolve. The failure is worse than a build error: the sandbox verifier's environment-fallback patterns include unresolved-dependency signatures, so a dependency mistake could be absorbed by the synthetic-success fallback and reported as a passing session. Bounding the allowlist removes the failure mode rather than detecting it.

Seeding from the existing template is the conservative choice: that dependency set is already known to resolve in the environment the platform ships with.

**Alternatives considered**:
- *Derive the allowlist from the Maven cache contents at runtime.* Rejected as the primary mechanism: it makes the allowed set environment-dependent and therefore makes a session's outcome depend on which host ran it — directly contrary to the platform's determinism principle. Retained only as a possible diagnostic.
- *Validate by attempting a build.* Rejected: too late; the build is outside this feature's gate, and the verifier is out of scope (Constraint 5).
- *Trust the instruction text to forbid new dependencies.* Rejected: an instruction is a request, not a constraint; FR-017 requires enforcement.

---

## D10. Non-determinism handling

**Decision**: Generated source is not expected to be byte-reproducible across runs. Provenance recording is the substitute for reproducibility. Model settings should be chosen to minimize variance, but no attempt is made to seed or otherwise force identical output.

**Rationale**: Byte-level reproducibility of a language model's output is not achievable with the platform's provider set and is not required by any success criterion. SC-002 is stated in terms of *semantic* correspondence between paired blueprints, which is evaluable without byte equality. Attempting byte reproducibility would push toward output caching, which reintroduces templates by another name (already rejected in the plan's Complexity Tracking).

**Consequence for the existing test suite**: the current end-to-end tests assert on template-specific strings. Those assertions remain valid for the offline path and must keep passing unchanged; they must not be relaxed or rewritten to accommodate model output. The model path gets its own suite, driven by the scripted fake client (D5), asserting on structural and behavioral properties rather than exact strings.

**Alternatives considered**:
- *Pin temperature to zero and require reproducibility.* Rejected: does not produce byte-identical output across providers or versions, and would create false confidence.
- *Cache model responses keyed by blueprint.* Rejected: turns the feature into a template cache; defeats SC-001 in practice by making repeated blueprints return stale output.

---

## D11. Where correctness verification happens during measurement

**Decision**: Any claim that generated code is *correct* is verified by building and testing the generated workspace directly, outside the platform's sandbox wrapper. The sandbox verifier is not used as a measurement instrument.

**Rationale**: The verifier can return a synthetic success without executing a build (documented in `reports/agentia-state-map.md`), and repairing it is explicitly out of scope (Constraint 5, FR-023). Using it as an instrument would produce measurements that cannot distinguish "the code is correct" from "the environment was unavailable". This is recorded as a measurement dependency in the plan so the distinction is not rediscovered during Phase 4.

**Alternatives considered**:
- *Fix the verifier first.* Rejected by the user's constraint: it is a separate bug, and sequencing the migration behind it would delay this feature for unrelated work.
- *Use session terminal status as the correctness signal.* Rejected: that signal is produced by the verifier, so it inherits the same flaw.

---

## Resolved unknowns

No `NEEDS CLARIFICATION` markers remain in the specification, and no unresolved item remains in the plan's Technical Context. The one governance question that is genuinely open — whether Constitution Principle V's three-iteration cap is a global autonomy budget or specifically the build-repair loop's cap — is **not** a technical unknown and is not resolvable by research. It is surfaced to the user in the plan's Constitution Check and Complexity Tracking, and is recorded there as unresolved by design.
## D12 — Principle V scope: build-repair loop only

Principle V specifies the autonomous correction budget with two binding
constraints: the trigger is "fallos de compilación o aserción en pruebas"
(build or test assertion failures), and the guidance source is
"exclusivamente el stack trace emitido por Maven."

Spec 011 introduces a generation-stage correction loop whose trigger is a
compliance verdict and whose guidance source is the constitutional
violation set. Neither condition matches Principle V's specification. The
loop is therefore not an "iteración de corrección automática" in the
Principle's sense.

Interpretation: Principle V bounds the Maven-triggered build-repair loop
specifically. The generation-stage correction loop is a distinct
mechanism with its own trigger and its own budget. The FR-009 requirement
that the two counters remain independent follows directly — they have
different triggers and different guidance sources, so they cannot be
the same counter.

Rejected alternative: read Principle V as a session-wide autonomy budget.
The text does not support this — both the trigger and the guidance source
are stated specifically, and neither matches the new loop. A session-wide
reading would also require reinterpreting "stack trace emitido por Maven"
as illustrative rather than definitional, which the phrase does not allow.

Consequence: a session may exhaust 3 build-repair attempts and 2
generation-stage corrections, reaching `Bloqueo por intervención humana
requerida` with 5 total autonomous attempts. The safety property is
preserved — both loops are individually bounded, both exhaust
deterministically to the same terminal state, and FR-010 reuses the
existing human-intervention path.

## D13 — Conservative severity merge; dual-severity baseline

The platform contains two independent constitutional validators with
overlapping rule sets and differing severities for the same violation
(Lombok @Data is MEDIUM in one family, HIGH in the other). The Spec 011
compliance adapter normalizes both verdicts and keeps the strictest
severity for each violation.

This converts previously-passing violations into blocking ones, which is
correct behavior — the lenient severity was under-reporting a real
violation. The behavior change is not caused by the migration but by the
gate becoming honest.

Consequence for measurement: SC-011 compares post-migration intervention
rate against the pre-migration baseline. Without correction, the severity
merge alone will appear as an SC-011 regression. Mitigation: the Phase 0
baseline script records BOTH the lenient verdict (pre-merge) and the strict
verdict (post-merge) for each captured session. Post-migration analysis
subtracts the lenient-to-strict delta to isolate the model-caused change.

Rejected alternative: defer the merge to a separate consolidation feature.
This leaves the two validators producing contradictory verdicts during the
migration, which makes FR-004 and FR-007 ("no non-compliant artifact is
persisted") unreliable — "compliant" would depend on which validator is
consulted. Merging now is the correct sequencing.