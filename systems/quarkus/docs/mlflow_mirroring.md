# MLflow mirroring — how telemetry leaves the platform (and why it is optional)

**Status on this host: the mirror is wired and inactive.** `mlflow` is not
installed, so every mirror attempt returns `False` and records a reason. This is
the designed behaviour, not a fault: **no code change is needed** to enable it.

---

## 1. What the mirror is, and what it is not

| | Role |
| --- | --- |
| `backend/cost_tracking.db` | **System of record.** Every call record is written here first. The cost report reads only this. |
| `MLFLOW_TRACKING_URI` (default `http://localhost:5000`) | **Best-effort mirror.** A convenience destination. Never read back. |

The mirror exists so cost telemetry can be inspected in a UI when one is
available. It is deliberately **off every critical path**:

- `cost/recording.py::_record_call` writes the local store, **then** calls
  `mirror_call_record(record)`.
- `cost/mlflow_sink.py::_record` catches everything. A missing library, an
  unreachable server, or a rejected write all return `False` and append a reason
  to `mirror_failures()`.
- Nothing decides anything based on the mirror's result. `_record_call` wraps the
  whole thing in its own `try/except` as well.

This is feature 013's decision (FR-005): making the local store authoritative is
what keeps the cost figures deterministic and offline, and it is what makes a
telemetry outage a non-event rather than a data-loss event.

The behaviour is pinned by `backend/tests/test_cost_mlflow_mirror.py`:

- the absent library returns `False`, records a reason, and does not raise;
- a destination that raises is also a non-event;
- **the local store is written even when the mirror is absent** — the property
  that makes the destination optional rather than load-bearing;
- a credential is never forwarded. The sink sends scalar metrics plus the
  identifier tags `session_id`, `stage`, `provider`, `model`, `pricing_basis`
  only. The recording site sits directly beside the API key, so this is asserted
  rather than assumed.

---

## 2. Why this host shows `False`

```
$ .venv/bin/python -c "import mlflow"
ModuleNotFoundError: No module named 'mlflow'
```

`mlflow_sink._record` imports `mlflow` **lazily**, inside the function, and
catches the `ImportError`. That is intentional: the library is not a platform
dependency, so the application must start and record costs without it.

To see the recorded reasons for any run:

```python
from app.cost.mlflow_sink import mirror_failures
print(mirror_failures())
# ['call: telemetry library unavailable (ModuleNotFoundError)']
```

---

## 3. Enabling it (operator steps)

These steps install a package and start a server, so they belong to the operator.
Run them from the repository root.

```bash
# 1. Install the client into the platform's virtualenv
.venv/bin/python -m pip install mlflow

# 2. Start a tracking server (SQLite-backed, files under ./mlruns by default)
.venv/bin/mlflow server \
  --backend-store-uri sqlite:///mlflow.db \
  --default-artifact-root ./mlruns \
  --host 127.0.0.1 --port 5000

# 3. Point the platform at it (backend/.env is loaded by load_dotenv)
echo 'MLFLOW_TRACKING_URI=http://127.0.0.1:5000' >> backend/.env

# 4. Run any session that makes a model call, then open the UI
#    http://127.0.0.1:5000
```

If a container runtime is preferred over a local install, that is also an
operator step — the agent's shell cannot reach the container runtime on this host.

### Verify it worked

```bash
# The mirror reports no failures after a call
.venv/bin/python -c "from app.cost.mlflow_sink import mirror_failures; print(mirror_failures())"

# The system of record is unchanged — the same call is still in SQLite
.venv/bin/python -c "
from app.cost.store import read_call_records
print(len(read_call_records()))"
```

A successful mirror does **not** change any number the cost report prints. If the
UI and the report ever disagree, the report is authoritative.

---

## 4. What lands in a run

Per call, one MLflow run named after the call's `session_id`:

- **Metrics** (all numeric, non-boolean fields): `latency_ms`, `input_tokens`,
  `output_tokens`, `cache_hit_input_tokens`, `cost_usd`, `priced`, and the rest.
- **Tags** (identifiers only): `session_id`, `stage`, `provider`, `model`,
  `pricing_basis`.
- **Not sent:** anything credential-shaped. Unknown string fields are ignored.

`mirror_session_cost_record` uses the same path for session-level aggregates.

---

## 5. Related reading

- `backend/app/cost/mlflow_sink.py` — the sink, and the docstring stating why its
  absence is a non-event.
- `backend/app/config.py` — `MLFLOW_TRACKING_URI` and `COST_STORE_PATH`.
- `docs/agentia_first_baseline.tex` §Telemetry — the first real run's position:
  15 priced calls in the local store, none in MLflow.
- `backend/scripts/report_session_costs.py` — the authoritative report.
