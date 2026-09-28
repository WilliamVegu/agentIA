# Phase 0 Research — Sandbox Verifier Honesty

All Technical Context unknowns were resolved by direct inspection of the repository; no agent dispatch was required and no `NEEDS CLARIFICATION` item remains. Each decision below records what was chosen, why, and what was rejected.

---

## D1 — Configuration flag shape

**Decision**: Add `ALLOW_HERMETIC_FALLBACK: bool = False` to `backend/app/config.py`'s `Settings` class.

**Rationale**: `Settings` is a `pydantic-settings` `BaseSettings` with `env_file=".env"` and `extra="ignore"`, so a plain annotated field with a default is automatically overridable by the environment variable of the same name. A near-identical precedent already exists: `ALLOW_OFFLINE_MOCK: bool = Field(default=False, ...)`. The spec's "default is honest failure" therefore needs no special handling — a false default *is* the honest default, and the spec's requirement that an unrecognized value fail safe comes free from pydantic's boolean coercion.

**Alternatives considered**:
- *Read `os.environ` directly at the call site.* Rejected: bypasses the settings object, is not testable by the established `Settings` override pattern, and duplicates configuration handling.
- *A `DOCKER_FALLBACK_MODE: str` enum (`allow` / `deny`).* Rejected as speculative generality: FR-002 asks for an opt-in switch, and a boolean expresses it exactly. A string mode would invite a third state no requirement asks for.

---

## D2 — Verification result field set

**Decision**: `DockerExecutionResult` (in `backend/app/sandbox/docker_runner.py`) gains:

| Field | Type | Purpose |
| --- | --- | --- |
| `fallback_used` | `bool` (default `False`) | The marking every consumer branches on (FR-001, FR-005) |
| `fallback_reason` | `Optional[str]` | Human-readable reason, carried into the session's recorded reason (FR-003) |
| `matched_pattern` | `Optional[str]` | Which recognised pattern triggered an ambiguous classification (FR-009) |
| `attribution_ambiguous` | `bool` (default `False`) | Whether the cause could be environment *or* project-authoring (FR-009) |

**Rationale**: `fallback_used` is a pure fact about how the result was produced, and it is the single discriminator the rest of the system needs. `matched_pattern` and `attribution_ambiguous` exist because Q2 chose to record the ambiguity rather than resolve it: without them the operator cannot tell a broken build file from a missing image, and the spec's SC-007 would be untestable. Defaults keep the model backward-compatible, so existing constructions (including the pre-existing `test_docker_execution_result_model`) remain valid.

**Alternatives considered**:
- *Reuse `stderr` to carry the reason.* Rejected: overloading an output field for control data makes the reason unparseable and couples consumers to log formatting.
- *An enum `VerificationOutcome = VERIFIED | FAILED | COULD_NOT_VERIFY`.* Considered and rejected **in this position**: it duplicates information already derivable from `(exit_code, fallback_used)` and would need a migration across every consumer. Note the *specification* does express the three-way distinction ("could not verify" vs "verified and failed" vs "verified and passed"); the plan represents it with two orthogonal fields rather than an enum, which keeps the change additive.

---

## D3 — Unified fallback policy

**Decision**: Replace `_build_hermetic_fallback_result` with a single policy function that every substitution site calls. It branches on `settings.ALLOW_HERMETIC_FALLBACK`:

- **Permitted** → legacy behavior: `exit_code = 0`, the synthetic stdout, `fallback_used = True`.
- **Not permitted** → `exit_code = 1`, **no** synthetic stdout, `fallback_used = True`, `fallback_reason` set.

All **four** existing call sites route through it. Investigation found four, not the three named in the input:

| # | Trigger | Current line |
| --- | --- | --- |
| 1 | Daemon unreachable (`check_docker_daemon()` false) | ~95 |
| 2 | `FileNotFoundError` — `docker` binary absent | ~134 |
| 3 | Runtime/daemon/pipe/connection error during execution | ~149 |
| 4 | Build failed **and** output matched an environment pattern | ~188 |

**Rationale**: FR-006 requires none of these to remain a silent success, and the spec's Input note named only three. Trigger 4 is the most severe: it converts a genuine build failure into a synthetic success, which is a false *pass*, not merely a missing verification. Unifying the four sites also removes the duplicated substitution block, which Principle III favours.

**Alternatives considered**:
- *Gate only the daemon-unavailable path.* Rejected: leaves three silent-success paths, contradicting FR-006.
- *Delete the fallback entirely.* Rejected: FR-002 requires it be retained behind the switch so offline development still works.

---

## D4 — No change to `graph.py`

**Decision**: `backend/app/orchestrator/graph.py` is **not modified**.

**Rationale**: `_route_after_sandbox` already reads:

```python
if state.get("build_success", False):      return END
if state.get("status") == "BLOCKED":       return END
return "repair"
```

So a sandbox result that sets `status = BLOCKED` and leaves `build_success` false already routes straight to `END`, bypassing the repair node. FR-003's required outcome — terminate in the human-intervention state, do not enter repair — is therefore reachable without touching the graph, which also preserves feature 011's FR-023 "repair loop behavior unchanged" boundary exactly.

**Alternatives considered**:
- *Add a dedicated `unverifiable` routing key.* Rejected as unnecessary: the existing `BLOCKED` branch does the job, and adding a second terminal route would duplicate it.
- *Let the session fall into the repair loop and block there.* Rejected: it burns repair attempts on an environment fault that no code patch can fix (`repair_node`'s cap is 5), produces misleading Maven-failure diagnostics, and misreports the cause.

---

## D5 — The state key for the recorded reason

**Decision**: `sandbox_node` sets the **`error`** state key with the fallback reason.

**Rationale**: `routes_session.py`'s blocked branch reads `final_state.get("error", "Human intervention required")` and persists it into `db_sess.error_message`. Using any other key (for example `error_message`, which is the *column* name) would silently discard the reason and defeat FR-003's "the reason MUST be recorded on the session". This is a genuine trap: the column and the state key have different names.

**Alternatives considered**: none — this is a factual constraint discovered by reading the persistence path.

---

## D6 — Metrics field

**Decision**: `VerificationMetrics` (in `backend/app/models/artifact.py`) gains `fallback_used: bool = False` and `fallback_reason: Optional[str] = None`.

**Rationale**: FR-005 requires the metrics payload to carry the marking so callers can branch on it. `VerificationMetrics` is a pydantic model already serialized into the agent state via `model_dump()` and already surfaced to consumers, so an additive optional field propagates everywhere without touching call sites. Defaults keep every existing construction valid.

**Alternatives considered**:
- *A separate sibling model.* Rejected: it would force every consumer to look in two places for one outcome.

---

## D7 — Persisting the marking for the session detail endpoint

**Decision**: Add a `verification_metrics_json` column to `GenerationSessionDB` and expose the flag on `GenerationSessionDetail`, registered through the existing idempotent additive-column mechanism (`_ensure_generation_columns` in `app/models/session.py`).

**Rationale**: The session detail endpoint reads from the database, and no column currently holds verification metrics — `test_metrics` lives only in the in-process agent state. Feature 011's T013 established precisely this pattern: purely additive `ALTER TABLE ... ADD COLUMN` guarded by a `PRAGMA table_info` check, wrapped in a swallow-and-continue, so an existing `studio.db` picks up the column with no migration tool. Reusing it is the repo's documented convention rather than a new mechanism.

**Alternatives considered**:
- *Write a verification-result JSON file into the workspace and have the detail endpoint read it.* Precedent exists (`security_audit_report.json` is written by `audit_workspace`), but it couples an API read to workspace filesystem state and would break for a session whose workspace was cleaned up. The database is the right home for session-scoped metadata.
- *Derive the flag from `error_message` text.* Rejected: string-sniffing for control flow is fragile and unqueryable.
- *Reuse `phase_progress_json`.* Rejected: its documented meaning is phase progress, and the additive-column docstring explicitly commits to keeping that meaning.

---

## D8 — Measurement filtering (FR-008)

**Decision**: The measurement harness (`backend/tests/test_generation_stage_measurement.py`) excludes fallback-marked sessions from its figures, and the exclusion count is recorded in the generated report.

**Rationale**: Q1 chose to let permissive mode reach `VERIFIED`, which means the terminal state alone no longer proves verification occurred. FR-008 therefore has to be enforced where figures are computed. Recording the excluded count keeps the filter auditable rather than invisible — a silent filter is its own honesty problem.

**Alternatives considered**:
- *Filter inside the metric definition rather than at the consumer.* Rejected: the metric layer has no access to the verification marking, and centralising the filter there would hide it from the operators who need to know how many sessions were dropped.

---

## D9 — The pre-existing test conflict (the one unavoidable break)

**Decision**: `backend/tests/test_docker_runner.py` is **updated**. Its three synthetic-success tests are re-pointed at permissive mode (monkeypatching the flag on), and new tests assert the honest default.

**Rationale**: This is not an incidental break — it is the crux of the feature. These three tests currently encode the bug as required behavior:

| Test | Current assertion | Conflict |
| --- | --- | --- |
| `test_run_docker_sandbox_daemon_offline_fallback` | `exit_code == 0`, `is_success is True`, "BUILD SUCCESS" in stdout, daemon offline | Directly contradicts FR-001 |
| `test_run_docker_sandbox_daemon_pipe_error_fallback` | `exit_code == 0` on a pipe error | Directly contradicts FR-001/FR-006 |
| `test_run_docker_sandbox_image_missing_fallback` | `exit_code == 0` on a missing image | Directly contradicts FR-001/FR-006 |

They cannot "keep passing unchanged" while FR-001 holds. Re-pointing rather than deleting them preserves all three as coverage of the *permissive* path, which is exactly what FR-002 needs tested, and the new default-config tests cover the honest path. Net coverage increases.

**Alternatives considered**:
- *Leave them and add new tests.* Rejected: the suite would then assert both `exit_code == 0` and `exit_code != 0` for the same condition, so at least one is guaranteed to be wrong and the suite would be self-contradictory.
- *Delete them.* Rejected: it discards the only existing coverage of the fallback construction path, which FR-002 still requires.

**Planning consequence**: this must be the *first* implementation task, not a later one. Any agent implementing the core change will see this file go red and must not respond by weakening FR-001.

---

## D10 — SC-003 cannot be verified on the development host

**Decision**: SC-003 (real runtime present, warmed cache → real build, `fallback_used = False`) is recorded as **deferred/unverified** unless a host with a working container runtime is available. It is never claimed on the strength of the current host.

**Rationale**: Measured during specification. The host has a `podman-docker` CLI shim, but it fails to initialise:

```
Failed to obtain podman configuration: set sticky bit on:
chmod /run/user/1000/libpod: read-only file system
```

`check_docker_daemon()` runs `docker info` with a 2-second timeout and returns `False` on any non-zero exit, so the platform correctly reports the daemon as unavailable. `~/.m2/repository` is warming as expected (178 MB, 372 artifacts), but a warm cache without a runtime still cannot build.

**Consequence for planning**: SC-001, SC-002, SC-004, and SC-005 are fully testable on this host (they need the daemon to be *absent*, which it is). SC-003 needs a host where `docker info` succeeds. The quickstart marks it explicitly so the gap cannot be mistaken for a pass.

**Alternatives considered**:
- *Treat the shim as "Docker present" and assert a real build.* Rejected outright: it would fail, and asserting around the failure would be the same dishonesty this feature exists to remove.
- *Skip SC-003 silently.* Rejected: an unrecorded gap is indistinguishable from a satisfied one.

---

## Summary of decisions

| ID | Decision | Primary requirement |
| --- | --- | --- |
| D1 | `ALLOW_HERMETIC_FALLBACK: bool = False` in `Settings` | FR-002 |
| D2 | 4 new fields on `DockerExecutionResult` | FR-001, FR-009 |
| D3 | One policy function behind all 4 substitution sites | FR-001, FR-006 |
| D4 | `graph.py` unchanged — `BLOCKED` already routes to `END` | FR-003 |
| D5 | Reason goes in the `error` state key | FR-003 |
| D6 | `VerificationMetrics.fallback_used` | FR-005 |
| D7 | Additive `verification_metrics_json` column + detail field | FR-005 |
| D8 | Measurement harness filters on `fallback_used = False` | FR-008 |
| D9 | `test_docker_runner.py` re-pointed at permissive mode (first task) | FR-001, FR-002 |
| D10 | SC-003 recorded as deferred on this host | SC-003 |

No open questions remain. All Technical Context unknowns are resolved.
