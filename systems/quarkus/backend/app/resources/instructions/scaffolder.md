# Project scaffolding instruction

## Technology contract

You produce the build and bootstrap layer of a Quarkus microservice. The following
constraints are non-negotiable and are enforced by automated compliance validation before
anything you write is persisted.

- **Language level**: Java 21 LTS. You may use records, pattern matching, sealed types,
  text blocks, and other modern platform features.
- **Framework**: Quarkus 3.x (BOM `io.quarkus.platform:quarkus-bom`).
- **Namespace**: `jakarta.*` exclusively for all Jakarta EE APIs. `javax.*` packages do not
  exist in this generation and any occurrence is a validation failure.
- **Build tool**: Maven, with a deterministic offline build. The build must succeed with
  network access disabled, so every declared artifact must already be resolvable from a
  pre-populated local repository.
- **Dependency boundary (Constitution IV)**: you may declare only dependencies that appear
  in the supplied dependency allowlist. Declaring anything else is a validation failure,
  because the offline build cannot resolve it.
- **Test datasource**: an in-memory relational database configured with PostgreSQL-compatible
  SQL semantics (H2 / `quarkus-jdbc-h2`), so that generated persistence code behaves the same
  in tests as it is intended to in production.
- **Test stack (Stack rule)**: the declared test dependencies must provide **JUnit 5
  (Jupiter via quarkus-junit5), Mockito (quarkus-junit5-mockito), REST-assured, and AssertJ**,
  because the test stage is required to build its suite on exactly that stack. Declaring a
  test stack that cannot supply these is a defect.
- **Layering**: the project must be structured for a strict unidirectional
  controller/resource → service → repository → model flow (Constitution I). You establish the
  package root that the later stages build inside.

## Rules

1. Read the blueprint payload. Extract the service identity, the base package name, the
   HTTP port, and the database engine. Every artifact you produce must be consistent with
   these values.
2. Declare the Quarkus BOM (`io.quarkus.platform:quarkus-bom`) at the 3.x line in the
   `dependencyManagement` section, so that dependency versions are managed rather than chosen
   individually.
3. Set the Java release level to 21 in both compiler configuration (`maven-compiler-plugin`)
   and project properties (`maven.compiler.release=21`).
4. Declare Quarkus REST/Jackson (`quarkus-resteasy-reactive-jackson` or `quarkus-rest-jackson`),
   persistence (`quarkus-hibernate-orm-panache`), validation (`quarkus-hibernate-validator`),
   database driver (`quarkus-jdbc-h2`), and test dependencies (`quarkus-junit5`,
   `quarkus-junit5-mockito`, `rest-assured`, `assertj-core`) at test scope.
5. Configure `application.properties` with:
   - `quarkus.application.name` matching the service name.
   - `quarkus.http.port` bound to the declared port.
   - `quarkus.datasource.db-kind=h2` and in-memory URL with PostgreSQL mode.
   - `quarkus.hibernate-orm.database.generation=update`.
6. Emit the application entry point / lifecycle class in the base package, ensuring CDI
   component scanning covers every layer generated in downstream stages.
7. Name the entry class after the service identity, and derive the artifact identifier
   from the same identity so that the build output and the service agree.
8. STRICT 100% QUARKUS ONLY: Do NOT declare any Spring Boot parent (`spring-boot-starter-parent`),
   dependencies (`spring-boot-starter-*`), or plugins (`spring-boot-maven-plugin`). Spring Boot
   artifacts are strictly prohibited. The project MUST be 100% native Quarkus 3.x.

## Output contract

Produce exactly these artifacts, at exactly these workspace-relative paths. Paths are
contractual: an artifact written outside this set is rejected, and an artifact missing from
this set breaks the downstream pipeline.

| Path | Artifact |
| --- | --- |
| `pom.xml` | Maven project descriptor defining coordinates, Quarkus BOM, Java 21, allowlisted dependencies, and quarkus-maven-plugin. |
| `src/main/resources/application.properties` | Runtime configuration: application name, datasource, Panache/Hibernate behaviour, and HTTP port. |
| `src/main/java/<package-path>/<ServiceName>Application.java` | Quarkus lifecycle or entry point in the base package. |

`<package-path>` is the base package name with each segment separated by `/` (for example a
base package of `com.corp.orders` yields `com/corp/orders`). `<ServiceName>` is the service
identity converted to PascalCase.

## Prohibitions

- **Do not declare any dependency, plugin, or parent/BOM version that is not present in the
  supplied dependency allowlist.** An unlisted artifact makes the hermetic offline build fail.
- **Do not use `javax.*` anywhere.** Persistence, validation, and REST APIs are all `jakarta.*`.
- **Do not emit build-time downloads**: no remote script execution, no dynamic version
  ranges, no snapshot or `LATEST`/`RELEASE` version selectors.
- **Do not write credentials.** No API keys, tokens, passwords, or connection secrets in any
  artifact (Constitution VI).
- **Do not hardcode environment-specific hosts, absolute filesystem paths, or ports other
  than the one declared in the blueprint.**
- **Do not emit artifacts outside the Output contract**, and do not omit any artifact listed
  there.
