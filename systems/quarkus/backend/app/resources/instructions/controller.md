# API layer instruction

## Technology contract

You produce the HTTP surface and centralized error handling of a Quarkus microservice
using Quarkus REST (RESTEasy Reactive / Jakarta REST). Automated compliance validation
runs before anything you write is persisted.

- **Language level**: Java 21 LTS.
- **Framework**: Quarkus 3.x, Quarkus REST (`jakarta.ws.rs.*`).
- **Namespace**: `jakarta.*` exclusively for validation and REST APIs. `javax.*` is a
  validation failure.
- **Layering (Constitution I)**: controllers/resources depend on the **service layer only**.
  A resource is limited to receiving HTTP, delegating to the service, and returning responses.
  It must not reach into repositories or persistence entities.
- **Centralized errors (Constitution III)**: exactly one global handler with Quarkus
  `@ServerExceptionMapper` or `ExceptionMapper` must exist, and every error response must be
  produced there. A resource that catches exceptions to build error bodies is a validation failure.
- **Uniform error shape (Constitution III)**: every error response must share one structure
  carrying at minimum a timestamp, the HTTP status code, a descriptive message, and — for
  validation failures — the per-field details.
- **Contracts (Constitution II)**: resources accept and return the immutable record
  contracts produced by the domain stage. A persistence entity must never appear in a
  resource signature, request body, or response body.
- **Validation**: request bodies are validated declaratively with `@Valid`, so invalid
  payloads are rejected before reaching the service layer.

## Rules

1. Read the blueprint payload and existing artifacts. Use the service interfaces and record
   contracts produced by earlier stages; do not redeclare them.
2. Declare, per entity, one REST resource class annotated with `@Path` bound to a collection
   path under `/api/v1` (e.g. `@Path("/api/v1/orders")`), producing and consuming JSON.
3. Expose the operations the blueprint scenarios require: creation (`@POST`), read-one
   (`@GET @Path("/{id}")`), read-all (`@GET`), and delete (`@DELETE @Path("/{id}")`).
4. Accept the request contract with `@Valid`, ensuring validation constraints are enforced.
5. Return standard HTTP statuses: `201 Created` for creation, `200 OK` for reads,
   `204 No Content` for deletions. Missing resources bubble to the global exception mapper.
6. Inject the service dependency via constructor injection or `@Inject`.
7. Delegate each operation to the service in a single call. A resource class must contain no
   domain branching and no data transformation.
8. Emit exactly one global exception mapper (`GlobalExceptionHandler`) handling: resource
   not found exception, validation violations (`ConstraintViolationException`), and generic
   unhandled exceptions.
9. Emit an operational health/catalogue resource reporting service identity, status, and
   exposed routes.
10. Ensure the exception mapper is in the base package and picked up by Quarkus CDI.
11. STRICT 100% QUARKUS REST ONLY: Do NOT use Spring Boot annotations or packages (`@RestController`,
    `@RequestMapping`, `@GetMapping`, `@PostMapping`, `@Autowired`, `@RestControllerAdvice`,
    `org.springframework.*`). Use ONLY Quarkus REST (`@Path`, `@GET`, `@POST`, `@DELETE`,
    `@Produces`, `@Consumes`, `@Valid`, `@ServerExceptionMapper` or `ExceptionMapper`). Mixing Spring
    annotations is strictly prohibited.

## Output contract

Produce exactly these artifacts, at exactly these workspace-relative paths. Emit one REST
resource for every domain entity, plus the global exception handler and service catalogue.

| Path | Artifact |
| --- | --- |
| `src/main/java/<package-path>/controller/<EntityName>Resource.java` | Quarkus REST resource exposing endpoints for the entity. |
| `src/main/java/<package-path>/controller/GlobalExceptionHandler.java` | Global exception mapper producing uniform error responses. Emitted once. |
| `src/main/java/<package-path>/controller/ServiceCatalogResource.java` | Operational catalogue reporting service identity and status. Emitted once. |

`<package-path>` is the base package with segments separated by `/`. `<EntityName>` is the
entity name in PascalCase.

## Prohibitions

- **Do not use `javax.*` anywhere.** Use `jakarta.ws.rs.*` and `jakarta.validation.*`.
- **Do not handle domain logic or transformations in the resource.**
- **Do not catch exceptions inside resource methods** to construct manual error bodies.
- **Do not import or use persistence entities or repositories** directly in resources.
- **Do not return entities from endpoints.** Return only record contracts or `Response`.
