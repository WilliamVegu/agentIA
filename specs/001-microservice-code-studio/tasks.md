# Tareas de Implementación: Fábrica de Agentes Java Quarkus 3.x ⚡

**Característica**: `001-quarkus-agent-factory` | **Iniciativa**: Fábrica de Agentes Java Quarkus | **Versión**: 3.0.0 | **Estado**: Completado y Verificado

---

## Fase 1: Fundamentos y Modelos de Datos (Backend FastAPI)

- [X] **T001**: Definir modelos Pydantic v2 para el Pedido en 5 bloques (`BasicDataBlock`, `BusinessRequirementBlock`, `TechnicalRequirementsBlock`, `AIModeBlock`, `AttachmentsBlock`) en `backend/app/models/quarkus_factory.py`.
- [X] **T002**: Definir la máquina de estados del pedido (`Recibido`, `Contrato en revisión`, `Aprobado`, `Generando`, `Probando`, `En revisión`, `Entregado`) y estructuras de auditoría de tokens (`TokensAudit`).
- [X] **T003**: Configurar base de datos portable con SQLite para soporte zero-setup en demostraciones locales y perfiles corporativos para SQL Server / Azure SQL / PostgreSQL.

---

## Fase 2: Equipo de 7 Agentes Especializados (Backend)

- [X] **T004**: Implementar el **Agente Analista** (`analyst_agent.py`): síntesis directa del contrato **OpenAPI 3.1** completo con schemas RFC 7807 y tags de endpoints, Historias de Usuario BDD y Modelo de Base de Datos.
- [X] **T005**: Implementar el **Agente Arquitecto** (`architect_agent.py`): generación de las 3 opciones de arquitectura (Capas Estándar, Hexagonal, Reactiva), catálogo de extensiones Quarkus y el **Previsualizador interactivo de arquetipos (Maven `pom.xml` vs Gradle `build.gradle`)**.
- [X] **T006**: Implementar el **Esqueleto Automático (Scaffolder)** (`scaffolder_service.py`): generación dinámica de DTOs Java Records inmutables desde OpenAPI, interfaces JAX-RS y observabilidad SmallRye (`/q/health`, `/q/metrics`, OpenTelemetry).
- [X] **T007**: Implementar los **Agentes Desarrollador Java y QA** (`developer_qa_service.py`): entidades Panache derivadas del modelo de base de datos, servicio con reglas de negocio y pruebas automatizadas `@QuarkusTest` JUnit 5 + RestAssured.
- [X] **T008**: Implementar el **Agente Documentador** (`documenter_devops_service.py`): generación obligatoria de los 5 documentos (`README.md`, `DOCUMENTACION_API.md`, `ADR_001`, `GUIA_PRUEBAS_COBERTURA.md`, `GUIA_OPERACION_SERVICIO.md`).
- [X] **T009**: Implementar el **Agente DevOps** (`documenter_devops_service.py`): generación de `Jenkinsfile` corporativo de 5 etapas, `Dockerfile.jvm` optimizado para Fast-JAR y simulación de Pull Request.
- [X] **T010**: Implementar el **Orquestador Central** (`factory_orchestrator.py`): coordinación de transiciones, persistencia en memoria, auditoría de tokens por agente y empaquetador dinámico en archivo `.ZIP`.

---

## Fase 3: Endpoints REST & Suite de Pruebas Backend

- [X] **T011**: Implementar router REST en `backend/app/api/routes_quarkus_factory.py` y registrar en `backend/app/main.py`.
- [X] **T012**: Desarrollar suite de pruebas automatizadas E2E en `backend/tests/test_quarkus_factory.py` cubriendo el ciclo completo optimizado, las 2 compuertas de control humano y la descarga del ZIP.
- [X] **T013**: Ejecutar y validar con `pytest` logrando 100% de tasa de aprobación.

---

## Fase 4: Frontend React - Flujo Limpio de 7 Pasos & 2 Controles Humanos

- [X] **T014**: Definir interfaces TypeScript en `frontend/src/types/quarkusFactory.ts` (incluyendo `QuarkusExtensionItem`) y servicio Axios en `frontend/src/services/quarkusFactoryService.ts`.
- [X] **T015**: Crear el contexto global `QuarkusContext.tsx` con manejo reactivo de pedidos, estado de pasos y compuertas de aprobación sin intermediación de preguntas.
- [X] **T016**: Implementar `QuarkusStepperNav.tsx`: barra de progreso de los 7 pasos limpios, badges de Control Humano y medidor transversal de tokens.
- [X] **T017**: Implementar `Step1OrderInput.tsx`: formulario en bloques con Java 21, selector de herramienta de build (Maven o Gradle) y validación reactiva.
- [X] **T018**: Implementar `Step3ContractControl1.tsx` (**Control Humano 1**): visor y editor YAML del contrato OpenAPI con interpretación dinámica en tiempo real y botón de congelamiento formal.
- [X] **T019**: Implementar `Step4ArchitectureArchetype.tsx`: selector de arquitectura, **Gestor y Aprobador de Extensiones Quarkus con Versiones Exactas** y **Previsualizador interactivo Maven vs Gradle**.
- [X] **T020**: Implementar `Step5ConstructionTracking.tsx`: monitor en tiempo real del avance, ejecución de pruebas `@QuarkusTest` y widget de auto-corrección (Self-Healing).
- [X] **T021**: Implementar `Step6Documentation.tsx`: visor con pestañas para los 5 documentos generados en Markdown.
- [X] **T022**: Implementar `Step7RevisionControl2.tsx` (**Control Humano 2**): reporte de Code Review, explorador de código Java, auditoría de tokens y formulario de aprobación final.
- [X] **T023**: Implementar `Step8DevOpsDelivery.tsx`: visor de `Jenkinsfile`, `Dockerfile`, Pull Request y botón de descarga directa de microservicio en `.ZIP`.
- [X] **T024**: Integrar vistas y compilar exitosamente con `npm run build` (100% libre de errores TypeScript).

---

## Fase 5: Eliminación de Módulo de Preguntas y Contract-Driven Dinámico

- [X] **T025**: **Eliminación Total del Módulo de Preguntas / Aclaración**: Eliminación de `Step2Clarifications.tsx` y retiro de `submit_clarifications` del flujo obligatorio.
- [X] **T026**: **Síntesis Directa de Contrato**: La creación de pedido genera de inmediato OpenAPI 3.1, Historias BDD y Modelo Relacional, pasando a estado `Contrato en revisión`.
- [X] **T027**: **Motor Contract-First Dinámico**: `ScaffolderService` y `DeveloperQAService` parsean dinámicamente el contrato OpenAPI modificado por el usuario, generando DTOs Java 21 Records inmutables y recursos JAX-RS correspondientes a los endpoints reales.
- [X] **T028**: **Gestor y Aprobador de Extensiones Quarkus y sus Versiones**: Implementación en backend y frontend de la lista transparente de dependencias Quarkus 3.x con versiones fijas, permitiendo al usuario aprobar, editar versión o reemplazar extensiones antes de generar código.
- [X] **T029**: **Bucle de Auto-Corrección (Self-Healing) y Code Review**: Integración en backend de comprobaciones de sintaxis y scopes CDI, y panel de Code Review en frontend.
- [X] **T030**: **Sincronización Total con SDD y Constitución v3.0.0**: Actualización de `constitution.md`, `spec.md`, `plan.md`, `tasks.md`, `data-model.md` y `README.md`.

---

## Fase 6: Medidor Continuo de Tokens, Progreso 0-100% y Resiliencia en Construcción

- [X] **T031**: **Medidor Continuo de Tokens No Restrictivo**: Migración de topes rígidos ("Modo Medio") a "Continuo (Sin límite)" en backend (`AIModeEnum.CONTINUO`, `TokensAudit.is_unlimited`) y frontend (`QuarkusStepperNav.tsx`, `Step1OrderInput.tsx`, `Step5ConstructionTracking.tsx`), permitiendo generación continua y visualización por agente sin cortes.
- [X] **T032**: **Monitor de Progreso 0-100% y Alerta de Finalización**: Implementación de barra de porcentaje en tiempo real vinculada a los hitos de construcción (DTOs, Panache, JAX-RS, Tests, Self-Healing) y banner de celebración al 100% con retención de vista en `QuarkusContext.tsx` y `Step5ConstructionTracking.tsx`.
- [X] **T033**: **Mapeo de Errores y Resiliencia en UI**: Detección y despliegue transparente de fallos y timeouts en Pasos 4 y 5 con botón de reintento, eliminando cargas silenciosas infinitas.
