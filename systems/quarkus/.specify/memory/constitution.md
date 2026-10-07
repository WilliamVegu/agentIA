<!--
SYNC IMPACT REPORT
==================
- Version change: 1.1.0 → 2.0.0 (MAJOR: Transición estructural del framework base de Spring Boot 3.x a Quarkus 3.x, consagración del principio AI-First / Zero-Defaults y formalización obligatoria de Historias de Usuario y BDD en Español)
- List of modified principles:
  * Principio I: Adaptado a la arquitectura en capas con Quarkus 3.x (JAX-RS/Quarkus REST `@Path`, CDI `@ApplicationScoped`, Hibernate ORM con Panache).
  * Principio II: Mantiene Records inmutables y Jakarta Validation, desacoplados de entidades Panache/JPA.
  * Principio III: Manejo centralizado de excepciones mediante Quarkus `@ServerExceptionMapper` / `ExceptionMapper<E>`.
  * Principio IV: Determinismo Offline-First adaptado al ciclo de build de Quarkus Maven.
  * Principio V: Quality Gates y auto-reparación basados en `@QuarkusTest` y suites de prueba Quarkus.
  * Principio VI: Seguridad de Secretos y frontera del orquestador (inmutable).
- Added sections/principles:
  * VII. Generación Exclusiva por IA y Cero Datos Predeterminados (AI-First & Zero-Default): Prohibición de datos simulados/mocks estáticos hardcodeados en flujos de usuario; inicio en estado limpio (Empty State); generación 100% dirigida por LLM.
  * VIII. Requerimientos Canónicos e Historias de Usuario en Español: Sintaxis obligatoria 'Como [rol], quiero [funcionalidad], para [beneficio]' y criterios BDD 'Dado [contexto], Cuando [evento], Entonces [resultado esperado]'.
- Removed sections: Ninguna
- Follow-up TODOs:
  * Actualizar specs y plantillas de agentes (scaffolder, domain, controller, service, test) para el stack Quarkus 3.x.
  * Refactorizar backend (prompts, services, dependencias) y frontend (limpieza de mocks y labels Quarkus).
-->

# Java/Quarkus Microservices Platform Constitution

## Core Principles

### I. Arquitectura en Capas Estricta y Separación de Responsabilidades en Quarkus
El diseño de cada microservicio MUST seguir de forma inquebrantable una estructura en capas unidireccional adaptada al ecosistema Quarkus 3.x:
`resource / controller` -> `service` (CDI `@ApplicationScoped`) -> `repository` (Hibernate ORM con `PanacheRepository<T>`) -> `model` / `entity`.
- Cada capa solo puede interactuar con su capa inmediata inferior.
- Los controladores / endpoints exponen APIs reactivas o bloqueantes usando Jakarta REST / Quarkus REST (`@Path`, `@GET`, `@POST`, `@PUT`, `@DELETE`, `@Produces`, `@Consumes`).
- Los servicios de negocio son beans CDI anotados con `@ApplicationScoped` y gestionan transacciones declarativas mediante `@Transactional`.
- Los repositorios implementan el patrón repositorio de Panache (`PanacheRepository<T>`), encapsulando el acceso a datos sin filtrar lógica de persistencia a capas superiores.

*Rationale*: Garantiza desacoplamiento absoluto, alta testabilidad unitaria y de integración ligera con `@QuarkusTest`, y aprovechamiento óptimo del build-time optimization característico de Quarkus.

### II. Contratos Inmutables y Validación Temprana
Los contratos de API (DTOs) MUST ser inmutables y estar estrictamente desacoplados de la persistencia:
- Todos los DTOs de Request y Response MUST implementarse mediante Java Records nativos (`record`).
- Queda terminantemente PROHIBIDO exponer entidades JPA o Panache directamente en los recursos REST o retornos de API.
- Todo record de Request MUST incorporar validaciones declarativas tempranas mediante anotaciones de Jakarta Validation (`@NotNull`, `@NotBlank`, `@Positive`, `@Email`, etc.).
- Ningún payload no validado debe alcanzar la capa de servicio.

*Rationale*: Previene mutaciones imprevistas de estado en memoria, evita la exposición del esquema relacional y detiene transacciones inválidas en la frontera de la API.

### III. Manejo Centralizado de Excepciones y Limpieza de Código
Toda respuesta de fallo MUST estar estandarizada y ser predecible:
- Se DEBE implementar el manejo global de excepciones utilizando Quarkus `@ServerExceptionMapper` o implementaciones de `ExceptionMapper<E>`.
- Ningún resource o controller debe contener bloques `try-catch` con fines de formateo de respuesta ni devolver entidades de error ad-hoc.
- Toda respuesta de error MUST responder a una estructura uniforme RFC 7807 (`ProblemDetails` o `ApiErrorRecord`) conteniendo: `timestamp`, código de estado HTTP (`status`), mensaje descriptivo (`message`) y detalles de validación cuando aplique.
- Clean Code obligatorio: Prohibido colocar lógica de negocio en capas de presentación o persistencia.

*Rationale*: Elimina inconsistencias en el consumo de APIs, simplifica la observabilidad y previene la fuga de stack traces o datos sensibles hacia el cliente.

### IV. Determinismo Offline-First y Aislamiento en Sandbox
La generación, compilación y verificación de código MUST ser estrictamente deterministas y autosuficientes:
- Las compilaciones y ejecuciones de pruebas MUST funcionar al 100% en modo offline (`mvn test -o`) dentro de contenedores Docker aislados sin acceso a redes externas.
- Queda terminantemente PROHIBIDO declarar dependencias en `pom.xml` que no pertenezcan al BOM de Quarkus o a la lista de dependencias permitidas previamente cacheadas en la imagen base.
- Prohibida cualquier descarga dinámica o resolución de red en tiempo de compilación.

*Rationale*: Garantiza reproducibilidad absoluta en entornos de integración continua (CI/CD) corporativos de alta seguridad y ejecución confiable en sandboxes herméticos.

### V. Quality Gates y Ciclo Acotado de Auto-Reparación
La validación del código generado y los límites de intervención autónoma MUST obedecer a compuertas estrictas:
- Aprobación 100% en pruebas: Todo microservicio DEBE superar el 100% de los tests unitarios y de integración ejecutados por Maven (`@QuarkusTest`, REST-assured, AssertJ, Mockito con `@InjectMock`).
- Cobertura exhaustiva: Toda funcionalidad DEBE contener pruebas tanto para el camino feliz (*happy path*) como para los caminos alternativos y excepciones (validaciones fallidas, recurso no existente, errores de negocio).
- Límite de auto-reparación: Ante fallos de compilación o aserción en pruebas, el agente autónomo dispone de un límite estricto de tres (3) iteraciones de corrección automática, guiándose exclusivamente por el stack trace emitido por Maven.
- Si la compilación o las pruebas no son exitosas al 3er intento, la tarea MUST ser abortada de forma inmediata y etiquetada bajo el estado: `Bloqueo por intervención humana requerida`.

*Rationale*: Evita bucles infinitos de alucinación o degradación de código, asegurando un desarrollo autónomo seguro y transparente.

### VI. Seguridad de Secretos y Frontera del Orquestador (LangGraph & LLMs)
La interacción entre el orquestador de IA, las API keys de modelos y el código del microservicio MUST cumplir límites estrictos:
- **Cero Secretos Hardcodeados**: Queda terminantemente PROHIBIDO hardcodear o exponer API keys de LLMs, tokens o credenciales en código fuente, archivos `application.properties`, scripts, Dockerfiles o commits.
- **Frontera del Orquestador**: LangGraph y los frameworks de IA operan estrictamente en la capa externa de orquestación. El código Quarkus generado DEBE mantenerse desacoplado y libre de dependencias del framework del orquestador.
- **Aislamiento en Pruebas**: Queda terminantemente PROHIBIDO que los tests unitarios o el build offline realicen llamadas a APIs de LLMs externas. Toda llamada debe ser simulada con mocks deterministas.
- **Inyección en Runtime**: Toda credencial en ambientes productivos MUST suministrarse vía variables de entorno seguras (`${LLM_API_KEY}`) o gestores de secretos.

*Rationale*: Protege la seguridad corporativa y previene costos imprevistos de API durante pruebas y verificación hermética.

### VII. Generación Exclusiva por IA y Cero Datos Predeterminados (AI-First & Zero-Default)
La plataforma MUST operar bajo el paradigma de generación autónoma auténtica sin datos preestablecidos:
- **Lienzo Limpio al Inicio (Empty State)**: La plataforma (Frontend y Backend) no debe precargar sesiones ficticias, especificaciones dummy ni microservicios de ejemplo (como `order-service` hardcodeado). El usuario debe iniciar en una pantalla limpia invitando a la creación genuina.
- **Generación Exclusiva por LLM**: Todo artefacto (historias de usuario, especificaciones, arquitectura, entidades, código fuente, suites de prueba y manifiestos) DEBE ser generado dinámicamente por la IA a partir de las instrucciones o requerimientos del usuario.
- **Prohibición de Fallback a Datos Simulados en Producción**: Queda prohibido el uso silencioso de datos sintéticos estáticos o simulados cuando el usuario espera una generación real de IA. Si no se configuran credenciales válidas, el sistema debe informar claramente la necesidad de configurar un proveedor de IA en lugar de simular una generación fija.

*Rationale*: Garantiza que la plataforma aporte valor real de ingeniería asistida por IA, evitando artefactos prefabricados o engañosos que no reflejen los requerimientos del usuario.

### VIII. Requerimientos Canónicos e Historias de Usuario en Español
Para garantizar la máxima claridad y alineación con los equipos de producto y negocio hispanohablantes:
- **Historias de Usuario**: Todas las historias de usuario generadas por la IA MUST redactarse obligatoriamente en español bajo la estructura canónica:
  `Como [rol del interesado], quiero [acción o capacidad técnica], para [beneficio o valor de negocio].`
- **Criterios de Aceptación BDD**: Todos los escenarios de prueba y aceptación MUST formularse en español bajo la convención Gherkin/BDD:
  `Dado [contexto o precondición inicial], Cuando [evento, acción o solicitud recibida], Entonces [resultado esperado, código de respuesta y estado resultante].`
- **Supuestos y Reglas de Negocio**: Todas las asunciones técnicas y restricciones del dominio deben expresarse en español estándar.

*Rationale*: Facilita la comprensión, validación y trazabilidad entre las partes interesadas hispanohablantes y los artefactos técnicos generados.

## Stack Tecnológico Base y Versiones

- **Lenguaje**: Java 21 LTS (Records, Pattern Matching, Sealed Types, Text Blocks).
- **Framework Principal**: Quarkus 3.x (Quarkus REST / RESTEasy Reactive, Hibernate ORM con Panache, SmallRye OpenAPI, Quarkus Hibernate Validator).
- **Inyección de Dependencias**: Jakarta CDI (`@ApplicationScoped`, `@Inject`, `@RequestScoped`).
- **Gestor de Construcción**: Maven 3.9+ con `quarkus-maven-plugin` y BOM `io.quarkus.platform:quarkus-bom`.
- **Persistencia en Pruebas**: Base de datos H2 en memoria (`quarkus-jdbc-h2`) con compatibilidad PostgreSQL o PostgreSQL DevServices.
- **Frameworks de Pruebas**: `@QuarkusTest`, `quarkus-junit5`, REST-assured, AssertJ y Mockito (`@InjectMock`).
- **Contratos y Validación**: Java 21 Records inmutables y Jakarta Validation (`jakarta.validation.constraints.*`).
- **Despliegue Containerizado**: Dockerfile multi-stage basado en Eclipse Temurin 21 (Quarkus Fast-jar) y manifiestos de salud vinculados a SmallRye Health (`/q/health`).

## Gobernanza y Enmiendas

- **Inmutabilidad y Cumplimiento**: Esta Constitución es la norma suprema del repositorio. Todo agente y flujo autónomo DEBE cumplirla sin excepciones.
- **Versionamiento**: SemVer (Mayor.Menor.Parche).
- **Control de Cambios**: Toda evolución requiere justificación técnica y análisis de impacto en los artefactos generados.

**Version**: 2.0.0 | **Ratified**: 2026-09-13 | **Last Amended**: 2026-09-29
