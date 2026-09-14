from fastapi import APIRouter, File, UploadFile, HTTPException, status
from app.models.blueprint import ArchitectureBlueprint, SpecificationSummary
from app.services.spec_service import parse_spec_markdown, save_specification, get_specification

router = APIRouter(prefix="/specifications", tags=["Specifications"])

@router.post("/upload", response_model=SpecificationSummary, status_code=status.HTTP_201_CREATED)
async def upload_specification_file(file: UploadFile = File(...)):
    """Ingests a standard Spec Kit Markdown file and returns parsed blueprint summary."""
    try:
        content_bytes = await file.read()
        content_str = content_bytes.decode("utf-8")
        blueprint = parse_spec_markdown(content_str)
        summary = save_specification(blueprint)
        return summary
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be valid UTF-8 text")
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to parse specification: {str(exc)}")

@router.post("", response_model=SpecificationSummary, status_code=status.HTTP_201_CREATED)
async def submit_specification_json(payload: ArchitectureBlueprint):
    """Directly ingests a structured JSON architecture blueprint."""
    try:
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

