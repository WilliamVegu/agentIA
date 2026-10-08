from datetime import datetime, timezone
from enum import Enum
from typing import List, Any, Dict, Optional
from pydantic import BaseModel, Field


class DeploymentStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
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
    hostPort: Optional[int] = None
    containerPort: int = 8080
    testUrl: Optional[str] = None
    healthStatus: Optional[str] = None
    errorMessage: Optional[str] = None
    startedAt: Optional[str] = None


class DevOpsDeployRequest(BaseModel):
    hostPort: Optional[int] = Field(None, ge=1024, le=65535)
    rebuild: Optional[bool] = False



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
