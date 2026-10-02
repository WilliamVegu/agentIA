import os
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
RUNTIME = Path(__file__).resolve().parent / "browser-runtime"
RUNTIME.mkdir(exist_ok=True)
os.environ["DATABASE_URL"] = "sqlite:///" + (RUNTIME / "browser.db").as_posix()
os.environ["WORKSPACE_DIR"] = str(RUNTIME / "workspaces")
sys.path.insert(0, str(ROOT / "backend"))
from app.main import app
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory=ROOT / "frontend/dist", html=True), name="frontend")
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8012, log_level="warning")
