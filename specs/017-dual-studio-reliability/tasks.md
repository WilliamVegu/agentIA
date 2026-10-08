# Tareas: fiabilidad de los dos estudios

**Entrada:** [plan](plan.md), [spec](spec.md), [modelo](data-model.md), [decisiones](research.md), [API](contracts/api.md) y [matriz](contracts/regression-matrix.md).  
**Estado:** implementación en curso; casillas marcadas sólo con evidencia. Registro de validación en integration/validation/reliability/. Rama `dual-systems-selector`, base `cd50688c8188b47ba789ec30683a50eabc7bd593`.

Rutas relativas a `C:/Users/willi/Downloads/agentIA`. «Nuevo» significa archivo por crear; las modificaciones espejo preservan la independencia de los estudios. [P] permite concurrencia sólo después de los prerrequisitos indicados y sin editar archivos compartidos. Cada prueba de defecto se escribe primero y debe demostrar el fallo previo; no ejecutar operaciones contra datos de usuario. Los detalles de campos/estados de data-model.md y API son parte obligatoria de cada tarea asociada.

## Fase 1 — Preparación (T001–T004)

Objetivo: base reproducible y fixtures aisladas; no corregir fuentes aún.

- [X] T001 Capturar commit, cambios locales, hashes, versiones y conteos del análisis en `integration/validation/reliability/baseline.json` (nuevo), sin secretos; preservar `integration/source-snapshots.json` y distinguir evidencia nueva de histórica.
- [X] T002 Resolver requirements/constraints en dos venv de prueba separados sin sustituir `.venv`, comprobar pip/Python/Node y locks, registrar resolución compatible por plataforma en `integration/validation/reliability/environment.json` (nuevo); usar `backend/requirements.txt`, `systems/quarkus/backend/requirements.txt` e `integration/constraints.txt` como entrada.
- [X] T003 [P] Reproducir/clasificar MAX_PATH, divergencia OpenAPI y fixture DOCKER de los tres fallos Spring, conservando los gates; documentar causas y resultados en `integration/validation/reliability/baseline-failures.md` (nuevo), con referencias a tests concretos encontrados al reproducir.
- [X] T004 [P] Crear fixtures de draft LedgerEntry/UUID/fechas/decimal/reglas y harness de SQLite/workspace/Git/Docker propios en `integration/reliability_fixtures.py` (nuevo); rechazar rutas originales, etiquetar recursos y bloquear llamadas IA, preparar fixtures legacy/corruptas y restaurar configuración al salir.

Puerta: T003 y T004 pueden hacerse en paralelo después de T001/T002. Diagnósticos ambientales visibles; ningún coste IA.

## Fase 2 — Fundamentos (T005–T008)

Objetivo: modelo aditivo y contrato base; bloquea historias hasta superar migraciones en copia.

- [X] T005 Definir modelos persistidos/repuestas de `data-model.md` en `backend/app/models/session.py`, `backend/app/models/execution.py` y equivalentes Quarkus (`execution.py` nuevo allí): DraftRevision, configuración, operaciones, evidence/audit/repair/events y SchemaMigration; conservar columnas legacy. Imponer «contenido inmutable», «databaseEngine H2/POSTGRESQL/MYSQL», «puerto 1024–65535», «credenciales nunca persistidas» y enums exactos del diseño.
- [X] T006 [P] Crear migración versionada/idempotente/observable en `backend/app/services/session_schema_migrations.py` y `systems/quarkus/backend/app/services/session_schema_migrations.py` (nuevos), integrar startup en ambos `backend/app/main.py` y retirar mutaciones de esquema silenciosas por import en ambos `models/session.py`; backup primero, checksum registrado, rollback transaccional y ninguna adopción de runtime sin propiedad.
- [X] T007 [P] Crear proyección/errores canónicos y saneamiento recursivo en `backend/app/services/session_projection.py`, `backend/app/services/secret_redaction.py` y sus equivalentes Quarkus (nuevos); aplicar API 400/403/404/409/422, cero/null reales, alias compatibles, conflicto 422 y exclusión de secretos. Trabajar tras T005 y coordinar cambios fuera de estos archivos con T006.
- [X] T008 Probar nueva DB y legacy, segunda migración, interrupción/fallo, evidencia incompleta, FAILED previo y reversión aditiva en `backend/tests/test_session_schema_migrations.py` y `systems/quarkus/backend/tests/test_session_schema_migrations.py` (nuevos); verificar «error detiene mutaciones dependientes», no perder fuentes/registros ni fabricar PASSED.

Puerta: contrato base compatible y migración conservadora sobre copia. T006/T007 sólo concurrentes en los módulos distintos especificados.

## Fase 3 — US1: archivos, datos y Git seguros — P1 (8 tareas)

**Prueba independiente:** rutas maliciosas no alcanzan sentinel externo; stop/restart conserva un registro; push divergente conserva historia y ningún PAT se encuentra en disco/logs.

- [X] T009 [P] [US1] Añadir casos 404/paths absolutos/UNC/cross-drive/ADS/traversal/symlink-junction/preview sin sesión/escritura fallida en `backend/tests/test_workspace_boundary.py` y `systems/quarkus/backend/tests/test_workspace_boundary.py` (nuevos); usar sentinelas propios fuera del workspace fixture y demostrar cero modificación/lectura externa.
- [X] T010 [P] [US1] Añadir pruebas Git bare divergente/token centinela/error/crash y Docker stop/cleanup con propietario ajeno en ambos `backend/tests/test_git_service.py` y nuevos `backend/tests/test_runtime_data_safety.py` (también bajo `systems/quarkus/`); tests reales de volumen se ejecutan sólo tras T014, con recursos T004.
- [X] T011 [P] [US1] Endurecer `backend/app/services/workspace_guard.py`: resolver por sesión, validar canonical path y enlaces, limitar archivos mutables, escritura atómica, error visible; usar paths internos extendidos para I/O Windows profundo sin admitir rutas absolutas suministradas por usuario.
- [X] T012 [P] [US1] Crear `systems/quarkus/backend/app/services/workspace_guard.py` con la misma frontera y pruebas espejo, sin copiar dependencias Spring; sesión inexistente primero 404, ruta peligrosa 400/422, locks y errores de escritura explícitos.
- [X] T013 [US1] Integrar guardas en lectura/escritura de código, reparación, remediación, ZIP y publicación: ambos `backend/app/api/routes_tests.py`, `routes_security.py`, `routes_artifact.py`, `routes_publish.py` y servicios llamados; eliminar búsqueda global cuando falta sesión y permitir preview sólo sobre sourceCode recibido.
- [X] T014 [US1] Separar stop/restart conservadores de cleanup/deleteData explícito en `backend/app/services/runtime_lifecycle.py`, `backend/app/services/local_operations.py`, `backend/app/api/routes_devops.py` y Quarkus `services/devops_service.py`, `services/docker_service.py`, `api/routes_devops.py`; quitar `down -v` de stop, verificar propiedad/resultado y no declarar STOPPED ante error. Crear servicios nativos Quarkus necesarios según US5, sin health inferido por puerto.
- [X] T015 [US1] Endurecer ambos `backend/app/services/git_service.py` y `api/routes_publish.py`: URL limpia, protocolo/branch validados, cabecera host-scoped sólo en entorno del subprocess, helpers desactivados cuando proceda, saneamiento, sin force ni fallback que resetee historia; mantener origin previo y devolver divergencia 409, sin PAT en argv/config/temporales.
- [X] T016 [US1] Implementar preview/confirmación de cleanup sobre identidades vigentes y errores de stop/Git en ambos `frontend/src/services/devopsService.ts`, `views/DevOpsDeploymentView.tsx`, `services/exportService.ts`, `views/ExportPublishView.tsx`; ejecutar T009/T010 y demostrar conservación de registro PostgreSQL/MySQL y recursos ajenos.

Puerta/MVP: H01/H06/H07 cerrados. Las operaciones destructivas de pruebas sólo afectan recursos propios.

## Fase 4 — US2: autoridad del draft — P1 (6 tareas)

**Prueba independiente:** LedgerEntry, UUID, reglas, paquete y puerto 18088 se conservan después de save/approve/restart/Auto-Pilot; revisión concurrente no sobrescribe al worker.

- [X] T017 [P] [US2] Crear regresión save/get/approve/restart/Auto-Pilot personalizada y legacy inválido en `backend/tests/test_draft_authority.py` y `systems/quarkus/backend/tests/test_draft_authority.py` (nuevos); exigir campos completos y ausencia de Order/Pedido sustitutos.
- [X] T018 [P] [US2] Probar revisión concurrente, aprobación no heredada, fingerprint y descendientes OUTDATED en ambos `backend/tests/test_artifact_revision.py` (nuevos); worker ligado a revisión original o conflicto 409, jamás mezcla de inputs.
- [X] T019 [US2] Crear `backend/app/services/draft_revision_service.py` y equivalente Quarkus (nuevos), integrar ambos `models/blueprint.py`: guardar JSON completo/hash/origen/aprobación y configuración, con «sessionId existente», «contenido inmutable» y «defaults explícitos al crear, no al recuperar»; validar versiones y NEEDS_REVIEW legacy sin reconstrucción inventada.
- [X] T020 [US2] Actualizar ambos `backend/app/api/routes_requirements.py` y `services/requirements_service.py` para GET/SAVE/APPROVE sobre revisión exacta, expectedRevisionId/version y alias; recuperar packageName/basePort originales y separar aprobación humana del simple guardado/generación automática.
- [X] T021 [US2] Corregir `_get_or_create_draft` y captura de inputs en ambos `backend/app/services/pipeline_runner.py` y `models/orchestrator.py`; revisión estructurada válida manda sobre Markdown/mock, regeneración desde texto sólo cuando no hay revisión utilizable y con origen registrado, sin aprobación ficticia.
- [X] T022 [US2] Registrar procedencia/invalidez de fases en ambos `backend/app/services/draft_revision_service.py`, `pipeline_runner.py` y orquestación por etapas; actualizar ambos `frontend/src/services/requirementsService.ts` y `views/RequirementsView.tsx` con revisión/approve/conflicto. Exigir «estado CURRENT/OUTDATED» y pruebas T017/T018.

Puerta: H02 cerrado; arquitectura/SQL/Java/tests/DevOps trazan revisión e inputs. Proyectos existentes se regeneran sólo por acción explícita con backup.

## Fase 5 — US3: estados, evidencia y reparación — P1 (8 tareas)

**Prueba independiente:** cero tests/fallback no aprueban; SOURCE_ONLY conserva FAILED previo; targets/pausa/cancelación/reparación reportan estados persistidos coherentes.

- [X] T023 [P] [US3] Crear tabla de pruebas de transiciones/target/pausa/cancel/CAS/checkpoint/reinicio/callback obsoleto en ambos `backend/tests/test_operation_state_machine.py` (nuevos), incluyendo terminal 409 y gate persistido antes de evento.
- [X] T024 [P] [US3] Crear regresiones suite vacía/fallback/interrupción/reporte ausente/hash cambiado/auditoría vacía/SOURCE_ONLY/FAILED y reparación hint-only en ambos `backend/tests/test_evidence_policy.py` (nuevos); exportar/publicar/desplegar deben respetar política por tipo de entrega.
- [X] T025 [US3] Implementar repositorio CAS/lease y writer único en `backend/app/services/session_execution.py`, `session_operation_lock.py` y equivalentes Quarkus (nuevos allí); capturar revisión/config/target, verificar operationId/version en cada callback y persistir checkpoints y SessionEvent junto con la transición en una transacción, antes de notificar. Cumplir «una operación escritora activa por sesión», «credenciales nunca persistidas» y estados exactos del modelo.
- [X] T026 [US3] Consolidar verificación en `backend/app/services/verification_policy.py`, `workspace_verification.py`, `source_snapshot.py` y equivalentes Quarkus (nuevos si faltan); criterio «suite >0, passed=total, failed=0, sin fallback/interrupción/error para PASSED», reportes/fingerprint comprobables y vigencia OUTDATED por cambio, conservando outcome/informes históricos inmutables. No exigir BOOT-INF a Quarkus; usar adaptador de US5.
- [X] T027 [US3] Aplicar máquina de estados a ambos `backend/app/services/pipeline_runner.py`, `api/routes_orchestrator.py`, `api/routes_session.py`: respetar targetPhase, PAUSE_REQUESTED→checkpoint→PAUSED, resume con opciones originales, cancel terminal 409 y DB BLOCKED antes de notificar; no completar etapas posteriores al target.
- [X] T028 [US3] Corregir reparación en ambos `backend/app/api/routes_tests.py` y `orchestrator/stages/runner.py`: guardar RepairAttempt, invalidar antes de escribir, guidanceHint canónico/promptHint alias con código, hint-only 422, máximo automático 3 persistido; VERIFIED sólo con evidencia, SOURCE_ONLY APPLIED_UNVERIFIED/diagnosticsResolved=false, errores visibles y bloqueo al agotar intentos.
- [X] T029 [US3] Corregir auditoría/métricas en ambos `backend/app/services/security_service.py`, `orchestrator/stages/compliance.py`, `models/security_quality.py`, `api/routes_security.py` y proyección T007: «sin fuentes => NOT_RUN y score=null», ceros reales y PASS sólo vigente; eliminar cifras 284/12/2.2/100 inventadas, declarar alcance real del scanner.
- [X] T030 [US3] Aplicar una política de entrega a ambos `backend/app/services/export_service.py`, `lifecycle_service.py`, `api/routes_publish.py`, `routes_artifact.py`, `routes_devops.py` y consultas session/overview/repairs: 404 inexistente, fuentes auditadas UNVERIFIED según modo, executable/deploy exige evidencia, mensajes distinguen generación/verificación/despliegue y nunca convierten FAILED en skip.

Puerta: H03/H10/H12/H13 cerrados en backend; frontend pendiente US6. Un estado terminal no implica automáticamente calidad aprobada.

## Fase 6 — US4: Java y SQL fieles — P1 (7 tareas)

**Prueba independiente:** servicios generados rechazan email/importe inválidos con 400 y conservan UUID/fechas/unique/FK en los tres motores.

- [X] T031 [P] [US4] Crear pruebas de descriptor/ID/FQN/fecha/decimal/unique y constraints incompletas/inyección en `backend/tests/test_normalized_domain.py` y `systems/quarkus/backend/tests/test_normalized_domain.py` (nuevos); reglas sin parámetros válidos se diagnostican antes de escribir, sin Java arbitrario.
- [X] T032 [P] [US4] Añadir regresiones de entidad/Record/repositorio/service/controller/tests y BDD pendiente en ambos `backend/tests/test_generated_validation_contract.py` (nuevos); incluir @Email/@Positive, cero, null, UUID con ID personalizado, LocalDate/LocalDateTime/Instant y restricciones únicas.
- [X] T033 [US4] Crear descriptor tipado en ambos `backend/app/services/domain_descriptor.py` (nuevos), actualizar ambos `models/blueprint.py`, `domain_model.py`, `devops.py` y contratos session/create: validar identificadores Java/SQL/paquete y normalizar tipos/estrategia/constraints, preservar isUnique; databaseEngine canónico, database alias y conflicto 422, config persistida sin adivinar SQL.
- [X] T034 [P] [US4] Corregir generación Spring en `backend/app/orchestrator/stages/deterministic/domain.py`, `service.py`, `controller.py`, `test_synthesis.py`, `scaffolder.py`: firmas de ID coherentes (sin Long impuesto), Records con constraints, @Valid y errores nativos; usar T033 como única descripción del dominio.
- [X] T035 [P] [US4] Corregir generación Quarkus en `systems/quarkus/backend/app/orchestrator/stages/deterministic/domain.py`, `service.py`, `controller.py`, `test_synthesis.py`, `scaffolder.py`: fechas Java reales, UUID/custom ID, isUnique, constraints, @Valid, Panache/ExceptionMapper; sin anotaciones/imports Spring.
- [X] T036 [US4] Alinear DDL/seeds/driver/ORM/Compose por motor en ambos `backend/app/services/model_sql_service.py`, `services/devops_service.py` y `orchestrator/stages/deterministic/scaffolder.py`; usar dialectos de `services/domain_descriptor.py`, adaptar helper Quarkus `deterministic/schema.py`. MySQL no usa IDENTITY/TIMESTAMP WITH TIME ZONE incompatibles; UUID físico y Java coinciden; Spring conserva Liquibase y Quarkus inicializa esquema una vez y valida después.
- [ ] T037 [US4] Crear/ejecutar `integration/test_generated_domain.py` (nuevo) con T004: doce combinaciones framework × Maven/Gradle × H2/PostgreSQL/MySQL, suites Java reales y HTTP de CRUD/validación/UUID/fecha/decimal/unique/FK; registrar informes/fingerprints y BDD pendiente, corregir cualquier discrepancia de T034–T036 antes de cerrar.

Puerta: H04/H08/H09/H11 cerrados; no basta comparar strings ni compilar.

## Fase 7 — US5: despliegue nativo y observado — P1 (7 tareas)

**Prueba independiente:** servidor ajeno en 8080 no acredita salud; AutoDeploy espera su operación; build/test offline funciona con el artefacto nativo correcto.

- [X] T038 [P] [US5] Añadir tests Maven/Gradle, manifiesto cambiado, cache insuficiente y layouts Spring JAR/Quarkus fast-jar en ambos `backend/tests/test_native_verification.py` (nuevos); ninguna imagen preparada antigua acredita manifests nuevos.
- [X] T039 [P] [US5] Crear escenarios Docker fallido/timeout/puerto ocupado/servicio ajeno/duplicado/legacy-unowned en ambos `backend/tests/test_deployment_identity.py` (nuevos); validar snapshot/image/labels/bindings y resultado real, no simples mocks de health.
- [X] T040 [US5] Separar adaptadores nativos de preparación/verificación/empaquetado en `backend/app/services/platform_verification.py`, `source_snapshot.py`, `sandbox/docker_runner.py`, `sandbox/verify_cache.py` y equivalentes Quarkus (crear servicios que faltan); preparación online explícita, Maven/Gradle offline, red externa bloqueada y reports, ninguna dependencia SPRING_DATASOURCE ni BOOT-INF en Quarkus.
- [X] T041 [US5] Persistir identidad/operación runtime en `backend/app/services/local_runtime.py`, `local_operations.py`, `runtime_lifecycle.py` y equivalentes Quarkus (nuevos si faltan), integrando `services/devops_service.py` y Compose: proyecto único por sesión, labels, imagen, bindings, estado UNKNOWN legacy; health nativo sólo de recursos propios y «HEALTHY requiere propiedad, imagen/fuentes vigentes y health nativo».
- [X] T042 [US5] Hacer que ambos `backend/app/services/pipeline_runner.py` y `api/routes_devops.py` esperen resultado terminal de DeploymentOperation al pedir AutoDeploy; BUILDING no es COMPLETED, error/timeout queda FAILED, infraestructura inaccesible pausa sin reparaciones ni cambio automático de modo.
- [X] T043 [US5] Corregir Dockerfiles/assets y detalle/status en ambos `backend/app/services/devops_service.py`, `api/routes_session.py`, `api/routes_devops.py`: deploy reutiliza artefacto verificado vigente, -DskipTests no constituye evidencia; exponer URL/health/config real y preparación/offline sin probe genérico de 8080 ni ruta Actuator Quarkus.
- [X] T044 [US5] Ejecutar integración runtime con identidad, dos sesiones, colisión, reinicio backend, Docker ausente y conservación DB en `integration/test_native_runtime.py` (nuevo); demostrar T038/T039 sobre Docker propio y adaptar cleanup T014, registrando ausencia de llamadas IA/descargas en fase offline.

Puerta: H05 cerrado y defensas H06 verificadas con operación observada.

## Fase 8 — US6: diez paneles auténticos — P2 (6 tareas)

**Prueba independiente:** sesión vacía, SOURCE_ONLY, FAILED, VERIFIED y HEALTHY muestran datos reales, ceros y acciones coherentes; nunca ejemplos ocultos.

- [X] T045 [P] [US6] Crear regresiones UI de estados/ceros/null/draft/config en ambos `frontend/src/test/reliability_views.test.tsx` (nuevos), cubriendo los diez paneles y aislamiento entre estudios; fixture vacía no permite aprobación ni export verificado.
- [X] T046 [P] [US6] Crear tests de contrato aliases/conflictos/expectedVersion/repair/overview/devops en ambos `frontend/src/test/reliability_services.test.ts` (nuevos); confrontar OpenAPI regenerado en versión fijada y probar guidanceHint/422 sin código.
- [X] T047 [US6] Alinear ambos `frontend/src/types/index.ts` y `services/sessionService.ts`, `orchestratorService.ts`, `requirementsService.ts`, `modelsService.ts`, `testsService.ts`, `devopsService.ts`, `securityService.ts`, `exportService.ts` con API canónica: databaseEngine, operationId/version, evidencia, score nullable y aliases sólo documentados; evitar valores por defecto al recuperar datos.
- [X] T048 [US6] Corregir ambos `frontend/src/views/StudioOverviewView.tsx`, `SecurityQualityView.tsx`, `GenerationMonitorView.tsx`, `components/layout/LifecycleStepper.tsx`: conteos reales, cero/null, sin 4/2/95 ni completed→testsPassed, bloqueo/target/repair-limit=3 y mensajes separados de fuentes/verificación/despliegue.
- [X] T049 [US6] Alinear ambos `frontend/src/views/SpecIngestionView.tsx`, `RequirementsView.tsx`, `ArchitectureView.tsx`, `DomainModelsView.tsx`, `CodeExplorerView.tsx` y `WorkspaceRouter.tsx`: revisión/approve/conflicto, motor real, origen/evidencia y hint con código; samples/mock sólo en diagnóstico explícito, ningún fallback silencioso de producción.
- [X] T050 [US6] Integrar estados asíncronos/gates y cleanup seguro en ambos `frontend/src/views/DevOpsDeploymentView.tsx`, `ExportPublishView.tsx`; probar fuentes auditadas vs entrega verificada, health nativo, URL nullable, error Git y datos conservados; ejecutar T045/T046, Vitest/builds y documentar diez paneles en `integration/validation/reliability/ui.md` (nuevo).

Puerta: H03/H08/H12/H13 cerrados también en UI. Login/selector mantienen acceso e independencia actuales; no ampliar privilegios demo.

## Fase 9 — US7: eventos y recuperación — P2 (4 tareas)

**Prueba independiente:** dos clientes reciben igual secuencia, replay/resync correcto, reinicio deja INTERRUPTED e historia conservada, MLflow ausente sólo degrada telemetría.

- [X] T051 [US7] Crear tests de dos suscriptores, desconexión, consumidor lento, replay/cursor expirado, caída DB/evento y restart sin secretos en ambos `backend/tests/test_session_events.py` (nuevos); agregar espejo frontend en ambos `frontend/src/test/reliability_sse.test.tsx` (nuevos).
- [X] T052 [P] [US7] Implementar persistencia/broadcast/replay acotado en ambos `backend/app/services/session_event_service.py` (nuevos), con «orden por sesión», «sin credenciales/código sensible completo», secuencia, operationId/version, retención configurable, dispatcher con recuperación de eventos persistidos no notificados y resync; sustituir consumo compartido q.get en ambos `api/routes_session.py`, `api/routes_orchestrator.py` y `services/pipeline_runner.py` después de US3.
- [X] T053 [P] [US7] Integrar recuperación de startup/checkpoints/historial y estado de tracing en ambos `backend/app/services/session_execution.py`, `models/session.py`, `main.py`, `cost/mlflow_sink.py`: activos→INTERRUPTED, memoria sólo caché, sin replay automático Docker/Git/IA, costes separados y fallback de telemetría declarado. Coordinar archivos compartidos con T052; módulos centrales se editan secuencialmente.
- [X] T054 [US7] Actualizar ambos `frontend/src/hooks/useSSE.ts`, `services/orchestratorService.ts` y monitor para IDs/deduplicación/replay/resync/cleanup; ejecutar T051 y caída real de backend sobre fixture, verificar historial persistido, eventos y ausencia de claves en `integration/validation/reliability/events.json` (nuevo).

Puerta: O02/O03 cerrados. T052/T053 sólo concurrentes en módulos propios; integración de callbacks/startup se hace secuencialmente.

## Fase 10 — US8: instalación, CI y journeys — P2 (6 tareas)

**Prueba independiente:** instalación desde limpio y CI detectan fallo/zero tests/secretos; journeys completos de ambos estudios no consumen IA y baseline histórico conserva integridad.

- [X] T055 [US8] Añadir regresiones de Python WindowsApps/pip ausente/venv separados/npm faltante/constraints incompatibles a `integration/test_launcher.py`; corregir `integration/launch.py`, `start-dual.ps1`, `start-dual.bat`, constraints/requirements con pins/markers comprobados, locks intactos y preflight accionable sin destruir instalaciones; regenerar/check OpenAPI en el entorno elegido.
- [X] T056 [P] [US8] Crear pruebas de CI generado con secret centinela, SAST conocido, cero suites y fallo de test en ambos `backend/tests/test_generated_ci_policy.py` (nuevos), ejecutando scripts reales en sandbox con repo de prueba; no afirmar éxito por presencia de nombres YAML.
- [X] T057 [US8] Generar CI GitHub/GitLab operativo desde `backend/app/services/local_ci_assets.py`, `devops_service.py` y equivalente Quarkus (`local_ci_assets.py` nuevo si falta), con scanner/secret checks ejecutables, test/reportes y gates; eliminar echo-only SAST/secret, publicar alcance, fijar Trivy action a revisión comprobada y mantener dependencias de verificación preparadas offline.
- [X] T058 [P] [US8] Extender `integration/verify_sources.py` y crear `integration/source-revisions.json` sin reescribir `source-snapshots.json`: cambios autorizados con baseline/hash antes/después/TID/evidencia, rechazar cambios no listados y probar manifest manipulado en `integration/test_source_revisions.py` (nuevo).
- [X] T059 [US8] Corregir tests/fixtures por causas T003, soporte I/O Windows profundo y skip explícito en pruebas implicadas de ambos `backend/tests/`; añadir matriz Windows/Linux reproducible en `.github/workflows/reliability.yml` (nuevo) y pruebas de rutas en `integration/test_windows_paths.py` (nuevo), sin debilitar validación/gates ni actualizar contratos desde entorno distinto.
- [ ] T060 [US8] Crear `integration/reliability_smoke.py` y `integration/test_reliability_journeys.py` (nuevos) con CLI de quickstart, reutilizando T004/T037/T044; cubrir ambos estudios manual/guided/Auto-Pilot, SOURCE_ONLY/DOCKER, DB, target/repair/interrupción/ZIP/Git local y migración. Registrar doce combinaciones Java y paneles; API real opt-in con límite explícito, nunca requerida por CI.

Puerta: H14/O01/O04/O05/O07 cerrados; no declarar matriz verde cuando Docker no estuvo disponible.

## Fase 11 — Cierre transversal (T061–T064)

- [ ] T061 Ejecutar suites Python/launcher/Vitest y builds de ambos estudios, doce combinaciones Java, runtime, journeys y CI adversarial de quickstart; consolidar conteos/resultados/skips en `integration/validation/reliability/RESULTADOS.md` (nuevo) con evidencia vigente y cero errores inesperados.
- [X] T062 Ensayar migración/reversión de código y repetición sobre copias legacy/concurrentes, conservación fuentes/DB/runtime ajeno; documentar backup, recuperación y límites en `docs/dual-studio-reliability-migration.md` (nuevo), incorporando evidencias T008/T060 sin restaurar una DB vieja sobre datos nuevos.
- [ ] T063 Completar cada fila de `specs/017-dual-studio-reliability/contracts/regression-matrix.md` con evidencia real/TID/commit, contrastar FR-01–FR-18 y ambos textos constitucionales; mantener pendiente cualquier capacidad no ejecutada y no fabricar aprobación, revisar manifest T058 y ausencia de secretos.
- [ ] T064 Actualizar `integration/README.md`, `docs/dual-studio-reliability.md` (nuevo), `specs/017-dual-studio-reliability/quickstart.md` y estado final de este tasks.md: instalación/modos/estados/repair=3/DB/stop-cleanup/compatibilidad, pasos comprobados y limitaciones; revisión final de diff sin publicar ni hacer cambios destructivos automáticamente.

## Dependencias y orden

```text
Preparación T001–T004 → Fundamentos T005–T008 → US1
US1 → US2 → US3
US2 + US3 → US4
US1 + US3 + US4 → US5
US2 + US3 + US4 + US5 → US6
US3 → US7 (integración final después de US6)
US1–US7 → US8 → Cierre T061–T064
```

US4 usa evidencia de US3 para las pruebas reales; US7 puede avanzar en módulos propios tras US3. T037 no depende del runner final T060: usa directamente T004. US5 completa adaptadores/runtime, conservando pruebas de generación ya efectuadas. Antes de cada historia se escriben regresiones; después modelos/servicios, API/clientes y validación independiente. Las pruebas finales revalidan los incrementos anteriores.

## Paralelismo permitido por historia

| Historia | Ejemplo sin conflicto después de prerrequisitos |
|---|---|
| US1 | T009 y T010; luego T011 Spring y T012 Quarkus |
| US2 | T017 autoridad y T018 procedencia; implementación T019–T022 secuencial |
| US3 | T023 máquina de estados y T024 evidencia; core T025–T030 secuencial |
| US4 | T031 descriptor y T032 emitters; tras T033, T034 Spring y T035 Quarkus |
| US5 | T038 empaquetado y T039 identidad; T040–T044 secuencial |
| US6 | T045 paneles y T046 contratos; T047–T050 secuencial |
| US7 | T052 módulo eventos y T053 módulo recovery/telemetría; callbacks/startup compartidos secuenciales |
| US8 | T056 tests CI mientras se prepara T058 en archivos distintos; T057 después de T056, T060 después de integraciones |

La marca [P] no autoriza saltar dependencias ni ejecutar agentes adicionales automáticamente. No editar simultáneamente session.py/pipeline_runner.py/routes compartidos entre historias.

## Estrategia incremental y control de terminado

Primer incremento: preparación + fundamentos + US1 (T001–T016). Validar seguridad/conservación antes de ampliar ejecución. Continuar US2–US8 y cierre para resolver todo el análisis. Una casilla sólo se marca con implementación y evidencia revisables; «infraestructura no disponible» deja pendiente el escenario afectado.

| Grupo | Número |
|---|---:|
| Preparación | 4 |
| Fundamentos | 4 |
| US1 / US2 / US3 / US4 | 8 / 6 / 8 / 7 |
| US5 / US6 / US7 / US8 | 7 / 6 / 4 / 6 |
| Cierre | 4 |
| **Total** | **64** |

Formato requerido: checkbox + TID secuencial + [P] opcional + [USn] en historias + descripción y ruta. Estado de implementación actualizado durante la validación; las casillas restantes requieren la evidencia pendiente indicada en RESULTADOS.md.


## Evidencia de implementación actual (2026-10-08)

Las tareas marcadas después de T015 corresponden a las suites backend y frontend, journeys/migración, datos reales PostgreSQL/MySQL, scripts PowerShell con rechazo de propietarios ajenos y matriz de generación. Informes bajo `integration/validation/reliability/`: `quarkus-current-final.xml` (652 aprobadas/6 skips), `spring-runtime-ownership-final.xml` (128 aprobadas/1 skip), `standalone-ownership-current.xml` (4 aprobadas), `integration-current-final.xml` (29 aprobadas), summaries `journeys/` y `migration/`, informes `*-db-conservation-current.xml`, Vitest/builds y las suites anteriores de contratos/CI adversarial.

T017/T042–T044 tienen evidencia nativa ampliada aprobada en ambos estudios. T037/T060/T061 siguen pendientes de repetir el HTTP Spring que agotó tres segundos bajo carga concurrente. T058 está completada: 182 revisiones exactas y baseline histórico intacto. T063/T064 exigen la revisión transversal final. La matriz Linux y GitHub Actions está preparada, sin ejecución remota localmente acreditada; no se afirma una validación de proveedor IA ni BDD.

Push del estado actual solicitado por el usuario: las validaciones pendientes permanecen abiertas; no se declara terminado todo el plan.
