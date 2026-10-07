"""Live guided HTTP generation and cost persistence using DeepSeek only."""
import check_regressions as checks
import json
import os

key = os.environ["AUDIT_DEEPSEEK_KEY"]
login = checks.client.post("/api/v1/auth/login", json={"email": os.environ["STUDIO_USER_EMAIL"], "password": os.environ["STUDIO_ACCESS_TOKEN"]})
assert login.status_code == 200
draft = json.loads((checks.OUT.parent / "verify-61c0f29/draft.json").read_text(encoding="utf-8"))
response = checks.client.post("/api/v1/models/generate", json={"draft": draft, "provider": "deepseek", "apiKey": key, "modelName": "deepseek-flash"},
                              headers={"X-Session-ID": "regression-unverified"})
assert response.status_code == 200, response.status_code
db = checks.SessionLocal()
row = db.get(checks.GenerationSessionDB, "regression-unverified")
cost = json.loads(row.cost_record_json or "{}")
assert cost.get("model_calls_count", 0) > 0
assert key not in (row.cost_record_json or "")
db.close()
(checks.OUT / "guided-api.json").write_text(json.dumps({"status": response.status_code, "cost": cost,
    "entities": response.json()["entities"]}, indent=2).replace(key, "[REDACTED]"), encoding="utf-8")
print("Live guided HTTP synthesis and persisted cost passed", flush=True)
