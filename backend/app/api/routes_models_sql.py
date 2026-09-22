from typing import Optional
from fastapi import APIRouter, Header, HTTPException, status

try:
    from app.models.domain_model import (
        ModelSqlGenerationRequest,
        ModelSqlRefinementRequest,
        DataModelSynthesisResponse,
    )
    from app.models.requirements import ApiErrorResponse
    from app.api.routes_requirements import resolve_api_key
    from app.services.model_sql_service import model_sql_service
except ImportError:
    from backend.app.models.domain_model import (
        ModelSqlGenerationRequest,
        ModelSqlRefinementRequest,
        DataModelSynthesisResponse,
    )
    from backend.app.models.requirements import ApiErrorResponse
    from backend.app.api.routes_requirements import resolve_api_key
    from backend.app.services.model_sql_service import model_sql_service

router = APIRouter(prefix="/models", tags=["Domain Models & SQL Schema"])

@router.post(
    "/generate",
    response_model=DataModelSynthesisResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ApiErrorResponse, "description": "Invalid specification draft"},
        401: {"model": ApiErrorResponse, "description": "Missing API Key"},
        500: {"model": ApiErrorResponse, "description": "Internal server error"},
    },
)
def generate_models_and_sql_endpoint(
    request: ModelSqlGenerationRequest,
    x_llm_api_key: Optional[str] = Header(default=None, alias="X-LLM-API-Key"),
    x_llm_provider: Optional[str] = Header(default=None, alias="X-LLM-Provider"),
):
    """
    Synthesizes domain entity models (JPA Java 21 classes), ANSI/PostgreSQL DDL (schema.sql),
    seed data DML (data.sql), and Mermaid ER diagram from a specification draft.
    """
    provider = request.provider or x_llm_provider
    api_key = resolve_api_key(request.apiKey, x_llm_api_key, provider=provider)
    try:
        response = model_sql_service.synthesize_domain_models_and_sql(request.draft, api_key, provider=provider)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to synthesize domain models and SQL schema: {str(e)}",
        )

@router.post(
    "/refine",
    response_model=DataModelSynthesisResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ApiErrorResponse, "description": "Invalid refinement prompt"},
        401: {"model": ApiErrorResponse, "description": "Missing API Key"},
        500: {"model": ApiErrorResponse, "description": "Internal server error"},
    },
)
def refine_models_and_sql_endpoint(
    request: ModelSqlRefinementRequest,
    x_llm_api_key: Optional[str] = Header(default=None, alias="X-LLM-API-Key"),
    x_llm_provider: Optional[str] = Header(default=None, alias="X-LLM-Provider"),
):
    """
    Interactively refines domain entity models, fields, and constraints,
    re-synchronizing SQL DDL and Mermaid ER diagrams.
    """
    provider = request.provider or x_llm_provider
    api_key = resolve_api_key(request.apiKey, x_llm_api_key, provider=provider)
    try:
        refined = model_sql_service.refine_domain_models_and_sql(
            current_response=request.currentResponse,
            feedback_prompt=request.feedbackPrompt,
            target_entity=request.targetEntity,
            api_key=api_key,
            provider=provider,
        )
        return refined
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refine domain models and SQL schema: {str(e)}",
        )

