# Contratos objetivo: API, UI y operaciones

Se aplican de forma equivalente a ambos backends bajo /api/v1, con adaptación nativa de framework. Este documento describe cambios por implementar. Regenerar OpenAPI desde FastAPI y derivar/verificar tipos TypeScript; no mantener un contrato manual paralelo sin prueba.

## Nombres y errores

Canónicos: serviceName, databaseEngine, executionMode, guidanceHint, sessionId, operationId, expectedRevisionId/expectedVersion. Mantener alias documentados snake_case y database/promptHint durante una versión de transición. Si dos aliases contradicen, 422. Campos mutantes desconocidos se rechazan; credenciales permitidas sólo en campos/header expresamente definidos y nunca se serializan en respuestas.

404: sesión/revisión/archivo inexistente. 400: ruta/protocolo peligroso. 422: payload/regla/alias inválido. 409: operación concurrente, transición terminal o revisión obsoleta. 403: gate real no satisfecho. Un fallo interno no se convierte en 200.

## Superficie

| Operación | Contrato y respuesta |
|---|---|
| POST /sessions/quick-start | motor/modo explícitos; 201 con configuración persistida y generationState NOT_STARTED; sin cifras ejemplificadas |
| POST /requirements/sessions/{id}/save | draft completo + expectedRevisionId; nueva revisionId/hash, approvalStatus; compatibilidad del save actual; confirmación humana separada del guardado |
| POST /requirements/sessions/{id}/approve (nuevo) | revisionId + expectedVersion; aprueba exactamente esa revisión, sin regeneración |
| GET /requirements/sessions/{id} | draft persistido completo + revisión/origen/aprobación; sin reconstrucción silenciosa de datos faltantes |
| POST /orchestrator/pipeline/run | sessionId, revisionId, targetPhase, autoDeploy, opciones; 202 operationId/runState/streamUrl; modo/config tomados de sesión, no fallback oculto |
| POST /orchestrator/pipeline/{id}/pause,resume,cancel | opera sobre operationId/expectedVersion; request confirmado; 409 si terminal incompatible; reintento de misma operación idempotente |
| GET /sessions/{id}, /metrics, /overview, /repairs | proyección de datos persistidos; 404 inexistente; los cuatro endpoints concuerdan |
| POST /sessions/{id}/manual-repair | filePath relativo y modifiedCode obligatorio; guidanceHint opcional; invalidate + apply + verify; 202 si async y operación consultable, nunca “resolved” anticipado |
| POST /security/remediate | preview con sourceCode sin persistencia; persist con sessionId + filePath relativo + expectedFingerprint; no búsqueda global |
| POST /devops/{id}/prepare | preparación online explícita, operationId; inventario/fingerprint del build tool y dependencias |
| POST /devops/{id}/deploy | gate de verificación/auditoría vigente; 202 operationId, no HEALTHY inmediato; estado final consultable |
| GET /devops/{id}/status | sólo inspección/reconciliación del recurso identificado; UNKNOWN/DOCKER_UNAVAILABLE si no puede verificarse |
| POST /devops/{id}/stop,restart | operación sobre recurso propio; conserva volúmenes; confirma exit/status |
| POST /devops/{id}/cleanup | deleteData=false por defecto; true sólo con confirmación explícita vinculada a sesión/config/operación; recursos ajenos rechazados |
| GET /sessions/{id}/export, /orchestrator/sessions/{id}/export-bundle | una misma política por tipo de entrega; fuentes SOURCE_ONLY auditadas permiten ZIP con informe UNVERIFIED; “ejecutable verificado” exige evidencia vigente |
| POST /sessions/{id}/publish | repo/branch válidos; default source delivery coherente con modo y evidencia incluida; push sin force ni PAT en config; divergencia 409; no declara PR creado |
| GET /orchestrator/pipeline/{id}/events, /sessions/{id}/stream | SSE con event IDs y snapshot/version; broadcast y replay, no cola consumida por cliente |

La confirmación de eliminación usa primero vista previa de los recursos que serán afectados y una acción explícita de la UI; el backend comprueba que siga vigente. No se requiere una confirmación para stop conservador. Los scripts de limpieza deben exigir el mismo opt-in.

## Proyección de estado

Overview contiene nombres reales: userStoriesCount, entitiesCount, testsExecuted, testsPassed, verificationOutcome, generationState, securityAuditVerdict, qualityScore nullable, deploymentStatus, deploymentUrl nullable, databaseEngine, availableActions, operationId/version y provenance.

testsPassed=true sólo con PASSED vigente. testsExecuted=false no es fracaso ni aprobación. score=null no es 95/100. Un 0 medido se renderiza como 0. deploymentUrl sólo existe para un recurso identificado; /q/health para Quarkus y /actuator/health para Spring. La UI no convierte phase COMPLETED en VERIFIED.

## Reparación

Respuesta final distingue VERIFIED, APPLIED_UNVERIFIED, APPLIED_VERIFICATION_PENDING y BLOCKED; mantiene aliases legacy documentados durante transición. diagnosticsResolved sólo true para VERIFIED con evidencia real. Una pista sola recibe 422 antes de cambiar archivos o estado. Se persiste historial, no diccionarios globales como autoridad.

## SSE

Cada evento incluye id=<sequence>, sessionId, operationId, operationVersion, type, timestamp y payload filtrado. Transición y evento se guardan atómicamente; publicación después del commit, con recuperación de pendientes. Last-Event-ID recupera posteriores dentro de la retención; cliente deduplica por sequence. Cursor expirado recibe evento resync_required y snapshot actual; no se simula replay completo. Ping/heartbeats sin datos sensibles; desconexión elimina suscriptor; cola por suscriptor acotada.

## Compatibilidad

Cambios aditivos en respuestas primero; actualizar UI y después hacer estrictos requests que antes ignoraban campos. Documentar 400→409 de conflictos de estado y alias deprecated. No copiar un JSON OpenAPI de una versión distinta: exportador/check ejecutados con dependencias fijadas.

