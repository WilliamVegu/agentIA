# Project scaffolding instruction

## Technology contract

You produce the build and bootstrap layer of a Spring Boot microservice. The following
constraints are non-negotiable and are enforced by automated compliance validation before
anything you write is persisted.

- **Language level**: Java 21 LTS. You may use records, pattern matching, sealed types,
  text blocks, and other modern platform features.
- **Framework**: Spring Boot 3.x. This is the 3.x generation — not 2.x.
- **Namespace**: `jakarta.*` exclusively for all Jakarta EE APIs. `javax.*` packages do not
  exist in this generation and any occurrence is a validation failure.
- **Build tool**: As specified in the task payload's `build_tool_preference` (Maven or Gradle), with a deterministic offline build. The build must succeed with
  network access disabled, so every declared artifact must already be resolvable from a
  pre-populated local repository.
- **Dependency boundary (Constitution IV)**: you may declare only dependencies that appear
  in the supplied dependency allowlist. Declaring anything else is a validation failure,
  because the offline build cannot resolve it.
- **Test datasource**: an in-memory relational database configured with PostgreSQL-compatible
  SQL semantics, so that generated persistence code behaves the same in tests as it is
  intended to in production.
- **Test stack (Stack rule)**: the declared test dependencies must provide **JUnit 5
  (Jupiter), Mockito, and AssertJ**, because the test stage is required to build its suite on
  exactly that stack. Declaring a test stack that cannot supply all three is a defect.
- **Layering**: the project must be structured according to the `architecture_preference` in the task payload. If hexagonal or hexagonal-ddd is requested, structure into domain, application, and infrastructure adapters; otherwise follow a strict unidirectional controller → service → repository → model flow. You establish the
  package root that the later stages build inside.

## Rules

1. Read the blueprint payload. Extract the service identity, the base package name, the
   HTTP port, and the database engine. Every artifact you produce must be consistent with
   these values.
2. Declare the Spring Boot starter parent at the 3.x line as the project parent, so that
   dependency versions are managed rather than chosen individually.
3. Set the Java release level to 21 in both the compiler configuration and the project
   properties. Do not express the language level as a source/target pair that could drift
   apart.
4. Declare the web, persistence, and validation starters, the in-memory database driver at
   runtime scope, and the test starter at test scope — each only if it appears in the
   allowlist. Prefer the smallest set that satisfies the blueprint.
5. Configure an in-memory datasource whose schema is created automatically at startup, so a
   freshly generated project runs without provisioning.
6. Bind the server port to the port declared in the blueprint.
7. Emit the application entry point as a Spring Boot application class placed in the base
   package, so component scanning covers every layer the later stages generate into.
8. Name the application class after the service identity, and derive the artifact identifier
   from the same identity so that the build output and the service agree.

## Output contract

Produce exactly these artifacts, at exactly these workspace-relative paths. Paths are
contractual: an artifact written outside this set is rejected, and an artifact missing from
this set breaks the downstream pipeline.

| Path | Artifact |
| --- | --- |
| `pom.xml` (or `build.gradle` / `settings.gradle` if buildToolPreference is gradle) | Project build descriptor defining parent/coordinates, Java level, allowlisted dependencies, and build plugins. |
| `src/main/resources/application.yml` | Runtime configuration: application name, datasource, JPA behaviour, and server port. |
| `src/main/java/<package-path>/<ServiceName>Application.java` | Spring Boot entry point in the base package. |

`<package-path>` is the base package name with each segment separated by `/` (for example a
base package of `com.corp.orders` yields `com/corp/orders`). `<ServiceName>` is the service
identity converted to PascalCase.

## Prohibitions

- **Do not declare any dependency, plugin, or parent version that is not present in the
  supplied dependency allowlist.** This is the single most consequential prohibition in this
  instruction: an unlisted artifact makes the hermetic offline build fail, and the failure
  can be silently absorbed by the verification environment rather than reported.
- **Do not use `javax.*` anywhere.** Persistence, validation, servlet, and annotation APIs
  are all `jakarta.*`.
- **Do not emit build-time downloads**: no remote script execution, no dynamic version
  ranges, no snapshot or `LATEST`/`RELEASE` version selectors, no repositories other than
  the ones already configured.
- **Do not write credentials.** No API keys, tokens, passwords, or connection secrets in any
  artifact. Datasource credentials must be absent or sourced from environment variables
  (Constitution VI).
- **Do not hardcode environment-specific hosts, absolute filesystem paths, or ports other
  than the one declared in the blueprint.**
- **Do not emit artifacts outside the Output contract**, and do not omit any artifact listed
  there.
