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
    from app.services.automatic_repair_service import automatic_repair
    return automatic_repair(request,framework='quarkus',effective_key=request.apiKey or x_llm_api_key)


@router.get(
    "/sessions/{sessionId}/repairs",
    response_model=RepairHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve complete repair history and diffs for a session",
)
def get_session_repairs(sessionId: str):
    from app.services.automatic_repair_service import repair_history
    return repair_history(sessionId)


@router.post(
    "/sessions/{sessionId}/manual-repair",
    response_model=ManualRepairResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit developer manual code edit or AI prompt hint to resolve a BLOCKED session",
)
def submit_manual_repair(
    sessionId: str, request: ManualRepairRequest,
    x_llm_api_key: Optional[str] = Header(None, alias="X-LLM-API-Key"),
):
    from app.services.manual_repair_service import manual_repair
    return ManualRepairResponse(**manual_repair(sessionId,request))
