# Data Model: Automated Test Generation, Code Analysis & Iterative Self-Repair

**Feature**: `005-automated-tests-analysis`  
**Date**: 2026-09-13  
**Status**: Completed  

---

## 1. Entity Definitions & Schemas

### 1.1 Enums

```python
class TestType(str, Enum):
    UNIT = "UNIT"                         # Service unit test with Mockito
    INTEGRATION_WEB = "INTEGRATION_WEB"   # Controller @WebMvcTest
    INTEGRATION_DB = "INTEGRATION_DB"     # Full @SpringBootTest with H2 PostgreSQL mode

class DiagnosticCategory(str, Enum):
    COMPILATION_ERROR = "COMPILATION_ERROR"
    ASSERTION_FAILURE = "ASSERTION_FAILURE"
    CONSTITUTIONAL_VIOLATION = "CONSTITUTIONAL_VIOLATION"
    RUNTIME_EXCEPTION = "RUNTIME_EXCEPTION"

class DiagnosticSeverity(str, Enum):
    BLOCKING = "BLOCKING"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class PatchType(str, Enum):
    METHOD_REPLACE = "METHOD_REPLACE"
    IMPORT_ADD = "IMPORT_ADD"
    STATEMENT_REPLACE = "STATEMENT_REPLACE"
    WHOLE_FILE = "WHOLE_FILE"

class RepairOutcome(str, Enum):
    SUCCESS = "SUCCESS"                   # 100% tests pass
    FAILED_CONTINUE = "FAILED_CONTINUE"   # Tests failed, attempts < 3
    FAILED_BLOCKED = "FAILED_BLOCKED"     # Tests failed, attempts == 3
```

---

### 1.2 Core Data Models

```python
class TestCaseDefinition(BaseModel):
    name: str = Field(..., description="Method name e.g. shouldCreateOrderSuccessfully")
    scenarioId: Optional[str] = Field(None, description="Mapped Given/When/Then scenario e.g. AC-1.1")
    testType: TestType
    targetMethod: str = Field(..., description="Method under test")
    description: str
    code: str = Field(..., description="Complete test method code including annotations")

class TestSuiteDefinition(BaseModel):
    className: str = Field(..., description="e.g. OrderServiceTest, OrderControllerTest")
    targetClassName: str = Field(..., description="e.g. OrderService, OrderController")
    packageName: str = Field(..., description="Package name e.g. com.example.orderservice.service")
    testType: TestType
    filePath: str = Field(..., description="Relative path e.g. src/test/java/com/example/.../OrderServiceTest.java")
    imports: List[str] = Field(default_factory=list)
    testCases: List[TestCaseDefinition] = Field(default_factory=list)
    fullSourceCode: str = Field(..., description="Runnable Java test class code")

class FailureDiagnostic(BaseModel):
    id: str = Field(..., description="Unique diagnostic ID e.g. DIAG-001")
    category: DiagnosticCategory
    severity: DiagnosticSeverity
    filePath: str = Field(..., description="Path to file causing failure")
    className: Optional[str] = None
    methodName: Optional[str] = None
    lineNumber: Optional[int] = None
    columnNumber: Optional[int] = None
    errorSummary: str = Field(..., description="High-level error summary")
    expectedValue: Optional[str] = None
    actualValue: Optional[str] = None
    rawStackTrace: str = Field(default="")
    suggestedFix: Optional[str] = None

class CodeRepairPatch(BaseModel):
    id: str = Field(..., description="Unique patch ID e.g. PATCH-001")
    filePath: str = Field(..., description="Target file path to modify")
    patchType: PatchType = Field(default=PatchType.METHOD_REPLACE)
    targetMethod: Optional[str] = None
    originalSnippet: str = Field(..., description="Exact code snippet to replace")
    replacementSnippet: str = Field(..., description="New replacement code snippet")
    explanation: str = Field(..., description="Rationale for the change")

class RepairIterationRecord(BaseModel):
    iterationNumber: int = Field(..., ge=1, le=3)
    diagnostics: List[FailureDiagnostic]
    patchesApplied: List[CodeRepairPatch]
    passedTestsBefore: int
    failedTestsBefore: int
    passedTestsAfter: int
    failedTestsAfter: int
    diffSummary: str = Field(..., description="Unified diff of all modifications in this iteration")
    durationSeconds: float
    outcome: RepairOutcome

class RepairHistoryResponse(BaseModel):
    sessionId: str
    totalIterations: int
    finalState: str
    iterations: List[RepairIterationRecord]
    canRetryManually: bool = False
    currentBlockedDiagnostic: Optional[FailureDiagnostic] = None
```

---

## 2. State Machine & Execution Flow

```mermaid
stateDiagram-v2
    [*] --> INITIALIZATION
    INITIALIZATION --> SCAFFOLDING: Blueprint Validated
    SCAFFOLDING --> CODE_GENERATION: Base Structure Ready
    CODE_GENERATION --> TEST_SYNTHESIS: App Classes Generated
    TEST_SYNTHESIS --> SANDBOX_BUILD: Test Suites Generated
    
    state SANDBOX_BUILD {
        [*] --> CompilingSource
        CompilingSource --> CompilingTests: Source OK
        CompilingTests --> RunningTests: Tests Compiled
        RunningTests --> [*]
    }
    
    SANDBOX_BUILD --> VERIFIED: 100% Tests Pass
    SANDBOX_BUILD --> FAILURE_DIAGNOSIS: Compilation or Assertion Error
    
    state SELF_REPAIR_LOOP {
        FAILURE_DIAGNOSIS --> STATIC_COMPLIANCE_CHECK: Extract Diagnostics
        STATIC_COMPLIANCE_CHECK --> PLAN_SURGICAL_PATCH: Constitution OK
        PLAN_SURGICAL_PATCH --> APPLY_PATCHES: Targeted Code Snippet
        APPLY_PATCHES --> RE_EXECUTE_SANDBOX: Patch Injected
        RE_EXECUTE_SANDBOX --> CheckOutcome: Test Results Parsed
        
        state CheckOutcome <<choice>>
        CheckOutcome --> Pass: All Tests Pass
        CheckOutcome --> Retry: Errors Remain & Iteration < 3
        CheckOutcome --> Exhausted: Errors Remain & Iteration == 3
    }
    
    Pass --> VERIFIED: Session Complete
    Retry --> FAILURE_DIAGNOSIS: Increment Iteration
    Exhausted --> BLOCKED: Human Intervention Required
    
    BLOCKED --> PLAN_SURGICAL_PATCH: Developer Submits Code Edit / AI Hint
    VERIFIED --> [*]
```

---

## 3. Sequence Diagram: Self-Repair Cycle

```mermaid
sequenceDiagram
    autonumber
    actor User as Developer / Web Studio
    participant Orchestrator as LangGraph Orchestrator
    participant Sandbox as Docker Runner (--network none)
    participant Analyzer as Code & Failure Analyzer
    participant RepairAgent as Surgical Repair Agent (LLM)
    participant Store as Session & Artifact Store

    Orchestrator->>Sandbox: Execute mvn test -o in container
    Sandbox-->>Orchestrator: Exit Code 1 + Maven Build Logs
    
    Orchestrator->>Analyzer: parse_and_diagnose(build_logs, source_files)
    Analyzer->>Analyzer: Check dynamic failures & Constitution rules
    Analyzer-->>Orchestrator: List[FailureDiagnostic] (Category, File, Line)
    
    alt Iteration <= 3
        Orchestrator->>RepairAgent: plan_surgical_repair(diagnostics, source_files)
        RepairAgent-->>Orchestrator: List[CodeRepairPatch] (method/block replace)
        Orchestrator->>Store: Apply patches & record unified diff
        Orchestrator->>Sandbox: Re-execute mvn test -o
        Sandbox-->>Orchestrator: Exit Code 0 (Success)
        Orchestrator->>Store: Update status to VERIFIED
        Orchestrator-->>User: Emit SSE: VERIFIED (100% tests passed)
    else Iteration > 3
        Orchestrator->>Store: Update status to BLOCKED
        Orchestrator-->>User: Emit SSE: BLOCKED (Max iterations exhausted)
        User->>Orchestrator: POST /api/v1/sessions/{id}/manual-repair (File edit + hint)
        Orchestrator->>Sandbox: Re-execute mvn test -o with manual fix
    end
```

