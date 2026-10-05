# Contratos vigentes de despliegue local

Revisión: 5 de octubre de 2026. `devops-api.yaml` se exporta desde las rutas y modelos FastAPI reales mediante `backend/scripts/export_devops_contract.py`. El contrato contiene rutas de sesiones, autenticación y DevOps; no acredita ejecución remota de pipelines ni Kubernetes.

## Elección, capacidad y evidencia

| Concepto | Valores y significado |
| --- | --- |
| Elección persistida | `SOURCE_ONLY` por defecto; `DOCKER` solo cuando el usuario lo elige. |
| Finalización de generación | `COMPLETED` también permite una entrega de fuentes sin ejecutar pruebas. No equivale a `VERIFIED`. |
| Verificación | `NOT_RUN`, `SKIPPED_BY_CHOICE`, `ENVIRONMENT_UNAVAILABLE`, `INTERRUPTED`, `PASSED`, `FAILED`, `OUTDATED`. |
| Despliegue | `IDLE`, `BUILDING`, `RUNNING`, `HEALTHY`, `DEGRADED`, `FAILED`, `STOPPED`, `DOCKER_UNAVAILABLE`, `SKIPPED_BY_CHOICE`. |
| Capacidad | Diagnóstico solicitado por el usuario; `readyForPreparation` y `preparedImagesAvailable` no son prueba de compilación ni aceptación offline. `offlineVerified` permanece false en el diagnóstico actual. |

El diagnóstico comprueba BuildKit seleccionado sin bootstrap, arquitectura de imágenes, mínimo de espacio host y cachés. La caché preparada se consulta mediante un contenedor temporal limitado, sin red/pulls/mounts ni escritura, con limpieza por etiqueta UUID. Presencia de JAR no demuestra todas las dependencias. Consulte [diagnóstico local](../../../docs/DIAGNOSTICO_LOCAL_DOCKER.md) para límites y recuperación.

`PASSED` exige una suite realmente ejecutada y no vacía, sin fallos/fallback/interrupción y fingerprint vigente. `HEALTHY` exige runtime de la sesión inspeccionado y salud HTTP actual; no acredita pruebas. Un build fallido nunca arranca. Cambiar a fuentes conserva fallos reales anteriores; no los convierte en aprobaciones. `NOT_EXECUTED` aparece en metadata de entrega inicial y no es un nuevo valor del enum de verificación.

## Rutas y efectos

Todas las rutas privadas requieren la cookie de autenticación creada mediante login o acceso MVP local habilitado. El JSON de configuración no incluye credenciales. Las rutas se identifican por `session_id`; no reciben una carpeta arbitraria del host.

| Ruta | Efecto |
| --- | --- |
| `POST /api/v1/sessions` o `/quick-start` | Crear sesión; `executionMode` omitido conserva SOURCE_ONLY. |
| `PATCH /api/v1/sessions/{session_id}/execution-mode` | Guardar elección explícita. Rechaza cambios durante generación/operación incompatible; un runtime activo debe detenerse antes de pasar a fuentes. |
| `POST /api/v1/sessions/{session_id}/verify` | Verificar fuentes actuales; en SOURCE_ONLY completa el alcance de fuentes sin ejecutar Docker. Devuelve status y metrics, no un PASS implícito. |
| `GET /api/v1/devops/{session_id}/configuration` | Leer motor/puerto/buildTool/buildDirectory resueltos sin Docker. |
| `GET .../diagnostics` | Diagnóstico bajo demanda; SOURCE_ONLY devuelve omisión sin CLI/daemon. |
| `POST .../generate` | Generar activos con auditoría y control de propiedad; `db_engine`/`host_port` omitidos conservan configuración guardada. |
| `POST .../prepare` | Preparación online explícita. Puede devolver BUILDING; no registra verificación offline. |
| `POST .../deploy` | Requiere evidencia vigente y auditoría; construye offline antes de up sin build/pull. `hostPort` omitido conserva configuración; puerto ocupado elige alternativa localhost. |
| `GET .../status` | Estado/identidad/puerto efectivo; SOURCE_ONLY no consulta Docker. |
| `POST .../stop` y `.../restart` | Inspección de recursos propios; conservan volúmenes y datos. Reinicio no ejecuta nuevas pruebas. |
| `POST .../cancel` | Body `operationId` obligatorio; solicita cancelar esa operación. `cancelRequested=true` no confirma que BuildKit haya terminado. |
| `POST .../cleanup` | Body `deleteData=true` confirma eliminación de recursos/datos de esa sesión. No es una acción de limpieza global. |
| `POST .../smoke-test` | Salud del runtime propio; campo `passed` describe el resultado real. |
| `GET .../logs` | Snapshot REST con `logs`, `events`, `lastEventId`. |
| `GET .../logs/stream` | SSE con cookie y header `Last-Event-ID`. Eventos `log`/`log-reset`; REST permite recuperar snapshot. Cursor inválido devuelve 400. |
| `GET .../playground/resources` y `POST .../playground` | Recursos de la sesión y proxy a localhost inspeccionado. No acepta una URL externa arbitraria. |

En esta tabla `...` significa `/api/v1/devops/{session_id}`. Prepare/deploy/restart pueden responder HTTP 200 con BUILDING o estado no ejecutado; el cliente debe consultar el resultado de operación. No interpretar HTTP 200, archivos de tests o manifests generados como evidencia de tests, CI o Kubernetes.

## Errores y recuperación

| HTTP | Interpretación |
| --- | --- |
| 401 | Falta autenticación; obtener sesión local válida. |
| 403 | Política, auditoría o evidencia no permiten la acción. |
| 404 | Sesión/workspace/recurso inexistente. |
| 409 | Operación incompatible, configuración inválida, activos ajenos/editados o control de operación en conflicto. `detail` explica la causa. |
| 422 | Body/query inválido; puertos explícitos deben estar entre 1024 y 65535. |

Los fallos de entorno también pueden ser estados de dominio con HTTP 200; leer `status`, `errorMessage`, `message`, `verificationOutcome` y métricas según la respuesta. Reintentar significa mantener/elegir DOCKER y verificar fuentes actuales. Continuar sin Docker significa cambiar explícitamente a SOURCE_ONLY y completar entrega de fuentes auditadas. El servidor no instala sustitutos ni cambia virtualización/permisos. Un error real de compilación no se clasifica automáticamente como fallo de infraestructura.

## Operaciones y logs

`operationId`, `operationKind`, `operationPhase`, `startedAt`, `finishedAt` y `cancelRequested` describen la operación local. La exclusión/idempotencia es por sesión y proceso backend; la aceptación entre procesos y la cancelación BuildKit completa siguen pendientes.

Cada evento de log contiene ID, timestamp, origen y mensaje redactado. Cursor/historial son por sesión. El historial está acotado a 1.000 eventos; captura Docker también acotada y con aviso de posible pérdida. Reconectar no inventa eventos ni duplica IDs; estos límites no garantizan captura sin pérdidas ante ráfagas/rotación.

## Reproducción del contrato

Desde la raíz con el Python del proyecto:

```powershell
.\.venv\Scripts\python.exe backend/scripts/export_devops_contract.py
.\.venv\Scripts\python.exe backend/scripts/export_devops_contract.py --check
```

El exportador utiliza DB temporal y tracing deshabilitado en su proceso; no usa las sesiones de usuario ni llama Docker o IA. Conserva referencias de schemas transitivas. La cookie y los modelos se derivan del código. Esta comparación comprueba coherencia estructural, no aceptación completa de cada ruta en navegador.

## Snapshot e identidad de ejecución

Verificaciones DOCKER nuevas guardan sourceSnapshotId en métricas. Deploy público exige ese sello, su integridad y fingerprint vigente; sesiones históricas requieren verificar nuevamente. Runtime expone sourceSnapshotId, workspaceFingerprint, imageId y executableJarSha256. Imagen y contenedor inspeccionados deben corresponder a esos valores; recuperación discrepante es DEGRADED, sin URL aprobada. La suite corre en copia privada y el deploy copia su JAR aprobado sin recompilar. SOURCE_ONLY conserva omisión explícita y no crea snapshot Docker. Los campos opcionales permiten leer estados históricos, sin acreditarles un sello nuevo.
