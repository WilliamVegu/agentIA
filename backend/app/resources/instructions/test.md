# Test synthesis instruction

## Technology contract

You produce the automated test suite of a Spring Boot microservice. Automated compliance
validation runs before anything you write is persisted.

- **Language level**: Java 21 LTS.
- **Framework**: Spring Boot 3.x test support.
- **Namespace**: `jakarta.*` exclusively. `javax.*` is a validation failure.
- **Test frameworks (Stack rule)**: **JUnit 5 (Jupiter)** as the test engine, **Mockito** for
  mocking and interaction verification, and **AssertJ** for fluent assertions. These three
  are the required stack; do not substitute a different engine, a different mocking library,
  or bare `assertTrue`-style assertions where a fluent assertion expresses the intent.
- **Coverage obligation (Constitution V)**: every declared functionality must be covered for
  both the happy path and the alternative and failure paths — failed validation, resource
  not found, and business-rule violations. Zero failing tests are permitted; the built
  service is only considered acceptable at a 100% pass rate.
- **Hermetic operation (Constitution IV and VI)**: the suite must run entirely offline with
  no network access. It must make no call to any external service, and in particular **no
  call to any language-model or other remote API**. Any such integration must be mocked with
  a deterministic stub.
- **Contracts**: tests operate against the record contracts and service interfaces produced
  by earlier stages. They must not reach into persistence entities to construct expectations
  in a way that bypasses the service contract.

## Rules

1. Read the blueprint payload, and in particular its **acceptance scenarios**. The scenarios
   — not a fixed list of method names — are the specification of what must be tested. Every
   scenario must map to at least one test method.
2. Derive each test method from the scenario it verifies: cover the precondition the
   scenario states, perform the action it describes, and assert the outcome it declares.
   Name each method after the behaviour it verifies, so the scenario-to-test mapping is
   readable from the test report.
3. Cover, per entity, at minimum: successful creation, successful retrieval by identifier,
   the not-found path for a missing resource, and successful retrieval of the full
   collection. Derive any further cases from additional declared scenarios.
4. Cover the failure paths explicitly — a missing resource must be asserted to raise the
   dedicated not-found exception, not merely to return an empty result.
5. Unit-test the service implementation in isolation: substitute the repository with a mock,
   inject it through the constructor, and verify both the returned value and the
   interactions the implementation is required to perform.
5a. **Unit tests do not prove persistence, so also emit a slice test that does.** A
   `@DataJpaTest` per entity, exercising the repository against a real database, must
   perform an actual `save()` and then read the row back. This is not optional coverage:
   a Mockito test substitutes the repository, so no persistence provider and no
   pre-insert entity validation runs, and a service whose every insert fails will pass its
   entire unit suite. A `@DataJpaTest` is the only layer in this contract that calls
   `save()` for real.
5b. **Emit a `@WebMvcTest` per controller.** With the service layer replaced by
   `@MockitoBean`, assert the HTTP contract: the created resource returns 201, an invalid
   body returns 400 through the global handler, and a missing resource returns 404. This
   covers the transport boundary that neither the unit tests nor the slice test exercises.
5c. Note what each layer cannot see, and do not claim otherwise in a test name: the unit
   test cannot see persistence, and the web slice cannot see either persistence or
   business logic.
6. Stub only what the test actually exercises. Do not add stubbings that no assertion depends
   on, because unnecessary stubbing fails under strict stub enforcement and is reported as a
   test error rather than a test failure.
7. Assert with fluent AssertJ assertions that express the intent — for example that a
   collection is not empty and has the expected size, or that an exception is thrown with a
   particular type — rather than asserting a bare boolean.
8. Emit a context-load test for the application entry point that confirms the Spring context
   starts with the generated configuration. It must be a genuine context assertion, not a
   placeholder that always passes.
9. Keep unit tests free of a running HTTP server and a real database. Where a test genuinely
   requires a Spring context, use the narrowest slice that satisfies it and keep the
   datasource in-memory.
10. Ensure the test tree mirrors the main source package layout exactly, so that test classes
    are discoverable by the build without additional configuration.

## Output contract

Produce exactly these artifacts, at exactly these workspace-relative paths. Emit one service
test class per declared domain entity, plus exactly one application context test.

| Path | Artifact |
| --- | --- |
| `src/test/java/<package-path>/<ServiceName>ApplicationTests.java` | Application context-load test for the Spring Boot entry point. Emitted once. |
| `src/test/java/<package-path>/service/<Entity>ServiceTest.java` | Mockito-backed unit tests for the entity's service implementation, derived from the declared acceptance scenarios. |
| `src/test/java/<package-path>/service/<Entity>ServiceTest.java` | (continued) |
| `src/test/java/<package-path>/repository/<Entity>RepositoryTest.java` | `@DataJpaTest` slice: saves and reads back a real row for each entity. The only generated test that exercises persistence. |
| `src/test/java/<package-path>/controller/<Entity>ControllerTest.java` | `@WebMvcTest` slice: asserts the HTTP contract (201/400/404) with the service layer mocked. |

`<package-path>` is the base package name with `/` separators. `<ServiceName>` is the service
identity in PascalCase; `<Entity>` is the PascalCase entity name from the blueprint. Package
declarations must match the directory layout exactly.

## Prohibitions

- **Do not make any network call from a test** — no remote API, no language-model provider,
  no external HTTP service. This is a blocking constitutional rule (Constitution VI) and it
  also breaks the hermetic offline build.
- **Do not emit a fixed, entity-independent set of test method names.** Coverage must follow
  the supplied acceptance scenarios; a suite that ignores them is non-compliant even if it
  passes.
- **Do not emit placeholder assertions** that cannot fail, such as asserting a literal
  constant is true purely to make a test exist.
- **Do not stub a method that the test does not exercise**, and do not disable strict stub
  checking to work around it.
- **Do not connect a unit test to a real external database**, and do not require a running
  server for a unit-scoped test.
- **Do not import `javax.*`.**
- **Do not use `@Data`**, `@Value`, or `@SneakyThrows`.
- **Do not hardcode credentials**, tokens, or environment-specific hosts in test
  configuration.
- **Do not weaken or bypass an assertion to make a test pass** — for example by catching an
  expected exception and asserting nothing.
- **Do not emit artifacts outside the Output contract**, and do not omit any listed artifact.
