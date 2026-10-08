from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field


class DeploymentStatus(str, Enum):
    SKIPPED_BY_CHOICE = "SKIPPED_BY_CHOICE"
    DEGRADED = "DEGRADED"
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
    dbEngine: Optional[DatabaseEngine] = None
    containerId: Optional[str] = None
    databaseContainerId: Optional[str] = None
    sourceSnapshotId: Optional[str] = None
    workspaceFingerprint: Optional[str] = None
    imageId: Optional[str] = None
    executableJarSha256: Optional[str] = None
    status: DeploymentStatus = DeploymentStatus.IDLE
    hostPort: int = 8080
    containerPort: int = 8080
    testUrl: Optional[str] = None
    healthStatus: Optional[str] = None
    errorMessage: Optional[str] = None
    startedAt: Optional[str] = None
    operationId: Optional[str] = None
    operationKind: Optional[str] = None
    operationPhase: Optional[str] = None
    finishedAt: Optional[str] = None
    cancelRequested: bool = False
    message: Optional[str] = None


class DevOpsDeployRequest(BaseModel):
    hostPort: Optional[int] = Field(None, ge=1024, le=65535)
    rebuild: Optional[bool] = False


class LocalProjectConfiguration(BaseModel):
    databaseEngine: DatabaseEngine
    hostPort: int = Field(ge=1024, le=65535)
    buildTool: Literal['maven', 'gradle']
    buildDirectory: Literal['.', 'bootstrap']


class DeploymentLogSnapshot(BaseModel):
    logs: List[str]
    events: List[Dict[str, Any]]
    lastEventId: int = Field(ge=0)


class LocalCleanupRequest(BaseModel):
    deleteData: bool = False
    confirmationToken: Optional[str] = None


class LocalCancelRequest(BaseModel):
    operationId: str = Field(min_length=1, max_length=100)


class DockerDiagnosticCheck(BaseModel):
    name: str
    status: str
    detail: str
    freeBytes: Optional[int] = None
    image: Optional[str] = None
    imageId: Optional[str] = None
    repoDigests: List[str] = Field(default_factory=list)


class DockerCapabilityReport(BaseModel):
    sessionId: str
    executionMode: str
    readyForPreparation: bool = False
    preparedImagesAvailable: bool = False
    offlineVerified: bool = False
    checks: List[DockerDiagnosticCheck] = Field(default_factory=list)
    availableActions: List[str] = Field(default_factory=list)



class PlaygroundProxyRequest(BaseModel):
    """One call the browser wants the platform to forward to the deployed container.

    The caller names a path, not a destination: the host and port are resolved from
    the session's deployment record server-side. See `services/playground_proxy`.
    """

    method: str = Field(default="GET", description="HTTP method; validated against an allow-list")
    path: str = Field(..., description="Absolute path on the deployed service, e.g. /api/v1/customers")
    body: Optional[Any] = Field(default=None, description="JSON body for POST/PUT/PATCH")


class PlaygroundProxyResponse(BaseModel):
    """What actually happened. `statusCode is None` with a populated `error` means the
    call did not complete -- never a synthesised success."""

    statusCode: Optional[int] = None
    url: str = ""
    latencyMs: Optional[int] = None
    contentType: str = ""
    truncated: bool = False
    body: Optional[Any] = None
    bodyText: Optional[str] = None
    error: Optional[str] = None


class PlaygroundResources(BaseModel):
    """The REST paths the generated service exposes, read from its controllers."""

    sessionId: str
    resources: List[str] = Field(default_factory=list)
    defaultResource: Optional[str] = None
