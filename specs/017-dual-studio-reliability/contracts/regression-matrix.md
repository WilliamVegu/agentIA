# Matriz de cierre de hallazgos

**Estado inicial de todas las filas: PENDIENTE.** Son criterios futuros, no resultados de correcciones. Ejecutar en ambos estudios salvo alcance explícito. Ninguna fila cierra por generar documentación, compilar sin tests, cambiar un mock o consumir tiempo. T063 añadirá enlaces de evidencia, commit y estado final.

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
| Spring / Maven | PENDIENTE | PENDIENTE | PENDIENTE |
| Spring / Gradle | PENDIENTE | PENDIENTE | PENDIENTE |
| Quarkus / Maven | PENDIENTE | PENDIENTE | PENDIENTE |
| Quarkus / Gradle | PENDIENTE | PENDIENTE | PENDIENTE |

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
