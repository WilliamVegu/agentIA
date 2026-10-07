"""Run real local regression checks in isolated storage; no substituted LLM."""
import asyncio
import json
import os
from pathlib import Path
import secrets
import sys
import threading
import time

OUT = Path(__file__).resolve().parent
RUNTIME = OUT / "runtime"
RUNTIME.mkdir(exist_ok=True)
os.environ["DATABASE_URL"] = "sqlite:///" + (RUNTIME / "checks.db").as_posix()
os.environ["WORKSPACE_DIR"] = str(RUNTIME / "workspaces")
os.environ["COST_STORE_PATH"] = str(RUNTIME / "cost.db")
os.environ["STUDIO_ACCESS_TOKEN"] = secrets.token_urlsafe(32)
os.environ["STUDIO_USER_EMAIL"] = "operator@example.test"
sys.path.insert(0, str(OUT.parents[1] / "backend"))

from fastapi.testclient import TestClient
from app.main import app
from app.models.session import Base, engine, SessionLocal, GenerationSessionDB, SessionPhase, SessionStatus
from app.services.queue_service import ConcurrencyQueueManager
from app.services.verification_policy import tests_really_passed, session_is_verified, workspace_fingerprint
from app.services.security_service import evaluate_quality_gate, calculate_code_metrics
from app.services.devops_service import generate_all_devops_assets
from app.sandbox.docker_runner import build_docker_cmd

Base.metadata.create_all(engine)
results = []
def check(name, condition):
    results.append({"name": name, "passed": bool(condition)})
    assert condition, name

valid = {"totalTests": 2, "passedTests": 2, "failedTests": 0, "allPassed": True, "fallback_used": False}
check("nonempty tests accepted", tests_really_passed(valid))
check("zero tests rejected", not tests_really_passed({**valid, "totalTests": 0, "passedTests": 0}))
check("fallback rejected", not tests_really_passed({**valid, "fallback_used": True}))
check("partial suite rejected", not tests_really_passed({**valid, "passedTests": 1}))
check("missing evidence rejected", not tests_really_passed(None))
check("empty audit blocked", not evaluate_quality_gate([], [], calculate_code_metrics({})).canExport)

async def queue_checks():
    manager = ConcurrencyQueueManager(1)
    await manager.acquire_slot("graph")
    acquired = threading.Event()
    def worker():
        if manager.acquire_slot_sync("autopilot"):
            acquired.set()
            manager.release_slot_sync("autopilot")
    thread = threading.Thread(target=worker)
    thread.start()
    await asyncio.sleep(.15)
    check("shared capacity enforced", not acquired.is_set() and len(manager.active_sessions) == 1)
    manager.cancel_waiting("graph")
    check("cancellation retains running slot", len(manager.active_sessions) == 1)
    await manager.release_slot("graph")
    thread.join(timeout=2)
    check("thread receives released slot", acquired.is_set() and not thread.is_alive())
    await manager.acquire_slot("holder")
    task = asyncio.create_task(manager.acquire_slot("queued"))
    await asyncio.sleep(.1)
    manager.cancel_waiting("queued")
    check("queued cancellation exits", await task is False)
    await manager.release_slot("holder")
asyncio.run(queue_checks())

client = TestClient(app)
check("anonymous API rejected", client.get("/api/v1/sessions").status_code == 401)
check("fabricated email rejected", client.get("/api/v1/sessions", headers={"X-User-Email": "admin@tcs.com"}).status_code == 401)
check("wrong password rejected", client.post("/api/v1/auth/login", json={"email": os.environ["STUDIO_USER_EMAIL"], "password": "wrong"}).status_code == 401)
response = client.post("/api/v1/auth/login", json={"email": os.environ["STUDIO_USER_EMAIL"], "password": os.environ["STUDIO_ACCESS_TOKEN"]})
check("configured login accepted", response.status_code == 200 and "HttpOnly" in response.headers["set-cookie"])
check("authenticated API available", client.get("/api/v1/sessions").status_code == 200)
check("empty API audit blocked", client.post("/api/v1/security/audit", json={"files": {}, "pomXml": ""}).json()["qualityGate"]["canExport"] is False)

sid = "regression-unverified"
ws = Path(os.environ["WORKSPACE_DIR"]) / sid
(ws / "src/main/java").mkdir(parents=True, exist_ok=True)
(ws / "build.gradle").write_text("plugins { id 'java' }\n", encoding="utf-8")
(ws / "settings.gradle").write_text("rootProject.name = 'checks'\n", encoding="utf-8")
source = ws / "src/main/java/Book.java"
source.write_text("class Book {}", encoding="utf-8")
db = SessionLocal()
row = db.get(GenerationSessionDB, sid)
if row is None:
    row = GenerationSessionDB(id=sid, spec_id="checks", spec_name="checks")
    db.add(row)
row.status, row.phase = SessionStatus.COMPLETED, SessionPhase.INITIALIZATION
row.error_message = None
row.verification_metrics_json = json.dumps({**valid, "totalTests": 0, "passedTests": 0})
db.commit()
check("unverified export rejected", client.get(f"/api/v1/sessions/{sid}/export").status_code == 403)
check("unverified bundle rejected", client.get(f"/api/v1/orchestrator/sessions/{sid}/export-bundle").status_code == 403)
history = client.get(f"/api/v1/sessions/{sid}/repairs")
check("history never fabricates VERIFIED", history.status_code == 200 and history.json().get("finalState") != "VERIFIED")
row.phase = SessionPhase.VERIFIED
row.verification_metrics_json = json.dumps({**valid, "workspaceFingerprint": workspace_fingerprint(ws)})
db.commit()
check("matching evidence recognized", session_is_verified(row))
source.write_text("class Book { int changed; }", encoding="utf-8")
check("edited source invalidates proof", not session_is_verified(row))
db.close()
command = build_docker_cmd(str(ws), str(RUNTIME / "m2"))
check("Gradle sandbox selected", "mvn" not in command and "--offline test" in command[-1])
assets = generate_all_devops_assets(str(ws), sid, "checks")
check("Gradle Dockerfile selected", "RUN gradle" in assets.dockerfileContent and "COPY pom.xml" not in assets.dockerfileContent)
check("Gradle CI selected", "run: mvn" not in assets.githubActionsWorkflow and "gradle --no-daemon" in assets.githubActionsWorkflow)
repair = client.post(f"/api/v1/sessions/{sid}/manual-repair", json={"filePath": "src/main/java/Book.java", "modifiedCode": "class Book { int fixed; }"})
check("manual repair performs verification", repair.status_code == 200 and repair.json()["status"] == "BLOCKED" and repair.json()["diagnosticsResolved"] is False)
check("unknown model session rejected", client.post("/api/v1/models/sessions/unknown-regression/save", json={}).status_code == 404)
check("architecture traversal rejected", client.post("/api/v1/architecture/sessions/../save", json={}).status_code in (400, 404, 405))
from app.services.git_service import publish_to_git
repo_path = RUNTIME / "git-credentials"
repo_path.mkdir(exist_ok=True)
(repo_path / "README.md").write_text("Disposable regression repository", encoding="utf-8")
fictitious_token = "fictitious-regression-token-123456"
try:
    publish_to_git(str(repo_path), "https://127.0.0.1:9/repository.git", "checks", fictitious_token)
except RuntimeError:
    pass
config = (repo_path / ".git/config").read_text(encoding="utf-8")
check("Git credential not persisted", fictitious_token not in config and "x-access-token:" not in config)
client.post("/api/v1/auth/logout")
check("logout revokes access", client.get("/api/v1/sessions").status_code == 401)
(OUT / "regressions.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
print(f"{len(results)} local regression checks passed")
