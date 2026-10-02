# Plan de Implementación: Fábrica de Agentes Java Quarkus 3.x ⚡

**Rama**: `001-quarkus-agent-factory` | **Fecha**: 2026-10-01 | **Especificación**: [spec.md](./spec.md) | **Versión**: 3.0.0 | **Iniciativa**: Fábrica de Agentes Java Quarkus

---

## 1. Resumen Ejecutivo

La **Fábrica de Agentes de Microservicios Quarkus** es una plataforma integral orientada a la síntesis autónoma de microservicios empresariales bajo el enfoque **Contract-First Dinámico**, cumpliendo con la [Constitución v3.0.0](../../.specify/memory/constitution.md).

El sistema elimina intermediaciones burocráticas (módulos de preguntas), operando bajo los principios de **Cero Datos Predeterminados (Zero Defaults)**, **Sincronización Reactiva con el Contrato OpenAPI**, **Aprobación de Extensiones Quarkus con Versiones Exactas** y **Bucle de Auto-Corrección (Self-Healing)**.

### Arquitectura de la Plataforma
```
┌────────────────────────────────────────────────────────────────────────┐
│            Frontend React / Vite Studio (Puerto :3000)                 │
│  - Paso 1: Pedido en formulario limpio + Arquetipo (Maven o Gradle)    │
│  - Paso 2 (Control 1): Editor OpenAPI 3.1 reactivo + CRUD HU/Modelo BD │
│  - Paso 3: Selector de Arquitectura + Gestor de Extensiones y Versiones│
│  - Paso 4: Monitor en vivo de Construcción, Pruebas y Self-Healing     │
│  - Paso 5: Visor de Documentación Oficial (README, API doc, ADR-001)   │
│  - Paso 6 (Control 2): Árbol de código Java, Code Review y Auditoría   │
│  - Paso 7: Entrega DevOps: Jenkinsfile, Dockerfile y descarga ZIP      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / REST API (/api/v1/quarkus/*)
┌───────────────────────────────────▼────────────────────────────────────┐
│            Backend Orquestador FastAPI (Puerto :8000)                  │
│  - Máquina de estados: Recibido → Revisión → Aprobado → Generando →    │
│    Probando → En revisión → Entregado                                  │
│  - Agente Analista (síntesis directa OpenAPI 3.1, HUs BDD y Modelo BD) │
│  - Agente Arquitecto (opciones arquitectónicas y catálogo extensiones) │
│  - Scaffolder Dinámico (parseo de schemas a Java 21 Records inmutables)│
│  - Agentes Desarrollador Java & QA (JAX-RS Reactive, Panache, Tests)   │
│  - Agente Revisor (auditoría estática de estándares y buenas prácticas)│
│  - Agente Documentador (README, API doc, ADR-001, guías de operación)  │
│  - Agente DevOps (Jenkinsfile, Dockerfile JVM/Nativo, empaquetado ZIP) │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Contexto Técnico y Stack Tecnológico

* **Runtime de la Plataforma**: Python 3.12 (Backend FastAPI) + Node.js / TypeScript / React 18 (Frontend Vite).
* **Modelos de IA**: Google Gemini 2.5 Flash, Gemini 3.8 Flash, OpenAI GPT-4o, Ollama local.
* **Stack del Microservicio Generado**:
  * **Lenguaje**: Java 21 LTS (Records inmutables, Jakarta Bean Validation).
  * **Framework Base**: Quarkus 3.15+ LTS (`io.quarkus.platform:quarkus-bom:3.15.1`).
  * **Capa Web**: RESTEasy Reactive (`quarkus-resteasy-reactive`, `quarkus-resteasy-reactive-jackson`).
  * **Documentación & Contrato**: SmallRye OpenAPI (`quarkus-smallrye-openapi`) y Swagger UI integrado (`/q/swagger-ui`).
  * **Persistencia**: Hibernate ORM con Panache (`quarkus-hibernate-orm-panache`) y migraciones Flyway (`quarkus-flyway`).
  * **Base de Datos Multi-Perfil**:
    * *Perfil DEV/TEST*: SQLite local portable zero-setup (`quarkus-jdbc-sqlite`).
    * *Perfil PROD*: Microsoft SQL Server (`quarkus-jdbc-mssql`) o PostgreSQL (`quarkus-jdbc-postgresql`).
  * **Seguridad**: SmallRye JWT (`quarkus-smallrye-jwt`) / OAuth2 OIDC.
  * **Observabilidad de Fábrica**:
    * Chequeos de Salud: SmallRye Health (`/q/health/live`, `/q/health/ready`).
    * Métricas Prometheus: Micrometer Prometheus (`/q/metrics`).
    * Trazas Distribuidas: OpenTelemetry (`quarkus-opentelemetry`).
  * **Herramientas de Build**: Maven (`pom.xml`) o Gradle (`build.gradle`) con versiones calibradas.
  * **Pruebas Automatizadas**: `@QuarkusTest`, RestAssured, JUnit 5, Mockito.
  * **CI/CD & Contenedores**: Jenkinsfile corporativo declarativo, Dockerfile multi-etapa (JVM y GraalVM Native).

---

## 3. Validación de Principios Constitucionales (Constitución v3.0.0)

| Principio Constitucional | Requisito Operativo | Estado | Mecanismo de Verificación |
| :--- | :--- | :---: | :--- |
| **I. Recepción Ágil & Arquetipo** | Cero preguntas de aclaración previas; selección Maven/Gradle y validación de calidad. | **CUMPLE** | Formulario limpio; avance directo a contrato OpenAPI sin cuestionarios. |
| **II. Contract-First Dinámico** | La IA adapta la API y modelos a cualquier cambio hecho en el contrato en revisión. | **CUMPLE** | Parser OpenAPI dinámico en Scaffolder y DeveloperQA que genera Java Records y Resources según el YAML. |
| **III. DTOs Inmutables** | Java 21 Records nativos con Jakarta Validation; persistencia Panache encapsulada. | **CUMPLE** | Generación dinámica de `record` para cada schema en `components.schemas`. |
| **IV. Arquitectura & Extensiones** | 3 patrones y catálogo transparente de extensiones Quarkus con versiones aprobables. | **CUMPLE** | Gestor interactivo en Paso 3 donde el usuario aprueba, edita versiones o reemplaza extensiones. |
| **V. Pruebas & Self-Healing** | Pruebas `@QuarkusTest` y detección/auto-corrección de errores de sintaxis y dependencias. | **CUMPLE** | Bucle de auto-corrección verificado en `DeveloperQAService` y registrado en `self_healing_log`. |
| **VI. Dos Controles Humanos** | Control 1 (Contrato/Modelo BD) y Control 2 (Código/Code Review/Tokens). | **CUMPLE** | Compuertas obligatorias de aprobación humana antes de generar código y antes de entregar a DevOps. |
| **VII. Code Review & Docs** | Auditoría estática de calidad y los 5 manuales Markdown obligatorios. | **CUMPLE** | Agente Revisor emite `code_review_report` y Agente Documentador entrega suite completa. |
| **VIII. CI/CD & ZIP** | Cero secretos en repo; Dockerfile multi-stage, Jenkinsfile y exportación ZIP. | **CUMPLE** | Empaquetado en memoria descargable listo para compilar con `./mvnw quarkus:dev`. |

---

## 4. Fases de Ejecución del Proyecto

1. **Fase 1: Eliminación de Módulo de Preguntas y Flujo Ágil Directo**
   * Remoción de endpoints, modelos y vistas de aclaración de negocio.
   * Generación inmediata de contrato OpenAPI, HUs BDD y Modelo Relacional al crear pedido.
2. **Fase 2: Motor Contract-First Dinámico y Gestor de Extensiones con Versiones**
   * Parser sintáctico de schemas OpenAPI a Java 21 Records inmutables con Jakarta Validation.
   * Implementación del gestor de extensiones Quarkus 3.x con versiones exactas y capacidad de reemplazo.
3. **Fase 3: Construcción, Pruebas Automatizadas y Bucle Self-Healing**
   * Implementación de endpoints RESTEasy Reactive, servicios y entidades Panache.
   * Ejecución de pruebas `@QuarkusTest` y auto-corrección de discrepancias técnicas.
4. **Fase 4: Code Review, Documentación y Entrega DevOps**
   * Auditoría de calidad de código por el Agente Revisor.
   * Suite documental de 5 manuales y exportación en `.ZIP`.
5. **Fase 5: Medidor Continuo de Tokens, Progreso Porcentual 0-100% y Resiliencia de Construcción**
   * Eliminación de cuotas punitivas o restricciones artificiales ("Modo Medio" -> "Continuo (Sin límite)").
   * Medidor de tokens en vivo por agente y consolidado con bandera de ilimitado.
   * Monitor de progreso de construcción en tiempo real (0% -> 100%) con fases visuales detalladas.
   * Alerta de felicitación y finalización explícita al 100% reteniendo la vista para inspección del usuario.
   * Mapeo de errores y reintentos en pantalla tanto en Fase de Esqueleto (Paso 4) como en Construcción (Paso 5).
