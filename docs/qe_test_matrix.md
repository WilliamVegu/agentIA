# QE test matrix — AgentIA backend

Measured with `pytest-cov` over `backend/app`. Run it yourself:

```bash
.venv/bin/python -m pytest -q --cov=backend/app --cov-report=term-missing:skip-covered
```

| | Before this batch | After |
| --- | --- | --- |
| Backend tests | 522 passed, 3 skipped | **573 passed, 3 skipped** |
| Frontend tests | 64 passed (10 files) | 64 passed |
| Statements covered | 82.6% (6,700 statements, 1,163 missed) | **84.6% (1,034 missed)** |

---

## 1. What the batch covered

| Module | Before | After | Why it was worth testing |
| --- | --- | --- | --- |
| `sandbox/verify_cache.py` | **0.0%** | **89.2%** | Decides whether a host can run the hermetic sandbox at all. A false "ready" sends a session into a build that cannot run; a false "not installed" blocks a capable host. Every branch is now exercised with `subprocess.run` faked — no container is executed. |
| `services/git_service.py` | **21.4%** | **89.3%** | The uncovered 79% handled the ephemeral PAT. Principle VI says the token is never persisted, so the tests assert the token **does not survive in the repository config** — after a successful publish *and* after a failed one, and that it never appears in an error message. |
| `api/routes_requirements.py` | **42.1%** | **87.4%** | The endpoints the UI uses to read back and save a requirements draft: the 404 for an unknown session, the no-draft case, a corrupt `user_stories.json`, and the save path. |
| `orchestrator/repair.py` | **63.2%** | **100.0%** | The fallback ladder — what the Maven parser returns when output does not match the strict patterns. That is precisely when a diagnostic matters. |
| `main.py` (error envelope) | 67.9% | 69.2% | Principle III makes the error envelope a contract. Both handlers are now asserted directly, plus one end-to-end 400 through the ASGI stack. |

Files: `test_qe_environment_repair.py` (25), `test_qe_publish_git.py` (15), `test_qe_api_surface.py` (11).

## 2. Two real contracts found while writing them

Both were discovered by the tests failing, not by reading the code:

- **`git_service`:** the token *is* set on the remote for the push and *is* scrubbed in a `finally` block — so the scrub also runs on a failed push. That is the guarantee worth pinning, and a naive test that stubbed only `create_remote` would have passed while checking nothing, because the scrub re-reads the remote via `repo.remote()`.
- **`SpecificationDraft`:** `given` / `when` / `then` each require **at least 3 characters**. A client posting placeholder text gets the 400 envelope and nothing is persisted. Pinned as a test.

## 3. Remaining gaps, ranked

| Module | Coverage | Missed | What is inside |
| --- | --- | --- | --- |
| `services/docker_service.py` | **40.4%** | 87 | local deploy/stop/status, health polling, log streaming. Shells out to the runtime — tests must fake the boundary. |
| `api/routes_session.py` | 69.9% | 82 | session lifecycle, the SSE stream, the generation pipeline entry point. |
| `services/lifecycle_service.py` | 76.4% | 71 | phase transition rules and completion percentages. |
| `services/architecture_service.py` | 70.9% | 67 | OpenAPI/Mermaid serialisation and refinement. |
| `services/requirements_service.py` | 63.1% | 62 | the LLM decomposition/refinement paths. |
| `services/pipeline_runner.py` | 82.3% | 61 | auto-pilot steps, pause/resume/cancel. |
| `services/model_sql_service.py` | 81.8% | 52 | JPA/DDL synthesis. |
| `orchestrator/stages/journal.py` | 70.9% | 44 | journal serialisation and budget edges. |
| `ssl_compat.py` | 25.6% | 29 | import-time TLS compatibility — low value to chase. |

**Highest value next, in order:** `docker_service.py` (the deploy path the demo UI drives, and the least covered module of any real size), then `routes_session.py` (the product's main surface), then `lifecycle_service.py` (the phase rules every session obeys).

## 4. What this coverage does *not* mean

Covered is not correct. The platform's own verification of generated code is **self-referential** — it writes the Mockito tests and then runs them — so a green `mvn test -o` proves the code does what the platform's own tests say, not what the blueprint's acceptance scenarios say. Closing that gap is a separate deliverable (independent HTTP acceptance tests, one per declared scenario, against the deployed service).
