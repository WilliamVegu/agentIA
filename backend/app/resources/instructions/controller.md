# API layer instruction

## Technology contract

You produce the HTTP surface and the centralized error handling of a Spring Boot
microservice. Automated compliance validation runs before anything you write is persisted.

- **Language level**: Java 21 LTS.
- **Framework**: Spring Boot 3.x, Spring Web.
- **Namespace**: `jakarta.*` exclusively for validation and servlet APIs. `javax.*` is a
  validation failure.
- **Layering (Constitution I)**: controllers depend on the **service layer only**. A
  controller is limited to receiving HTTP, orchestrating service calls, and serialising
  responses. It must not reach into repositories or persistence entities.
- **Centralized errors (Constitution III)**: exactly one global handler annotated with
  `@RestControllerAdvice` must exist, and every error response must be produced there. A
  controller that catches exceptions in order to build an error body is a validation
  failure.
- **The handler must log what it caught, with its stack trace.** A catch-all that returns a
  tidy error envelope and writes nothing to the log is a validation failure: it converts a
  diagnosable failure into an undocumented one. Use an SLF4J `Logger` obtained via
  `LoggerFactory.getLogger(GlobalExceptionHandler.class)` and call `logger.error(...)` with
  the exception as the last argument, so the stack trace is recorded. Declare the logger
  `private static final`.
- **Do not invent the message for an unexpected failure.** For the catch-all handler, pass
  the exception's own message through (or a fixed prefix concatenated with it) so the
  response, the log and the stack trace agree. A constant string such as
  `"An unexpected error occurred"` discards the only information that would identify the
  cause, and it is a validation failure.
- **Uniform error shape (Constitution III)**: every error response must share one structure
  carrying at minimum a timestamp, the HTTP status code, a descriptive message, and — for
  validation failures — the per-field details. Do not invent a different error body per
  handler.
- **Contracts (Constitution II)**: controllers accept and return the immutable record
  contracts produced by the domain stage. A persistence entity must never appear in a
  controller signature, request body, or response body.
- **Validation**: request bodies are validated declaratively at the boundary, so an invalid
  payload is rejected before it reaches the service layer.


### Requested architecture profile

The task payload's architecture_preference takes precedence over the default layered paths above.
For hexagonal / ports-and-adapters use domain/model for domain types, domain/port for interfaces,
application/dto for immutable contracts, application/service for use cases, infrastructure/persistence
for JPA entities, infrastructure/adapter/out for repository adapters, and infrastructure/adapter/in
for REST controllers and exception handling. Domain and application depend on ports, never on
Spring Data repositories or infrastructure. The SERVICE stage implements ports and outgoing adapters;
the DOMAIN stage owns domain types, ports, DTOs and persistence entities. Reuse all prior artifacts and
respect the selected identifier types. Tests must reference these actual package names.
For layered architecture retain the default output contract. Never substitute layered packages for a
requested hexagonal architecture. For Gradle use build.gradle/build.gradle.kts, never require pom.xml.


## Rules

1. Read the blueprint payload and the artifacts already produced by the earlier stages. Use
   the service interfaces and record contracts that already exist; do not redeclare them.
2. Declare, per entity, one REST controller bound to a collection path derived from the
   entity name, resolved under the application's versioned API root.
3. Expose, per controller, the operations the blueprint's acceptance scenarios require: a
   creation endpoint accepting the request contract, a read-one endpoint addressing a single
   resource by identifier, a read-all endpoint, and a delete endpoint. Derive the set from
   the scenarios rather than emitting a fixed catalogue.
4. Accept the request contract as a validated request body, so that declarative constraints
   are enforced before the service is entered.
5. Return the HTTP status that correctly expresses the outcome of each operation: creation
   returns the created-resource status, successful reads and deletions return the statuses
   appropriate to those operations, and a missing resource is expressed through the global
   handler rather than by the controller.
6. Obtain the service dependency through constructor injection. Do not use field injection
   and do not construct the service inside a method.
7. Delegate every operation to the service in a single call, and return the result. A
   controller must contain no branching on domain state and no data transformation.
8. Emit exactly one global exception handler covering, at minimum: the not-found exception
   raised by the service layer, request-payload validation failures, and any unhandled
   failure. Each case must produce the same uniform error structure.
9. Emit a root-path service catalogue endpoint that reports the service identity, an
   operational status, and the endpoints the service exposes, so an operator can confirm at
   a glance that the service is running and what it offers.
10. Ensure the global handler is discoverable from the application's base package, so that
    no controller needs to be individually registered with it.

## Output contract

Produce exactly these artifacts, at exactly these workspace-relative paths. Emit one
controller per declared domain entity, plus exactly one shared exception handler and exactly
one shared service catalogue endpoint.

| Path | Artifact |
| --- | --- |
| `src/main/java/<package-path>/controller/GlobalExceptionHandler.java` | Single `@RestControllerAdvice` producing the uniform error structure for every failure case. Emitted once. Must hold an SLF4J `Logger` and log every handled exception with its stack trace. |
| `src/main/java/<package-path>/controller/HomeController.java` | Root-path service catalogue endpoint reporting service identity, status, and exposed endpoints. Emitted once. |
| `src/main/java/<package-path>/controller/<Entity>Controller.java` | REST controller bound to the entity's collection path, delegating to the service interface. |

`<package-path>` is the base package name with `/` separators. `<Entity>` is the PascalCase
entity name from the blueprint. Package declarations must match the directory layout exactly.

## Prohibitions

- **Do not write `try`/`catch` in a controller for the purpose of formatting an error
  response**, and do not return an ad-hoc error body from a controller. Error handling
  belongs exclusively to the global advice. This is a blocking compliance rule
  (Constitution III).
- **Do not let a controller depend on a repository or on a persistence entity**, directly or
  transitively. This is a blocking compliance rule (Constitution I).
- **Do not return a persistence entity** in a response body, and do not accept one as a
  request body. Expose the record contracts only.
- **Do not define more than one global exception handler**, and do not scatter
  advice-annotated methods across controllers.
- **Do not leak internal detail to the client**: no stack traces, no exception class names,
  no SQL, and no persistence identifiers in error messages.
- **Do not import `javax.*`.**
- **Do not use `@Data`**, `@Value`, or `@SneakyThrows`.
- **Do not place business logic in a controller** — no computation on domain state, no
  validation beyond declarative annotations, no persistence calls.
- **Do not hardcode credentials**, tokens, or environment-specific hosts and ports.
- **Do not emit artifacts outside the Output contract**, and do not omit any listed artifact.
