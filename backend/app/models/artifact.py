from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class ArtifactFileType(str, Enum):
    JAVA_SOURCE = "JAVA_SOURCE"
    JAVA_RECORD = "JAVA_RECORD"
    POM_XML = "POM_XML"
    YAML_CONFIG = "YAML_CONFIG"
    TEST_SOURCE = "TEST_SOURCE"

class ArtifactSummary(BaseModel):
    id: str
    sessionId: str
    relativePath: str
    fileType: ArtifactFileType
    sizeBytes: int

class ArtifactContent(BaseModel):
    relativePath: str
    fileType: ArtifactFileType
    content: str
    sizeBytes: int

class VerificationMetrics(BaseModel):
    workspaceFingerprint: Optional[str] = None
    totalTests: int = Field(default=0, ge=0)
    passedTests: int = Field(default=0, ge=0)
    failedTests: int = Field(default=0, ge=0)
    executionDurationMs: int = Field(default=0, ge=0)
    allPassed: bool = Field(default=False)
    surefireReport: Optional[dict] = None

    # Feature 012 (FR-005, FR-007). Mirrors the verification result so consumers
    # can branch on the metrics payload alone. allPassed=True together with
    # fallback_used=True is legal ONLY under ALLOW_HERMETIC_FALLBACK, and means
    # "reported as passing without verification" (FR-008 requires such records be
    # excluded from every published figure).
    fallback_used: bool = Field(default=False)
    fallback_reason: Optional[str] = None

