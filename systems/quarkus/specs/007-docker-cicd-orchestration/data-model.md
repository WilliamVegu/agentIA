# Data Model: Docker Containerization, CI/CD Pipelines & Deployment Orchestration

**Feature**: `007-docker-cicd-orchestration`  
**Date**: 2026-09-13  
**Status**: Completed  

---

## 1. Domain Entities & Schemas

```mermaid
classDiagram
    class DevOpsManifestBundle {
        +string sessionId
        +string serviceName
        +DatabaseEngine databaseEngine
        +string dockerfileContent
        +string dockerignoreContent
        +string dockerComposeContent
        +string githubActionsWorkflow
        +string gitlabCiWorkflow
        +Map~string,string~ kubernetesManifests
        +datetime generatedAt
    }

    class LocalDeploymentSession {
        +string sessionId
        +string containerId
        +string databaseContainerId
        +DeploymentStatus status
        +int hostPort
        +int containerPort
        +string testUrl
        +string healthStatus
        +string errorMessage
        +datetime startedAt
    }

    class SmokeTestResult {
        +bool passed
        +int statusCode
        +Map~string,any~ statusPayload
        +float latencyMs
        +string testUrl
        +datetime checkedAt
        +string details
    }

    class DeploymentStatus {
        <<enumeration>>
        IDLE
        BUILDING
        RUNNING
        HEALTHY
        FAILED
        STOPPED
        DOCKER_UNAVAILABLE
    }

    class DatabaseEngine {
        <<enumeration>>
        POSTGRESQL
        MYSQL
        H2
    }

    DevOpsManifestBundle --> DatabaseEngine
    LocalDeploymentSession --> DeploymentStatus
    LocalDeploymentSession o-- SmokeTestResult
```

---

## 2. JSON Schema Definitions

### 2.1 `DevOpsManifestBundle`
Represents the complete generated suite of containerization, orchestration, pipeline, and production deployment assets for a microservice.

```json
{
  "sessionId": "session-12345",
  "serviceName": "order-service",
  "databaseEngine": "POSTGRESQL",
  "dockerfileContent": "FROM eclipse-temurin:21-jre-alpine AS builder ...",
  "dockerignoreContent": ".git\ntarget/\n*.log\n",
  "dockerComposeContent": "version: '3.8'\nservices:\n  order-service:\n    build: .\n    ports:\n      - \"8080:8080\"\n...",
  "githubActionsWorkflow": "name: CI/CD Pipeline\non: [push, pull_request] ...",
  "gitlabCiWorkflow": "stages:\n  - build\n  - test\n  - security\n  - package ...",
  "kubernetesManifests": {
    "deployment.yaml": "apiVersion: apps/v1\nkind: Deployment ...",
    "service.yaml": "apiVersion: v1\nkind: Service ...",
    "configmap.yaml": "apiVersion: v1\nkind: ConfigMap ...",
    "ingress.yaml": "apiVersion: networking.k8s.io/v1\nkind: Ingress\nspec:\n  ingressClassName: nginx ..."
  },
  "generatedAt": "2026-09-13T21:00:00Z"
}
```

### 2.2 `LocalDeploymentSession`
Tracks the execution lifecycle of local Docker containers launched from the Web Studio.

```json
{
  "sessionId": "session-12345",
  "containerId": "a1b2c3d4e5f6",
  "databaseContainerId": "f6e5d4c3b2a1",
  "status": "HEALTHY",
  "hostPort": 8080,
  "containerPort": 8080,
  "testUrl": "http://localhost:8080/actuator/health",
  "healthStatus": "UP",
  "errorMessage": null,
  "startedAt": "2026-09-13T21:02:15Z"
}
```

### 2.3 `SmokeTestResult`
Captures the output of automated post-deployment health verification.

```json
{
  "passed": true,
  "statusCode": 200,
  "statusPayload": {
    "status": "UP",
    "components": {
      "db": {"status": "UP"},
      "diskSpace": {"status": "UP"}
    }
  },
  "latencyMs": 42.5,
  "testUrl": "http://localhost:8080/actuator/health",
  "checkedAt": "2026-09-13T21:02:45Z",
  "details": "Application is UP and responding normally."
}
```

---

## 3. Interaction & Deployment Lifecycle Flow

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer / Web Studio
    participant API as FastAPI DevOps Service
    participant Engine as Local Docker Engine Service
    participant Daemon as Docker Daemon (Socket/Pipe)
    participant App as Spring Boot Container

    Dev->>API: POST /api/v1/devops/{session_id}/generate
    activate API
    API->>API: Generate Dockerfile, compose, CI/CD & K8s
    API-->>Dev: DevOpsManifestBundle
    deactivate API

    Dev->>API: POST /api/v1/devops/{session_id}/deploy
    activate API
    API->>Engine: Initiate background build & run
    Engine->>Daemon: Ping socket
    alt Docker Daemon Unavailable (Option A)
        Daemon-->>Engine: Connection Refused
        Engine-->>API: DOCKER_UNAVAILABLE
        API-->>Dev: Status DOCKER_UNAVAILABLE (Export-Only Mode)
    else Docker Daemon Available
        Daemon-->>Engine: Connection Established
        Engine->>Daemon: docker build -t service:latest
        Daemon-->>Engine: Stream build output
        Engine-->>Dev: SSE Logs (/api/v1/devops/{id}/logs/stream)
        Engine->>Daemon: docker compose up -d (db + app)
        Daemon->>App: Launch container with non-root user
        loop Smoke Test Polling (every 2s, up to 60s)
            Engine->>App: GET http://localhost:8080/actuator/health
            App-->>Engine: 200 OK {"status": "UP"}
        end
        Engine-->>API: SmokeTestResult (PASS)
        API-->>Dev: Status HEALTHY with clickable local URL
    end
    deactivate API
```

