# Testing Examples — Microservice Code Studio

Companion to the runnable examples in
[`backend/tests/test_app_examples.py`](backend/tests/test_app_examples.py).
That file contains 29 working tests, one per technique; this document explains
how to run them, how the isolation works, and how to test the app by hand.

---

## 1. Running the suite

```bash
# Everything (uses pytest.ini: testpaths=backend/tests, pythonpath=backend)
.venv/bin/python -m pytest

# Just the illustrative examples
.venv/bin/python -m pytest backend/tests/test_app_examples.py -v

# One test, or one group
.venv/bin/python -m pytest backend/tests/test_app_examples.py -k "security or secret" -v

# Stop at the first failure and show the full assertion
.venv/bin/python -m pytest backend/tests/test_app_examples.py -x --tb=long

# Slowest tests first (useful when the suite grows)
.venv/bin/python -m pytest backend/tests --durations=10

# Coverage of the app package only
.venv/bin/python -m pytest backend/tests --cov=app --cov-report=term-missing
```

`pytest.ini` already sets `pythonpath = backend`, so tests import
`from app.main import app` without any `sys.path` juggling.

---

## 2. The test levels used in this project

| Level | What it proves | Example in the file |
| --- | --- | --- |
| Smoke | The app imports and serves | `test_example_smoke_health_endpoint` |
| API / contract | Status codes, payload shape, error envelope | `test_example_submit_blueprint_json`, `test_example_invalid_blueprint_uses_error_envelope` |
| Workspace / filesystem | Endpoints write the expected files | `test_example_quick_start_creates_session_and_spec` |
| LLM-backed, offline | AI features work with the mock engine | `test_example_requirements_transform_offline_mock` |
| Security / quality | SAST, secrets, CVE, quality gate | `test_example_security_audit_blocks_secret_and_injection` |
| State machine | Lifecycle transitions and their guards | `test_example_lifecycle_and_phase_transition` |
| External boundary | Git publish without touching a server | `test_example_publish_to_git_with_mocked_boundary` |
| Pure unit | Parsers and rules with no I/O | `test_example_unit_parse_maven_compilation_error` |
| Parametrized | One rule across many inputs | `test_example_parametrized_service_names` |
| Internals | Pipeline steps with one dependency mocked | `test_example_pipeline_stops_at_blocked_quality_gate` |

---

## 3. The three isolation rules

These three habits keep the examples fast, deterministic, and non-destructive.

### Rule 1 — The database is already isolated

[`backend/tests/conftest.py`](backend/tests/conftest.py) installs an
`autouse`, session-scoped fixture that rebinds `SessionLocal` to a temporary
SQLite file. You never need to reset `backend/studio.db` yourself:

```python
from app.models.session import GenerationSessionDB, SessionLocal

def test_reading_sessions():
    db = SessionLocal()
    try:
        assert db.query(GenerationSessionDB).limit(1).count() <= 1
    finally:
        db.close()
```

Rows you insert are yours to clean up (use `try/finally`):

```python
def _delete_session(session_id: str) -> None:
    db = SessionLocal()
    try:
        db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).delete()
        db.commit()
    finally:
        db.close()
```

### Rule 2 — Redirect `WORKSPACE_DIR` before anything generates code

Endpoints such as `/sessions/quick-start` and the pipeline write into
`settings.WORKSPACE_DIR`. Point it at `tmp_path` so `backend/workspaces/`
stays clean:

```python
def test_quick_start(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "WORKSPACE_DIR", str(tmp_path))
    response = client.post("/api/v1/sessions/quick-start", json={"serviceName": "order-service"})
    assert (tmp_path / response.json()["sessionId"] / "spec.md").exists()
```

### Rule 3 — Never call a real LLM or a real Git remote

Use `provider="mock"` (deterministic, zero cost, offline) or monkeypatch the
single boundary function:

```python
monkeypatch.setattr(routes_publish, "publish_to_git", fake_publish_to_git)
```

The mock engine is selected automatically for `provider="mock"`, for any key
containing `mock` (`mock-key`, `test-key`), or when `ALLOW_OFFLINE_MOCK=True`.

---

## 4. Copy-paste recipes

### Quick-start a session (the fastest end-to-end entry point)

```python
payload = {
    "serviceName": "inventory-service",
    "rawText": "Manage stock levels, warehouse items, and low-inventory alerts.",
    "databaseEngine": "POSTGRESQL",
    "autoRun": False,          # True starts the pipeline in a background thread
}
response = client.post("/api/v1/sessions/quick-start", json=payload)
assert response.status_code == 201
```

Empty payloads are valid and fall back to `app-service`.

### Ingest a blueprint and audit it

```python
spec = client.post("/api/v1/specifications", json=blueprint).json()   # 201
audit = client.post("/api/v1/security/audit", json={
    "serviceName": spec["serviceName"],
    "files": {"src/main/java/.../Dto.java": source_code},
    "pomXml": "<project></project>",
}).json()
assert audit["qualityGate"]["status"] in ("PASS", "BLOCKED")
```

### Guard the export path

The quality gate is enforced at export and publish time, not just reported:

```python
assert client.get(f"/api/v1/sessions/{sid}/audit").json()["qualityGate"]["status"] == "BLOCKED"
assert client.get(f"/api/v1/sessions/{sid}/export").status_code == 403
assert client.post(f"/api/v1/sessions/{sid}/publish", json={...}).status_code == 403
```

### Drive the lifecycle state machine

```python
lifecycle = client.get(f"/api/v1/orchestrator/sessions/{sid}/lifecycle").json()
assert len(lifecycle["phases"]) == 7

# Prerequisites are enforced: this 400s until spec.md exists
client.post(f"/api/v1/orchestrator/sessions/{sid}/transition",
            json={"targetPhase": "STORIES", "force": False})
```

### Parametrize instead of copy-pasting

```python
@pytest.mark.parametrize("service_name, expected", [
    ("order-service", "order-service"),
    ("", "app-service"),
])
def test_names(tmp_path, monkeypatch, service_name, expected):
    monkeypatch.setattr(settings, "WORKSPACE_DIR", str(tmp_path))
    ...
```

---

## 5. Testing by hand against a running server

Start the backend (from the repo root):

```bash
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

Then:

```bash
# 1. Health
curl -s http://localhost:8000/healthz | jq

# 2. Cheap session
SID=$(curl -s -X POST http://localhost:8000/api/v1/sessions/quick-start \
  -H 'Content-Type: application/json' \
  -d '{"serviceName":"demo-service","rawText":"Track demo items with reorder alerts."}' | jq -r .sessionId)
echo "$SID"

# 3. Interactive API docs (all routes, all schemas)
xdg-open http://localhost:8000/docs

# 4. Requirements with the offline mock engine (no API key needed)
curl -s -X POST http://localhost:8000/api/v1/requirements/transform \
  -H 'Content-Type: application/json' \
  -d '{"serviceName":"order-service","provider":"mock","rawText":"Gestionar órdenes de compra con email y monto."}' | jq '.userStories | length'

# 5. Upload a Spec Kit markdown file
curl -s -X POST http://localhost:8000/api/v1/specifications/upload \
  -F 'file=@specs/001-microservice-code-studio/spec.md' | jq

# 6. Security audit of the generated workspace
curl -s -X POST http://localhost:8000/api/v1/security/audit \
  -H 'Content-Type: application/json' \
  -d '{"serviceName":"demo","files":{"src/main/resources/application.yml":"openai: sk-proj-12345678901234567890abcdef"},"pomXml":"<project></project>"}' \
  | jq '.qualityGate.status'          # -> "BLOCKED"

# 7. Session detail / audit / export
curl -s "http://localhost:8000/api/v1/sessions/$SID" | jq
curl -s "http://localhost:8000/api/v1/sessions/$SID/audit" | jq '.qualityGate'
curl -s -o demo.zip -w '%{http_code}\n' "http://localhost:8000/api/v1/sessions/$SID/export"

# 8. Live SSE log feed (Ctrl-C to stop)
curl -N "http://localhost:8000/api/v1/sessions/$SID/stream"
```

> **Why curl for SSE?** A live SSE response keeps emitting keepalives, so
> reading it with `TestClient` inside pytest blocks forever. Assert the stream
> contract in-process (history/404) and use `curl -N` for the live behaviour.
> `test_example_sse_event_history_is_recorded` shows the in-process version.

---

## 6. Frontend checks

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
npm run build      # production build must succeed
npm run lint       # if configured
```

Smoke checklist for the UI: create a 1-Click session, watch the live monitor,
open the code explorer, run the security audit, generate DevOps assets, and
download the ZIP.

---

## 7. Checklist before adding a real test

- [ ] Does it assert **behaviour** (status, payload, files), not implementation details?
- [ ] Does it isolate state (`tmp_path` for workspaces, cleanup for DB rows)?
- [ ] Does it avoid the network and real credentials (`provider="mock"` or a monkeypatched boundary)?
- [ ] Would it fail if the feature broke? (Try inverting the assertion once.)
- [ ] Is the name a sentence about the rule, e.g. `test_export_blocked_when_quality_gate_fails`?
- [ ] Does it run in well under a second? Slow tests belong behind a marker.
