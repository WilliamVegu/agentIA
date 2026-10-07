"""Authorized live DeepSeek calls using fictitious library requirements only."""
import check_regressions as checks
import json
import os
import time
import uuid
from pathlib import Path

from app.models.requirements import SpecificationDraft
from app.services.model_sql_service import model_sql_service
from app.services.pipeline_runner import run_pipeline, _active_threads
from app.models.orchestrator import LifecyclePhase

key = os.environ["AUDIT_DEEPSEEK_KEY"]
draft = SpecificationDraft(**json.loads((checks.OUT.parent / "verify-61c0f29/draft.json").read_text(encoding="utf-8")))
started = time.monotonic()
model = model_sql_service.synthesize_domain_models_and_sql(draft, api_key=key, provider="deepseek", model_name="deepseek-flash")
checks.check("live model synthesis", bool(model.entities and model.sqlSchema.schemaDdl))
refined = model_sql_service.refine_domain_models_and_sql(model,
    "Add an optional String shelfCode attribute to Book. Preserve the UUID id and unique ISBN.",
    target_entity="Book", api_key=key, provider="deepseek", model_name="deepseek-flash")
checks.check("live refinement follows feedback", any(a.name == "shelfCode" for e in refined.entities if e.name == "Book" for a in e.attributes))

sid = str(uuid.uuid4())
ws = Path(os.environ["WORKSPACE_DIR"]) / sid
ws.mkdir(parents=True)
(ws / "spec.md").write_text("A fictitious library stores books with UUID identifiers and a unique ISBN. Librarians register and find books. Reject duplicate ISBN values and report missing books.", encoding="utf-8")
db = checks.SessionLocal()
db.add(checks.GenerationSessionDB(id=sid, spec_id="fictitious-library", spec_name="audit-library"))
db.commit()
db.close()
checks.check("live partial pipeline starts", run_pipeline(sid, target_phase=LifecyclePhase.STORIES,
    api_key=key, provider="deepseek", model_name="deepseek-flash"))
_active_threads[sid].join(timeout=180)
checks.check("live partial pipeline stops", not _active_threads[sid].is_alive())
db = checks.SessionLocal()
row = db.get(checks.GenerationSessionDB, sid)
checks.check("partial generation is PAUSED", row.status == checks.SessionStatus.PAUSED)
checks.check("partial generation is not VERIFIED", not checks.session_is_verified(row))
db.close()
result = {"elapsedSeconds": round(time.monotonic()-started, 2), "provider": "deepseek", "model": "deepseek-flash",
          "sessionId": sid, "checks": checks.results,
          "refinedModel": refined.model_dump(mode="json")}
(checks.OUT / "deepseek.json").write_text(json.dumps(result, indent=2).replace(key, "[REDACTED]"), encoding="utf-8")
print("Live DeepSeek synthesis, refinement and partial pipeline passed", flush=True)
