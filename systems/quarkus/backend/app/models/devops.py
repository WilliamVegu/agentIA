from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class DeploymentStatus(str, Enum):
    IDLE = "IDLE"
    BUILDING = "BUILDING"
    RUNNING = "RUNNING"
    HEALTHY = "HEALTHY"
    FAILED = "FAILED"
    STOPPED = "STOPPED"
    DOCKER_UNAVAILABLE = "DOCKER_UNAVAILABLE"


class DatabaseEngine(str, Enum):
    POSTGRESQL = "POSTGRESQL"
    MYSQL = "MYSQL"
    H2 = "H2"


class DevOpsManifestBundle(BaseModel):
    sessionId: str
    serviceName: str
    databaseEngine: DatabaseEngine = DatabaseEngine.POSTGRESQL
    dockerfileContent: str
    dockerignoreContent: str
    dockerComposeContent: str
    githubActionsWorkflow: str
    gitlabCiWorkflow: str
    kubernetesManifests: Dict[str, str] = Field(default_factory=dict)
    generatedAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SmokeTestResult(BaseModel):
    passed: bool
    statusCode: int = 200
    statusPayload: Dict[str, Any] = Field(default_factory=dict)
    latencyMs: float = 0.0
    testUrl: str
    checkedAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: str = ""


class LocalDeploymentSession(BaseModel):
    sessionId: str
    containerId: Optional[str] = None
    databaseContainerId: Optional[str] = None
    status: DeploymentStatus = DeploymentStatus.IDLE
    hostPort: int = 8080
    containerPort: int = 8080
    testUrl: Optional[str] = None
    healthStatus: Optional[str] = None
    errorMessage: Optional[str] = None
    startedAt: Optional[str] = None


class DevOpsDeployRequest(BaseModel):
    hostPort: Optional[int] = 8080
    rebuild: Optional[bool] = False

