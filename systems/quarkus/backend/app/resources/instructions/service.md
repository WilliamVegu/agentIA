# Service layer instruction

## Technology contract

You produce the persistence-access and business-logic layers of a Quarkus microservice
using Hibernate ORM with Panache and Jakarta CDI. Automated compliance validation runs
before anything you write is persisted.

- **Language level**: Java 21 LTS.
- **Framework**: Quarkus 3.x, Hibernate ORM with Panache, Jakarta CDI.
- **Namespace**: `jakarta.*` exclusively (`jakarta.enterprise.context.*`, `jakarta.transaction.*`).
  `javax.*` is a validation failure.
- **Layering direction (Constitution I)**: `controller/resource → service (interface and
  implementation) → repository → model/entity`. Each layer may talk only to the layer
  immediately beneath it.
  - A service depends on its repository and on domain contracts. It does not depend on the web layer.
  - A repository depends on the persistence entity only.
  - No circular dependencies between layers.
- **Business logic home (Constitution I)**: services are the *only* place business rules and
  domain decisions live.
- **Contracts (Constitution II)**: services accept and return the immutable record contracts
  produced by the domain stage. They must never expose a persistence entity across their own
  boundary.
- **Dependency injection**: Jakarta CDI (`@ApplicationScoped`, constructor injection or `@Inject`).
- **Lombok (Stack rule)**: `@Data`, `@Value`, and `@SneakyThrows` are prohibited. Prefer
  explicit Java code.

## Rules

1. Read the blueprint payload and scaffolding/domain artifacts. Work only with existing
   entities and contracts.
2. Declare, per entity, one Panache repository implementing `PanacheRepository<EntityName>`
   in package `<package-path>.repository`.
3. Declare, per entity, one service interface expressing the operations required by the
   scenarios (create, read-one, read-all, delete).
4. Declare one service implementation annotated with `@ApplicationScoped`, marked
   `@Transactional` on mutating methods (or class level).
5. Implement creation by translating the request record into a new entity, persisting it via
   the Panache repository (`repository.persist(entity)`), and returning the response record.
6. Implement read-one and delete so that an absent resource raises the dedicated
   `ResourceNotFoundException`. Never return `null` to signal absence.
7. Implement read-all by streaming or listing all entities (`repository.listAll()`) and
   mapping each to its response record via `ResponseRecord.fromEntity(e)`.
8. Keep domain validation and business rules strictly in the service implementation.
9. Translate between contracts and entities exclusively through the response contract's
   factory and entity accessors.
10. Emit the dedicated `ResourceNotFoundException` as an unchecked runtime exception.
11. STRICT 100% QUARKUS PANACHE & CDI ONLY: Do NOT use Spring Boot annotations or packages
    (`@Service`, `@Repository`, `@Autowired`, `JpaRepository`, `org.springframework.*`). Use ONLY
    Jakarta CDI `@ApplicationScoped`, `@Inject`, `@Transactional` (jakarta.transaction) and Panache
    `PanacheRepository<EntityName>`. Mixing Spring annotations is strictly prohibited.

## Output contract

Produce exactly these artifacts, at exactly these workspace-relative paths. Emit one
repository, one service interface, and one service implementation per entity, plus the
domain exception.

| Path | Artifact |
| --- | --- |
| `src/main/java/<package-path>/repository/<EntityName>Repository.java` | Panache repository for data access. |
| `src/main/java/<package-path>/service/<EntityName>Service.java` | Service interface declaring business operations. |
| `src/main/java/<package-path>/service/<EntityName>ServiceImpl.java` | CDI `@ApplicationScoped` service implementation. |
| `src/main/java/<package-path>/exception/ResourceNotFoundException.java` | Dedicated domain exception for missing resources. Emitted once. |

`<package-path>` is the base package with segments separated by `/`. `<EntityName>` is the
entity name in PascalCase.

## Prohibitions

- **Do not use `javax.*` anywhere.**
- **Do not leak persistence entities across the service interface.**
- **Do not put business rules in repositories or resources.**
- **Do not use field injection in ways that hinder unit testability.**
- **Do not use prohibited Lombok annotations (`@Data`, `@Value`, `@SneakyThrows`).**
