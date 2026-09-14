from typing import Optional
from fastapi import APIRouter, Header, HTTPException, status

try:
    from app.models.architecture import (
        ArchitectureDesignRequest,
        ArchitectureRefinementRequest,
        ArchitectureDesignResponse,
    )
    from app.models.requirements import ApiErrorResponse
    from app.api.routes_requirements import resolve_api_key
    from app.services.architecture_service import (
        design_architecture,
        refine_architecture,
    )
except ImportError:
    from backend.app.models.architecture import (
        ArchitectureDesignRequest,
        ArchitectureRefinementRequest,
        ArchitectureDesignResponse,
    )
    from backend.app.models.requirements import ApiErrorResponse
    from backend.app.api.routes_requirements import resolve_api_key
    from backend.app.services.architecture_service import (
        design_architecture,
        refine_architecture,
    )

router = APIRouter(prefix="/architecture", tags=["Architecture & Component Design"])

@router.post(
    "/design",
    response_model=ArchitectureDesignResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ApiErrorResponse, "description": "Invalid specification draft"},
        401: {"model": ApiErrorResponse, "description": "Missing API Key"},
        500: {"model": ApiErrorResponse, "description": "Internal server error"},
    },
)
async def design_architecture_endpoint(
    request: ArchitectureDesignRequest,
    x_llm_api_key: Optional[str] = Header(default=None, alias="X-LLM-API-Key"),
    x_llm_provider: Optional[str] = Header(default=None, alias="X-LLM-Provider"),
):
    """
    Synthesizes a formal 4-layer Spring Boot 3 architecture, component catalog,
    REST endpoints, Mermaid flowchart, and OpenAPI 3.0 specification from a specification draft.
    """
    api_key = resolve_api_key(request.apiKey, x_llm_api_key)
    provider = request.provider or x_llm_provider
    try:
        design = design_architecture(request, api_key, provider=provider)
        return design
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to synthesize architecture: {str(e)}",
        )

@router.post(
    "/refine",
    response_model=ArchitectureDesignResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ApiErrorResponse, "description": "Invalid refinement payload"},
        401: {"model": ApiErrorResponse, "description": "Missing API Key"},
        500: {"model": ApiErrorResponse, "description": "Internal server error"},
    },
)
async def refine_architecture_endpoint(
    request: ArchitectureRefinementRequest,
    x_llm_api_key: Optional[str] = Header(default=None, alias="X-LLM-API-Key"),
    x_llm_provider: Optional[str] = Header(default=None, alias="X-LLM-Provider"),
):
    """
    Applies natural language feedback or delta adjustments to update the component
    catalog, layers, or REST endpoints.
    """
    api_key = resolve_api_key(request.apiKey, x_llm_api_key)
    provider = request.provider or x_llm_provider
    try:
        refined_design = refine_architecture(request, api_key, provider=provider)
        return refined_design
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refine architecture: {str(e)}",
        )

