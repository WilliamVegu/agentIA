# Modelo de datos y estados

Es un diseño objetivo, no una migración ya aplicada. Cada backend conserva su SQLite; IDs no se comparten entre estudios. Añadir tablas/campos versionados; no cambiar silenciosamente el significado de columnas anteriores.

## Entidades

| Entidad | Campos principales | Reglas |
|---|---|---|
| DraftRevision | sessionId, revisionId, schemaVersion, payloadJson, canonicalHash, source, approvalStatus, createdAt, parentRevisionId | contenido inmutable; sessionId existente; aprobación humana explícita |
| SessionConfiguration | sessionId, version, databaseEngine, executionMode, hostPort, framework, buildTool | databaseEngine H2/POSTGRESQL/MYSQL; puerto 1024–65535; defaults explícitos al crear, no al recuperar |
| PipelineOperation | operationId, sessionId, version, targetPhase, revisionId, configVersion, state, checkpoint, requestedControl, timestamps, errorCode | CAS y lock; una operación escritora activa por sesión; credenciales nunca persistidas |
| ArtifactProvenance | sessionId, relativePath, phase, revisionId, inputHash, contentHash, status | ruta contenida; estado CURRENT/OUTDATED; hash incluye manifiestos/config relevantes |
| VerificationRun | runId, operationId, sessionId, snapshotId, fingerprint, revisionId, outcome, validity, runner, exitCode, counts, reportPaths, timestamps | resultado histórico inmutable; validity CURRENT/OUTDATED; suite >0, passed=total, failed=0, sin fallback/interrupción/error para PASSED; informes y snapshot comprobables |
| AuditRun | runId, sessionId, fingerprint, evaluatedStatus, validity, status, score, sourceCount, ruleSetVersion, findings, timestamps | veredicto histórico inmutable; validity CURRENT/OUTDATED; sin fuentes => NOT_RUN y score=null; scope publicado; PASS sólo sobre fingerprint vigente |
| DeploymentOperation | operationId, sessionId, sourceSnapshotId, fingerprint, framework, composeProject, labels, containerIds, imageId, bindings, state, errorCode, timestamps | HEALTHY requiere propiedad, imagen/fuentes vigentes y health nativo; no inferir identidad por puerto |
| RepairAttempt | repairId, operationId, sessionId, relativePath, beforeHash, afterHash, guidanceHint, verificationRunId, outcome, iteration, timestamps | máximo automático 3; aplicación no implica resolución; historial persistente |
| SessionEvent | sessionId, sequence, eventType, operationId, operationVersion, payload, createdAt | orden por sesión; transición y evento en misma transacción; sin credenciales/código sensible completo; retención y cursor explícitos |
| SchemaMigration | migrationVersion, appliedAt, checksum | idempotente, observable; error detiene mutaciones dependientes |
| NormalizedAttribute | name, columnName, javaType, sqlTypeByEngine, nullable, isPrimaryKey, isUnique, idStrategy, constraints | Java simple/FQN normalizado; restricciones con parámetros tipados; no código arbitrario |

payloadJson conserva serviceName, packageName, basePort, entities, userStories, assumptions, markdownSpec e inputInterface. Guardar una edición nueva crea otra revisión; aprobación de una revisión no se hereda automáticamente.

## Estados y compatibilidad

- SessionStatus existente sigue siendo resumen. La aprobación/verificación nunca se deduce de él.
- PipelineOperation.state: QUEUED, RUNNING, PAUSE_REQUESTED, PAUSED, CANCEL_REQUESTED, CANCELLED, COMPLETED, BLOCKED, INTERRUPTED.
- generationState: NOT_STARTED, IN_PROGRESS, PARTIAL, READY, FAILED.
- VerificationOutcome: NOT_RUN, SKIPPED_BY_CHOICE, ENVIRONMENT_UNAVAILABLE, INTERRUPTED, PASSED, FAILED, OUTDATED.
- AuditRun.status: NOT_RUN, PASS, BLOCKED, OUTDATED; score null antes de evaluar.
- Deployment state: IDLE, BUILDING, RUNNING, HEALTHY, DEGRADED, FAILED, STOPPED, DOCKER_UNAVAILABLE, SKIPPED_BY_CHOICE, UNKNOWN.

## Transiciones

| Evento | Precondición | Resultado persistido |
|---|---|---|
| run | sin otro escritor, revisión/config válidas | operation RUNNING; revisión capturada |
| target alcanzado | checkpoint duradero de target | operation COMPLETED + targetReached; generación parcial según artefactos; no PASSED implícito |
| pause | RUNNING | PAUSE_REQUESTED; worker confirma PAUSED en checkpoint |
| resume | PAUSED/INTERRUPTED, inputs revisados, sin escritor | nueva identidad/version de ejecución ligada al checkpoint; mismo target/opciones; worker antiguo no puede actualizar |
| cancel | QUEUED/RUNNING/PAUSED | CANCEL_REQUESTED o CANCELLED confirmado; terminal incompatible => 409 |
| gate bloqueado | auditoría válida BLOCKED | DB BLOCKED antes del evento |
| reparar | sesión existente, archivo permitido, sin escritor | evidencia OUTDATED; RepairAttempt aplicado; verificación posterior decide |
| editar fuente/config/draft | permiso/lock + expectedVersion | nueva revisión/version; descendientes y evidencia OUTDATED |
| deploy | PASSED vigente + audit PASS + recursos identificables | BUILDING; HEALTHY/FAILED/DOCKER_UNAVAILABLE según resultado real |
| stop | recurso propio inspeccionado | STOPPED sólo si confirmado; volúmenes conservados |
| cleanup deleteData | confirmación explícita + recursos propios | eliminación sólo de identidades registradas; fallo visible |
| reinicio backend | operación marcada activa sin worker/lease | INTERRUPTED; recursos reconciliados, no reejecución automática |

Una sesión SOURCE_ONLY puede completar generación y permitir ZIP de fuentes auditadas, pero mantiene verification=SKIPPED_BY_CHOICE/NOT_RUN y deployment=SKIPPED_BY_CHOICE. Si ya hubo un FAILED real, ese registro permanece y no se sustituye por SKIPPED; el modo nuevo sólo rige futuras operaciones.

OUTDATED es vigencia, no una reescritura del resultado histórico: conservar outcome/informes originales de VerificationRun y el veredicto evaluado de AuditRun; la proyección actual muestra OUTDATED cuando el fingerprint ya no coincide. FAILED histórico permanece aun si se invalida o cambia el modo. Guardar transición + SessionEvent atómicamente; el dispatcher transmite después del commit y consulta eventos pendientes al recuperar. Replay puede repetir eventos, por lo que clientes deduplican por secuencia. No se promete entrega exactly-once.

## Migración legacy

1. Copiar DB y manifiestos de runtime antes de migrar; excluir secretos y restringir permisos de la copia.
2. Añadir esquema bajo transacción y registrar versión/checksum; segunda ejecución no modifica otra vez.
3. Importar draft completo si existe y valida. Entidades/historias parciales se marcan NEEDS_REVIEW; no inventar packageName/port como datos originales.
4. Importar verificación sólo si reportes/snapshot/fingerprint se pueden comprobar; de lo contrario NOT_RUN. Conservar FAILED anterior.
5. Runtime sin identidad suficiente queda UNKNOWN/LEGACY_UNOWNED; no detener ni borrar automáticamente.
6. Mantener columnas legacy para lectura compatible; serializadores proyectan el nuevo modelo.
7. Reversión de código conserva tablas aditivas; cualquier rollback de datos se ensaya sobre copia con procedimientos explícitos. Nunca restaurar una DB vieja encima de cambios de usuario sin revisión.

