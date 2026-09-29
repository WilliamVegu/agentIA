# QE test matrix — AgentIA backend

Measured with `pytest-cov` over `backend/app`. Run it yourself:

```bash
.venv/bin/python -m pytest -q --cov=backend/app --cov-report=term-missing:skip-covered
cd frontend && npm test
```

The PM-facing write-up of the second campaign (Spanish, PDF) is
`docs/qe_plan_y_resultados.pdf`; its source is `docs/qe_plan_y_resultados.tex`. Raw run
logs and per-file coverage JSON live in `reports/qe/`.

---

## Campaign 2 — the three riskiest modules (this one)

Baseline: commit `2bddc0a`, the HEAD immediately before this campaign, run through the same
harness. 131 new tests.

| | Before | After |
| --- | --- | --- |
| Backend tests | 589 passed, 3 skipped | **720 passed, 3 skipped** |
| Frontend tests | 64 passed (10 files) | 64 passed (10 files) |
| Statements covered | 85.3% (6,752 statements, 994 missed) | **88.5% (776 missed)** |

| Module | Before | After | Why it was worth testing |
| --- | --- | --- | --- |
| `services/docker_service.py` | **52.7%** | **100.0%** | The deploy path the demo UI drives. Every branch decides what the operator is told about a container. `HEALTHY` is a *verification claim*: it is only honest if a real `/actuator/health` answered `UP`, and `docker compose up` exiting 0 only means the containers started. |
| `api/routes_session.py` | **71.3%** | **100.0%** | The product's main surface. The uncovered half was the *outcome* paths: what is persisted and broadcast when a run completes, completes as BLOCKED, or crashes. A crash must still terminate the session — otherwise the row stays `RUNNING` and the UI polls a dead session forever. |
| `services/lifecycle_service.py` | **76.4%** | **100.0%** | Phase gates, completion percentage, next action. Part of the uncovered surface was **unreachable** (see D-01). |
| `cost/mlflow_sink.py` | 100.0% (33 stmts) | **100.0% (42 stmts)** | Already fully covered; the D-03 fix added 9 statements, all covered. |

Files: `test_qe_deploy_docker.py` (33), `test_qe_session_surface.py` (50),
`test_qe_lifecycle_rules.py` (46), plus 2 in `test_cost_mlflow_mirror.py`.

### Three defects found — all by a test failing or hanging, none by reading

**D-03 (critical). The "best-effort" telemetry mirror blocked the critical path.**
`cost/mlflow_sink.py` calls itself "deliberately not on any critical path" and promises that
an unreachable destination "silently does nothing". It did not. MLflow's defaults are a
120 s HTTP timeout and 7 retries with exponential backoff — its own docs put that at ~4
minutes — and the destination defaults to `http://localhost:5000`. The caller is
`RecordingChatClient.invoke`, which wraps *every* model call, so a telemetry outage stalled
every generation session. It also made the backend suite **unable to complete at all**, so
coverage could not be measured. `_bound_the_transport()` now pins
`MLFLOW_HTTP_REQUEST_TIMEOUT=5` and `MLFLOW_HTTP_REQUEST_MAX_RETRIES=0` via `setdefault`.
The test that hung forever now takes 1.45 s.

**D-02 (high). The blocking reason was computed and discarded.**
Both BLOCKED paths assigned a local `blocked_reason`, but `PhaseState` is built from
`reason`. Nothing read `blocked_reason`, so a session stopped by the 3-attempt limit — or by
a failed quality gate — reached the UI as `BLOCKED` with `blockingReason: null`. The
operator saw the stop but not the cause. Both paths now assign `reason`.

**D-01 (medium). Two functions defined twice.**
`mark_downstream_outdated` and `clear_outdated_phases` were each defined twice in
`lifecycle_service.py` (lines 325/351 and 437/478). Python binds the last one, so the first
pair was dead code — 34 statements no test could ever reach. The contracts differed: the
shadowed `mark_downstream_outdated` returned `None` and *overwrote* the outdated set, while
the live one returns the accumulated list. The dead pair is removed.

### Harness change

`conftest.py` gained an autouse `no_outbound_telemetry` fixture that redirects
`MLFLOW_TRACKING_URI` to a throwaway local file store. Without it, any test driving the real
recording seam reaches the sink for real (D-03). It *redirects* rather than stubs, because
`test_the_local_store_is_written_even_when_the_mirror_is_absent` asserts the mirror really
was consulted — stubbing it would make that test vacuous. The address is patched on the
setting, not on `_tracking_uri`, so the helper stays under test.

---

## Campaign 1 — the untested surfaces (commit `7253d6d`)

Kept for history; its numbers were measured against the tree at that time and have since
moved on.

522 → **573 passed**, 82.6% → **84.6%**. `sandbox/verify_cache.py` 0.0% → 89.2%,
`services/git_service.py` 21.4% → 89.3%, `api/routes_requirements.py` 42.1% → 87.4%,
`orchestrator/repair.py` 63.2% → 100.0%. Two contracts were pinned after tests failed: the
git token is set on the remote for the push and scrubbed in a `finally` (so the scrub also
runs on a failed push), and `SpecificationDraft` requires at least 3 characters per
given/when/then clause. Those tests remain and still pass (67 tests across
`test_qe_api_surface.py`, `test_qe_environment_repair.py`, `test_qe_publish_git.py`,
`test_qe_schema_consistency.py`).

---

## Remaining gaps, ranked

| Module | Coverage | Missed | What is inside |
| --- | --- | --- | --- |
| `services/architecture_service.py` | 70.9% | 67 | OpenAPI/Mermaid serialisation and refinement. |
| `services/requirements_service.py` | 63.1% | 62 | The LLM decomposition/refinement paths. |
| `services/pipeline_runner.py` | 82.4% | 61 | Auto-pilot steps, pause/resume/cancel. |
| `services/model_sql_service.py` | 83.3% | 53 | JPA/DDL synthesis. |
| `orchestrator/stages/journal.py` | 70.9% | 44 | Journal serialisation and budget edges. |
| `orchestrator/stages/runner.py` | 91.6% | 34 | Stage dispatch. |
| `ssl_compat.py` | 25.6% | 29 | Import-time TLS compatibility — low value to chase. |

**Highest value next, in order:** `pipeline_runner.py` (the unattended Auto-Pilot path),
then `architecture_service.py` and `model_sql_service.py` (both produce deliverables, so a
serialisation bug is found late and by the client), then `journal.py`.

## What this coverage does *not* mean

Covered is not correct. The platform's own verification of generated code is
**self-referential** — it writes the Mockito tests and then runs them — so a green
`mvn test -o` proves the code does what the platform's own tests say, not what the
blueprint's acceptance scenarios say. Closing that gap is a separate deliverable
(independent HTTP acceptance tests, one per declared scenario, against the deployed
service).
