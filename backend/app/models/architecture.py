from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

try:
    from app.models.requirements import SpecificationDraft
    from app.models.blueprint import ArchitectureBlueprint, DomainEntity, UserStoryRecord
except ImportError:
    from backend.app.models.requirements import SpecificationDraft
    from backend.app.models.blueprint import ArchitectureBlueprint, DomainEntity, UserStoryRecord

class LayerType(str, Enum):
    CONTROLLER = "controller"
    SERVICE = "service"
    REPOSITORY = "repository"
    MODEL = "model"
    INFRASTRUCTURE = "infrastructure"

class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"

class InteractionType(str, Enum):
    CALLS = "calls"
    PERSISTS = "persists"
    MAPS = "maps"
    INTERCEPTS = "intercepts"

class ComponentDefinition(BaseModel):
    name: str = Field(..., description="PascalCase component name, e.g. OrderController, OrderService")
    layer: LayerType = Field(..., description="Architectural layer")
    stereotype: str = Field(..., description="Spring stereotype, e.g. @RestController, @Service, @Repository")
    packageName: str = Field(..., description="Full Java package name, e.g. com.corp.order.controller")
    responsibilities: List[str] = Field(default_factory=list, description="List of component responsibilities")
    dependencies: List[str] = Field(default_factory=list, description="Target component names this component depends on")
    mappedStories: List[str] = Field(default_factory=list, description="Associated user story IDs, e.g. US-1")

class ApiEndpointDefinition(BaseModel):
    method: HttpMethod = Field(..., description="HTTP Method")
    path: str = Field(..., description="Route URI, e.g. /api/v1/orders")
    summary: str = Field(..., description="Operation summary")
    requestDto: Optional[str] = Field(default=None, description="Inbound Java Record name, e.g. CreateOrderRequest")
    responseDto: Optional[str] = Field(default=None, description="Outbound Java Record name, e.g. OrderResponse")
    successStatus: int = Field(default=200, description="Expected HTTP success code, e.g. 200, 201")
    errorStatuses: List[int] = Field(default_factory=lambda: [400, 500], description="Expected HTTP error codes")
    mappedScenarioId: Optional[str] = Field(default=None, description="Linked acceptance scenario ID, e.g. AC-1.1")

class ComponentInteraction(BaseModel):
    sourceComponent: str = Field(..., description="Calling component name")
    targetComponent: str = Field(..., description="Target component name")
    interactionType: InteractionType = Field(default=InteractionType.CALLS, description="Type of interaction")

class ArchitectureDesignRequest(BaseModel):
    draft: SpecificationDraft = Field(..., description="Specification draft with entities and user stories")
    apiKey: Optional[str] = Field(default=None, description="Optional ephemeral LLM API key")
    provider: Optional[str] = Field(default=None, description="Optional LLM provider: 'gemini', 'groq', 'openai', or 'mock'")
    modelName: Optional[str] = Field(default=None, description="Optional custom LLM model name")

class ArchitectureDesignResponse(BaseModel):
    serviceName: str = Field(..., description="Hyphenated service name, e.g. order-service")
    packageName: str = Field(..., description="Base Java package, e.g. com.corp.order")
    basePort: int = Field(default=8080, description="Service HTTP port")
    components: List[ComponentDefinition] = Field(default_factory=list, description="Component catalog")
    endpoints: List[ApiEndpointDefinition] = Field(default_factory=list, description="REST endpoints catalog")
    interactions: List[ComponentInteraction] = Field(default_factory=list, description="Component interaction flows")
    mermaidDiagram: str = Field(default="", description="Pre-rendered Mermaid flowchart code")
    architectureMarkdown: str = Field(default="", description="Pre-rendered architecture documentation markdown")
    openapiYaml: str = Field(default="", description="Pre-rendered OpenAPI 3.0 specification in YAML")
    entities: List[DomainEntity] = Field(default_factory=list, description="Domain entities preserved from draft")
    userStories: List[UserStoryRecord] = Field(default_factory=list, description="User stories preserved from draft")

    def to_blueprint(self) -> ArchitectureBlueprint:
        """Convert design into a fully-compliant ArchitectureBlueprint for Feature 001 generation."""
        return ArchitectureBlueprint(
            serviceName=self.serviceName,
            packageName=self.packageName,
            basePort=self.basePort,
            entities=self.entities,
            userStories=self.userStories,
        )

class ArchitectureRefinementRequest(BaseModel):
    currentDesign: ArchitectureDesignResponse = Field(..., description="Current architecture design state")
    feedbackPrompt: str = Field(..., min_length=3, description="User feedback or delta adjustment prompt")
    targetComponent: Optional[str] = Field(default=None, description="Optional specific component to modify")
    apiKey: Optional[str] = Field(default=None, description="Optional ephemeral LLM API key")
    provider: Optional[str] = Field(default=None, description="Optional LLM provider: 'gemini', 'groq', 'openai', or 'mock'")
    modelName: Optional[str] = Field(default=None, description="Optional custom LLM model name")

