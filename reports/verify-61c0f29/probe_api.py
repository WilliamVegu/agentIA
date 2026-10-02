"""Audit real HTTP contracts and containment using only disposable audit files.

AI calls use the DeepSeek key in the process environment. No model is replaced.
Run against run_backend.py to keep application data isolated.
"""
import json
import os
import time
from pathlib import Path
import httpx

OUT = Path(__file__).resolve().parent
WS = OUT / "runtime" / "workspaces"
BASE = "http://127.0.0.1:8011"
KEY = os.environ["AUDIT_DEEPSEEK_KEY"]
headers = {"X-LLM-API-Key": KEY, "X-LLM-Provider": "deepseek"}
client = httpx.Client(base_url=BASE, timeout=300)
results = []

def redact(value):
    return json.loads(json.dumps(value, ensure_ascii=False).replace(KEY, "[REDACTED]"))

def req(name, method, path, payload=None, authenticated=False):
    started = time.monotonic()
    response = client.request(method, path, json=payload, headers=headers if authenticated else {})
    try:
        data = response.json()
    except ValueError:
        data = response.text[:4000]
    record = redact({"name": name, "method": method, "path": path,
                     "status": response.status_code, "seconds": round(time.monotonic()-started, 2),
                     "response": data})
    results.append(record)
    (OUT / "api-results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: record[k] for k in ["name", "status", "seconds"]}), flush=True)
    return data

req("health", "GET", "/healthz")
schema = client.get("/openapi.json").json()
(OUT / "openapi.json").write_text(json.dumps(schema, indent=2), encoding="utf-8")
req("sessions_without_auth", "GET", "/api/v1/sessions")
req("unknown_repair_history", "GET", "/api/v1/sessions/audit-nonexistent/repairs")

prompt = ("Un microservicio de biblioteca permite registrar libros con ISBN unico, titulo y autor; "
          "consultarlos por ISBN, actualizar el titulo y eliminarlos. Rechaza ISBN duplicados y titulos vacios. "
          "Usa Java 21 Spring Boot 3 y H2 para pruebas. Devuelve 201 al crear, 404 al consultar inexistentes y 400 ante datos invalidos.")
session = req("create_guided", "POST", "/api/v1/sessions/quick-start",
              {"service_name":"audit-library", "prompt":prompt, "database":"H2", "auto_run":False,
               "llm_provider":"deepseek", "api_key":KEY,
               "input_interface":{"requestVolume":"high","architecturePreference":"hexagonal","buildToolPreference":"gradle"}}, True)
sid = session["sessionId"]
(OUT / "session.json").write_text(json.dumps({"sessionId":sid}), encoding="utf-8")
req("guided_overview", "GET", f"/api/v1/orchestrator/sessions/{sid}/overview")
req("guided_initial_metrics", "GET", f"/api/v1/sessions/{sid}/metrics")

# Only files created by this audit are used to demonstrate escaping containment.
sentinel = OUT / "runtime" / "outside-sentinel.txt"
sentinel.write_text("AUDIT_SENTINEL_BEFORE", encoding="utf-8")
req("manual_repair_absolute_path", "POST", f"/api/v1/sessions/{sid}/manual-repair",
    {"filePath": str(sentinel), "modifiedCode":"AUDIT_SENTINEL_AFTER"})
print("sentinel_modified=" + str(sentinel.read_text(encoding="utf-8") == "AUDIT_SENTINEL_AFTER"), flush=True)
req("manual_repair_missing_file", "POST", "/api/v1/sessions/audit-nonexistent/manual-repair",
    {"filePath":"missing.java", "modifiedCode":"audit"})
prefix_sibling = WS / (sid + "-sibling")
prefix_sibling.mkdir(exist_ok=True)
(prefix_sibling / "audit.txt").write_text("AUDIT_SIBLING_FILE", encoding="utf-8")
req("artifact_prefix_traversal", "GET", f"/api/v1/sessions/{sid}/artifacts/content?path=../{sid}-sibling/audit.txt")
req("artifact_absolute_session_escape", "GET", "/api/v1/sessions/../artifacts/content?path=audit.txt")

draft = req("real_deepseek_requirements", "POST", "/api/v1/requirements/transform",
            {"rawText":prompt,"serviceName":"audit-library","packageName":"com.audit.library",
             "provider":"deepseek","modelName":"deepseek-flash"}, True)
if "entities" not in draft:
    raise SystemExit("Real requirements generation failed; see api-results.json")
(OUT / "draft.json").write_text(json.dumps(draft, indent=2, ensure_ascii=False), encoding="utf-8")
req("save_real_requirements", "POST", f"/api/v1/requirements/sessions/{sid}/save", draft, True)
retrieved = req("reload_real_requirements", "GET", f"/api/v1/requirements/sessions/{sid}")
print(f"entities_before={len(draft['entities'])}; entities_after={len(retrieved.get('draft',{}).get('entities',[]))}", flush=True)

arch = req("real_deepseek_architecture", "POST", "/api/v1/architecture/design", {"draft":draft,"provider":"deepseek"}, True)
if "components" in arch:
    (OUT / "architecture.json").write_text(json.dumps(arch, indent=2, ensure_ascii=False), encoding="utf-8")
    req("save_real_architecture", "POST", f"/api/v1/architecture/sessions/{sid}/save", arch, True)
models = req("real_deepseek_models", "POST", "/api/v1/models/generate", {"draft":draft,"provider":"deepseek"}, True)
if "sqlSchema" in models:
    (OUT / "models.json").write_text(json.dumps(models, indent=2, ensure_ascii=False), encoding="utf-8")
    req("save_real_models", "POST", f"/api/v1/models/sessions/{sid}/save", models, True)
    print("saved_sql_exists=" + str((WS / sid / "schema.sql").exists()), flush=True)

req("pause_idle_session", "POST", f"/api/v1/orchestrator/pipeline/{sid}/pause")
req("lifecycle_after_idle_pause", "GET", f"/api/v1/orchestrator/sessions/{sid}/lifecycle")
# Full pipeline: real credentials, real model, no deployment or mock verification.
req("start_real_pipeline", "POST", "/api/v1/orchestrator/pipeline/run",
    {"sessionId":sid, "provider":"deepseek", "apiKey":KEY, "model":"deepseek-flash",
     "targetPhase":"CODE_TESTS","stopOnGate":True,"autoDeploy":False}, True)
req("schema_bad_payload", "POST", "/api/v1/requirements/transform", {"rawText":"x"}, True)
req("payload_security_audit", "POST", "/api/v1/security/audit",
    {"serviceName":"audit","files":{},"pomXml":""})
print("API probes complete; pipeline running asynchronously", flush=True)
