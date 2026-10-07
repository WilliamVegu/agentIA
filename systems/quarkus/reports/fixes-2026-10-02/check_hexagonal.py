"""Live stage generation with the authorized DeepSeek provider."""
import check_regressions as checks
import json
import os
import time
import uuid
from app.models.requirements import SpecificationDraft
from app.orchestrator.stages.instructions import load_instruction_set
from app.orchestrator.stages.runner import run_stages, STAGE_ORDER
from app.orchestrator.nodes.sandbox_node import sandbox_node

sid = str(uuid.uuid4())
ws = checks.RUNTIME / "workspaces" / sid
ws.mkdir(parents=True)
draft = SpecificationDraft(**json.loads((checks.OUT.parent / "verify-61c0f29/draft.json").read_text(encoding="utf-8")))
blueprint = draft.model_dump(mode="json")
blueprint["inputInterface"] = {"architecturePreference": "hexagonal", "buildToolPreference": "gradle"}
state = {"session_id": sid, "blueprint": blueprint, "workspace_path": str(ws), "logs": [], "generated_files": {},
         "generation_mode": "MODEL", "instruction_set_revision": load_instruction_set().revision,
         "llm_provider": "deepseek", "llm_model": "deepseek-flash", "llm_api_key": os.environ["AUDIT_DEEPSEEK_KEY"]}
started = time.monotonic()
result = run_stages(state, stages=STAGE_ORDER, api_key=os.environ["AUDIT_DEEPSEEK_KEY"])
summary = {"sessionId": sid, "elapsedSeconds": round(time.monotonic()-started, 2),
           "status": result.get("status"), "error": result.get("error"), "files": sorted(result.get("generated_files", {})),
           "logs": result.get("logs"), "journal": result.get("generation_journal")}
(checks.OUT / "hexagonal.json").write_text(json.dumps(summary, indent=2).replace(os.environ["AUDIT_DEEPSEEK_KEY"], "[REDACTED]"), encoding="utf-8")
checks.check("live stages did not block", result.get("status") != "BLOCKED")
checks.check("live Gradle artifacts", (ws / "build.gradle").exists() or (ws / "build.gradle.kts").exists())
checks.check("live domain packages", any("/domain/" in path for path in summary["files"]))
checks.check("live application packages", any("/application/" in path for path in summary["files"]))
checks.check("live infrastructure packages", any("/infrastructure/" in path for path in summary["files"]))
checks.check("no substituted layered service packages", not any("/service/impl/" in path for path in summary["files"]))
verification = sandbox_node(result)
summary["verification"] = {k: verification.get(k) for k in ("status", "current_phase", "test_metrics", "error")}
(checks.OUT / "hexagonal.json").write_text(json.dumps(summary, indent=2).replace(os.environ["AUDIT_DEEPSEEK_KEY"], "[REDACTED]"), encoding="utf-8")
checks.check("unavailable Docker never verifies", verification.get("status") == "BLOCKED" and not verification["test_metrics"]["allPassed"])
print("Live hexagonal/Gradle generation passed; Docker verification honestly BLOCKED", flush=True)
