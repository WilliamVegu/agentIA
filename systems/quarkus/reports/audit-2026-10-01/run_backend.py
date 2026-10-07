"""Run the audited checkout with isolated storage; no credentials are persisted."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = Path(__file__).resolve().parent
runtime = AUDIT / "runtime"
runtime.mkdir(exist_ok=True)
os.environ.update({
    "DATABASE_URL": f"sqlite:///{(runtime / 'studio.db').as_posix()}",
    "WORKSPACE_DIR": str(runtime / "workspaces"),
    "SPECIFICATION_DIR": str(runtime / "specifications"),
    "COST_STORE_PATH": str(runtime / "cost_tracking.db"),
    "ALLOW_OFFLINE_MOCK": "false",
    "ALLOW_HERMETIC_FALLBACK": "false",
    "MLFLOW_TRACKING_URI": (runtime / "mlruns").as_uri(),
})
sys.path.insert(0, str(ROOT / "backend"))
import uvicorn

uvicorn.run("app.main:app", host="127.0.0.1", port=8011, log_level="warning")
