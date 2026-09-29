# Constitution Check — feature 013 (Cost Tracing)

Companion to [plan.md](plan.md) § Constitution Check. Records the gate evaluation, the branch exception for a third stacked feature, and the two constraints that shape implementation sequencing.

---

## 1. Gate evaluation

All six principles are satisfied. **No Complexity Tracking entries are required** — the design removes duplication (one recording proxy, one pricing lookup, one authoritative store) rather than adding it.

| Principle | Bearing | Verdict |
| --- | --- | --- |
| I. Arquitectura en Capas Estricta | None. Layering is a property of generated Java; this feature touches orchestration only. | **PASS** |
| II. Contratos Inmutables y Validación Temprana | None. No DTO or generated contract changes. | **PASS** |
| III. Manejo Centralizado de Excepciones y Limpieza de Código | One recording path and one pricing lookup are shared rather than duplicated at each call site. Every branch — usage known/unknown, priced/unpriced, cache hit/miss, sync/async — is exercised by a test, so no branch is dead. | **PASS** |
| IV. Determinismo Offline-First y Aislamiento en Sandbox | The report is offline and deterministic over the local store and makes no live call. Recording writes locally first, so it adds no network dependency to any path. The peak/off-peak basis is computed from a timestamp already on the call, not fetched. | **PASS** |
| V. Quality Gates y Ciclo Acotado de Auto-Reparación | FR-007 excludes sessions whose verification was synthetic from the completed-session cost average — the honesty constraint feature 012 established, applied to money. A session that was not genuinely verified is not a completed generation and must not be priced as one. The bounded-repair cap is untouched; correction attempts are recorded as real spend, which is what "bounded" is for. | **PASS** |
| VI. Seguridad de Secretos y Frontera del Orchestrator | Two testable requirements: no credential may appear in any cost record, report line, or telemetry parameter (the wrapper sits directly beside the credential, which is where leaking it is easiest); and the wrapper wraps the **orchestration-side** client only, adding nothing to the generated artifact's dependency surface. The suite makes zero provider calls. | **PASS** |

---

## 2. Deliberate exception — branch isolation, third stacked feature

**Decision**: feature 013 is implemented on `feature/011-llm-generation-nodes`, which already carries 011 and 012. **No dedicated branch.**

**Convention being departed from**: each feature normally gets its own branch so review and merge boundaries align with feature boundaries.

**Rationale — the requirement the convention protects is preserved.** That requirement is that the integration branch (`main`) is never modified by in-progress work, and it holds:

- **`main` is untouched.** None of the three features has merged.
- **Three features in the same arc.** 011 built the LLM-driven generation stages and the stage execution boundary; 012 made the sandbox verifier honest; 013 measures what the generation calls cost. Each is a direct consequence of the one before.
- **The isolation benefit of splitting is zero.** Nothing merges to `main` either way. Creating a branch now would mean rebasing three features' commits to buy nothing.
- **Splitting would yield branches that are not independently green.** 013 depends on 011's stage boundary to establish the recording context and on 012's verification-fallback marking for the report's exclusion rule. A branch carrying 013 alone would not have a passing test suite, which makes it a worse review unit, not a better one.

**Risk accepted, and its mitigation**: one branch now carries three features' worth of review surface. Mitigation is that the commits remain separable and ordered by feature — 011 culminates at `a7ef45d`, 012 at `fbe39d6`, and 013's specification and plan follow — so the stack can still be reviewed commit-by-commit, and the features can be split retroactively if required.

**Reversal**: a dedicated branch can still be created before 013's implementation begins. Nothing in the feature depends on the branch name.

This follows [012's recorded exception](../../012-sandbox-verifier-honesty/constitution-recheck.md) §2, which covered the first two features of the arc.

---

## 3. Sequencing constraints that carry constitutional weight

Two implementation-order constraints are recorded here because violating either would produce a feature that *looks* verified without being verified — the failure mode this project's specifications have consistently refused.

### 3.1 The usage-reporting fake comes first (research D12)

The existing fake reports no token usage, so every recording assertion written before it is extended would exercise only the unknown-usage path. SC-001 claims ten sessions produce records with **non-zero** token counts; without the extension that claim is untestable, and every downstream task reading a recorded token count is unverifiable.

**Constraint**: the fake is **extended, not reshaped**. Existing tests assert on `.content` and `.calls`, so usage metadata is additive and defaulted, and **no pre-existing assertion may be weakened** to accommodate it. A later task that wants to relax a pre-existing test is a signal the extension was done wrong.

### 3.2 The wrapper must not break a partial-interface client (research D11)

The fake implements only the synchronous entry point. A wrapper that unconditionally forwards an asynchronous call would raise. The chosen fallback delegates the async call to the synchronous implementation and **records it**, rather than passing it through unrecorded: a call that happens is a call that costs, and a silent pass-through would be a second, quieter form of the silent-spend problem this feature exists to close.

**Constraint**: the behaviour must be documented (the two options have different recording semantics), and a test must assert **both** that it does not raise **and** that the documented recording behaviour occurred. Asserting only "does not raise" would let the recording silently disappear later.

---

## 4. Post-design re-check

Re-evaluated after Phase 1 design. **Verdict unchanged: all six principles satisfied.** The two decisions carrying the most constitutional weight:

- **The local store is authoritative and the telemetry destination is a mirror** — approved, and now stated directly in FR-005 rather than inferred from ambiguous wording. This is what makes Principle IV's determinism requirement hold for the report even when an external service is unavailable.
- **Unknown is never recorded as zero** — for tokens, for cost, and for pricing. A missing value is reported as missing and counted, on the same reasoning that made feature 012 refuse a synthetic verification success. A zero is a claim; an absence is not.

**No new violations. No Complexity Tracking entries added.**
