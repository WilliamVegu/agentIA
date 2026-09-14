from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field

try:
    from app.models.blueprint import (
        DomainEntity,
        EntityAttribute,
        UserStoryRecord,
        AcceptanceScenarioRecord,
        ArchitectureBlueprint,
    )
except ImportError:
    from backend.app.models.blueprint import (
        DomainEntity,
        EntityAttribute,
        UserStoryRecord,
        AcceptanceScenarioRecord,
        ArchitectureBlueprint,
    )

class RequirementsTransformRequest(BaseModel):
    rawText: str = Field(
        ...,
        min_length=10,
        description="Raw requirements narrative, bullet points, or user notes (minimum 10 characters).",
    )
    serviceName: Optional[str] = Field(
        default=None,
        description="Optional pre-assigned service name (e.g. billing-service).",
    )
    packageName: Optional[str] = Field(
        default=None,
        description="Optional base Java package (e.g. com.corp.billing).",
    )
    apiKey: Optional[str] = Field(
        default=None,
        description="Optional ephemeral LLM API key.",
    )
    provider: Optional[str] = Field(
        default=None,
        description="Optional LLM provider: 'gemini', 'groq', 'openai', or 'mock'.",
    )
    modelName: Optional[str] = Field(
        default=None,
        description="Optional custom LLM model name (e.g. 'gemini-2.0-flash', 'llama-3.3-70b-versatile').",
    )

class SpecificationDraft(BaseModel):
    serviceName: str = Field(..., description="Hyphenated service name (e.g. payment-service).")
    packageName: str = Field(..., description="Reverse domain Java package (e.g. com.corp.payment).")
    basePort: int = Field(default=8080, description="Default port (8080).")
    entities: List[DomainEntity] = Field(default_factory=list, description="List of extracted domain entities.")
    userStories: List[UserStoryRecord] = Field(
        default_factory=list,
        description="List of synthesized stories, each with role, intent, benefit, and >= 2 acceptance scenarios.",
    )
    assumptions: List[str] = Field(
        default_factory=list,
        description="List of assumptions made during analysis.",
    )
    markdownSpec: str = Field(
        default="",
        description="Pre-rendered Spec Kit compliant spec.md string for download.",
    )

    def to_blueprint(self) -> ArchitectureBlueprint:
        """Convert SpecificationDraft into an ArchitectureBlueprint for Feature 001 handoff."""
        return ArchitectureBlueprint(
            serviceName=self.serviceName,
            packageName=self.packageName,
            basePort=self.basePort,
            entities=self.entities,
            userStories=self.userStories,
        )

class RefinementRequest(BaseModel):
    currentDraft: SpecificationDraft = Field(
        ...,
        description="Current state of the draft specification including entities and user stories.",
    )
    feedbackPrompt: str = Field(
        ...,
        min_length=3,
        description="User natural language instructions (e.g. 'add a negative test for balance below zero').",
    )
    targetStoryId: Optional[str] = Field(
        default=None,
        description="Optional identifier of a specific story to re-synthesize (e.g. US-2). If omitted, applies globally.",
    )
    apiKey: Optional[str] = Field(
        default=None,
        description="Optional ephemeral LLM API key.",
    )
    provider: Optional[str] = Field(
        default=None,
        description="Optional LLM provider: 'gemini', 'groq', 'openai', or 'mock'.",
    )
    modelName: Optional[str] = Field(
        default=None,
        description="Optional custom LLM model name.",
    )

class ApiErrorResponse(BaseModel):
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp",
    )
    status: int = Field(..., description="HTTP status code")
    message: str = Field(..., description="Human-readable error description")
    details: List[str] = Field(default_factory=list, description="Additional context or validation errors")

