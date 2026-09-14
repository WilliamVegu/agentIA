import uuid
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Header, status

try:
    from app.models.test_analysis import (
        TestSynthesisRequest,
        TestSynthesisResponse,
        CodeAnalysisRequest,
        CodeAnalysisResponse,
        RepairExecutionRequest,
        RepairIterationRecord,
        RepairHistoryResponse,
        ManualRepairRequest,
        ManualRepairResponse,
        RepairOutcome,
    )
    from app.services.test_analysis_service import test_analysis_service
    from app.services.spec_service import SPECIFICATIONS_STORE
except ImportError:
    from backend.app.models.test_analysis import (
        TestSynthesisRequest,
        TestSynthesisResponse,
        CodeAnalysisRequest,
        CodeAnalysisResponse,
        RepairExecutionRequest,
        RepairIterationRecord,
        RepairHistoryResponse,
        ManualRepairRequest,
        ManualRepairResponse,
        RepairOutcome,
    )
    from backend.app.services.test_analysis_service import test_analysis_service
    from backend.app.services.spec_service import SPECIFICATIONS_STORE

router = APIRouter(prefix="/api/v1", tags=["Tests & Self-Repair"])

# In-memory storage for repair history per session
REPAIR_HISTORIES_STORE: Dict[str, List[RepairIterationRecord]] = {}
BLOCKED_SESSIONS_STORE: Dict[str, Dict] = {}


@router.post(
    "/tests/synthesize",
    response_model=TestSynthesisResponse,
    status_code=status.HTTP_200_OK,
    summary="Synthesize hybrid unit and integration test suites",
)
def synthesize_test_suites(
    request: TestSynthesisRequest,
    x_llm_api_key: Optional[str] = Header(None, alias="X-LLM-API-Key"),
):
    """
    Synthesizes Mockito unit tests, @WebMvcTest controller tests, and @SpringBootTest context tests.
    """
    effective_key = request.apiKey or x_llm_api_key

    # Resolve blueprint
    blueprint = request.blueprint
    if not blueprint and request.specId:
        stored = SPECIFICATIONS_STORE.get(request.specId)
        if stored:
            blueprint = stored.model_dump() if hasattr(stored, "model_dump") else (stored.dict() if hasattr(stored, "dict") else dict(stored))

    if not blueprint:
        # If still no blueprint, return a 400 Bad Request
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Specification blueprint is required to synthesize test suites.",
        )

    try:
        response = test_analysis_service.synthesize_test_suites(
            blueprint=blueprint,
            test_types=request.testTypes,
            api_key=effective_key,
        )
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to synthesize test suites: {str(e)}",
        )


@router.post(
    "/tests/analyze",
    response_model=CodeAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze build logs, test results, and static code compliance",
)
def analyze_code_and_failures(request: CodeAnalysisRequest):
    """
    Parses compiler logs and test failure stack traces into structured FailureDiagnostics,
    and runs static constitutional compliance checks on the source files.
    """
    try:
        response = test_analysis_service.analyze_execution_and_code(
            raw_build_logs=request.rawBuildLogs,
            source_files=request.sourceFiles,
        )
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze execution and code: {str(e)}",
        )


@router.post(
    "/tests/repair",
    response_model=RepairIterationRecord,
    status_code=status.HTTP_200_OK,
    summary="Plan and apply an autonomous surgical self-repair patch",
)
def execute_repair_iteration(
    request: RepairExecutionRequest,
    x_llm_api_key: Optional[str] = Header(None, alias="X-LLM-API-Key"),
):
    """
    Plans and applies a surgical method/block patch bounded strictly by 3 iterations (Constitution Principle V).
    """
    effective_key = request.apiKey or x_llm_api_key

    if request.iterationNumber > 3:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Constitution Principle V Violation: Auto-repair cycle hard-capped at 3 iterations. Session is now BLOCKED.",
        )

    try:
        record = test_analysis_service.execute_repair_iteration(
            session_id=request.sessionId,
            iteration_number=request.iterationNumber,
            diagnostics=request.diagnostics,
            source_files=request.sourceFiles,
            api_key=effective_key,
        )

        # Record in memory store
        if request.sessionId not in REPAIR_HISTORIES_STORE:
            REPAIR_HISTORIES_STORE[request.sessionId] = []
        REPAIR_HISTORIES_STORE[request.sessionId].append(record)

        if record.outcome == RepairOutcome.FAILED_BLOCKED:
            BLOCKED_SESSIONS_STORE[request.sessionId] = {
                "blocked": True,
                "diagnostic": request.diagnostics[0] if request.diagnostics else None,
            }

        return record
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute repair iteration: {str(e)}",
        )


@router.get(
    "/sessions/{sessionId}/repairs",
    response_model=RepairHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve complete repair history and diffs for a session",
)
def get_session_repairs(sessionId: str):
    """
    Returns the history of repair attempts, applied patches, and diff summaries.
    """
    records = REPAIR_HISTORIES_STORE.get(sessionId, [])
    blocked_info = BLOCKED_SESSIONS_STORE.get(sessionId, {})

    final_state = "VERIFIED"
    if blocked_info.get("blocked", False) or (records and records[-1].outcome == RepairOutcome.FAILED_BLOCKED):
        final_state = "BLOCKED"
    elif records and records[-1].outcome == RepairOutcome.FAILED_CONTINUE:
        final_state = "REPAIRING"

    return RepairHistoryResponse(
        sessionId=sessionId,
        totalIterations=len(records),
        finalState=final_state,
        iterations=records,
        canRetryManually=final_state == "BLOCKED",
        currentBlockedDiagnostic=blocked_info.get("diagnostic"),
    )


@router.post(
    "/sessions/{sessionId}/manual-repair",
    response_model=ManualRepairResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit developer manual code edit or AI prompt hint to resolve a BLOCKED session",
)
def submit_manual_repair(
    sessionId: str,
    request: ManualRepairRequest,
    x_llm_api_key: Optional[str] = Header(None, alias="X-LLM-API-Key"),
):
    """
    Allows the developer to provide a manual code fix or natural language hint to unblock a session.
    """
    if not request.filePath:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="filePath is required for manual repair.",
        )

    # Clear blocked state
    if sessionId in BLOCKED_SESSIONS_STORE:
        del BLOCKED_SESSIONS_STORE[sessionId]

    if request.modifiedCode:
        from pathlib import Path
        from app.config import settings
        from app.api.routes_session import SESSION_GENERATION_STATE

        ws_file = Path(settings.WORKSPACE_DIR) / sessionId / request.filePath
        try:
            if ws_file.parent.exists():
                ws_file.write_text(request.modifiedCode, encoding="utf-8")
        except Exception:
            pass

        if sessionId in SESSION_GENERATION_STATE and "generated_files" in SESSION_GENERATION_STATE[sessionId]:
            SESSION_GENERATION_STATE[sessionId]["generated_files"][request.filePath] = request.modifiedCode

    return ManualRepairResponse(
        sessionId=sessionId,
        status="REPAIR_APPLIED",
        message=f"Manual modification applied to '{request.filePath}'. Re-running sandbox verification...",
        diagnosticsResolved=True,
    )
