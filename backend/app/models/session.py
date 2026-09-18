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
    current_lifecycle_phase = Column(String(50), nullable=True, default="INITIAL")
    lifecycle_mode = Column(String(50), nullable=True, default="GUIDED_STEP")
    phase_progress_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

Base.metadata.create_all(bind=engine)

from sqlalchemy import text
def _ensure_sqlite_lifecycle_columns():
    try:
        with engine.connect() as conn:
            res = conn.execute(text("PRAGMA table_info(generation_sessions)")).fetchall()
            existing_cols = [r[1] for r in res]
            if existing_cols:
                if "current_lifecycle_phase" not in existing_cols:
                    conn.execute(text("ALTER TABLE generation_sessions ADD COLUMN current_lifecycle_phase VARCHAR(50) DEFAULT 'INITIAL'"))
                if "lifecycle_mode" not in existing_cols:
                    conn.execute(text("ALTER TABLE generation_sessions ADD COLUMN lifecycle_mode VARCHAR(50) DEFAULT 'GUIDED_STEP'"))
                if "phase_progress_json" not in existing_cols:
                    conn.execute(text("ALTER TABLE generation_sessions ADD COLUMN phase_progress_json TEXT"))
                conn.commit()
    except Exception:
        pass

_ensure_sqlite_lifecycle_columns()

from pydantic import BaseModel, Field, ConfigDict

# Pydantic Response Schemas
class GenerationSessionSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(..., alias="sessionId")
    status: SessionStatus
    queue_position: Optional[int] = Field(0, alias="queuePosition")
    stream_url: str = Field(..., alias="streamUrl")

class GenerationSessionListItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(..., alias="sessionId")
    spec_id: Optional[str] = Field(None, alias="specId")
    spec_name: str = Field(..., alias="specName")
    status: SessionStatus
    current_lifecycle_phase: Optional[str] = Field("INITIAL", alias="currentLifecyclePhase")
    lifecycle_mode: Optional[str] = Field("GUIDED_STEP", alias="lifecycleMode")
    completion_percentage: float = Field(0.0, alias="completionPercentage")
    created_at: datetime = Field(..., alias="createdAt")

class QuickStartSessionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    service_name: Optional[str] = Field(None, alias="serviceName")
    spec_name: Optional[str] = Field(None, alias="specName")
    raw_text: Optional[str] = Field(None, alias="rawText")
    prompt: Optional[str] = Field(None, alias="prompt")
    database_engine: Optional[str] = Field("POSTGRESQL", alias="databaseEngine")
    auto_run: Optional[bool] = Field(False, alias="autoRun")
    api_key: Optional[str] = Field(None, alias="apiKey")
    llm_provider: Optional[str] = Field(None, alias="llmProvider")

class QuickStartSessionResponse(BaseModel):
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
    phase: SessionPhase
    queue_position: Optional[int] = Field(0, alias="queuePosition")
    repair_attempts: int = Field(0, alias="repairAttempts")
    created_at: datetime = Field(..., alias="createdAt")
    started_at: Optional[datetime] = Field(None, alias="startedAt")
    completed_at: Optional[datetime] = Field(None, alias="completedAt")
    error_message: Optional[str] = Field(None, alias="errorMessage")

