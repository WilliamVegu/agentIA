import re
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

class EntityAttribute(BaseModel):
    name: str = Field(..., description="camelCase attribute name")
    type: str = Field(..., description="Java type, e.g. String, Long, UUID, BigDecimal")
    columnName: Optional[str] = Field(default=None, description="Explicit SQL column name")
    referencesEntity: Optional[str] = Field(default=None, description="Explicit foreign key target entity")
    referencesAttribute: Optional[str] = Field(default=None, description="Target primary key attribute; defaults to declared PK")
    required: bool = Field(default=False)
    nullable: bool = Field(default=False)
    isPrimaryKey: bool = Field(default=False)
    isUnique: bool = Field(default=False, description="True if unique constraint applies")
    validationRules: List[str] = Field(default_factory=list, description="Jakarta Validation annotations e.g. @NotNull")

class DomainEntity(BaseModel):
    name: str = Field(..., description="PascalCase entity name, e.g. Order, Payment")
    tableName: str = Field(..., description="snake_case table name, e.g. orders, payments")
    attributes: List[EntityAttribute] = Field(..., min_length=1)

class LayerDefinition(BaseModel):
    name: str = Field(..., description="Layer name: controller, service, repository, model")
    packageNameSuffix: str = Field(..., description="Suffix: .controller, .service, .repository, .model")

class AcceptanceScenarioRecord(BaseModel):
    scenarioId: str = Field(..., description="Identifier e.g. AC-1.1")
    given: str = Field(..., min_length=3, description="Preconditions")
    when: str = Field(..., min_length=3, description="Triggering action")
    then: str = Field(..., min_length=3, description="Expected outcome")

class UserStoryRecord(BaseModel):
    id: str = Field(..., description="User story ID e.g. US-1")
    priority: str = Field(default="P1", pattern="^P[1-9]$")
    role: str = Field(..., min_length=2)
    intent: str = Field(..., min_length=3)
    benefit: str = Field(..., min_length=3)
    scenarios: List[AcceptanceScenarioRecord] = Field(..., min_length=1)

class InputInterface(BaseModel):
    """Interfaz de entrada (feature 'levantando_observaciones'): lo que impulsa la
    inferencia de arquitectura. Campos de entrada + preferencias elegibles."""
    requestVolume: str = Field(default="low", description="low | medium | high (throughput tier)")
    expectedQps: Optional[int] = Field(default=None, ge=0, description="Expected requests per second")
    dataNeeds: List[str] = Field(default_factory=list, description="relational | document | cache | fulltext | blob")
    integrations: List[str] = Field(default_factory=list, description="messaging | external-http | scheduler | none")
    consistency: str = Field(default="strong", description="strong | eventual")
    architecturePreference: Optional[str] = Field(default=None, description="layered | hexagonal | hexagonal-ddd (None = infer)")
    buildToolPreference: Optional[str] = Field(default=None, pattern="^(maven|gradle)$", description="maven | gradle (None = default del perfil)")


class ArchitectureBlueprint(BaseModel):
    serviceName: str = Field(..., pattern="^[a-z0-9-]+$")
    packageName: str = Field(..., description="Base Java package, e.g. com.corp.order")
    basePort: int = Field(default=8080, ge=1024, le=65535)
    databaseMode: str = Field(default="PostgreSQL")
    inputInterface: Optional[InputInterface] = Field(
        default=None,
        description="Interfaz de entrada que decide arquitectura, DB, build tool y librerías",
    )
    layers: List[LayerDefinition] = Field(
        default_factory=lambda: [
            LayerDefinition(name="controller", packageNameSuffix=".controller"),
            LayerDefinition(name="service", packageNameSuffix=".service"),
            LayerDefinition(name="repository", packageNameSuffix=".repository"),
            LayerDefinition(name="model", packageNameSuffix=".model"),
        ]
    )
    entities: List[DomainEntity] = Field(..., min_length=1)
    userStories: List[UserStoryRecord] = Field(..., min_length=1)

    @field_validator("packageName")
    @classmethod
    def validate_package(cls, v: str) -> str:
        if not re.match(r"^[a-z]+(\.[a-z][a-z0-9]*)*$", v):
            raise ValueError("Invalid Java package format")
        return v

class SpecificationSummary(BaseModel):
    specId: str
    serviceName: str
    packageName: str
    entityCount: int
    storyCount: int
    isValid: bool
    validationWarnings: List[str] = Field(default_factory=list)

