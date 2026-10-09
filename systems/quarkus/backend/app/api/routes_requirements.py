import os
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Header, HTTPException, status
from fastapi.responses import JSONResponse

try:
    from app.models.requirements import (
        RequirementsTransformRequest,
        RefinementRequest,
        SpecificationDraft,
        ApiErrorResponse,
    )
    from app.services.requirements_service import (
        transform_requirements,
        refine_specification,
    )
except ImportError:
    from backend.app.models.requirements import (
        RequirementsTransformRequest,
        RefinementRequest,
        SpecificationDraft,
        ApiErrorResponse,
    )
    from backend.app.services.requirements_service import (
        transform_requirements,
        refine_specification,
    )

router = APIRouter(prefix="/requirements", tags=["Requirements Transformation"])

def resolve_api_key(
    payload_key: Optional[str] = None,
    header_key: Optional[str] = None,
    provider: Optional[str] = None,
) -> str:
    """
    Resolves the ephemeral LLM API key with priority:
    1. Offline mock if provider is 'mock'
    2. Payload key
    3. Header X-LLM-API-Key
    4. Host environment variables: GEMINI_API_KEY / GOOGLE_API_KEY, GROQ_API_KEY, OPENAI_API_KEY
    5. Fallback to offline-mock if ALLOW_OFFLINE_MOCK is True
    Raises HTTP 401 if no valid key is resolved per Constitution Principle VI.
    """
    clean_provider = (provider or "").strip().lower()
    if clean_provider == "mock":
        return "offline-mock"

    key = (
        payload_key
        or header_key
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GROQ_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    if not key or not key.strip():
        allow_mock = os.environ.get("ALLOW_OFFLINE_MOCK", "").lower() in ("true", "1", "yes")
        try:
            from app.config import settings
            allow_mock = allow_mock or getattr(settings, "ALLOW_OFFLINE_MOCK", False)
        except Exception:
            pass

        if allow_mock:
            return "offline-mock"

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="LLM API key is required to perform requirements transformation. "
                   "Configure your free Gemini or Groq key in the Settings sidebar or provide via X-LLM-API-Key header."
        )
    return key.strip()

@router.post(
    "/transform",
    response_model=SpecificationDraft,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ApiErrorResponse, "description": "Invalid input"},
        401: {"model": ApiErrorResponse, "description": "Missing API Key"},
        500: {"model": ApiErrorResponse, "description": "Internal server error"},
    },
)
def transform_requirements_endpoint(
    request: RequirementsTransformRequest,
    x_llm_api_key: Optional[str] = Header(default=None, alias="X-LLM-API-Key"),
    x_llm_provider: Optional[str] = Header(default=None, alias="X-LLM-Provider"),
):
    """
    Decompose natural language requirements narrative into formal User Stories
    with Given/When/Then acceptance criteria and extracted Domain Entities.
    """
    provider = request.provider or x_llm_provider
    api_key = resolve_api_key(request.apiKey, x_llm_api_key, provider=provider)
    try:
        draft = transform_requirements(request, api_key, provider=provider)
        return draft
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to transform requirements: {str(e)}",
        )

@router.post(
    "/refine",
    response_model=SpecificationDraft,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ApiErrorResponse, "description": "Invalid payload"},
        401: {"model": ApiErrorResponse, "description": "Missing API Key"},
        500: {"model": ApiErrorResponse, "description": "Internal server error"},
    },
)
def refine_requirements_endpoint(
    request: RefinementRequest,
    x_llm_api_key: Optional[str] = Header(default=None, alias="X-LLM-API-Key"),
    x_llm_provider: Optional[str] = Header(default=None, alias="X-LLM-Provider"),
):
    """
    Refine existing specification draft based on natural language feedback prompt,
    updating specific stories or globally adjusting criteria.
    """
    provider = request.provider or x_llm_provider
    api_key = resolve_api_key(request.apiKey, x_llm_api_key, provider=provider)
    try:
        refined_draft = refine_specification(request, api_key, provider=provider)
        return refined_draft
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refine specification: {str(e)}",
        )


@router.get('/sessions/{session_id}')
async def get_session_requirements(session_id: str):
    from app.services.draft_revision_service import get_revision
    result = get_revision(session_id)
    draft = result['draft']
    raw_prompt = draft.get('markdownSpec', '') if draft else ''
    if draft is None:
        from app.services.workspace_guard import resolve_workspace_file, io_path
        specification = resolve_workspace_file(session_id, 'spec.md')
        if io_path(specification).is_file():
            raw_prompt = io_path(specification).read_text(encoding='utf-8')
    return {**result, 'sessionId': session_id, 'hasDraft': draft is not None,
            'serviceName': draft['serviceName'] if draft else None,
            'rawPrompt': raw_prompt}


@router.post('/sessions/{session_id}/save')
async def save_session_requirements(session_id: str, draft: SpecificationDraft, expectedRevisionId: Optional[str] = None, expectedVersion: Optional[int] = None):
    from app.services.draft_revision_service import save_revision
    result = save_revision(session_id, draft.model_dump(), expected_revision_id=expectedRevisionId, expected_version=expectedVersion)
    return {**result, 'sessionId': session_id, 'status': 'SAVED',
            'storiesCount': len(draft.userStories), 'entitiesCount': len(draft.entities)}


@router.post('/sessions/{session_id}/approve')
async def approve_session_requirements(session_id: str, revisionId: str, expectedVersion: Optional[int] = None):
    from app.services.draft_revision_service import approve_revision
    return {'sessionId': session_id, **approve_revision(session_id, revisionId, expected_version=expectedVersion)}


@router.post('/sessions/{session_id}/regenerate')
async def regenerate_revision(session_id: str, revisionId: str, confirmBackup: bool = False):
    if not confirmBackup: raise HTTPException(422,'Confirme explícitamente la regeneración con backup')
    from app.services.draft_revision_service import prepare_regeneration
    backup=prepare_regeneration(session_id,revisionId)
    return {'sessionId':session_id,'revisionId':revisionId,'status':'READY_TO_REGENERATE','backup':backup.name}
