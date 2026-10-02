# Domain model instruction

## Technology contract

You produce the persistence entities and the API contracts for a Spring Boot microservice.
Automated compliance validation runs before anything you write is persisted.

- **Language level**: Java 21 LTS.
- **Framework**: Spring Boot 3.x.
- **Namespace**: `jakarta.*` exclusively. Persistence annotations come from
  `jakarta.persistence`, validation annotations from `jakarta.validation.constraints`.
  `javax.*` is a validation failure.
- **Layer placement (Constitution I)**: persistence entities belong to the model layer and
  to nothing else. They must not be referenced by controllers and must not be returned from
  any API surface.
- **Immutable API contracts (Constitution II)**: every request and response contract must be
  a **native Java record**. A request or response declared as a class is a validation
  failure. Contracts must be structurally decoupled from the persistence entity — a contract
  is not the entity, and it must not carry persistence annotations.
- **Validation (Constitution II)**: request contracts carry declarative Jakarta Validation
  annotations. Constraints must be expressed on the contract, so that no unvalidated payload
  can reach the service layer.
- **Lombok (Stack rule)**: Project Lombok is restricted to `@Getter`, `@Setter`, `@Builder`,
  `@NoArgsConstructor`, and `@AllArgsConstructor`. **`@Data` is prohibited on JPA entities**
  — and on every other class — because it generates `equals`/`hashCode` over mutable state.
  `@Value` and `@SneakyThrows` are likewise prohibited. Prefer writing the accessors
  explicitly; omitting Lombok entirely is always acceptable.


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

1. Read the blueprint payload. It declares the domain entities, and for each one its
   attributes with a name, a type, and constraints (whether it is required and whether it is
   the identifier).
2. Produce exactly one persistence entity per declared domain entity. Do not invent
   entities that the blueprint does not declare, and do not merge two declared entities into
   one.
3. Guarantee that each entity declares exactly one identifier attribute. If the blueprint
   already marks one, use it. If it does not, add a generated surrogate identifier of an
   integral type rather than promoting an arbitrary business attribute.
4. Map each declared attribute to a Java type appropriate to its declared type, and map the
   identifier to its own type. Do not widen a declared type to a universal type such as
   `String` merely to avoid a mapping decision.
5. Apply declarative validation to every attribute that the blueprint marks as required or
   as carrying a format constraint. Choose the annotation that matches the declared
   constraint: a not-null style constraint for required non-text attributes, a not-blank
   style constraint for required text attributes, and a format-specific constraint where the
   blueprint declares one (for example an email-shaped constraint).
6. **Apply no validation constraint that the blueprint does not declare.** A constraint you
   invent is as much a defect as a missing one, because it changes the service's contract
   without authorisation.
7. Give the entity a no-argument constructor so the persistence provider can instantiate it,
   and implement identity equality over the identifier only. Do not implement equality over
   mutable business attributes.
8. Emit, per entity, one response contract that represents the full readable shape, and one
   request contract that represents the writable shape. The request contract excludes the
   identifier; the response contract includes it.
9. Give the response contract a static factory that builds it from a persistence entity, so
   that entity-to-contract translation has exactly one home. Return `null` for a `null`
   input rather than throwing.
10. Order your work entity first, then the response contract, then the request contract, so
    that each artifact refers only to artifacts that already exist.

## Output contract

Produce exactly these artifacts, at exactly these workspace-relative paths. Emit one entity
trio per declared domain entity.

| Path | Artifact |
| --- | --- |
| `src/main/java/<package-path>/model/entity/<Entity>.java` | JPA entity annotated for persistence, with a single identifier, typed attributes, and declared validation. |
| `src/main/java/<package-path>/model/dto/<Entity>Response.java` | Native record carrying the readable shape, with a static factory from the entity. |
| `src/main/java/<package-path>/model/dto/Create<Entity>Request.java` | Native record carrying the writable shape, with Jakarta Validation annotations matching the declared constraints. |

`<package-path>` is the base package name with `/` separators. `<Entity>` is the PascalCase
entity name from the blueprint. Package declarations must match the directory layout exactly.

## Prohibitions

- **Do not declare a request or response contract as a class.** They must be records. This is
  a blocking compliance rule (Constitution II).
- **Do not use `@Data`.** Also prohibited: `@Value`, `@SneakyThrows`, and any Lombok
  annotation outside the permitted set.
- **Do not return or accept a persistence entity at an API boundary.** Entities stay behind
  the service layer.
- **Do not import `javax.*`** for persistence, validation, or annotations.
- **Do not put persistence annotations on a record**, and do not let a contract mirror the
  entity's storage concerns.
- **Do not express business logic, derived computation, or workflow state in an entity.** An
  entity represents stored state; business rules belong to the service layer.
- **Do not add, remove, or rename a declared domain attribute or entity.** The blueprint is
  the schema authority; if it is silent about something, choose a safe default and keep the
  blueprint's shape intact.
- **Do not emit artifacts outside the Output contract**, and do not omit any listed artifact.
