# Feature Specification: 016 - Quarkus AI-Native Studio (Zero-Defaults & Spanish BDD)

**Feature Branch**: `016-quarkus-ai-native-studio`

**Created**: 2026-09-29

**Status**: Draft

**Constitution Version**: 2.0.0 (Quarkus 3.x, AI-First & Zero-Default, Historias en Español)

---

## 1. Visión y Resumen Ejecutivo

Esta funcionalidad transforma la plataforma de generación autónoma de microservicios:
1. **Reemplazo Integral de Framework**: Transición completa del stack de generación de **Spring Boot 3.x** hacia **Quarkus 3.x** (Java 21 LTS, Quarkus REST / RESTEasy Reactive, Hibernate ORM con Panache, Jakarta EE 10 / CDI `@ApplicationScoped` y `@QuarkusTest`).
2. **Generación Exclusiva por IA y Cero Datos Predeterminados (AI-First & Zero-Default)**: Eliminación de sesiones predeterminadas, mocks precargados (`order-service`, `Order`, datos dummy). La plataforma arranca en un **Lienzo Limpio (Empty State)** esperando los requerimientos reales del usuario y conexión con un proveedor de IA.
3. **Historias de Usuario y Criterios BDD en Español**: Estandarización de las especificaciones y contratos funcionales en idioma español nativo (`Como... quiero... para...` y `Dado... cuando... entonces...`).

---

## 2. Requerimientos Funcionales (FRs)

### FR-001: Lienzo Limpio y Cero Datos Predeterminados (Zero-Defaults)
- Al ingresar a la aplicación web, el estado inicial de la sesión debe ser nulo o vacío (`Empty State`), sin preseleccionar microservicios ficticios ni simular generaciones previas.
- El usuario debe ver una pantalla que le invite explícitamente a ingresar sus requerimientos en lenguaje natural y configurar su proveedor de IA (Gemini, Groq, OpenAI o DeepSeek).
- Se elimina la ejecución silenciosa de mocks estáticos prefabricados.

### FR-002: Historias de Usuario y BDD en Español
- El servicio de descomposición de requerimientos (`requirements_service.py`) debe formular las historias de usuario en español canónico:
  * `Como [rol], quiero [acción/funcionalidad], para [beneficio].`
- Los criterios de aceptación BDD deben estructurarse estrictamente en español:
  * `Dado [precondición], Cuando [evento/solicitud], Entonces [resultado esperado].`
- Los supuestos arquitectónicos, entidades y títulos generados en `spec.md` deben redactarse en español.

### FR-003: Pipeline de Scaffolding y Generación Quarkus 3.x
- El generador de scaffolding debe sintetizar un `pom.xml` basado en `io.quarkus.platform:quarkus-bom` (versión 3.x) y `quarkus-maven-plugin`.
- Configuración en `src/main/resources/application.properties` con propiedades estándar de Quarkus (puerto `quarkus.http.port`, base de datos H2/PostgreSQL `quarkus.datasource.db-kind`, hibernate panache `quarkus.hibernate-orm.database.generation=update`).
- La clase principal de aplicación no requiere anotaciones de Spring y utiliza el ciclo de vida de Quarkus.

### FR-004: Arquitectura en Capas de Quarkus
- **Controladores / Recursos REST**: Empleo de Jakarta REST (`@Path`, `@GET`, `@POST`, `@PUT`, `@DELETE`, `@Produces(MediaType.APPLICATION_JSON)`, `@Consumes(MediaType.APPLICATION_JSON)`).
- **Servicios de Dominio**: Beans CDI gestionados por `@ApplicationScoped` con transaccionalidad declarativa `@Transactional`.
- **Persistencia**: Implementación del patrón Repository con Hibernate ORM y Panache (`PanacheRepository<T>`).
- **Manejo de Errores**: Manejadores de excepciones globales con `@ServerExceptionMapper` o `ExceptionMapper<T>`.

### FR-005: Catálogo de Dependencias Permitidas para Quarkus
- Actualizar `backend/app/resources/dependency_allowlist.json` para permitir únicamente artefactos del ecosistema Quarkus (`io.quarkus:quarkus-resteasy-reactive-jackson`, `io.quarkus:quarkus-hibernate-orm-panache`, `io.quarkus:quarkus-jdbc-h2`, `io.quarkus:quarkus-hibernate-validator`, `io.quarkus:quarkus-smallrye-openapi`, etc.).

### FR-006: Pruebas Unitarias y de Integración con `@QuarkusTest`
- Generar suites de prueba con `@QuarkusTest`, `quarkus-junit5`, REST-assured (`given().when().then()`) y `@InjectMock` para servicios dependientes.

### FR-007: Dockerfile y Despliegue Containerizado
- Actualizar los manifiestos de Docker para generar imágenes multi-stage compatibles con Quarkus Fast-jar (`quarkus-app/quarkus-run.jar`) sobre Eclipse Temurin 21.

### FR-008: Experiencia de Usuario (UI) Adaptada
- Actualizar etiquetas, guías y vistas del Frontend (`RequirementsView`, `ArchitectureView`, `CodeExplorerView`, `DevOpsDeploymentView`, `StudioOverviewView`) sustituyendo referencias de Spring Boot por Quarkus 3.x.

---

## 3. Historias de Usuario

### Historia de Usuario 1: Inicio en Lienzo Limpio y Configuración de IA (Prioridad: P1)
- **Como** ingeniero de software,
- **quiero** acceder a la plataforma y encontrar un espacio de trabajo limpio sin datos predeterminados,
- **para** iniciar la definición de un microservicio desde cero sin datos ficticios heredados.
- **Criterios de Aceptación:**
  * **Dado** que un usuario abre la aplicación por primera vez o inicia una sesión nueva,
  * **Cuando** carga la vista principal,
  * **Entonces** la plataforma muestra un estado vacío invitando a escribir requerimientos o configurar el proveedor de IA.

### Historia de Usuario 2: Requerimientos e Historias BDD en Español (Prioridad: P1)
- **Como** analista funcional o Product Owner hispanohablante,
- **quiero** ingresar requerimientos en lenguaje natural y recibir historias de usuario y criterios Given/When/Then en español,
- **para** validar de forma inmediata que la IA interpretó adecuadamente las reglas de negocio.
- **Criterios de Aceptación:**
  * **Dado** un texto en lenguaje natural ingresado por el usuario,
  * **Cuando** la IA ejecuta la descomposición de requerimientos,
  * **Entonces** las historias siguen el formato "Como... quiero... para..." y los escenarios BDD "Dado... Cuando... Entonces..." en español.

### Historia de Usuario 3: Generación de Baseline Quarkus 3.x (Prioridad: P1)
- **Como** arquitecto de software,
- **quiero** que el código generado use Java 21 y Quarkus 3.x con Panache y Jakarta REST,
- **para** desplegar un microservicio ultra ligero, nativo para la nube y de arranque instantáneo.
- **Criterios de Aceptación:**
  * **Dado** una especificación validada en Spec-Kit,
  * **Cuando** el pipeline de generación sintetiza los archivos del microservicio,
  * **Entonces** se produce un `pom.xml` con `quarkus-bom`, controladores `@Path`, entidades con Panache y pruebas con `@QuarkusTest`.
