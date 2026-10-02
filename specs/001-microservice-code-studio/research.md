# Investigación y Decisiones Técnicas: Fábrica de Agentes Java Quarkus ⚡

**Característica**: `001-quarkus-agent-factory` | **Fecha**: 2026-10-01 | **Iniciativa**: Pedido 2 de Lorena

---

## 1. Visión General

La **Fábrica de Agentes de Microservicios Quarkus** implementa un modelo de colaboración entre herramientas automáticas deterministas y agentes de IA especializados para generar microservicios Java 21 LTS de nivel producción en Quarkus, bajo un enfoque estricto **Contract-First**.

---

## 2. Decisiones Técnicas Fundamentales

### Decisión 1: Enfoque Contract-First con Quarkus OpenAPI Generator
* **Decisión**: El microservicio no genera endpoints libres a partir de prompts; se redacta y aprueba primero un contrato **OpenAPI 3.1** que luego se congela inmutablemente. Las interfaces JAX-RS y DTOs nacen directamente de dicho contrato.
* **Justificación**: Cumple el requisito de diseño del documento de Lorena: "Nada se construye sin esta aprobación". Evita alucinaciones de nombres de rutas, métodos HTTP o esquemas de payload.
* **Herramientas de Referencia**:
  * *Quarkus OpenAPI Generator*: Generación oficial de interfaces de servidor y modelos desde especificaciones OpenAPI.
  * *SmallRye OpenAPI*: Exposición dinámica de Swagger UI en `/q/swagger-ui`.

---

### Decisión 2: Previsualización y Elección de Arquetipos (Maven vs Gradle)
* **Decisión**: En el Paso 4, el usuario cuenta con un previsualizador interactivo que le permite examinar el `pom.xml` proyectado con el BOM `io.quarkus.platform:quarkus-bom:3.15.1` y sus plugins, o el `build.gradle` equivalente, junto con la estructura de carpetas y comandos de ejecución, antes de generar el esqueleto.
* **Justificación**: Responde a la preferencia explícita del usuario de validar cómo se estructura el proyecto antes de ejecutar la descarga o generación.

---

### Decisión 3: Multi-Perfil de Persistencia (SQLite Portable para Demo vs SQL Server Corporativo)
* **Decisión**: El microservicio generado incluye soporte dual en `application.properties`:
  * `%dev` y `%test`: Base de datos **SQLite local portable (zero-setup)** con dialecto Hibernate comunitario para que el microservicio compile y ejecute sus pruebas unitarias en cualquier máquina de demo sin requerir un servidor SQL Server encendido.
  * `%prod`: Configuración oficial para **Microsoft SQL Server / Azure SQL** mediante `quarkus-jdbc-mssql` con variables de entorno (`DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`).
* **Justificación**: Permite portabilidad absoluta de la demo solicitada por el usuario, manteniendo el cumplimiento del perfil corporativo de SQL Server requerido por Lorena.

---

### Decisión 4: Observabilidad de Fábrica Integrada
* **Decisión**: Todo microservicio generado incluye sin configuración manual:
  1. *SmallRye Health*: Liveness (`/q/health/live`) y Readiness (`/q/health/ready`).
  2. *Micrometer Prometheus*: Métricas en formato scrapeable en `/q/metrics`.
  3. *OpenTelemetry*: Trazas distribuidas con inyección automática de span y traceId.
  4. *Logging JSON*: Formato estructurado JSON para producción.
* **Justificación**: Estándar ineludible de microservicios nativos para despliegue en Kubernetes o Azure Container Apps.

---

### Decisión 5: División en 7 Agentes de IA Especializados
* **Decisión**: En lugar de un agente monolítico, la síntesis se divide en 7 roles:
  1. *Analista*: Aclaración previa (3-5 preguntas) y síntesis OpenAPI 3.1.
  2. *Arquitecto*: Evaluación de patrones (Capas, Hexagonal, Reactiva) y extensiones Quarkus.
  3. *Desarrollador Java*: Lógica de negocio y entidades Panache con principios SOLID.
  4. *QA*: Pruebas unitarias `@QuarkusTest`, RestAssured y Mockito.
  5. *Documentador*: Generación de README, API docs, ADR-001 y guías operativas.
  6. *Revisor*: Auditoría estática en Modo Alto.
  7. *DevOps*: Jenkinsfile corporativo, Dockerfile y simulación de Pull Request.
* **Justificación**: Aísla el contexto por tarea, reduce drásticamente las alucinaciones y permite una auditoría granular del consumo de tokens por especialidad.
