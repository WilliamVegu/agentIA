
# Auditoría de agentIA — 1 de octubre de 2026 (Lima)

## Alcance y conclusión

La carpeta corresponde a la rama **`levantando_observaciones`**, commit **`3e696a4`**, coincidente con la primera captura de GitHub. Se preservó la modificación local previa de `backend/app/ssl_compat.py`. No se modificó código de la aplicación.

Se revisaron backend FastAPI, frontend React, proveedores LLM, requisitos, arquitectura, modelos y SQL, generación por etapas, sandbox, estados y persistencia, controles de ejecución, auditoría de seguridad, exportación, Git, DevOps, playground y registro de costes. Se recorrieron las diez pestañas mediante Edge/Playwright, con solicitudes enviadas al backend real aislado, sin respuestas HTTP simuladas.

**El sistema genera código mediante DeepSeek, pero no ofrece todavía una verificación ni un aislamiento fiables.** Hay defectos reproducidos que permiten escribir y leer fuera del workspace, reutilizar información de otra sesión, exportar un proyecto bloqueado y declarar pruebas aprobadas que nunca se ejecutaron. Auto-Pilot falla antes de generar requisitos. La cancelación no detiene el trabajo del generador por grafo.

Todas las llamadas LLM iniciadas por la auditoría usaron la clave proporcionada y el proveedor DeepSeek. Se verificó la conexión real y se ejecutaron requisitos, arquitectura, validación de especificación y dos generaciones por etapas con `deepseek-flash`. No se ejecutaron las suites que sustituyen el LLM por respuestas preparadas. Se detectó que el propio módulo Modelos & SQL devuelve una respuesta prefabricada incluso cuando se le solicita DeepSeek: se registra como defecto, no como validación mediante IA.

La clave se suministró en memoria/variables de entorno, se ocultó en los registros y no se incluyó en estos scripts. Las pruebas de archivos utilizaron testigos desechables; la prueba de Git utilizó un token ficticio expresamente identificado como tal, sin publicar en un repositorio externo.

## Qué se comprobó

| Área | Resultado y evidencia |
|---|---|
| Rama y cambios locales | `levantando_observaciones`, `3e696a4`; solo cambio previo en SSL y nueva carpeta de auditoría. |
| Backend | Arranque real en puerto 8011, SQLite y directorios aislados en `runtime/`; servicios previos 8000/3000 conservados. |
| DeepSeek | Autenticación real aceptada. Lista de modelos y verificación de conexión reales. |
| Navegador | Diez pestañas, selección de proveedor, verificación, generación de requisitos, aprobación, cambio de sesión, arquitectura y cierre/reapertura de sesión. Sin errores JavaScript registrados en el recorrido. |
| Grafo de generación | Una ejecución completó las cinco etapas LLM; diario con `provider=deepseek`, `mode=MODEL` y artefactos persistidos. Terminó bloqueada correctamente al intentar verificar sin Docker. |
| Cancelación | Segunda ejecución real: cancelada al inicio, continuó creando archivos durante 270 segundos y terminó `BLOCKED`. |
| Verificación Java | **No ejecutada:** daemon de Docker inaccesible. No hay evidencia de compilación ni pruebas Java aprobadas. |
| Exportación y seguridad | Reproducciones de escape de rutas, escritura, respuestas de reparación falsas y evasión del quality gate. |
| Persistencia | Guardar/recargar requisitos y modelos; reiniciar backend; estados y métricas antes y después. |
| Git | Flujo original ejecutado en repositorio temporal, con remoto local inalcanzable y token ficticio; sin publicación externa. |
| Python | 127 módulos analizados sintácticamente; 588 funciones; sin errores de sintaxis. Esto no demuestra corrección funcional. |
| Frontend | TypeScript de producción y compilación Vite pasaron. `npm run build` completo falló por ausencia de `msw`/`msw/node` en la instalación local y errores derivados en archivos de pruebas. |

Los nombres de modelo se contrastaron con la documentación oficial y con la API real; **no se considera un error que aparezca `deepseek-flash`**. Referencias: [modelos de DeepSeek](https://api-docs.deepseek.com/api/list-models) y [documentación de precios/modelos](https://api-docs.deepseek.com/quick_start/pricing).

## Hallazgos reproducidos

P1: corregir antes de confiar en generación, verificación, acceso o publicación. P2: defecto funcional o de información que requiere corrección. Cada hallazgo indica su evidencia para distinguir un fallo ejecutado de una deducción del código.

### H01 — P1: Auto-Pilot falla con un proveedor real

`_get_or_create_draft` llama a `transform_requirements` con `chosen_provider` y `chosen_model`, argumentos inexistentes en la firma del servicio. Con DeepSeek y una sesión nueva termina con `TypeError`, sin generar requisitos. El monitor muestra el fallo y cero reparaciones.

Código: [pipeline_runner.py:264](/C:/Users/willi/Downloads/agentIA/backend/app/services/pipeline_runner.py:264), [requirements_service.py:228](/C:/Users/willi/Downloads/agentIA/backend/app/services/requirements_service.py:228). Evidencia: `api-results.json`, `ui-Monitor_Live.png`.

Corrección: unificar la firma y el contrato del proveedor/modelo; cubrir el arranque sin borrador con una llamada real autorizada.

### H02 — P1: una sesión utiliza los requisitos de otra

Tras aprobar requisitos de biblioteca en A, se seleccionó una sesión B de reservas de salas. La solicitud real de arquitectura desde B contenía el borrador de A y DeepSeek devolvió una arquitectura para `audit-library`. `selectSession` limpia el borrador solo cuando el identificador es nulo, no al cambiar entre sesiones. Puede guardar artefactos ajenos en la sesión seleccionada.

Código: [StudioContext.tsx:95](/C:/Users/willi/Downloads/agentIA/frontend/src/context/StudioContext.tsx:95). Evidencia: `browser-results.json`, `ui-cross-session.png`.

Corrección: mantener estado por sesión o limpiarlo y cargarlo al cambiar; asociar cada respuesta asíncrona al identificador que originó la solicitud.

### H03 — P1: reparación manual permite escribir fuera del workspace

Una ruta absoluta en `filePath` reemplaza el prefijo del workspace. La API, sin autenticación de usuario, modificó un archivo testigo externo al directorio de la sesión de `BEFORE` a `AFTER` y devolvió HTTP 200. No se requiere que exista la sesión.

Código: [routes_tests.py:222](/C:/Users/willi/Downloads/agentIA/backend/app/api/routes_tests.py:222). Evidencia: `api-results.json` y testigo bajo `runtime/`.

Corrección: rechazar rutas absolutas, resolver la ruta y comprobar pertenencia real al workspace; validar sesión y propietario antes de escribir.

### H04 — P1: dos rutas permiten leer archivos ajenos

La lectura de artefactos comprueba pertenencia con `str.startswith`; una carpeta hermana cuyo nombre empieza por el identificador de la sesión supera el control mediante `../...` y devuelve su archivo. La remediación de seguridad acepta una ruta absoluta existente y devuelve su contenido como `originalCode`, aunque esté fuera de la sesión.

Código: [routes_artifact.py:81](/C:/Users/willi/Downloads/agentIA/backend/app/api/routes_artifact.py:81), [routes_security.py:83](/C:/Users/willi/Downloads/agentIA/backend/app/api/routes_security.py:83). Evidencia: `api-results.json` (`AUDIT_SIBLING_FILE`), `extra-results.json` (lectura de testigo absoluto).

Corrección: aplicar el mismo control de rutas resueltas a toda lectura, restringido a una sesión autorizada.

### H05 — P1: el inicio de sesión no protege las API

Las solicitudes de lectura, creación y escritura funcionaron sin credenciales de usuario. El login solo comprueba sufijo de correo y longitud de contraseña en el navegador. Al cerrar sesión y recargar reaparece automáticamente el usuario de demostración. La clave LLM autentica al proveedor, no al usuario de agentIA.

Código: [AuthContext.tsx:31](/C:/Users/willi/Downloads/agentIA/frontend/src/context/AuthContext.tsx:31), [AuthContext.tsx:50](/C:/Users/willi/Downloads/agentIA/frontend/src/context/AuthContext.tsx:50), rutas de sesión y reparación. Evidencia: `browser-results.json`, solicitudes sin autenticación en `api-results.json`.

Corrección: definir explícitamente el modo de demostración; exigir autenticación y autorización de sesión en backend cuando se usa como sistema compartido.

### H06 — P1: Modelos & SQL devuelve datos prefabricados con DeepSeek

El servicio construye el cliente real y luego devuelve incondicionalmente `_mock_domain_model_response` sin invocarlo. La síntesis con clave válida respondió inmediatamente. El borrador real definía `Book.id` UUID, pero el modelo/DDL resultante lo convirtió a Long/bigint y no conservó todas las restricciones solicitadas. La refinación también usa reglas locales, y la síntesis de pruebas utiliza plantillas sin consultar al modelo.

Código: [model_sql_service.py:505](/C:/Users/willi/Downloads/agentIA/backend/app/services/model_sql_service.py:505), [model_sql_service.py:351](/C:/Users/willi/Downloads/agentIA/backend/app/services/model_sql_service.py:351), [test_analysis_service.py:115](/C:/Users/willi/Downloads/agentIA/backend/app/services/test_analysis_service.py:115). Evidencia: `draft.json`, `models.json`, `api-results.json`.

Corrección: usar la respuesta real del proveedor y validar tipos/restricciones contra el borrador; identificar expresamente las operaciones deterministas en la interfaz.

### H07 — P1: consultar la lista convierte un proyecto bloqueado en verificado

El grafo real terminó `BLOCKED/FAILED`, con cero pruebas ejecutadas y Docker inaccesible. Tras generar archivos DevOps, el cálculo por presencia de archivos alcanzó 100 %. Un `GET /sessions` escribió `COMPLETED/VERIFIED` en la base de datos. El resumen también declaró `testsPassed=true`, pese a conservar el error de verificación.

Código: [routes_session.py:439](/C:/Users/willi/Downloads/agentIA/backend/app/api/routes_session.py:439), [lifecycle_service.py:170](/C:/Users/willi/Downloads/agentIA/backend/app/services/lifecycle_service.py:170), [lifecycle_service.py:388](/C:/Users/willi/Downloads/agentIA/backend/app/services/lifecycle_service.py:388). Evidencia: `graph-state.json`, `final-results.json`.

Corrección: hacer las consultas libres de modificaciones; separar artefactos presentes de etapas ejecutadas y exigir evidencia de pruebas para `VERIFIED`.

### H08 — P1: después de reiniciar aparecen cinco pruebas ficticias aprobadas

Antes del reinicio, las métricas indicaban cero pruebas y verificación no realizada. Después, la API de métricas devolvió cinco pruebas, cinco aprobadas, `allPassed=true` y 2150 ms. El fallback depende de `COMPLETED` y no lee las métricas persistidas. El detalle de la misma sesión seguía reconociendo el fallback por Docker inaccesible.

Código: [routes_artifact.py:108](/C:/Users/willi/Downloads/agentIA/backend/app/api/routes_artifact.py:108). Evidencia: `final-results.json`, `restart-results.json`, métricas originales en `graph-state.json`.

Corrección: leer la evidencia persistida; si falta, devolver estado desconocido/no ejecutado, nunca números de ejemplo.

### H09 — P1: cancelar no detiene la generación ni conserva el estado terminal

Se inició otro grafo real, se canceló al segundo y la API devolvió 204 con estado `CANCELLED`. El trabajador siguió generando: pasó de 6 a 24 archivos y, a los 270 segundos, reemplazó la cancelación por `BLOCKED`. La ruta solo cambia el estado y libera el puesto de cola; no detiene el trabajador, que continúa consumiendo llamadas al proveedor.

Código: [routes_session.py:626](/C:/Users/willi/Downloads/agentIA/backend/app/api/routes_session.py:626), [routes_session.py:347](/C:/Users/willi/Downloads/agentIA/backend/app/api/routes_session.py:347). Evidencia completa: `cancel-results.json`.

Corrección: cancelación cooperativa en cada etapa, control antes de llamadas/escrituras, y protección de estados terminales; liberar la capacidad cuando el trabajador realmente termina.

### H10 — P1: exportación alternativa elude el quality gate

En una sesión testigo, SAST detectó una violación alta y devolvió `BLOCKED/canExport=false`. La exportación normal respondió 403; la descarga del bundle respondió 200 e incluyó el mismo archivo. Además, el proyecto real sin verificación Java pudo exportarse por la ruta normal: esa ruta exige SAST pero no pruebas ejecutadas.

Código: [routes_orchestrator.py:194](/C:/Users/willi/Downloads/agentIA/backend/app/api/routes_orchestrator.py:194), [routes_publish.py:57](/C:/Users/willi/Downloads/agentIA/backend/app/api/routes_publish.py:57). Evidencia: `extra-results.json`, `final-results.json`.

Corrección: centralizar la política para todos los puntos de exportación/publicación y mostrar por separado permiso para descargar y permiso para publicar un proyecto verificado.

### H11 — P1: las preferencias arquitectónicas no llegan al generador real

La especificación enviada al grafo pidió arquitectura hexagonal y Gradle mediante `inputInterface`. Los artefactos reales usaron Maven y la estructura fija controller/service/repository/model. La inferencia aislada sí reconoció hexagonal/Gradle; el payload de las etapas no transporta el plan ni la interfaz. El alcance fijo de artefactos limita las salidas al perfil anterior.

Código: [runner.py:491](/C:/Users/willi/Downloads/agentIA/backend/app/orchestrator/stages/runner.py:491). Evidencia: `probe_extra.py`, `static-results.json`, `graph-state.json`, workspace de la generación.

Corrección: persistir y propagar un plan único al generador, al verificador, a DevOps y a la interfaz; validar la salida contra ese plan.

### H12 — P1: seleccionar un modelo no determina el modelo usado al generar

La verificación admite un modelo seleccionado, pero las solicitudes de requisitos del navegador solo envían texto, nombre, proveedor y clave; omiten el modelo. Los flujos de generación conservan sus valores por defecto. Cambiar el modelo después de verificar tampoco invalida `isVerified`: el navegador conserva la marca positiva correspondiente al modelo anterior.

Código: [requirementsService.ts:18](/C:/Users/willi/Downloads/agentIA/frontend/src/services/requirementsService.ts:18), [LlmContext.tsx:102](/C:/Users/willi/Downloads/agentIA/frontend/src/context/LlmContext.tsx:102). Evidencia: contratos y solicitudes reales en `browser-results.json`. No se ejecutó deliberadamente una generación con otro proveedor.

Corrección: transportar proveedor/modelo en todos los contratos y guardar la procedencia; verificar una combinación exacta de proveedor, modelo y credencial.

### H13 — P1: publicar Git guarda temporalmente el token en disco

El flujo original incorpora el token a la URL y la guarda como remoto en `.git/config` antes del push. Una prueba con token ficticio observó ese valor en disco durante la ejecución. En el fallo normal el `finally` lo limpió; una interrupción del proceso puede dejarlo persistido. No se probó con un token real ni se publicó externamente.

Código: [git_service.py:67](/C:/Users/willi/Downloads/agentIA/backend/app/services/git_service.py:67). Evidencia: `git-results.json`.

Corrección: suministrar credenciales mediante un mecanismo efímero de Git sin insertarlas en la configuración del repositorio.

### H14 — P2: guardar requisitos pierde entidades y cambia el paquete

El borrador real tenía una entidad y paquete `com.audit.library`. Tras guardar y consultar volvió con `entities=[]`, sin supuestos y paquete reconstruido como `com.corp.audit.library`. El guardado solo persiste historias; el GET reconstruye un borrador incompleto. La aprobación del navegador sin `markdownSpec` también conserva el texto inicial en lugar de la especificación aprobada completa.

Código: [routes_requirements.py:194](/C:/Users/willi/Downloads/agentIA/backend/app/api/routes_requirements.py:194), [routes_requirements.py:225](/C:/Users/willi/Downloads/agentIA/backend/app/api/routes_requirements.py:225). Evidencia: `draft.json`, `api-results.json`, solicitudes de aprobación en `browser-results.json`.

Corrección: persistir el borrador completo con versión y reconstruir exactamente los mismos datos al recargar.

### H15 — P2: guardar Modelos & SQL no materializa el SQL aprobado

La operación respondió `SAVED` y escribió `domain_model.json`, pero no creó `schema.sql` ni `data.sql`; la etapa de datos seguía sin iniciar según la detección de artefactos. El estado visual guardado y el workspace consumido por pasos posteriores divergen.

Código: [routes_models_sql.py:104](/C:/Users/willi/Downloads/agentIA/backend/app/api/routes_models_sql.py:104). Evidencia: `api-results.json`, `models.json`.

Corrección: definir y persistir conjuntamente el modelo, sus scripts y la evidencia de aprobación de la etapa.

### H16 — P1: reparación informa éxito y verificación sin ejecutarlas

Una reparación con archivo y sesión inexistentes devolvió 200, `diagnosticsResolved=true` y mensaje de que se está repitiendo la verificación, aunque no la invoca. Los errores de archivo se ocultan. Consultar reparaciones de una sesión inexistente devuelve `VERIFIED` por defecto. El mismo falso positivo aparece en la sesión real bloqueada sin Docker.

Código: [routes_tests.py:177](/C:/Users/willi/Downloads/agentIA/backend/app/api/routes_tests.py:177), [routes_tests.py:235](/C:/Users/willi/Downloads/agentIA/backend/app/api/routes_tests.py:235). Evidencia: `api-results.json`, `final-results.json`.

Corrección: validar sesión/archivo, exponer fallos de escritura y ejecutar o programar verificación real; responder pendiente hasta obtener resultados.

### H17 — P2: auditoría sin código otorga PASS y permiso de exportar

Una sesión vacía obtuvo puntuación 100, `PASS` y `canExport=true`, sin archivos evaluables. Esto representa ausencia de hallazgos como garantía de calidad y puede habilitar acciones posteriores sin evaluación.

Evidencia: `api-results.json`, `extra-results.json`; entrada de auditoría en [routes_security.py:40](/C:/Users/willi/Downloads/agentIA/backend/app/api/routes_security.py:40).

Corrección: devolver `NOT_EVALUATED` para entradas vacías y separar cobertura del escaneo de su puntuación.

### H18 — P2: pausar una sesión inactiva devuelve éxito

Se pausó una sesión sin pipeline activo. La API devolvió 200/PAUSED. El controlador permite establecer el estado aunque no exista un trabajador que pueda pausarse, por lo que el estado no representa una operación real.

Código: [pipeline_runner.py:142](/C:/Users/willi/Downloads/agentIA/backend/app/services/pipeline_runner.py:142). Evidencia: `api-results.json`.

Corrección: validar transiciones y existencia del proceso antes de confirmar controles.

### H19 — P2: el diagrama presenta atributos que no pertenecen al modelo

El visor muestra `id: Long`, `createdAt: Instant` y `status: String` mediante contenido fijo; no representa fielmente el código/diagrama suministrado. En el recorrido aparece un modelo de biblioteca con esos atributos aunque el borrador real contiene UUID, ISBN, título y autor. Puede inducir al usuario a aprobar una estructura que no ha sido generada.

Código: [MermaidViewer.tsx:99](/C:/Users/willi/Downloads/agentIA/frontend/src/components/common/MermaidViewer.tsx:99). Evidencia: `ui-3__Modelos___SQL.png`, `browser-results.json`, `draft.json`.

Corrección: renderizar el diagrama recibido o construirlo a partir de las entidades reales; evitar atributos decorativos presentados como datos.

### H20 — P2: el monitor atribuye cualquier bloqueo a reparaciones agotadas

El monitor del fallo de Auto-Pilot indicó que se agotaron cinco intentos, mientras la sesión y el contador mostraban cero. Un error de argumentos o la falta de Docker no implica haber ejecutado cinco reparaciones.

Código: [GenerationMonitorView.tsx:396](/C:/Users/willi/Downloads/agentIA/frontend/src/views/GenerationMonitorView.tsx:396). Evidencia: `ui-Monitor_Live.png`, estado en `api-results.json`.

Corrección: mostrar la causa persistida y condicionar el mensaje de agotamiento al número de intentos realmente realizados.

### H21 — P2: el coste de la sesión no se agrega al terminar

La ejecución real dejó cinco registros de llamadas con uso y coste, pero cero agregados de sesión y `cost_record_json` nulo tras finalizar. Existe una función de agregación, sin integración en las rutas de terminación revisadas. Las llamadas guiadas fuera del contexto de registro tampoco tienen la misma cobertura de costes.

Código: [aggregate.py:30](/C:/Users/willi/Downloads/agentIA/backend/app/cost/aggregate.py:30). Evidencia: `cost-results.json`, fila de sesión en `graph-state.json`.

Corrección: agregar al finalizar, fallar o cancelar de forma idempotente; delimitar y mostrar qué llamadas están contabilizadas. Los importes registrados son estimaciones del sistema, no una comprobación de facturación del proveedor.

## Hallazgos adicionales por revisión del código

Estos cuatro hallazgos tienen un recorrido de código identificable, pero **no se reprodujeron funcionalmente**. El fallo temprano de Auto-Pilot y la falta de Docker impidieron alcanzar algunas rutas. No se presentan como despliegues o pruebas ejecutadas.

### H22 — P1: Auto-Pilot puede finalizar después de fallar la verificación

En `_execute_pipeline_steps`, `build_success=false` emite un bloqueo pero no termina la función. Continúa con seguridad y DevOps y luego escribe `COMPLETED/VERIFIED`. Corregir H01 puede hacer accesible esta ruta.

Código: [pipeline_runner.py:641](/C:/Users/willi/Downloads/agentIA/backend/app/services/pipeline_runner.py:641), [pipeline_runner.py:700](/C:/Users/willi/Downloads/agentIA/backend/app/services/pipeline_runner.py:700). Corrección: detener o entrar en reparación cuando falla la verificación; impedir éxito sin pruebas reales.

### H23 — P2: la fase objetivo de Auto-Pilot se ignora

`target_phase` se recibe y se pasa al trabajador, pero no controla las etapas ejecutadas. Una petición de detenerse en requisitos puede recorrer las etapas posteriores. La reanudación tampoco conserva todo el contrato original de ejecución.

Código: [pipeline_runner.py:319](/C:/Users/willi/Downloads/agentIA/backend/app/services/pipeline_runner.py:319), [pipeline_runner.py:794](/C:/Users/willi/Downloads/agentIA/backend/app/services/pipeline_runner.py:794). Corrección: persistir el plan de ejecución y comprobar su límite antes de cada etapa.

### H24 — P1: Auto-Pilot no usa el mismo límite de concurrencia que el grafo

La creación por grafo encola y adquiere un puesto de `queue_manager`; el arranque de Auto-Pilot crea su propio hilo sin ese control compartido. El límite configurado no cubre todos los caminos de generación. H09 además demuestra que la cancelación libera capacidad mientras continúa el trabajo.

Código: [routes_session.py:559](/C:/Users/willi/Downloads/agentIA/backend/app/api/routes_session.py:559), [pipeline_runner.py:794](/C:/Users/willi/Downloads/agentIA/backend/app/services/pipeline_runner.py:794). Corrección: usar un ejecutor/cola común y vincular los puestos a trabajadores efectivos.

### H25 — P1: un despliegue nuevo no asigna el identificador requerido por Playground

`deploy_local` crea y conserva una sesión con `containerId` nulo; después de Compose exitoso cambia estado/salud sin asignar el identificador. La recuperación que sí asigna ese dato se usa cuando no existe sesión en memoria. Playground rechaza cualquier sesión sin `containerId`. Un despliegue nuevo puede aparecer saludable y aun así ser rechazado hasta recuperar el estado.

Código: [docker_service.py:205](/C:/Users/willi/Downloads/agentIA/backend/app/services/docker_service.py:205), [docker_service.py:246](/C:/Users/willi/Downloads/agentIA/backend/app/services/docker_service.py:246), [playground_proxy.py:89](/C:/Users/willi/Downloads/agentIA/backend/app/services/playground_proxy.py:89). Corrección: consultar y asignar el contenedor propio tras Compose; validar también su puerto y pertenencia.

## Orden recomendado de reparación

1. **Acceso y archivos:** H03, H04, H05 y H13. Centralizar autorización y resolución segura de rutas.
2. **Veracidad de resultados:** H07, H08, H10, H16 y H22. Un único estado persistido basado en evidencias reales; nunca aprobar por presencia de archivos o valores de ejemplo.
3. **Control de ejecución:** H01, H09, H18, H23 y H24. Unificar el ejecutor, sus contratos y sus transiciones.
4. **Integridad de generación:** H02, H06, H11, H12, H14 y H15. Aislar sesiones, preservar borradores y propagar preferencias/procedencia.
5. **Interfaz y operación:** H17, H19, H20, H21 y H25. Mostrar cobertura, resultados y disponibilidad efectivos.

## Evidencias y reproducción

Todos los archivos siguientes están junto a este informe. Los scripts contienen los pasos concretos y leen `AUDIT_DEEPSEEK_KEY` del entorno cuando necesitan IA. Para repetirlos, levantar primero `run_backend.py` desde la raíz del proyecto y usar una copia nueva de `runtime/` si se quieren evitar estados acumulados. El navegador usa el frontend existente en 3000 y redirige las solicitudes al backend real 8011. No ejecutar indiscriminadamente todos los scripts: algunos reinician estados, generan llamadas de pago o escriben testigos para comprobar vulnerabilidades.

| Archivo | Contenido |
|---|---|
| `api-results.json` / `probe_api.py` | Contratos HTTP, requisitos, arquitectura, modelos, persistencia, rutas y Auto-Pilot. |
| `browser-results.json` / `probe_browser.cjs` | Navegación, solicitudes saneadas, textos visibles, estado de login y selección del modelo. |
| `extra-results.json` / `probe_extra.py` | Especificación real, inicio del grafo, quality gate, bundles, lectura y playground. |
| `graph-state.json` / `collect_runtime.py` | Estado original bloqueado, artefactos, procedencia, diario y métricas persistidas. |
| `final-results.json` / `probe_final.py` | Falsa promoción por GET, resumen, reparaciones y exportación sin pruebas. |
| `restart-results.json` / `probe_restart.py` | Métricas fabricadas después de reiniciar. |
| `cancel-results.json` / `probe_cancel.py` | Evolución temporal completa después de cancelar. |
| `git-results.json` / `probe_git.py` | Observación del token ficticio en configuración del repositorio temporal. |
| `cost-results.json` | Registros reales de llamadas y ausencia de agregado de sesión. |
| `static-results.json` / `probe_static.py` | Sintaxis Python y comprobación de inferencia de arquitectura. |
| `draft.json`, `architecture.json`, `models.json` | Salidas de los flujos revisados para comparar semántica. |
| `ui-*.png` | Capturas del navegador: requisitos, modelos, arquitectura, cambio de sesión y monitor. |
| `runtime/` | Base de datos y workspaces aislados, con artefactos reales y testigos de auditoría. |

## Límites de la revisión

- No fue posible verificar compilación Java, pruebas herméticas, arranque de contenedores, conectividad de base de datos ni un despliegue Docker saludable: el daemon no estaba disponible. Ese límite **no** valida el código Java generado.
- No se realizó push a un repositorio externo; la prueba de Git comprobó el manejo local de credenciales y el fallo de conexión.
- No se ejecutaron suites que sustituyen el proveedor de IA, ni se evaluaron otros proveedores. Las pruebas sintácticas y de contratos no invocan un LLM.
- El recorrido del navegador y la revisión de módulos no constituyen cobertura exhaustiva de todas las combinaciones de entradas, carreras ni entornos de producción. Se incluyen pasos y evidencia para continuar con pruebas dirigidas después de reparar los bloqueos.
- La falta local de `msw` se clasifica como limitación de instalación/build, no como demostración de un defecto de lógica de producción. No se reinstalaron dependencias del usuario.
- Se conservó el cambio previo de compatibilidad SSL/UUID, por lo que la ejecución corresponde al commit indicado más esa modificación local existente.

La auditoría deja **21 hallazgos reproducidos y 4 adicionales por revisión del código**. No se aplicaron reparaciones: el resultado es un diagnóstico con evidencia y prioridades.
