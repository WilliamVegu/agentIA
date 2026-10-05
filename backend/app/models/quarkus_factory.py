"""
Modelos de Datos para la Fábrica de Agentes Java Quarkus (Lorena - Pedido 2).
Enfoque Contract-First, 5 Bloques de Pedido, Tracking de Estados y 2 Controles Humanos.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, ConfigDict
import uuid


class BuildToolEnum(str, Enum):
    MAVEN = "maven"
    GRADLE = "gradle"


class AIModeEnum(str, Enum):
    CONTINUO = "Continuo (Sin límite)"  # Medidor en tiempo real sin restricción de límite de tokens
    BAJO = "Bajo"      # Lógica básica asistida
    MEDIO = "Medio"    # Lógica completa de servicios y pruebas
    ALTO = "Alto"      # Arquitectura avanzada, alta cobertura y revisor


class OrderStatusEnum(str, Enum):
    RECIBIDO = "Recibido"
    CONTRATO_EN_REVISION = "Contrato en revisión"
    APROBADO = "Aprobado"
    GENERANDO = "Generando"
    PROBANDO = "Probando"
    EN_REVISION = "En revisión"
    ENTREGADO = "Entregado"
    FALLIDO = "Fallido"


class ArchitecturePatternEnum(str, Enum):
    LAYERED = "layered"          # Capas estándar (Resource -> Service -> Panache Entity)
    HEXAGONAL = "hexagonal"      # Puertos y Adaptadores (Domain Core -> Ports -> Adapters)
    REACTIVE = "reactive"        # Mutiny Reactive Streams + Panache Reactive + Kafka


class DatabaseEnum(str, Enum):
    SQL_SERVER = "SQL Server"
    AZURE_SQL = "Azure SQL"
    SQLITE = "SQLite (Demo local portable)"
    POSTGRESQL = "PostgreSQL"
    H2 = "H2 (En memoria)"
    MYSQL = "MySQL"


class SecurityEnum(str, Enum):
    JWT = "JWT (SmallRye JWT)"
    OAUTH2 = "OAuth2 / OIDC"
    NONE = "Sin autenticación"


# ==========================================
# 5 BLOQUES DEL PEDIDO (ENTRADA DEL PROGRAMA)
# ==========================================

class BasicDataBlock(BaseModel):
    """Bloque 1: Datos básicos del microservicio"""
    service_name: str = Field(default="microservice", description="Nombre del servicio")
    team: str = Field(default="Backend Core", description="Equipo responsable")
    group_id: str = Field(default="com.empresa.service", description="GroupId Maven/Gradle")
    java_version: str = Field(default="21", description="Versión de Java (11, 17, 21)")
    build_tool: BuildToolEnum = Field(default=BuildToolEnum.MAVEN, description="Herramienta de construcción preferida")


class BusinessRequirementBlock(BaseModel):
    """Bloque 2: Qué debe hacer (texto libre de negocio)"""
    description: str = Field(
        default="",
        description="Entidades, operaciones, reglas de negocio y casos de error (sin tecnología)."
    )


class TechnicalRequirementsBlock(BaseModel):
    """Bloque 3: Requisitos técnicos (opciones)"""
    database: DatabaseEnum = Field(default=DatabaseEnum.SQLITE, description="Base de datos seleccionada")
    security: SecurityEnum = Field(default=SecurityEnum.JWT, description="Mecanismo de seguridad")
    enable_kafka: bool = Field(default=False, description="Mensajería asíncrona con Apache Kafka")
    integraciones: List[str] = Field(default_factory=list, description="Integraciones con otros servicios o APIs")


class AIModeBlock(BaseModel):
    """Bloque 4: Modo de IA y medidor continuo de tokens"""
    mode: str = Field(default="Continuo (Sin límite)", description="Modo de uso de IA / Medidor continuo sin restricción de límite")
    estimated_tokens_min: int = Field(default=0, description="Tokens consumidos base")
    estimated_tokens_max: int = Field(default=0, description="0 indica sin límite restrictivo (Ilimitado)")


class AttachmentsBlock(BaseModel):
    """Bloque 5: Adjuntos opcionales"""
    existing_openapi: Optional[str] = Field(default=None, description="Contrato OpenAPI preexistente (si viene, omite redacción)")
    support_docs: List[str] = Field(default_factory=list, description="Documentos de apoyo o contexto de negocio")


class CreateOrderRequest(BaseModel):
    """Payload completo para ingresar un pedido a la fábrica"""
    basic_data: BasicDataBlock = Field(default_factory=BasicDataBlock)
    business: BusinessRequirementBlock = Field(default_factory=BusinessRequirementBlock)
    technical: TechnicalRequirementsBlock = Field(default_factory=TechnicalRequirementsBlock)
    ai_mode: Optional[AIModeBlock] = Field(default_factory=AIModeBlock)
    attachments: Optional[AttachmentsBlock] = Field(default_factory=AttachmentsBlock)


# ==========================================
# PREGUNTAS DE ACLARACIÓN (AGENTE ANALISTA)
# ==========================================

class ClarificationQuestion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    category: Optional[str] = Field(
        default="Negocio",
        description="Dimensión: Objetivo, Necesidad, Usuarios, Funcionalidades, Información, Reglas del negocio, Validaciones, Flujo de trabajo, Notificaciones, Reportes, Integraciones, Prioridad"
    )
    question: str
    context_or_reason: str
    suggested_options: List[str] = Field(default_factory=list)
    user_answer: Optional[str] = None


class ClarificationAnswerItem(BaseModel):
    question_id: str
    answer: str


class SubmitAnswersRequest(BaseModel):
    answers: List[ClarificationAnswerItem]


# ==========================================
# HISTORIAS DE USUARIO & MODELO DE BASE DE DATOS
# ==========================================

class BddScenario(BaseModel):
    title: str
    given: str
    when: str
    then: str


class UserStory(BaseModel):
    id: str  # e.g., "US-01"
    title: str
    role: str       # "Como cliente", "Como administrador"
    goal: str       # "quiero registrar un pedido con ítems"
    benefit: str    # "para recibir mis productos"
    scenarios: List[BddScenario] = Field(default_factory=list)


class ColumnDefinition(BaseModel):
    name: str
    data_type: str     # VARCHAR(100), UUID, DECIMAL(10,2), TIMESTAMP, INTEGER, BOOLEAN
    is_primary_key: bool = False
    is_foreign_key: bool = False
    references: Optional[str] = None  # e.g., "pedidos(id)"
    is_nullable: bool = False
    description: str = ""


class TableDefinition(BaseModel):
    name: str
    description: str
    columns: List[ColumnDefinition] = Field(default_factory=list)


class RelationshipDefinition(BaseModel):
    source_table: str
    target_table: str
    relation_type: str  # "1:N", "N:M", "1:1"
    description: str


class DatabaseModelProposal(BaseModel):
    database_engine: str  # SQLite, SQL Server, etc.
    tables: List[TableDefinition] = Field(default_factory=list)
    relationships: List[RelationshipDefinition] = Field(default_factory=list)
    mermaid_er_diagram: str
    ddl_sql: str
    validation_notes: List[str] = Field(default_factory=list)


# ==========================================
# CONTROL 1: REVISIÓN Y APROBACIÓN DE CONTRATO Y MODELO DE DATOS
# ==========================================

class ApproveContractRequest(BaseModel):
    approved_by: str = Field("Usuario (Product Owner)", description="Identificación del aprobador")
    comments: Optional[str] = Field(None)
    modified_openapi: Optional[str] = Field(None, description="OpenAPI modificado si el usuario hizo ediciones directas")
    modified_user_stories: Optional[List[UserStory]] = Field(None, description="Historias de usuario modificadas o agregadas por el usuario")
    modified_database_model: Optional[DatabaseModelProposal] = Field(None, description="Modelo de base de datos modificado o agregado por el usuario")
    approve_database_model: bool = Field(True, description="Confirmación de validación del modelo de base de datos relacional")


# ==========================================
# ARQUITECTURA & ARQUETIPO (AGENTE ARQUITECTO)
# ==========================================

class ArchitectureOption(BaseModel):
    id: ArchitecturePatternEnum
    title: str
    description: str
    structure_layers: List[str]
    pros: List[str]
    cons: List[str]
    recommended_for: str
    is_recommended: bool = False


class ArchetypePreview(BaseModel):
    build_tool: BuildToolEnum
    config_file_name: str  # pom.xml o build.gradle
    config_file_content: str
    folder_tree: List[str]
    command_dev: str
    command_test: str
    summary_features: List[str]


class QuarkusExtensionItem(BaseModel):
    id: str = Field(..., description="Coordenadas Maven (ej. io.quarkus:quarkus-resteasy-reactive-jackson)")
    name: str = Field(..., description="Nombre legible de la extensión")
    version: str = Field("3.15.1", description="Versión exacta compatible con Quarkus 3.x")
    category: str = Field("General", description="Categoría: Web & REST, Persistencia, Observabilidad, Seguridad, etc.")
    description: str = Field("", description="Propósito de la extensión en el microservicio")
    is_selected: bool = Field(True, description="Estado de selección del usuario")
    is_mandatory: bool = Field(False, description="Si es requerida por la constitución o arquitectura")


class ArchitectureProposal(BaseModel):
    options: List[ArchitectureOption]
    selected_option: ArchitecturePatternEnum
    recommended_extensions: List[str]
    quarkus_extensions: List[QuarkusExtensionItem] = Field(default_factory=list)
    maven_preview: ArchetypePreview
    gradle_preview: ArchetypePreview


class SelectArchitectureRequest(BaseModel):
    selected_pattern: ArchitecturePatternEnum
    chosen_build_tool: BuildToolEnum
    extensions: List[str] = Field(default_factory=list)
    selected_extensions: List[QuarkusExtensionItem] = Field(default_factory=list)


class SuggestExtensionRequest(BaseModel):
    query: str = Field(..., description="Necesidad o funcionalidad requerida para consultar a la IA")


class SuggestedExtensionResponse(BaseModel):
    id: str
    name: str
    version: str = "3.15.1"
    category: str = "Integración"
    description: str
    justification: str
    usage_example: str


class GenerateArchetypeRequest(BaseModel):
    selected_pattern: ArchitecturePatternEnum = ArchitecturePatternEnum.LAYERED
    chosen_build_tool: BuildToolEnum = BuildToolEnum.MAVEN
    extensions: List[QuarkusExtensionItem] = Field(default_factory=list)


# ==========================================
# CONTROL 2: REVISIÓN DE ENTREGA & DEVOPS
# ==========================================

class ApproveDeliveryRequest(BaseModel):
    approved_by: str = Field("Usuario (Control 2)")
    comments: Optional[str] = None
    target_git_repo: Optional[str] = Field("https://github.com/empresa/orders-service.git")
    branch_name: Optional[str] = Field("feat/quarkus-microservice-orders")
    git_token: Optional[str] = Field(None, description="Personal Access Token (PAT) efímero para Git")
    commit_message: Optional[str] = Field(None, description="Mensaje de commit opcional")


class PublishQuarkusGitRequest(BaseModel):
    repository_url: str = Field(..., description="URL destino del repositorio Git (HTTPS)")
    branch_name: str = Field(..., description="Nombre de la rama feature")
    git_token: Optional[str] = Field(None, description="Personal Access Token (PAT) efímero")
    commit_message: Optional[str] = Field(
        default="feat(quarkus): microservicio Quarkus 3.x generado y verificado",
        description="Mensaje del commit en Git"
    )


class PublishQuarkusGitResponse(BaseModel):
    branch_url: str = Field(..., alias="branchUrl")
    commit_hash: str = Field(..., alias="commitHash")
    pull_request_url: Optional[str] = Field(None, alias="pullRequestUrl")
    branch_name: str = Field(..., alias="branchName")
    status: str = "PUBLICADO"



# ==========================================
# TRACKING & AUDITORÍA INTEGRAL DEL PEDIDO
# ==========================================

class SpecializedAgentInfo(BaseModel):
    id: str = Field(..., description="Identificador único del agente (requirements, architecture, etc.)")
    number: int = Field(..., description="Número de orden en el pipeline (1 a 8)")
    name: str = Field(..., description="Nombre del agente con emoji")
    role: str = Field(..., description="Misión y responsabilidad del agente")
    status: str = Field("Pendiente", description="Estado actual: Pendiente, En progreso, Completado, Activo")
    tokens_consumed: int = Field(0, description="Tokens consumidos específicamente por este agente")
    deliverables: List[str] = Field(default_factory=list, description="Artefactos y entregables producidos")


class TokensAudit(BaseModel):
    estimated_range: List[int] = Field(default_factory=lambda: [0, 0])
    is_unlimited: bool = Field(default=True, description="Medidor continuo activo sin restricción de tokens")
    by_agent: Dict[str, int] = Field(default_factory=lambda: {
        # 8 Agentes Especializados
        "requirements": 0,
        "architecture": 0,
        "coding": 0,
        "database": 0,
        "security": 0,
        "testing_debug": 0,
        "code_review": 0,
        "devops": 0,
        # Claves legacy para compatibilidad
        "analista": 0,
        "arquitecto": 0,
        "desarrollador": 0,
        "qa": 0,
        "documentador": 0,
        "revisor": 0,
    })
    total_consumed: int = 0


class FactoryOrder(BaseModel):
    """Entidad principal que rastrea el ciclo de vida del pedido en la fábrica"""
    id: str = Field(default_factory=lambda: f"ORD-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    status: OrderStatusEnum = OrderStatusEnum.RECIBIDO

    # Datos del pedido
    basic_data: BasicDataBlock
    business: BusinessRequirementBlock
    technical: TechnicalRequirementsBlock
    ai_mode: AIModeBlock
    attachments: AttachmentsBlock

    # Aclaraciones (Agente Analista)
    clarification_questions: List[ClarificationQuestion] = Field(default_factory=list)
    clarifications_completed: bool = False

    # Contrato OpenAPI, Historias de Usuario & Modelo Relacional (Agente Analista)
    openapi_contract: Optional[str] = None
    user_stories: List[UserStory] = Field(default_factory=list)
    database_model: Optional[DatabaseModelProposal] = None
    database_model_approved: bool = False
    control_1_approved: bool = False
    control_1_approval_info: Optional[Dict[str, Any]] = None

    # Arquitectura, Arquetipo y Extensiones Quarkus
    architecture_proposal: Optional[ArchitectureProposal] = None
    chosen_architecture: Optional[Dict[str, Any]] = None
    quarkus_extensions: List[QuarkusExtensionItem] = Field(default_factory=list)

    # Esqueleto y Código (Scaffolder, Desarrollador, QA)
    skeleton_generated: bool = False
    code_generated: bool = False
    tests_executed: bool = False
    tests_summary: Optional[Dict[str, Any]] = None
    correction_attempts_used: int = 0
    self_healing_log: List[Dict[str, Any]] = Field(default_factory=list)
    code_review_report: Optional[Dict[str, Any]] = None
    generated_files: Dict[str, str] = Field(default_factory=dict)

    # Documentación (Agente Documentador)
    documentation: Dict[str, str] = Field(default_factory=dict)

    # Control 2 y DevOps (Agente DevOps)
    control_2_approved: bool = False
    control_2_approval_info: Optional[Dict[str, Any]] = None
    devops_artifacts: Dict[str, str] = Field(default_factory=dict)

    # Auditoría transversal
    tokens_audit: TokensAudit = Field(default_factory=TokensAudit)
    specialized_agents: List[SpecializedAgentInfo] = Field(default_factory=list)
    step_durations_sec: Dict[str, float] = Field(default_factory=dict)
    timeline_events: List[Dict[str, Any]] = Field(default_factory=list)

