# Especificación: fiabilidad de los estudios Spring Boot y Quarkus

**Estado:** propuesta lista para implementación; no implementada.  
**Rama analizada:** dual-systems-selector, cd50688c8188b47ba789ec30683a50eabc7bd593.  
**Fecha:** 2026-10-07, America/Lima.  
**Solicitud:** solucionar todos los hallazgos del análisis previo, conservando ambos estudios.

## Alcance

Corregir H01–H14 y cerrar las observaciones de instalación, eventos, recuperación, rutas profundas, pruebas inconsistentes, telemetría y evidencia incompleta. Mantener backends, datos y frontends independientes. No sustituir Quarkus por Spring ni realizar una extracción general de librerías compartidas.

El plan incluye pruebas de regresión obligatorias para los fallos funcionales y de seguridad. Ninguna prueba normal consume APIs IA reales; los recursos Docker/Git de prueba son temporales, identificados y aislados.

## Historias de usuario

### US1 — Operar sin escapar del workspace, perder datos o sobrescribir Git — P1

Como desarrollador, quiero que lectura, reparación, remediación, detención y publicación actúen exclusivamente sobre mis recursos, para conservar archivos, datos e historia.

Aceptación:
1. Una sesión inexistente devuelve 404; una ruta absoluta, UNC, cross-drive, ADS, traversal o enlace que escape devuelve 400/422 y no lee ni modifica archivos externos.
2. Una remediación preview sin sesión transforma sólo sourceCode recibido; no busca archivos globalmente.
3. Stop/restart conservan registros de PostgreSQL/MySQL. Cleanup con eliminación exige deleteData=true, confirmación explícita en UI e identidad verificada; jamás borra recursos de otra sesión.
4. Un push divergente devuelve conflicto y conserva historia. Ningún PAT figura en URL, argv, .git/config, logs, respuesta, archivo temporal o artefacto.
5. Errores de lectura, escritura, Docker y Git se propagan sin declarar éxito.

### US2 — Generar exactamente desde el diseño elegido — P1

Como arquitecto, quiero que el draft guardado y aprobado sea la autoridad del pipeline, para conservar entidades, reglas, historias, paquete, puerto y configuración.

Aceptación:
1. LedgerEntry, UUID, balance @Positive, paquete com.audit.custom y puerto 18088 se conservan tras guardar, reiniciar y ejecutar Auto-Pilot.
2. La ejecución captura una revisión inmutable; un cambio concurrente provoca 409 o una revisión nueva, sin sobrescribir silenciosamente la que usa el worker.
3. Un draft corrupto/legacy incompleto requiere corrección explícita; no se sustituye por Order/Pedido ni se inventan campos perdidos.
4. Arquitectura, SQL, Java, tests y DevOps registran revisión y fingerprint. Ediciones invalidan sólo las fases descendientes afectadas.
5. Sólo se transforma texto cuando no hay una revisión estructurada utilizable; una generación automática registra su origen y no inventa aprobación humana.

### US3 — Confiar en estados, verificación y reparación — P1

Como desarrollador, quiero estados persistentes respaldados por resultados, para distinguir fuentes generadas, pruebas ejecutadas, fallos e infraestructura inaccesible.

Aceptación:
1. VERIFIED/PASSED exige suite real no vacía, cero fallos, sin fallback/interrupción y evidencia vigente sobre el snapshot probado.
2. SOURCE_ONLY entrega fuentes tras auditoría estática válida, con pruebas/despliegue no ejecutados; no convierte un FAILED histórico en éxito u omisión.
3. Target REQUIREMENTS termina esa ejecución parcial sin generar Java; pausa/cancelación terminal se rechazan sin alterar historia.
4. Pausa se confirma en checkpoint seguro; reanudación conserva opciones y revisión, sin dos escritores simultáneos ni callbacks obsoletos.
5. Reinicio deja operaciones inconclusas INTERRUPTED; no repite automáticamente publicaciones, despliegues ni llamadas IA.
6. La reparación conserva el bloqueo hasta verificar; SOURCE_ONLY devuelve APPLIED_UNVERIFIED y diagnosticsResolved=false. El límite automático efectivo es tres intentos, conforme a ambas constituciones.
7. Una pista sin código devuelve 422 con explicación; esta entrega no añade un agente nuevo de reparación por prompt. guidanceHint es canónico y promptHint es alias de compatibilidad cuando acompaña código.

### US4 — Obtener un dominio y SQL fieles al contrato — P1

Como consumidor del servicio generado, quiero tipos y restricciones coherentes con el blueprint y el motor elegido, para que el comportamiento real respete mis criterios BDD.

Aceptación:
1. Ambos servicios rechazan correo inválido, importe negativo y cero con 400 cuando existen @Email/@Positive; aceptan valores válidos.
2. UUID y claves con nombre personalizado se mantienen en entidades, DTO, repositorios, servicios, endpoints, SQL y tests; fechas siguen siendo fechas.
3. Unicidad y restricciones tipadas llegan a Java/DDL. Anotaciones Java arbitrarias o reglas incompletas se rechazan antes de escribir.
4. databaseEngine coincide en UI, SQLite, driver, ORM, DDL, seeds, Compose y overview. Alias database se admite temporalmente; discrepancia entre ambos devuelve 422.
5. H2, PostgreSQL y MySQL arrancan con su DDL; CRUD, validación, claves, fechas, decimal, unicidad y FK se comprueban sobre motores reales.
6. Criterios BDD no implementados no se certifican por compilar; el reporte identifica cobertura pendiente.

### US5 — Desplegar el artefacto correcto y observar su resultado — P1

Como operador, quiero que el despliegue use un artefacto nativo verificado y recursos identificados por sesión, para evitar falsos HEALTHY y colisiones.

Aceptación:
1. Un servicio ajeno en 8080 no acredita salud. Spring usa /actuator/health y Quarkus /q/health sobre el contenedor e imagen identificados.
2. AutoDeploy sólo completa su etapa cuando la operación requerida alcanza HEALTHY; fallo/timeout queda persistido como FAILED o pausa por infraestructura.
3. Preparación online y ejecución offline son pasos distintos. Build/test posterior no descarga dependencias ni llama IA.
4. Dos sesiones con el mismo serviceName operan con identidades Compose distintas y puertos disponibles. Recursos legacy sin propiedad verificable no se adoptan ni borran automáticamente.
5. Sin Docker, hay una respuesta explícita de infraestructura, conservación de fuentes y ninguna reparación consumida.
6. Adaptadores de empaquetado verifican Spring Boot executable JAR o Quarkus fast-jar, sin exigir BOOT-INF a Quarkus.

### US6 — Ver información auténtica en los diez paneles — P2

Como usuario, quiero que tarjetas y acciones reflejen contratos y evidencia, para no confundir ejemplos, ceros y operaciones pendientes con resultados.

Aceptación:
1. Workspace vacío no muestra suites aprobadas ni gate aprobado; 0 sigue siendo 0 y ausencia de medición se muestra como “No evaluado”.
2. Historias/entidades corresponden a conteos reales; no hay defaults 4/2/95/284/12/2.2.
3. Acciones de generación, reparación, pruebas, DevOps y entrega responden al estado válido del backend.
4. El mensaje final distingue entrega de fuentes, verificación y despliegue. No promete “desplegado” al omitir Docker.
5. Datos de ambos estudios permanecen separados; mock/samples sólo aparecen en diagnóstico explícito, nunca como fallback silencioso de producción.

### US7 — Recuperar y observar operaciones sin perder eventos — P2

Como usuario, quiero historia y eventos coherentes después de reconectar o reiniciar, para conocer exactamente qué ocurrió.

Aceptación:
1. Dos clientes reciben la misma secuencia SSE de una sesión; reconexión con Last-Event-ID recupera eventos o informa que debe recargar el snapshot.
2. IDs ordenados por sesión, eventos con operationId/version y buffers acotados; clientes lentos no bloquean workers.
3. La transición se confirma en DB antes de publicar su evento; la memoria es caché.
4. Tracing MLflow ausente se muestra como degradado sin romper el flujo; costes y credenciales no se mezclan entre estudios.
5. Historial de reparación y operaciones se conserva; tokens/API keys no se persisten para reanudación.

### US8 — Validar una instalación y un CI reproducibles — P2

Como mantenedor, quiero instalación y comprobaciones ejecutables, para detectar regresiones sin esconder fallos ni consumir IA de pago.

Aceptación:
1. Launcher resuelve un intérprete funcional y verifica pip, entornos separados y npm/lockfiles; falta de prerrequisitos da instrucciones accionables y no destruye instalaciones existentes.
2. CI GitHub/GitLab ejecuta realmente auditoría, pruebas e informes. Secretos centinela, cero tests y tests fallidos bloquean.
3. Todas las suites pasan en versiones fijadas; las tres aserciones Spring previas se tratan por su causa, no debilitando gates.
4. Windows rutas profundas y Linux se validan; un skip tiene motivo visible.
5. Baseline histórico permanece inmutable y las revisiones autorizadas tienen hashes antes/después, tareas y evidencia.
6. E2E de ambos estudios cubre manual/guided/Auto-Pilot, SOURCE_ONLY/DOCKER, tres DB, interrupción, reparación, ZIP y publicación local sin force.
7. Prueba IA real es opcional, manual y fuera del CI normal, con límite de llamadas/coste definido antes de ejecutarla. Cero llamadas por defecto.

## Requisitos funcionales

| ID | Requisito | Historias |
|---|---|---|
| FR-01 | Resolver de archivos por sesión y escritura atómica, sin búsqueda global | US1 |
| FR-02 | Stop conserva volúmenes; cleanup destructivo explícito y sólo propietario | US1, US5 |
| FR-03 | Git sin force/PAT en disco y con conflictos reales | US1 |
| FR-04 | Draft completo versionado y aprobación/origen explícitos | US2 |
| FR-05 | Ejecución ligada a revisión y proveniencia; invalidez descendiente | US2, US3 |
| FR-06 | Evidencia de pruebas/auditoría separada de generación y despliegue | US3 |
| FR-07 | Transiciones persistentes, CAS, locks, checkpoints y recuperación | US3, US7 |
| FR-08 | Reparación real, contratos de hint y máximo tres intentos | US3 |
| FR-09 | Atributos normalizados, allowlist segura y firmas de IDs coherentes | US4 |
| FR-10 | Configuración DB explícita y dialectos/ORM/seeds coherentes | US4 |
| FR-11 | Runtime identificado y resultado de operación requerido | US5 |
| FR-12 | Adaptadores nativos y build/test offline tras preparación | US5, US8 |
| FR-13 | Contratos frontend exactos y métricas sin ejemplos ficticios | US6 |
| FR-14 | Broadcast/replay SSE acotado y logging sin secretos | US7 |
| FR-15 | Instalación reproducible, CI auténtico y trazabilidad de snapshots | US8 |
| FR-16 | Migración aditiva, versionada y conservadora de datos legacy | US2, US3, US5 |
| FR-17 | Regresiones negativas obligatorias y pruebas end-to-end reales | Todas |
| FR-18 | Sin ampliación de acceso demo ni publicación/destrucción automática | US1, US8 |

## Exclusiones

No fusionar estudios, cambiar stack/hosting, implementar autenticación empresarial Quarkus, actualizar masivamente dependencias, publicar PRs/remotos ni desplegar Kubernetes. No garantizar cualquier regla BDD arbitraria: las reglas no soportadas deben producir diagnóstico, no una implementación inventada.

## Definición de terminado

Los 14 hallazgos tienen prueba de cierre en la matriz; pasan suites y builds fijados, escenarios reales obligatorios y migraciones; la UI no atribuye resultados no ejecutados. Ninguna fase se declara completa por agotar tiempo o por omitir infraestructura. Los límites ambientales se documentan como pendientes y bloquean sólo la capacidad que falta.

