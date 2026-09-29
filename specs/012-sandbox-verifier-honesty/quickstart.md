# Quickstart — Sandbox Verifier Honesty

Validation guide for feature 012. Each scenario is independently runnable and maps to a success criterion. Nothing here requires a live model provider or network access (Constitution Principle VI).

---

## Prerequisites

| Requirement | Check | Expected |
| --- | --- | --- |
| Virtualenv present | `ls .venv/bin/python` | exists |
| Test runner works | `.venv/bin/python -m pytest --version` | prints a pytest version |
| Container daemon state known | `docker info >/dev/null 2>&1; echo $?` | see note below |

**Run all commands from the repository root.**

### Container daemon note — read before starting

The development host has a `podman-docker` CLI shim installed but **non-functional**:

```
Failed to obtain podman configuration: set sticky bit on:
chmod /run/user/1000/libpod: read-only file system
```

`docker info` therefore exits non-zero, and the platform's reachability check reports the daemon as unavailable. This is the **default-state** condition the feature is about, so scenarios 1, 2, 4, and 5 run natively here. **Scenario 3 cannot — it requires a host where `docker info` succeeds.** Do not treat scenario 3 as passing on this host.

The Hermetic Fallback switch:

```bash
# default (unset) is the honest path
echo "${ALLOW_HERMETIC_FALLBACK:-<unset>}"
```

---

## Scenario 1 — Docker absent, default config (SC-001)

**Purpose**: prove that an unverifiable workspace is never reported as verified.

**Setup**: no environment changes; daemon absent.

**Action**: run the honest-default suite.

```bash
.venv/bin/python -m pytest backend/tests/test_sandbox_verifier_honesty.py -v
```

**Expected**:

- Every fallback trigger returns a non-zero exit code and `fallback_used = True`.
- The result carries a non-empty reason.
- No synthetic `BUILD SUCCESS` text appears in the captured output.
- A session whose sandbox step cannot verify terminates in the **blocked** state with phase `FAILED`, and does **not** enter the repair loop.
- The recorded reason states that verification could not be performed — it does not read as a test or compilation failure.

**Failure looks like**: `exit_code == 0` for any trigger, or a session reaching the verified state, or the repair node being visited.

---

## Scenario 2 — Docker absent, permissive mode (SC-002)

**Purpose**: prove the opt-in switch restores the pre-change behavior, and that the marking survives.

**Setup**:

```bash
export ALLOW_HERMETIC_FALLBACK=true
```

**Action**:

```bash
.venv/bin/python -m pytest backend/tests/test_docker_runner.py -v
```

**Expected**:

- The three re-pointed fallback tests pass: synthetic success, exit code `0`, synthetic test counts.
- `fallback_used` is **still `True`** on every result, and the reason is still recorded (FR-007).
- A session in this mode may reach the verified state (Q1, Option A).

**Teardown**: `unset ALLOW_HERMETIC_FALLBACK` — leaving it set silently changes every later run.

**Failure looks like**: `fallback_used == False` in permissive mode (the audit blind spot FR-007 exists to prevent).

---

## Scenario 3 — Docker present, warmed cache (SC-003) — **TESTABLE ON THIS HOST**

**Purpose**: prove a real build actually runs when it can, with no substitution.

**Setup**: a `podman` backend behind the `docker` CLI shim, with `~/.m2/repository` warm (178 MB / 372 artifacts, including `surefire-junit-platform-3.1.2.jar`).

**Precondition check — do this first**:

```bash
docker info >/dev/null 2>&1 && echo "runtime reachable" || echo "runtime NOT reachable from this shell"
```

If this prints `NOT reachable` while the socket exists, you are in a shell whose sandbox makes the runtime's state directory read-only — see the caveat below. That is **not** the same as the daemon being absent, and it does **not** make the criterion fail.

**Action**: run a session to the sandbox step, twice — once against a workspace whose tests pass and once against one whose tests fail.

**Expected**:

- The real `mvn test -o` path executes inside the container.
- `fallback_used == False` on both runs.
- The passing workspace reports success with the **genuine** Maven output; the failing workspace reports failure. The pass/fail pair is the substance of SC-003: it proves the verifier can still tell a real pass from a real fail once the synthetic path is closed.
- No synthetic result is substituted.

### Caveat — the invoking shell, not the host

The runtime writes into its state directory (`/run/user/<uid>/libpod`) before serving any request. Under a restricted file sandbox that path is read-only and **every** `docker` invocation fails, so `check_docker_daemon()` returns `False` and the sandbox step honestly reports a fallback. Observed under such a sandbox:

```
Error: acquiring runtime init lock: open /run/user/1000/libpod/tmp/alive.lck:
read-only file system
```

If you hit this, SC-003 is **not verified by you**. Verify it from a shell that can reach the runtime, or explicitly grant that access. Do **not** mark it satisfied from someone else's report — asserting an unobserved result is exactly the failure this feature exists to remove.

---

## Scenario 4 — Offline generation path unchanged (SC-004)

**Purpose**: prove FR-004 — the fallback policy governs build substitution, not generation mode.

**Action**:

```bash
.venv/bin/python -m pytest backend/tests/test_generation_stages_offline.py -q
.venv/bin/python -m pytest -q
```

**Expected**:

- The offline suite passes **unmodified**.
- The full suite passes. Expected count: the pre-change total, adjusted only by the new and re-pointed verifier tests in `test_docker_runner.py` and `test_sandbox_verifier_honesty.py`.
- No offline session's terminal state or metrics differ from before.

**Failure looks like**: an offline session gaining `fallback_used`, or an offline terminal state changing.

---

## Scenario 5 — Marking visible to all consumers (SC-005)

**Purpose**: prove FR-005 across the metrics payload, the session detail endpoint, and the live stream.

**Action**: run the observability suite.

```bash
.venv/bin/python -m pytest backend/tests/test_sandbox_verifier_honesty.py -v -k "observab or metric or detail or stream"
```

**Expected**:

| Surface | Observation |
| --- | --- |
| Metrics payload | `fallback_used` present and `True` for a substituted attempt |
| Session detail (`GET /api/v1/sessions/{id}`) | `verificationFallbackUsed` is `True`; readable after a fresh database session, proving it survived a restart |
| Session detail, unknown metrics | degrades to `False` **without raising** |
| Live stream | a structured fallback field is present, not only a free-text log line |

---

## Scenario 6 — Measurement figures exclude unverified sessions (FR-008)

**Purpose**: prove that a permissive-mode "verified" session is excluded from published figures.

**Action**:

```bash
.venv/bin/python -m pytest backend/tests/test_generation_stage_measurement.py -q
```

**Expected**:

- The regenerated report under `reports/measurements/` records the number of sessions excluded for having used a fallback.
- No published figure includes a fallback-marked session, **even one that reached the verified state**.
- A session that reached the verified state via substitution is still excluded — the status is deliberately not the discriminator.

---

## Scenario 7 — The pre-existing test conflict is resolved, not hidden

**Purpose**: verify research.md D9 was implemented as planned rather than by weakening the requirement.

**Action**:

```bash
git diff --stat HEAD -- backend/tests/test_docker_runner.py
.venv/bin/python -m pytest backend/tests/test_docker_runner.py -v
```

**Expected**:

- The file is **modified** — three tests re-pointed at permissive mode rather than deleted or relaxed.
- With `ALLOW_HERMETIC_FALLBACK` unset, those three tests must **not** assert synthetic success.
- The synthetic-success assertions survive only under the permissive flag.

**Failure looks like**: the three tests deleted, or left asserting `exit_code == 0` under the default configuration — either would mean FR-001 was not actually implemented.

---

## Definition of Done

- [ ] Scenario 1 passes (SC-001)
- [ ] Scenario 2 passes (SC-002)
- [ ] Scenario 3 verified from a shell that can reach the runtime (SC-003); if the shell could not reach it, recorded as **not verified by the implementer** rather than assumed
- [ ] Scenario 4 passes; offline path unmodified (SC-004)
- [ ] Scenario 5 passes on all three surfaces (SC-005)
- [ ] Scenario 6 passes; excluded count recorded (SC-006)
- [ ] Ambiguous condition-4 substitutions record the matched pattern (SC-007)
- [ ] Scenario 7 confirms `test_docker_runner.py` was re-pointed, not gutted
- [ ] Full suite passes; `graph.py` and the repair loop are unchanged
- [ ] No open `NEEDS CLARIFICATION` remains in [spec.md](spec.md)
