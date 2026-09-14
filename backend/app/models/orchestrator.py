from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class LifecyclePhase(str, Enum):
    INITIAL = "INITIAL"
    REQUIREMENTS = "REQUIREMENTS"
    STORIES = "STORIES"
    ARCHITECTURE = "ARCHITECTURE"
    DATA_MODEL = "DATA_MODEL"
    CODE_TESTS = "CODE_TESTS"
    SECURITY_AUDIT = "SECURITY_AUDIT"
    DEVOPS_DEPLOY = "DEVOPS_DEPLOY"
    COMPLETED = "COMPLETED"


class PhaseStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    OUTDATED = "OUTDATED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


class PipelineExecutionMode(str, Enum):
    AUTO_PILOT = "AUTO_PILOT"
    GUIDED_STEP = "GUIDED_STEP"


class PipelineRunStatus(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    AWAITING_INTERVENTION = "AWAITING_INTERVENTION"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PhaseState(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    phase: LifecyclePhase
    status: PhaseStatus = PhaseStatus.NOT_STARTED
    title: str
    description: str
    tab_index: int = Field(0, alias="tabIndex")
    completed_at: Optional[datetime] = Field(None, alias="completedAt")
    artifact_summary: Dict[str, Any] = Field(default_factory=dict, alias="artifactSummary")
    can_enter: bool = Field(False, alias="canEnter")
    blocking_reason: Optional[str] = Field(None, alias="blockingReason")


class LifecycleState(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(..., alias="sessionId")
    current_phase: LifecyclePhase = Field(LifecyclePhase.INITIAL, alias="currentPhase")
    completion_percentage: float = Field(0.0, alias="completionPercentage")
    phases: List[PhaseState] = Field(default_factory=list)
    next_recommended_action: str = Field(
        "Ingresar o confirmar requisitos del microservicio", alias="nextRecommendedAction"
    )
    next_target_phase: Optional[LifecyclePhase] = Field(
        LifecyclePhase.REQUIREMENTS, alias="nextTargetPhase"
    )
    can_advance: bool = Field(True, alias="canAdvance")
    active_mode: PipelineExecutionMode = Field(
        PipelineExecutionMode.GUIDED_STEP, alias="activeMode"
    )
    is_outdated: bool = Field(False, alias="isOutdated")
    pipeline_status: PipelineRunStatus = Field(
        PipelineRunStatus.IDLE, alias="pipelineStatus"
    )


class PipelineRunRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(..., alias="sessionId")
    target_phase: Optional[LifecyclePhase] = Field(
        LifecyclePhase.DEVOPS_DEPLOY, alias="targetPhase"
    )
    stop_on_gate: bool = Field(True, alias="stopOnGate")
    auto_deploy: bool = Field(False, alias="autoDeploy")
    force: bool = Field(False, alias="force")
    api_key: Optional[str] = Field(None, alias="apiKey")
    provider: Optional[str] = None
    model: Optional[str] = None


class PipelineProgressEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: str = Field(..., alias="sessionId")
    phase: LifecyclePhase
    step: str
    percent: float
    message: str
    status: PhaseStatus = PhaseStatus.IN_PROGRESS
    error: Optional[str] = None


class PhaseTransitionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    target_phase: LifecyclePhase = Field(..., alias="targetPhase")
    force: bool = False
    api_key: Optional[str] = Field(None, alias="apiKey")
    provider: Optional[str] = None


class ProjectOverviewSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(..., alias="sessionId")
    spec_name: str = Field(..., alias="specName")
    lifecycle: LifecycleState
    framework: str = "Java 21 / Spring Boot 3"
    database_engine: str = Field("POSTGRESQL", alias="databaseEngine")
    user_stories_count: int = Field(0, alias="userStoriesCount")
    entities_count: int = Field(0, alias="entitiesCount")
    tests_passed: bool = Field(False, alias="testsPassed")
    security_audit_verdict: str = Field("PENDING", alias="securityAuditVerdict")
    deployment_status: str = Field("IDLE", alias="deploymentStatus")
    deployment_url: Optional[str] = Field(None, alias="deploymentUrl")
    pipeline_status: PipelineRunStatus = Field(
        PipelineRunStatus.IDLE, alias="pipelineStatus"
    )

