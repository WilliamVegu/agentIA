# Data Model: Unified End-to-End Workflow Orchestration

**Feature**: `008-unified-workflow-orchestration`  
**Date**: 2026-09-13  
**Status**: Completed  

---

## 1. Domain Entities & Enums

### 1.1 Enumerations

```mermaid
classDiagram
    class LifecyclePhase {
        <<enumeration>>
        INITIAL
        REQUIREMENTS
        STORIES
        ARCHITECTURE
        DATA_MODEL
        CODE_TESTS
        SECURITY_AUDIT
        DEVOPS_DEPLOY
        COMPLETED
    }

    class PhaseStatus {
        <<enumeration>>
        NOT_STARTED
        IN_PROGRESS
        COMPLETED
        OUTDATED
        BLOCKED
        SKIPPED
    }

    class PipelineExecutionMode {
        <<enumeration>>
        AUTO_PILOT
        GUIDED_STEP
    }

    class PipelineRunStatus {
        <<enumeration>>
        IDLE
        RUNNING
        PAUSED
        COMPLETED
        AWAITING_INTERVENTION
        FAILED
    }
```

### 1.2 Core Data Models

```mermaid
classDiagram
    class PhaseState {
        +LifecyclePhase phase
        +PhaseStatus status
        +String title
        +String description
        +DateTime completedAt
        +Dict artifactSummary
        +Boolean canEnter
        +String blockingReason
    }

    class LifecycleState {
        +String sessionId
        +LifecyclePhase currentPhase
        +Float completionPercentage
        +List~PhaseState~ phases
        +String nextRecommendedAction
        +LifecyclePhase nextTargetPhase
        +Boolean canAdvance
        +PipelineExecutionMode activeMode
        +Boolean isOutdated
    }

    class PipelineProgressEvent {
        +DateTime timestamp
        +String sessionId
        +LifecyclePhase phase
        +String step
        +Float percent
        +String message
        +PhaseStatus status
        +String error
    }

    class ProjectOverviewSummary {
        +String sessionId
        +String specName
        +LifecycleState lifecycle
        +String framework
        +String databaseEngine
        +Integer userStoriesCount
        +Integer entitiesCount
        +Boolean testsPassed
        +String securityAuditVerdict
        +String deploymentStatus
        +String deploymentUrl
    }

    LifecycleState "1" *-- "many" PhaseState
    ProjectOverviewSummary "1" *-- "1" LifecycleState
```

---

## 2. Pydantic Models Definition (`backend/app/models/orchestrator.py`)

```python
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


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


class PhaseState(BaseModel):
    phase: LifecyclePhase
    status: PhaseStatus = PhaseStatus.NOT_STARTED
    title: str
    description: str
    completedAt: Optional[datetime] = None
    artifactSummary: Dict[str, Any] = Field(default_factory=dict)
    canEnter: bool = False
    blockingReason: Optional[str] = None


class LifecycleState(BaseModel):
    sessionId: str
    currentPhase: LifecyclePhase = LifecyclePhase.INITIAL
    completionPercentage: float = 0.0
    phases: List[PhaseState] = Field(default_factory=list)
    nextRecommendedAction: str = "Ingresar o confirmar requisitos del microservicio"
    nextTargetPhase: Optional[LifecyclePhase] = LifecyclePhase.REQUIREMENTS
    canAdvance: bool = True
    activeMode: PipelineExecutionMode = PipelineExecutionMode.GUIDED_STEP
    isOutdated: bool = False


class PipelineRunRequest(BaseModel):
    sessionId: str
    targetPhase: Optional[LifecyclePhase] = LifecyclePhase.DEVOPS_DEPLOY
    stopOnGate: bool = True
    autoDeploy: bool = False


class PipelineProgressEvent(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sessionId: str
    phase: LifecyclePhase
    step: str
    percent: float
    message: str
    status: PhaseStatus = PhaseStatus.IN_PROGRESS
    error: Optional[str] = None


class PhaseTransitionRequest(BaseModel):
    targetPhase: LifecyclePhase
    force: bool = False


class ProjectOverviewSummary(BaseModel):
    sessionId: str
    specName: str
    lifecycle: LifecycleState
    framework: str = "Java 21 / Spring Boot 3"
    databaseEngine: str = "POSTGRESQL"
    userStoriesCount: int = 0
    entitiesCount: int = 0
    testsPassed: bool = False
    securityAuditVerdict: str = "PENDING"
    deploymentStatus: str = "IDLE"
    deploymentUrl: Optional[str] = None
```

---

## 3. Sequence Diagrams

### 3.1 Autonomous Auto-Pilot Execution with Quality Gate Guard

```mermaid
sequenceDiagram
    autonumber
    actor Developer
    participant Studio as Web Studio (Streamlit)
    participant Orchestrator as Orchestrator API
    participant Runner as Pipeline Runner (Thread)
    participant SecService as Security Service (Spec 006)
    participant DevOps as DevOps Engine (Spec 007)

    Developer->>Studio: Clicks "🚀 Ejecutar Flujo Completo (Auto-Pilot)"
    Studio->>Orchestrator: POST /api/v1/orchestrator/pipeline/run {sessionId}
    Orchestrator->>Runner: Spawns Background Pipeline Thread
    Orchestrator-->>Studio: 202 Accepted (Pipeline Started)
    
    Studio->>Orchestrator: GET /api/v1/orchestrator/pipeline/{id}/events (SSE)
    Runner-->>Studio: Event: STORIES In Progress (15%)
    Runner-->>Studio: Event: ARCHITECTURE In Progress (30%)
    Runner-->>Studio: Event: DATA_MODEL In Progress (45%)
    Runner-->>Studio: Event: CODE_TESTS In Progress (65%)
    
    Runner->>SecService: Execute Quality Gate Audit
    alt Quality Gate Fails (BLOCKED)
        SecService-->>Runner: QualityGateVerdict: BLOCKED
        Runner-->>Studio: Event: SECURITY_AUDIT BLOCKED (80%)
        Runner->>Runner: Pause pipeline (AWAITING_INTERVENTION)
        Studio->>Developer: Displays Warning Banner with direct link to Tab 6
    else Quality Gate Passes
        SecService-->>Runner: QualityGateVerdict: APPROVED
        Runner->>DevOps: Generate Manifests & Deploy Containers
        DevOps-->>Runner: Container Launched & Healthy
        Runner-->>Studio: Event: DEVOPS_DEPLOY COMPLETED (100%)
        Studio->>Developer: Renders Success Banner with Local Test URL
    end
```

### 3.2 Hot-Pausing & Mode Switching Sequence

```mermaid
sequenceDiagram
    autonumber
    actor Developer
    participant Studio as Web Studio
    participant Orchestrator as Orchestrator API
    participant Runner as Pipeline Runner (Thread)

    Note over Runner: Pipeline running Phase 4 (Code/Tests)...
    Developer->>Studio: Clicks "⏸️ Pausar Auto-Pilot"
    Studio->>Orchestrator: POST /api/v1/orchestrator/pipeline/{id}/pause
    Orchestrator->>Runner: Sets _pause_event signal
    Note over Runner: Completes active compilation step
    Runner->>Runner: State -> PAUSED, Mode -> GUIDED_STEP
    Runner-->>Studio: SSE Event: PAUSED at CODE_TESTS
    Studio->>Studio: Switches UI to Tab 5 (Code Explorer)
    Developer->>Studio: Inspects code, edits file, clicks "Siguiente Paso"
    Studio->>Orchestrator: POST /api/v1/orchestrator/sessions/{id}/transition {SECURITY_AUDIT}
    Orchestrator-->>Studio: Advances to Phase 6 in Guided Step-by-Step Mode
```

