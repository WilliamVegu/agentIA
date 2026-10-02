<!--
INFORME DE IMPACTO DE SINCRONIZACIÓN CONSTITUCIONAL
===================================================
- Versión: 3.0.0 (MAJOR: Eliminación total del módulo de preguntas/aclaración, adopción de Enfoque Contract-Driven Reactivo Dinámico, Aprobación previa de Extensiones Quarkus 3.x con Versiones Exactas, y Bucle de Auto-Corrección Self-Healing)
- Principios Rectores:
  * I. Recepción Ágil de Requisitos de Negocio & Arquetipo (Maven o Gradle, Java 21 LTS sin cuestionarios)
  * II. Contrato OpenAPI Dinámico y Revisión Viva (La IA interpreta cada cambio del contrato en tiempo real)
  * III. Contratos Inmutables con Java 21 Records y Desacoplamiento de Persistencia
  * IV. Arquitectura Seleccionable & Aprobación/Reemplazo de Extensiones Quarkus con Versiones
  * V. Generación de Código, Pruebas Automatizadas y Bucle de Auto-Corrección (Self-Healing)
  * VI. Las Dos Compuertas de Control Humano Obligatorias (Control 1: Contrato/BD; Control 2: Revisión de Código)
  * VII. Code Review Automatizado y Suite Documental Completa
  * VIII. Seguridad de Secretos, Observabilidad de Fábrica y CI/CD Corporativo (Dockerfile, Jenkinsfile, ZIP)
- Stack Base: Java 21 LTS, Quarkus 3.15+ LTS, SmallRye, SQLite dev / SQL Server & PostgreSQL prod, Maven y Gradle.
-->

# Constitución de la Fábrica de Agentes de Microservicios Quarkus 3.x

Esta Constitución establece los principios de diseño, límites operativos, compuertas de control humano y directrices arquitectónicas inmutables para la **Fábrica de Agentes de Software Quarkus**. Todo microservicio generado autónomamente DEBE obedecer estrictamente este marco normativo.

---

## Principios Fundamentales (Core Principles)

### I. Recepción Ágil de Requisitos y Selección de Arquetipo
El diseño y generación de microservicios DEBE iniciar directamente desde los requerimientos funcionales del negocio:
- **Cero Módulos de Preguntas Inútiles**: Queda formalmente ELIMINADO cualquier módulo de preguntas de aclaración o cuestionarios previos que retrasen o bloqueen el flujo de trabajo. La IA procesa directamente los requerimientos del usuario para sintetizar el contrato.
- **Cero Datos Predeterminados (Zero Defaults)**: Queda estrictamente PROHIBIDO precargar nombres de servicio fijos, pedidos predeterminados o catálogos estáticos en formularios.
- **Validador de Calidad del Pedido**: Exige nombre técnico kebab-case, equipo propietario, groupId Java válido, descripción funcional suficiente (mínimo 30 caracteres) y motor de base de datos.
- **Selección de Arquetipo de Construcción**: Soporte nativo para **Apache Maven** (`pom.xml`) y **Gradle** (`build.gradle`), compatibles con Java 21 LTS.

---

### II. Contrato OpenAPI Dinámico y Revisión Viva (Contract-Driven Real)
El contrato OpenAPI 3.1 revisado por el usuario es la **ÚNICA FUENTE DE VERDAD**:
- **Interpretación Reactiva en Tiempo Real**: La IA DEBE parsear e interpretar dinámicamente cualquier modificación, adición o corrección que el usuario realice en el contrato durante la fase de revisión (endpoints, payloads, schemas, tipos y códigos de error).
- **Prohibición de Plantillas Estáticas**: Queda terminantemente PROHIBIDO utilizar clases o esquemas hardcodeados ajenos al contrato editado por el usuario.
- **Sincronización Transversal**: Toda ruta definida en el contrato genera su correspondiente interfaz JAX-RS / RESTEasy Reactive, y todo esquema genera su DTO inmutable.

---

### III. Contratos Inmutables con Java 21 Records y Desacoplamiento Panache
Los contratos de API (DTOs) MUST ser inmutables y estar estrictamente desacoplados de la persistencia:
- Todos los DTOs de Request y Response MUST implementarse mediante **Java 21 Records inmutables**.
- Queda terminantemente PROHIBIDO exponer entidades de persistencia (`PanacheEntity` o entidades JPA) directamente en los endpoints o retornos de la API.
- Todo record de Request MUST incorporar validaciones declarativas tempranas mediante Jakarta Bean Validation (`@NotNull`, `@NotBlank`, `@DecimalMin`, `@Email`, `@Size`, etc.).
- Las entidades de base de datos extienden de `PanacheEntityBase` con identificadores primarios UUID generados automáticamente.

---

### IV. Arquitectura Seleccionable & Aprobación Previa de Extensiones Quarkus
Antes de generar una sola línea de código, la arquitectura y dependencias deben ser transparentes:
- **3 Opciones de Arquitectura**: Capas Estándar (Pragmática), Hexagonal / Ports & Adapters (DDD), o Reactiva (Mutiny + Kafka).
- **Catálogo Explícito de Extensiones Quarkus y sus Versiones**:
  - La IA DEBE listar con total transparencia las extensiones Quarkus 3.x que se utilizarán con sus coordenadas de artefacto, versión exacta (ej. `3.15.1`) y justificación funcional.
  - El usuario cuenta con la potestad de **aprobarlas**, **descartarlas**, **cambiar su versión** o **añadir extensiones adicionales** antes de la construcción del código.

---

### V. Construcción de Código, Pruebas y Bucle de Auto-Corrección (Self-Healing)
La síntesis y validación técnica garantizan robustez antes de cualquier entrega:
- **Generación de APIs, Modelos y Persistencia**: Implementación desacoplada de Resources JAX-RS, Servicios de negocio, Entidades Panache y scripts de migración Flyway (`V1.0.0__init_schema.sql`).
- **Pruebas Automatizadas Integradas**: Generación obligatoria de suite `@QuarkusTest`, pruebas de integración con RestAssured y pruebas unitarias de servicios con Mockito.
- **Bucle de Auto-Corrección (Self-Healing)**: El sistema detecta automáticamente errores de sintaxis, imports faltantes, desajustes de tipos o fallos en aserciones de pruebas, aplicando correcciones automáticas sobre el código generado.

---

### VI. Las Dos Compuertas de Control Humano Obligatorias
El control final reside invariablemente en el operador humano:
- **Control Humano 1 (Revisión y Congelamiento de Contrato OpenAPI y Modelo de BD)**:
  - El usuario inspecciona y edita el YAML de OpenAPI 3.1, las Historias de Usuario BDD y el esquema relacional de tablas/columnas.
  - Al dar el visto bueno, el alcance queda formalmente congelado para la generación determinista.
- **Control Humano 2 (Revisión Final de Entrega y Code Review)**:
  - El usuario audita el árbol de archivos generado, los resultados de pruebas, el informe de Code Review y el consumo de tokens.
  - Concede la autorización final para la exportación y despliegue a Git/DevOps.

---

### VII. Code Review Automatizado y Documentación Oficial
- **Auditoría de Buenas Prácticas**: El Agente Revisor evalúa cumplimiento de principios SOLID, inyección CDI (`@ApplicationScoped`), gobernanza de perfiles y seguridad.
- **Suite Documental de 5 Artefactos**: Todo microservicio incluye `README.md`, `DOCUMENTACION_API.md`, `ADR_001_DECISIONES_ARQUITECTURA.md`, `GUIA_PRUEBAS_COBERTURA.md` y `GUIA_OPERACION_SERVICIO.md`.

---

### VIII. Seguridad de Secretos, Observabilidad y CI/CD
- **Cero Secretos en Repositorio**: Variables de entorno preparadas para Kubernetes y perfiles duales (%dev SQLite portable vs %prod SQL Server / PostgreSQL).
- **Observabilidad Integrada**: SmallRye Health (`/q/health`), Prometheus Metrics (`/q/metrics`) y OpenTelemetry de fábrica.
- **Empaquetado y Despliegue**: Dockerfile multi-etapa (JVM y GraalVM Native), pipeline `Jenkinsfile` y descarga directa del microservicio en paquete `.ZIP` listo para compilar.
