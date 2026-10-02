# Layer Architecture

## Granularity
task-level

## When to apply
Apply whenever generating or modifying a Spring Boot microservice, before writing
any class. Every artifact this skill covers belongs to exactly one layer, and the
layer decides the file's package, its dependencies, and what it is allowed to
return.

## Rules
1. Place every class in exactly one layer package: `controller`, `service`
   (interface and `impl`), `repository`, or `model` (`entity` and `dto`).
2. Depend only on the layer immediately below. A controller may call a service; a
   service may call a repository and other services; a repository may use entities
   only. Never skip a layer.
3. Never import a repository type from a controller. If a controller needs data,
   it calls a service method and receives a DTO.
4. Keep all business logic in the service layer. A controller orchestrates a call
   and serialises the result; nothing else.
5. Keep all persistence logic in the repository layer. A service must not
   construct queries inline or open transactions by hand.
6. Never return a JPA entity from a controller, and never accept one as a request
   body. Cross layer boundaries with DTOs only.
7. Declare service behaviour on an interface and implement it in the `impl`
   package, so callers depend on the interface rather than the implementation.
8. Place every exception type in its own package and let it propagate to the
   global handler. Do not catch an exception in a controller to build a response.

<!-- SLOW_UPDATE_START -->
<!-- SLOW_UPDATE_END -->
