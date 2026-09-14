<!--
SYNC IMPACT REPORT
==================
- Version change: 1.0.0 → 1.1.0 (MINOR: incorporación de principio de seguridad de secretos y frontera del orquestador LangGraph/LLM)
- List of modified principles:
  * Principios I a V: Se mantienen íntegros y vigentes.
- Added sections/principles:
  * VI. Seguridad de Secretos y Frontera del Orquestador (LangGraph & LLM API Keys)
  * Reglas de inyección de credenciales y aislamiento del motor de IA en el Stack Tecnológico
- Removed sections: Ninguna
- Follow-up TODOs: Ninguno
-->

# Java/Spring Boot Microservices Platform Constitution

## Core Principles

### I. Arquitectura en Capas Estricta y Separación de Responsabilidades
El diseño de cada microservicio MUST seguir de forma inquebrantable una estructura en capas unidireccional:
`controller` -> `service` (interfaz e implementación) -> `repository` -> `model` / `entity`.
- Cada capa solo puede interactuar con su capa inmediata inferior.
- Los `controllers` se limitan exclusivamente a la recepción HTTP, orquestación de llamadas al servicio y serialización de respuestas.
- Los `services` son los únicos responsables de concentrar la lógica de negocio y reglas de dominio.
- Los `repositories` gestionan exclusivamente el acceso a datos y consultas de persistencia.

*Rationale*: Garantiza desacoplamiento, mantenibilidad a largo plazo, alta testabilidad con mocks independientes y preparación para auditorías de código corporativas.

### II. Contratos Inmutables y Validación Temprana
Los contratos de API (DTOs) MUST ser inmutables y estar estrictamente desacoplados de la persistencia:
- Todos los DTOs de Request y Response MUST implementarse mediante Java Records nativos.
- Queda terminantemente PROHIBIDO exponer entidades JPA directamente en los controllers o retornos de API.
- Todo record de Request MUST incorporar validaciones declarativas tempranas mediante anotaciones de Jakarta Validation (`@NotNull`, `@NotBlank`, `@Positive`, `@Email`, etc.).
- Ningún payload no validado debe alcanzar la capa de servicio.

*Rationale*: Previene mutaciones no intencionadas de estado en memoria, evita la exposición accidental del esquema de base de datos y detiene transacciones inválidas en el borde de la aplicación.

### III. Manejo Centralizado de Excepciones y Limpieza de Código
Toda respuesta de fallo MUST estar estandarizada y ser predecible para clientes internos y externos:
- Se DEBE implementar un manejador global mediante `@RestControllerAdvice`.
- Ningún controller debe contener bloques `try-catch` con fines de formateo de respuesta ni devolver entidades de error ad-hoc.
- Toda respuesta de error MUST responder a una estructura uniforme `ProblemDetails` (RFC 7807) o `ApiErrorRecord` conteniendo: `timestamp`, código de estado HTTP (`status`), mensaje descriptivo (`message`) y detalles de validación de campo cuando aplique.
- Clean Code obligatorio: Prohibido colocar lógica de negocio en capas de presentación o persistencia.

*Rationale*: Elimina inconsistencias en el consumo de APIs, simplifica la observabilidad y previene la fuga de stack traces o datos sensibles hacia el cliente.

### IV. Determinismo Offline-First y Aislamiento en Sandbox
La generación, compilación y verificación de código MUST ser estrictamente deterministas y autosuficientes:
- Las compilaciones y ejecuciones de pruebas MUST funcionar al 100% en modo offline (`mvn test -o`) dentro de contenedores Docker aislados sin acceso a redes externas.
- Queda terminantemente PROHIBIDO declarar o incorporar dependencias en `pom.xml` que no se encuentren previamente cacheadas en la imagen base de Docker.
- Prohibida cualquier dependencia dinámica, descarga de scripts remotos en tiempo de compilación o resolución de artefactos de red en tiempo de build.

*Rationale*: Garantiza reproducibilidad absoluta en entornos de integración continua (CI/CD) corporativos de alta seguridad, elimina vulnerabilidades de la cadena de suministro (supply-chain attacks) y asegura la ejecución en sandboxes herméticos.

### V. Quality Gates y Ciclo Acotado de Auto-Reparación
La validación del código generado y los límites de intervención autónoma MUST obedecer a compuertas estrictas:
- Aprobación 100% en pruebas: Todo microservicio DEBE superar el 100% de los tests unitarios ejecutados por Maven para considerarse aprobado. Cero pruebas fallidas permitidas.
- Cobertura exhaustiva: Toda funcionalidad DEBE contener pruebas unitarias con Mockito y AssertJ tanto para el camino feliz (happy path) como para los caminos alternativos y excepciones (validaciones fallidas, recurso no existente, errores de negocio).
- Límite de auto-reparación: Ante fallos de compilación o aserción en pruebas, el agente autónomo dispone de un límite estricto de tres (3) iteraciones de corrección automática, guiándose exclusivamente por el stack trace emitido por Maven.
- Si la compilación o las pruebas no son exitosas al 3er intento, la tarea MUST ser abortada de forma inmediata y etiquetada bajo el estado: `Bloqueo por intervención humana requerida`.

*Rationale*: Evita bucles infinitos de alucinación o degradación de código, manteniendo un proceso de desarrollo autónomo seguro, transparente y con control humano preventivo.

### VI. Seguridad de Secretos y Frontera del Orquestador (LangGraph & LLMs)
La interacción entre el orquestador de IA, las API keys de modelos y el código del microservicio MUST cumplir límites estrictos:
- **Cero Secretos Hardcodeados**: Queda terminantemente PROHIBIDO hardcodear, commitear o exponer API keys de LLMs (OpenAI, Anthropic, Gemini, etc.), tokens o credenciales en código fuente, archivos de configuración (`application.yml`, `application.properties`), scripts, Dockerfiles o mensajes de commit.
- **Frontera de LangGraph**: LangGraph opera estrictamente en la capa externa de orquestación del agente (ej. en el pipeline de ejecución y supervisor de tareas). El código de los microservicios Java generados DEBE mantenerse desacoplado y libre de dependencias del framework del orquestador, salvo requerimiento funcional explícito de negocio.
- **Aislamiento en Pruebas (Zero LLM Network Calls)**: Queda terminantemente PROHIBIDO que los tests unitarios o el proceso de build offline (`mvn test -o`) realicen peticiones de red hacia APIs de LLMs externas. Si el microservicio incluye integración con modelos de lenguaje, toda llamada MUST ser 100% simulada mediante mocks deterministas (Mockito).
- **Inyección en Tiempo de Ejecución**: Toda credencial o API key requerida por el microservicio en ambientes productivos MUST suministrarse exclusivamente a través de variables de entorno seguras (`${LLM_API_KEY}`) o gestores de secretos corporativos (Vault, AWS Secrets Manager).

*Rationale*: Protege la seguridad corporativa evitando filtraciones de claves en repositorios, previene costos imprevistos de API durante pruebas y preserva la regla inquebrantable de compilación hermética y offline.

## Stack Tecnológico Base y Versiones

Las siguientes versiones y tecnologías representan la línea base obligatoria e inmutable del repositorio:

- **Lenguaje**: Java 21 LTS (aprovechando Records, Pattern Matching y características modernas de la plataforma).
- **Framework Principal**: Spring Boot 3.x (Spring Web, Spring Data JPA, Spring Validation).
- **Gestor de Construcción**: Maven 3.9+ (con configuración para compilación determinista y ejecución offline).
- **Persistencia en Pruebas**: Base de datos H2 en memoria configurada en sintaxis PostgreSQL (`jdbc:h2:mem:testdb;MODE=PostgreSQL`).
- **Frameworks de Pruebas**: JUnit 5 (Jupiter), Mockito (mocking y verificación de interacciones) y AssertJ (aserciones fluidas).
- **Librerías de Utilidad**: Project Lombok queda estrictamente RESTRINGIDO a las siguientes anotaciones:
  - `@Getter`
  - `@Setter`
  - `@Builder`
  - `@NoArgsConstructor`
  - `@AllArgsConstructor`
  - *Nota*: Se prohíbe el uso de `@Data`, `@SneakyThrows` o `@Value` en clases de entidad o servicio para evitar efectos colaterales en Equals/HashCode o enmascaramiento de excepciones.
- **Capa de Orquestación y Agentes**:
  - *Orquestador Autónomo*: LangGraph (gestionado exclusivamente en el plano de control del agente / pipeline CI/CD externo, fuera del artefacto JAR final).
  - *Gestión de Secretos de IA*: Variables de entorno seguras en el host/contenedor; ninguna clave persistida en el repositorio.
  - *Aislamiento de IA en Pruebas*: Mockito para desacoplar cualquier cliente de LLM en las compuertas de calidad.

## Ciclo de Vida de Entrega y Auditoría

- **Generación basada en Especificaciones**: Todo microservicio se genera a partir de especificaciones formales gestionadas por Spec Kit.
- **Aislamiento de Entregables**: Todo código final validado y probado DEBE aislarse en una rama Git dedicada bajo la convención:
  `feature/[nombre-spec]`
- **Commits Atómicos**: Cada entrega debe constar de commits atómicos, concisos y conformes a Conventional Commits (e.g., `feat(order-service): implement order creation endpoints`), listos para apertura de Pull Request sin dependencias de ramas sucias ni secretos residuales.
- **Preparación para Auditoría Interna**: El código debe ser limpio, autodocumentado, sin dead code ni variables sin usar, cumpliendo con las guías de estilo institucionales y preparado para pasar herramientas de escaneo estático y análisis de secretos (SonarQube, GitGuardian, TruffleHog).

## Gobernanza

- **Inmutabilidad y Supremacía**: Esta Constitución constituye la ley fundamental y suprema para el desarrollo y generación de microservicios en este repositorio. Ningún agente autónomo ni contribuidor humano puede revocar o ignorar estas reglas de forma tácita.
- **Procedimiento de Enmienda**: Cualquier modificación a estas normas exige un proceso de revisión formal, aprobación colegiada, justificación técnica y un plan de migración para los microservicios existentes.
- **Política de Versionamiento**: Este documento sigue Semantic Versioning (SemVer):
  - **MAJOR**: Remoción, debilitamiento o cambio incompatible de principios o gobernanza.
  - **MINOR**: Incorporación de nuevos principios, estándares de arquitectura o ampliación sustancial del stack tecnológico.
  - **PATCH**: Correcciones de formato, aclaraciones tipográficas o refinamientos no semánticos.
- **Verificación de Cumplimiento**: Todo Pull Request, pipeline de CI y ciclo de revisión debe verificar explícitamente el cumplimiento de los seis Principios Fundamentales antes del merge.

**Version**: 1.1.0 | **Ratified**: 2026-09-13 | **Last Amended**: 2026-09-13
