# Matriz de cierre de hallazgos

Los siguientes casos conservan los criterios originales de aceptación. El registro de revisión al final distingue resultados locales comprobados y capacidades pendientes; una aprobación local no acredita ejecución remota ni un proveedor IA real.

Capas: U = unitario, A = API/contrato, F = frontend, I = integración de proceso/Git/Docker, J = Java y HTTP reales. Las pruebas I/J usan fixtures propias de T004; nunca recursos/DB del usuario. La generación IA se simula únicamente en tests, no como fallback de producción.

## Hallazgos H01–H14

| ID / prioridad | Caso obligatorio y resultado esperado | Capas | Historias / tareas |
|---|---|---|---|
| H01 / P1 | Quarkus y Spring: sesión inexistente 404 antes de acceso a archivo; rutas absoluta/UNC/otro drive/ADS/traversal/junction/symlink externa rechazadas. Sentinel no leído/escrito. Preview sin sesión transforma sourceCode únicamente. Fallo de escritura no devuelve éxito. | U/A/I | US1: T009, T011–T013; T061 |
| H02 / P1 | Guardar/aprobar LedgerEntry, UUID, importe positivo, com.audit.custom y 18088; GET y Auto-Pilot tras restart conservan diseño. Cambio concurrente crea revisión o 409, aprobación no se hereda. Legacy corrupto requiere revisión, sin Order/Pedido sustituto. Todos los artefactos trazan revisión/fingerprint. | U/A/F/I | US2: T017–T022; T045–T049, T060 |
| H03 / P1 | Quarkus: workspace vacío sin 4 historias/2 entidades/suites aprobadas/95/100; gate no autoriza export verificado. GET overview/detail/metrics/repairs concuerdan; UUID de sesión ausente 404. COMPLETED parcial no es PASSED; suite cero/fallback/report ausente no aprueba. Spring conserva su gate vacío ya correcto. | U/A/F | US3/US6: T024, T026, T029–T030, T045–T050 |
| H04 / P1 | Ambos Java reales: email inválido e importe negativo/cero devuelven 400 con @Email/@Positive; válidos crean recurso. @Valid/Record/handler nativo efectivos. Tests negativos fallan si se elimina la anotación; BDD no soportado aparece pendiente. | U/J | US4: T031–T037; T060–T061 |
| H05 / P1 | Quarkus: 8080 ocupado por servicio ajeno no produce HEALTHY. AutoDeploy pendiente sigue pendiente y fallo Compose/timeout no termina COMPLETED con éxito. Native health del contenedor/imagen/snapshot propio, dos sesiones independientes. Revalidar Spring con iguales pruebas. | A/F/I | US5: T038–T044; T050, T060 |
| H06 / P1 | Insertar registros PostgreSQL y MySQL, stop/restart y releer. Sin eliminación de volumen. Cleanup sin opt-in o con propietario ajeno rechazado; con confirmación vigente sólo elimina fixture propia. Error Docker no se convierte en STOPPED. | A/F/I/J | US1/US5: T010, T014, T016, T041, T044 |
| H07 / P1 | Git local bare: push válido y divergencia sin force/reset. Historial remoto previo permanece. PAT centinela ausente de URL/argv/config/archivo temporal/log/respuesta/ZIP incluso en errores y proceso interrumpido. Credencial limitada al host esperado y origin conservado. | U/A/I | US1: T010, T015–T016; T060 |
| H08 / P2 | H2/POSTGRESQL/MYSQL elegidos coinciden en request/SQLite/GET/driver/SQL/Compose/overview. Alias database compatible; conflicto con databaseEngine => 422, no default silencioso. No inferir DB por VARCHAR. | U/A/F/J | US4/US6: T033, T036–T037, T046–T050 |
| H09 / P1 MySQL | Quarkus: DDL/seeds MySQL ejecutan sin sintaxis PostgreSQL/H2; UUID/ID/fecha/decimal/FK/unique coherentes. H2/PostgreSQL también arrancan. Spring conserva Liquibase y no rompe dialectos. Doble inicialización de esquema evitada. | U/J | US4: T031, T036–T037; T060 |
| H10 / P2 | Target REQUIREMENTS no genera Java/DevOps; pause confirmada sólo en checkpoint; cancel/pause terminal 409 sin reescribir historia; resume mantiene revisión/opciones y sólo un worker. Gate BLOCKED en DB sobrevive restart; callback antiguo no actualiza nueva operación. | U/A/F/I | US3/US7: T023, T025–T027; T048, T051–T054 |
| H11 / P2 | Spring UUID/ID personalizado coherente en todas las firmas, sin Long impuesto. Quarkus Instant/LocalDate/LocalDateTime conservan tipos; isUnique llega a entidad/DDL. CRUD/deserialización/valores persistidos correctos sobre tres DB y ambos build tools. | U/J | US4: T031–T037 |
| H12 / P2 | Ambos: cero fuentes => auditoría NOT_RUN, score=null; cero métricas medido se mantiene cero, sin 284/12/2.2/100 de ejemplo. Fuente con defecto => gate real bloqueado; mensaje SOURCE_ONLY no dice desplegado. No atribuir falso PASS global al gate vacío Spring, que ya bloqueaba. | U/A/F | US3/US6: T024, T029–T030, T045, T048–T050 |
| H13 / P2 | Quarkus no declara diagnosticsResolved por escribir/rerun sin pruebas. SOURCE_ONLY APPLIED_UNVERIFIED; DOCKER pendiente/FAILED/VERIFIED según ejecución real. Error escritura/runner conserva bloqueo. guidanceHint canónico y promptHint alias; hint-only 422 sin mutación. Máximo tres intentos persistidos tras restart. | U/A/F/I | US3/US6: T024, T028, T046–T049; T060 |
| H14 / P2 | CI Quarkus GitHub/GitLab ejecuta scanner/secret checks/test gate reales: secret centinela/SAST conocido/test fallido/zero suite bloquean. Trivy action fijada, reportes accesibles y alcance publicado. Equivalentes Spring pasan escenarios sin relajación. | U/I/J | US8: T056–T057, T060–T061 |

## Observaciones complementarias O01–O07

| ID | Caso obligatorio y resultado esperado | Capas | Tareas |
|---|---|---|---|
| O01 — instalación | Python WindowsApps, falta de pip/node/npm/venv o locks dan preflight accionable. Dos venv y paquetes app separados. Instalación limpia Windows/Linux con resolución compatible, sin destruir venv existente. | U/I | T001–T004, T055, T059, T061 |
| O02 — SSE | Dos clientes reciben secuencia completa e igual por sesión; cliente lento no bloquea, reconexión replay o resync si expiró. Evento después de commit DB, callbacks obsoletos ignorados y suscriptores liberados. | U/A/F/I | T023, T051–T054 |
| O03 — recuperación/telemetría | Restart convierte operación inconclusa en INTERRUPTED y mantiene reparación/evidencia/historia. No reejecuta IA/Git/Docker. MLflow inaccesible degrada tracing sin romper flujo. Costes/sessionIds entre estudios aislados, secretos nunca en eventos/DB/log. | U/A/I | T005–T008, T025, T028, T051–T054 |
| O04 — matriz real | Doce combinaciones framework × Maven/Gradle × DB verificadas; seis journeys mínimos por estudio cubren manual/guided/Auto-Pilot × modo, más casos de fallo/repair/interrupción/ZIP/Git. Tests vacíos o infra ausente jamás se certifican. | A/F/I/J | T037, T044, T050, T060–T061 |
| O05 — baseline/revisiones | source-snapshots histórico inmutable. Manifest autorizado con hashes antes/después/TID/evidencia permite sólo cambios listados; hash incorrecto/modificación no listada/manifest manipulado falla. | U/I | T001, T058, T063 |
| O06 — límite reparación | Constante/UI/API efectiva = tres intentos automáticos por ciclo; restart no reinicia contador ni borra intentos. Error de infraestructura no consume intento. Al agotar, bloqueo y acción humana explícita; manual no reinicia silenciosamente loop automático. | U/A/F/I | T023–T025, T028, T048, T054, T063 |
| O07 — tres fallos Spring previos | Reproducir en entorno fijado y short path; MAX_PATH tratado en I/O/clon diagnóstico, OpenAPI generado desde FastAPI elegido, fixture DOCKER respeta 403 y precondición real. Suites pasan sin debilitar gate; skip explícito si falta capacidad. | U/I | T002–T003, T011, T055, T059, T061 |

## Matriz Java obligatoria

Cada celda ejecuta tests reales, empaquetado nativo offline y HTTP de contrato (positivo/negativo), además de guardar reportes/fingerprint. PostgreSQL/MySQL prueban arranque con DDL propio y conservación de datos. Usar perfiles apropiados para cada motor, sin cambiar silenciosamente a H2 durante un caso PostgreSQL/MySQL.

| Framework / build | H2 | PostgreSQL | MySQL |
|---|---|---|---|
| Spring / Maven | JAVA/HTTP PASSED | JAVA/HTTP PASSED | JAVA/HTTP PASSED |
| Spring / Gradle | JAVA/HTTP PASSED | JAVA/HTTP PASSED | JAVA/HTTP PASSED |
| Quarkus / Maven | JAVA/HTTP PASSED | JAVA/HTTP PASSED | JAVA/HTTP PASSED |
| Quarkus / Gradle | JAVA/HTTP PASSED | JAVA/HTTP PASSED | JAVA/HTTP PASSED |

Evidencia Java: `integration/validation/reliability/current-matrix/java-matrix-relational-{springboot,quarkus}-all-all.json`. HTTP Quarkus: `current-matrix/quarkus-native-http.xml`. Repetición HTTP Spring: `closure-http-verified/springboot-native-http.xml`, seis casos aprobados el 2026-10-09. Las seis huellas Spring coinciden exactamente con las de la matriz Java anterior; el fallo previo bajo carga se conserva. Estos resultados corresponden a fixtures explícitamente offline, sin proveedor IA.

Preparación online y ejecución offline se documentan separadas. La red privada con DB no implica permiso para descargar dependencias o llamar proveedores IA. Tests Java de validación deben fallar al introducir deliberadamente el defecto en fixture; quitar defecto después y conservar ambas evidencias.

## Journeys y casos transversales

Por estudio, cubrir manual, guided y Auto-Pilot en SOURCE_ONLY y DOCKER. SOURCE_ONLY no ejecuta Docker ni Java por obligación y ofrece ZIP de fuentes auditadas con metadata UNVERIFIED. DOCKER exige evidencia vigente para verified delivery. Incluir un FAILED real seguido de elección SOURCE_ONLY: FAILED histórico permanece.

Casos adicionales: cambio de revisión durante ejecución; edición manual invalida snapshot; gate vacío/código con defecto; infraestructura ausente y retry; pausa segura y resume; target parcial; cancel terminal; reparación fuente/pendiente/fallida/exitosa; hint-only; dos suscriptores/reconexión; restart; migración legacy dos veces y fallo; health ajeno; colisión; stop/cleanup; push divergente. Export/publish deben adjuntar el mismo tipo de evidencia que usa overview.

Los diez paneles: overview, especificación, requisitos, arquitectura, modelos/SQL, generación, explorador, seguridad/calidad, DevOps y export/publicación. Selector/login se comprueban como aislamiento/acceso existente, sin añadir privilegios.

## Relación con requisitos funcionales

| Requisito | Tareas principales |
|---|---|
| FR-01 / FR-02 / FR-03 | T009–T016, T041, T044 |
| FR-04 / FR-05 | T017–T022, T025–T026 |
| FR-06 / FR-07 / FR-08 | T023–T030, T051–T054 |
| FR-09 / FR-10 | T031–T037, T047, T049 |
| FR-11 / FR-12 | T038–T044, T055, T057, T060 |
| FR-13 / FR-14 | T045–T054 |
| FR-15 | T001–T004, T055–T060 |
| FR-16 | T005–T008, T019, T025, T041, T053, T062 |
| FR-17 | Pruebas de cada historia, T060–T061 y revisión T063 |
| FR-18 | T010, T014–T016, T050, T054, T060, T064 |

## Registro al cerrar una fila

Registrar ID, framework, commit, TIDs, fecha, input/revisión/config, esperado/observado, proceso/exit code, conteos, informes, fingerprint y recursos fixture. Estado final: CERRADO, FALLA o PENDIENTE con motivo/capacidad requerida. Un skip no equivale a CERRADO. Evidencia nueva bajo `integration/validation/reliability/`; no sobrescribir informes históricos ni persistir secretos.

## Revisión local del 2026-10-09 (T063)

Código de partida: `02f8ef2`; correcciones posteriores locales en escritura de pruebas de persistencia y lectura de hashes de artefactos sobre rutas largas. Todos los enlaces siguientes parten de `integration/validation/reliability/`. El registro aplica a ambos estudios salvo indicación explícita. Las suites completas anteriores tienen 1572/663 pruebas aprobadas; `final-journeys` actualiza los recorridos a 34 por estudio y dos reinicios reales. No sumar suites solapadas como pruebas únicas.

| Fila | Estado / evidencia / alcance |
|---|---|
| H01 | CERRADO local: `test_workspace_boundary` en XML completos; `final-paths.xml` verifica generación, inyección y proveniencia a más de 400 caracteres; errores de acceso conservan bloqueo. T009, T011–T013, T059. |
| H02 | CERRADO local: `test_draft_authority`, `test_artifact_revision`, `final-journeys/*-journeys.xml` y runtime Auto-Pilot. Revisión/configuración/personalización conservadas. T017–T022, T045–T049. |
| H03 | CERRADO local: gates y reportes vacíos/ausentes en XML Quarkus, `quarkus-offline-choice-final.xml` y `ui.md`; no PASSED sintético. T024, T026, T029–T030. |
| H04 | CERRADO validación local: JAVA/HTTP PASSED en las doce combinaciones; `validation-mutation-verified.xml` (2) prueba cuatro anotaciones eliminadas/detectadas y dos contratos restaurados, sin modificar fuentes originales. BDD completo PENDIENTE. T031–T037. |
| H05 | CERRADO runtime local: `spring-native-autopilot-final.xml`, `quarkus-native-autopilot-verified.xml` y JSON `*-native-identity-current`; tres sesiones propias, Auto-Pilot, colisión, Docker ausente y proceso nuevo. T038–T044. |
| H06 | CERRADO local: `spring-db-conservation-current.xml` (3), `quarkus-db-conservation-current.xml` (6), `standalone-ownership-current.xml` (4) y matriz HTTP. Recursos del usuario no utilizados. T010, T014, T016, T041, T044. |
| H07 | CERRADO local: `test_git_safety` en `final-journeys` usa bare propio; divergencia sin force, origin preservado y token centinela excluido. No certifica un proveedor Git remoto. T010, T015–T016. |
| H08 | CERRADO local: contratos DB/alias y `test_normalized_domain`, matrix Java/HTTP, `frontend-*-contract-final.log`. T033, T036–T037, T046–T050. |
| H09 | CERRADO local: seis contratos Quarkus y builds offline con DDL propio por motor; MySQL conserva UUID/FK/fecha/decimal y datos. T031, T036–T037. |
| H10 | CERRADO local: `final-journeys`, checkpoints 51/14 y `events.json`; target, pausa/resume, cancel terminal y CAS persistidos. T023, T025–T027, T051–T054. |
| H11 | CERRADO local: doce combinaciones Java/HTTP y huellas/reportes no vacíos. T031–T037. |
| H12 | CERRADO local: gates/auditoría vacíos, `ui.md`, contratos/paneles 23/25; cero/null conservados. T024, T029–T030, T045, T048–T050. |
| H13 | CERRADO local: `test_persisted_repair`, `final-journeys` y paneles; escritura no acredita resolución, hint-only no muta y tres intentos sobreviven reinicio. T024, T028, T046–T049. |
| H14 | PENDIENTE ejecución remota/CVE: `generated-ci-{spring,quarkus}.xml` acredita scanner, secretos y gates locales; no acredita GitHub/GitLab ni Trivy remoto. T056–T057. |
| O01 | PENDIENTE Linux/instalación limpia remota: preflight y dos entornos Windows comprobados; `.github/workflows/reliability.yml` preparado. T001–T004, T055, T059. |
| O02 | CERRADO local: `test_session_events`, `final-journeys` y `events.json`; dos suscriptores, replay/resync y persistencia previa a emisión. T023, T051–T054. |
| O03 | CERRADO local: `final-journeys/real-restart.xml` (2) y aislamiento/telemetría en suites; recuperación sin efectos externos automáticos. T005–T008, T025, T051–T054. |
| O04 | PENDIENTE cobertura externa exhaustiva: matriz Java/HTTP y tres sesiones runtime comprobadas; recorridos API/Vitest usan proveedor mock explícito. No certifican IA real ni toda combinación de navegación visual y modo. T037, T044, T050, T060–T061. |
| O05 | CERRADO local: `verify_sources.py` aprobó el manifest vigente de 186 archivos; `final-integration.xml` incluye comprobaciones negativas del manifest. Baseline histórico inmutable. T001, T058. |
| O06 | CERRADO local: reparación persistida, checkpoints y contratos UI; constante efectiva tres, sin reset por restart. T023–T025, T028, T048, T054. |
| O07 | CERRADO para MAX_PATH/OpenAPI/modo: `final-paths.xml`, suites y fixtures sin relajar gates. El cierre de la suite completa posterior consta en RESULTADOS. T002–T003, T011, T055, T059. |

Contraste FR-01–FR-18: FR-01–03 corresponden a H01/H06/H07; FR-04–05 a H02; FR-06–08 a H03/H10/H12/H13/O06; FR-09–10 a H04/H08/H09/H11; FR-11–12 a H05/matriz; FR-13–14 a `ui.md`/O02; FR-15 a O01/O05/H14; FR-16 a `final-migration`/O03; FR-17 a la matriz y sus pruebas negativas; FR-18 a los límites de propiedad, SOURCE_ONLY y publicación explícita. FR-15/17 conservan pendientes externos; no se declara cumplimiento universal.

Constituciones contrastadas: `.specify/memory/constitution.md` (Spring 1.1.0 y aclaración SOURCE_ONLY) y `systems/quarkus/.specify/memory/constitution.md` (Quarkus 2.0.0). Capas/Records/validación/handlers se comprueban en fixtures nativas; offline, suites no vacías y reparación=3 tienen evidencia local. Cero llamadas IA y ninguna credencial añadida. Quarkus VII exige ausencia de fallback silencioso: tests de configuración explícita aprobados; la generación mock se declara diagnóstico y no prueba un LLM. Quarkus VIII/BDD español completo y cobertura de toda generación LLM quedan PENDIENTES. No se modifican las constituciones ni se fabrica aprobación constitucional.
