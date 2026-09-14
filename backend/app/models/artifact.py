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
    totalTests: int = Field(default=0, ge=0)
    passedTests: int = Field(default=0, ge=0)
    failedTests: int = Field(default=0, ge=0)
    executionDurationMs: int = Field(default=0, ge=0)
    allPassed: bool = Field(default=False)
    surefireReport: Optional[dict] = None

