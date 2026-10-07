# Contract Specification: Server-Sent Events (SSE) Stream

**Endpoint**: `GET /api/v1/sessions/{id}/stream`
**Content-Type**: `text/event-stream`
**Transport**: HTTP/1.1 or HTTP/2
**Encoding**: UTF-8

## Overview

The `/stream` endpoint transmits real-time events regarding the code synthesis, Docker sandbox compilation, unit test execution, and auto-repair iterations of a `GenerationSession`.

Clients connect using the standard HTML5 `EventSource` API or any SSE client.

---

## Connection Lifecycle & Headers

### Request Headers
```http
GET /api/v1/sessions/f81d4fae-7dec-11d0-a765-00a0c91e6bf6/stream HTTP/1.1
Host: localhost:8080
Accept: text/event-stream
Last-Event-ID: 42
Cache-Control: no-cache
```

- `Last-Event-ID` *(Optional)*: If the client was disconnected, supplying this header resumes streaming from the specified event sequence number, replaying missed events from the server's in-memory ring buffer.

### Response Headers
```http
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

---

## Event Catalog & Schemas

Every SSE message includes an `id`, an `event` type name, and a JSON string formatted in the `data:` field.

### 1. `queue_status`
Emitted immediately after connection if the session is waiting in the FIFO queue.

```http
id: 1
event: queue_status
data: {"sessionId":"f81d4fae-7dec-11d0-a765-00a0c91e6bf6","queuePosition":2,"activeWorkers":2,"maxWorkers":2,"message":"Waiting for worker slot..."}
```

### 2. `phase_transition`
Emitted whenever the generation pipeline transitions between major lifecycle phases.

```http
id: 5
event: phase_transition
data: {"sessionId":"f81d4fae-7dec-11d0-a765-00a0c91e6bf6","previousPhase":"SCAFFOLDING","currentPhase":"CODE_GENERATION","timestamp":"2026-09-13T16:20:01.120Z"}
```

**Phase Enum Values**:
- `INITIALIZATION`
- `SCAFFOLDING`
- `CODE_GENERATION`
- `SANDBOX_BUILD`
- `TEST_EXECUTION`
- `SELF_REPAIR`
- `VERIFIED`
- `FAILED`

### 3. `build_log`
Emitted for streaming real-time stdout and stderr output from the Docker sandbox container running `mvn test -o`.

```http
id: 28
event: build_log
data: {"sessionId":"f81d4fae-7dec-11d0-a765-00a0c91e6bf6","stream":"stdout","line":"[INFO] Running com.corp.order.service.OrderServiceTest","timestamp":"2026-09-13T16:20:15.340Z"}
```

### 4. `repair_diagnostic`
Emitted when a compilation or test assertion failure triggers the bounded self-repair state machine.

```http
id: 45
event: repair_diagnostic
data: {"sessionId":"f81d4fae-7dec-11d0-a765-00a0c91e6bf6","attempt":1,"maxAttempts":3,"failedComponent":"OrderServiceTest.java","failureReason":"AssertionFailedError: expected <ACTIVE> but was <PENDING>","remedyAction":"Patching OrderService.java status assignment logic"}
```

### 5. `session_completed`
Emitted when the project passes 100% of unit tests and satisfies all constitutional quality gates.

```http
id: 88
event: session_completed
data: {"sessionId":"f81d4fae-7dec-11d0-a765-00a0c91e6bf6","status":"COMPLETED","totalTests":14,"passedTests":14,"failedTests":0,"durationMs":4320,"artifactCount":18,"downloadUrl":"/api/v1/sessions/f81d4fae-7dec-11d0-a765-00a0c91e6bf6/export"}
```

### 6. `session_blocked`
Emitted when the 3rd self-repair iteration fails, halting execution and escalating to human review.

```http
id: 92
event: session_blocked
data: {"sessionId":"f81d4fae-7dec-11d0-a765-00a0c91e6bf6","status":"BLOCKED","label":"Bloqueo por intervención humana requerida","attemptsExhausted":3,"finalStackTrace":"[ERROR] COMPILATION ERROR: ...","message":"Autonomous self-repair could not resolve compilation after 3 attempts."}
```

### 7. Heartbeat / Keep-Alive
Every 15 seconds of silence, the server sends a comment line to maintain the HTTP connection across proxies and load balancers:
```http
: heartbeat
```

---

## Client Reconnection Protocol

1. The client maintains `eventSource.onmessage` and stores the received event `id`.
2. Upon connection drop, `EventSource` automatically attempts reconnection after 3 seconds, sending the header:
   `Last-Event-ID: <last_seen_id>`
3. The server checks its in-memory buffer (size: 500 events):
   - If `Last-Event-ID` is in the buffer, it replays missed events from that point onwards.
   - If `Last-Event-ID` has expired from the buffer, the server sends a fresh snapshot event with full session state.

