# Fábrica de Agentes · Agente Java Developer de Microservicios Quarkus ⚡

> **Plataforma Web para la Generación Autónoma y Verificación de Microservicios Quarkus 3.x / Java 21 LTS**  
> *Enfoque Contract-First Dinámico · Metodología SDD (Spec-Driven Development) · Constitución v3.0.0*

La **Fábrica de Agentes Quarkus** es una plataforma orientada a la síntesis autónoma de microservicios empresariales bajo un enfoque **Contract-First Dinámico y Reactivo**. Combina un equipo de agentes especializados de IA con herramientas automáticas y deterministas, eliminando cuestionarios burocráticos y permitiendo que cada modificación hecha al contrato OpenAPI en la revisión dirija dinámicamente la generación de APIs, DTOs inmutables (Java 21 Records), modelos relacionales y pruebas.

---

## 🏛️ Arquitectura del Sistema

```
┌────────────────────────────────────────────────────────────────────────┐
│            Frontend React / Vite Studio (Puerto :3000)                 │
│  - Paso 1: Pedido sin datos precargados + Arquetipo (Maven vs Gradle)  │
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
│  - 🧠 1. Requirements Agent (especificaciones técnicas y HUs BDD)      │
│  - 🏗️ 2. Architecture Agent (OpenAPI 3.1, arquetipo y extensiones)      │
│  - 💻 3. Java/Quarkus Coding Agent (JAX-RS Reactive, DTOs Java 21)     │
│  - 🗄️ 4. Database Agent (Modelo ER, DDL SQL, Panache y migraciones)    │
│  - 🔐 5. Security Agent (SmallRye JWT/OIDC, RBAC y secretos)           │
│  - 🧪 6. Testing & Debug Agent (JUnit 5, RestAssured, Self-Healing)    │
│  - 🔎 7. Code Review Agent (Auditoría estática, SOLID, OWASP y score) │
│  - 🚀 8. DevOps Agent (pom.xml/gradle, Docker, K8s, CI/CD y docs)      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🤖 El Equipo de 8 Agentes Especializados (Ciclo Autónomo)

El ciclo técnico opera de forma continua y automatizada:  
$$\text{Requisito} \rightarrow \text{Diseño} \rightarrow \text{Código} \rightarrow \text{Compilación} \rightarrow \text{Tests} \rightarrow \text{Corrección (Self-Healing)} \rightarrow \text{Code Review} \rightarrow \text{Proyecto Listo}$$

| # | Agente | Rol Técnico | Entregables Clave |
|---|---|---|---|
| **1** | 🧠 **Requirements Agent** | Analiza requisitos y los convierte en especificaciones técnicas. | Historias de usuario BDD, casos de uso, restricciones y glosario. |
| **2** | 🏗️ **Architecture Agent** | Diseña microservicios, capas, patrones, OpenAPI y arquitectura. | Contrato OpenAPI 3.1 YAML, matriz de extensiones Quarkus 3.15 LTS, patrón arquitectónico. |
| **3** | 💻 **Java/Quarkus Coding Agent** | Genera y modifica código Java 21 + Quarkus. | DTOs Java 21 Records inmutables, recursos JAX-RS / RESTEasy Reactive, servicios `@ApplicationScoped`. |
| **4** | 🗄️ **Database Agent** | Modelos, SQL, repositorios, migraciones y conexiones DB. | Modelo Relacional, Diagrama ER Mermaid, DDL `schema.sql`, entidades Panache. |
| **5** | 🔐 **Security Agent** | JWT, OAuth2, hashing, cifrado y configuraciones seguras. | SmallRye JWT / OIDC, RBAC `@RolesAllowed`, gobernanza de variables de entorno. |
| **6** | 🧪 **Testing & Debug Agent** | JUnit, Mockito, integración, ejecución de tests y self-healing. | Suites `@QuarkusTest`, tests RestAssured, ejecutor sandbox y bucle de auto-corrección. |
| **7** | 🔎 **Code Review Agent** | Revisa calidad, SOLID, patrones y vulnerabilidades. | Auditoría estática, verificación anti-patrones Quarkus, reporte de calidad y puntuación. |
| **8** | 🚀 **DevOps Agent** | Maven/Gradle, Git, Docker, Kubernetes y Jenkins/CI-CD. | `pom.xml` / `build.gradle`, `Dockerfile` JVM y Native, manifiestos K8s, `Jenkinsfile` y `README.md`. |

---

## 📜 Cumplimiento Constitucional (Constitución v3.0.0)

1. **Principio I: Recepción Ágil de Requisitos & Arquetipo (Maven o Gradle)**: Formulario limpio sin precargas fijas, validación técnica en tiempo real y **cero cuestionarios de preguntas que retrasen el flujo**.
2. **Principio II: Contrato OpenAPI Dinámico y Revisión Viva**: La IA parsea dinámicamente cualquier cambio que el usuario haga en el contrato OpenAPI durante la revisión; el contrato congelado es la única fuente de verdad para la API.
3. **Principio III: Contratos Inmutables con Java 21 Records**: DTOs inmutables con validación Jakarta Bean Validation (`@NotNull`, `@NotBlank`, `@Size`, etc.). Entidades de persistencia Panache desacopladas de la API.
4. **Principio IV: Arquitectura Seleccionable & Aprobación de Extensiones con Versiones**: 3 patrones (Capas, Hexagonal o Reactiva) y catálogo transparente de extensiones Quarkus 3.x con versiones exactas para aprobar, modificar o reemplazar antes de generar código.
5. **Principio V: Construcción, Pruebas y Bucle Self-Healing**: Suite `@QuarkusTest` con RestAssured y Mockito. Detección y auto-corrección automática de errores de sintaxis y dependencias.
6. **Principio VI: Dos Compuertas de Control Humano**:
   - *Control 1*: Revisión, edición reactiva y congelamiento del contrato OpenAPI y modelo de datos.
   - *Control 2*: Inspección de código Java, reporte de Code Review, pruebas y auditoría de tokens antes de autorizar la entrega.
7. **Principio VII: Seguridad y CI/CD**: Cero credenciales persistidas; `Dockerfile` multi-etapa (JVM y GraalVM Native), `Jenkinsfile` declarativo y descarga directa en `.ZIP`.

---

## 🚀 Requisitos Previos

- **Python**: 3.11 o 3.12 (`python --version`)
- **Node.js**: 20+ y npm (`npm --version`)
- **Java** (opcional, para compilar el proyecto exportado): Java 21 LTS (`java -version`)

---

## 📦 Puesta en Marcha Rápida (1 Clic)

Puedes iniciar ambos servicios simultáneamente ejecutando:

```cmd
run_all.bat
```

O arrancar cada componente de forma individual:

### 1. Iniciar el Backend (FastAPI :8000)
```bash
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
```
*Documentación interactiva Swagger UI disponible en:* `http://localhost:8000/docs`

### 2. Iniciar el Frontend (React + Vite :3000)
```bash
cd frontend
npm run dev
```
*Interfaz de usuario disponible en:* `http://localhost:3000`

---

## 🧪 Ejecución de la Suite de Pruebas Automatizadas

El backend incluye pruebas automatizadas con un 100% de tasa de aprobación:

```bash
# Ejecutar todas las pruebas con pytest
python -m pytest backend/tests/test_quarkus_factory.py -o pythonpath=backend
```

---

## 🖥️ Flujo de Trabajo en la Interfaz Web (7 Pasos)

La interfaz web organiza el ciclo de vida del microservicio en 7 etapas claras y sin fricción:

1. **📝 Paso 1 - Pedido & Arquetipo (Maven o Gradle)**:
   - Datos básicos (Nombre kebab-case, equipo, groupId, versión de Java 21 LTS y build tool).
   - Requerimientos funcionales de negocio (mínimo 30 caracteres con validador en tiempo real).
   - Requisitos técnicos (SQLite demo local vs SQL Server / PostgreSQL, JWT, Kafka).
2. **🔒 Paso 2 - Control Humano 1: Contrato OpenAPI & Revisión Dinámica**:
   - La IA genera directamente el contrato OpenAPI 3.1, Historias de Usuario BDD y Modelo Relacional sin cuestionarios.
   - Visor y editor interactivo YAML: **cada cambio que haces en el contrato es interpretado en tiempo real por la IA**.
   - Congelamiento formal del contrato y modelo de datos.
3. **🏛️ Paso 3 - Arquitectura & Aprobación/Reemplazo de Extensiones**:
   - Selección entre las 3 opciones de arquitectura (Capas Estándar, Hexagonal o Reactiva).
   - **Gestor de Extensiones Quarkus 3.x**: Tabla explícita de artefactos y versiones exactas con casillas de verificación, edición de versiones y opción de añadir extensiones personalizadas.
   - **Previsualizador interactivo Maven vs Gradle**: Comparativa de `pom.xml` vs `build.gradle`, dependencias y árbol de carpetas.
4. **⚙️ Paso 4 - Construcción de Código, APIs, Modelos y Pruebas**:
   - Generación dinámica de DTOs Java 21 Records inmutables a partir de los esquemas OpenAPI revisados.
   - Recursos JAX-RS / RESTEasy Reactive, servicios de negocio y entidades Panache ORM con scripts Flyway.
   - Ejecución de pruebas `@QuarkusTest` JUnit 5 con RestAssured.
   - **Bucle Self-Healing**: Detección y auto-corrección de errores de sintaxis y dependencias.
5. **📚 Paso 5 - Documentación Oficial**:
   - Visualización de los 5 documentos generados (`README.md`, `DOCUMENTACION_API.md`, `ADR_001`, `GUIA_PRUEBAS_COBERTURA.md`, `GUIA_OPERACION_SERVICIO.md`).
6. **🔍 Paso 6 - Control Humano 2: Revisión Final de Entrega & Code Review**:
   - Informe de auditoría de calidad de código (**Code Review**) emitido por el Agente Revisor.
   - Inspección del árbol de código Java, pruebas y tabla de auditoría de tokens consumidos.
7. **🚀 Paso 7 - Entrega DevOps & Descarga ZIP**:
   - Inspección de `Jenkinsfile`, `Dockerfile` y botón de descarga directa del microservicio en archivo **.ZIP** listo para ejecutar con `./mvnw quarkus:dev`.

---

## 📁 Estructura del Repositorio

```text
agentIA/
├── backend/app/
│   ├── models/quarkus_factory.py        # Modelos Pydantic del Pedido, Extensiones y Tokens
│   ├── services/quarkus_factory/        # Los Agentes especializados de Quarkus
│   └── api/routes_quarkus_factory.py    # Endpoints REST de la Fábrica
├── frontend/src/
│   ├── types/quarkusFactory.ts          # Interfaces TypeScript (QuarkusExtensionItem, etc.)
│   ├── services/quarkusFactoryService.ts# Cliente HTTP Axios
│   ├── context/QuarkusContext.tsx       # Estado global y controles humanos
│   └── views/quarkus/                   # Componentes de los 7 pasos
├── specs/001-microservice-code-studio/  # Documentación formal SDD en español
│   ├── spec.md                          # Especificación funcional detallada v3.0.0
│   ├── plan.md                          # Plan de arquitectura e implementación v3.0.0
│   ├── tasks.md                         # Tareas ordenadas y completadas v3.0.0
│   ├── data-model.md                    # Modelo de datos y esquemas v3.0.0
│   ├── research.md                      # Decisiones técnicas y herramientas
│   └── quickstart.md                    # Guía paso a paso para la demo
├── .specify/memory/constitution.md      # Constitución v3.0.0 en español
├── run_all.bat                          # Lanzador 1-clic para Windows
├── run_backend.bat                      # Lanzador backend FastAPI
└── run_frontend.bat                     # Lanzador frontend React Vite
```
