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
) -> str:
    """
    Resolves the ephemeral LLM API key with priority:
    1. Payload key (ephemeral session state from Streamlit)
    2. Header X-LLM-API-Key
    3. Host environment variables: GEMINI_API_KEY / GOOGLE_API_KEY, GROQ_API_KEY, OPENAI_API_KEY
    Raises HTTP 401 if no valid key is resolved per Constitution Principle VI.
    """
    key = (
        payload_key
        or header_key
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GROQ_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    if not key or not key.strip():
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
    api_key = resolve_api_key(request.apiKey, x_llm_api_key)
    provider = request.provider or x_llm_provider
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
    api_key = resolve_api_key(request.apiKey, x_llm_api_key)
    provider = request.provider or x_llm_provider
    try:
        refined_draft = refine_specification(request, api_key, provider=provider)
        return refined_draft
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refine specification: {str(e)}",
        )


@router.get("/sessions/{session_id}")
async def get_session_requirements(session_id: str):
    """Retrieves existing requirements, prompt, and user stories draft for an active session."""
    import json
    from pathlib import Path
    from app.config import settings
    from app.models.session import GenerationSessionDB, SessionLocal

    db = SessionLocal()
    try:
        sess = db.query(GenerationSessionDB).filter(GenerationSessionDB.id == session_id).first()
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found")
        spec_name = sess.spec_name or "Microservicio"
    finally:
        db.close()

    ws_path = Path(settings.WORKSPACE_DIR) / session_id
    raw_prompt = ""
    if ws_path.exists():
        spec_file = ws_path / "spec.md"
        if spec_file.exists():
            try:
                raw_prompt = spec_file.read_text(encoding="utf-8").strip()
            except Exception:
                pass

    stories_file = ws_path / "user_stories.json"
    draft_data = None
    if stories_file.exists():
        try:
            with open(stories_file, "r", encoding="utf-8") as f:
                stories_json = json.load(f)
            draft_data = {
                "serviceName": spec_name,
                "packageName": f"com.corp.{spec_name.lower().replace('-', '.')}",
                "basePort": 8080,
                "entities": [],
                "userStories": stories_json if isinstance(stories_json, list) else stories_json.get("userStories", []),
                "assumptions": [],
            }
        except Exception:
            pass

    return {
        "sessionId": session_id,
        "serviceName": spec_name,
        "rawPrompt": raw_prompt,
        "hasDraft": draft_data is not None,
        "draft": draft_data,
    }


@router.post("/sessions/{session_id}/save")
async def save_session_requirements(session_id: str, draft: SpecificationDraft):
    """Saves approved requirements draft and advances session to Architecture phase."""
    import json
    from pathlib import Path
    from app.config import settings
    from app.services.lifecycle_service import transition_phase, LifecyclePhase

    ws_path = Path(settings.WORKSPACE_DIR) / session_id
    ws_path.mkdir(parents=True, exist_ok=True)

    stories_file = ws_path / "user_stories.json"
    with open(stories_file, "w", encoding="utf-8") as f:
        json.dump([s.model_dump() for s in draft.userStories], f, indent=2)

    spec_file = ws_path / "spec.md"
    if draft.markdownSpec:
        with open(spec_file, "w", encoding="utf-8") as f:
            f.write(draft.markdownSpec)

    transition_phase(session_id, LifecyclePhase.STORIES, force=True)
    return {"sessionId": session_id, "status": "SAVED", "storiesCount": len(draft.userStories)}


