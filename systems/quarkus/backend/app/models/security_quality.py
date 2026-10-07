from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class QualityGateStatus(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    BLOCKED = "BLOCKED"


class SeverityLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class VulnerabilityCategory(str, Enum):
    SAST_INJECTION = "SAST_INJECTION"
    SAST_DESERIALIZATION = "SAST_DESERIALIZATION"
    SAST_ACCESS_CONTROL = "SAST_ACCESS_CONTROL"
    SAST_DATA_EXPOSURE = "SAST_DATA_EXPOSURE"
    SECRET_LEAK = "SECRET_LEAK"
    CVE_DEPENDENCY = "CVE_DEPENDENCY"


class ConstitutionPrinciple(str, Enum):
    PRINCIPLE_I_LAYER_ISOLATION = "PRINCIPLE_I_LAYER_ISOLATION"
    PRINCIPLE_II_IMMUTABLE_DTOS = "PRINCIPLE_II_IMMUTABLE_DTOS"
    PRINCIPLE_III_CENTRALIZED_ERRORS = "PRINCIPLE_III_CENTRALIZED_ERRORS"
    PRINCIPLE_IV_OFFLINE_DETERMINISM = "PRINCIPLE_IV_OFFLINE_DETERMINISM"
    PRINCIPLE_V_QUALITY_GATES = "PRINCIPLE_V_QUALITY_GATES"
    PRINCIPLE_VI_ZERO_SECRETS = "PRINCIPLE_VI_ZERO_SECRETS"
    STACK_LOMBOK_RESTRICTION = "STACK_LOMBOK_RESTRICTION"


class SecurityVulnerabilityFinding(BaseModel):
    id: str = Field(..., description="Unique finding ID e.g. SEC-VULN-001")
    title: str = Field(..., description="Short finding title")
    category: VulnerabilityCategory
    severity: SeverityLevel
    cweId: str = Field(..., description="Common Weakness Enumeration ID e.g. CWE-89")
    owaspCategory: str = Field(..., description="OWASP Top 10 category e.g. A03:2021-Injection")
    filePath: str = Field(..., description="Relative or workspace file path")
    lineNumber: int = Field(default=1, description="Line number of detected issue")
    codeSnippet: str = Field(..., description="Relevant code excerpt")
    description: str = Field(..., description="Detailed description of vulnerability")
    remediationGuidance: str = Field(..., description="Actionable guidance to remediate")
    autoFixAvailable: bool = Field(default=False, description="True if 1-click surgical patch is supported")


class StandardsComplianceViolation(BaseModel):
    id: str = Field(..., description="Unique violation ID e.g. CONST-VIOL-001")
    principle: ConstitutionPrinciple
    severity: SeverityLevel
    filePath: str = Field(..., description="File where violation was detected")
    offendingElement: str = Field(..., description="Class, method, or declaration causing violation")
    ruleDescription: str = Field(..., description="Explanation of violated rule")
    suggestedFix: str = Field(..., description="Suggested code replacement or structure")
    autoFixAvailable: bool = Field(default=False, description="True if 1-click surgical patch is supported")


class CodeQualityMetrics(BaseModel):
    averageCyclomaticComplexity: float = Field(default=1.0, description="Average cyclomatic complexity per method")
    maxCyclomaticComplexity: int = Field(default=1, description="Maximum cyclomatic complexity observed in any method")
    totalMethodsAudited: int = Field(default=0, description="Total methods evaluated")
    methodsExceedingThreshold: int = Field(default=0, description="Methods with cyclomatic complexity > 10")
    totalLinesOfCode: int = Field(default=0, description="Total executable lines of code")
    duplicationPercentage: float = Field(default=0.0, description="Estimated code duplication percentage")
    testAssertionDensity: float = Field(default=0.0, description="Average assertions per test method")
    totalCodeSmells: int = Field(default=0, description="Total non-critical code smells detected")


class QualityGateVerdict(BaseModel):
    status: QualityGateStatus
    score: int = Field(..., ge=0, le=100, description="Composite quality score from 0 to 100")
    criticalCount: int = Field(default=0)
    highCount: int = Field(default=0)
    mediumCount: int = Field(default=0)
    lowCount: int = Field(default=0)
    canExport: bool = Field(default=True, description="False if BLOCKED by CRITICAL or HIGH findings")
    summaryMessage: str = Field(..., description="High-level evaluation verdict summary")


class SecurityQualityAuditReport(BaseModel):
    sessionId: str
    serviceName: str
    qualityGate: QualityGateVerdict
    metrics: CodeQualityMetrics
    vulnerabilities: List[SecurityVulnerabilityFinding] = Field(default_factory=list)
    violations: List[StandardsComplianceViolation] = Field(default_factory=list)
    auditedAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AuditRequest(BaseModel):
    files: Dict[str, str] = Field(..., description="Map of relative file path to file content")
    pomXml: Optional[str] = Field(None, description="Optional pom.xml content for dependency scanning")
    serviceName: Optional[str] = Field(default="microservice", description="Target service name")


class RemediationRequest(BaseModel):
    findingId: str = Field(..., description="ID of finding or violation to remediate")
    filePath: str = Field(..., description="File path to patch")
    sourceCode: Optional[str] = Field(None, description="Optional source code override; if omitted, read from workspace")


class RemediationResponse(BaseModel):
    findingId: str
    filePath: str
    originalCode: str
    remediatedCode: str
    diff: str
    applied: bool = True

