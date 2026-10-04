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

**Lectura actual:** consultar primero [SQL y migraciones](#18-sql-migraciones-y-semillas-en-despliegue-real), junto al aislamiento de la sección 17 y las secciones 14–16. Las secciones anteriores conservan diagnóstico, decisiones y etapas previas. El motor funciona en este equipo; kit integral, CI/CD/Kubernetes y aceptación completa siguen abiertos.

### Cómo mantener esta referencia

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
