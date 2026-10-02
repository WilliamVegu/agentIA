# Verificación del commit 61c0f29 — 2 de octubre de 2026

**El conjunto sigue parcialmente corregido.** Se resolvieron los errores concretos de proveedor DeepSeek, imports de Modelos & SQL, escritura mediante `..` y token Git en `.git/config`. Se reprodujeron problemas pendientes de verificación, exportación, concurrencia, auditoría vacía y arquitectura.

Rama: `levantando_observaciones`. Commit: `61c0f29 arreglismos`. El árbol estaba limpio al empezar. Esta revisión creó únicamente archivos en `reports/verify-61c0f29/`; no modificó la aplicación.

## Pruebas realizadas

Se repitieron las solicitudes contra un backend real aislado en 8011, con almacenamiento nuevo. Se usó la clave autorizada en memoria y DeepSeek real para requisitos, arquitectura, modelos, una ejecución de Auto-Pilot hasta CODE_TESTS, otra hasta STORIES y un grafo de cinco etapas con preferencias hexagonal/Gradle. Ninguna respuesta de IA ni HTTP fue sustituida.

Edge recorrió las diez pestañas, comprobó conexión DeepSeek, cambio de modelo, cambio de sesión y logout/recarga. El primer recorrido tuvo un fallo de selector del script: Monitor Live incorpora un contador al tener ejecuciones activas. Se ajustó exclusivamente el selector del script y se repitió el recorrido completo sin errores de aplicación registrados.

`npm run build` pasó con TypeScript y Vite; queda el aviso de bundle mayor de 500 kB. Se analizaron sintácticamente 128 módulos Python sin errores. También se probó Git con un token ficticio y un destino local inalcanzable, sin publicar externamente. La comprobación de concurrencia usa el gestor real y sus primitivas, sin ejecutar ni simular un LLM.

Docker continúa inaccesible. **No se ejecutaron pruebas Java ni un despliegue saludable.** Se reinició el backend aislado para comprobar la persistencia de métricas. Los servicios anteriores en 8000 y 3000 se conservaron.

## Los seis problemas destacados en la respuesta anterior

| Problema | Resultado actual | Evidencia |
|---|---|---|
| Requisitos enviaba DeepSeek a OpenAI | **Corregido en la reproducción.** La misma solicitud responde 200; el servicio utiliza proveedor/modelo resueltos. Auto-Pilot también generó requisitos. | `api-results.json`, diario y estado de Auto-Pilot. |
| Modelos & SQL fallaba con `EntityAttribute` | **Corregido ese error.** Llamada real sin NameError; salida conserva UUID e ISBN único. Sigue existiendo fallback silencioso ante errores del proveedor, por código. | `real-model-results.json`, `model_sql_service.py:605`. |
| Guardado con `..` fuera del workspace | **Corregido en las rutas probadas.** Modelos y requisitos rechazan el identificador con 400; no se crea archivo externo. Guardar modelos para un identificador inexistente aún devuelve 200. | `focus-results.json`, `extra-results.json`. |
| Git guardaba el token en disco | **Corregido para ejecución real.** La traza no encuentra el token en `.git/config`. La URL autenticada pasa como argumento del proceso de Git, por lo que no es un diseño exclusivamente en memoria del servidor. | `git-results.json`, `git_service.py:106`. |
| Gradle/hexagonal ignorados | **Parcial.** Se generaron `build.gradle` y `settings.gradle`; dominio, servicio y controladores conservaron la arquitectura de cuatro capas. Sandbox y DevOps aún ejecutan Maven. | `graph-state.json`, workspace del grafo, instrucciones de dominio/servicio. |
| Exportaciones y verificación falsas/API abierta | **Parcial.** BLOCKED ya no exporta. Auto-Pilot COMPLETED con cero pruebas sí exporta y su historial dice VERIFIED. Las API siguen sin autenticación real. | `final-results.json`, `autopilot-api-results.json`, solicitud sin autenticación. |

## Fallos reproducidos que siguen pendientes

### P1 — Auto-Pilot marca COMPLETED y permite exportar sin pruebas

La ejecución `7d15e3fe-e207-40f6-8dc1-aae3a24f6869`, con DeepSeek real y objetivo CODE_TESTS, completó las cinco etapas de generación. Al no poder ejecutar Docker persistió:

```json
{"totalTests":0,"passedTests":0,"allPassed":false,"fallback_used":true}
```

Aun así terminó `COMPLETED/INITIALIZATION`, su historial de reparación devolvió `finalState="VERIFIED"` y tanto exportación normal como bundle respondieron **200**. El control nuevo solo prohíbe exportar cuando el estado es BLOCKED; la otra vía sigue abierta.

Una segunda ejecución real, con objetivo STORIES, terminó también COMPLETED y el historial informó VERIFIED, aunque solo existían `spec.md`, `user_stories.json` y el reporte de auditoría, con cero pruebas. Haber alcanzado una fase parcial no equivale a verificar un proyecto.

Código: [pipeline_runner.py:689](/C:/Users/willi/Downloads/agentIA/backend/app/services/pipeline_runner.py:689), [routes_tests.py:191](/C:/Users/willi/Downloads/agentIA/backend/app/api/routes_tests.py:191), [routes_publish.py:45](/C:/Users/willi/Downloads/agentIA/backend/app/api/routes_publish.py:45). Evidencias: `autopilot-state.json`, `autopilot-api-results.json`, `target-results.json`.

### P1 — El límite de concurrencia no es compartido

El gestor tiene un `asyncio.Semaphore` para el grafo y otro `threading.Semaphore` para Auto-Pilot, cada uno con la capacidad completa. Con `max_concurrent=1`, adquirir un puesto asíncrono y después uno síncrono permitió **dos trabajadores activos**. No bloqueó el segundo.

No se sustituyeron primitivas ni servicios: se ejecutaron los métodos originales del gestor en una instancia local. Esta reproducción demuestra que la configuración no limita el conjunto de ambos flujos.

Código: [queue_service.py:12](/C:/Users/willi/Downloads/agentIA/backend/app/services/queue_service.py:12), [queue_service.py:53](/C:/Users/willi/Downloads/agentIA/backend/app/services/queue_service.py:53). Evidencia: `focus-results.json`, `probe_focus.py`.

### P1 — Las API siguen sin autenticar al usuario

Listado, creación y guardados siguen funcionando sin sesión autenticada. El nuevo control de workspace valida rutas, pero no identifica al usuario ni autoriza la propiedad del proyecto. El encabezado de correo enviado desde el navegador no se verifica como credencial.

Logout/recarga sí continúa corregido en el navegador. Ese resultado no protege las API.

Evidencias: `api-results.json`, `contract-results.json`, `browser-recheck.json`; revisión de `main.py` y rutas.

### P2 — La auditoría vacía está corregida solo en uno de los puntos de entrada

`audit_workspace` ahora bloquea un workspace sin código. Pero **POST `/api/v1/security/audit` con `files={}` y `pomXml=""` sigue devolviendo PASS, score 100 y `canExport=true`**, con cero líneas evaluadas. El endpoint no utiliza el nuevo control.

Código: [routes_security.py:28](/C:/Users/willi/Downloads/agentIA/backend/app/api/routes_security.py:28), [security_service.py:660](/C:/Users/willi/Downloads/agentIA/backend/app/services/security_service.py:660). Evidencia: `focus-results.json`.

### P1 — Gradle funciona al generar, pero no completa el resto del flujo

El grafo `330dab8e-c435-4fce-8ba3-dc46d67c705e` recibió preferencias hexagonal/Gradle y generó realmente archivos Gradle. Sin embargo, DOMAIN, SERVICE y CONTROLLER emitieron `model/entity`, `model/dto`, `repository`, `service/impl` y `controller`, en lugar de los componentes hexagonales solicitados.

Además, el Dockerfile generado contiene `COPY pom.xml .` y `RUN mvn clean package`, aunque ese workspace no tiene `pom.xml`. Sandbox ejecuta siempre `mvn test -o`. No se intentó un build Docker efectivo por indisponibilidad del daemon; la contradicción entre los archivos generados y el comando/configuración se comprobó directamente.

Código: [domain.md:13](/C:/Users/willi/Downloads/agentIA/backend/app/resources/instructions/domain.md:13), [service.md:11](/C:/Users/willi/Downloads/agentIA/backend/app/resources/instructions/service.md:11), [docker_runner.py:149](/C:/Users/willi/Downloads/agentIA/backend/app/sandbox/docker_runner.py:149), [devops_service.py:18](/C:/Users/willi/Downloads/agentIA/backend/app/services/devops_service.py:18). Evidencia: `graph-state.json`, `final-results.json`, workspace bajo `runtime/workspaces/330dab8e-c435-4fce-8ba3-dc46d67c705e/`.

## Pendientes comprobados por revisión de código

- **Modelo elegido en la interfaz:** los servicios admiten modelo, pero `RequirementsView` y `ArchitectureView` siguen extrayendo únicamente proveedor/clave de `useLlm` y no envían el modelo seleccionado. Cambiar modelo invalida correctamente la verificación, como se comprobó en navegador.
- **Fallback silencioso de Modelos & SQL:** la llamada correcta funciona, pero `except Exception` sigue devolviendo un modelo local a partir del borrador. Un fallo real del proveedor puede parecer una síntesis correcta. Refinación mantiene reglas locales. No se provocó un fallo de proveedor enviando la clave a otro servicio.
- **Reparación manual:** devuelve honestamente `diagnosticsResolved=false`, pero no ejecuta/programa la verificación pendiente.
- **VERIFIED sin métricas:** el overview ya prioriza métricas reales cuando existen, pero si no existen sigue confiando solo en el enum VERIFIED. No equivale a evidencia de ejecución.
- **Cancelación:** el código de la ruta del grafo no cambió respecto de la revisión anterior, que conservaba CANCELLED pero dejaba terminar la operación en curso y liberaba el puesto antes del fin del trabajador. No se repitió otra generación cancelada en esta revisión.
- **Despliegue:** se eliminó el identificador ficticio del contenedor; sigue dependiendo del parsing del texto de Compose. No se validó la recuperación de identidad/puerto real por falta de Docker.

## Estado de los hallazgos anteriores

| ID | Estado en esta revisión |
|---|---|
| H01 | Arranque/proveedor corregidos con DeepSeek real; verificación final sigue pendiente en H22. |
| H02 | Corregido en cambio normal de sesión: B vacía no envía el borrador de A. No se probaron carreras. |
| H03–H04 | Reproducciones de rutas absoluta, relativa y carpeta hermana rechazadas. |
| H05 | Parcial: logout corregido, autorización de API pendiente. |
| H06 | Parcial: imports corregidos y llamada real funciona; fallback/refinación pendientes. |
| H07 | Parcial: sesión BLOCKED real permanece bloqueada al listar; persiste confusión con sesiones parciales COMPLETED. |
| H08 | Reproducción corregida: reinicio conserva cero pruebas y fallback real. |
| H09 | No se repitió cancelación; código del grafo mantiene la limitación anterior. |
| H10 | Parcial: BLOCKED devuelve 403; Auto-Pilot no verificado con COMPLETED devuelve 200. |
| H11 | Parcial: Gradle generado; arquitectura y herramientas posteriores no completan el contrato. |
| H12 | Parcial: verificación se invalida; vistas no envían modelo elegido. |
| H13 | Reproducción de persistencia en `.git/config` corregida; token en argumentos de Git. |
| H14 | Backend conserva los datos y materializa markdown ausente. La comparación literal del script mostró False únicamente por el nuevo campo `isUnique=false` agregado por el esquema; no representa pérdida de los campos antiguos. El cliente aún reconstruye datos al aprobar. |
| H15 | SQL se guarda; nuevo escape `..` rechazado. Sesión inexistente aún aceptada en guardado de modelos. |
| H16 | Parcial: historial de BLOCKED corregido; sesiones COMPLETED sin pruebas siguen con finalState VERIFIED. Reparación no verifica. |
| H17 | Parcial: workspace vacío bloqueado; payload vacío aprobado. |
| H18 | Reproducción corregida: pausa sin trabajador devuelve 400. |
| H19 | Parser de arquitectura actualizado por revisión; build pasa. La interfaz aún anuncia cuatro capas. No se validó exhaustivamente sintaxis Mermaid. |
| H20 | Se conserva la corrección de mensajes por contador; navegador recorrió Monitor Live sin error de aplicación. |
| H21 | Agregados presentes para grafo terminal y salidas por fase objetivo. Cobertura uniforme de llamadas guiadas sigue pendiente. |
| H22 | Pendiente: reproducción real termina COMPLETED sin verificación y permite exportar. |
| H23 | Parcial: objetivo STORIES sí detiene y persiste finalización/coste; se etiqueta como proyecto COMPLETED y reparación VERIFIED sin pruebas. |
| H24 | Pendiente: dos semáforos independientes exceden la capacidad compartida. |
| H25 | Sin prueba funcional de despliegue; eliminado identificador ficticio, parsing permanece. |

## Evidencias y límites

Los archivos de esta carpeta contienen nuevas respuestas, diarios y scripts: `api-results.json`, `real-model-results.json`, `git-results.json`, `contract-results.json`, `focus-results.json`, `graph-state.json`, `autopilot-state.json`, `autopilot-api-results.json`, `target-results.json`, `final-results.json`, `restart-results.json`, `browser-recheck.json` y `cost-results.json`.

El grafo terminó honestamente BLOCKED con cero pruebas por Docker inaccesible. Tras reiniciar conserva esas métricas y `testsPassed=false`. Auto-Pilot, en cambio, declara COMPLETED en la misma situación: esa diferencia es parte del defecto reproducido, no una aprobación de su código Java.

No se publicaron repositorios ni se aplicaron cambios a la aplicación. Los testigos de archivos y de estados heredados se construyeron únicamente en almacenamiento aislado; no se confundieron con salidas del modelo. Las llamadas externas autorizadas utilizaron DeepSeek y datos ficticios de biblioteca. No hay evidencia para afirmar que todo el sistema esté corregido.
