from datetime import datetime, timezone
from enum import Enum
import uuid
from typing import Optional

from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, Enum as SQLEnum
from sqlalchemy.orm import declarative_base, sessionmaker
from pydantic import BaseModel, Field

from app.config import settings

Base = declarative_base()
engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class SessionStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"

class SessionPhase(str, Enum):
    INITIALIZATION = "INITIALIZATION"
    SCAFFOLDING = "SCAFFOLDING"
    CODE_GENERATION = "CODE_GENERATION"
    TEST_SYNTHESIS = "TEST_SYNTHESIS"
    SANDBOX_BUILD = "SANDBOX_BUILD"
    TEST_EXECUTION = "TEST_EXECUTION"
    SELF_REPAIR = "SELF_REPAIR"
    SELF_REPAIR_LOOP = "SELF_REPAIR_LOOP"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"

class GenerationSessionDB(Base):
    __tablename__ = "generation_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    spec_id = Column(String(36), nullable=False)
    spec_name = Column(String(100), nullable=False)
    status = Column(SQLEnum(SessionStatus), nullable=False, default=SessionStatus.QUEUED)
    phase = Column(SQLEnum(SessionPhase), nullable=False, default=SessionPhase.INITIALIZATION)
    queue_position = Column(Integer, nullable=True, default=0)
    repair_attempts = Column(Integer, nullable=False, default=0)
    execution_mode = Column(String(20), nullable=False, default="SOURCE_ONLY")
    database_engine = Column(String(20), nullable=False, default="POSTGRESQL")
    current_lifecycle_phase = Column(String(50), nullable=True, default="INITIAL")
    lifecycle_mode = Column(String(50), nullable=True, default="GUIDED_STEP")
    phase_progress_json = Column(Text, nullable=True)
    # Feature 011 additive storage (T013). Deliberately NEW columns rather than
    # reuse of phase_progress_json: the specification does not permit assuming an
    # existing column changes meaning. Records provider and model identifiers only
    # — never credentials (FR-018, Constitution VI).
    generation_journal_json = Column(Text, nullable=True)
    artifact_provenance_json = Column(Text, nullable=True)
    # Feature 012 additive storage. Holds the serialized VerificationMetrics so
    # the session detail endpoint can report whether verification actually ran,
    # including after a process restart (the in-process state does not survive).
    verification_metrics_json = Column(Text, nullable=True)
    # Feature 013 additive storage. Holds the session's cost aggregate so the
    # session detail surface can report what a session cost without reading the
    # cost store. The cost store remains the system of record; this is a copy.
    cost_record_json = Column(Text, nullable=True)
    revision_id = Column(String(36), nullable=True)
    configuration_version = Column(Integer, nullable=False, default=0)
    operation_version = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

from pydantic import BaseModel, Field, ConfigDict

# Pydantic Response Schemas
from app.models.execution import ExecutionMode, VerificationOutcome
from app.models.devops import DatabaseEngine
class GenerationSessionSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(..., alias="sessionId")
    status: SessionStatus
    execution_mode: ExecutionMode = Field(ExecutionMode.SOURCE_ONLY, alias="executionMode")
    queue_position: Optional[int] = Field(0, alias="queuePosition")
    stream_url: str = Field(..., alias="streamUrl")

class GenerationSessionListItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(..., alias="sessionId")
    spec_id: Optional[str] = Field(None, alias="specId")
    spec_name: str = Field(..., alias="specName")
    status: SessionStatus
    execution_mode: ExecutionMode = Field(ExecutionMode.SOURCE_ONLY, alias="executionMode")
    verification_outcome: VerificationOutcome = Field(VerificationOutcome.NOT_RUN, alias="verificationOutcome")
    error_message: Optional[str] = Field(None, alias="errorMessage")
    phase: Optional[SessionPhase] = Field(None, alias="phase")
    current_lifecycle_phase: Optional[str] = Field("INITIAL", alias="currentLifecyclePhase")
    lifecycle_mode: Optional[str] = Field("GUIDED_STEP", alias="lifecycleMode")
    completion_percentage: float = Field(0.0, alias="completionPercentage")
    created_at: datetime = Field(..., alias="createdAt")

from app.models.contract_aliases import AliasContract

class QuickStartSessionRequest(AliasContract, BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    execution_mode: ExecutionMode = Field(ExecutionMode.SOURCE_ONLY, alias="executionMode")
    auto_deploy: bool = Field(False, alias="autoDeploy")

    service_name: Optional[str] = Field(None, alias="serviceName")
    spec_name: Optional[str] = Field(None, alias="specName")
    raw_text: Optional[str] = Field(None, alias="rawText")
    prompt: Optional[str] = Field(None, alias="prompt")
    database_engine: DatabaseEngine = Field(DatabaseEngine.POSTGRESQL, alias="databaseEngine")
    auto_run: Optional[bool] = Field(False, alias="autoRun")
    api_key: Optional[str] = Field(None, alias="apiKey")
    llm_provider: Optional[str] = Field(None, alias="llmProvider")
    model_name: Optional[str] = Field(None, alias="modelName")
    # The "interfaz de entrada" (levantando_observaciones): volume, data needs,
    # integrations, architecture/build-tool preference. Drives the InferenceEngine.
    input_interface: Optional[dict] = Field(None, alias="inputInterface")

class QuickStartSessionResponse(BaseModel):
    execution_mode: ExecutionMode = Field(ExecutionMode.SOURCE_ONLY, alias="executionMode")
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(..., alias="sessionId")
    spec_id: Optional[str] = Field(None, alias="specId")
    spec_name: str = Field(..., alias="specName")
    status: SessionStatus
    current_lifecycle_phase: str = Field("REQUIREMENTS", alias="currentLifecyclePhase")
    lifecycle_mode: str = Field("GUIDED_STEP", alias="lifecycleMode")
    pipeline_started: bool = Field(False, alias="pipelineStarted")
    message: str

class GenerationSessionDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    spec_id: str = Field(..., alias="specId")
    spec_name: str = Field(..., alias="specName")
    status: SessionStatus
    execution_mode: ExecutionMode = Field(ExecutionMode.SOURCE_ONLY, alias="executionMode")
    verification_outcome: VerificationOutcome = Field(VerificationOutcome.NOT_RUN, alias="verificationOutcome")
    available_actions: list[str] = Field(default_factory=list, alias="availableActions")
    phase: SessionPhase
    queue_position: Optional[int] = Field(0, alias="queuePosition")
    repair_attempts: int = Field(0, alias="repairAttempts")
    created_at: datetime = Field(..., alias="createdAt")
    started_at: Optional[datetime] = Field(None, alias="startedAt")
    completed_at: Optional[datetime] = Field(None, alias="completedAt")
    error_message: Optional[str] = Field(None, alias="errorMessage")
    # Feature 012 (FR-005): whether verification actually ran. Defaults to False
    # so a session with no persisted metrics -- or an older row -- degrades to
    # "no known fallback" rather than raising.
    verification_fallback_used: bool = Field(False, alias="verificationFallbackUsed")


# Register additive tables without modifying a database at import time.
from app.models import reliability as _reliability_models  # noqa: E402,F401
