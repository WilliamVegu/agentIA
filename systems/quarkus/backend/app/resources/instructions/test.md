# Test synthesis instruction

## Technology contract

You produce the automated test suite of a Quarkus microservice. Automated compliance
validation runs before anything you write is persisted.

- **Language level**: Java 21 LTS.
- **Framework**: Quarkus 3.x test support (`@QuarkusTest`, `io.quarkus.test.junit.QuarkusTest`).
- **Namespace**: `jakarta.*` exclusively. `javax.*` is a validation failure.
- **Test frameworks (Stack rule)**: **JUnit 5 (Jupiter)**, **Mockito** (`@InjectMock`),
  **REST-assured** for endpoint verification, and **AssertJ** for fluent assertions.
  These four are the required stack; do not substitute a different test engine or bare
  assertions.
- **Coverage obligation (Constitution V)**: every declared functionality must be covered for
  both happy path and alternative/failure paths (failed validation, resource not found,
  business error). Zero failing tests are permitted.
- **Hermetic operation (Constitution IV and VI)**: the suite must run entirely offline with
  no network access. It must make no call to external services or remote LLM APIs.
- **Contracts**: tests operate against record contracts, REST endpoints, and service interfaces.

## Rules

1. Read the blueprint payload and acceptance scenarios. Every scenario must map to at least
   one test method.
2. Derive each test method from the scenario it verifies: test preconditions, execute the
   action, and assert the outcome. Name methods descriptively.
3. Test service implementations in isolation using JUnit 5, AssertJ, and Mockito: mock the
   Panache repository, inject it, and verify returned record contracts and interactions.
4. Test HTTP resources using `@QuarkusTest` and REST-assured: verify HTTP status codes
   (`201 Created`, `200 OK`, `400 Bad Request`, `404 Not Found`), response content-type,
   and JSON payload bodies.
5. Cover failure paths explicitly: missing resources must return 404 with standard RFC 7807
   error details; invalid payloads must return 400 with validation violations.
6. Stub only what the test exercises. Avoid unnecessary stubbing.
7. Use AssertJ fluent assertions (`assertThat(...)`) to express expectations clearly.
8. Emit an application health / startup test verifying that the Quarkus runtime boots
   successfully and exposes the service catalogue.
9. Keep unit tests isolated and fast; use in-memory H2 database for integration tests.
10. Ensure the test directory structure mirrors `src/main/java` package layout exactly.
11. STRICT 100% QUARKUS TEST ONLY: Do NOT use Spring Boot test annotations (`@SpringBootTest`, `@WebMvcTest`,
    `@MockBean`, `org.springframework.test.*`). Use ONLY `@QuarkusTest`, `io.quarkus.test.junit.QuarkusTest`,
    `io.quarkus.test.junit.mockito.InjectMock`, and `io.restassured.RestAssured`. Mixing Spring test
    frameworks is strictly prohibited.

## Output contract

Produce exactly these artifacts, at exactly these workspace-relative paths. Emit one unit
test suite and one resource integration test suite per entity, plus the lifecycle test.

| Path | Artifact |
| --- | --- |
| `src/test/java/<package-path>/service/<EntityName>ServiceTest.java` | Unit tests for service logic with Mockito and AssertJ. |
| `src/test/java/<package-path>/controller/<EntityName>ResourceTest.java` | Endpoint integration tests using `@QuarkusTest` and REST-assured. |
| `src/test/java/<package-path>/ApplicationLifecycleTest.java` | Quarkus boot and catalogue verification test. Emitted once. |

`<package-path>` is the base package with segments separated by `/`. `<EntityName>` is the
entity name in PascalCase.

## Prohibitions

- **Do not use `javax.*` anywhere.**
- **Do not make network or external API calls during tests.**
- **Do not leave unasserted scenarios or placeholder tests that always pass.**
- **Do not bypass the service boundary to touch persistence state directly in unit tests.**
- **Do not use untested random data or non-deterministic test ordering.**
