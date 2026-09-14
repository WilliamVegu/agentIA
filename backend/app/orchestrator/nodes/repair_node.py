from pathlib import Path
from typing import Dict, Any, List
from app.orchestrator.state import GenerationAgentState
from app.models.session import SessionPhase, SessionStatus
from app.orchestrator.repair import can_retry, format_repair_prompt

try:
    from app.services.test_analysis_service import test_analysis_service
    from app.models.test_analysis import (
        FailureDiagnostic,
        DiagnosticCategory,
        DiagnosticSeverity,
        RepairIterationRecord,
        RepairOutcome,
    )
    from app.api.routes_tests import REPAIR_HISTORIES_STORE, BLOCKED_SESSIONS_STORE
except ImportError:
    from backend.app.services.test_analysis_service import test_analysis_service
    from backend.app.models.test_analysis import (
        FailureDiagnostic,
        DiagnosticCategory,
        DiagnosticSeverity,
        RepairIterationRecord,
        RepairOutcome,
    )
    from backend.app.api.routes_tests import REPAIR_HISTORIES_STORE, BLOCKED_SESSIONS_STORE

def repair_node(state: GenerationAgentState) -> Dict[str, Any]:
    repair_attempts = state.get("repair_attempts", 0) + 1
    max_attempts = state.get("max_repair_attempts", 3)
    session_id = state.get("session_id", "default-session")
    diag = state.get("last_diagnostic", {})
    logs = state.get("logs", [])
    generated_files = dict(state.get("generated_files", {}))
    workspace_path = state.get("workspace_path")

    logs.append(f"[REPAIR] Evaluating auto-repair attempt {repair_attempts}/{max_attempts}")

    # Build structured FailureDiagnostic
    diagnostics: List[FailureDiagnostic] = []
    if diag:
        if isinstance(diag, FailureDiagnostic):
            diagnostics.append(diag)
        elif isinstance(diag, dict):
            failed_file = diag.get("failed_file") or diag.get("filePath", "unknown")
            error_msg = diag.get("summary") or diag.get("errorSummary", "Sandbox build or test failure")
            category = (
                DiagnosticCategory.COMPILATION_ERROR
                if "compil" in str(diag.get("error_type", "")).lower()
                else DiagnosticCategory.ASSERTION_FAILURE
            )
            diagnostics.append(
                FailureDiagnostic(
                    id=f"DIAG-{repair_attempts}",
                    category=category,
                    severity=DiagnosticSeverity.BLOCKING if repair_attempts >= 3 else DiagnosticSeverity.HIGH,
                    filePath=failed_file,
                    errorSummary=error_msg,
                    lineNumber=diag.get("line_number") or diag.get("lineNumber"),
                    rawStackTrace=diag.get("raw_trace", ""),
                )
            )

    if not can_retry(repair_attempts - 1, max_attempts) or repair_attempts > 3:
        logs.append("[REPAIR] Bloqueo por intervención humana requerida: 3 repair attempts exhausted.")
        if diagnostics:
            BLOCKED_SESSIONS_STORE[session_id] = {
                "blocked": True,
                "diagnostic": diagnostics[0],
            }
        return {
            "repair_attempts": repair_attempts,
            "status": SessionStatus.BLOCKED.value,
            "current_phase": SessionPhase.FAILED.value,
            "error": "Bloqueo por intervención humana requerida: Maximum repair attempts (3) exhausted.",
            "diff_summary": "-- Maximum repair attempts (3) exhausted. Human intervention required.",
            "logs": logs,
        }

    # Execute repair iteration with surgical patch planner
    record = test_analysis_service.execute_repair_iteration(
        session_id=session_id,
        iteration_number=repair_attempts,
        diagnostics=diagnostics,
        source_files=generated_files,
    )

    if session_id not in REPAIR_HISTORIES_STORE:
        REPAIR_HISTORIES_STORE[session_id] = []
    REPAIR_HISTORIES_STORE[session_id].append(record)

    # Apply patches to files and disk workspace
    for patch in record.patchesApplied:
        generated_files, _ = test_analysis_service.apply_code_patch(generated_files, patch)
        if workspace_path and patch.filePath in generated_files:
            target_path = Path(workspace_path) / patch.filePath
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(generated_files[patch.filePath], encoding="utf-8")

    diff_summary = record.diffSummary or format_repair_prompt(diag)
    logs.append(f"[REPAIR] Applied patch (attempt {repair_attempts}/{max_attempts}): {diff_summary[:80]}...")

    return {
        "repair_attempts": repair_attempts,
        "current_phase": SessionPhase.SELF_REPAIR_LOOP.value,
        "diff_summary": diff_summary,
        "generated_files": generated_files,
        "logs": logs,
    }

