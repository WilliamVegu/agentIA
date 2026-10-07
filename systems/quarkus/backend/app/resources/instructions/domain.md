# Domain model instruction

## Technology contract

You produce the persistence entities and the API contracts for a Quarkus microservice
utilizing Hibernate ORM with Panache. Automated compliance validation runs before anything
you write is persisted.

- **Language level**: Java 21 LTS.
- **Framework**: Quarkus 3.x, Hibernate ORM with Panache.
- **Namespace**: `jakarta.*` exclusively. Persistence annotations come from
  `jakarta.persistence`, validation annotations from `jakarta.validation.constraints`.
  `javax.*` is a validation failure.
- **Layer placement (Constitution I)**: persistence entities belong to the model layer and
  to nothing else. They must not be referenced by controllers/resources and must not be
  returned from any API surface.
- **Immutable API contracts (Constitution II)**: every request and response contract must be
  a **native Java record**. A request or response declared as a class is a validation
  failure. Contracts must be structurally decoupled from the persistence entity — a contract
  is not the entity, and it must not carry persistence annotations.
- **Validation (Constitution II)**: request contracts carry declarative Jakarta Validation
  annotations. Constraints must be expressed on the contract, so that no unvalidated payload
  can reach the service layer.
- **Lombok (Stack rule)**: Project Lombok is restricted to `@Getter`, `@Setter`, `@Builder`,
  `@NoArgsConstructor`, and `@AllArgsConstructor`. **`@Data` is prohibited on JPA/Panache entities**
  — and on every other class — because it generates `equals`/`hashCode` over mutable state.
  `@Value` and `@SneakyThrows` are likewise prohibited. Prefer standard Java accessors or native
  Panache entity definitions without Lombok.

## Rules

1. Read the blueprint payload. It declares the domain entities, and for each one its
   attributes with a name, a type, and constraints (whether it is required and whether it is
   the identifier).
2. Produce exactly one persistence entity per declared domain entity using standard Jakarta
   Persistence (`@Entity`, `@Table`) compatible with Panache Repository pattern.
3. Guarantee that each entity declares exactly one identifier attribute (`@Id`, `@GeneratedValue`).
   If the blueprint marks one, use it. If not, add a surrogate identifier (Long or UUID).
4. Map each declared attribute to a Java type appropriate to its declared type (`String`, `Long`,
   `BigDecimal`, `Boolean`, `LocalDateTime`, `UUID`).
5. Apply declarative validation to every attribute that the blueprint marks as required or
   as carrying a format constraint.
6. Apply no validation constraint that the blueprint does not declare.
7. Give the entity a default constructor so Hibernate can instantiate it, and implement
   identity equality over the identifier only.
8. Emit, per entity, one response contract that represents the full readable shape, and one
   request contract that represents the writable shape. The request contract excludes the
   identifier; the response contract includes it.
9. Give the response contract a static factory method `fromEntity(Entity entity)` that builds
   it from a persistence entity, so entity-to-contract translation is encapsulated. Return
   `null` for a `null` input.
10. Order your work: entity first, then the response contract, then the request contract.
11. STRICT 100% QUARKUS & JAKARTA ONLY: Do NOT use Spring annotations or classes (`org.springframework.*`).
   Entities use standard Jakarta Persistence (`jakarta.persistence.*`), and contracts use native Java Records
   with Jakarta Validation (`jakarta.validation.constraints.*`). Spring Data or Spring annotations are prohibited.

## Output contract

Produce exactly these artifacts, at exactly these workspace-relative paths. Emit one
persistence entity, one request contract, and one response contract for every domain entity
declared in the blueprint.

| Path | Artifact |
| --- | --- |
| `src/main/java/<package-path>/model/<EntityName>.java` | JPA Persistence entity mapped to the entity's database table. |
| `src/main/java/<package-path>/dto/<EntityName>Request.java` | Immutable Java record contract for request payloads with Jakarta validation. |
| `src/main/java/<package-path>/dto/<EntityName>Response.java` | Immutable Java record contract for response payloads with static `fromEntity` factory. |

`<package-path>` is the base package with segments separated by `/`. `<EntityName>` is the
entity name in PascalCase.

## Prohibitions

- **Do not use `javax.*` anywhere.** Use `jakarta.persistence.*` and `jakarta.validation.*`.
- **Do not expose entities across the API boundary.** Returning an entity directly from a
  resource/controller or accepting one as an endpoint argument violates Constitution II.
- **Do not declare contracts as classes.** Request and response contracts MUST be Java records.
- **Do not put `@Data`, `@Value`, or `@SneakyThrows` on any class.**
- **Do not place business logic in entities or contracts.** Entities hold persistent state;
  contracts represent external API shape.
