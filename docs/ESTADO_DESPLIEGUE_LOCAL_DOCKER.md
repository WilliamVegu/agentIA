# Estado del despliegue local mediante Docker — AgentIA

## Referencia de esta conversación

- **Fecha de revisión y consolidación:** 4 de octubre de 2026, zona America/Lima.
- **Repositorio revisado:** `C:\Users\willi\Downloads\agentIA`.
- **Objetivo del usuario:** conseguir que toda la parte de despliegue local mediante Docker sea funcional y efectiva.
- **Alcance autorizado inicialmente:** analizar el sistema y verificar su estado actual; no implementar correcciones todavía.
- **Solicitud posterior:** consolidar la información obtenida en este Markdown y consultarlo durante esta conversación.
- **Autorización vigente:** el usuario pidió comenzar la implementación del plan y actualizar este documento.
- **Estado general:** implementación parcial; despliegue básico real demostrado en seis combinaciones, con aceptación integral y pendientes del plan todavía abiertos.
- **Plan vigente:** [PLAN_IMPLEMENTACION_DESPLIEGUE_LOCAL.md](C:/Users/willi/Downloads/agentIA/docs/PLAN_IMPLEMENTACION_DESPLIEGUE_LOCAL.md), creado después de las aclaraciones del usuario. GitLab remoto queda aplazado; Docker opcional por sesión es la prioridad.

**Lectura actual:** consultar primero la sección 44 (correcciones tras prueba DeepSeek/Docker), sección 43 (entrega ejecutable, CI/Kubernetes y operaciones) y después los bloques anteriores. Los conteos de tareas y pendientes de cada sección corresponden a su fecha; esta corrección no cierra anticipadamente el plan completo.

### Cómo mantener esta referencia

**Última continuación:** sección [42, Gradle y cachés](#42-compatibilidad-gradle-y-caches-privadas-t15). T15 implementada; **32/54 marcadas y 22 sin marcar**. Contenedores de aceptación retirados; instancia manual sigue detenida. Conteos históricos corresponden a su fecha.

**Instancia para prueba manual:** detenida al cerrar sección 31, después de que el usuario indicó que ya no necesitaba mantener AgentIA activo. Se verificaron ejecutable/comando/PID de los procesos de prueba; se detuvieron backend 12892 y frontend 9832 (su launcher 6564 terminó junto con el hijo). .run/local-app-processes.json conserva stoppedAt/stoppedPids y los logs. No se borraron ni alteraron estados de sesiones en BD. Las comprobaciones UP/HTTP 200 de sección 30 son históricas. Un nuevo arranque cargará el código actualizado; todavía falta aceptación del recorrido completo en navegador/backend.

1. Consultar este archivo antes de continuar con análisis, propuestas, cambios o verificaciones relacionados con Docker en esta conversación.
2. Mantener los identificadores de los hallazgos y actualizar su estado cuando haya evidencia nueva.
3. Separar lo observado en el entorno, lo comprobado en código, las reproducciones con dependencias simuladas y las pruebas con contenedores reales.
4. No marcar un problema como corregido o un despliegue como funcional únicamente porque se generaron archivos o una prueba con mocks pasó.
5. Registrar cambios y verificaciones posteriores en la bitácora final. Una observación del entorno representa la fecha de su comprobación, no una condición permanente.
6. No incorporar claves API, tokens, contraseñas reales ni el contenido completo de los archivos `.env`.

Este documento es una referencia de trabajo para esta conversación. No amplía por sí mismo la autorización para modificar, desplegar o eliminar recursos.

## 1. Alcances distintos de Docker

| Alcance | Estado actual |
|---|---|
| Contenerizar y desplegar la plataforma AgentIA: frontend React/Vite y backend FastAPI | No se encontró Dockerfile ni Compose propios de la plataforma en la raíz, frontend o backend. El arranque documentado utiliza Python, Node y scripts locales. |
| Verificar los microservicios Java generados | Existe sandbox Docker sin red, con soporte de comandos Maven y Gradle. Requiere motor accesible, imagen y caché de dependencias disponibles. |
| Desplegar los microservicios generados desde DevOps | Existen generadores, endpoints, ejecución Compose, estado, parada y smoke test. Presenta los defectos registrados en este documento. |

La existencia de Dockerfiles en `backend/workspaces` o `reports/**/runtime/workspaces` corresponde a proyectos generados, no a la contenerización de AgentIA.

Fuentes: [README.md](C:/Users/willi/Downloads/agentIA/README.md), [run_all.ps1](C:/Users/willi/Downloads/agentIA/run_all.ps1), [vite.config.ts](C:/Users/willi/Downloads/agentIA/frontend/vite.config.ts).

## 2. Componentes y flujo actual

| Componente | Responsabilidad |
|---|---|
| [config.py](C:/Users/willi/Downloads/agentIA/backend/app/config.py) | Habilitación de Docker, imagen, caché Maven y directorio de workspaces. |
| [devops_service.py](C:/Users/willi/Downloads/agentIA/backend/app/services/devops_service.py) | Generar Dockerfile, `.dockerignore`, Compose, CI/CD y Kubernetes; añadir Actuator y drivers a los archivos de construcción. |
| [docker_service.py](C:/Users/willi/Downloads/agentIA/backend/app/services/docker_service.py) | Comprobar daemon, ejecutar Compose en segundo plano, registrar estado y logs, recuperar contenedores por sesión, detener y probar salud. |
| [routes_devops.py](C:/Users/willi/Downloads/agentIA/backend/app/api/routes_devops.py) | API de generación, despliegue, estado, logs, parada, smoke test y playground. |
| [devops.py](C:/Users/willi/Downloads/agentIA/backend/app/models/devops.py) | Contratos de manifiestos, despliegue y smoke test. |
| [DevOpsDeploymentView.tsx](C:/Users/willi/Downloads/agentIA/frontend/src/views/DevOpsDeploymentView.tsx) | Interfaz de manifiestos, controles, terminal y pruebas REST. |
| [devopsService.ts](C:/Users/willi/Downloads/agentIA/frontend/src/services/devopsService.ts) | Cliente HTTP y tipos del frontend. |
| [docker_runner.py](C:/Users/willi/Downloads/agentIA/backend/app/sandbox/docker_runner.py) | Verificación hermética mediante `docker run --network none`. |
| [lifecycle_artifacts.py](C:/Users/willi/Downloads/agentIA/backend/app/services/lifecycle_artifacts.py) | Materializar documentos y colocar `schema.sql` también en el classpath del proyecto. |
| [pipeline_runner.py](C:/Users/willi/Downloads/agentIA/backend/app/services/pipeline_runner.py) | Integrar generación de manifiestos, verificación y despliegue opcional en el pipeline. |

### API disponible

Rutas bajo `/api/v1/devops/{session_id}`:

- `POST /generate`: audita el workspace y genera manifiestos con motor de BD y puerto indicados.
- `POST /deploy`: audita el workspace, genera manifiestos si no existe Compose e inicia el despliegue.
- `GET /status`: consulta el registro y comprueba salud; puede recuperar identidad desde Docker.
- `GET /logs`: devuelve historial en memoria.
- `GET /logs/stream`: ofrece un generador SSE.
- `POST /stop`: ejecuta Compose down.
- `POST /smoke-test`: consulta el health endpoint.
- `POST /playground`: proxy hacia el servicio desplegado.
- `GET /playground/resources`: descubre las rutas REST del código generado.

### Secuencia de despliegue

1. Resolver sesión, workspace y nombre del servicio.
2. Ejecutar `audit_workspace` y exigir `qualityGate.canExport`.
3. Si falta `docker-compose.yml`, generar los activos.
4. Comprobar Docker con `docker info`, timeout de 2 segundos, siempre que `DOCKER_ENABLED` esté activo.
5. Registrar `BUILDING` y lanzar un hilo daemon.
6. Ejecutar `docker compose -p <session_id> up -d`, añadiendo `--build` cuando se solicita.
7. Leer salida de Compose y consultar `docker compose -p <session_id> ps --format json`.
8. Obtener identidad del contenedor de aplicación, contenedor de BD y puerto publicado con destino 8080.
9. Ejecutar hasta 20 intentos del smoke test automático, separados por 2 segundos y con timeout HTTP de 3 segundos por intento.
10. Registrar `HEALTHY` si Actuator devuelve HTTP 200 y `status=UP`; en caso contrario, registrar `FAILED`.

La respuesta inicial del endpoint normalmente representa el inicio del trabajo, no su finalización.

## 3. Capacidades implementadas

- Dockerfile Maven con construcción, extracción de capas Spring Boot y runtime Java 21.
- Variante Gradle detectada por `build.gradle` o `build.gradle.kts`.
- Usuario y grupo sin privilegios, UID/GID 10001.
- Configuración JVM de memoria y healthcheck contra Actuator.
- `.dockerignore` que excluye secretos y archivos temporales habituales.
- Compose para PostgreSQL 16, MySQL 8 y H2 embebido.
- Redes por proyecto Compose y volúmenes persistentes de BD.
- Dependencia de la aplicación respecto de la salud de la BD en PostgreSQL y MySQL.
- Inyección de Actuator y drivers PostgreSQL/MySQL en Maven y Gradle.
- Ejecución Compose por sesión mediante `-p <session_id>`.
- Recuperación básica de contenedores tras reiniciar backend usando la etiqueta `com.docker.compose.project`.
- Estado `DOCKER_UNAVAILABLE` cuando la ejecución está deshabilitada o el daemon no responde.
- Validación estática de calidad previa a generación y despliegue.
- Proxy del playground para evitar llamadas directas del navegador al servicio generado; descubrimiento de rutas desde controladores.
- Sandbox Maven con `mvn test -o`, red deshabilitada y repositorio Maven montado en solo lectura.
- Sandbox Gradle con `gradle --no-daemon --offline test`, caché montada en solo lectura y copiada a un directorio temporal del contenedor.
- El fallback actual del sandbox devuelve un resultado de no verificación; no fabrica `BUILD SUCCESS`.

Estas capacidades están presentes en el código. Su presencia no demuestra que todos los caminos funcionen con contenedores reales en este equipo.

## 4. Estado del entorno observado

| Elemento | Resultado del 04/10/2026 |
|---|---|
| Docker CLI | Instalado; versión reportada `29.7.2`, Windows amd64. |
| Docker Compose | Instalado; versión reportada `v5.5.1`. |
| Contexto seleccionado | `desktop-linux`. |
| Docker Engine | No accesible: falta la named pipe `//./pipe/dockerDesktopLinuxEngine`. |
| Contenedores e imágenes existentes | No se pudieron enumerar por el fallo de conexión al motor. No se concluye que estén ausentes. |
| Habilitación Docker en configuración | `DOCKER_ENABLED=False` por defecto; sin asignación encontrada en `.env`, `backend/.env` o la variable de entorno inspeccionada. No se consultó una instancia viva del backend para confirmar su configuración efectiva. |
| Caché Maven por defecto | Existe `C:\Users\willi\.m2\repository`, pero estaba vacía. |
| Caché Gradle | No se obtuvo una caché utilizable en la inspección del directorio por defecto. No se validó una caché alternativa. |
| Python del PATH | Apunta al alias WindowsApps; su ejecución falló. No se encontró launcher `py`. |
| Python bundled de Codex | Disponible, pero sin `pytest`, `fastapi`, `pydantic_settings`, `sqlalchemy`, `requests`, `yaml` ni `langgraph` en la comprobación realizada. |

No se inició Docker Desktop, no se descargaron imágenes ni dependencias y no se modificaron los `.env`.

## 5. Hallazgos principales

| ID | Prioridad | Estado | Hallazgo y efecto |
|---|---|---|---|
| D01 | Alta | Observado en entorno | Motor Docker inaccesible: impide verificar, construir y desplegar realmente ahora. |
| D02 | Alta | Confirmado en configuración | Docker deshabilitado por defecto y sin habilitación encontrada. Activar el motor por sí solo no habilita la ejecución del sistema. |
| D03 | Alta | Confirmado en código y prueba aislada | El puerto del payload de despliegue no modifica Compose; puede diferir del puerto que realmente se publica. |
| D04 | Alta | Confirmado en código | La vista DevOps no hace polling ni se suscribe a SSE; puede permanecer en `BUILDING` y no seguir los logs. |
| D05 | Alta | Reproducido con dependencias simuladas | Un registro `HEALTHY` conserva ese estado cuando la comprobación posterior devuelve DOWN o falla. |
| D06 | Alta | Reproducido con dependencias simuladas | Parada informa `STOPPED` aunque Compose down devuelva error; también silencia excepciones. |
| D07 | Alta | Confirmado en contratos | Frontend y backend usan campos diferentes para smoke test y parte del estado de despliegue. |
| D08 | Media | Confirmado en código | Puertos de BD fijos y sin asignación dinámica ni detección de conflicto; limita despliegues simultáneos. |
| D09 | Media | Observado; migración antigua fuera del alcance acordado | Manifiestos antiguos no se regeneran automáticamente al desplegar. El usuario prioriza exclusivamente los proyectos posteriores a la nueva implementación. |
| D10 | Alta para verificación | Observado en entorno | Caché Maven vacía: la verificación hermética offline carece de dependencias precargadas. |
| D11 | Media | Confirmado en código | Interfaz y varios puntos del pipeline fuerzan o asumen PostgreSQL. |
| D12 | Alta para garantía de calidad | Confirmado en código | Desplegar exige auditoría estática, pero no evidencia vigente de pruebas aprobadas; la construcción de imagen omite las pruebas. |
| D13 | Media | Confirmado en código | Logs y registros de despliegue viven en memoria; no existe captura continua de logs reales de aplicación. |
| D14 | Media | Confirmado en código | Construcción y consulta de Compose carecen de timeout; no hay bloqueo por sesión contra despliegues simultáneos. |
| D15 | Media | Confirmado en revisión de pruebas | Pruebas de despliegue desactualizadas y sin demostración E2E con Docker real. |
| D16 | Fuera del alcance acordado | Confirmado por inventario | No hay empaquetado Docker de la propia plataforma AgentIA; el usuario solicita Docker únicamente para los microservicios generados. |

### D03 — Puerto solicitado y puerto efectivo

En [routes_devops.py:98](C:/Users/willi/Downloads/agentIA/backend/app/api/routes_devops.py:98), la generación automática llama a `generate_all_devops_assets` sin transmitir el puerto del payload. Este se lee después, y se pasa al registro de despliegue.

En [docker_service.py:233](C:/Users/willi/Downloads/agentIA/backend/app/services/docker_service.py:233), Compose se ejecuta sin modificar el manifiesto ni aplicar un override de puerto. Si el archivo ya existe, se reutiliza su puerto.

La prueba aislada con solicitud `hostPort=18080` y sin Compose registró:

```json
{"requestedPort":18080,"manifestGenerationCall":[{"args":[".","audit","audit-service"],"kwargs":{}}],"registryPort":18080}
```

El generador usa 8080 cuando no recibe otro valor. La inspección posterior de Compose puede corregir el puerto del registro, pero no satisface la elección del usuario. Generar manifiestos explícitamente con `host_port=18080` sí incluye ese puerto.

### D04 y D07 — Interfaz y contratos

Fuentes: [DevOpsDeploymentView.tsx:102](C:/Users/willi/Downloads/agentIA/frontend/src/views/DevOpsDeploymentView.tsx:102), [devopsService.ts](C:/Users/willi/Downloads/agentIA/frontend/src/services/devopsService.ts), [devops.py:36](C:/Users/willi/Downloads/agentIA/backend/app/models/devops.py:36).

- `fetchStatus` se invoca al seleccionar sesión y tras generar manifiestos; no hay `setInterval` ni `EventSource` en esta vista.
- El despliegue actualiza la vista con la respuesta inicial y no espera su conclusión.
- `isDeploying` vuelve a false tras esa respuesta; el botón no queda bloqueado durante todo `BUILDING`.
- El texto de despliegue puede decir «Contenedor levantado» aunque el backend devuelva `BUILDING` o `DOCKER_UNAVAILABLE`, porque busca `res.message`, campo que el backend no devuelve.
- El backend devuelve `errorMessage`; el tipo y renderizado del frontend esperan `message`.
- El backend devuelve para smoke test `passed`, `statusCode`, `statusPayload`, `testUrl`, `details` y `latencyMs`.
- El frontend espera `status: SUCCESS|FAILURE|SKIPPED`, `message`, `endpointTested` y `httpStatusCode`, entre otros campos.
- La vista colorea el resultado según `smokeResult.status`, ausente en la respuesta real del backend.
- `dbEngine` y `serviceName` se declaran en el tipo del estado del frontend, pero no existen en el modelo de estado del backend.

### D05 y D06 — Estado y parada

Fuentes: [docker_service.py:120](C:/Users/willi/Downloads/agentIA/backend/app/services/docker_service.py:120), [docker_service.py:322](C:/Users/willi/Downloads/agentIA/backend/app/services/docker_service.py:322).

Se ejecutaron las funciones existentes aisladas, con respuestas HTTP y procesos simulados, sin abrir sockets ni iniciar contenedores:

```json
{"probe":"healthy_service_now_returns_503","status":"HEALTHY","healthStatus":"DOWN"}
{"probe":"compose_down_exit_17","reportedStatus":"STOPPED"}
```

- La consulta solo promueve a HEALTHY; no degrada el estado anterior cuando health falla.
- Para registros existentes no reconcilia siempre su identidad y ejecución con Docker antes de confiar en el endpoint.
- La recuperación sin registro utiliza `docker ps`, no contenedores detenidos; no recupera sus causas de salida.
- La parada ignora el código de retorno y captura las excepciones sin reflejarlas como error.
- Cuando no existe registro previo, la parada crea un objeto para responder, pero no lo incorpora al registro global.
- El smoke test manual usa el puerto proporcionado/default 8080; no resuelve obligatoriamente la identidad y puerto del contenedor de la sesión. Una respuesta saludable de otro servicio en ese puerto puede pasar la comprobación.

### D08 y D11 — Base de datos y sesiones simultáneas

Fuente: [devops_service.py:100](C:/Users/willi/Downloads/agentIA/backend/app/services/devops_service.py:100).

- Aplicación: puerto fijo elegido al generar, por defecto `8080:8080`.
- PostgreSQL: `5432:5432`.
- MySQL: `3306:3306`.
- No se encontró detección preventiva de puertos ocupados ni selección automática de puertos libres.
- Aislar redes y volúmenes por proyecto Compose no elimina conflictos en puertos del host.
- La interfaz llama a `generateManifests` con `POSTGRESQL` literal; no ofrece selección del motor aquí.
- La generación automática de manifiestos del despliegue y del pipeline omite el motor y utiliza PostgreSQL por defecto.
- El generador sí admite MySQL y H2 cuando se invoca explícitamente.
- La interfaz muestra PostgreSQL como fallback y en varios textos del playground, incluso si el proyecto usa otro motor.

### D09 — Artefactos previos y esquema SQL

Inventario de `backend/workspaces/*/docker-compose.yml`:

```json
{"existingLocalComposeFiles":116,"filesWithOldSchemaBindMount":107}
```

La detección buscó el montaje efectivo `./schema.sql:/docker-entrypoint-initdb.d/`, no solamente una mención en comentarios.

El generador PostgreSQL actual elimina ese bind mount y configura:

```text
SPRING_SQL_INIT_MODE=always
SPRING_JPA_HIBERNATE_DDL_AUTO=none
```

`lifecycle_artifacts.py` coloca el esquema también en `src/main/resources/schema.sql`, para que viaje dentro del artefacto y lo aplique Spring Boot. La copia utiliza escritura solo si el archivo falta; no garantiza sincronización de ediciones posteriores. No se comprobó el arranque ni la compatibilidad del esquema de cada proyecto existente.

MySQL usa `SPRING_JPA_HIBERNATE_DDL_AUTO=update`; sus mecanismos de inicialización no son idénticos a los de PostgreSQL.

### D10 y D12 — Construcción, caché y evidencia de pruebas

Fuentes: [docker_runner.py](C:/Users/willi/Downloads/agentIA/backend/app/sandbox/docker_runner.py), [warm_maven_cache.py](C:/Users/willi/Downloads/agentIA/backend/scripts/warm_maven_cache.py), [verification_policy.py](C:/Users/willi/Downloads/agentIA/backend/app/services/verification_policy.py).

- La imagen Maven por defecto es `maven:3.9-eclipse-temurin-21`; la construcción del Dockerfile utiliza su variante Alpine.
- Montar una caché vacía en solo lectura y ejecutar offline no precarga las dependencias.
- Existe un script que genera proyectos de calentamiento y muestra el comando de ejecución online; no se ejecutó.
- Gradle utiliza por defecto `gradle:8-jdk21`, con overrides por variables `GRADLE_CACHE_DIR` y `GRADLE_DOCKER_IMAGE`.
- No se pudo comprobar si las imágenes están disponibles localmente porque el motor no responde.
- Dockerfile Maven: `RUN mvn clean package -Dmaven.test.skip=true`.
- Dockerfile Gradle: `RUN gradle --no-daemon clean bootJar -x test`.
- El build de imagen utiliza comandos online; llamarlo «hermético» en textos no demuestra un build sin red. La verificación sandbox sí configura red deshabilitada y modo offline.
- Las rutas DevOps llaman a la auditoría estática; no llaman a `require_verified_session` ni exigen `session_has_current_evidence`.
- Generar activos puede añadir dependencias al proyecto; hay que considerar su efecto sobre la evidencia de verificación previa.
- Algunas descripciones de `docker_runner.py` y `config.py` aún hablan de fallback permisivo/sintético. La implementación inspeccionada de `_build_hermetic_fallback_result` siempre devuelve fallo de verificación, sin salida sintética de éxito.

### D13 y D14 — Logs y ciclo de vida

- `_active_deployments`, `_log_queues` y `_raw_log_history` son estructuras globales en memoria.
- Reiniciar el backend pierde historial y registro; la recuperación por etiquetas reconstruye solo parte del estado.
- Se captura salida de `compose up -d`; no se ejecuta `docker logs -f` ni `docker compose logs -f` para seguir los logs de Spring o BD.
- SSE reproduce el historial y luego consume una cola que contiene esos mismos mensajes, con posibilidad de duplicarlos.
- La cola se comparte entre consumidores y no implementa difusión a varios suscriptores.
- El stream termina tras unas 30 iteraciones ociosas de 0,5 segundos; no mantiene una suscripción indefinida.
- `proc.wait()` y la inspección `compose ps` no tienen timeout en el despliegue.
- No se encontró control que impida lanzar dos trabajadores de despliegue para la misma sesión.
- El pipeline puede invocar despliegue automático en segundo plano y continuar; completar el pipeline no equivale a esperar ni confirmar HEALTHY.
- La consulta de estado y el smoke test usan llamadas bloqueantes dentro de endpoints declarados async.
- El puerto del modelo de solicitud es un entero opcional sin restricción explícita al rango de puertos.

## 6. Pruebas y verificaciones realizadas

### Comandos de entorno

```powershell
docker version
docker compose version
docker context show
docker ps --format '{{.Names}} {{.Status}} {{.Ports}}'
docker images --format '{{.Repository}}:{{.Tag}} {{.Size}}'
```

Se obtuvo información del cliente y Compose; las consultas al servidor fallaron por named pipe ausente.

### Validación de Compose actual

Se extrajeron en memoria las funciones generadoras existentes y se entregó su salida por stdin a:

```text
docker compose -p audit-readonly -f - config --quiet
```

| Motor | Puerto solicitado al generador | Resultado |
|---|---|---|
| PostgreSQL | 18080 | Código 0; contiene `18080:8080`. |
| MySQL | 18080 | Código 0; contiene `18080:8080`. |
| H2 | 18080 | Código 0; contiene `18080:8080`. |

Compose advirtió que el atributo `version: '3.8'` es obsoleto y se ignora. No fue un error de validación.

Esta prueba verifica la configuración Compose, no la existencia/compatibilidad de las imágenes ni una construcción o ejecución exitosa.

### Comprobaciones aisladas de lógica

- Estado previamente HEALTHY con HTTP 503: conserva HEALTHY y pasa health a DOWN.
- Parada con proceso de salida 17: informa STOPPED.
- Despliegue sin Compose y payload 18080: la generación automática no recibe el puerto; el registro sí.
- Inventario de manifiestos locales: 116 Compose, 107 con montaje antiguo.

Las comprobaciones ejecutaron funciones existentes con dependencias externas simuladas. No constituyen pruebas con Docker real.

### Suite existente

Fuentes: [test_qe_deploy_docker.py](C:/Users/willi/Downloads/agentIA/backend/tests/test_qe_deploy_docker.py), [test_routes_devops.py](C:/Users/willi/Downloads/agentIA/backend/tests/test_routes_devops.py), [test_devops_service.py](C:/Users/willi/Downloads/agentIA/backend/tests/test_devops_service.py), [test_docker_runner.py](C:/Users/willi/Downloads/agentIA/backend/tests/test_docker_runner.py).

- QE de despliegue simula subprocess, requests e hilos; su cabecera declara que no inicia contenedores ni abre sockets.
- Hay expectativas anteriores a `-p <session_id>`, tanto para up como para down.
- Una prueba espera eliminar volúmenes con `down -v`; el servicio actual utiliza down sin `-v`.
- El fixture QE inspeccionado no habilita explícitamente `DOCKER_ENABLED`; algunos casos de disponibilidad dependen de ese valor.
- El éxito simulado no adapta todas las expectativas a la inspección JSON posterior de Compose.
- Una prueba de ruta acepta `DOCKER_UNAVAILABLE` como resultado válido; pasarla no demuestra despliegue efectivo.
- **Pytest no se ejecutó en esta revisión.** No se atribuyen cantidades de tests aprobados o fallidos.

## 7. Información histórica y diferencias documentales

Se consultaron [spec.md de Docker/CI/CD](C:/Users/willi/Downloads/agentIA/specs/007-docker-cicd-orchestration/spec.md), [contrato DevOps](C:/Users/willi/Downloads/agentIA/specs/007-docker-cicd-orchestration/contracts/devops-api.yaml), [matriz QE](C:/Users/willi/Downloads/agentIA/docs/qe_test_matrix.md) y [verificación previa](C:/Users/willi/Downloads/agentIA/reports/verify-61c0f29/VERIFICACION.md).

- La especificación prevé resolución de conflictos de puertos; no se encontró su implementación actual.
- La especificación menciona backoff y tiempos de disponibilidad; el servicio actual usa intervalos fijos. El tiempo total depende también de los timeouts de cada petición, no solo de intentos por intervalo.
- La especificación y README contienen referencias a Streamlit; la interfaz activa inspeccionada es React/Vite.
- La especificación conserva la inicialización SQL por montaje en el contenedor de BD; el generador PostgreSQL actual utiliza el classpath y Spring Boot.
- Reportes anteriores indicaban falta de soporte Gradle en Docker/sandbox. El código actual ya tiene variantes Gradle; esos hallazgos históricos no deben repetirse como ausencia actual de implementación.
- El reporte previo también declaró que Docker inaccesible impedía demostrar despliegue real. No reemplaza la verificación actual.
- Los porcentajes de cobertura y aprobaciones históricas no prueban el funcionamiento operativo presente.
- Los pipelines CI/CD generados incluyen pasos de auditoría basados en mensajes `echo`; su presencia no equivale a ejecutar SAST. Esto es contexto del generador, no una verificación de CI remoto.

## 8. Límites y criterios para una validación posterior

No se comprobó con contenedores reales:

- Construcción de imágenes Maven o Gradle.
- Disponibilidad y compatibilidad de imágenes base.
- Extracción de capas y arranque del JarLauncher.
- Healthcheck dentro de la imagen.
- Arranque y conexión de PostgreSQL/MySQL/H2.
- Aplicación del esquema SQL y compatibilidad con entidades generadas.
- CRUD efectivo, lectura posterior y persistencia tras reiniciar.
- Dos despliegues simultáneos sin colisiones.
- Recuperación de estado después de reiniciar backend.
- Parada efectiva y conservación de los datos.
- Comportamiento de UI y logs durante un build real.

Para declarar funcional el flujo en un trabajo posterior, será necesario demostrar al menos: motor accesible y habilitado, dependencias disponibles, build real, arranque de aplicación y BD cuando corresponda, identidad y puerto correctos, Actuator UP, CRUD y persistencia, seguimiento visible en UI y parada comprobada. Si se acuerda contenerizar AgentIA, ese alcance necesitará además su configuración y validación propias.

## 9. Orden propuesto de trabajo posterior

Esta lista es una propuesta inicial, no una implementación ejecutada. Las decisiones de la sección 11 la precisan y tienen prioridad sobre las dudas de alcance de esta lista:

1. Precisar si el objetivo abarca también ejecutar AgentIA completa en Docker.
2. Resolver entorno, habilitación y precarga de imágenes/cachés.
3. Corregir puertos, motor de BD y tratamiento de manifiestos existentes.
4. Reconciliar estados y errores con la realidad de Docker; corregir parada y vincular smoke test a la sesión.
5. Alinear contratos frontend/backend y seguir estado/logs automáticamente.
6. Mejorar control de despliegues, timeout y logs reales.
7. Actualizar pruebas y ejecutar validaciones reales de Maven, Gradle, BD, persistencia y sesiones simultáneas.
8. Actualizar la documentación con los resultados efectivamente demostrados.

## 10. Bitácora

| Fecha | Acción | Resultado |
|---|---|---|
| 04/10/2026 | Análisis solicitado del estado Docker | Diagnóstico anterior; sin cambios al sistema ni contenedores. |
| 04/10/2026 | Consolidación solicitada en Markdown | Creado este documento como referencia de esta conversación. Las correcciones continúan pendientes. |
| 04/10/2026 | Aclaraciones previas al plan | Registradas las decisiones del usuario en la sección 11, con énfasis en Docker opcional por microservicio y funcionamiento en laboratorio restringido. Pendientes las aclaraciones finales antes de redactar el plan. |
| 04/10/2026 | Segunda ronda de aclaraciones | Acordadas las opciones Reintentar/Continuar sin Docker, preparación inicial online y alcance offline excepto IA. GitLab real queda sujeto a definir recursos y nivel de integración. |
| 04/10/2026 | Alcance remoto aplazado y plan creado | El usuario deja de lado GitLab. Creado plan local con 54 tareas, Docker opcional por sesión como prioridad y validación local de artefactos CI/CD/Kubernetes. Sin implementación de código. |

Antes de la consolidación, Git mostraba un directorio `.gradle/` no rastreado en un workspace de un reporte anterior. Era preexistente al análisis y no se eliminó ni modificó. Este documento y el plan vinculado son los cambios documentales intencionales; no se implementaron cambios de aplicación.

## 11. Decisiones del usuario para el plan

Estas decisiones provienen de las respuestas explícitas del usuario y sustituyen los supuestos anteriores incompatibles.

| Pregunta original | Decisión acordada |
|---|---|
| 1. Alcance Docker | Solo los microservicios generados. No contenerizar AgentIA. |
| 2. Entorno | Windows como objetivo principal; no es necesario implementar soporte para otros sistemas. |
| 3. Instalación | Si es posible, despliegue sencillo con un comando y sin herramientas de compilación instaladas en el host. Este objetivo se aplica a los microservicios; no se ha acordado empaquetar AgentIA. |
| 4. Red | Preparación inicial con internet permitida. Después, funcionamiento offline de los flujos locales, con la generación mediante IA excluida de ese requisito. La preparación debe cubrir imágenes, dependencias y herramientas necesarias para el alcance elegido. |
| 5. Cobertura | Probar todo lo posible; incluir la matriz Maven/Gradle y PostgreSQL/MySQL/H2, registrando honestamente las combinaciones verificadas y las limitaciones. |
| 6. Proyectos previos | No importa migrar lo antiguo. El alcance funcional comienza con los proyectos de la nueva implementación. Esto no autoriza borrar proyectos ni datos previos. |
| 7. Docker opcional | Requisito prioritario: el sistema se utilizará también en un laboratorio con permisos restringidos y virtualización deshabilitada. Al crear el microservicio se debe poder elegir si se dispone/desea usar Docker. Si se elige no usarlo, su ausencia y las etapas relacionadas no deben impedir terminar el flujo. |
| 8. Modos de despliegue | Conservar despliegue manual y automático. El automático se aplica cuando Docker está elegido y disponible. |
| 9. Puertos | Si el puerto está ocupado, elegir otro e informar al usuario. |
| 10. Persistencia | Conservar los datos al detener. Separar la acción explícita de borrado. No se acordó todavía un requisito de arranque automático tras reiniciar el equipo. |
| 11. Acceso | Uso exclusivamente mediante localhost. No se indicó un presupuesto de RAM o disco. |
| 12. CI/CD y Kubernetes | Corregir artefactos y validar localmente. Tras considerar los requisitos, el usuario aplaza GitLab; no se requieren cuenta, runner remoto, registry remoto ni contratación para ejecutar el plan local. |

### Requisito central: laboratorio sin Docker

La selección debe pertenecer al microservicio/sesión, persistir y respetarse en los distintos puntos de entrada: creación, flujo guiado, grafo, Auto-Pilot, verificación, DevOps, overview y exportación. Un interruptor global del servidor no satisface por sí solo la elección por proyecto.

Interpretación de trabajo para el plan, compatible con la instrucción del usuario:

- En modo sin Docker, generar los artefactos y completar el flujo de fuentes sin requerir virtualización, daemon, imágenes ni cachés Docker.
- Las compilaciones, pruebas de ejecución, smoke tests y despliegues que no se realicen deben figurar como no ejecutados u omitidos por elección; no como aprobados, HEALTHY o VERIFIED.
- Mantener las comprobaciones estáticas que no dependen de Docker. Docker opcional no implica fabricar resultados ni omitir todos los controles de calidad.
- Permitir la entrega de los artefactos correspondientes al modo de fuentes, con el estado de verificación visible.
- No exigir Java/Maven/Gradle locales como sustituto obligatorio de Docker en el laboratorio.
- La generación de Dockerfile, Compose, CI/CD y Kubernetes puede conservarse para uso posterior en otro equipo, aunque su ejecución local esté omitida. Esto se propondrá expresamente en el plan.
- Si una sesión eligió Docker y luego falla el entorno, distinguir indisponibilidad de infraestructura de fallo real de compilación o pruebas. Nunca interpretar pruebas realmente fallidas como una simple omisión.
- Las validaciones reales de la implementación deberán cubrir tanto un entorno con Docker como el flujo completo sin Docker; que el laboratorio no pueda ejecutar contenedores no debe impedir usar el sistema.

### Brecha actual relevante al punto 7

Ya hay tratamiento parcial de `verificationSkipped` y entrega de fuentes cuando `settings.DOCKER_ENABLED` es false. Sin embargo:

- `workspace_verification.py` decide omitir con la configuración global.
- `verification_policy.py` condiciona la entrega sin Docker a esa misma configuración global.
- `pipeline_runner.py` decide fuentes/despliegue utilizando el interruptor global.
- En los modelos de creación y ejecución revisados no se encontró una preferencia explícita y persistente de Docker por sesión.

Por ello, el plan debe unificar la decisión por sesión y evitar que elegir sin Docker en un proyecto dependa de deshabilitarlo para todos los demás.

### Aclaraciones adicionales resueltas

1. Si el usuario eligió Docker y este no está disponible: mostrar **Reintentar** y **Continuar sin Docker**. No convertir silenciosamente la ejecución solicitada en éxito ni cambiar el modo sin elección explícita.
2. Se permite preparación inicial con internet.
3. El funcionamiento offline abarca todo el alcance local salvo la IA. No incluye fabricar resultados si una imagen, herramienta o dependencia no fue preparada. Las operaciones remotas GitLab necesitan acceso al servicio y deben ser opcionales para completar el flujo local.
4. El usuario desea idealmente validación real en GitLab, pero solicita aclarar los recursos y alcance antes de cerrar el plan.

### GitLab: contexto histórico; integración aplazada

**Decisión posterior del usuario:** dejar este tema de lado por ahora. Las preguntas siguientes quedan suspendidas y no bloquean el plan local. La consideración del usuario sobre costes no se ha verificado como condición aplicable a su cuenta; no se concluye que todo uso de GitLab.com requiera pago.

Consulta de documentación oficial realizada el 04/10/2026:

- Los [runners](https://docs.gitlab.com/ci/runners/) ejecutan los jobs definidos en `.gitlab-ci.yml`; un archivo YAML por sí solo no demuestra ejecución.
- Los [runners alojados por GitLab](https://docs.gitlab.com/ci/runners/hosted_runners/) permiten ejecutar trabajos fuera del equipo del laboratorio y consumen minutos de cómputo de la cuenta. No se verificó disponibilidad ni cuota de la cuenta del usuario.
- La [construcción de imágenes](https://docs.gitlab.com/ci/docker/using_docker_build/) necesita un runner con capacidades compatibles con el método elegido. No se debe asumir que Docker-in-Docker estará permitido en el laboratorio o en cualquier runner.
- [Publicar imágenes en el registry](https://docs.gitlab.com/user/packages/container_registry/build_and_push_images/) es un alcance adicional a compilar y ejecutar tests; requiere autenticación y un destino de almacenamiento.
- [Desplegar desde GitLab a Kubernetes](https://docs.gitlab.com/user/clusters/agent/ci_cd_workflow/) requiere un cluster operativo y acceso configurado; disponer de GitLab no implica disponer de un cluster.

Decisiones aún necesarias:

1. GitLab.com o servidor institucional/privado, cuenta y proyecto de prueba disponibles.
2. Runner alojado por GitLab o runner institucional ya disponible; no instalar un runner Docker como requisito en el laboratorio sin virtualización.
3. Qué validar remotamente: compilación, pruebas, auditoría, construcción/escaneo de imagen, publicación de imagen y/o despliegue.
4. Si existe un cluster Kubernetes de prueba, dónde está y quién administra el acceso; si no existe, decidir alcance de validación local y futura ejecución real.
5. Límite de gasto: uso de recursos/cuotas disponibles o presupuesto autorizado. No se asume contratación ni compra.
6. Experiencia de integración: publicación/inicio/seguimiento desde AgentIA o exportación y ejecución gestionadas desde GitLab.

El uso de GitLab y Kubernetes remoto debe seguir siendo opcional y no impedir completar una sesión local sin Docker o sin conectividad al servicio remoto. No se han publicado repositorios, registrado runners, enviado código ni ejecutado pipelines remotos.

## 12. Plan local y observación adicional offline

El [plan de implementación](C:/Users/willi/Downloads/agentIA/docs/PLAN_IMPLEMENTACION_DESPLIEGUE_LOCAL.md) organiza 54 tareas en nueve fases P0–P8, con dependencias, archivos afectados, condiciones de aceptación y trazabilidad de D01–D16.

- El modo sin Docker tiene prioridad: elección persistida por sesión, flujo completo de fuentes y resultados de ejecución honestos.
- Las operaciones remotas GitLab quedan aplazadas; se conserva corrección y validación local de artefactos entregables CI/CD/Kubernetes.
- La prueba Docker/Kubernetes real requerirá un entorno con virtualización funcional, pero no se exigirá ese entorno al laboratorio para generar y entregar fuentes.
- Observación adicional al preparar el plan: `frontend/index.html` contiene enlaces activos a Google Fonts (`fonts.googleapis.com` y `fonts.gstatic.com`). La tarea T54 contempla assets locales y preparación de dependencias de la plataforma para que el requisito offline, salvo IA, no dependa de esos servicios.
- No se han ejecutado las tareas ni se han dado por cerrados los fallos técnicos del diagnóstico.
## 13. Bitácora de implementación — 04/10/2026

El usuario autorizó comenzar la implementación del plan. La prioridad sigue siendo completar el flujo sin Docker en el laboratorio. Se incorporó elección persistida por sesión y generación para Maven/Gradle × PostgreSQL/MySQL/H2 sin invocar Docker incluso con la configuración global habilitada. El frontend compila y muestra elección, reintento, continuación sin Docker y preparación online.

**Todavía no se ha demostrado un despliegue real ni funcionamiento offline de extremo a extremo:** el motor Docker de este equipo no está accesible. Las pruebas de generación, UI y dependencias simuladas descritas a continuación no sustituyen esa evidencia.

La descripción histórica precedente se conserva como diagnóstico previo; no representa necesariamente el código después de los cambios.


### Cambios implementados

**Laboratorio / punto 7:**

- Nuevas sesiones con `executionMode=SOURCE_ONLY` por defecto. Se persiste la elección y el motor de BD; cambio aditivo del esquema SQLite existente. Creación rápida e ingesta permiten seleccionar Docker, sin exigirlo.
- Grafo, sandbox y Auto-Pilot usan la preferencia de la sesión. La configuración global es únicamente un límite administrativo; su default nuevo permite Docker, pero no lo solicita por defecto. No se modificaron los `.env` reales del usuario.
- Fuentes: generación de código y pruebas como archivos, auditoría estática y ZIP permitido por la auditoría. La generación determinista ahora produce archivos Gradle cuando se elige esa herramienta; la matriz de seis combinaciones se ejercitó por grafo y Auto-Pilot con exportación.
- `SKIPPED_BY_CHOICE`, `ENVIRONMENT_UNAVAILABLE`, `PASSED`, `FAILED` y `OUTDATED` distinguen elección, indisponibilidad y evidencia. No se usa `COMPLETED` para afirmar pruebas ejecutadas.
- Docker solicitado pero no disponible queda pendiente; la UI ofrece Reintentar y Continuar sin Docker. El backend permite verificar las fuentes existentes y cambiar explícitamente el modo, con exclusión frente a una operación activa.
- Tras un fallo real, la entrega explícita de fuentes conserva resultados, error anterior y documentación. No elimina los XML de ejecuciones anteriores solo porque se haya elegido omitir una nueva ejecución.
- Fingerprint incluye fuentes/recursos de módulos anidados, manifiestos de build y configuración Docker. Ediciones posteriores invalidan la evidencia. Exportación excluye `.env` reales, cachés, build y registros privados; no crea un JAR ficticio.

**Primera versión Docker, todavía sin ejecución real:**

- Actuator y drivers incorporados antes de verificar. Builders por fingerprint de dependencias y runtime preparado. Construcción Maven/Gradle offline con caché temporal privada; empaquetado de JAR ejecutable y aplicación no root.
- Compose usa publicación `127.0.0.1`, BD interna sin puertos publicados al host y volúmenes por proyecto. H2 de archivos sin contenedor de BD. Credenciales PostgreSQL/MySQL requeridas como entrada local; no se generan valores secretos reales en el export.
- Preparación inicial online explícita. Su resultado no se registra como PASS offline. Build explícito y arranque con `--no-build --pull never`; imagen ausente requiere preparación, sin pull silencioso. Las versiones están fijadas por tags; digests e integridad portable aún pendientes.
- Bloqueo por sesión compartido por preparación/despliegue/verificación/cambio de modo, ID de operación, procesos acotados, puerto alternativo y reintento limitado ante conflicto durante el bind. Liberación del bloqueo si falla el inicio del worker o la persistencia final.
- Inspección por etiquetas y puerto real. Salud actual degrada el estado si Actuator cae o responde JSON inválido. Smoke test revalida identidad durante los intentos. Playground rechaza contenedores detenidos y no se redirige a un proceso ajeno en el puerto anterior.
- Estado operativo durable en `.agentia-runtime`; recuperación tras reinicio e indicación de operación interrumpida. Parada comprueba retorno y contenedores, conserva datos y no fabrica STOPPED. AutoDeploy espera salud final; en fuentes se omite.
- UI con polling y limpieza al cambiar sesión, mensajes/contratos correctos y puerto/motor efectivos. Logs guardados, limitados y con redacción básica; aún se capturan al terminar cada comando, no hay captura continua app/BD ni reconexión SSE completa.
- Scripts `prepare-local.ps1`, `start-local.ps1`, `stop-local.ps1`, `cleanup-local.ps1` en proyectos nuevos. No instalan Java en Windows, no cambian políticas ni habilitan virtualización. Limpieza de datos exige `-DeleteData`.
- Configuración nueva de FastAPI/Vite y lanzadores Windows limita escucha a localhost. Se retiraron Google Fonts externos. Guía de uso React/Windows, plan técnico y contrato OpenAPI actualizados; este último deriva de 14 paths de la aplicación y 19 schemas con referencias resueltas.

**No se intervinieron los proyectos históricos inventariados.** Los artefactos de pruebas se generaron en directorios temporales. No se publicó código ni se ejecutaron pipelines o clusters remotos.

### Entorno de implementación

- **Base del trabajo comprobada con el usuario:** rama local `no-docker`, commit `863553aaf43d0b7178f2e37cf6d4cbdf96a7efed` (`Corre`). Coincide con el `863553a` de su captura, con `origin/no-docker` y con la rama remota consultada directamente mediante `git ls-remote` el 04/10/2026. Los cambios de esta implementación se hicieron sobre ese checkout; no se cambió de rama ni se hizo reset. La copia de HEAD usada como baseline corresponde a esa base.

- Se preparó Python 3.12.14 con uv bajo `.runtime/python`, entorno `.venv` y caché `.uvcache`, en el repositorio y sin instalación global/administrativa. Se instalaron dependencias del backend para poder ejecutar pruebas; esta preparación inicial usó internet y no acredita instalación offline reproducible.
- Frontend con las dependencias locales existentes; compilación TypeScript/Vite correcta. Aviso de tamaño de bundle, sin error de build.
- Docker CLI/Compose siguen disponibles; el motor `desktop-linux` no responde por la named pipe ausente. El intento de localizar/iniciar Docker Desktop no encontró `C:\Program Files\Docker\Docker\Docker Desktop.exe`.
- CIM informó `HypervisorPresent=True`, pero flags de virtualización del procesador falsos. No demuestra por sí solo que se pueda activar virtualización anidada o que el motor sea utilizable. No se cambiaron opciones del sistema operativo.
- No se descargaron imágenes Docker, no se ejecutó Java en contenedor ni se midieron build/CRUD/persistencia reales.

### Evidencia y límites de las pruebas

| Comprobación | Resultado | Alcance real |
|---|---|---|
| Pruebas enfocadas backend (modo, runtime, assets, Auto-Pilot) | **53 PASS, 1 XFAIL** | Generación/BD temporal/exportación reales; motor Docker y HTTP de contenedor simulados. XFAIL estricto identifica SQL/semillas pendiente (T22), sin convertirlo en aprobado. |
| Matriz sin Docker: Maven/Gradle × PostgreSQL/MySQL/H2 | **6/6 grafo y 6/6 Auto-Pilot PASS** | Generación, finalización, auditoría y ZIP, con CLI/subprocesos y sandbox prohibidos mediante assertions, aun con permiso global habilitado. IA excluida mediante proveedor de prueba. No demuestra compilación Java. |
| UI enfocada (elección, decisiones, DevOps/auditoría/exportación) | **10 PASS** | React/Vitest con respuestas API simuladas. |
| Regresión frontend actual | **63 PASS, 9 FAIL** | Mismos 9 fallos presentes en HEAD aislado; no se declara suite verde. |
| Frontend `npm run build` | **PASS** | TypeScript y producción Vite. |
| PowerShell generado | **8 scripts, 0 errores de sintaxis** | Parser real de Windows, preparar/iniciar/detener/limpiar para Maven y Gradle; no ejecución Docker de scripts. |
| Regresión backend general más reciente | **948 PASS, 174 FAIL, 3 SKIP, 1 XFAIL** | Comparación con HEAD aislado: 927 PASS, 162 FAIL, 3 SKIP. La regresión general precede al último ajuste de descubrimiento/conservación XML; ese ajuste y cuatro casos nuevos pasaron después en la suite enfocada de 53 pruebas. |
| Diff/formato | **PASS** | `git diff --check`; solo avisos habituales LF/CRLF. |
| Docker offline / Compose real / Kubernetes real | **NO EJECUTADO** | Motor inaccesible; no se consideran PASS por simulación. |

La diferencia en la última regresión backend es **15 fallos adicionales, todos en `test_qe_deploy_docker.py`, y 3 fallos previos resueltos**. Ese archivo conserva contratos anteriores de `Popen`, colas compartidas y consultas de salud sin identidad de contenedor. Debe adaptarse y revisarse caso por caso en T48; no se descarta el incremento de fallos ni se marca aceptado. Los tests nuevos de identidad, errores, JSON inválido, exclusión, parada y logs están en `test_local_docker_runtime.py`. Los otros 159 fallos coinciden por nombre con la línea base; ese dato no elimina su deuda ni demuestra que todas sus causas sean idénticas.

El primer intento de regresión produjo 189 fallos backend y 10 frontend. Se corrigieron diferencias de contratos/payloads y defectos encontrados hasta obtener los resultados anteriores. Las pruebas usaron SQLite temporal, workspaces temporales y claves de IA vacías. El backend real del usuario y su base no se usaron como destino de tests.

Evidencias locales (ignoradas por Git): `.run/local-focused.txt`, `.run/frontend-focused.txt`, `.run/frontend-tests-current.txt`, `.run/frontend-build-current.txt`, `.run/backend-tests-final-stage.txt`, `.run/backend-baseline.txt`, `.run/frontend-baseline.txt` y `.run/regression-comparison.json`. La comparación baseline procede de una copia de HEAD bajo `.run/baseline`, con las mismas dependencias locales; no se alteró la rama o checkout del usuario.

Reproducción enfocada, desde raíz con `.venv`:

```powershell
$env:DATABASE_URL='sqlite://'
$env:GEMINI_API_KEY=''; $env:GOOGLE_API_KEY=''; $env:GROQ_API_KEY=''
$env:OPENAI_API_KEY=''; $env:ANTHROPIC_API_KEY=''
.venv\Scripts\python.exe -m pytest backend/tests/test_local_execution_mode.py backend/tests/test_local_docker_runtime.py backend/tests/test_devops_service.py backend/tests/test_pipeline_runner.py -q
```

Las fixtures crean su propia BD SQLite temporal. Para frontend: `npm.cmd test -- --run src/test/local_execution_mode.test.tsx src/test/views_devops_security_export.test.tsx` y `npm.cmd run build`, desde `frontend`.

### Hallazgos: avance, sin cierre E2E

| Hallazgos | Situación tras esta etapa |
|---|---|
| D01 | Sigue bloqueando exclusivamente la validación/ejecución Docker real; no el flujo de fuentes. |
| D02 | Default administrativo cambiado a permitido; elección por sesión sigue SOURCE_ONLY. Indisponibilidad conserva decisión explícita. |
| D03 / D08 / D11 | Corregidos en generación/operación y comprobados con sockets reales y simulación: puerto efectivo, BD interna y elección persistida; matriz real pendiente. |
| D04 / D07 | UI con seguimiento por polling y contratos alineados; pruebas enfocadas/build pasan. SSE completo pendiente. |
| D05 / D06 | Correcciones probadas con dependencias simuladas: salud actual y parada con error. Falta contenedor real. |
| D09 | Migración antigua fuera de alcance; cambios de manifiestos nuevos y ediciones del usuario aún requieren protección/versionado integral. |
| D10 | Primer mecanismo de preparación por proyecto; catálogo, kit/importación/integridad y red externa bloqueada pendientes. |
| D12 | Evidencia vigente requerida para despliegue, build ejecuta pruebas y fingerprint abarca módulos/configuración. Imagen/JAR del mismo snapshot y SQL todavía requieren cierre. |
| D13 / D14 | Persistencia básica, logs acotados, exclusión y timeouts implementados; cancelación, logs vivos, límites globales y limpieza propia pendientes. |
| D15 | Pruebas enfocadas añadidas; suite general y E2E real abiertos. |
| D16 | Se respeta que AgentIA siga nativo. |

### Pendientes prioritarios

1. T48: actualizar los 15 contratos de prueba Docker adicionales y revisar los fallos previos relevantes; mantener las pruebas negativas y los escenarios nuevos.
2. T22: DDL por dialecto/clase/entidad y semillas idempotentes. El runtime actual usa Hibernate `update` y SQL init deshabilitado; no satisface todavía la inicialización del esquema diseñado. El XFAIL estricto conserva ese criterio pendiente.
3. P2: diagnóstico detallado, digests/catálogo, preparación de scanners y Kubernetes, kit portable con integridad y dependencias de AgentIA offline.
4. P4/P5/P6: cancelación y cleanup propios, límites, logs continuos/reconexión, coherencia total snapshot/imagen y entrega ejecutable offline.
5. P7: CI/CD con controles reales (actualmente hay pasos que solo imprimen mensajes) y perfiles Kubernetes completos por BD, validación local y ejecución aislada. No confiar en esas plantillas como certificadas.
6. P8: Docker funcional en Windows para matriz real, CRUD, persistencia, pruebas offline con acceso externo bloqueado e importación de kit limpio. Esto no es requisito para terminar fuentes en el laboratorio.

**Incidencia de aprobación automática:** se rechazó la propuesta de sustituir el archivo de pruebas Docker existente y eliminar el archivo nuevo, al considerarla una mutación destructiva innecesaria para la consulta de Docker que la acompañaba. No se ejecutó esa sustitución/eliminación; ambos archivos se conservaron y se continuó con comprobaciones y cambios independientes. No se necesita esa operación para mantener las pruebas nuevas ni para usar el modo de fuentes.

## 14. Continuación — pruebas, diagnóstico y kit de imágenes

**Fecha:** 04/10/2026. **Base:** se mantiene el checkout `no-docker` / `863553a` confirmado con GitHub. El usuario autorizó continuar. Esta sección prevalece sobre los pendientes y cifras de la etapa anterior.

### Contratos de pruebas y errores

Se adaptó puntualmente `test_qe_deploy_docker.py`, conservando sus 34 escenarios y el archivo nuevo de pruebas. Sus mocks usan ahora la elección Docker explícita, workspace temporal, construcción separada del arranque e identidad inspeccionada. Los asserts verifican `--no-build`, ausencia de pull, puerto propio, salud, parada con fallo, conservación de datos y entrega independiente de logs. Los tests ya no exigen borrar volúmenes al detener ni inventar HTTP 503 cuando no hubo una respuesta; conservan el código HTTP realmente recibido o 0 sin respuesta.

Se corrigieron defectos de producto encontrados: salida vacía/espacios no ocupa el log; errores de comandos incluyen exit code; fallo de smoke conserva su causa. Una excepción al persistir el inicio de una operación deja FAILED y libera el bloqueo, tanto en preparación como despliegue, evitando un BUILDING permanente.

**Resultado:** el archivo de 34 escenarios pasa. La comparación de la última regresión general con HEAD muestra **cero fallos adicionales por nombre y 13 fallos anteriores resueltos**. Los 149 restantes siguen pendientes; no se declara verde la suite global. Esto tampoco certifica que todas sus causas coincidan con HEAD.

### Diagnóstico explícito

Nuevo endpoint `GET /api/v1/devops/{session_id}/diagnostics`, contrato y botón **Diagnosticar Docker** en DevOps. Se ejecuta bajo demanda; los resultados se limpian al cambiar sesión y una respuesta de otra sesión no se presenta en la actual.

Comprueba permiso administrativo, presencia de CLI, contexto, Compose, plugin Buildx, motor Linux, escritura temporal del workspace y espacio libre. Con motor operativo identifica imágenes requeridas mediante ID/digests. Informa `readyForPreparation`, `preparedImagesAvailable` y mantiene `offlineVerified=false`: encontrar imágenes o instalar un plugin no prueba que un build offline pueda finalizar.

En SOURCE_ONLY no consulta CLI/daemon, ni realiza la prueba temporal de escritura; devuelve SKIPPED_BY_CHOICE. Sesiones inexistentes se rechazan antes de diagnosticar. Con Docker solicitado y capacidad ausente conserva Reintentar/Continuar sin Docker. El endpoint trabaja fuera del hilo async del servidor.

**Comprobación real del equipo:** CLI presente, contexto `desktop-linux`, Compose `v5.5.1`, Buildx `v0.36.1-desktop.1`; motor inaccesible (exit code 1, pipe `dockerDesktopLinuxEngine` ausente). El workspace temporal era escribible y se midió espacio libre. No se prepararon imágenes ni se modificaron permisos/virtualización. El plugin Buildx está presente; su backend de construcción no se probó con motor real.

Se probó también el health endpoint del backend real con PATH vacío y subprocesos prohibidos, manteniendo `DOCKER_ENABLED=True`. Respondió UP sin Docker. Esa salud corresponde a AgentIA; no se usa para certificar un microservicio.

### Kit portable: primera versión para imágenes del proyecto

Los proyectos nuevos incluyen `export-offline-kit.ps1`, `import-offline-kit.ps1` y `OFFLINE_KIT.md` además de los cuatro scripts iniciales. No se requiere Java/Maven/Gradle ni AgentIA para ejecutar estos scripts en el equipo destino; sí Docker Linux cuando se solicita ejecutar contenedores.

1. Tras preparar el proyecto con conexión, exportar a una carpeta nueva **fuera de las fuentes**. No se sobrescribe un kit previo.
2. El kit incluye builder/dependencias actuales, runtime y BD cuando corresponda en `images.tar`; un `manifest.json` registra versión de formato, timestamp UTC, fingerprint, IDs, OS, arquitectura/digests y SHA256/tamaño. Nunca se marca offlineVerified por transferirlo.
3. Importar verifica que los manifiestos de build actuales coincidan con los que originaron los scripts y que no se añadieron otros fuera de caches. Comprueba fingerprint, catálogo, tamaño y SHA256 antes de llamar a Docker load. No extrae paths proporcionados por un archivo: el nombre admitido es `images.tar`.
4. Rechaza arquitectura no compatible con el motor Linux y tags existentes con ID distinto, sin sobrescribirlos automáticamente. Después de cargar comprueba las identidades importadas.
5. Nuevas dependencias/manifiestos requieren regenerar scripts y repetir preparación. El kit pesado queda fuera del ZIP de fuentes. SHA256 detecta corrupción; no es una firma de autenticidad: usar kits de procedencia confiable.

**Ejecución comprobada:** nueve escenarios sobre Windows PowerShell real con la función Docker simulada: transferencia válida, tamaño incorrecto, hash incorrecto manteniendo tamaño, fingerprint incompatible, manifest de build modificado, módulo nuevo, manifest bajo cache excluido, tag local distinto y arquitectura distinta. Los casos inválidos fallaron antes de Docker load. No se cambiaron políticas de ejecución.

En este entorno `Get-FileHash` no estaba disponible en Windows PowerShell; se corrigió el generador para calcular SHA256 mediante streams .NET, sin instalar módulos ni cambiar restricciones. Se comprobaron los scripts corregidos ejecutándolos, no solo buscando cadenas.

**Límites:** aún no se exportaron/importaron imágenes reales. El kit no incluye Python/Node/paquetes de AgentIA, bases de scanners, herramientas/imágenes Kubernetes ni imagen de aplicación. No se completa T16/T40 ni se promete funcionamiento offline integral con esta transferencia parcial. Sigue siendo obligatorio demostrar build/pruebas/arranque con red externa bloqueada y entorno limpio.

### Verificación de esta continuación

| Comprobación | Resultado | Evidencia |
|---|---|---|
| Backend enfocado final | **107 PASS, 1 XFAIL** | `.run/docker-focused-stage2.txt`; incluye fuentes/grafo/Auto-Pilot, 34 casos anteriores, diagnóstico, kit, errores, identidad y exportación. Docker/HTTP de microservicio simulados. XFAIL SQL estricto sigue abierto. |
| Scripts de kit ejecutados en Windows PowerShell | **9 PASS** | `.run/kit-powershell.txt`; archivos/hash/JSON y scripts reales, Docker simulado. |
| UI enfocada | **11 PASS** | `.run/diagnostics-ui.txt`; diagnóstico explícito y ausencia de despliegue automático. |
| Build TypeScript/Vite | **PASS** | `.run/diagnostics-build.txt`; aviso de tamaño del bundle, sin error de compilación. |
| Sintaxis PowerShell | **12 scripts, 0 errores** | Preparar/iniciar/detener/limpiar/exportar/importar para Maven y Gradle, generados en `.run/script-validation`. |
| Regresión general backend más reciente | **986 PASS, 149 FAIL, 3 SKIP, 1 XFAIL** | `.run/backend-stage2.txt`. Fue anterior a los últimos casos/guard del kit y persistencia; estos se probaron después en la suite enfocada. |
| Comparación con HEAD original | **0 fallos adicionales; 13 previos resueltos** | `.run/regression-stage2.json`, por nombre de test; baseline 162 FAIL. |
| Diagnóstico Docker real | **Motor no disponible** | `.run/real-docker-diagnostics.json`; no se iniciaron contenedores. |

La última regresión frontend completa anterior conserva 63 PASS/9 FAIL; después se comprobó la UI modificada con las 11 pruebas enfocadas y build. El contrato DevOps actual, derivado de la aplicación, incluye **15 paths y 21 schemas** con referencias resueltas. Se corrigió también `run_all.bat` para escuchar backend en `127.0.0.1`, coherente con los otros lanzadores y Vite.

### Próximos pendientes

- SQL/semillas (T22) sigue abierto y con XFAIL estricto. Se revisó el generador y se encontró que DDL/JPA pueden usar nombres de tabla y tipos distintos, y que recuperar modelos desde código no abarca todavía todos los módulos. No se habilitó ciegamente SQL init ni se presentó Hibernate update como aplicación del esquema diseñado.
- Kit integral: catálogo/digests, scanners, Kubernetes y dependencias Python/Node; transferencia real, snapshots y prueba offline con caches frías.
- Cancelación, cleanup propio, límites, SSE con IDs/reconexión y captura continua app/BD.
- Corrección y validación local CI/CD/Kubernetes. GitLab remoto sigue aplazado.
- Matriz Docker real Maven/Gradle × PostgreSQL/MySQL/H2, CRUD y persistencia cuando el motor sea accesible. El laboratorio sin Docker puede seguir completando fuentes; no se intenta habilitar virtualización o saltarse permisos.

## 15. Continuación — historial durable y reconexión SSE

**Fecha:** 04/10/2026. **Base comprobada de nuevo:** `no-docker`, HEAD `863553aaf43d0b7178f2e37cf6d4cbdf96a7efed`. Se conservan los cambios locales anteriores. Esta etapa no ejecutó contenedores ni volvió a consultar el motor; sigue pendiente demostrar su disponibilidad.

### Defecto corregido y comportamiento actual

El stream anterior calculaba el cursor usando la posición dentro de una lista limitada a 1000 mensajes. Una vez llena, nuevas entradas mantenían el mismo tamaño y podían quedar sin entregar al suscriptor. Los IDs volvían a empezar en cada conexión y se ignoraba `Last-Event-ID`, causando repetición del historial al reconectar.

- El historial nuevo conserva un contador monotónico por sesión y registros con ID, independientemente de la rotación. Mantiene como máximo 1000 entradas y 4000 caracteres por mensaje.
- Se escribe a un archivo temporal y se reemplaza atómicamente `logs.json`; la memoria solo avanza después del commit. Si falla el reemplazo, se conserva el historial confirmado y no se consume el ID.
- Reiniciar el backend o vaciar el cache recupera el contador del archivo. Los suscriptores tienen cursores independientes; no consumen una cola compartida.
- El endpoint SSE admite `Last-Event-ID` numérico no negativo, de hasta 20 dígitos, y devuelve solo las entradas posteriores. Un cursor fuera del historial disponible produce un evento `log-reset` con causa y primer ID retenido, seguido del historial disponible. No inventa entradas que ya fueron rotadas.
- Las rutas de historial y stream comprueban existencia de sesión y workspace antes de responder; un ID desconocido devuelve 404. Un cursor mal formado devuelve 400 antes de abrir el stream. El contrato OpenAPI registra el header y `text/event-stream`.
- Sigue disponible el formato REST `{logs: string[]}`. El formato antiguo de archivo se lee conservando sus mensajes; se convierte al nuevo al agregar una entrada. Un archivo corrupto o con IDs inconsistentes falla explícitamente, sin sobrescribir evidencia ni reiniciar el contador silenciosamente.
- Redacción ampliada para valores entre comillas/JSON, Bearer y credenciales en URLs, incluida la lectura de historial anterior. Sigue siendo redacción por patrones, sin garantía para todos los formatos posibles de secretos.

El mecanismo usa el header de reconexión definido por el [estándar SSE de WHATWG](https://html.spec.whatwg.org/multipage/server-sent-events.html#the-last-event-id-header). `log-reset` es un evento propio de AgentIA para informar pérdida por retención o cursor incompatible.

### Verificación

| Comprobación | Resultado | Alcance |
|---|---|---|
| Primera selección de logs/runtime/contratos Docker | **58 PASS** | `.run/log-reconnect-focused.txt`; persistencia/streams reales, Docker simulado. |
| Regresión enfocada final | **117 PASS, 1 XFAIL** | `.run/docker-focused-stage3.txt`; los 107 casos anteriores más 10 escenarios nuevos. El XFAIL estricto SQL/semillas permanece abierto. |
| Rotación y reconexión | **PASS** | Entrega después de llenar/rotar historial, IDs tras reinicio, replay sin duplicados, suscriptores con cursores distintos y avisos de cursor atrasado/adelantado. |
| Persistencia y errores | **PASS** | 40 escrituras concurrentes reales con IDs únicos, fallo de reemplazo simulado sin pérdida del archivo confirmado, formato anterior, archivo corrupto, límites/redacción/escape de SSE. |
| API | **PASS** | TestClient real, header de reconexión, 400/404; pruebas de lectura/stream prohíben llamadas a Docker/subprocesos. |
| Contrato y formato | **PASS** | OpenAPI regenerado: 15 paths, 21 schemas; `git diff --check` sin errores, únicamente avisos LF/CRLF. |

El intento inicial dentro del sandbox no pudo abrir el SQLite temporal de las fixtures y terminó con errores de setup; no fue un resultado de comportamiento del producto. La repetición autorizada fuera de esa restricción usó SQLite/workspaces temporales aislados y pasó. No se modificó la base del usuario ni las restricciones del laboratorio.

### Límites y próximos pendientes

T34/T35 avanzaron en backend, pero **no se marcan completos**: la vista React todavía usa polling; falta su suscripción SSE, tratamiento visual de `log-reset` y prueba en navegador. Build/preparación aún capturan salida al terminar cada comando; falta captura continua de build/aplicación/BD con origen y timestamp. La persistencia y exclusión son para un proceso backend; no se certifica coordinación de varios workers escribiendo el mismo archivo.

No se repitió la suite global ni el build frontend en esta etapa porque no hubo cambios frontend; la última regresión general permanece 986 PASS/149 FAIL/3 SKIP/1 XFAIL y la UI completa 63 PASS/9 FAIL, con los límites documentados en la sección 14. Los 117 PASS no convierten esas suites en verdes.

Se mantienen pendientes SQL/semillas, kit offline integral, cancelación/cleanup/límites, CI/CD/Kubernetes y la matriz real Docker/offline. El modo de fuentes sigue sin invocar Docker para terminar su flujo; GitLab remoto continúa aplazado.

### Actualización del entorno proporcionada por el usuario

El usuario confirmó que las pruebas Docker se harán en este mismo equipo y proporcionó una ejecución de PowerShell: CLI 29.7.2, contexto `desktop-linux`, Compose v5.5.1 y fallo del servidor por ausencia de la pipe `dockerDesktopLinuxEngine`. Esta evidencia confirma la indisponibilidad actual del motor, pero no determina su causa ni demuestra que falte instalar Docker Desktop.

Se comprobó después que `docker` resuelve a `C:\Users\willi\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe`; el plugin `docker desktop` está disponible. `docker desktop status` terminó con exit code 1: no pudo obtener el estado e indicó iniciar mediante `docker desktop start`. Esto corrige la interpretación de la búsqueda anterior limitada a Program Files: hay archivos de Docker Desktop en la instalación por usuario. Todavía no se certifica que el motor pueda arrancar.

Siguiente comprobación del usuario: iniciar Docker Desktop (`docker desktop start --timeout 60` o desde Inicio), esperar su arranque y ejecutar `docker info` de nuevo. Si falla, conservar el error para distinguir inicio pendiente de requisitos de virtualización/WSL o restricciones. No se indicó cambiar BIOS, permisos ni políticas. Referencia: [Docker Desktop CLI start](https://docs.docker.com/reference/cli/docker/desktop/start/). Los pendientes de código independientes del motor pueden continuar.

## 16. Motor disponible — primer despliegue real

**Fecha:** 04/10/2026. El usuario inició Docker Desktop en este mismo equipo. Su `docker info` mostró servidor 29.7.2, Linux x86_64 sobre WSL2, 12 CPU y 7.68 GiB, 12 contenedores detenidos y 8 imágenes previas. Se confirmó servidor/OS/arquitectura mediante CLI. El sandbox del agente deniega la pipe; la consulta y las pruebas se ejecutaron con escalación autorizada, sin cambiar permisos del sistema. La indisponibilidad inicial del motor queda superada en este equipo, sin generalizar ese resultado al laboratorio.

### Maven/H2: prueba real aprobada

Proyecto nuevo aislado `agentia-probe-4545d80ebc`, bajo `.run/real-docker/`, generado mediante los cinco stages deterministas actuales y el generador DevOps; sin llamadas IA ni uso de sesiones/BD del usuario. Se ejecutaron los scripts PowerShell generados sin bypass de políticas ni Java/Maven nativos en Windows.

1. Preparación inicial online: descargó la imagen Maven fijada y dependencias de Spring Boot 3.2.3/Java 21; ejecutó tests y creó builder/runtime preparados.
2. `start-local.ps1 -Port 19080`: build con `--no-cache`, Maven `-o` y red de build deshabilitada, ejecutó **8 tests Java, 0 fallos/errores/skips**, empaquetó el JAR y Compose lo arrancó con `--no-build --pull never`. Uno de los ocho tests es el antiguo `assertTrue(true)` de ApplicationTests; no se presenta como prueba de carga del contexto. Los otros incluyen servicio, controller y repositorio; el contexto/runtime se comprobó adicionalmente mediante health y CRUD reales.
3. Publicación real comprobada `127.0.0.1:19080`; Actuator devolvió 200/UP. Creación 201, lectura 200 con el dato creado, validación de nombre vacío 400, borrado 204 y lectura posterior 404.
4. `stop-local.ps1` seguido de `compose up --no-build --pull never --wait`: el registro creado seguía disponible después de reiniciar, probando persistencia H2 en su volumen.
5. Parada final con `compose -p agentia-probe-4545d80ebc down`, sin eliminar el volumen. No se iniciaron ni eliminaron contenedores previos del usuario; se descargaron/crearon imágenes nuevas de preparación y prueba.

Evidencia: `.run/real-docker/agentia-probe-4545d80ebc/probe-result.json` y logs de preparar/iniciar/detener/reiniciar. Harness reproducible `.run/real_local_probe.py`; acepta `--build maven|gradle --database H2|POSTGRESQL|MYSQL`. Credenciales de BD de pruebas se generan efímeramente, sin almacenarlas en fuentes/reportes.

Se reforzó el Dockerfile generado con `RUN --network=none` explícito, además del `build.network: none` que ya establece Compose; así la restricción no depende exclusivamente de invocar Compose. Pruebas de regresión relacionadas **50 PASS, 1 XFAIL** en `.run/real-probe-unit.txt`. XFAIL SQL/semillas permanece pendiente.

**Alcance:** acredita scripts y runtime de un proyecto Maven/H2 sencillo. No prueba el flujo API/UI de despliegue, otros motores/builds, proyectos multimódulo, todos los modelos posibles, SQL/semillas ni kit importado. El build sin red no constituye validación offline integral del equipo: las imágenes/bases se resolvieron inicialmente con conexión y no se bloqueó globalmente el acceso externo del host/motor. `offlineGlobalVerified=false` se conserva en el informe.

### Matriz básica real: seis combinaciones aprobadas

Se completó la misma prueba de scripts, health, CRUD/validación y conservación de datos en **6/6 combinaciones**, de forma secuencial:

| Build | BD | Resultado | Proyecto aislado / evidencia |
|---|---|---|---|
| Maven | H2 | **PASS** | `agentia-probe-4545d80ebc` |
| Gradle | H2 | **PASS** | `agentia-probe-834e073540` |
| Maven | PostgreSQL | **PASS** | `agentia-probe-8893e3b55f` |
| Maven | MySQL | **PASS** | `agentia-probe-299a28a41d` |
| Gradle | PostgreSQL | **PASS** | `agentia-probe-dc26cd7a0b` |
| Gradle | MySQL | **PASS** | `agentia-probe-612717f16f` |

Informe conjunto `.run/real-docker/matrix.json`, runner `.run/run_probe_matrix.py`; cada carpeta contiene `probe-result.json` y logs. Los seis proyectos finalizaron con `compose down` sin eliminación de volúmenes. PostgreSQL 16.4-alpine y MySQL 8.0.40 se descargaron y usaron realmente. Los builds Gradle completaron `test` y `bootJar` sin red; no se infiere un número exacto de tests a partir del resumen quiet de Gradle.

**No equivale a cerrar T50/T51/T52 ni al objetivo completo:** esta matriz usa un modelo sencillo Item, scripts standalone y volúmenes propios. Quedan despliegue mediante API/UI con evidencias/fingerprints, multimódulo/modelos más complejos, SQL/semillas, puertos ocupados y concurrencia real, cancelación y fallos, y offline integral/importación limpia. Tampoco cubre interacción entre despliegues simultáneos del mismo nombre: el generador actual usa la etiqueta de imagen de aplicación `{service_name}:local`, compartida por nombre; revisar aislamiento/versionado de imágenes en T20/T28 antes de certificar concurrencia entre sesiones. La prueba secuencial no elimina ese riesgo.

### Transferencia real de kit Maven/H2

Se ejecutaron los scripts generados `export-offline-kit.ps1` e `import-offline-kit.ps1` con Docker real y Windows PowerShell, sin bypass. Exportación a carpeta nueva `.run/real-kit-5d86efb2`, fuera de las fuentes del proyecto; `images.tar` contiene builder Maven/H2 y runtime, **411117568 bytes**, SHA256 `c9858c8d2e0742bfafc913f84de2520885e596f41dd08b26e908c46f35136eb0`. Importación comprobó manifiestos, tamaño/hash, IDs y arquitectura y completó Docker load de las dos imágenes, con inspección posterior correcta. Evidencias `.run/real-kit-export.txt`, `.run/real-kit-import.txt` y manifest del kit.

**PASS de transferencia real en el mismo motor**, con ambas imágenes ya presentes y con IDs coincidentes. No es importación en motor limpio ni certificación offline integral; no se eliminaron imágenes para simular limpieza. El kit/manifest mantiene `offlineVerified=false`. Scanners, Kubernetes, dependencias Python/Node e imagen de aplicación siguen fuera de esta primera versión.

## 17. Aislamiento de imágenes, puertos y datos entre sesiones

**Fecha:** 04/10/2026. Se corrige el riesgo identificado al finalizar la matriz: el tag de aplicación se compartía entre proyectos del mismo nombre (`{service_name}:local`). Reconstruir uno podía reemplazar la imagen que otro usaría al reiniciar.

### Implementación y prueba real

El generador Compose usa ahora `${COMPOSE_PROJECT_NAME}-{service_name}:local`. El nombre efectivo de proyecto viene del `-p` usado por backend/scripts; Compose lo expone para interpolación y el flag tiene precedencia sobre la variable de entorno ([referencia oficial](https://docs.docker.com/reference/compose-file/version-and-name/), [precedencia](https://docs.docker.com/compose/how-tos/environment-variables/envvars/)). Contenedores/volúmenes ya estaban separados por proyecto; ahora la imagen de aplicación también lo está. La guía generada explica conservar el nombre al usar Compose manualmente. No se migraron proyectos antiguos.

Se añadió `backend/tests/test_local_docker_real_isolation.py`, prueba real **opt-in** mediante `AGENTIA_RUN_REAL_DOCKER=1`. Por defecto queda SKIP antes de consultar Docker, conservando el uso del laboratorio. Requiere builder Maven/H2 y runtime previamente preparados; no descarga imágenes ni instala Java silenciosamente. Genera fuentes nuevas mediante stages actuales, usa scripts Windows reales y conserva volúmenes al detener.

**PASS real**, 85.83 segundos. Dos proyectos diferentes, ambos llamados `probe-service`, se mantuvieron activos al mismo tiempo:

| Proyecto | Puerto localhost | Imagen |
|---|---|---|
| `agentia-isolation-6ebe3b3418-a` | 19100 | `agentia-isolation-6ebe3b3418-a-probe-service:local` |
| `agentia-isolation-6ebe3b3418-b` | 19101 | `agentia-isolation-6ebe3b3418-b-probe-service:local` |

- El segundo pidió 19100, detectó el puerto ocupado y anunció 19101.
- Se inspeccionaron IDs reales, etiquetas del proyecto, usuario `10001:10001` y publicación exclusiva `127.0.0.1`.
- Ambas imágenes tenían IDs distintos y servían marcadores distintos empaquetados en sus propios JAR. Construir/reconstruir B no cambió el ID del tag A ni su respuesta.
- Detener B dejó A respondiendo con su propio registro. Reiniciar B sin build/pull sirvió el nuevo JAR y conservó su registro anterior.
- Cada BD H2 tenía exactamente su registro, sin compartir datos. La parada final de ambos proyectos pasó sin borrar volúmenes; recursos anteriores del usuario no se usaron como destino.

Evidencia `.run/real-isolation/6ebe3b3418/result.json` (IDs, puertos, checks y `cleanupErrors=[]`), logs por proyecto y `.run/real-isolation-pytest-final.txt`. El primer intento falló por una suposición incorrecta del **harness** sobre el orden de `compose config --images`; se corrigió consultando `services.probe-service.image` en JSON. El informe inicial se conserva en `.run/real-isolation-pytest.txt` y carpeta `15b441b6ca`; su proyecto iniciado fue detenido por el cleanup. Se fijó además el puerto efectivo al recrear B desde el proceso de prueba, en vez de asumir que el entorno de un PowerShell hijo modifica al padre.

### Regresión y límites

- Suite enfocada **117 PASS, 1 SKIP, 1 XFAIL**, `.run/isolation-focused.txt`. SKIP es el opt-in Docker; XFAIL sigue siendo SQL/semillas pendiente. La ejecución real opt-in anterior es un resultado separado, no se presenta como suite global verde.
- `git diff --check` pasó. No hubo cambios frontend en esta etapa ni repetición innecesaria de su build/suite.
- **T28/T52 avanzan, sin cerrarse completamente:** dos servicios coexistiendo no prueba una carrera de arranque exactamente simultáneo. Faltan concurrencia API/UI, límites/cancelación y snapshots/identidad de imagen frente a ediciones durante el build (T20). El tag por proyecto sigue siendo mutable dentro de la misma sesión; no equivale a un tag inmutable por fingerprint.
- Copiar dos proyectos a carpetas con el mismo nombre no crea automáticamente nombres Compose diferentes: usar identidades de proyecto distintas si se desea independencia. Sesiones nuevas ya usan IDs diferentes.
- SQL/semillas, kit offline integral, suscripción UI a logs, CI/CD/Kubernetes y aceptación integral siguen pendientes. Las seis combinaciones de la etapa anterior se ejecutaron antes de esta corrección; el cambio actual se validó realmente con dos proyectos Maven/H2 y regresión enfocada, sin afirmar una nueva matriz completa.

Reproducción opt-in desde raíz con builder/runtime preparados:

```powershell
$env:DATABASE_URL='sqlite://'
$env:AGENTIA_RUN_REAL_DOCKER='1'
.venv\Scripts\python.exe -m pytest backend/tests/test_local_docker_real_isolation.py -q
Remove-Item Env:AGENTIA_RUN_REAL_DOCKER
```

No cambiar políticas de PowerShell ni virtualización para esta prueba. En un equipo sin Docker, conservar la variable sin establecer y continuar la generación/exportación de fuentes.

## 18. SQL, migraciones y semillas en despliegue real

### Cambios de esta etapa

- T22 avanza mediante Liquibase, incluido como dependencia gestionada por Spring Boot para Maven y Gradle. Los proyectos nuevos empaquetan `001-schema.sql` y, cuando existe `data.sql` no vacío, `002-seed.sql`, con changelog en el classpath del módulo ejecutable. No se montan scripts del host dentro del contenedor de BD.
- Hibernate usa `validate`, Liquibase está habilitado y `spring.sql.init.mode=never`. El historial de cambios en la BD controla la ejecución única: reiniciar no vuelve a insertar las semillas. La construcción sigue ejecutando tests sin red; la preparación inicial incorpora las dependencias nuevas.
- JPA determinista conserva el nombre explícito de tabla/columna, nulabilidad y unicidad. Se corrigieron tipos de fecha, UUID, Float y BigDecimal; el decimal usa precisión 19 y escala 2. El DDL distingue identity estándar para PostgreSQL/H2 de AUTO_INCREMENT para MySQL y los tipos específicos de MySQL.
- Los SQL raíz editados por el usuario prevalecen. Una migración inicial existente diferente se rechaza, sin sobrescribirla ni borrar datos. Se conservan versiones adicionales agregadas al changelog; los conflictos de destinos y propiedades se comprueban antes de copiar migraciones. Los tests H2 llevan un esquema derivado del Java real, separado del SQL y semillas de producción.
- La recuperación de entidades recorre módulos anidados y solo considera clases con `@Entity`, evitando convertir DTOs en tablas. Un fixture antiguo omitía esa anotación; se corrigió el fixture para representar una entidad JPA válida.
- El contrato histórico XFAIL exigía inicialización sin versión en cada arranque. Se reemplazó por comprobaciones de Liquibase, `validate` y ausencia de bind mounts, conservando la finalidad y el caso de prueba. El arranque/reinicio real con semillas sustenta esta corrección; no se presenta como cierre de toda T22.

### Evidencia inicial y reproducción

- Maven/H2: `agentia-probe-6fb926dcfd`, PASS. Maven/PostgreSQL: `agentia-probe-0c84d9d386`, PASS. Tabla explícita `inventory_records`, decimal y fecha no nulos, seed inicial, CRUD y validación HTTP; al reiniciar persistieron el registro nuevo y una sola semilla.
- Se conserva el intento MySQL `agentia-probe-8dbd08dcae`: arrancó y pasó CRUD, pero falló la lectura posterior porque el harness no conservaba el puerto alternativo al reiniciar. Se corrigió el entorno del proceso padre; este resultado permanece FAILED, sin modificar su evidencia.
- La prueba reproducible está en `scripts/verify_local_database.py` y `backend/tests/test_local_docker_real_migrations.py`. La aceptación real usa `AGENTIA_RUN_REAL_SQL=1`; sin esa variable, los seis casos se omiten antes de invocar Docker, preservando el flujo del laboratorio.
- Ejecución desde la raíz en PowerShell, con Docker Desktop iniciado y la preparación online autorizada:

```powershell
$env:DATABASE_URL='sqlite://'
$env:PYTHONPATH='backend'
$env:AGENTIA_RUN_REAL_SQL='1'
.venv\Scripts\python.exe -m pytest backend/tests/test_local_docker_real_migrations.py -q
Remove-Item Env:AGENTIA_RUN_REAL_SQL
```

Cada proyecto nuevo guarda logs y `probe-result.json` bajo `.run/real-docker/agentia-probe-*`. El runner conserva el puerto realmente asignado, comprueba el avance de identity tras la semilla y detiene solo sus contenedores al finalizar, conservando los volúmenes. No toca los recursos anteriores del usuario.

### Límites de aceptación

T22 permanece parcial: la matriz tipada no cubre relaciones complejas, enums, claves compuestas o claves UUID; la generación determinista todavía fuerza Long/identity en la PK. La recuperación por expresiones regulares no interpreta todo JPA. Se preservan SQL editados aunque sean incompatibles: el error debe resolverse mediante una versión nueva, no mediante borrado ni `ddl-auto=update`. La evolución real y el rechazo de checksum se comprobaron después en Maven/H2, según la evidencia al final de esta sección; faltan otros modelos, motores y edición por API/UI.

No se afirma instalación limpia, desconexión global del host ni kit offline integral. No se cierran CI/CD/Kubernetes, observabilidad UI, cancelación o aceptación completa. GitLab remoto sigue aplazado; no se modifican permisos ni virtualización del laboratorio.

### Regresión y evolución comprobadas

- Regresión enfocada: **147 PASS, 7 SKIP opt-in, sin XFAIL** (`.run/sql-focused-final.txt`). Generación offline, migraciones y manifiestos: **22 PASS** (`.run/sql-generation-regression.txt`).
- La primera suite general dio 1.013 PASS / 151 FAIL / 10 SKIP: dos fallos nuevos eran comparaciones congeladas del Java antiguo. Se conservaron el JSON histórico y todos sus archivos; `fixtures/local_deployment_java_baseline.json` agrega únicamente ocho salidas Java revisadas (columnas/nombres y tipos), sin generar expectativas durante pytest ni omitir comparaciones. Los demás artefactos siguen comparándose byte a byte contra el registro original.
- Suite general definitiva: **1.015 PASS, 149 FAIL, 10 SKIP**, sin XFAIL. Los 149 nombres fallidos ya existían en la base `no-docker`; comparación contra HEAD: **0 nuevos y 13 resueltos** frente a los 162 originales. Evidencias `.run/sql-backend-full-final.txt` y `.run/regression-sql-final.json`. La suite global sigue sin estar verde.
- Evolución real Maven/H2 sobre `agentia-probe-dd974cb030`: **PASS**. Alterar la migración inicial produjo `ValidationFailedException` y diferencia de checksum; el servicio no arrancó. Se restauró el script inicial, se agregó `003-extra.sql` al changelog y se comprobó vía HTTP la semilla anterior más la nueva. Tras parar/reiniciar ambas aparecieron exactamente una vez. Contenedores detenidos; volumen, nueva versión y logs conservados. Resultado `evolution-result.json`, logs `checksum-runtime.log` y `version-*.log` en ese workspace.
- Reproducción permanente: `scripts/verify_local_migration_evolution.py --workspace <probe-H2-nuevo> --port 19200`, usando el mismo Python/PYTHONPATH. Acepta solo un probe H2 con semillas aprobado bajo `.run/real-docker`, detenido y sin una versión 003 previa. Modifica únicamente ese proyecto; conserva la nueva migración y los datos para inspección. No se repite sobre el proyecto ya evolucionado.
- Maven/MySQL repetido: `agentia-probe-2a2764cacc`, PASS. Primer Gradle/H2 `agentia-probe-1424b13c06`: FAILED por puerto ocupado durante una construcción paralela, con tests Java/build aprobados; evidencia conservada. El script nuevo comprueba disponibilidad después del build. Gradle/H2 repetido `agentia-probe-1a72542ac1`: PASS.

La evolución y rechazo de checksum ya tienen evidencia real en Maven/H2. No se extiende esa conclusión automáticamente a relaciones complejas, a todos los motores o al flujo completo de edición/API/UI. La tarea T22 sigue parcial por esos límites.

### Cierre de la matriz y recuperación tras interrupción

La ejecución original de pytest fue interrumpida antes de completar MySQL y la repetición de aislamiento. Se conservan los logs parciales, `interruption-result.json` del probe `agentia-probe-bfb52a6d7d` y de `.run/real-isolation/f1869a42c4`. Al retomar se detuvo únicamente el contenedor A pendiente de esa prueba; ambos proyectos se limpiaron sin eliminar volúmenes. Estos intentos no se presentan como aprobados.

Matriz SQL real consolidada: **6/6 combinaciones PASS**, a partir de los resultados individuales originales y retomados:

| Build | BD | Proyecto aprobado |
|---|---|---|
| Maven | H2 | `agentia-probe-dd974cb030` |
| Gradle | H2 | `agentia-probe-1a72542ac1` |
| Maven | PostgreSQL | `agentia-probe-4e344e3406` |
| Gradle | PostgreSQL | `agentia-probe-da3fb3d790` |
| Maven | MySQL | `agentia-probe-1218286c4a` |
| Gradle | MySQL | `agentia-probe-02368d30d3` |

Todos los casos tienen SQL tipado, migraciones, seed única, CRUD/validación y persistencia tras reinicio, con comandos de parada final aprobados. La preparación es online; el build posterior ejecuta tests con red deshabilitada. El resumen `.run/sql-real-matrix-final.json` conserva cada reporte e indica también si el script de esa ejecución comprobaba el puerto después del build. No se atribuye un único resultado pytest de seis casos a un proceso interrumpido: la reanudación MySQL dio **2 PASS, 4 deselected** en `.run/sql-real-mysql-resumed.txt`.

Aislamiento con las migraciones y scripts actuales: **1 PASS** en `.run/sql-isolation-resumed.txt`, resultado `.run/real-isolation/6bc4bff2ad/result.json`. Dos proyectos con el mismo servicio, puertos 19100/19101, imágenes distintas, reconstrucción/parada de B sin afectar A y datos independientes conservados. No hubo errores de limpieza.

Verificación final: `docker ps` sin contenedores activos; volúmenes y logs de pruebas conservados, sin borrar imágenes/datos ni tocar los recursos anteriores. Rama `no-docker`, HEAD `863553aaf43d0b7178f2e37cf6d4cbdf96a7efed`, sin cambios de rama, commits ni publicación.

Siguiente prioridad del plan: kit offline integral y aceptación en entorno limpio, seguida de observabilidad/cancelación y corrección/validación de CI/CD y Kubernetes. T22 sigue parcial por modelos complejos y aceptación completa vía API/UI; Docker continúa siendo una elección explícita por sesión, con el flujo de fuentes disponible para el laboratorio.

## 19. Kit nativo offline de AgentIA para Windows

### Implementación de esta etapa

T54/T16 avanzan con `scripts/native_offline_kit.py`, independiente de Docker. La preparación inicial verifica `backend/requirements.txt` contra el entorno instalado, fija sus versiones en un lock y descarga wheels binarios; npm usa el lockfile del frontend. El kit incluye los runtimes locales Python/Node, wheels, caché npm y un helper que se puede ejecutar con el Python incluido, sin PATH global ni instalación de administrador.

El manifiesto registra plataforma/arquitectura, versiones, hashes del requirements/package/package-lock y un catálogo de archivos con bytes/SHA256. La instalación valida todo antes de escribir o ejecutar; exige destino nuevo. Usa `pip --no-index`, `npm --offline`, caché npm privada, configs npm vacías distintas, temporales propios y compilación TypeScript/Vite. No activa Docker, no modifica políticas/permisos ni contiene el `.env` del proyecto. El hash comprueba integridad, no autentica al autor.

Guía: `docs/GUIA_KIT_NATIVO_OFFLINE_WINDOWS.md`. La carpeta de calentamiento `preparation` no es necesaria para transferir el kit. La reutilización de descargas requiere un kit íntegro y locks coincidentes; no acepta automáticamente dependencias nuevas de IA.

### Resultados conservados y correcciones

- Pruebas de integridad y regresión del modo fuentes/kit Docker: **42 PASS**, `.run/native-kit-tests-final.txt`; 7 escenarios nuevos rechazan wheel/metadata alterados, archivos extra/ausentes, dependencias modificadas y arquitectura distinta antes de crear instalación o ejecutar procesos.
- Kit inicial `.run/native-offline-kit-v1`: preparación online completada; primera instalación falló por TEMP denegado en el sandbox. Se corrigió el producto para usar temporales locales escribibles, sin cambiar permisos.
- Preparación/instalación v2: Python instalado offline; npm rechazó una configuración global y de usuario que usaban el mismo archivo vacío. Se corrigieron con dos archivos distintos. Los logs fallidos se conservan; no se declaran PASS.
- Kit definitivo `.run/native-offline-kit-v3`: preparación completada reutilizando las descargas del v1 verificadas por SHA256/lock. npm instaló 302 paquetes en modo offline. La instalación v3 completó wheels, npm y TypeScript, pero Vite falló por EPERM de `realpath` impuesto por el sandbox. Se inició instalación nueva v4 fuera del sandbox para distinguir esa restricción del funcionamiento real, sin instalar nada globalmente ni cambiar permisos del equipo.

El kit nativo no incluye scanners, Kubernetes ni imágenes Docker. Instalar paquetes sin registros no acredita desconexión global de Windows ni compatibilidad con otro equipo limpio. T54 sigue parcial hasta completar aceptación de runtime/flujo y de las restricciones reales del laboratorio. Las etapas anteriores de Docker/SQL siguen vigentes; GitLab remoto continúa aplazado.

### Aceptación nativa completada en este equipo

- Kit v3: **79 wheels**, **302 paquetes npm**, Python **3.12.14**, Node **v24.18.0**; catálogo de **4.891 archivos / 215.757.762 bytes** (sin calentamiento). Preparación inicial online; reconstrucción del kit v3 reutilizó cachés verificadas y npm `--offline`.
- Instalación nueva `.run/native-offline-install-v4`: **PASS**, wheels sin índice/cache pip global, npm en modo offline con caché privada, TypeScript aprobado y build Vite correcto. No usó `.venv` ni `node_modules` del proyecto como destino/base de dependencias. `installation-result.json` conserva versiones y hashes. Se ejecutó fuera del sandbox de Codex que denegaba `realpath` a Node; eso no es una instalación de administrador ni un cambio de permisos del sistema.
- Backend/frontend/proxy nativos con **PATH vacío: PASS**. Puertos localhost temporales 58750/58751; claves IA vacías, sin IA, sin CLI Docker/Python/Node global. `native-smoke-result.json` y logs en la instalación; ambos procesos propios terminaron detenidos. Prueba en `scripts/verify_native_install.py`.
- **33 PASS** desde el entorno Python nuevo (`.run/native-fresh-environment-tests.txt`), incluyendo generación/Auto-Pilot/exportación SOURCE_ONLY para Maven/Gradle × las tres BD con invocaciones Docker prohibidas por los fixtures. Se conservan los resultados honestos de tests omitidos/fallos anteriores y las garantías de exportación sin secretos.
- UI desde el Node/dependencias del kit: **12 PASS, 2 FAIL históricos** (`.run/native-fresh-ui-tests.txt`). Los dos fallos de `workflow_journeys.test.tsx` ya constan en `.run/frontend-baseline.txt`: localizadores antiguos del formulario y del título de navegación. `local_execution_mode.test.tsx` pasa. No se declara una suite UI completamente verde ni se cambiaron esos tests para esconderlos.
- Regresión del kit/flujo de fuentes/kit de imágenes anterior: **42 PASS**. Integridad del kit v3 verificada nuevamente después de instalar: PASS; runtimes/cachés compartidos no se modificaron por la instalación. No se repitió la matriz Docker/SQL porque esta etapa no cambia sus generadores o ejecución.

La prueba instala en un directorio nuevo y sin depender de paquetes/runtimes globales para ejecutar; no es un equipo Windows nuevo. `externalNetworkGloballyBlocked=false` se conserva: pip/npm bloquean sus registros mediante flags y proxies externos inválidos en los pasos offline, pero no se cambió el firewall. Tampoco se certifica un navegador completo ni todas las políticas del laboratorio. T54/T16/T11/T49/T51 avanzan y permanecen parciales; faltan scanners, aceptación global offline y otro entorno limpio, además de los pendientes Docker/CI/Kubernetes.

Rama actual `no-docker`; el usuario guardó los cambios anteriores en `54b6bb3` antes de esta etapa. El diagnóstico de la sección 18 conserva el HEAD de su momento; esta etapa no crea commits, cambia de rama ni publica recursos. Guía nativa incorporada al README.

## 20. Suscripción frontend a logs y recuperación (T34)

La vista de despliegue dejó de reemplazar el terminal mediante polling REST. Ahora mantiene una suscripción SSE con `Last-Event-ID`, credenciales de sesión por cookie, cursor privado y retención de 1.000 mensajes. Reconecta al finalizar el stream; ante error recupera historial/ID mediante REST y reintenta con espera progresiva de 1 a 15 segundos. Procesa `log-reset` cuando el backend informa un cursor fuera del historial y descarta IDs duplicados. No coloca claves IA ni tokens en URLs.

El endpoint REST conserva `logs: string[]` y añade `events`/`lastEventId`, obtenidos de una misma copia bajo el lock de historial para evitar carreras entre mensajes y cursor. Las rutas de lectura continúan validando la sesión y no invocan Docker. Al cambiar de sesión/desmontar se abortan peticiones, se cancelan esperas de reconexión y se limpia el historial; respuestas tardías del estado anterior se descartan. La recuperación de estado sigue activa con polling secuencial, sin solicitudes periódicas solapadas.

El terminal muestra conexión/recuperación e historial vacío de manera explícita. Su título se ajustó a «Registro de Despliegue»: todavía no hay captura continua de stdout de aplicación/BD, por lo que no se anuncia esa capacidad.

Validaciones de esta etapa:

- **17 PASS frontend**: parsing de eventos fragmentados CRLF/Unicode, heartbeat, deduplicación, reconexión desde último ID, reset, recuperación REST tras HTTP 503, cancelación de solicitud/espera, límite de historial, cambio de sesión y regresión de vistas DevOps/seguridad/exportación. `.run/sse-frontend-final.txt`.
- **43 PASS backend**: persistencia/rotación/concurrencia/redacción/SSE, contrato REST extendido, modo laboratorio con Docker prohibido e integridad del kit nativo. `.run/sse-backend-focused.txt`.
- TypeScript `--noEmit` y build de producción Vite **PASS**. Vite conserva su aviso de bundle mayor de 500 kB; no es fallo de compilación.
- Primer intento del test nuevo de cambio de sesión: **FAIL** por consultar un input inexistente. El test corregido verifica el puerto realmente visible y que el resultado anterior no lo sustituya; resultado final PASS. No fue un fallo histórico ni se ocultó.

T34 se marca implementada con estos controles. Frontend usa streams controlados en tests; backend usa rutas FastAPI e historial reales. No se acredita un recorrido completo de navegador conectado al backend ni se repite la suite global histórica. Las pruebas de instalación del kit nativo de la sección 19 corresponden a la versión anterior a esta suscripción; no se afirma una reinstalación integral nueva.

Pendientes: **T35**, captura continua de aplicación/BD con origen/timestamp; cancelación de operaciones; kit integral y aceptación offline aislada; CI/CD/Kubernetes y aceptación general. Docker continúa opcional por sesión; no se modificaron permisos, virtualización, firewall ni contenedores en esta etapa. Se preservan los cambios locales anteriores y la rama `no-docker`.

## 21. Captura de build, aplicación y base de datos (T35)

Se implementó `logged_process.py`: stdout/stderr combinados se publican durante el build y preparación, mediante lectura incremental UTF-8, líneas acotadas y cola final limitada para errores. Se limita cada línea leída a 8.192 caracteres y se descarta su resto; el historial redacta y limita el mensaje a 4.000 caracteres antes de persistir/publicar. Se respeta el timeout y se termina/recolecta el proceso CLI propio. Esto no acredita cancelación completa de tareas BuildKit que pudieran continuar en el daemon; ese pendiente sigue abierto.

`runtime_log_capture.py` mantiene un recolector por sesión, independiente del número de suscriptores, con consultas cada dos segundos y comandos limitados por timeout de cinco segundos. Enumera contenedores por etiqueta Compose y vuelve a validar proyecto y rol en `docker inspect` antes de leerlos. Solo admite `application` y `database`; no recoge contenedores de otros proyectos ni el inicializador de volumen. Guarda eventos con origen, timestamp Docker e ID durable; los de build/preparación llevan timestamp UTC de captura. El frontend presenta esos metadatos igual al recuperar REST y al recibir SSE.

El cursor por ID de contenedor y los conteos de mensajes repetidos en un mismo timestamp se guardan con el lote de eventos mediante un único reemplazo atómico. Un fallo de escritura no publica ni avanza el cursor en memoria. La recarga conserva IDs/cursor y evita duplicados; la rotación del historial mantiene el contador. Los checkpoints están limitados a ocho contenedores y se validan al cargar; corrupción se rechaza sin sustituir la evidencia. Los historiales anteriores siguen legibles sin inventarles timestamp/origen retroactivos.

El recolector se activa al reconciliar el estado del despliegue, incluido después de reiniciar el backend y consultar su estado. Termina si no hay contenedores activos, cambia a SOURCE_ONLY, se solicita parada o falla el acceso al daemon. Ante fallo registra un aviso; una posterior consulta de estado puede reactivarlo. SOURCE_ONLY retorna antes de cualquier llamada Docker o creación de recolector. La parada conserva datos e historial.

Límites deliberados: 1.000 eventos retenidos y consulta `docker logs --tail 1000 --since <cursor>`; los streams stdout/stderr se combinan y ordenan por timestamp. Si se alcanza el umbral se registra `[LOG GAP]` de posible pérdida previa. No se promete captura sin pérdidas bajo ráfagas que superen ese límite, logs rotados/eliminados por Docker o timestamps que retrocedan. El recolector no impone cambios de logging a contenedores existentes.

Validaciones:

- **102 PASS backend**: registros/cursor atómicos, recarga/deduplicación incluso con mensajes iguales en el mismo timestamp, retención, checkpoints corruptos, etiquetas ajenas, logs finales de contenedor detenido, un recolector compartido, build antes del fin del comando, timeout/error/redacción/líneas largas, despliegue y modo laboratorio/kit nativo. `.run/runtime-logs-backend-final.txt`.
- **18 PASS frontend**, incluyendo presentación de origen/timestamp consistente entre REST y SSE y regresiones de T34/modos/vistas. `.run/runtime-logs-frontend.txt`. TypeScript PASS; Vite PASS en `.run/runtime-logs-build.txt`, con aviso previo de tamaño del bundle.
- **1 PASS con Docker real**: imagen local `agentia-runtime:21-v1`, dos contenedores temporales con roles aplicación/BD, sin red/descargas; captura inicial y stdout nuevo, secretos redactados, cursor recargado sin duplicados, consumidores SSE independientes y SOURCE_ONLY sin invocar Docker. `.run/runtime-logs-real-final.txt`; `.run/real-runtime-logs/agentia-log-probe-21956438af/result.json`. Ambos contenedores propios retirados (`cleanup.removed=true`); recursos anteriores no modificados.

La prueba real usa procesos shell para comprobar el transporte/roles Docker; no reemplaza la matriz Spring/SQL ni acredita un recorrido completo de navegador. Se actualizaron fixtures de comandos para la nueva función de lectura; el comportamiento real de pipes/timeout tiene pruebas separadas. No se repitió ni se declaró verde la suite global histórica. T35 se marca implementada; siguiente bloque T36/T37, con kit integral/offline, cancelación, CI/CD/Kubernetes y aceptación final aún pendientes. Rama `no-docker`, sin commits/publicación ni cambios de permisos/virtualización/firewall.

## 22. Estados, acciones y playground (T36/T37 parciales)

Correcciones de esta etapa:

- Acciones DevOps y peticiones del playground se bloquean durante operaciones incompatibles, incluyendo BUILDING, preparación, verificación, smoke, parada y generación de manifiestos. Los servicios DEGRADED admiten smoke/parada. SOURCE_ONLY mantiene generación de artefactos y deshabilita ejecución/playground; no se prueba Docker para entregar fuentes.
- La vista distingue operación pendiente, omitida por elección, fallida y salud aprobada, mostrando `message`/`errorMessage`. La falta de respuesta al desplegar no se convierte automáticamente en «Docker ausente». Reintentar/Continuar sin Docker permanecen cuando corresponde; una indisponibilidad histórica no reemplaza la disponibilidad actual.
- Los resultados tardíos de acciones no se aplican a otra sesión: la guarda usa una revisión, incluso al cambiar A→B→A. También se descartan consultas periódicas anteriores a una acción. Al cambiar sesión se reinician indicadores, artefactos, recursos/modelo, campos, registros locales, consola REST y smoke. Cambio de contenedor/puerto invalida respuestas pendientes del playground y limpia evidencia del runtime anterior.
- Smoke renueva estado tanto tras respuesta como tras error. La parada limpia smoke/consola/registros y deshabilita playground/URLs; usa el resultado confirmado por backend. Un timeout del proxy se presenta como respuesta no confirmada, sin asegurar falsamente que la operación nunca se ejecutó.
- `LocalDeploymentSession.dbEngine` deriva del driver configurado en el contenedor identificado (`H2`, `MYSQL`, `POSTGRESQL`); driver desconocido queda sin confirmar. No se devuelve el ambiente/secretos. La vista usa ese dato y el puerto efectivo, y retira nombres PostgreSQL fijos en badge, formulario, botón y título Compose. Se trata del motor **configurado e inspeccionado**, no de una prueba SQL independiente.

Validación: **23 PASS frontend**, incluida operación BUILDING, DEGRADED, causas, respuesta REST tardía, elección de modo interrumpida por cambio de sesión, actualización tras smoke y limpieza al parar; regresión SSE y vistas. **99 PASS backend**, incluidos cuatro drivers/motores y ausencia de secretos en la respuesta, despliegue/modo laboratorio/logs. Evidencias `.run/actions-ui-final.txt`, `.run/actions-backend-final.txt`. TypeScript/build Vite PASS (`.run/actions-build.txt`); permanece aviso de bundle mayor de 500 kB.

T36/T37 siguen sin marcar completos: esta etapa cubre la vista DevOps y el contrato del motor, con frontend bajo servicios simulados y backend con inspecciones controladas. Faltan revisar etapas/causas en monitor/tests/exportación y validar reinicio operativo y navegador/backend real. No se repitió matriz Docker/SQL ni suite global histórica. Próximo bloque: completar consistencia de esas vistas, seguido de reinicio/cancelación según dependencias. Kit integral/offline, CI/CD/Kubernetes y aceptación final continúan pendientes. Se preservaron cambios locales y rama `no-docker`; no hay commits/publicación ni cambios de permisos/virtualización/firewall.

## 23. Verificación coherente en monitor/tests/exportación (T36)

Se incorporó `VerificationStatus` para mantener un mismo criterio de evidencia en monitor, explorador de código/pruebas y exportación. `PASSED` indica pruebas aprobadas; `FAILED` conserva fallos previos incluso al continuar sin Docker; `SKIPPED_BY_CHOICE`/SOURCE_ONLY informa ejecución omitida y pruebas como artefactos; `ENVIRONMENT_UNAVAILABLE` propone Reintentar/Continuar sin Docker desde despliegue. Sin resultado explícito se indica pendiente/sin evidencia. Si fuentes conserva PASSED histórico, se declara que no hay nueva ejecución.

El monitor dejó de inferir aprobación de sandbox/auto-reparación a partir de COMPLETED o avance de fase. Las etapas de ejecución en fuentes se presentan omitidas con causa, y completar generación no produce la afirmación «Verificado al 100%» ni «Sandbox verificado sin errores». Conteos recibidos no sustituyen el resultado explícito. Explorador/pruebas muestra ese resultado en lugar de usar finalState de reparación como evidencia de tests aprobados.

Exportación dejó de mostrar «Release Ready» incondicionalmente y no afirma que el ZIP siempre contenga Maven/manifiestos ni pruebas ejecutadas. La descarga de fuentes sigue disponible y el backend conserva su validación/gate. El mensaje Git por defecto describe fuentes generadas; no afirma una suite verificada. Cambio de sesión limpia token efímero, rama/resultados/error y descarta respuestas de publicación anteriores; no hubo publicación remota durante esta etapa.

El hook SSE de generación limpia mensajes/evento/conexión al cambiar URL, filtra el evento de la URL anterior durante el cambio y rechaza callbacks de conexiones cerradas. Monitor reinicia completion/fase/acciones y evita aplicar inicio/cancelación a otra sesión. Explorador reinicia artefactos, historial/recuentos de reparación y formulario, y rechaza cargas/resultados tardíos. Reparación manual se bloquea durante RUNNING/QUEUED; inicio/cancelación del monitor tampoco se solapan entre sí. Recibir una corrección sin mensaje no inventa desbloqueo exitoso.

Validación: **31 PASS frontend** en cinco archivos, incluidos resultados explícitos y PASSED histórico en fuentes, generación COMPLETED sin sandbox aprobado, ZIP habilitado sin prometer release y limpieza/rechazo de callbacks SSE de sesiones anteriores. Regresión de monitor/explorador, DevOps/seguridad/exportación y modo laboratorio. TypeScript y build Vite **PASS**, con aviso existente de bundle >500 kB. Evidencias `.run/verification-views-final.txt` y `.run/verification-views-build.txt`.

T36 se marca implementada con estos controles; servicios simulados/componentes/hooks, sin recorrido integral de navegador/backend real ni suite global histórica repetida. No hubo cambios de lógica backend/Docker, por lo que no se repitió la matriz SQL ni se iniciaron contenedores. **T37 sigue parcial en esta etapa**: próximo bloque reinicio operativo T31/T37 con datos conservados y estado/playground actualizado; luego cancelación, kit integral/offline, CI/CD/Kubernetes y aceptación final. Se preservaron cambios locales y rama `no-docker`, sin commits, permisos, virtualización ni firewall modificados.

## 24. Recuperación, reinicio y limpieza (T30/T31/T37)

Este bloque implementa conjuntamente recuperación de estado, parada comprobada, reinicio conservando datos y limpieza explícita, con sus acciones UI y scripts Windows. SOURCE_ONLY retorna antes de invocar Docker en reinicio/limpieza; las acciones de ejecución siguen deshabilitadas en la interfaz. El laboratorio conserva el flujo de fuentes sin Docker.

### Comportamiento implementado

- La reconciliación recupera registros persistidos y consulta contenedores detenidos además de activos. Una aplicación caída por salida anormal/error/OOM se distingue de parada normal; salida 143 admite parada por SIGTERM. BD activa sin aplicación, BD requerida ausente o healthcheck unhealthy degrada el estado. Daemon inaccesible informa DOCKER_UNAVAILABLE/UNKNOWN, conserva identidad/puerto y retira URL; no afirma parada comprobada.
- Parada enumera e inspecciona **todos los contenedores propios** y detiene sus IDs exactos, sin depender de un Compose editado. Confirma que no quede ninguno activo y verifica retornos; fallo/timeout queda FAILED con salud desconocida. Conserva volúmenes, redes y contenedores detenidos.
- Reinicio usa la imagen existente con `--no-build --pull never`, valida manifiesto/localhost/aislamiento y espera readiness. Rechaza recursos externos, nombres globales e imagen de aplicación sin prefijo de sesión. Reintenta hasta tres veces ante puerto ocupado, informa el alternativo y solo declara HEALTHY tras smoke real. Persiste operación/resultado y libera el bloqueo en errores; conserva datos.
- Limpieza requiere `deleteData=true` en API o `-DeleteData` en PowerShell y confirmación por checkbox en UI. Inspecciona etiquetas de contenedores/volúmenes/redes **antes de cualquier mutación**, elimina solo sus IDs/nombres comprobados y confirma ausencia. Rechaza identidad ajena/incompleta y operación concurrente. Fuentes, historial e imágenes preparadas quedan conservados; el borrado de datos es explícito y separado de parada/reinicio.
- DevOps incorpora «Reiniciar conservando datos» y limpieza confirmada, bloqueadas durante operaciones incompatibles. Limpia smoke/playground al actuar y descarta respuestas de sesiones anteriores; polling reconcilia identidad/puerto efectivos al terminar. Motor mostrado deriva del driver inspeccionado, sin devolver secretos, como en sección 22.
- Paquetes nuevos incluyen `runtime-common.ps1`, `stop-local.ps1`, `restart-local.ps1` y `cleanup-local.ps1`, utilizables sin AgentIA. PowerShell verifica propiedad, puerto/readiness y retorno de cada comando. Reinicio conserva imagen/datos y ofrece puerto alternativo; guía generada explica las operaciones. No cambia execution policy ni requiere instalar Maven/Java en Windows para reiniciar una imagen preparada.

### Validación y evidencia

- **129 PASS backend**, `.run/lifecycle-backend-final.txt`: recuperación, estados negativos, propiedad ajena, confirmación, locks, rutas API, modo fuentes con Docker prohibido, regresión de despliegue/logs/diagnóstico/kits y scripts. Incluye dos tests ejecutados en Windows PowerShell con Docker simulado que comprueban arrays de múltiples contenedores y rechazo de propiedad ajena antes de mutar.
- **39 PASS frontend** en seis archivos, `.run/lifecycle-frontend-final.txt`: acciones reinicio/limpieza, confirmación, fallo honesto, bloqueo/modo laboratorio, playground/sesiones y regresión de verificación/SSE/logs. Servicios simulados, sin recorrido integral de navegador.
- TypeScript `--noEmit` y build Vite **PASS**; `.run/lifecycle-build.txt`, con aviso existente de bundle >500 kB.
- **1 PASS Docker real**, `.run/lifecycle-real-scripts-final.txt`, `backend/tests/test_runtime_lifecycle_real.py`. Spring/H2 con imagen local existente; registro CRUD conservado tras parada, recarga del registro operativo y reinicio API. Puerto anterior ocupado por socket propio: puerto alternativo anunciado, nuevo contenedor con el mismo ID de imagen y health UP. Luego parada/reinicio/readiness y persistencia mediante scripts PowerShell reales; limpieza PowerShell y API idempotente confirmadas.
- Resultado: `.run/real-lifecycle/fdc2e820-bf08-4a5c-8d92-c2a43aed9943/result.json`, PASS/cleanup STOPPED. Imagen fuente `agentia-isolation-6bc4bff2ad-a-probe-service:local`, ID `sha256:13c6eee67967a135fb8f8b3ea1074e57dfa4cdeda4c969a798a4415d16abdcda`, conservada. Sin construcción, pull ni descarga en esta prueba. Revisión posterior por etiquetas UUID exactas confirmó ausencia de contenedores/volúmenes/redes de esta sesión y de los dos intentos fallidos descritos abajo.

Reproducción real opt-in: desde backend con su entorno Python, `AGENTIA_RUN_REAL_DOCKER=1 python -m pytest tests/test_runtime_lifecycle_real.py -q`; requiere Docker Linux operativo y la imagen fixture local (configurable con `AGENTIA_LIFECYCLE_FIXTURE_IMAGE`). Sin opt-in omite ejecución real. No instala herramientas globales ni modifica recursos ajenos.

### Intentos fallidos conservados y límites

El primer harness real (`90ecb510-cbb6-4b2f-b92c-eb345ffac5fc`) dejó de esperar al ver RUNNING, antes de terminar smoke/HEALTHY. La limpieza concurrente fue rechazada correctamente por operación activa. Se corrigió la espera hasta resultado final y se recuperaron/eliminaron después únicamente los recursos de esa sesión; el resultado FAILED original se conserva. Un segundo intento (`720d814a-f04e-455a-b358-54a1f35f9790`) encontró un error del helper PowerShell: envolver el resultado completo de ConvertFrom-Json en otro array producía un conteo incorrecto para varios contenedores. Se corrigió y agregaron regresiones; su cleanup API fue STOPPED. No se convierten estos intentos en PASS.

Dos tests frontend iniciales usaron un selector único para un mensaje que aparece tanto en estado como en feedback; se corrigieron los selectores. Los fixtures antiguos de parada esperaban Compose down y se adaptaron al contrato de parada por IDs comprobados, manteniendo escenarios timeout/error. La suite enfocada final pasó. No se repitió ni se declara verde la suite global histórica.

T30/T31/T37 se marcan implementadas con esta evidencia. La recuperación real vació el registro en memoria y releyó persistencia/Docker; no fue un reinicio completo del proceso backend ni un E2E de navegador, pendientes de aceptación global. La prueba real nueva es H2; la matriz SQL anterior sigue documentada en sección 18. T41 avanza en scripts/UI, pero sigue parcial por resumen completo de verificación/versiones/recursos del paquete. Cancelación del build, snapshot inmutable, kit integral/aceptación offline, CI/CD/Kubernetes y aceptación final permanecen abiertos. **13 tareas marcadas de 54; 41 sin marcar**, varias con avances. Se conserva rama y trabajo local, sin commits/publicación ni cambios de virtualización/firewall/permisos.

## 25. Puertos, identidad HTTP y Auto-Pilot (T26/T29/T32)

Bloque conjunto para asegurar que el resultado operativo corresponda a la sesión y que Auto-Pilot espere su finalización real. SOURCE_ONLY conserva generación/entrega sin llamadas Docker; tampoco hace solicitudes HTTP de smoke/playground ni espera un despliegue.

### Cambios y contratos comprobados

- Se comprobaron HOST_PORT efectivo antes de Compose, puerto alternativo informado y reintentos acotados a tres ante conflicto de bind ocurrido después de seleccionarlo. Agotar intentos deja FAILED y libera el lock; no detiene/borra recursos para apropiarse del puerto. La selección mediante socket no constituye reserva atómica; los conflictos se resuelven mediante esos reintentos.
- Salud/smoke comparan ID de aplicación, ID de BD, puerto e instancia activa inspeccionados **antes y después** del HTTP UP. Reemplazo/parada durante respuesta impide PASS; una consulta de estado degrada salud y retira URL si no puede confirmar la instancia. Fallo de inspección tampoco conserva URL como evidencia vigente. Las consultas HTTP de salud usan 127.0.0.1 y `allow_redirects=False`, evitando que localhost resuelva un listener IPv6 ajeno o una redirección certifique otro destino. La URL presentada puede seguir siendo localhost. Script de reinicio usa IPv4 para comprobar salud.
- Playground valida path antes de resolver destino, usa 127.0.0.1 y el puerto inspeccionado de la sesión, nunca el puerto del caller. Comprueba de nuevo aplicación/BD/puerto y estado después del HTTP. Si cambia, descarta statusCode/cuerpo y comunica que la petición **pudo ejecutarse** antes del cambio, evitando prometer reversión de POST/PUT/DELETE. Permite consultar un servicio DEGRADED activo, como antes; no habilita uno detenido o sin identidad.
- `wait_for_deployment` espera la liberación del lock de operación: RUNNING durante smoke no se considera final. No interroga salud para anticiparse al worker mientras esté ocupado. Solo entrega estado final confirmado después del cierre/persistencia; RUNNING sin operación se reconcilia. Deadline excedido informa que Docker puede seguir activo y no altera el registro real ni afirma cancelación.
- Auto-Pilot espera tanto BUILDING como RUNNING; únicamente HEALTHY permite continuar. FAILED/DOCKER_UNAVAILABLE causa AWAITING_INTERVENTION y sesión PAUSED con causa real y evento BLOCKED; indisponibilidad ofrece Reintentar/Continuar sin Docker. Elección de fuentes omite desplegar/esperar. Interrumpir la espera por cancelación preserva CANCELLED; pausa solicitada durante espera impide anunciar COMPLETED.
- Se actualizó una prueba de ruta playground que fallaba por 401 antes de alcanzar su contrato. Ahora autentica el request de prueba y resuelve su workspace de forma controlada, exigiendo **400 exacto** al rechazo de forwarding; ya no admite un 404 previo como prueba del handler. No se cambió autenticación de producción.

### Evidencia

- **171 PASS backend** en once archivos: `.run/completion-backend-final.txt`. Incluye 16 escenarios de espera/identidad/puertos, 9 de integración del control Auto-Pilot con límites Docker/IA simulados, regresión de proxy/targeting, runtime/lifecycle, modo fuentes y logs/scripts. BD y workspaces temporales de tests, sin proveedores IA.
- Prueba adicional SOURCE_ONLY para smoke/playground prohíbe tanto subprocess Docker como requests HTTP: PASS. Archivo correspondiente repetido después con ese caso nuevo: **17 PASS**, `.run/completion-source-final.txt` (16 ya contados arriba y uno adicional; no se suman 17 al total de la suite).
- **39 PASS frontend**, seis archivos de monitor/explorador/DevOps/modo fuentes/verificación/SSE/logs; `.run/completion-ui-final.txt`. No cambió código frontend en este bloque; se verificaron los consumidores del contrato. No se repitió compilación TypeScript/Vite al no modificar frontend; último build aprobado en sección 24.
- **1 PASS Docker real final**, `.run/completion-real-final.txt` (63,39 s). Imagen Spring/H2 local existente, sin build/pull/descargas. Puerto anterior ocupado por socket propio; reinicio API esperado hasta readiness final. Smoke recibió intencionalmente el puerto antiguo y usó el actual inspeccionado; playground leyó el registro CRUD conservado por el puerto efectivo. Scripts Windows reales conservaron datos tras otro reinicio y limpiaron los recursos propios.
- Resultado final `.run/real-lifecycle/76a875ca-7a28-41e2-870a-03b21aec784f/result.json`: PASS/cleanup STOPPED, imagen fuente conservada con ID registrado en sección 24. Primer recorrido real también PASS en `.run/completion-real.txt`, sesión `97855bb4-fe3d-4f67-aa7a-7a456838b3b1`; se repitió después de fijar IPv4 para comprobar la versión final. Consulta posterior por etiquetas UUID exactas confirmó que ninguna de estas dos sesiones dejó contenedores/volúmenes/redes.

### Correcciones de pruebas y límites

Primer intento `.run/completion-first.txt`: 9 FAIL/111 PASS. Ocho tests nuevos de Auto-Pilot no llegaban al despliegue porque su fixture declaraba BUILD SUCCESS sin resumen de tests y el gate lo rechazaba correctamente. Se agregó resultado explícito de tests, y en fuentes resultado omitido; no se debilitó el gate. El otro fallo correspondía al 401 de la prueba antigua descrita arriba. Un test adicional de pausa falló porque el harness no registraba un hilo activo y `pause_pipeline` rechazaba la solicitud; se representó ese hilo activo y pasó. Intentos y correcciones conservados en `.run/completion-backend.txt`, `.run/completion-backend-final-v2.txt`; no se presentan como PASS históricos.

T26/T29/T32 se marcan implementadas. **16/54 tareas marcadas; 38 sin marcar**, varias parciales. No es aceptación integral ni matriz SQL nueva: la prueba real es Spring/H2 y el control del pipeline usa límites de infraestructura/modelo simulados. Falta navegador conectado al backend, offline externo bloqueado/entorno limpio y cierre del resto del plan. La comprobación antes/después de HTTP detecta cambios observados; no reserva el puerto ni revierte una escritura ya enviada. Fingerprint de imagen/snapshot inmutable sigue pendiente T20/T28. Cancelar la espera de Auto-Pilot no cancela una construcción del daemon: T25/T27 continúan abiertas. Próximos bloques: cancelación/gestión de operaciones y snapshot, kit integral/offline, CI/CD/Kubernetes y aceptación general. Sin commits/publicación ni cambios de permisos, virtualización o firewall.

## 26. Operaciones y cancelación local (T25/T27, avance conjunto)

Se agregaron controles comunes para preparación, despliegue y reinicio, con cancelación identificada por **ID exacto de operación**, etapas persistidas y marcas de inicio/fin. No se cierran T25/T27 porque cancelar el proceso CLI no demuestra cancelación completa de tareas del daemon y falta integrar todas las operaciones de verificación/sandbox.

### Implementación

- `local_operations.py` registra un evento independiente por operación. Persisten `operationKind`, `operationPhase`, `startedAt`, `finishedAt` y `cancelRequested`. Las fases son QUEUED/PREFLIGHT/PREPARE/BUILD/START/READINESS/COMPLETE; INTERRUPTED identifica una interrupción controlada. Se preserva la fase del fallo ordinario para explicar dónde ocurrió. El lock por sesión existente sigue evitando operaciones simultáneas de prepare/deploy/restart; el control se retira al finalizar o fallar el arranque del worker.
- `POST /devops/{session}/cancel` exige `operationId`; valida sesión/workspace y devuelve 409 si la operación cambió. Repetir la solicitud para la misma operación es idempotente; una solicitud antigua no cancela un reintento nuevo. La respuesta indica **solicitud**, sin fingir finalización. SOURCE_ONLY retorna antes de Docker.
- Build/preparación pasan el evento a `run_logged`. Se consulta cancelación antes de crear el proceso y cada hasta 200 ms mientras corre; al cancelar/timeout se termina y recolecta el proceso CLI propio. Windows usa `taskkill /PID <pid creado> /T /F` para su árbol, sin enumerar/matar procesos ajenos ni cambiar políticas. Esto no termina por sí mismo un trabajo ya ejecutándose dentro del daemon.
- Los límites son configurables mediante `LOCAL_BUILD_TIMEOUT=600`, `LOCAL_PREPARE_TIMEOUT=900`, `LOCAL_START_TIMEOUT=200` y `LOCAL_DEPLOY_WAIT_TIMEOUT=1400` segundos. Valores positivos acotados por configuración. La espera global se amplió para admitir los tres intentos de arranque; timeout sigue sin afirmar cancelación del daemon.
- Cada fase y los límites entre comandos verifican cancelación y elección SOURCE_ONLY. Build cancelado no pasa a START. Readiness comprueba el evento entre intentos y permite interrumpir su espera; una petición HTTP en curso conserva su timeout. Los comandos de inspección/configuración/arranque usan `subprocess.run` con límites y verifican cancelación antes/después: no se promete interrupción inmediata de un Compose up que ya está corriendo.
- Ante cancelación/timeout después de intentar arrancar, el dueño del lock enumera/inspecciona contenedores con la etiqueta exacta de sesión y detiene los propios, comprobando ausencia de activos. No borra datos/volúmenes, no usa prune y no afecta otros proyectos. Si la comprobación/parada falla o la sesión ya cambió a fuentes, informa parada no confirmada; no vuelve a invocar Docker en SOURCE_ONLY para completar esa parada.
- Auto-Pilot cancelado señala también el evento del despliegue DEPLOY activo de su sesión, usando su ID exacto, además de interrumpir su espera. CANCELLED del pipeline no certifica detención de BuildKit. Pausar mantiene el comportamiento cooperativo de la sección 25.
- DevOps muestra operación/fase y finalización del worker, y permite «Cancelar operación local» mientras otras acciones incompatibles permanecen bloqueadas, incluido RUNNING intermedio en readiness. Botón queda bloqueado después de solicitar cancelación; mensaje aclara que no confirma detención de BuildKit. Al cambiar sesión se limpian indicadores y se descartan respuestas tardías.
- Si el backend recupera una operación persistida sin worker activo, marca su fase INTERRUPTED y fin local, evitando un bloqueo permanente de la UI. La reconciliación Docker sigue determinando si el servicio realmente está vivo; fin del worker no implica parada del daemon.

### Validación

- **155 PASS backend** en diez archivos, `.run/operations-backend-final-v2.txt`: once casos nuevos de controles (ID/idempotencia/reintento, build cancelado sin START, timeout con parada propia/datos conservados, fuente sin Docker, prepare/restart, contratos API 422/409/404/200, cancelación Auto-Pilot propagada y recuperación sin worker), más regresión de runtime/lifecycle/logs/modo fuentes/diagnóstico/espera/puertos. Un test ejecuta un proceso Python Windows real e interrumpe/recolecta su árbol; comandos Docker en estos tests están simulados.
- **2 PASS adicionales** de los contratos anteriores de cancelación Auto-Pilot, `.run/operations-autopilot-cancel.txt` (44 casos no seleccionados). No se ejecutó la suite global histórica ni se declara verde.
- **40 PASS frontend**, seis archivos, `.run/operations-ui-final.txt`. Incluye envío del ID exacto, ausencia de llamada a parada desde el botón, solicitud sin fingir resultado final y regresión de fuentes/monitor/playground/SSE. TypeScript `--noEmit` PASS (`.run/operations-typescript.txt`) y Vite PASS (`.run/operations-build.txt`), con aviso previo de bundle >500 kB.
- **2 PASS Docker real**, `.run/operations-real.txt`. Nuevas pruebas opt-in usan imágenes locales sin build/pull/descargas. Una interrumpe `docker wait` real: confirma que su contenedor sigue vivo tras cancelar el CLI; luego parada propia comprobada, volumen conservado, otro proyecto de prueba activo intacto e imagen fuente sin modificar. La otra repite Spring/H2 de sección 25 con controles nuevos: reinicio, puerto alternativo, health, playground, persistencia y scripts Windows reales aprobados.
- Evidencia nueva `.run/real-operation-controls/1b36649b-21e4-4bcf-82cd-f4a85c63fc9c/result.json`: PASS/cleanup CONFIRMED; proyecto test independiente `99b975f2-28c3-4079-9810-0ba38d1f9c1b`. Imagen `agentia-runtime:21-v1` conservada. Spring/H2: `.run/real-lifecycle/7d2e0d3f-f281-4170-bd0c-be0a4b11774a/result.json`, PASS/cleanup STOPPED. Revisión posterior por las tres etiquetas UUID exactas: ningún contenedor, volumen o red de esas pruebas quedó presente.

### Incidencias conservadas y pendientes

Dos intentos de la suite quedaron esperando el portal de TestClient. `.run/operations-first.txt` conserva la ejecución incompleta; `.run/operations-diagnostic.txt` conserva el stack de AnyIO. El fixture sustituía `threading.Thread` globalmente y, según el orden de importación, impedía arrancar el portal. Se corrigieron ambos fixtures de Docker para sustituir solo las fábricas de workers de nuestros módulos. Se terminaron únicamente los procesos pytest propios identificados por PID/comando; ninguna ejecución incompleta se cuenta como PASS. Una regresión posterior dio 1 FAIL/106 PASS (`.run/operations-backend.txt`) porque un contrato antiguo esperaba salud None; se actualizó a **UNKNOWN exacto**, sin permitir UP ante smoke fallido. Las suites finales anteriores pasaron.

T25/T27 permanecen **parciales**, sin cambios al conteo **16/54 marcadas, 38 sin marcar**. Falta gestionar/cancelar de forma comprobable tareas BuildKit y contenedores de build temporales, integrar el gestor con verificación/sandbox, registrar identidad inmutable de fuentes/imagen y completar aceptación de concurrencia/recuperación por proceso/navegador. La prueba real nueva usa `docker wait` y contenedores propios, **no** una construcción BuildKit larga cancelada; no se extrapola su resultado. Los controles en memoria corresponden a un proceso backend; no acreditan coordinación entre procesos backend distintos. Siguen kit integral/offline, CI/CD/Kubernetes y aceptación final. No se tocó virtualización, permisos, firewall, execution policy, recursos ajenos, Git remoto ni commits.

## 27. Verificación y cancelación del sandbox (T25/T27)

### Cambios implementados

- La verificación de workspaces gestionados con elección DOCKER comparte el bloqueo por sesión con prepare/deploy/restart. Registra operación VERIFY con UUID, fases y timestamps; rechaza otra operación antes de modificar fuentes o informes. La verificación manual conserva el bloqueo exterior mediante contexto explícito, sin volver a adquirirlo ni liberarlo prematuramente. Auto-Pilot propaga cancelación tanto a DEPLOY como a VERIFY.
- El runner recibe evento e identidad de operación. Cada sandbox usa nombre aleatorio y etiquetas exactas de sesión, rol verification y operación. Consulta cancelación durante la espera y utiliza LOCAL_BUILD_TIMEOUT. Ante cancelación/timeout termina y recolecta el CLI propio, cancela/drena sus lectores y comprueba el contenedor por nombre e inspección de las tres etiquetas antes de retirarlo por ID. Después confirma su ausencia. No elimina volúmenes, imágenes, otros contenedores ni cachés.
- Si Docker no responde o la identidad no coincide, no declara limpieza confirmada. Guarda `cleanup_confirmed=False` y la causa; no muta recursos ajenos. La ausencia previa o retirada automática por `--rm` se confirman con una consulta Docker satisfactoria, no con el mero fin del CLI.
- Resultado nuevo INTERRUPTED y métrica verificationInterrupted distinguen la interrupción de PASSED/FAILED/ENVIRONMENT_UNAVAILABLE. Incluso si llega un resultado exitoso después de cancelar, no se confirma una aprobación. La sesión manual queda PAUSED y conserva causa de limpieza; el grafo no entra en auto-reparación por interrupción. Monitor, explorador y exportación muestran el estado mediante su componente compartido.
- SOURCE_ONLY retorna antes de comprobar daemon, inspeccionar imágenes o crear contenedores. Se mantienen generación y entrega de fuentes sin virtualización; las pruebas omitidas no se declaran ejecutadas.
- La consulta de disponibilidad usa `docker info --format {{.ServerVersion}}`, evitando el informe completo con plugins del cliente. Conserva timeout de dos segundos y resultado indisponible cuando no se puede comprobar acceso; no garantiza disponibilidad permanente.

### Evidencia

- **164 PASS backend, 1 SKIP** en diez archivos, `.run/sandbox-controls-backend-final.txt`: verificación, política de evidencia, SOURCE_ONLY, controles de operaciones, contratos Docker, reinicio, espera y Auto-Pilot. El skip pertenece al caso opcional ya existente. Comandos Docker de esta suite están simulados; incluye proceso Python real para recolección del CLI.
- Después del ajuste final de drenaje asíncrono: **11 PASS**, `.run/sandbox-controls-confirmation.txt`: diez casos de controles repetidos y **una prueba Docker real**. Cubren exclusión, bloqueo manual sin deadlock, cancelación tardía sin PASS, limpieza rechazada ante identidad ajena, timeout/cancelación, limpieza no confirmada y cero comprobaciones Docker en SOURCE_ONLY.
- **30 PASS frontend**, cuatro archivos, `.run/sandbox-controls-ui-final.txt`; TypeScript PASS (`.run/sandbox-controls-typescript.txt`) y Vite PASS (`.run/sandbox-controls-build.txt`). Se mantiene el aviso de bundle >500 kB. No son un recorrido E2E conectado al backend.
- La prueba real usa la imagen local `agentia-runtime:21-v1`, `--pull never`, `--network none` y un proceso shell de espera; **no construye Maven/Gradle ni cancela BuildKit**. Ejercita el gestor y runner reales con cancelación y timeout, dos IDs distintos, retirada del contenedor de cada intento, bloqueo liberado, ausencia de PASS, fuentes e imagen conservadas y otro proyecto de prueba aún activo durante ambas comprobaciones. Después retira también ese proyecto propio.
- Resultado final: `.run/real-verification-controls/88101e44-1cf9-44dd-bff4-da8512f269ea/result.json`, PASS/cleanup CONFIRMED; otro UUID propio `601436c9-b108-463a-ae00-cab7838cb497`. Una ejecución real anterior también pasó: `.run/sandbox-controls-real-diagnostic.txt` y `.run/real-verification-controls/583415e0-c7b3-4558-b3e2-8b40b42627a5/result.json`. Las repeticiones no se suman como escenarios independientes.

### Incidencias y trabajo restante

El primer grupo dio **75 PASS/3 FAIL/1 SKIP**, `.run/sandbox-integration-first.txt`. Los tres fallos ya figuraban en `.run/backend-baseline.txt`: el fixture del grafo no elegía DOCKER y esperaba BLOCKED ante motor ausente. Se explicitó la elección DOCKER y la espera PAUSED que ofrece Reintentar/Continuar sin Docker, conservando las exigencias de no VERIFIED, no PASS y no auto-reparación. La siguiente ejecución dio 91 PASS/1 SKIP/1 ERROR porque pytest recogió como test una función importada llamada tests_really_passed; se corrigió mediante alias. `.run/sandbox-integration-focused-final.txt` confirmó 91 PASS/1 SKIP antes de los casos adicionales.

Dos intentos Docker reales terminaron con motor no disponible, sin aprobación ficticia y con cleanup propio confirmado: `.run/sandbox-controls-real.txt` y `.run/sandbox-controls-real-final.txt`, UUIDs `33675cf5-0c70-48f1-9755-299c955c6b4b` y `21324bab-fa7a-4ff6-b311-8186a696191a`. Sus result.json conservan result RUNNING por haber fallado antes de escribir PASS; no se cuentan como aprobados. Se conserva el informe de cada intento en `.run/real-verification-controls`; el posterior diagnóstico directo desde Python comprobó el acceso y las dos ejecuciones reales siguientes pasaron. Cambiar a salida formateada reduce trabajo del chequeo; no permite atribuir todos esos fallos intermitentes únicamente a plugins.

La primera ejecución Vitest con proceso separado quedó esperando sin resultados; `.run/sandbox-controls-ui.txt` se considera incompleto. Se terminaron solo sus dos procesos propios identificados por PID/relación/comando y se ejecutaron los cuatro archivos con un worker de hilos; esa ejecución final pasó. No se repitió ni se declara verde la suite global histórica.

**T25/T27 continúan parciales, 16/54 tareas marcadas y 38 sin marcar.** La integración de controles con el sandbox ya está implementada y comprobada en los escenarios descritos. Faltan cancelación/limpieza BuildKit demostradas, snapshot inmutable (T20), recuperación de un proceso completo y aceptación de concurrencia entre procesos/navegador. El gestor sigue siendo por proceso backend. Continúan kit integral y aceptación offline, entrega documentada, CI/CD/Kubernetes y aceptación global. Sin commits/publicación ni cambios de permisos, virtualización, firewall o políticas.

## 28. Arranque independiente y entrega (T39/T41)

### Implementación

- start-local.ps1 permite SourcesOnly antes de cualquier descubrimiento/consulta Docker: entrega de fuentes con compilación, pruebas y despliegue NO EJECUTADOS. Este camino no cambia permisos, políticas o virtualización.
- Para ejecutar, valida LOCAL_DELIVERY.json, hashes y conjunto de manifiestos de build, motor Linux, arquitectura de imágenes preparadas, propiedad de aplicación/volúmenes/redes y puertos solo en localhost. Un cambio de dependencias exige regenerar activos/preparar; no dispara descargas o instalaciones automáticas.
- El arranque normal hace Compose build sin pull y sin reutilizar capas del build; el Dockerfile ya usa RUN sin red y Maven/Gradle offline. Fallo de build impide arrancar. Después utiliza restart-local.ps1 para reintentos acotados de puerto, inspección de contenedor propio, readiness HTTP y URL efectiva. Health no sigue redirecciones. No requiere AgentIA abierta ni IA/Java/Maven/Gradle instalados en Windows.
- ReuseImage exige imágenes existentes compatibles, omite construcción y avisa que no ejecutó nuevas pruebas. Readiness no se convierte en PASS de tests. Stop/restart conservan datos; start normal reconstruye; cleanup mantiene confirmación DeleteData e inspección propia.
- LOCAL_DELIVERY.json declara formato, build tool/Java21, referencias de imágenes con versiones previstas y volúmenes appdata/dbdata según motor. Su verificación inicial es NOT_EXECUTED: generar scripts no es evidencia. Los valores son configuración prevista, no inventario de versiones instaladas.
- El ZIP añade DELIVERY_STATUS.json con evidencia actual persistida de la sesión y fingerprint. Distingue PASSED, OUTDATED, INTERRUPTED y SKIPPED_BY_CHOICE; no consulta Docker. Marca SOURCES/includesImages=false y explica el kit separado. Excluye .env e images.tar, reemplaza cualquier DELIVERY_STATUS.json antiguo y rechaza cambios de fingerprint detectados durante empaquetado. No crea un snapshot inmutable: T20 permanece abierta.
- Solo cambian activos regenerados a partir de esta implementación; no se migran proyectos históricos. La reconstrucción no elimina datos para resolver errores SQL.

### Evidencia

- **82 PASS backend**, siete archivos, .run/delivery-scripts-backend-final.txt: entrega, exportación, PowerShell, modo fuentes, reinicio/runtime y controles de verificación. PowerShell real con Docker controlado prueba salida SourcesOnly sin CLI, dependencia cambiada antes de Docker, configuración ajena, fallo de build/readiness y éxito; ZIP omite secretos/kit pesado y conserva resultado actual/obsoleto/interrumpido/omitido. Un caso cambia fuentes durante exportación y comprueba rechazo.
- **1 PASS Docker real**, .run/delivery-scripts-real.txt; .run/real-standalone-delivery/be5c923f-6ca9-4662-83b6-d2f755ee7c5c/result.json PASS/cleanup CONFIRMED. Nuevo proyecto UUID usa copias del fixture Spring/H2 y builder local preparado agentia-builder:f3a47171af85acdfddd092dd; no se descargó ni preparó online.
- start-local.ps1.log conserva build Maven offline real: **8 tests, 0 failures, 0 errors, 0 skipped**, BUILD SUCCESS y URL efectiva localhost:60863. Se ocupó 60862 con socket propio; el script informó el conflicto y cambió a 60863. Health y CRUD reales aprobados.
- Después de stop, start -ReuseImage mantuvo el mismo ID de imagen, informó ausencia de nuevas pruebas y conservó el registro H2. cleanup -DeleteData eliminó solo contenedores/volúmenes/red propios; la imagen UUID de aplicación fue retirada por teardown de la prueba y el builder compartido se mantuvo idéntico. Los scripts funcionan sin servidor AgentIA activo en esta prueba.
- No hay cambios frontend en este bloque; no se repitieron build ni suite global histórica. git diff --check sin errores de whitespace.

### Incidencias y límites

Primera suite: **4 FAIL/34 PASS**, .run/delivery-scripts-first.txt. Get-FileHash no era localizable en Windows PowerShell de este entorno; la comprobación rechazaba incluso el proyecto intacto. Se sustituyó por SHA256 de .NET, liberando stream/algoritmo y sin instalar módulos ni modificar permisos. .run/delivery-scripts-diagnostic.txt conserva el diagnóstico; .run/delivery-scripts-focused-final.txt pasó **38 tests** antes de agregar los cuatro casos de evidencia del ZIP. Las 82 pruebas finales incluyen esos casos.

La prueba real fue Maven/H2, no una nueva matriz Gradle/PostgreSQL/MySQL. El builder/dependencias y bases estaban preparados; no se vació caché global del daemon ni se bloqueó internet del equipo. RUN/build de aplicación se hizo sin red, pero no acredita offline integral en Windows limpio ni importación del kit en otro motor. El arranque no registra automáticamente un nuevo veredicto PASSED ni copia XML desde las capas al ZIP; su log contiene la evidencia real y la metadata de sesión permanece independiente. Cancelación/timeout del build y snapshot/imagen inmutables siguen en T20/T25/T27/T28.

**T39/T41 implementadas; 18/54 tareas marcadas, 36 sin marcar.** T40 continúa parcial: entrega de fuentes informada y kit separado disponibles, paquete ejecutable con imagen de aplicación todavía pendiente. Continúan kit integral/offline, CI/CD/Kubernetes y aceptación completa. Sin commits/publicación, recursos ajenos alterados o cambios de virtualización, permisos, firewall o execution policy.

## 29. Transferencia de kit y descargas implícitas (T16/T17)

### Implementación

- Antes de exportar/importar, los scripts de kit comprueban el catálogo Docker save con .NET en PowerShell, sin extraer archivos y sin Python/Java/Maven en Windows. La lectura está acotada para JSON/config y omite por seek los blobs grandes de capas; no carga en memoria el TAR entero.
- Comprueban checksum de cabecera, tamaños, catálogo manifest.json único, tags exactos sin adicionales/duplicados, digest del contenido de config y concordancia con su nombre. Para OCI, comprueban también index.json, los nombres completos de imágenes, digest de índices/manifiestos y vínculo con config. Admiten ID clásico de config o ID de índice OCI del Docker instalado; no confunden ambos.
- El archivo debe contener todas y solo las referencias declaradas; un tag OCI ajeno, índice falsificado o config no vinculada impide load. Después siguen las comprobaciones previas de tags existentes y las posteriores de ID/OS/arquitectura. El hash no es una firma: la procedencia confiable sigue siendo necesaria.
- Exportación registra engine/arquitectura/versión disponible y capacidades incluidas. Declara explícitamente que este kit contiene dependencias de build y no contiene imagen de aplicación, AgentIA nativo, scanners externos o herramientas Kubernetes. offlineVerified permanece false.
- Todos los comandos de sandbox, incluso los caminos de imagen explícita/caché de host Maven/Gradle, usan pull never y network none. La ejecución con imagen faltante no intenta descargarla. start-local conserva el error y propone importar kit/preparación online explícita o SourcesOnly.
- Los cambios se aplican a activos nuevos/regenerados. Generación/exportación SOURCE_ONLY no exige usar el kit ni consulta el motor. No hay instalación alternativa para saltar permisos del laboratorio.

### Evidencia

- **83 PASS backend**, seis archivos, .run/kit-transfer-backend-final-v2.txt. Incluye 17 casos PowerShell de kit/TAR/OCI (layout clásico y OCI válidos; corrupción, tamaño/hash/fingerprint, manifiestos cambiados/añadidos, caché excluida, tag existente distinto, arquitectura, tags extra/duplicados, config nombrada falsamente, índice falsificado y vínculo OCI erróneo), más controles de imágenes faltantes, los cuatro caminos Maven/Gradle preparado/host-cache sin pull, laboratorio, diagnóstico y sandbox. Los Docker de estos casos están controlados; la lectura TAR/hashes y PowerShell son reales.
- **1 PASS Docker real**, .run/kit-transfer-real-final.txt. Kit guardado en .run/real-kit-transfer/13019ff3-c4d7-47bc-a087-ea984e52ff69/kit, con **418.344.448 bytes (~399 MiB)** de images.tar. Exportó builder agentia-builder:f3a47171af85acdfddd092dd y runtime agentia-runtime:21-v1; importó con scripts reales y confirmó mismos IDs. Luego un SHA256 incorrecto en el manifiesto fue rechazado, con IDs conservados, y se restauró el manifiesto original.
- Resultado .run/real-kit-transfer/13019ff3-c4d7-47bc-a087-ea984e52ff69/result.json PASS, transferAndIdentityConfirmed/corruptManifestRejected/imagesPreserved=true. El kit válido se conserva para revisión; no se crearon contenedores, redes o volúmenes ni se eliminaron imágenes.
- El motor de esta prueba es el existente, con las dos imágenes ya presentes. No es un motor limpio, otro Windows, build de caché fría ni internet externo bloqueado. La prueba real se hizo antes de añadir campos informativos engine/included; esos campos se validaron en la suite final. No se cambiaron frontend ni sus dependencias; no se repitió su build o suite global histórica.

### Incidencias y pendientes

La primera ejecución de catálogo dio **13 FAIL**, .run/kit-transfer-first.txt: las cabeceras TAR terminan el checksum con NUL y espacio; recortar ambos por separado dejaba un terminador sin eliminar. Se corrigió el trim conjunto. La transferencia real inicial falló por lo mismo (.run/kit-transfer-real-first.txt, UUID ad0595c5-f6f4-4e2d-820c-e5cc59cf853f); no alcanzó load. Se conservan logs/result.json FAILED; se retiró únicamente su TAR duplicado de 399 MiB mediante ruta literal comprobada, sin tocar el kit válido ni imágenes.

El segundo grupo dio **12 PASS/1 FAIL**, .run/kit-transfer-catalog-final.txt: la config tenía contenido con hash correcto pero nombre de digest falso. Se añadió concordancia nombre/contenido. La inspección del TAR real mostró que Docker actual usa ID de índice OCI, distinto de config; se implementó la comprobación del vínculo, sin relajar identidad. .run/kit-transfer-catalog-final-v2.txt pasó 13 tests y la transferencia real posterior pasó. Cuatro casos OCI adicionales más regresión dieron 79 PASS (.run/kit-transfer-backend-final.txt); cuatro casos de prohibición de pull y metadata final elevaron la suite a 83 PASS. No se suman las repeticiones como escenarios distintos.

**T16/T17 siguen parciales; 18/54 marcadas y 36 sin marcar.** Falta kit integral de herramientas/scanners/catálogos Kubernetes, fecha de bases de vulnerabilidades y aceptación offline en otro motor limpio. La prevalidación admite TAR Docker save con manifest.json y configs de hasta 4 MiB/JSON de catálogo hasta 8 MiB; formatos no comprobables se rechazan antes de importar. No es importación transaccional frente a otro proceso que cambie tags durante load, ni prueba de autenticidad del emisor. Continúan snapshot/imagen, cancelación BuildKit, paquete ejecutable T40, CI/CD/Kubernetes y aceptación global. Sin commits/publicación, cambios de permisos/virtualización/firewall/políticas o llamadas IA.

## 30. Manifiestos versionados y construcción separada (T23/T24)

### Implementación

- La función pública generate_all_devops_assets prepara todos los cambios en staging corto bajo .run/asset-staging. Conserva el nombre de la carpeta de sesión para generar identidades Compose coherentes. No modifica fuentes mientras los generadores aún pueden fallar; elimina solamente su carpeta temporal exclusiva.
- ASSET_CONFIGURATION.json registra formatVersion=1, templateVersion=2, sesión, servicio normalizado, motor, puerto y build tool. .agentia-runtime/generated-assets.json guarda la identidad, configuración y hashes SHA256 de los activos de Docker, scripts, kit, CI/CD y Kubernetes propios. Estos hashes detectan cambios, no certifican procedencia ni son firma.
- Regeneración idempotente y actualización de configuración de activos intactos; rechaza cambios o eliminación manual de activos registrados, activos existentes no registrados, registro corrupto/ajeno o versión futura. La API devuelve HTTP 409 con causa. No adopta ni sobrescribe activos históricos. SQL/migraciones mantienen sus restricciones anteriores: modificar configuración no convierte automáticamente SQL publicado ni elimina volúmenes/datos.
- Comparte el bloqueo por sesión con las operaciones locales. Antes de publicar verifica que el inventario original no cambió durante la preparación. Reemplaza archivos individualmente de forma atómica y revierte su contenido si falla la publicación/registro. Fuente sin Docker genera estos archivos sin llamadas al CLI y sin exigir virtualización.
- Backend y scripts conservan construcción explícita offline antes del arranque con --no-build y --pull never. Fallo de build impide ejecutar up. Se añadieron comprobaciones de orden y de ausencia de up tras error. Compose permite red app/BD; puertos publicados en localhost. ReuseImage informa ausencia de nuevas pruebas.

### Evidencia

- **103 PASS backend**, siete archivos: test_asset_generation, test_devops_service, test_local_docker_runtime, test_local_execution_mode, test_standalone_delivery, test_offline_kit_scripts y test_export_service. Evidencia .run/assets-version-backend-final.txt. Incluye ediciones del usuario, registro inválido/futuro/ajeno, fallo de escritura de archivos o registro con rollback, edición de fuentes durante staging, exclusión por operación activa, idempotencia/cambio de puerto, API 409, laboratorio sin Docker y contratos build/arranque. Docker de estos escenarios es controlado; PowerShell, archivos y hash son reales.
- **1 PASS Docker real** en .run/assets-version-real.txt. Nuevo proyecto generado mediante la función pública en .run/real-standalone-delivery/2777cbf7-7c08-4a27-9995-4bfb1b796487; configuración versión 2 y registro presentes. El build Maven/Spring/H2 utilizó builder preparado agentia-builder:f3a47171af85acdfddd092dd y ejecutó **8 tests, 0 failures/errors/skipped**, BUILD SUCCESS.
- Readiness/CRUD reales, conflicto de puerto resuelto a localhost:64388, stop y start -ReuseImage sin build/nuevas pruebas, mismo ID de imagen y registro H2 conservado. result.json PASS, cleanup CONFIRMED, builderUnchanged=true. Se retiraron solo contenedores/volúmenes/red/imagen UUID de esta prueba; builder/runtime compartidos conservados.
- Instancia manual comprobada: backend /healthz UP, HTML frontend HTTP 200 y proxy /healthz UP. No se reinició el backend sin reload ante 13 sesiones registradas RUNNING/QUEUED; no se aseguró su actividad efectiva. Ese proceso aún necesita recarga para incorporar este bloque. No hubo cambios frontend ni repetición de suite global histórica.

### Incidencias y límites

Primera suite .run/assets-version-first.txt: **13 FAIL, 34 PASS, 19 ERROR**, por rutas largas Windows cuando staging duplicaba la ruta dentro del workspace. Se movió a la ruta corta del repositorio. Segunda .run/assets-version-focused-final.txt: **20 FAIL, 27 PASS, 19 ERROR**, porque el registro requería crear .agentia-runtime después de ese cambio. Se corrigió creando su carpeta antes de escribir y limpiando temporal UUID ante error. .run/assets-version-focused-v2.txt pasó **66 tests** antes de añadir casos de registro/API y ampliar regresión. Los fallos no se ocultan ni se cuentan repeticiones como escenarios distintos.

Una revisión automática no pudo autorizar la prueba por límite de uso y no ejecutó el comando; el reintento posterior autorizado pasó. Un comando de regresión apuntó a archivos de pruebas inexistentes y no ejecutó tests; se corrigieron los nombres. Una comprobación HTTP sin permisos de socket fue rechazada por el sandbox; la comprobación autorizada posterior confirmó disponibilidad.

Este guard no constituye snapshot inmutable durante todo el build ni transacción entre procesos/crashes: bloqueo solo en el proceso backend, reemplazos atómicos por archivo y rollback ante excepciones normales. Ediciones después de la comprobación final o caída del proceso durante publicación siguen siendo límites. T20/T25/T27/T28 y aceptación de concurrencia permanecen pendientes. La prueba real fue Maven/H2 en el motor existente con dependencias preparadas; no se repitió la matriz completa, ni se vació caché del daemon, ni se bloqueó internet externo, ni se acreditó Windows/motor limpio. El hash de activos no sustituye la evidencia de verificación de sesión.

**T23/T24 implementadas; 20/54 tareas marcadas y 34 sin marcar**, varias parciales. Continúan snapshot/identidad de imagen, cancelación BuildKit, kit integral/offline, paquete ejecutable T40, CI/CD/Kubernetes y aceptación completa. Sin commits/publicación, recursos ajenos alterados, instalaciones o cambios de virtualización, permisos, firewall o políticas.

## 31. Build, JAR ejecutable y Compose (T18/T19/T21)

Continuación del 5 de octubre de 2026, America/Lima. El usuario indicó que no era necesario mantener AgentIA activo.

### Implementación

- Nuevo resolver común build_layout para Maven/Gradle Groovy/Kotlin en raíz o bootstrap. Reactor Maven entra por POM raíz; Gradle con settings raíz y módulo bootstrap entra por la raíz. Si hay dos herramientas o ambos dialectos Gradle en la misma entrada, rechaza la ambigüedad antes de publicar activos; no elimina archivos para resolverla.
- Generación, preparación online y Dockerfile offline acuerdan la herramienta y el directorio. Se corrigió la inyección Gradle del módulo Kotlin y la detección de bootstrap. ASSET_CONFIGURATION.json pasa a templateVersion=3 y agrega buildDirectory; se pueden regenerar activos intactos registrados con versión 2. Esta metadata no demuestra compilación ni cambia la elección SOURCE_ONLY.
- Selector POSIX inspecciona la integridad ZIP, BOOT-INF y Main-Class JarLauncher/PropertiesLauncher de Spring Boot. Excluye JAR plain/original/sources/javadoc, conserva espacios y exige exactamente un ejecutable. Cero o múltiples candidatos, corrupción o manifest no ejecutable provocan fallo antes de copiar /application.jar. Ya no elige el primer archivo encontrado.
- Build y selección RUN usan network=none, Maven/Gradle offline y caché preparada copiada al área de escritura. Runtime usa el JAR completo con java -jar, sin depender de comandos de extracción de capas distintos entre versiones Spring Boot. Conserva usuario 10001:10001; Dockerfile.runtime exige wget y grep antes de preparar la imagen para healthcheck.
- Compose mantiene imagen/volúmenes por proyecto, aplicación publicada solo en 127.0.0.1, BD sin ports y contraseñas por variables, espera de salud de BD y data-init propio sin red. H2 usa volumen appdata sin BD externa. Estos comportamientos ya tenían implementación y evidencia previas; ahora se validó además la configuración efectiva de las seis combinaciones con Compose real.

### Evidencia

- **112 PASS, 10 SKIP**, .run/build-layout-backend-final-v2.txt, siete archivos. Los SKIP corresponden a los selectores Docker opt-in que se ejecutaron después en el grupo real. Cubre las seis entradas de build, reactor Gradle, rechazo de ambigüedad sin publicación, registro/versionado, scripts/kit, las seis combinaciones manuales y AutoPilot SOURCE_ONLY sin llamadas Docker, y contratos runtime. Los seis casos Compose real se añadieron después y se ejecutaron por separado; no se declara una suite global verde.
- **22 PASS**, .run/build-layout-real.txt: 11 casos locales de layout/Compose, **10 casos en contenedores reales** de selección Maven/Gradle (uno válido con espacios, múltiples, ausente, manifest no ejecutable y ZIP corrupto), y **1 E2E real Maven/Spring/H2**. Selección ejecuta el RUN generado con sus continuaciones Docker; no una reimplementación simulada. Contenedores exclusivos --rm, sin red ni pull; usa builder Maven preparado para las utilidades ZIP/POSIX, no acredita compilación Gradle nueva.
- E2E .run/real-standalone-delivery/180677bc-4500-4851-b1c2-4d949c38cf71/result.json PASS, cleanup CONFIRMED. Configuración versión 3; **8 tests Maven, 0 failures/errors/skipped**, BUILD SUCCESS. Inspección real confirma USER 10001:10001 y publicación en 127.0.0.1. Readiness/CRUD, puerto ocupado resuelto a 49194, stop/start -ReuseImage, mismo ID de imagen y registro H2 conservado; builder compartido inalterado. Se retiraron solo recursos e imagen UUID de la prueba.
- **6 PASS Compose real**, .run/build-layout-compose-real.txt, Maven/Gradle × PostgreSQL/MySQL/H2. docker compose -p UUID config --format json resuelve imagen, volumen por sesión, puerto/host y credenciales de fixture por entorno. No arranca servicios, no consulta proveedores IA ni descarga imágenes. Resultados mínimos sin valores de credenciales en .run/real-compose-config/<UUID>/result.json. Para CRUD/aislamiento de los seis perfiles se conserva la evidencia previa de secciones 16–18; no se repitió toda esa matriz.
- git diff --check sin errores de whitespace. No hubo cambios frontend y no se repitieron build Vite ni suite global histórica.

### Incidencias y límites

.run/build-layout-first.txt terminó **3 FAIL/49 PASS** y .run/build-layout-backend-final.txt **3 FAIL/90 PASS/10 SKIP**: la fixture del grafo empezaba con un POM Maven ajeno al generador, incluso para Gradle. El resolver detectó ambos archivos. Se corrigió la prueba para empezar con entrada limpia, como los casos AutoPilot; el código no borra POM del usuario ni relaja el rechazo de ambigüedad. La regresión posterior pasó. Un patch inicial no se aplicó porque su contexto no coincidía; se corrigió antes de ejecutar pruebas.

La aceptación real sigue siendo el motor Windows existente con imágenes y dependencias preparadas. No se probó equipo/motor limpio, internet externo bloqueado ni compilación real de cada layout bootstrap; esos layouts tienen pruebas de generación, coherencia y directorio. La ejecución actual conserva el JAR completo, no optimiza extracción de capas. No se modificó el runtime compartido instalado: la nueva exigencia grep afecta su siguiente preparación, mientras el healthcheck existente funcionó en el E2E.

T18 permanece parcial: falta resolver de manera uniforme preferencias/configuración persistida y defaults en todas las rutas de verificación/sandbox/despliegue. Snapshot, imagen ligada a evidencia, cancelación BuildKit y aceptación de concurrencia siguen pendientes. Los nuevos assets no migran proyectos históricos y el flujo de fuentes continúa sin Docker/virtualización obligatorios.

Tras la autorización del usuario se verificaron ruta/comando de los procesos de la instancia manual. Se detuvieron backend 12892 y Vite 9832; launcher 6564 ya no existía al consultarlo después. Registro stoppedAt/stoppedPids en .run/local-app-processes.json; no se borraron sesiones/estados de BD ni se detuvo Docker Desktop. Las URLs manuales históricas ya no se anuncian como disponibles.

**T19/T21 implementadas; T18 parcial. 22/54 tareas marcadas y 32 sin marcar**, varias parciales. Continúan configuración persistida completa, snapshot/identidad, BuildKit, kit integral/offline, entrega ejecutable T40, CI/CD/Kubernetes y aceptación completa. Sin commits/publicación, recursos ajenos alterados, instalaciones o cambios de virtualización, permisos, firewall o políticas.

## 32. Configuración guardada y sandbox modular (T18/T08/T09)

Continuación del 5 de octubre de 2026, America/Lima. Avance agrupado; no constituye cierre integral de estas tres tareas.

### Implementación

- local_configuration resuelve motor/puerto con prioridad petición explícita, ASSET_CONFIGURATION.json y, solo sin configuración de proyecto, datos de sesión/defaults iniciales. No consulta Docker/red. Rechaza JSON corrupto, identidad ajena, campos requeridos ausentes, motor inválido y puertos fuera de rango o booleanos; no oculta estos errores usando PostgreSQL/8080.
- La función pública de generación conserva configuración si los parámetros se omiten. Preparación toma motor/puerto del proyecto, aunque el motor por defecto de la sesión difiera. Despliegue sin puerto explícito utiliza el puerto guardado y mantiene elección/información de alternativa si está ocupado. Configuración inválida o conflicto devuelve HTTP 409 en generar/preparar/desplegar. Request hostPort y query host_port permiten omisión; peticiones explícitas siguen prevaleciendo.
- SOURCE_ONLY mantiene su salida anterior a resolver/desplegar y no consulta el motor. Generación añade el driver H2 faltante en Maven/Gradle; los archivos de dependencias y su fingerprint reflejan ese cambio, que puede exigir preparar nuevamente la caché. No registra PASS por generar activos ni ejecuta preparación online automáticamente.
- Los cuatro caminos de sandbox (Maven/Gradle, builder preparado/caché host) usan el resolver común de build de sección 31. Mantienen montaje del workspace completo y seleccionan working directory raíz o /workspace/bootstrap según entrada real; conservan network none/pull never y cachés preparados/copias privadas anteriores. Reactor Gradle con settings raíz conserva entrada raíz.
- Verificación de fuentes existentes acepta manifest Maven/Gradle/Groovy/Kotlin en bootstrap. En modo fuentes puede completar entrega con verificación omitida, sin cambiarla a VERIFIED y sin borrar fallos históricos. Las políticas existentes de auditoría/fingerprint/exportación siguen aplicando.

### Evidencia

- Primera regresión .run/config-flow-first.txt: **70 PASS**. Después de los casos nuevos .run/config-flow-final.txt: **108 PASS/16 SKIP**. Final .run/config-flow-backend-final.txt: **139 PASS/17 SKIP**, nueve archivos (configuración, runner, runtime, laboratorio, activos, layouts, controles de operaciones, entrega y kit). Los SKIP son escenarios reales opt-in: 16 del bloque anterior y uno nuevo ejecutado por separado; no se cuentan como fallos ni pruebas aprobadas.
- Casos nuevos verifican conservación de motor/puerto pese a defaults de sesión diferentes, precedencia explícita, deploy sin puerto, prepare sin cambiar puerto/motor, configuración inválida/ajena y directorio de sandbox en seis combinaciones de manifest/preparado. Tres casos de entrega SOURCE_ONLY en bootstrap terminan COMPLETED, permiten fuentes, permanecen no verificados y no llaman Docker; usan auditoría controlada para aislar el contrato de ejecución. La regresión existente mantiene las seis combinaciones manual/AutoPilot y otros controles SAST/entrega.
- **1 PASS Docker real**, .run/config-flow-real.txt. .run/real-bootstrap-sandbox/4a69febd0fa744d18941597872927a69/result.json PASS y sandbox.log conservados. Copia nueva del fixture Maven/Spring/H2 con POM/src dentro de bootstrap. Ejecutó el comando real generado por build_docker_cmd, builder preparado agentia-builder:f3a47171af85acdfddd092dd, pull never/network none, caché copiada a /tmp/m2 y Maven verify offline.
- Log real: **8 tests, 0 failures/errors/skipped, BUILD SUCCESS**. Contenedor UUID --rm, inspección final para retirar únicamente ese contenedor si quedaba presente; sin construir/retaggear/borrar imágenes, sin recursos de BD persistente creados. Esta prueba compila/prueba/empaqueta el módulo, no despliega una aplicación HTTP nueva.
- git diff --check sin errores de whitespace. No hubo cambios frontend, build Vite ni repetición de suite global histórica. Instancia AgentIA continúa detenida; estas pruebas no dependen de ella ni de proveedores IA.

### Límites y pendientes

La prueba real usa cache/dependencias e imagen existentes en el mismo motor; no se preparó online ni se descargó automáticamente. No acredita nuevo build Gradle bootstrap, matriz SQL completa, motor limpio o internet externo bloqueado fuera del contenedor. Los caminos de caché host conservan las limitaciones documentadas previamente; este bloque corrige su selección de herramienta/directorio.

El frontend aún puede enviar sus defaults explícitos; start-local.ps1 conserva parámetro Port con default 8080. Falta completar presentación/propagación uniforme de configuración persistida y aceptación por UI/standalone, además del cierre completo de reparación, vistas/contratos y entrega previsto en T08/T09. Snapshot/imagen asociada a evidencia y cancelación BuildKit siguen fuera de este bloque. No se migraron proyectos históricos.

**T18/T08/T09 parciales; 22/54 tareas marcadas y 32 sin marcar**, varias parciales. Continúan configuración completa, snapshot/imagen, BuildKit, kit integral/offline, paquete ejecutable T40, CI/CD/Kubernetes y aceptación general. Sin commits/publicación, instalaciones, recursos ajenos alterados ni cambios de virtualización, permisos, firewall o políticas.

## 33. Configuración UI y arranque independiente (T18/T39)

Continuación del 5 de octubre de 2026, America/Lima. Cierre de T18 y refinamiento de T39, ya implementada anteriormente.

### Implementación

- GET /api/v1/devops/{session}/configuration resuelve datos persistidos/entrada de build y devuelve únicamente databaseEngine, hostPort, buildTool y buildDirectory. No llama Docker ni devuelve paths absolutos, credenciales o instrucciones de instalación. La autenticación existente protege el endpoint; configuración inválida devuelve 409 y sesión inexistente 404.
- React lee configuración al abrir/cambiar sesión, muestra build/BD y expone Puerto local editable antes del runtime. Generación usa el motor configurado y omite puerto si el usuario no lo editó; despliegue también omite puerto no elegido explícitamente. El cliente deja de sustituir omisiones por PostgreSQL/8080. El backend conserva la precedencia de sección 32.
- Lectura de configuración cancelada al cambiar sesión; una respuesta tardía no pisa puerto editado ni puerto efectivo de contenedor activo. Polling/fetchStatus con IDLE/SOURCE_ONLY no sustituyen puerto guardado por un default del estado. El campo se bloquea ante operación/runtime activo para evitar alterar las URLs del playground mientras se utiliza el servicio.
- Metadata LOCAL_DELIVERY.json agrega hostPort. start-local.ps1 sin -Port toma ese valor, valida tipo/rango y lo pasa a restart-local; un -Port explícito prevalece. SourcesOnly conserva salida anterior a lectura de metadata/runtime y a cualquier llamada Docker. Restart mantiene su resolución de contenedor/Compose anterior. Configuración de assets templateVersion=4; se regeneran solo activos intactos registrados, sin migrar históricos.

### Evidencia

- **104 PASS backend/17 SKIP**, seis archivos, .run/config-ui-backend-final-v2.txt. Fuente sin Docker consulta el endpoint a través de FastAPI completo con sesión de autenticación de prueba: petición anónima 401, login/cookie válido y GET 200 con los cuatro campos esperados, logout; cero llamadas Docker. PowerShell real con CLI controlado valida puerto guardado omitido y parámetro explícito, además de todos los casos anteriores de SourcesOnly, dependencias, build/readiness, conservación de metadata/ZIP, configuración y laboratorio. Los 17 SKIP son escenarios reales opt-in, no fallos ni aprobaciones.
- **24 PASS frontend**, dos archivos, .run/config-ui-frontend-final.txt. Cuatro casos nuevos cubren configuración pese a defaults iniciales, parámetros omitidos en generación SOURCE_ONLY, edición antes de respuesta tardía, descarte de otra sesión y preservación del puerto efectivo. React/servicios controlados; no son un recorrido completo de navegador con backend real.
- TypeScript y build Vite PASS con Node/dependencias locales existentes. Vite mantiene aviso de bundle JS superior a 500 kB; no impide build y no es un error nuevo del bloque. git diff --check sin errores de whitespace.
- **1 PASS Docker real**, .run/config-ui-real.txt. .run/real-standalone-delivery/6ca36bed-2685-4fcf-9b31-828484fbdc44/result.json PASS, savedPortUsedWithoutParameter=true, cleanup CONFIRMED. Se regeneró un proyecto nuevo con el puerto de un socket propio ocupado; start sin -Port usó el valor guardado y eligió localhost:49896. Log contiene **8 tests Maven, 0 failures/errors/skipped, BUILD SUCCESS**, build offline con builder preparado, readiness/CRUD, USER 10001:10001.
- Stop y start -ReuseImage con puerto explícito conservaron ID de imagen y registro H2. Cleanup/teardown retiró solo contenedores, volúmenes, red e imagen UUID propios; builder compartido inalterado. No se inició AgentIA ni se descargaron dependencias/imágenes para este E2E.

### Incidencias y límites

Frontend inicial .run/config-ui-frontend-first.txt: **1 FAIL/19 PASS**, expectativa antigua del test que exigía enviar 8080 explícito. Se actualizó para comprobar omisión del parámetro y se agregaron casos de configuración. Backend inicial .run/config-ui-backend-first.txt pasó 46 tests antes de ampliar casos; .run/config-ui-backend-final.txt terminó **1 FAIL/103 PASS/17 SKIP** porque el test nuevo intentó acceder anónimamente al endpoint protegido. Se corrigió la petición con login/cookie de prueba y se añadió assert de rechazo anónimo. No se deshabilitó autenticación ni se cambiaron credenciales del sistema. Regresión final pasó.

La aceptación real utiliza Maven/H2 e imágenes/dependencias preparadas en el motor existente. No demuestra nueva matriz de seis despliegues, Windows/motor limpio ni internet externo bloqueado. No se repitió suite global histórica ni recorrido integral en navegador; aceptación completa sigue separada. T08/T09 conservan pendientes de cierre integral de reparación, vistas/contratos y entrega; configuración persistida de este bloque ya está implementada. Snapshot/imagen asociada a evidencia, BuildKit y kit integral siguen pendientes.

**T18 implementada; T39 refinada. 23/54 tareas marcadas y 31 sin marcar**, varias parciales. Instancia AgentIA sigue detenida. Sin commits/publicación, instalaciones, recursos ajenos alterados ni cambios de virtualización, permisos, firewall o políticas.


## 34. Contratos y documentación vigentes (T01/T02)

Continuación del 5 de octubre de 2026, America/Lima. Cierre agrupado de T01/T02; no constituye aceptación integral del despliegue.

### Implementación

- spec.md sustituye la especificación antigua con requisitos del laboratorio sin virtualización, SOURCE_ONLY por defecto, modos manual/AutoPilot, preparación online explícita, alcance offline y GitLab remoto aplazado. Elimina requisitos de Streamlit, Docker obligatorio, aprobación sintética, extracción obligatoria de capas y SQL por bind mounts. Identifica limitaciones reales y escenarios pendientes, sin anunciar CI/CD/Kubernetes ejecutados.
- quickstart.md explica AgentIA nativo/kit separado, autenticación local, entrega de fuentes, reintentar/continuar, scripts independientes, puerto guardado/alternativo, SourcesOnly, ReuseImage, conservación/borrado explícito de datos y transferencia de imágenes. Actualiza referencias a SQL versionado y a pruebas reales existentes, manteniendo pendiente la aceptación en motor/equipo limpio y red externa bloqueada.
- plan técnico vigente actualizado. data-model.md, research.md y tasks.md de septiembre llevan aviso histórico explícito: sus Completed/checkboxes no son estado vigente. Las 54 tareas oficiales siguen en el plan de implementación de docs.
- Contrato YAML reemplazado por exportación de 24 rutas FastAPI seleccionadas (sesiones, autenticación, DevOps), schemas transitivos y cookie real. contracts/README.md define elección/capacidad/evidencia/despliegue, HTTP 200 sin aprobación implícita, errores, acciones, operaciones y límites de logs. SSE usa header Last-Event-ID, no una query inventada; cursor inválido devuelve 400.
- Modelos de respuesta explícitos para configuración (motor/puerto/buildTool/buildDirectory), elección por sesión, verificación (status/metrics) y snapshot de logs. Mantienen autenticación y validación; no alteran comandos Docker ni inician AgentIA. Docstring de DockerExecutionResult corregido para no presentar fallback con exit 0 como aprobación permitida.
- backend/scripts/export_devops_contract.py regenera/comprueba el contrato desde código con SQLite temporal y tracing deshabilitado, sin Docker/IA ni sesiones del usuario. Cierra el engine antes de eliminar temporales en Windows. backend/tests/test_devops_contract.py comprueba igualdad, referencias, defaults/enums separados, puerto opcional, cookie y SSE.

### Evidencia e incidencias

- **80 PASS / 1 SKIP**, seis archivos backend, .run/contracts-backend-final.txt: contrato, configuración, elección/fuentes, reconexión de logs, operaciones de despliegue y verificación. El SKIP es escenario real opt-in; no se cuenta como fallo ni aprobación. Pruebas existentes ejercitan respuestas/endpoints con dependencias controladas y configuración a través de app autenticada; no son un recorrido integral en navegador.
- Exportador --check PASS en .run/contracts-export-check.txt; igualdad con rutas/modelos FastAPI actuales. Todas las referencias de schemas exportadas resuelven. git diff --check sin errores de whitespace; Git informa normalización LF/CRLF en archivos del workspace.
- Primera exportación escribió el YAML pero terminó con WinError32 al intentar eliminar SQLite abierto. Se corrigió con engine.dispose() en finally; regeneración y comprobación posteriores terminaron con salida 0. No se oculta el fallo ni se deshabilita la limpieza.
- No se repitieron Docker E2E, TypeScript/Vite ni suite global histórica: este bloque cambia documentación, publicación de contratos y schemas de respuesta backend. Evidencia Docker/frontend anterior sigue en 33 y anteriores, con sus límites. No se afirma suite global sin fallos.

### Límites y siguientes pendientes

Un contrato estructural coherente no acredita cada endpoint en navegador ni funciones pendientes. Continúan snapshot/imagen ligada a evidencia, atomicidad frente a caída/múltiples procesos, cancelación completa de BuildKit, aceptación de concurrencia, kits integrales en equipo/motor limpio, paquete T40, CI/CD/Kubernetes y pruebas de red externa bloqueada. T08/T09 siguen parciales para reparación/vistas/entrega integral. Los generadores CI/Kubernetes existentes no se certifican por esta documentación.

**T01/T02 implementadas. 25/54 tareas marcadas y 29 sin marcar**, varias parciales. AgentIA permanece detenido. Sin commits/publicación, nuevas instalaciones, recursos Docker ajenos alterados ni cambios de virtualización, permisos, firewall o políticas.


## 35. Fixtures reproducibles y regresión (T04/T48)

Continuación del 5 de octubre de 2026, America/Lima. Cierre de T04 y avance agrupado de T48, que continúa parcial.

### Implementación

- backend/scripts/local_microservice_fixture.py genera fuentes nuevas para Maven/Gradle × H2/PostgreSQL/MySQL usando etapas deterministas sin IA, Java del host, Docker ni preparación/descargas. Opciones validadas y destino nuevo/vacío obligatorio: no sobrescribe proyectos. Ambas variantes (básica y semilla BigDecimal/LocalDateTime) y layouts raíz/bootstrap disponibles.
- Item persistente, nombre obligatorio, SQL por motor, pruebas Java como archivos y assets opcionales. FIXTURE_MANIFEST.json registra catálogo v1, parámetros, SHA256 de fuentes/build/SQL, payloads, NOT_EXECUTED y offlineVerified=false. Dos destinos con los mismos parámetros producen hashes iguales; los hashes reflejan cambios del generador. No constituye snapshot inmutable ni PASS de ejecución.
- El generador genérico actual ofrece POST/GET/DELETE, pero carece de PUT. FixtureUpdateController añade actualización exclusivamente al fixture para probar CRUD completo, validación y persistencia. No se modificó el generador del producto ni se afirma actualización en todos los microservicios generados.
- Entrega independiente real, kit real y sandbox bootstrap ya no copian .run/real-isolation/6bc4bff2ad: regeneran su entrada desde el catálogo. El probe scripts/verify_local_database.py comparte la misma fuente, comprueba PUT y devuelve salida 1 si su reporte termina FAILED. La preparación online explícita de ese probe sigue separada; entrega/sandbox/kit opt-in exigen imágenes previamente preparadas.
- backend/tests/fixtures/LOCAL_MICROSERVICES.md documenta comandos, seis pares, variantes, ausencia de secretos, límites y consumidores. Nuevos tests verifican reproducibilidad, estructura/validación, hashes, SQL/motor, layouts y rechazo de sobrescritura con subprocess prohibido. No certifican por sí solos compilación/HTTP de las seis combinaciones.

### Evidencia

- **74 PASS / 1 SKIP**, cinco archivos backend, .run/fixture-catalog-final-v2.txt. Incluye 18 casos nuevos de catálogo y regresión de configuración, entrega PowerShell, kit y migraciones. El SKIP es sandbox real opt-in, ejecutado por separado. Procesos externos prohibidos en la creación de fixtures; PowerShell de las pruebas de entrega usa CLI controlado como antes.
- **1 PASS Docker real**, .run/fixture-catalog-real.txt, 60.70 segundos. .run/real-standalone-delivery/6b934f8c-4f53-4e7b-99aa-175f36fc1916/result.json PASS/cleanup CONFIRMED. Proyecto Maven/H2 generado desde cero, builder preparado agentia-builder:f3a47171af85acdfddd092dd sin cambios; build offline con **8 tests Maven, 0 failures/errors/skipped, BUILD SUCCESS**.
- Puerto guardado ocupado resuelto a localhost:52203, readiness, POST/GET/PUT/DELETE, nombre inválido rechazado al crear/actualizar, registro actualizado conservado tras stop/start ReuseImage e imagen sin cambios. Cleanup retiró solamente contenedores/volúmenes/red e imagen UUID propia; builder compartido conservado.
- Probe --help termina con salida 0 y DB en memoria, sin Docker ni preparación. git diff --check sin errores de whitespace; avisos LF/CRLF existentes.
- **1 PASS sandbox Docker real**, .run/fixture-bootstrap-real.txt, 23.09 segundos. El fixture recién generado en bootstrap y sin assets compiló/prueba/empaqueta con el builder preparado existente, network none/pull never, 8 tests sin fallos y BUILD SUCCESS. El contenedor temporal UUID se elimina con --rm y teardown inspecciona su etiqueta antes de cualquier retirada. No despliega un runtime HTTP ni descarga/prepara imágenes.

### Incidencias y límites

Primera ejecución del test nuevo falló en colección por usar resolve_build_layout en lugar de build_layout real. Se corrigió al contrato tuple existente. Segunda .run/fixture-catalog-second.txt: 12 FAIL/6 PASS por esperar ItemRequest en lugar de CreateItemRequest. Primera regresión ampliada .run/fixture-catalog-final.txt: 12 FAIL/62 PASS/1 SKIP por contar servicios sin tener en cuenta data-init de permisos. Se corrigieron las expectativas, comprobando rol database, sin eliminar data-init ni relajar validación del producto. La regresión final pasó.

No se repitió la matriz Docker completa ni transferencia pesada de kit: este bloque aporta seis fixtures reproducibles y aceptación real nueva Maven/H2. PostgreSQL/MySQL, Gradle y semillas conservan evidencia real anterior y requieren nueva aceptación de la variante de actualización. No acredita motor/equipo limpio ni bloqueo externo de red. No se repitió frontend ni suite global histórica. T48 permanece parcial porque aún hay fallos históricos y pruebas incompatibles por revisar. T20, cancelación BuildKit, CI/CD/Kubernetes y aceptación completa siguen pendientes.

**T04 implementada; T48 parcial. 26/54 tareas marcadas y 28 sin marcar**, varias parciales. AgentIA detenido. Sin commits/publicación, nuevas instalaciones ni cambios de virtualización, permisos, firewall o políticas.


## 36. Diagnóstico bajo demanda y cachés (T12)

Continuación del 5 de octubre de 2026, America/Lima. Bloque agrupado de diagnóstico de infraestructura y caché; cierre de T12. No cierra preparación/catálogos, concurrencia de builds ni aceptación offline integral.

### Implementación

- SOURCE_ONLY conserva return anterior a CLI, paths, daemon o contenedores. Docker administrativamente prohibido conserva explicación y acciones RETRY/CONTINUE_WITHOUT_DOCKER. Diagnóstico sigue siendo petición explícita; leer status/listado no lo activa.
- Contexto, Compose y plugin Buildx continúan consultados con timeout; se añade buildx inspect sin bootstrap. readyForPreparation requiere nodos running, contexto accesible, motor Linux, workspace escribible y mínimo de espacio host. Estado ilegible/detenido, disco bajo o lectura de espacio fallida no se convierten en preparado.
- Imágenes requeridas deben tener identidad SHA256 y arquitectura Linux compatible con el motor (x86_64→amd64, aarch64→arm64). Imagen ajena/incompatible no se lanza para consultar caché. preparedImagesAvailable conserva significado de imágenes, no suite ni dependencias completas.
- Caché host alternativa Maven/Gradle se consulta mediante lectura acotada del directorio: legible/no vacío. No modifica su contenido y no es requisito para el builder preparado. No anuncia completa una carpeta existente.
- Caché preparada se comprueba mediante contenedor UUID: --rm, --pull never, network none, rootfs read-only, sin mounts, cap-drop ALL/no-new-privileges, memoria 64 MiB, CPU 0.5, pids 32. Solo test de directorio legible y presencia de JAR. No copia/calienta cache, compila, inicia app ni descarga. Ante timeout, inspección y rm requieren coincidencia de etiqueta UUID; recurso ajeno no se retira. Limpieza no confirmada produce UNKNOWN.
- LOCAL_DIAGNOSTIC_CACHE_TIMEOUT default 15 s (1–60) y LOCAL_MIN_FREE_BYTES default 512 MiB (>=0), declarados en config/.env.example. Consultas normales 4 s cada una; no se promete timeout global de toda petición. Umbral host no estima disco interno Docker ni tamaño total del build. Errores/contexto/versiones pasan por redacción de credenciales existente.
- docs/DIAGNOSTICO_LOCAL_DOCKER.md y contracts/README.md explican interpretación, contenedor temporal, límites y recuperación. offlineVerified continúa false incluso con todos los checks disponibles.

### Evidencia

- Primera regresión .run/diagnostics-first.txt: **8 PASS**. Ampliada .run/diagnostics-final.txt: **50 PASS**. Final .run/diagnostics-final-v2.txt: **52 PASS**, tres archivos (diagnóstico, elección/fuentes, contratos). Casos cubren política/CLI/daemon/Windows/malformado/permisos, BuildKit detenido/inválido, contexto/Compose, espacio bajo/ilegible, arquitectura incompatible sin run, cache ausente, timeout/cleanup propio, rechazo de retirada ajena, redacción y caché host alternativa.
- **1 PASS diagnóstico Docker real final**, .run/diagnostics-real-final.txt, 3.83 segundos. .run/real-diagnostics/f336d431-fe8d-42af-8c42-7d2a577741af/result.json conserva readyForPreparation=true, preparedImagesAvailable=true y offlineVerified=false. BuildKit operativo v0.32.2 en Docker Desktop Linux 29.7.2; cache host Maven vacía no impidió consultar la cache preparada AVAILABLE.
- Fixture Maven/H2 nuevo, builder agentia-builder:f3a47171af85acdfddd092dd conservó ID sha256:891068b4a22d05df21c280ed9bd595a665e23b7d377f855acf1f7e11fcd5a00b. Set de contenedores con etiqueta de diagnóstico idéntico antes/después. Sin pulls, build, preparación, app/BD nuevas ni modificaciones al builder. Primera prueba real .run/diagnostics-real.txt: **1 PASS**, 3.78 s, anterior a endurecer ID y añadir cache host.
- CLI local buildx inspect --help confirma que esta versión no ofrece --format; se usa lectura de Status de nodos y se rechaza output no verificable. No se usó bootstrap ni se cambió el builder seleccionado. Contrato YAML sigue igual a modelos/rutas en la regresión.

### Límites

Leer JAR/cache no acredita que todos los plugins/dependencias estén preparados ni verifica fingerprint de un snapshot inmutable. El diagnóstico no prueba restricciones de bind mounts de Docker Desktop, almacenamiento interno/espacio total, arranque/CRUD/persistencia ni aceptación con red externa bloqueada. Las pruebas reales fueron sobre motor e imágenes existentes; no equipo limpio ni nueva matriz Gradle/BD. No se repitió frontend/build ni suite global histórica. La cancelación completa de BuildKit y limpieza bajo fallos del daemon siguen en T25/T27, no se deducen de cleanup de este contenedor temporal.

**T12 implementada. 27/54 tareas marcadas y 27 sin marcar**, varias parciales. AgentIA detenido. Sin commits/publicación, nuevas instalaciones, recursos ajenos alterados ni cambios de virtualización, permisos, firewall o políticas.


## 37. Vigencia de entradas y despliegue (T20/T28)

Continuación del 5 de octubre de 2026, America/Lima. Avance agrupado; T20/T28 permanecen abiertas.

### Implementación

- WorkspaceVerification captura fingerprint después de inyectar contrato y antes de ejecutar sandbox, y lo devuelve junto a source_changed. Compara las entradas al finalizar; un cambio neto observado convierte incluso BUILD SUCCESS en resultado no aprobado, stderr OUTDATED y exit code no cero. Reports/target/build no alteran fingerprint de fuentes.
- Verificación manual y pipeline guardan fingerprint de entradas, no el calculado únicamente al terminar. verificationOutdated persiste que se observó un cambio; tests_really_passed lo rechaza y verification_outcome devuelve OUTDATED incluso si luego se restauran los archivos anteriores. Los contadores reales se conservan.
- Grafo recibe cambios de entradas como BLOCKED/FAILED con evidencia OUTDATED, sin entrar a reparación automática de un conjunto de fuentes mutable. Pipeline allPassed requiere también result.is_success; un resumen de suite aprobada con exit code 1 no es aprobación de build.
- Verificar fuentes en DOCKER genera previamente activos/dependencias de despliegue, conservando motor/puerto guardados. Conflictos de propiedad/activos editados devuelven 409. No descarga/prepara imágenes automáticamente. SOURCE_ONLY conserva su camino sin esta regeneración y no invoca Docker.
- Generación de activos respeta borrowed_lock de la verificación manual: usa el lock ya adquirido y no lo libera. Fuera de ese contexto mantiene exclusión existente. Esto corrige la adquisición doble detectada al agregar generación previa.
- Endpoint deploy vuelve a exigir evidencia vigente después de generar Compose ausente: drivers/Actuator/manifests añadidos no pueden usar la aprobación anterior. Worker captura fingerprint al solicitar deploy y lo comprueba antes de preflight/build y antes de start; cambio en cola o durante build termina FAILED sin up, conservando fuentes y datos.
- React VerificationStatus presenta OUTDATED explícitamente tanto en DOCKER como en SOURCE_ONLY; cambiar el modo no muestra una omisión como si borrara la evidencia obsoleta. Docstring de métricas elimina permiso histórico de aprobación sintética mediante fallback.

### Evidencia

- **122 PASS / 1 SKIP**, nueve archivos backend, .run/input-integrity-backend-final.txt. Integridad de entradas, AutoPilot, controles de verificación/operaciones, runtime, laboratorio, pipeline, activos y configuración. Casos nuevos prueban edición durante verificación, restauración posterior sin borrar OUTDATED, reports de salida válidos, cambio en cola/durante build sin up, gate posterior a regeneración, fingerprint manual original y build fallido pese a resumen aprobado. El SKIP es sandbox bootstrap opt-in, no fallo ni aprobación.
- **1 PASS Docker real**, .run/input-integrity-real.txt, 45.97 segundos. .run/real-input-integrity/6f2515fe-1203-4508-8962-10b2d2f6f58b/result.json conserva sourceChanged=true, fingerprints diferentes, fallback_used=false y exit code 1 por evidencia obsoleta. Fixture Maven/H2 nuevo con imágenes/dependencias existentes, sandbox network none/pull never, **9 tests, 0 failures/errors/skipped, BUILD SUCCESS** (incluye contrato de plataforma). Callback añadió una fuente al recibir BUILD SUCCESS, antes de cerrar la verificación: el resultado dejó de ser aprobación. Contenedor temporal propio retirado; sin runtime/BD nuevos ni proveedores IA.
- **11 PASS frontend**, .run/input-integrity-frontend.txt: incluye OUTDATED visible en ambos modos y regresión de monitor/exportación. TypeScript --noEmit PASS y build Vite PASS, .run/input-integrity-frontend-build.txt; mantiene aviso de JS >500 kB. No recorrido integral en navegador/backend.
- Exportador --check PASS: no cambios estructurales del contrato de rutas publicado. git diff --check sin errores de whitespace (avisos LF/CRLF del workspace).

### Incidencias y límites

Primera .run/input-integrity-first.txt: **1 FAIL/76 PASS**; generación previa intentaba adquirir de nuevo el lock externo de verificación manual. Se integró borrowed_lock en generación de activos. Un patch dejó indentación incorrecta en finally; .run/input-integrity-final.txt terminó en error de colección, corregido antes de continuar. .run/input-integrity-final-v2.txt: **93 PASS**; regresión ampliada final 122 PASS/1 SKIP. No se eliminó la exclusión para resolver el fallo.

Los checks detectan cambios netos observados antes/después; no son un snapshot inmutable. Un cambio transitorio restaurado antes de comprobar puede escapar, y sigue una ventana de modificación tras el último check/pre-start. Aún falta ejecutar/empacar desde un snapshot sellado y asociar reports/JAR/imagen con él. La imagen del runtime todavía no se vincula por estos checks a un fingerprint verificado: T20/T28 no se cierran. Scripts independientes mantienen sus controles anteriores; los nuevos guards de worker son de AgentIA.

No se probó nueva matriz Gradle/BD, motor limpio, bloqueo externo de red ni suite global histórica. Aceptación completa, cancelación BuildKit, aislamiento entre procesos, kits integrales y CI/CD/Kubernetes siguen pendientes. No se inició AgentIA.

**T20/T28 parciales; 27/54 tareas marcadas y 27 sin marcar**, varias parciales. Sin commits/publicación, instalaciones, recursos ajenos alterados ni cambios de virtualización, permisos, firewall o políticas.

## 38. Snapshot sellado, JAR e identidad de imagen (T20/T28)

Continuación del 5 de octubre de 2026, America/Lima. T20/T28 implementadas para verificaciones nuevas; aceptación integral permanece separada.

### Implementación

- Verificación DOCKER captura fuentes una vez en sources.zip y copia privada de ejecución, excluyendo credenciales .env, imágenes, outputs anteriores y metadata de runtime. SOURCE_ONLY retorna por su camino anterior sin crear snapshot ni consultar Docker. Activos/drivers/Actuator se generan antes de verificar; imágenes/dependencias deben estar preparadas explícitamente, sin descargas automáticas.
- .agentia-runtime/snapshots/<id>/manifest.json registra identidad de sesión, fingerprint, hashes del archivo y de cada fuente, resultado real, informes XML y JAR ejecutable con SHA256. La copia temporal se elimina al terminar. Los cambios originales observados siguen invalidando vigencia; una edición transitoria del original no altera la copia en ejecución.
- Fingerprint incluye ahora .mvn, directorio gradle, scripts Gradle, lockfiles y wrappers. Integridad de archivo, catálogo, rutas, informes y JAR se comprueba antes de exportar/desplegar; contenido corrupto no conserva evidencia vigente. Se rechazan enlaces y rutas fuera del snapshot.
- Deploy materializa las fuentes selladas y exactamente un JAR Spring Boot aprobado; usa Dockerfile.verified para copiarlo a runtime sin otra compilación ni suite. Credenciales locales se pasan separadamente mediante --env-file, sin incluirlas en el archivo de fuentes.
- Imagen incorpora etiquetas de snapshot, fingerprint y SHA256 del JAR. Se inspecciona ID real después del build y se comprueba que el contenedor usa ese ID y esas etiquetas. Readiness vuelve a comparar toda la identidad; recuperación marca DEGRADED ante discrepancia con evidencia persistida. Roles application/database duplicados son ambiguos, no se elige el primero.
- Nuevos campos API: sourceSnapshotId, workspaceFingerprint, imageId, executableJarSha256. Deploy público exige snapshot: sesiones históricas sin sello deben verificarse nuevamente. Exportación aprobada lee bytes de sources.zip, sin incorporar archivos extra no verificados. El ZIP sigue siendo de fuentes: no incluye imagen ejecutable ni credenciales; T40 permanece pendiente.
- Catálogo reproducible de fixtures sube a versión 2: PUT de aceptación usa ItemService y su implementación; elimina acceso directo a repositorio desde controlador que el SAST real rechazó. Generador productivo conserva su alcance anterior.

### Evidencia

- Regresión final .run/snapshot-backend-final-v2.txt: **158 PASS / 1 SKIP**, doce archivos. Incluye sello/corrupción de fuente, XML, JAR y metadata; aislamiento de edición transitoria; exportación; cambios de configuración de build; rechazo de identidad falsa antes/después de up; readiness y regresiones de laboratorio, operaciones, pipeline, fixtures y contrato. El SKIP es bootstrap Docker opt-in, no aprobación.
- **1 PASS Docker real**, .run/snapshot-real-final.txt, 70.65 s. Proyecto nuevo 28a42f25-c083-4dd8-b20c-cf601d9c01ae: SAST real, verificación de **9 tests** y **5 informes**, JAR verificado empaquetado sin recompilar, readiness localhost:19080, POST/GET de datos, ZIP sellado y recuperación desde disco. SHA256 del JAR dentro del contenedor coincide con el sellado. Snapshot 86c5ef33a0fb4069b5bdd327f7be579e; imagen sha256:50d2e98137350a53fb1be801537ba4f137eb292727bf08c42350393fd442ad38. result.json conserva PASS y cleanup CONFIRMED; contenedores/volúmenes/red e imagen exclusivos de prueba retirados, builder compartido preservado.
- **1 PASS Docker real** adicional, .run/snapshot-input-integrity-real.txt, 42.75 s: cambio del original durante verificación aislada conserva los contadores reales pero invalida aprobación. No arranca runtime ni consume IA.
- Exportador --check PASS (.run/snapshot-contract-check.txt); YAML contiene campos reales. Sin cambios frontend en este bloque: no se repite su build. No se declara suite global aprobada.

### Incidencias y límites

Primera regresión mostró tres fallos porque mocks escribían XML en el original, en lugar de la copia ejecutada; se corrigió el harness. Primera aceptación real (.run/snapshot-real.txt) falló por SAST del fixture PUT con repositorio directo: se corrigió su capa de servicio y se conservó el gate real. Regresión intermedia 133 PASS/1 SKIP y primera suite de snapshot 8 PASS preceden al cierre final 158 PASS/1 SKIP. Check de contrato en sandbox no pudo crear su BD temporal; repetido con permisos de ejecución pasó. No se deshabilitó ninguna regla de calidad.

Sellado SHA256 detecta corrupción y desacopla edición del proyecto original; no impone ACL/read-only ni autentica frente a un usuario con permisos para reescribir contenido y todos los hashes. El contenedor de verificación escribe en su copia privada para compilar; modificación neta de entradas se invalida, sin prometer defensa ante código malicioso que modifique/restaure entradas dentro de esa misma copia. Metadata de auditoría capturada en fuentes representa el momento de captura; el gate de exportación sigue evaluando el workspace vigente.

Aceptación nueva de este bloque es Maven/H2 en motor e imágenes existentes. Gradle/PostgreSQL/MySQL, navegador/API completos, simultaneidad entre procesos, caídas del daemon, kit en equipo limpio/red externa bloqueada y paquete ejecutable siguen pendientes en sus tareas. Helpers internos/standalone históricos conservan su ruta anterior sin presentar un snapshot sellado; API de despliegue nueva exige revalidación. No se migra evidencia vieja ni se promete offline integral: offlineGlobalVerified=false.

**29/54 tareas marcadas; 25 sin marcar**, varias parciales. AgentIA permanece detenido. Sin commits/publicación, instalaciones ni cambios de permisos, virtualización, firewall o políticas.

## 39. Migraciones, integridad SQL y persistencia (T22/T48/T52)

Continuación del 5 de octubre de 2026, America/Lima. Bloque agrupado de inicialización SQL, rechazos de configuración y aceptación de datos tras reconstrucción. Las tres tareas permanecen parciales.

### Implementación

- LOCAL_MIGRATIONS.json dentro del changelog registra formato, motor, hashes SHA256 del SQL normalizado UTF-8/LF y seedPolicy=ONCE_PER_DATABASE. Regeneración valida el registro y rechaza motor/contenido inicial diferentes, sin reescribir migraciones publicadas ni borrar datos. Historial adicional del usuario permanece permitido por el changelog.
- Retirar o vaciar data.sql después de publicar 002-seed se rechaza explícitamente; antes podía conservarse el changeSet sin advertir que las fuentes ya no describían la inicialización. Se conserva el SQL publicado y se exige nueva versión.
- application.properties existente debe tener los valores efectivos del changelog, ddl-auto=validate y sql.init.mode=never. Una propiedad posterior contradictoria ya no pasa por contener la cadena esperada en alguna línea anterior. Esta comprobación cubre la sintaxis key=value generada; no es un parser completo de Java Properties ni de todas las fuentes de configuración Spring.
- El schema.sql derivado se escribe después de validar conflictos de todos los outputs, evitando dejar un esquema nuevo cuando las propiedades rechazan la operación. No se promete transacción ante caída del proceso/sistema de archivos.
- DDL fallback conserva UUID como UUID/BINARY(16), Integer como INTEGER e identidad solo para claves numéricas, en lugar de forzar BIGINT para cualquier PK. Encabezado declara el motor pedido. Semillas de PK UUID usan literal UUID/UNHEX, y PK de texto usa literal entre comillas en lugar de un entero.
- Tests antiguos Models & SQL usan ahora autenticación MVP local real, logout, proveedor mock explícito y SPECIFICATION_DIR temporal. No se relajó el middleware ni se llamó a IA. Guía docs/MIGRACIONES_LOCALES.md y guía generada explican motor, historial, semillas y recuperación.

### Evidencia

- .run/migrations-integrity-final-v2.txt: **113 PASS / 1 SKIP**, nueve archivos backend: migraciones, configuración, generación segura, fixtures, servicio/rutas Models & SQL, snapshots, entrega y vigencia. Incluye semillas retiradas/vaciadas, motor incompatible, propiedades duplicadas contradictorias, conflicto sin schema parcial y UUID en H2/PostgreSQL/MySQL. SKIP corresponde a prueba bootstrap opt-in; no aprobación.
- .run/migrations-integrity-real.txt: **1 PASS Docker real**, 87.48 s. UUID nuevo 8bc8aea4-208a-4e6d-8459-f48d4ed8328b, fixture Maven/H2 con semillas de catálogo v2. Primer registro semilla; identidad siguiente 2; creación, lectura, actualización, validación y borrado. Parada/reutilización y posterior rebuild con tests offline conservaron la fila actualizada y exactamente una semilla. Log de reconstrucción conserva **8 tests, 0 failures/errors/skipped, BUILD SUCCESS**.
- Puerto guardado ocupado resuelto a localhost:51189; readiness real, usuario 10001:10001 y bind 127.0.0.1. Builder compartido conservó ID sha256:891068b4a22d05df21c280ed9bd595a665e23b7d377f855acf1f7e11fcd5a00b. result.json conserva seedOnce=true, dataPreservedAfterRebuild=true, identityAdvanced=true y cleanup=CONFIRMED. Retirados contenedores/volúmenes/red e imagen exclusivos de la prueba.
- Primera regresión de cinco archivos: **71 PASS / 1 SKIP**, .run/migrations-integrity-first.txt. Ampliación .run/migrations-integrity-final.txt: **109 PASS / 4 FAIL / 1 SKIP**, los cuatro fallos fueron rutas históricas sin cookie. Corrección del harness: **4 PASS**, .run/migrations-routes-fix.txt; luego regresión final completa 113 PASS/1 SKIP. git diff --check sin errores; avisos CRLF conservados en .run/migrations-whitespace-warnings.txt.

### Límites y siguientes pendientes

T22 sigue abierta: falta unificar el diseño completo Models & SQL con la selección de motor y ampliar tipos/relaciones/semillas dependientes. La corrección UUID tiene prueba de SQL, no aceptación de entidad UUID ejecutada sobre los tres motores. Nueva prueba real de este bloque es Maven/H2; Gradle/PostgreSQL/MySQL conservan evidencia anterior, pero requieren aceptación actualizada. No se repitió la suite global histórica ni frontend sin cambios. T48/T52 mantienen sus otros pendientes.

Scripts offline usaron imágenes/dependencias presentes y red de aplicación/BD local; offlineGlobalVerified no se certifica sin bloqueo externo y entorno limpio. Sin IA, preparación/pull, nuevos servicios de AgentIA ni cambios de virtualización/permisos/políticas. El flujo SOURCE_ONLY conserva generación/exportación sin Docker. **29/54 marcadas y 25 sin marcar**, varias parciales. Sin commits o publicación.

## 40. Catalogo de entradas y preparacion vigente (T14/T16/T17)

Continuación del 5 de octubre de 2026, America/Lima. Bloque conjunto de identidad de dependencias, preparación explícita y validación del kit/arranque independiente. No cierra las tareas integrales T14/T16/T17.

### Implementación

- dependency_inputs.py centraliza archivos de build: POM/build/settings/gradle.properties de módulos, scripts .gradle/.gradle.kts, .lockfile, wrappers y archivos bajo .mvn/gradle/buildSrc. SHA256 y selección son compartidos por identidad del builder, LOCAL_DELIVERY.json, kit y vigencia del snapshot.
- Se excluyen outputs/caches, .idea/__pycache__, archivos .env privados, .pyc y metadata del sistema. Las entradas enlazadas/fuera del proyecto se rechazan. Los selectores Python y PowerShell coinciden en el conjunto comprobado. Capturar el snapshot con esos archivos privados presentes sigue funcionando y no los copia.
- Una entrada adicional/modificada/retirada cambia el builder requerido. Start/importación comprueban hashes y conjunto antes de construir/cargar; no activan red automáticamente ni asumen que un kit antiguo representa las dependencias actuales. Proyectos básicos conservan el fingerprint/tag anterior; no se modifican proyectos históricos.
- Preparación API captura catálogo y tag al solicitar la operación; comprueba entre comandos y antes de acreditar COMPLETE. Cambios observados terminan FAILED y omiten los siguientes builds/pull. No elimina imágenes generadas ni recursos ajenos.
- prepare-local.ps1 comprueba manifiestos antes de Docker, entre builds/pull y antes de anunciar preparación completa. SHA256 usa .NET sin depender de Get-FileHash. Nuevo -SourcesOnly retorna antes de metadata/Docker; start conserva la misma salida temprana. Regenerar los activos actualiza los manifiestos sin preparar implícitamente.
- docs/CATALOGO_ENTRADAS_BUILD.md explica catálogo, exclusiones, invalidación y límites. SOURCE_ONLY mantiene su flujo; no instala herramientas ni requiere virtualización.

### Evidencia

- **165 PASS / 17 SKIP**, diez archivos backend, .run/dependency-catalog-final-v3.txt (58.37 s). Incluye catálogo, scripts PowerShell, kit, operaciones, snapshot, layout, fixtures, generación segura, configuración y diagnóstico. Omitidos: perfiles Docker/bootstrap opt-in; no son aprobación de ejecución real.
- Comprobación posterior de vigencia alineada: **43 PASS**, .run/dependency-catalog-snapshot-final.txt. Selector y captura de snapshot con metadata/credenciales presentes: **22 PASS**, .run/dependency-catalog-selector-final.txt. Se solapan con la regresión; no sumar como casos independientes.
- **19 PASS kit**, .run/dependency-catalog-kit-final.txt: añadido catálogo Gradle o modificado .mvn/maven.config rechaza importación sin load; integridad y rechazos de archivo anteriores siguen aprobados. También incluidos en la regresión final.
- **1 PASS Docker real**, .run/dependency-catalog-real.txt (59.31 s), proyecto nuevo b4a07b3e-7f1f-494d-90bf-9214337be71e, fixture v2 Maven/H2. Arranque con catálogo nuevo, build offline, puerto ocupado alternativo localhost:59122, readiness/CRUD/validación, imagen reutilizada sin nuevas pruebas y datos conservados. Builder mantuvo ID sha256:891068b4a22d05df21c280ed9bd595a665e23b7d377f855acf1f7e11fcd5a00b. Recursos/imagentag UUID propios retirados, cleanup CONFIRMED; imagen compartida preservada.
- git diff --check sin errores de whitespace; avisos CRLF en .run/dependency-catalog-whitespace-warnings.txt. No cambios de schema API ni frontend en este bloque, no se repite su build.

### Incidencias y límites

Primera .run/dependency-catalog-first.txt: 105 PASS/16 SKIP. Ampliación .run/dependency-catalog-final.txt: 162 PASS/1 FAIL/17 SKIP; el guard de PowerShell dependía de Get-FileHash, no disponible en ese entorno. Diagnóstico preservado en .run/dependency-catalog-guard-diagnostic-v2.txt. Se sustituyó por cálculo SHA256 .NET con streams/algoritmos liberados; no se instaló un módulo ni se relajó el rechazo. .run/dependency-catalog-final-v2.txt: 165 PASS/17 SKIP, anterior a alinear exclusiones finales. La versión final v3 y comprobaciones posteriores pasaron.

El catálogo enumera configuración local; no es un catálogo semántico completo de paquetes/versiones, ni descubre repositorios/builds externos al workspace. Preparación observa cambios netos entre pasos, sin congelar su filesystem ni garantizar detectar modificación transitoria/restauración durante un build. La verificación posterior mantiene snapshot privado/sellado. No se ejecutó preparación/pull online real para esta aceptación.

Faltan compatibilidad completa Gradle, herramientas/scanners/catálogos Kubernetes y aceptación del kit en motor/equipo limpio con red externa bloqueada. Esta prueba real usa imágenes presentes y Maven/H2; no actualiza toda la matriz. T14/T16/T17 siguen abiertas. **29/54 tareas marcadas; 25 sin marcar**, varias parciales. AgentIA detenido. Sin IA, commits/publicación ni cambios de permisos, virtualización, firewall o políticas.

## 41. Aceptacion nativa del flujo de fuentes (T11/T54)

Continuación del 5 de octubre de 2026, America/Lima. Cierre T11/T54 dentro del alcance implementado en Windows; aceptación de otro equipo/políticas y navegador permanece en T50/T51.

### Implementación y alcance

- verify_native_source_flow.py ejecuta el backend actual con Python de la instalación nativa v4, PATH vacío, DB/workspaces/specs/costes privados y claves IA vacías. Selecciona generación determinista mediante proveedor mock explícito, sin peticiones a IA ni resultados de rutas simulados.
- Flujo API real: autenticación MVP local, especificación válida, sesión SOURCE_ONLY, grafo/generación de fuentes y pruebas, finalización, verificación manual omitida, manifiestos, diagnóstico omitido, auditoría real, exportación ZIP y recuperación de elección/estado/evidencia tras reiniciar backend. No afirma VERIFIED ni una suite ejecutada.
- sitecustomize privado instrumenta descubrimiento CLI, comandos Docker, SDK Docker y DNS/conexiones externas. Cada intento se registra y rechaza. Marker activo con PID/parentPid se comprueba en ambos arranques, incluyendo el proceso hijo del launcher venv en Windows. No modifica resultados de endpoints ni seguridad productiva. Ausencia de eventos es condición de PASS.
- stop_process_tree retira únicamente el árbol del Popen creado por el probe; en Windows usa taskkill absoluto con PID propio y /T, evitando dar por detenido un launcher mientras sigue el hijo. Verificación nativa de backend/frontend utiliza ahora esa misma parada. Logs, fuentes exportadas y result.json se conservan.
- Kit/instalación nativa de sección 19 ya demostraban locks Python/npm, runtimes incluidos, instalación sin registros, TypeScript/build y eliminación de Google Fonts remotos. Se conserva esta implementación; no se requiere una nueva descarga para el runtime/flujo actual. Guía nativa incorpora la nueva aceptación reproducible.

### Evidencia

- **61 PASS backend**, seis archivos, .run/native-source-regression-final.txt (19.94 s): guard registra/rechaza Docker discovery/SDK/red, integridad del kit, modo laboratorio, AutoPilot, controles de verificación y contrato.
- **2 PASS nativos reales**, .run/native-source-flow-real-final-v2.txt (14.56 s). Backend actual de la fuente, Python incluido, sin Docker visible en PATH y con CLI/SDK prohibidos. Caso global true: .run/native-source-flow-real/bd04ebd8-f79e-4800-a236-ada23d3be080/result.json, sesión 86561be8-8849-4743-87b8-0863a74dc462, localhost:62123. Caso global false: ad4a6436-4ca1-49b2-9ee9-e86d67fec9b9/result.json, sesión 0dbce057-74ab-42e0-b9f0-b187a63b1955, localhost:62333. Ambos PASS, generatedTests/executionSkipped/staticAuditAndExport/restartRecovered/guardActiveForBothStarts true, forbiddenAttempts=0 y processesStopped=true.
- **PASS arranque nativo**, .run/native-startup-confirmation.txt y .run/native-offline-install-v4/native-smoke-result.json: backend health, frontend HTTP y proxy de salud aprobados; PATH vacío, localhost:51771/51772, procesos propios detenidos. Frontend es el instalado v4; esta prueba no acredita un recorrido actual de todas las vistas.
- Consulta final de procesos no encontró uvicorn activo. No se dejó abierta AgentIA, no se instalaron sustitutos de Docker ni se iniciaron contenedores. git diff --check sin errores de whitespace.

### Incidencias y límites

Primera aceptación .run/native-source-flow-first.txt falló porque el fixture enviaba userStories vacío, contrario al contrato; se corrigió a historia/escenario válido. Segundo recorrido .run/native-source-flow-second.txt pasó antes de endurecer marker/parada. Primera prueba del marker (.run/native-source-flow-real-final.txt) falló en ambos casos al comparar PID de launcher con PID real: se incorporó parentPid y parada del árbol; versión final pasó. Logs/evidencias previos se conservan, no se relajan requisitos.

PATH vacío y guard representan CLI/daemon inaccesibles de forma comprobable para estos procesos. Docker Desktop sigue instalado en el equipo: no se desinstaló ni cambiaron sus permisos, y no se certifica un equipo físico sin instalación. El flujo no intentó usarlo. Generación determinista no valida proveedores IA remotos; su conectividad queda fuera de la aceptación de infraestructura.

externalNetworkGloballyBlocked=false: el guard bloquea salida del backend de prueba, no modifica el firewall global ni demuestra instalación offline del conjunto en un equipo limpio. No se garantiza ejecutar Python/Node si el laboratorio prohíbe sus binarios o escritura en el destino. Estas restricciones adicionales, navegador, matriz completa, herramientas externas y kit integral continúan en T50/T51/T16/P7. No se repitió la suite global histórica ni se declara íntegramente aprobada.

**T11/T54 implementadas. 31/54 tareas marcadas; 23 sin marcar**, varias parciales. Plataforma nativa; Docker opcional por sesión. Sin cambios de permisos/virtualización/firewall/políticas, commits, publicación o llamadas IA.

## 42. Compatibilidad Gradle y caches privadas (T15)

Continuación del 5 de octubre de 2026, America/Lima. Cierre T15 para los perfiles preparados nuevos. No cierra concurrencia completa de builds, gestores entre procesos, kit integral ni aceptación offline global.

### Implementación

- gradle_compatibility.py define perfil 8.10.2 y valida wrappers locales: una distribución legible, bin/all y versión exacta. Declaración ausente del wrapper usa el Gradle instalado del perfil; un archivo presente sin URL válida o con declaraciones duplicadas se rechaza. No se cambia el wrapper ni descarga distribución automáticamente.
- Sandbox valida configuración después del return SOURCE_ONLY y antes de consultar daemon. Versión incompatible devuelve fallo sin PASS sintético incluso si se habilitó el fallback histórico. Preparación API falla antes de sus comandos build/pull. Scripts start/prepare hacen la misma comprobación previa a Docker; SourcesOnly retorna antes de metadata/compatibilidad/CLI.
- Dockerfile y sandbox del perfil Gradle comprueban también versión instalada con comando offline y grep exacto antes de test/bootJar. Usan cache privada por contenedor/etapa. Maven ya apunta a /tmp/m2; Gradle ahora exporta GRADLE_USER_HOME privado también para esa comprobación de versión. El directorio /opt/agentia-cache de la imagen base no es un host cache modificable compartido.
- docs/GRADLE_CACHE_LOCAL.md explica perfiles, recuperación, almacenamiento privado y límites. Generar fuentes/activos permanece permitido para un wrapper incompatible; la obligación corresponde a ejecutar el perfil Docker.

### Evidencia

- **123 PASS / 16 SKIP**, nueve archivos backend, .run/gradle-cache-final-v4.txt (39.07 s). Versiones válida/incompatibles/desconocida, URL ausente/duplicada, PowerShell positivo hasta frontera Docker y negativo sin consultas, SourcesOnly, legado sin PASS falso; catálogo, comandos, operaciones, entrega, layout, fixtures, snapshots y controles. SKIP corresponde a perfiles Docker/bootstrap opt-in.
- **2 PASS Docker real**, .run/gradle-cache-real-final.txt (11.58 s). Dos contenedores concurrentes por herramienta usan copias de cache separadas, marcadores independientes y JAR preparados. Validación de versión Gradle usa el mismo guard de producción. Versiones Maven 3.9.9 y Gradle 8.10.2 confirmadas, network none/pull never y base intacta. Reportes en .run/real-cache-isolation/74cd3cc39c6346fdb211d17d84346e71 y cc053d7f93964d9da2f1992f6f21606d, con PASS y cleanup CONFIRMED.
- IDs compartidos preservados: Maven sha256:891068b4a22d05df21c280ed9bd595a665e23b7d377f855acf1f7e11fcd5a00b; Gradle sha256:2ae0ecf5018c2b203ba430beea526a2313e14d4cf8fa8380854a8c377c8f9384. No mounts de host, compilación de app, pulls, datos/volúmenes nuevos ni IA en estas pruebas de cache. Solo se retiran contenedores cuyo UUID de etiqueta se inspeccionó.
- Regresión anterior .run/gradle-cache-final-v2.txt: 94 PASS/16 SKIP; ampliación v3: 123 PASS/16 SKIP antes de añadir guard de versión instalada. Primer aislamiento real corregido v2: 2 PASS (14.25 s). No sumar casos repetidos. git diff --check sin errores de whitespace; no cambios frontend/schema API.

### Incidencias y límites

El trabajo se interrumpió al agotarse el límite del servicio de revisión automática: las ejecuciones solicitadas no se realizaron, sin determinación de inseguridad. Tras el usuario pedir continuar, la revisión aprobó reintentos normales. Primera colección falló por nombre de helper de sandbox inexistente; corregido a run_docker_sandbox. Primer rechazo unitario aún consultaba daemon; se movió antes de la consulta. Un patch intermedio de esa reubicación dejó indentación incorrecta y se corrigió antes de volver a ejecutar.

Primer test Docker real encontró daemon detenido (.run/gradle-cache-real.txt) y falló también la comprobación de limpieza al no poder consultar el motor; no se habían creado contenedores. Se inició Docker Desktop mediante su comando normal. Se corrigió asimismo una concatenación de string del harness de cache que emitía SyntaxWarning. Versiones finales unitarias y reales pasaron; logs fallidos se conservan.

La base es la imagen Docker de contenido inmutable; escrituras del contenedor/etapa son privadas. Sus tags locales siguen reemplazables por un operador; el guard confirma versión, no firma ni autentica una imagen modificada. Catálogo completo/digests y transferencia siguen en T13/T14/T16. Dos copias de cache concurrentes no prueban dos compilaciones Spring completas simultáneas ni races de preparación/arranque; esos escenarios permanecen T25/T27/T52. Otro Gradle requiere un perfil preparado explícito adicional.

No se certifica nueva matriz Spring/SQL, motor limpio, red externa global bloqueada ni suite global histórica aprobada. SOURCE_ONLY permanece funcional sin Docker. **32/54 tareas marcadas y 22 sin marcar**, varias parciales. AgentIA manual detenido; Docker Desktop quedó disponible, contenedores de prueba retirados. Sin commits/publicación ni cambios de permisos, virtualización, firewall o políticas.


## 43. Bloque conjunto: entrega ejecutable, CI local, Kubernetes y operaciones

Actualización 05/10/2026. Base actual: rama `no-docker`, HEAD `7d3221f5aa92e3c4ffbd0e11bc6f6e70a6887b51`; se conserva el trabajo local y no se cambia de rama ni se publica.

### Cambio de alcance solicitado

El usuario indicó **«lo del offline dejalo de lado por ahora»**. Se aplazan nuevas implementaciones y aceptaciones específicas offline (T14/T16/T17/T51 y partes relacionadas de T13/T40/T53). Se conserva lo ya construido; no se elimina la preparación explícita ni se habilitan descargas silenciosas. Docker sigue siendo opcional: SOURCE_ONLY y laboratorio sin virtualización mantienen prioridad. La prueba aislada que estaba ejecutándose ya finalizó; no se inicia otra matriz offline.

### Implementación y evidencia disponible

- Entrega ejecutable T40: API `/sessions/{id}/export-executable` y botón en React. Exige verificación vigente, auditoría y runtime saludable del mismo snapshot/JAR/imagen; entrega fuentes selladas, imagen, manifiesto SHA256 y script Windows de importación/arranque/parada/limpieza. No incluye datos ni contraseñas; las imágenes compartidas de BD se preparan por separado. SOURCE_ONLY rechaza esta entrega antes de Docker y mantiene ZIP de fuentes. `.run/executable-delivery-real.txt`: **1 PASS real**, 9 tests del microservicio, imagen/JAR idénticos, localhost alternativo, persistencia tras stop/start y proyecto original intacto; limpieza propia confirmada. La integración posterior de etiquetas BuildKit requiere nueva comprobación.
- CI local T42/T43: `local-ci.py` realiza auditoría real de fuentes; con elección Docker compila y verifica JUnit real. Trivy opcional inspecciona dependencias del JAR y registra fecha de su base; sin scanner deja vulnerabilidades como NO EJECUTADO. No acredita análisis de vulnerabilidades del sistema operativo de la imagen. Pipelines GitHub/GitLab manuales generan pasos equivalentes, sin publicar ni ejecutar servicios remotos. `.run/real-local-ci/0fd36a2ed3e5498abc78e27d3d49927c`: Maven, **8 tests PASS**; `.run/local-ci-gradle-scanner-real.txt`: Gradle, **8 tests PASS**, auditoría/dependencias PASS. El scanner ahora usa copia privada del cache; esta última modificación queda por confirmar.
- Kubernetes T44–T47: perfil local canónico H2/PostgreSQL/MySQL, Deployment no root, probes, PVC de app, ConfigMap y, cuando corresponde, StatefulSet/Service/PVC de BD. Secretos se aportan por stdin; no se exportan credenciales. Imágenes locales con pullPolicy Never, sin registry/Ingress requerido. Validador compara el catálogo canónico y referencias: **no es un validador general de todas las APIs Kubernetes**. Runner usa herramientas preparadas, cluster/network UUID propios, kubeconfig privado y port-forward 127.0.0.1; SOURCE_ONLY hace validación estática y retorna antes de Docker/herramientas.
- `.run/kubernetes-real-postgresql-v7.txt` y `.run/kubernetes-real-mysql-v7.txt`: **PASS real** de rollout, salud, CRUD, rechazo de entrada y persistencia al reemplazar pods de app/BD, limpieza propia confirmada. Red bridge normal: **no acreditan aislamiento offline**. Los intentos v2–v6 se conservan: incompatibilidad de kind inicial, encoding del harness, falta de gateway con red internal y archivo multiarch incompleto; corregidos con kind 0.33.0, nodo Kubernetes 1.35.8 y exportación linux/amd64.
- Preparación explícita `prepare_local_tools.py`: kind 0.33.0, kubectl 1.35.8 y Trivy 0.75.0, descargas oficiales/checksums, manifest de archivos/versiones y transferencia validada. `.run/local-tools-preparation-v3.txt` y `.run/local-tools-transfer-v3.txt` PASS. Se conserva como avance de T13/T16; el perfil offline integral queda aplazado.
- Operaciones: bloqueo por sesión entre threads/procesos mediante lock del SO; restauración no marca interrumpido al worker vivo de otro proceso. Cancelación por ID exacto compartida entre workers. UUID temporales evitan colisiones al persistir. `.run/multiprocess-kube-final-v2.txt`: **13 PASS**, incluido cierre del árbol propio del launcher Windows y cancelación entre procesos.
- BuildKit: etiquetas de operación y consulta de historia de la operación exacta para distinguir cancelación confirmada de resultado desconocido; no se detiene ni purga builder compartido. `.run/buildkit-cancellation-real.txt`: **1 PASS real**, cancelación en RUN sleep, registro daemon canceled y ausencia del paso final. `.run/buildkit-source-regression.txt`: **78 PASS**. Integración prepare/deploy usa etiquetas diferenciadas por fase; su retest real está pendiente.
- Models & SQL: petición/UI preservan el motor elegido; SQL, semillas y refinamiento usan ese dialecto. Mejoras PK/FK, orden de semillas y campos Java owning; T22 sigue parcial por relaciones/tipos ampliados y aceptación real.
- Frontend completo: `.run/frontend-completion-final.txt`, **104 PASS / 15 archivos**. Contratos históricos se adaptaron con autenticación local real simulada en frontera HTTP y proveedor mock explícito; no se debilitó autenticación ni se inventó verificación. Build de producción posterior pendiente.
- Backend global: `.run/backend-completion-regression.txt`, **1255 PASS / 147 FAIL / 41 SKIP / 34 ERROR**. No se declara suite global verde. Las 34 incidencias de inventario de locks se corrigieron excluyendo `.operation-locks`: `.run/deploy-legacy-lock-regression.txt`, **34 PASS**. Fixture sandbox de fuentes no vacías: `.run/sandbox-honesty-current-contract.txt`, **32 PASS / 1 SKIP**. Fallos históricos de auth/defaults/fallback siguen requiriendo actualización y regresión final.
- Offline ya finalizado antes del aplazamiento: `.run/clean-offline-engine-maven-h2.txt`, **PASS**, motor desechable vacío (0 imágenes/0 contenedores), network none, kit importado con IDs exactos, build frío Maven/H2, salud/CRUD/persistencia y limpieza propia confirmada. No se tocó contexto/firewall/motor global; no acredita toda la matriz ni equipo Windows limpio. No se continuará esta aceptación por ahora.

### Pendientes activos

Modelos/SQL completos y matriz actual, integración final de operaciones y builds, contratos backend históricos relevantes, build frontend y regresión final, casos de concurrencia/recuperación y documentación final. T08/T09/T25/T27/T48–T50/T52/T53 no se cierran por anticipado. Offline y servicios GitLab remotos quedan aplazados. No se mantienen procesos manuales AgentIA ni se modifican permisos/virtualización/firewall. Sin commits o publicación.

## 44. Correcciones tras única sesión DeepSeek y Docker

05/10/2026. El usuario solicitó una sola prueba completa y después resolver sus errores. Sesión `4c849f7c-4240-4aa2-8dca-83ae9a4a837d`, Maven/PostgreSQL. Generación IA real produjo el proyecto; sandbox ejecutó 28 tests aprobados, pero falló guardar XML de snapshot en ruta de 280 caracteres. Preparación posterior falló por MockitoBean en fuentes originales con Spring Boot 3.2.3: la normalización se aplicaba solo a la copia temporal.

Correcciones: rutas extendidas Windows para informes/JAR/validación/limpieza; normalización canónica antes de preparación/fingerprint/snapshot y sin cambios posteriores en copia sellada; errores de evidencia conservan salida/conteos y bloquean aceptación sin fallback ni reparación automática. Campo evidenceError propagado a métricas y rechazado por política de aprobación.

Regresión conjunta: **195 PASS / 2 SKIP**, 13 archivos, 68.85 s. Recuperación real reutilizó las fuentes y sesión originales, sin nuevas llamadas IA: preparación COMPLETE, **28/28 tests PASS**, snapshot sellado, despliegue HEALTHY PostgreSQL, CRUD y validación, persistencia tras stop/restart, ZIP de fuentes e imagen ejecutable. CRC de ambos ZIP correcto. Un fallo adicional del comprobador por DB_PASSWORD ausente se resolvió aportando credencial aleatoria local temporal; el backend ya admitía env-file externo. El archivo se eliminó al terminar.

Fuentes y evidencia: [CORRECCIONES.md](../reports/docker-flow-20261005-112428-ad8273/CORRECCIONES.md), `recovery-result.json`, logs de recuperación y dos ZIP en esa carpeta. Resultado inicial conservado. Parada final comprobada, sin contenedores activos de la sesión; datos/imagen/volúmenes preservados. Sin nueva generación, navegador, cambios de políticas Windows, commit ni publicación. Esta aceptación no certifica toda la suite global ni la matriz completa de modelos/herramientas/BD.
