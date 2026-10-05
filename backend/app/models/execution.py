"""A user's execution choice is independent of host capabilities and test evidence."""
from enum import Enum
from typing import Any, Dict, Literal
from pydantic import BaseModel


class ExecutionMode(str, Enum):
    SOURCE_ONLY = "SOURCE_ONLY"
    DOCKER = "DOCKER"


class VerificationOutcome(str, Enum):
    NOT_RUN = "NOT_RUN"
    SKIPPED_BY_CHOICE = "SKIPPED_BY_CHOICE"
    ENVIRONMENT_UNAVAILABLE = "ENVIRONMENT_UNAVAILABLE"
    INTERRUPTED = "INTERRUPTED"
    PASSED = "PASSED"
    FAILED = "FAILED"
    OUTDATED = "OUTDATED"


class ExecutionModeResponse(BaseModel):
    sessionId: str
    executionMode: ExecutionMode


class SessionVerificationResponse(BaseModel):
    sessionId: str
    metrics: Dict[str, Any]
    status: Literal['COMPLETED', 'PAUSED', 'BLOCKED']
