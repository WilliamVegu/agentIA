"""Trusted stage contracts selected from supported architecture preferences."""

def is_hexagonal(preference):
    value = str(preference or "").lower()
    return "hex" in value or "ports" in value or "adapters" in value


def hexagonal_instruction(stage, default):
    if stage == "SCAFFOLDER":
        return default
    common = """Generate complete compilable Java 21 / Spring Boot 3 source for a HEXAGONAL architecture.
Use jakarta namespaces, constructor injection and immutable Java record DTOs. No Lombok @Data,
@Value or @SneakyThrows. Preserve exact identifier types, attributes, business keys and scenarios.
All code must reference actual prior artifacts and remain coherent with their signatures.
Domain types and ports are framework independent. Application depends on domain ports, never on
infrastructure or Spring Data. Infrastructure adapters depend inward on domain and application.
The following profile REPLACES the default layered instruction and its default output paths.
Never emit package-root model/, repository/, service/, service/impl/, controller/ or exception/.
Emit only the stage-owned artifacts as the required JSON map. No markdown or placeholder code.
"""
    contracts = {
        "DOMAIN": """For each declared entity emit:
1. A domain/model/<Entity>.java plain domain object or record preserving every attribute.
2. domain/port/out/<Entity>RepositoryPort.java for persistence operations on domain objects.
3. domain/port/in/<Entity>UseCase.java for story-driven use cases expressed only in domain types.
4. application/dto/Create<Entity>Request.java and <Entity>Response.java as records with validation.
   DTO mapping factories accept the domain model, NEVER a JPA persistence type.
5. infrastructure/persistence/<Entity>JpaEntity.java mapped to the requested SQL table.
Keep domain/model separate from JPA annotations and map entity attributes exactly. Do not emit
repository interfaces, service implementations or REST adapters; those belong to later stages.
""",
        "SERVICE": """For each entity consume the already emitted domain models, input and output ports:
1. application/service/<Entity>ApplicationService.java implements the input use-case port,
   annotated @Service, with constructor injection of the output repository port. Keep all business
   decisions here; use @Transactional and readOnly transactions where appropriate.
2. infrastructure/persistence/<Entity>JpaRepository.java extends JpaRepository over the actual JPA entity.
3. infrastructure/adapter/out/<Entity>PersistenceAdapter.java implements the output repository port
   by using the JPA repository and mapping JPA objects to and from domain objects.
4. application/exception/ResourceNotFoundException.java for absent resources.
Do not reference JPA entities or Spring Data repositories from the application service. Domain
objects cross ports; DTOs cross REST boundaries. Follow the exact prior method signatures.
""",
        "CONTROLLER": """Emit infrastructure/adapter/in/web/<Entity>Controller.java consuming the domain input
use-case port and mapping request/response records to/from domain objects. Derive routes and status
codes from actual scenarios. Validate request records. Emit centralized GlobalExceptionHandler
in the same incoming adapter, mapping actual application exceptions to appropriate HTTP responses.
No controller may import persistence entities or Spring Data repositories. Do not emit a default
package-root controller or a default service implementation. Do not add undeclared demo endpoints.
""",
        "TEST": """Generate runnable JUnit5/Mockito unit tests for the actual application services using mocked
domain output ports, WebMvcTest tests for actual incoming REST adapters, and repository/context tests
using H2 as appropriate. Match every actual package, method signature, constructor and UUID type.
Cover declared Given/When/Then scenarios, duplicate business keys and missing resources. Tests must
run offline and may not contact any model or external API. Never invent five passing tests or
pretend these generated tests have executed. Use only dependencies declared by the actual build.
""",
    }
    return common + contracts[stage]
