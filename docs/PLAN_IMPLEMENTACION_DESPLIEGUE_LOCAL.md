# Plan de implementación — despliegue local de microservicios

**Fecha:** 4 de octubre de 2026, America/Lima.  
**Estado:** implementación iniciada por autorización del usuario; aceptación integral pendiente.  
**Referencia obligatoria:** [diagnóstico y decisiones](C:/Users/willi/Downloads/agentIA/docs/ESTADO_DESPLIEGUE_LOCAL_DOCKER.md).  
**Prioridad principal:** completar el flujo en un laboratorio sin virtualización cuando el usuario elige no usar Docker.

**Última revisión:** 04/10/2026. La elección por sesión, el flujo de fuentes, reintentos, diagnóstico y operaciones/scripts Docker están implementados parcialmente. El motor funciona y la matriz básica de seis combinaciones pasó; se comprobaron aislamiento entre sesiones y migraciones/semillas en despliegues reales. Las tareas abiertas pueden tener avances parciales. La evidencia actual y los límites están en las secciones 17–18 del documento de estado; la aceptación integral sigue pendiente.

## 1. Resultado que debe alcanzarse

AgentIA permitirá crear un microservicio y elegir su modo de ejecución:

1. **Sin Docker:** generar requisitos, arquitectura, modelos, código, pruebas como archivos y artefactos DevOps; realizar controles estáticos; terminar el flujo y descargar el proyecto. Compilación, pruebas de ejecución y despliegue figurarán como no ejecutados, sin exigir Docker ni herramientas Java locales.
2. **Con Docker:** preparar el entorno, verificar el código, construir y desplegar el microservicio con su base de datos cuando corresponda, usando puertos disponibles de localhost y resultados verificables.

Si Docker fue elegido y la infraestructura no está disponible, mostrar **Reintentar** y **Continuar sin Docker**. Las omisiones por elección y los fallos reales de compilación/pruebas deben permanecer separados.

El modo se guardará por sesión y se respetará en creación rápida, ingesta, flujo guiado, grafo, Auto-Pilot, pruebas/reparación, DevOps, overview y exportación.

## 2. Alcance acordado

### Incluido

- Windows y Docker Desktop con contenedores Linux para los microservicios Java.
- Java 21 y Spring Boot 3.x; Maven y Gradle; PostgreSQL, MySQL y H2.
- Despliegue manual y automático.
- Preparación inicial con internet; construcción, verificación y operación local posterior sin internet, con IA excluida de ese requisito.
- Despliegue de microservicios desde la aplicación y desde el proyecto exportado mediante un comando/script.
- Seguimiento de estado y logs, errores claros, puertos alternativos y persistencia.
- Corrección y validación local de los artefactos CI/CD y Kubernetes que se entregan. Prueba Kubernetes local en un entorno con Docker cuando se ejecute la validación completa.
- Documentación, pruebas con entornos simulados y evidencias reales diferenciadas.

### Excluido o aplazado

- Contenerizar AgentIA o eliminar sus requisitos actuales de Python/Node. El arranque sencillo sin Java/Maven/Gradle en host se refiere a los microservicios.
- Migrar los proyectos antiguos; tampoco se borrarán sus archivos o datos.
- Compatibilidad obligatoria con Linux/macOS como hosts.
- Integración, publicación y pruebas remotas en GitLab; contratación de servicios y configuración de runners/registries/clusters remotos.
- Generación de IA offline, despliegue público, acceso LAN y clúster productivo.
- Prometer funcionamiento offline para dependencias arbitrarias nunca preparadas.

El aplazamiento de GitLab es una decisión de alcance del usuario; este plan no afirma que exista una obligación de pago para cualquier uso de GitLab.com.

## 3. Reglas de diseño y estados

### 3.1 Separar elección, capacidad y evidencia

Persistir conceptos independientes, con nombres finales definidos en los contratos:

- **Elección por sesión:** `SOURCE_ONLY` o `DOCKER`; valor seguro por defecto `SOURCE_ONLY` cuando no se suministra una elección.
- **Capacidad del entorno:** CLI, daemon, Compose, imágenes, dependencias y herramientas de validación disponibles, con causas específicas de indisponibilidad.
- **Resultado de verificación:** `NOT_RUN`, `SKIPPED_BY_CHOICE`, `ENVIRONMENT_UNAVAILABLE`, `PASSED`, `FAILED` u `OUTDATED`.
- **Resultado de despliegue:** no solicitado, omitido por elección, esperando decisión, preparando/construyendo/iniciando, saludable, degradado/fallido o detenido.

`COMPLETED` significará que finalizó el alcance elegido, no que todo fue verificado. `VERIFIED` requerirá evidencia real y vigente; `HEALTHY` requerirá identidad del contenedor y salud actual.

La configuración global se conservará como límite administrativo de ejecución del host, no como preferencia de todos los proyectos. Si el administrador prohíbe Docker, una sesión que lo pide recibirá explicación y las dos opciones acordadas. Una sesión sin Docker no cambiará el comportamiento de las demás.

### 3.2 Flujo sin Docker

- No llamar a Docker CLI, SDK, Compose, descarga de imágenes ni calentamiento de cachés para avanzar.
- No pausar por ausencia de virtualización, daemon, imagen, dependencias offline o herramientas de validación de contenedores.
- Generar pruebas como código y diferenciarlo de ejecutar pruebas.
- Auditar fuentes y generar manifiestos sin exigir un build previo cuando el usuario elige entrega de fuentes.
- Exportar proyecto y documentación de verificación; no adjuntar JAR/imágenes inexistentes ni informes ficticios.
- Mantener los hallazgos reales de seguridad y la auditoría estática. Si un control depende de una herramienta ausente, reportarlo como no ejecutado; no convertirlo en aprobación ni en bloqueo por Docker.
- Permitir activar Docker posteriormente con una acción explícita y verificar entonces el workspace actual.

### 3.3 Decisión cuando falla la infraestructura

| Evento | Comportamiento |
|---|---|
| Sesión sin Docker | Omitir etapas de ejecución, completar fuentes y mostrar estado honesto. |
| Docker solicitado pero ausente/deshabilitado | Esperar elección: Reintentar o Continuar sin Docker. |
| Imagen/caché no preparada en modo offline | Mostrar qué falta; permitir reintento tras preparación o continuar sin Docker. Sin descarga silenciosa. |
| Compilación o pruebas realmente fallidas | Registrar fallo y aplicar reparación acotada; no cambiar automáticamente a pruebas omitidas. |
| Usuario cambia explícitamente a fuentes tras un fallo real | Conservar el fallo y su evidencia en la entrega; cambiar el alcance no convierte esas pruebas en aprobadas. |
| Pérdida de Docker durante build/deploy | Resolver operación como interrumpida/infraestructura no disponible, conservar logs y ofrecer las opciones aplicables. |
| Puerto ocupado | Seleccionar otro, persistir puerto real e informarlo. |

## 4. Fases y tareas

Las tareas se completarán por dependencia. Los nombres de módulos nuevos son propuestas y se ajustarán a la estructura del repositorio durante la implementación.

### Fase P0 — Contratos y base de aceptación

**Dependencias:** ninguna. **Salida:** decisiones y semántica consistentes antes de cambiar ejecución.

- [ ] T01. Actualizar especificación, contrato DevOps y quickstart vigentes para React, Docker opcional por sesión, alcance offline y GitLab aplazado. Retirar las contradicciones documentales sobre Streamlit, montajes SQL antiguos y fallback sintético.
- [ ] T02. Definir contratos de elección/capacidad/verificación/despliegue, errores y acciones Reintentar/Continuar; separar finalización, verificación y despliegue.
- [x] T03. Alinear la documentación constitucional con la elección explícita de entrega sin Docker y soporte Gradle solicitado, manteniendo la verificación real offline cuando se ejecuta. La instrucción del usuario es la autoridad para esta excepción; no bloquear el trabajo solicitando nuevamente la misma autorización.
- [ ] T04. Preparar fixtures nuevos pequeños y reproducibles para las seis combinaciones de herramienta y BD, con una entidad persistente, validación de entrada y CRUD observable. La IA no será necesaria para pruebas de infraestructura.

**Archivos principales:** `specs/007-docker-cicd-orchestration/{spec.md,plan.md,quickstart.md,contracts/devops-api.yaml}`, `.specify/memory/constitution.md`, modelos de sesión/orquestador/DevOps y documentación de este plan.

### Fase P1 — Elección por sesión y laboratorio sin Docker

**Dependencias:** P0. **Salida:** flujo completo sin Docker, independientemente del interruptor global y de otras sesiones.

- [x] T05. Añadir almacenamiento de preferencia por sesión y cambios aditivos de esquema. No migrar artefactos históricos; conservar la base existente y usar un default seguro para registros sin preferencia.
- [x] T06. Exponer la elección en creación rápida e ingesta, con explicación «generar fuentes»/«verificar y desplegar con Docker»; incluirla en solicitudes, respuestas, contexto y detalle persistido.
- [x] T07. Crear una política central que resuelva preferencia, límites administrativos y evidencia, sin replicar condicionales globales por todo el sistema.
- [ ] T08. Aplicar la política a grafo, sandbox, pipeline, flujo guiado y reparación. Omitir solo las operaciones de ejecución que corresponden al modo elegido; mantener generación de pruebas y controles estáticos.
- [ ] T09. Aplicar la misma política a overview, listado, estado de tests, ZIP/bundle y generación de manifiestos. Completar fuentes sin afirmar VERIFIED ni pruebas aprobadas.
- [x] T10. Implementar cambio explícito a fuentes, reintento y activación posterior de Docker. Invalidar evidencia al cambiar fuentes o configuración relevante; conservar fallos reales anteriores.
- [ ] T11. Probar arranque de AgentIA y flujo completo sin Docker instalado, sin permisos de daemon y con Docker global habilitado pero sesión en fuentes. Comprobar ausencia de llamadas a Docker y ausencia de instalación de herramientas sustitutas.

**Archivos principales:** `backend/app/models/{session.py,orchestrator.py,devops.py}`, `backend/app/api/{routes_session.py,routes_orchestrator.py,routes_tests.py,routes_devops.py,routes_publish.py}`, `services/{pipeline_runner.py,verification_policy.py,workspace_verification.py}`, `orchestrator/{graph.py,state.py,nodes/sandbox_node.py}`, modelos/servicios/estado del frontend, `StudioOverviewView.tsx`, `SpecIngestionView.tsx`, `ExportPublishView.tsx`.

### Fase P2 — Diagnóstico y preparación offline

**Dependencias:** P0–P1. **Salida:** entorno preparado explícitamente y problemas de infraestructura identificables.

- [ ] T12. Implementar diagnóstico bajo demanda: CLI, daemon/contexto Linux, Compose/BuildKit, imágenes, cachés, permisos de paths y espacio. La mera lectura de una sesión sin Docker no debe activar estas operaciones.
- [ ] T13. Añadir preparación online explícita de versiones fijadas: builder Maven/Gradle, runtime Java, BD, herramientas/scanners y, para validación Kubernetes, imagen de nodo y herramientas locales. Verificar integridad y registrar versiones/digests sin secretos.
- [ ] T14. Preparar dependencias y plugins con los proyectos/contratos realmente utilizados. Incluir Actuator, drivers, tests inyectados y dependencias de empaquetado, no solo el POM inicial. Congelar un catálogo soportado y detectar dependencias nuevas propuestas por IA antes de una ejecución offline.
- [ ] T15. Distribuir una base de dependencias preparada e inmutable; dar a cada build un área temporal de escritura para metadatos/locks. Comprobar compatibilidad de versiones Gradle y no compartir directorios modificables entre builds concurrentes.
- [ ] T16. Crear manifiesto de preparación por versión/conjunto de dependencias, verificación de integridad e importación/exportación de kit offline. Incluir imágenes, herramientas y bases locales de scanners cuando correspondan. No afirmar disponibilidad basándose solo en que una carpeta existe.
- [ ] T17. Bloquear descargas implícitas en ejecución offline. Reportar dependencia/imagen faltante con acción útil; no habilitar red automáticamente. Para scanners, indicar fecha de la base preparada y distinguir análisis estático local de vulnerabilidades obtenidas por herramientas externas.
- [ ] T54. Cubrir también dependencias locales de AgentIA en la preparación inicial: instalación reproducible de Python/Node y paquetes sin permisos de administrador cuando el entorno lo permita, frontend con assets locales y telemetría no bloqueante. Sustituir las fuentes Google Fonts remotas de `frontend/index.html` por archivos locales o fuentes de sistema. No contenerizar la plataforma ni hacer de Docker un requisito de esta preparación.

**Archivos principales:** `config.py`, `docker_runner.py`, `workspace_verification.py`, `backend/scripts/warm_maven_cache.py`; módulos propuestos de capacidades y preparación; scripts PowerShell bajo `scripts/` y documentación de preparación.

**Condición offline:** no basta con `--network none` en instrucciones RUN. También deben estar disponibles bases, frontend/build backend, herramientas y metadatos que el motor podría intentar descargar. Se validará con acceso externo realmente bloqueado.

### Fase P3 — Artefactos reproducibles y bases de datos

**Dependencias:** P0 y contratos de P2. **Salida:** activos nuevos consistentes con la sesión y aptos para ejecución offline.

- [ ] T18. Resolver herramienta de build, motor de BD y puerto desde datos persistidos. Eliminar literales PostgreSQL del frontend y defaults que contradicen al proyecto.
- [ ] T19. Generar Dockerfiles que utilicen builders preparados y comandos offline. Garantizar JAR ejecutable único, capas compatibles con la versión Spring Boot fijada, usuario sin privilegios y healthcheck con herramientas realmente presentes.
- [ ] T20. Verificar y empaquetar el mismo snapshot de fuentes; asociar fingerprint, informes y JAR/imagen. Preparar todas las dependencias antes de verificar. No añadir drivers/Actuator después de un PASS sin invalidarlo.
- [ ] T21. Generar Compose con identidad por sesión, puertos de aplicación limitados a `127.0.0.1`, BD no publicada por defecto, volúmenes por sesión y salud/credenciales coherentes. H2 no tendrá contenedor de BD.
- [ ] T22. Unificar inicialización SQL por motor: dialecto correcto, DDL presente en classpath, alineación con entidades y control de datos semilla repetidos. Preservar datos al reconstruir y no usar borrado automático para resolver errores de esquema.
- [ ] T23. Generar manifiestos desde una configuración versionada nueva; actualizar con seguridad los artefactos de proyectos nuevos al cambiar configuración, sin sobrescribir modificaciones del usuario de forma silenciosa. No intervenir los 116 proyectos históricos inventariados.
- [ ] T24. Separar construcción offline de arranque: construir explícitamente, luego iniciar sin build ni pull implícitos. En la ejecución local permitir red entre aplicación/BD sin depender de internet.

**Archivos principales:** `devops_service.py`, `lifecycle_artifacts.py`, generadores de scaffolding/configuración/tests y `model_sql_service.py`; `.dockerignore` y artefactos de cada proyecto nuevo.

### Fase P4 — Ejecución, concurrencia y estado real

**Dependencias:** P1–P3. **Salida:** servicio desplegado corresponde a la sesión y las operaciones terminan de manera comprobable.

- [ ] T25. Introducir gestor de operaciones por sesión con exclusión/idempotencia, identificadores, timestamps, cancelación y límites configurables. Evitar dos builds/deploys simultáneos del mismo proyecto y carreras al pulsar Reintentar.
- [ ] T26. Aplicar puertos solicitados mediante configuración/override real antes de Compose. Elegir otro si está ocupado; manejar carreras entre selección y bind con reintentos acotados, sin interrumpir otros servicios.
- [ ] T27. Separar prepare/build/start/readiness; acotar procesos y comprobar códigos de salida. Terminar procesos y contenedores temporales propios ante timeout/cancelación sin tocar recursos ajenos.
- [ ] T28. Obtener identidad por etiquetas de proyecto y servicio, no por heurísticas de nombres. Inspeccionar ejecución, exit code, health, puertos efectivos, BD e imagen del snapshot.
- [ ] T29. Vincular smoke test y playground a esa identidad y puerto. Revalidarlos antes de usar la URL; evitar que un servicio ajeno en 8080 certifique la sesión.
- [ ] T30. Persistir estado operativo y reconciliarlo con Docker tras reiniciar backend; recuperar también contenedores detenidos/fallidos. Degradar HEALTHY cuando cambie la realidad y distinguir inaccesibilidad del daemon de parada comprobada.
- [ ] T31. Detener comprobando retorno y ausencia efectiva de contenedores activos propios. Conservar volúmenes; implementar reinicio y limpieza explícita separada con identificación estricta de los recursos afectados.
- [ ] T32. Auto-Pilot con despliegue solicitado esperará el resultado final, no solo el lanzamiento del hilo. En fuentes omitirá el despliegue; en infraestructura ausente esperará la decisión acordada.

**Archivos principales:** `docker_service.py`, `routes_devops.py`, `pipeline_runner.py`, contratos/almacenamiento de operaciones; módulo propuesto de gestión de procesos.

### Fase P5 — Interfaz y observabilidad

**Dependencias:** contratos P1 y eventos P4. **Salida:** UI representa el estado actual y permite resolver incidencias.

- [x] T33. Alinear tipos frontend/backend para estado, errores y smoke test; suprimir mensajes de éxito al recibir BUILDING o infraestructura no disponible.
- [ ] T34. Suscribir la vista a eventos/logs, con reconexión, último identificador y consulta de estado como recuperación. Cancelar suscripciones y limpiar datos al cambiar sesión.
- [ ] T35. Recoger logs de build y de aplicación/BD, con origen, timestamp e ID. Evitar duplicados y colas que reparten eventos entre consumidores; permitir varios suscriptores. Guardar historial con límite y redactar secretos.
- [ ] T36. Mostrar etapas omitidas, fallidas, pendientes y aprobadas con sus causas. Ofrecer Reintentar/Continuar sin Docker cuando corresponda y deshabilitar acciones incompatibles mientras haya operación activa.
- [ ] T37. Mostrar puerto efectivo, URL y motor real. Renovar estado después de smoke test/parada/reinicio y mantener el playground consistente con la sesión.

**Archivos principales:** `DevOpsDeploymentView.tsx`, `StudioOverviewView.tsx`, vistas de monitor/tests/exportación, `devopsService.ts`, `sessionService.ts`, contexto Studio y servicios de eventos backend.

### Fase P6 — Entrega y ejecución con un comando

**Dependencias:** P2–P5. **Salida:** proyecto exportado puede ejecutarse sin Java/Maven/Gradle instalados en Windows.

- [x] T38. Incluir script PowerShell de preparación y script de arranque de microservicio; ofrecer wrapper `.cmd` si hace falta para políticas de PowerShell. No cambiar automáticamente políticas de ejecución ni habilitar virtualización/WSL.
- [ ] T39. El script de arranque validará kit/configuración, resolverá puerto y ejecutará build/verificación/despliegue según el alcance elegido; esperará readiness e imprimirá URL o diagnóstico. No requiere que AgentIA esté abierta ni invoca IA.
- [ ] T40. Ofrecer paquete de fuentes siempre que la política lo permita y paquete ejecutable offline cuando exista imagen/evidencia real. Separar el kit pesado compartido de cada ZIP y documentar cómo importarlo.
- [ ] T41. Mantener parada sin borrado, reconstrucción y limpieza explícita en scripts y UI; el paquete indicará estado de verificación, versiones y recursos persistentes.

**Límite:** el modo Docker necesita Docker instalado y virtualización utilizable. En el laboratorio se completa el flujo de fuentes sin ese requisito. Los scripts no intentarán sortear restricciones administrativas.

### Fase P7 — CI/CD y Kubernetes, validación local

**Dependencias:** P2–P3 y P6. **Salida:** artefactos entregados tienen comportamiento comprobado localmente en el nivel declarado.

- [ ] T42. Reutilizar comandos de verificación/empaquetado como pasos CI locales; sustituir pasos de auditoría que solo imprimen mensajes por controles reales. Corregir artefactos que aplican a Maven/Gradle y documentar su entorno, sin ejecutar servicios remotos.
- [ ] T43. Validar YAML y reglas de los pipelines con herramientas locales preparadas; ejecutar pasos equivalentes y registrar que esto no demuestra ejecución en GitLab/GitHub ni compatibilidad de un runner no probado. No introducir dependencia remota en el flujo local.
- [ ] T44. Generar perfil Kubernetes de prueba local completo: app, configuración, probes, imagen identificada, BD/Service/PVC cuando corresponda y H2 sin BD externa. No dar por desplegable un manifiesto que carece de su BD o credenciales requeridas.
- [ ] T45. Validar esquemas Kubernetes con catálogo local preparado; comprobar referencias, puertos, recursos, secretos por entrada y readiness/liveness. No generar credenciales reales en archivos exportados.
- [ ] T46. En Windows con Docker funcional, crear entorno Kubernetes de prueba aislado —propuesta: kind— usando herramientas/imágenes preparadas; cargar imagen local sin registry, aplicar manifests, verificar rollout, salud, CRUD y persistencia para BD externa. Acceso por port-forward en localhost; Ingress no será requisito.
- [ ] T47. Limpiar únicamente el cluster/contexto y recursos de validación creados para la prueba. Sin Docker, validar lo que permiten herramientas locales y marcar la ejecución Kubernetes como no ejecutada, sin impedir entregar el proyecto.

No se desplegará remotamente ni se instalará Kubernetes como requisito del laboratorio. La prioridad de P7 es posterior al flujo local fundamental.

### Fase P8 — Validación integral y cierre

**Dependencias:** P0–P7. **Salida:** evidencias reproducibles y documentación coincidente con lo demostrado.

- [ ] T48. Actualizar pruebas existentes incompatibles con comandos actuales, mocks y contratos; probar comportamiento y errores, no solo presencia de cadenas en Dockerfile.
- [ ] T49. Ejecutar regresión backend/frontend relevante y build del frontend; aislar DB/workspaces/costes de prueba. No llamar a proveedores IA en tests de infraestructura.
- [ ] T50. Ejecutar matriz sin Docker y con Docker descrita abajo; registrar cada caso como PASS, FAIL o NO EJECUTADO con causa.
- [ ] T51. Probar offline con acceso externo bloqueado, imágenes/dependencias preparadas y caché de build de aplicación fría; importar kit en un entorno limpio para evitar éxitos por cachés accidentales.
- [ ] T52. Verificar cambios de fuentes, estado obsoleto, reparación, reinicios, concurrencia, fallos de BD, puerto ocupado y servicio ajeno. Conservar informes, logs, fingerprints e identidades reales.
- [ ] T53. Actualizar README, guía Windows/laboratorio, documentación offline, especificación y este diagnóstico. Cerrar los hallazgos únicamente con evidencia aplicable.

## 5. Matriz mínima de aceptación

### A. Laboratorio y elección de Docker — condición principal

| Caso | Resultado exigido |
|---|---|
| Creación rápida sin Docker | Preferencia persistida; generación y exportación completables. |
| Ingesta y grafo sin Docker | Sin invocaciones Docker; pruebas generadas, ejecución omitida. |
| Flujo guiado y Auto-Pilot sin Docker | Alcance final completado; no PAUSED/BLOCKED por virtualización ausente. |
| Reinicio de AgentIA | Conserva elección y estado honesto de fuentes. |
| Sesiones mixtas | Una en fuentes no deshabilita Docker para otra. |
| Docker elegido pero no disponible | Reintentar y Continuar sin Docker visibles; ambas acciones funcionan. |
| Continuar sin Docker | Fuentes exportables y motivo de omisión documentado. |
| Docker habilitado posteriormente | Verifica snapshot vigente; no reutiliza un PASS ficticio o anterior. |
| Error real de tests | No se etiqueta como omitido ni aprobado. |
| Herramienta de auditoría externa ausente | Se identifica control no ejecutado; no bloquea por ausencia de Docker. |

### B. Matriz de builds y bases de datos

Probar Maven × PostgreSQL/MySQL/H2 y Gradle × PostgreSQL/MySQL/H2: **seis combinaciones**. Por combinación: build offline, suite no vacía realmente aprobada, imagen ejecutable, salud, CRUD, validación de entrada y parada. La plantilla runtime nueva usa H2 de archivos con volumen; los perfiles de pruebas pueden seguir usando H2 en memoria. La persistencia de PostgreSQL/MySQL y del perfil H2 de archivos requiere evidencia después de reconstruir/reiniciar.

Para cada combinación, comprobar manifiestos exportados y ejecución desde script. La ejecución Kubernetes local usará las mismas combinaciones cuando el entorno de validación esté disponible, con evidencia separada de Compose.

### C. Escenarios transversales

- Dos sesiones activas solicitando el mismo puerto; ambas accesibles y asociadas correctamente.
- Servicio ajeno saludable en el puerto por defecto; ninguna sesión recibe su evidencia.
- Docker detenido, imagen ausente, dependencia ausente y permisos de workspace denegados.
- Build/prueba/health fallido, timeout y cancelación; sin operación perpetua ni contenedor temporal huérfano.
- Reinicio backend durante/después de despliegue y contenedor que termina inesperadamente.
- Parada Compose fallida: error visible y estado reconciliado, nunca STOPPED inventado.
- Reconexión de logs y múltiples observadores sin duplicados ni pérdida por reparto de cola.
- Modificación de fuentes/configuración después de PASS: evidencia obsoleta y nueva verificación obligatoria para declarar VERIFIED.
- Fuentes sin Docker con cache/imágenes vacías y acceso a daemon prohibido: completan el flujo.
- Kit offline importado en equipo limpio; no se produce pull, descarga de dependencias ni curl remoto durante ejecución.
- Validación/exportación estática de CI/CD y Kubernetes sin servicios remotos.

## 6. Trazabilidad de hallazgos

| Hallazgos del diagnóstico | Resolución prevista |
|---|---|
| D01–D02, entorno y habilitación | P1 elección por sesión; P2 diagnóstico/preparación; P4 acciones de recuperación. |
| D03, puerto ignorado | P3 configuración; T26 puertos efectivos; pruebas de conflicto. |
| D04, UI sin seguimiento | P5 eventos, logs y recuperación. |
| D05–D06, salud/parada falsas | T28–T31 reconciliación e identidad; pruebas negativas. |
| D07, contratos incompatibles | P0 contratos; T33 alineación y pruebas. |
| D08, puertos BD fijos | T21 BD interna; T26 resolución de puertos. |
| D09, artefactos antiguos | Migración fuera de alcance; T23 coherencia de proyectos nuevos. |
| D10, caché vacía | T13–T17 kit preparado y control de faltantes. |
| D11, PostgreSQL forzado | T18 selección real y matriz de seis combinaciones. |
| D12, evidencia insuficiente | T07–T10 política por modo; T20 snapshot; verificación real antes del despliegue declarado aprobado. |
| D13, logs/estado efímeros | T30 persistencia/reconciliación; T35 historial de logs. |
| D14, concurrencia/timeout | T25–T27 operaciones acotadas. |
| D15, pruebas obsoletas/sin E2E | P8 y matriz con evidencias de ejecución. |
| D16, plataforma sin Docker propio | Fuera del alcance por decisión del usuario. |
| Requisito prioritario de laboratorio y UI offline | P1 completa, T54 preparación de dependencias/assets, matriz A y regresión transversal en P8. |

## 7. Evidencias y criterio de finalización

Guardar en una carpeta nueva de reportes de la implementación:

- Versiones y capacidades del entorno, manifiesto de kit e integridad, sin claves.
- Resultados de backend/frontend, validación de manifiestos y scripts.
- Matriz de seis combinaciones con informes de tests, logs, fingerprints, IDs de contenedor y puertos.
- Evidencia CRUD y persistencia para BD externa; semántica temporal de H2.
- Pruebas del laboratorio sin Docker y captura de los mensajes/acciones de la UI.
- Pruebas offline, de exportación, concurrencia, reinicio y parada.
- Nivel real de comprobación de CI/CD y Kubernetes; distinguir validación de archivos de ejecución.

**El trabajo fundamental no estará completo** si el modo sin Docker depende del interruptor global, bloquea por falta de virtualización o declara verificaciones ficticias. **El despliegue Docker no estará demostrado** mientras no haya build, pruebas y operación real en Windows con motor accesible. Si ese entorno sigue indisponible, se avanzará en las tareas independientes, pero se dejarán explícitamente pendientes las pruebas reales.

La preparación inicial puede usar internet; la validación offline posterior no. Las fuentes generadas que introduzcan dependencias fuera del catálogo preparado requerirán nueva preparación explícita antes de prometer build offline.

## 8. Referencias técnicas verificadas

Estas referencias sustentan mecanismos concretos; las versiones y comandos definitivos se fijarán y probarán durante P2.

- [Docker Compose: pull_policy](https://docs.docker.com/reference/compose-file/services/): `never` exige imagen local y falla si falta; no equivale a preparar imágenes.
- [Docker Build: networking](https://docs.docker.com/reference/cli/docker/buildx/build/): `--network none` controla la red de RUN; la preparación de imágenes y builder se comprobará además.
- [Gradle: dependency caching](https://docs.gradle.org/current/userguide/dependency_caching.html): offline exige artefactos presentes; caches copiadas necesitan compatibilidad. Se usará documentación de la versión Gradle finalmente fijada.
- Constitución, especificación y pruebas existentes del repositorio: adaptar documentación a las decisiones del usuario y conservar evidencia real.

## 9. Seguimiento

Consultar este plan junto al diagnóstico antes de cada fase. Marcar una tarea solo tras implementar y validar su salida; registrar limitaciones y decisiones adicionales. La implementación comenzó por P0/P1 y avanzó parcialmente en P2–P6. Las siguientes prioridades son cerrar los contratos de pruebas anteriores, SQL/semillas, diagnóstico/kit offline y CI/CD/Kubernetes, además de las pruebas reales que requieren un motor accesible. No se han ejecutado tareas remotas.

### Avances de la primera etapa

| Fase | Implementado y comprobado | Pendiente para cerrar la fase |
|---|---|---|
| P0 | Constitución alineada; contratos OpenAPI derivados de la aplicación; guía React/Windows y plan técnico actualizados. | Retirar completamente los requisitos históricos contradictorios del spec; diagnóstico detallado; fixtures CRUD ejecutables reales. |
| P1 | Elección persistida y default seguro, formularios, política central, generación/Auto-Pilot y exportación sin llamadas Docker; decisiones explícitas y conservación de fallos. | Extender pruebas a todas las rutas de reparación, arranque en host sin CLI instalada y validación de todas las vistas. |
| P2 | Preparación online explícita por proyecto, comandos sin pull y cachés privadas; fuentes tipográficas externas retiradas. | Catálogo/digests, scanners, diagnóstico completo, kit portable con integridad e instalación offline reproducible de Python/Node. |
| P3 | Gradle real en generación determinista, motores de BD persistidos, dependencias antes de verificar, Dockerfile offline y Compose localhost. Fingerprint incluye módulos anidados y configuración Docker. | SQL/semillas, snapshot de imagen/JAR, respeto a ediciones de manifiestos del usuario y matriz real. |
| P4 | Bloqueos e ID de operación, timeouts, puerto alternativo, identidad inspeccionada, salud/parada honestas, estado durable y espera de AutoDeploy. | Cancelación, límites globales, limpieza propia ante timeout, reconciliación integral de fallos y tests Docker reales. |
| P5 | Contratos frontend alineados, polling con limpieza al cambiar sesión, decisiones de infraestructura, logs acotados y redactados. | SSE con reconexión/IDs estables y captura continua de logs app/BD. |
| P6 | Scripts PowerShell preparar/iniciar/detener/limpiar y ZIP de fuentes sin secretos/cachés. | Kit ejecutable offline, wrapper si lo exige el entorno, readiness/CRUD real y limpieza/reinicio completos desde UI. |
| P7 | Alcance remoto GitLab aplazado; documentación distingue archivos de ejecución. | Corrección y validación local de CI/CD/Kubernetes; las plantillas actuales no se consideran verificadas. |
| P8 | Pruebas enfocadas, regresión comparada con HEAD, frontend compilado y sintaxis PowerShell revisada. | Fallos antiguos y contratos Docker pendientes; aceptación offline y Docker/Kubernetes real. |

Resultados, límites y comandos de reproducción están en la sección 13 de `ESTADO_DESPLIEGUE_LOCAL_DOCKER.md`. Las casillas marcadas acreditan únicamente la salida de esas tareas; no certifican que todo el despliegue local esté terminado.

### Continuación: diagnóstico y kit de imágenes

- T48 avanzó: los 34 escenarios de `test_qe_deploy_docker.py` se conservaron y adaptaron mediante cambios puntuales; pasan junto a las pruebas nuevas. No se sustituyó ese archivo por el nuevo ni se eliminó ninguno. La suite general todavía presenta 149 fallos, todos coincidentes por nombre con HEAD.
- T12 avanzó: diagnóstico bajo demanda con capacidad administrativa, CLI/contexto, Compose, plugin Buildx, motor Linux, escritura/espacio e identidad de imágenes. La consulta en fuentes no prueba CLI ni escribe archivos temporales. El diagnóstico informa capacidad para preparar e imágenes locales; no afirma PASS offline ni prueba el backend BuildKit con una construcción real.
- T16/T40 avanzaron: scripts de exportación/importación de kit con catálogo por proyecto, manifiesto, SHA256/tamaño, fingerprint de dependencias e IDs/arquitectura. Rechazan build modificado, corrupción, arquitectura incompatible y tags locales distintos antes de cargar. Los scripts se ejecutaron en Windows PowerShell con el límite Docker simulado; importación real, scanners, Kubernetes y Python/Node siguen pendientes.
- T11 avanzó: se probó `/healthz` del backend real con PATH vacío y CLI/subprocesos prohibidos, manteniendo Docker administrativamente permitido. No sustituye una prueba de arranque completo del frontend en un equipo limpio.
- T25 avanzó: un error inicial de persistencia libera el bloqueo y deja FAILED, evitando un BUILDING permanente.
- Verificaciones actuales: **107 PASS y 1 XFAIL** en backend enfocado; **11 PASS** UI enfocada; build frontend correcto; **12 scripts**, sin errores de sintaxis. Última regresión general: **986 PASS, 149 FAIL, 3 SKIP, 1 XFAIL**, anterior a las últimas incorporaciones del kit/guard de persistencia, comprobadas después con la suite enfocada.

Las siguientes prioridades siguen siendo SQL/semillas coherentes, cierre del kit offline integral, observabilidad/cancelación y CI/CD/Kubernetes. Los cambios anteriores no cierran la aceptación con Docker real ni autorizan cambiar restricciones del laboratorio.

### Continuación: IDs durables y recuperación de logs

- T34/T35 avanzaron en backend: IDs monotónicos persistidos independientes del límite de retención, escritura atómica y cursores por suscriptor. SSE acepta `Last-Event-ID` y comunica un `log-reset` explícito cuando el cursor quedó fuera del historial. Las rutas de logs validan sesión/workspace; el contrato OpenAPI registra header y tipo de respuesta.
- Se conservan el REST `logs: string[]` y mensajes del archivo anterior. Corrupción o fallo de escritura no reinician el contador silenciosamente ni reemplazan el archivo confirmado. Se amplió la redacción de valores entre comillas/JSON, Bearer y credenciales en URLs.
- **117 PASS, 1 XFAIL** en regresión backend enfocada, incluidos los 107 casos anteriores y 10 nuevos para rotación, reinicio, reconexión, concurrencia, fallo atómico, corrupción, redacción y API. Evidencia `.run/docker-focused-stage3.txt`; los tests de logs prohíben Docker/subprocesos. Suite global no repetida, no se declara verde.
- Ambas tareas permanecen sin marcar: faltan suscripción React/reconexión visual y captura continua con origen/timestamp de build/aplicación/BD. No se certifica escritura concurrente entre procesos backend distintos.
- Estado detallado y límites en la sección 15 de `ESTADO_DESPLIEGUE_LOCAL_DOCKER.md`. Base `no-docker` / `863553a` conservada; no hubo ejecución Docker real, tareas remotas ni cambios de virtualización/permisos.

### Continuación: motor operativo y primeras pruebas reales

El usuario inició Docker Desktop en este equipo; motor Linux 29.7.2 confirmado. T50/T52 avanzan mediante proyectos nuevos aislados generados por el sistema: Maven/H2 y Gradle/H2 completaron preparación online, construcción sin red ni cache de capas, tests Java, arranque localhost, health, CRUD/validación y conservación de datos después de parar/reiniciar. Se detuvieron únicamente sus proyectos de prueba conservando volúmenes y recursos anteriores.

Se completó la matriz básica **6/6 PASS**: PostgreSQL/MySQL/H2 × Maven/Gradle, secuencialmente, con CRUD/validación/persistencia reales. Cada resultado se registra en `.run/real-docker/*/probe-result.json` y el conjunto en `matrix.json`. El Dockerfile incorpora ahora `RUN --network=none` explícito para mantener la restricción al construirlo directamente, además de la configuración de red de Compose. Regresión relacionada: 50 PASS/1 XFAIL SQL. Kit Maven/H2: exportación/importación real y verificación de integridad/IDs aprobadas en el mismo motor, con imágenes ya presentes; no es instalación limpia ni aceptación offline integral.

Las tareas no se cierran todavía: faltan flujo API/UI real, proyectos/módulos adicionales, esquema y semillas, offline global con kit importado en entorno limpio y aceptación de los escenarios negativos. T20/T28 deben revisar también la imagen de aplicación etiquetada por nombre de servicio, que no aísla sesiones simultáneas del mismo nombre; las seis pruebas secuenciales no certifican concurrencia. Evidencia y estado más reciente en la sección 16 del documento de estado.

### Continuación: aislamiento real entre sesiones

T28/T52 avanzaron: imagen de aplicación prefijada por el proyecto Compose efectivo, además del nombre de servicio. Prueba real opt-in incorporada al repositorio, con dos proyectos Maven/H2 del mismo nombre activos a la vez; imágenes/IDs diferentes, puerto alternativo anunciado, reconstrucción y parada de B sin afectar A, reinicio del JAR nuevo conservando datos independientes. Ambos proyectos terminaron detenidos y sus volúmenes se conservaron.

Resultado real **1 PASS**; regresión enfocada **117 PASS, 1 SKIP Docker opt-in, 1 XFAIL SQL**. Evidencias y reproducción en la sección 17 del documento de estado. Se conserva el fallo inicial del harness de prueba y su corrección; no se eliminó evidencia ni se reetiquetó como PASS.

El riesgo de imagen compartida por nombre entre sesiones nuevas queda corregido. T20/T28/T52 permanecen sin marcar: el tag dentro de una sesión aún es mutable, falta snapshot inmutable y protección frente a ediciones durante el build, carreras de arranque simultáneo y concurrencia completa por API/UI. Próximos pendientes: SQL/semillas, kit integral, UI/logs/cancelación y CI/CD/Kubernetes.

### Continuación: SQL versionado y semillas

T22 avanza con migraciones Liquibase incluidas en el JAR, Hibernate `validate` y SQL init sin versión deshabilitado. La generación conserva nombres y tipos JPA, selecciona dialecto por motor, incluye las dependencias antes de preparar/verificar y protege los scripts editados. El changelog admite versiones adicionales sin reescribir las iniciales; los tests H2 usan un esquema separado derivado del Java real.

La primera aceptación real tipada pasó con Maven en H2, PostgreSQL y MySQL: semilla única, avance del ID, CRUD y persistencia tras reinicio. Se agregó `test_local_docker_real_migrations.py`, una matriz opt-in de seis combinaciones con `scripts/verify_local_database.py`. Sin activación expresa omite Docker antes de invocarlo, manteniendo la prioridad del laboratorio.

Regresión enfocada: **147 PASS, 7 SKIP opt-in, sin XFAIL**. El antiguo contrato de SQL sin versión se adaptó a la solución Liquibase, respaldada por las pruebas reales; se conserva su finalidad de no montar SQL del host ni alterar silenciosamente el esquema. La suite global y matriz definitiva se documentan al terminar en la sección 18 del documento de estado.

Se conserva la evidencia FAILED de un harness que perdió el puerto alternativo al reiniciar y del primer Gradle/H2 que encontró un puerto ocupado durante una construcción simultánea. Se corrigió el harness; los scripts nuevos comprueban el puerto después del build, justo antes del arranque. Esto no acredita ausencia de carreras de reserva exactamente simultáneas.

T22 sigue sin marcar: faltan modelos y relaciones complejos y aceptación completa por API/UI. La evolución de migraciones y el rechazo de checksum ya pasaron en una BD persistente Maven/H2: versión nueva aplicada, datos anteriores conservados y semillas únicas tras reinicio. El kit integral, snapshot inmutable, logs/cancelación y CI/CD/Kubernetes siguen abiertos. No se modifica la virtualización ni los permisos del laboratorio.

Suite general definitiva: **1.015 PASS, 149 FAIL históricos, 10 SKIP; 0 fallos nuevos frente a HEAD**. El baseline original de generación se conserva; un fixture separado recoge únicamente los ocho archivos Java modificados para JPA y tipos. Evidencia y reproducción de evolución en la sección 18 del documento de estado.

Matriz SQL cerrada para los casos tipados probados: **6/6 combinaciones PASS** (Maven/Gradle × H2/PostgreSQL/MySQL), con seed única y datos persistentes. La ejecución fue recuperada tras una interrupción; MySQL retomado dio **2 PASS** y aislamiento actual **1 PASS**. Evidencias individuales y consolidado `.run/sql-real-matrix-final.json` se detallan en la sección 18 del documento de estado. Los intentos incompletos se conservan y no se cuentan como PASS.

La comprobación final no encontró contenedores activos. Se conservaron volúmenes y evidencia; rama `no-docker` / `863553a` sin cambios. Próximo bloque: kit offline integral y entorno limpio; luego observabilidad/cancelación y CI/CD/Kubernetes. No se marca aceptación integral ni se exige Docker al laboratorio.
