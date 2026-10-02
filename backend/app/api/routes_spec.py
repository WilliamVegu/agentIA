from typing import Optional

from fastapi import APIRouter, File, Header, UploadFile, HTTPException, status
from app.models.blueprint import ArchitectureBlueprint, SpecificationSummary
from app.services.injection_guard import PromptInjectionError, assert_no_injection
from app.services.injection_judge import JudgeRefusal, is_blocking, judge_document
from app.services.llm_factory import LLMFactory
from app.services.specification_guard import UnlikelySpecificationError
from app.services.spec_service import parse_spec_markdown, save_specification, get_specification

router = APIRouter(prefix="/specifications", tags=["Specifications"])

@router.post("/upload", response_model=SpecificationSummary, status_code=status.HTTP_201_CREATED)
async def upload_specification_file(file: UploadFile = File(...)):
    """Ingests a standard Spec Kit Markdown file and returns parsed blueprint summary."""
    try:
        content_bytes = await file.read()
        content_str = content_bytes.decode("utf-8")
        blueprint = parse_spec_markdown(content_str)
        assert_no_injection(blueprint, field="spec.md")
        summary = save_specification(blueprint)
        return summary
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be valid UTF-8 text")
    except PromptInjectionError as injected:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=injected.to_dict())
    except UnlikelySpecificationError as unlikely:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=unlikely.to_dict())
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to parse specification: {str(exc)}")

@router.post("", response_model=SpecificationSummary, status_code=status.HTTP_201_CREATED)
async def submit_specification_json(
    payload: ArchitectureBlueprint,
    x_llm_api_key: Optional[str] = Header(default=None, alias="X-LLM-API-Key"),
    x_llm_provider: Optional[str] = Header(default=None, alias="X-LLM-Provider"),
):
    """Directly ingests a structured JSON architecture blueprint.

    Two guard layers run before the spec is stored: the deterministic heuristic
    (refuses known instruction-shaped attempts) and, when a model key is supplied,
    a constrained LLM judge (refuses strong injection verdicts). Offline submits
    without a key are still guarded by the heuristic.
    """
    try:
        assert_no_injection(payload, field="blueprint")

        # Second layer: constrained LLM judge, only when a real client is available.
        if x_llm_api_key and not LLMFactory.is_mock(x_llm_api_key, x_llm_provider):
            try:
                client = LLMFactory.get_chat_model(
                    api_key=x_llm_api_key, provider=x_llm_provider, temperature=0.0
                )
            except Exception:  # noqa: BLE001 — a judge outage must not block ingestion
                client = None
            if client is not None:
                verdict = judge_document(payload, client)
                if is_blocking(verdict):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Prompt-injection rejected by LLM judge: {verdict.reason}",
                    )

        summary = save_specification(payload)
        return summary
    except PromptInjectionError as injected:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=injected.to_dict())
    except JudgeRefusal:
        # The judge could not be constrained; fall through to the heuristic-only
        # outcome rather than blocking valid work on a judge that did not answer.
        summary = save_specification(payload)
        return summary
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))

@router.get("/{spec_id}", response_model=ArchitectureBlueprint)
async def get_specification_by_id(spec_id: str):
    """Retrieves the full blueprint by its ID."""
    try:
        return get_specification(spec_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Specification not found")

