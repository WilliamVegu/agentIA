# Especificación vigente: despliegue local opcional de microservicios

**Revisión:** 5 de octubre de 2026. **Estado:** implementación parcial; aceptación integral pendiente.

Esta especificación sustituye la de septiembre. Las decisiones del usuario y el seguimiento de las 54 tareas están en [plan de implementación](../../docs/PLAN_IMPLEMENTACION_DESPLIEGUE_LOCAL.md); las pruebas y límites, en [estado consolidado](../../docs/ESTADO_DESPLIEGUE_LOCAL_DOCKER.md). El contrato estructural vigente es [devops-api.yaml](contracts/devops-api.yaml), acompañado de [semántica y recuperación](contracts/README.md).

## Alcance

La plataforma se ejecuta nativamente mediante FastAPI/Python y React/Vite/Node. Docker se usa para los microservicios generados Java 21/Spring Boot 3, con Maven o Gradle y PostgreSQL, MySQL o H2. Windows es el host requerido; el acceso es exclusivamente localhost. Se conservan los modos manual y AutoPilot.

Una preparación inicial explícita puede usar internet. Después, el objetivo es operar con imágenes, runtimes y dependencias preparadas sin acceso externo. Dependencias nuevas requieren nueva preparación. La IA remota queda fuera del requisito offline.

GitLab remoto, contratación/configuración de servicios externos, publicación pública y despliegue productivo están aplazados. La corrección y validación local de CI/CD y Kubernetes permanecen en el plan. Generar esos archivos no demuestra su ejecución. No se migran proyectos históricos.

## Prioridad: laboratorio sin virtualización

**FR-LOCAL-01.** Cada sesión guarda SOURCE_ONLY o DOCKER. SOURCE_ONLY es el valor por defecto para las nuevas solicitudes sin elección. La configuración administrativa del host limita el permiso de ejecutar Docker; no reemplaza la elección individual.

**FR-LOCAL-02.** SOURCE_ONLY permite completar requisitos, arquitectura, modelo, código, pruebas como archivos, auditoría estática, manifiestos y exportación de fuentes. No llama Docker, Compose, SDK, preparación de imágenes o descargas para avanzar. No requiere Java, Maven/Gradle, virtualización ni permisos administrativos en el host.

**FR-LOCAL-03.** Las herramientas de ejecución ausentes se registran como no ejecutadas. Los hallazgos reales y el gate de auditoría de fuentes siguen vigentes; la ausencia de Docker no se convierte en hallazgo de código ni en un PASS.

**FR-LOCAL-04.** Cuando se solicita DOCKER y falta infraestructura, el flujo ofrece Reintentar y Continuar sin Docker. Reintentar verifica las fuentes actuales. Continuar cambia explícitamente a SOURCE_ONLY y permite terminar su alcance. Se conservan los fallos reales anteriores de compilación/pruebas.

**FR-LOCAL-05.** Creación rápida, ingesta, flujo guiado, grafo, AutoPilot, reparación, overview, DevOps y exportación respetan la elección. Activar Docker posteriormente requiere una acción explícita; se verifica entonces el workspace vigente.

**FR-LOCAL-06.** No se cambian automáticamente virtualización, WSL, políticas de ejecución, firewall ni permisos del laboratorio. Python/Node y dependencias de AgentIA se preparan por separado de los contenedores del microservicio.

## Preparación, construcción y datos

**FR-LOCAL-07.** El diagnóstico diferencia CLI, daemon, Compose, imágenes y dependencias. Tener imágenes o readyForPreparation no acredita operación offline ni pruebas aprobadas.

**FR-LOCAL-08.** Preparación online y ejecución offline son acciones separadas. Las rutas/scripts offline no descargan silenciosamente. Kits transferibles validan catálogo, hashes, fingerprint, plataforma y arquitectura; SHA256 detecta corrupción, no autentica al autor.

**FR-LOCAL-09.** Configuración explícita de petición prevalece sobre ASSET_CONFIGURATION.json; solo su ausencia permite defaults de sesión/iniciales. Configuración corrupta o de otra sesión se rechaza. Motor, puerto y herramienta/directorio de build se conservan entre UI, API y entrega independiente.

**FR-LOCAL-10.** Se resuelve Maven/Gradle/Groovy/Kotlin en raíz o bootstrap; entradas ambiguas se rechazan. El build exige un único JAR Spring Boot ejecutable e íntegro. Se admite ejecución del JAR completo; extracción de capas no es requisito de aceptación.

**FR-LOCAL-11.** Construir precede a arrancar. Un build fallido no ejecuta up. Builder preparado, dependencias offline y caché privada de escritura evitan modificar la caché compartida. El runtime usa usuario no root y healthcheck con herramientas presentes.

**FR-LOCAL-12.** La aplicación publica en localhost y la BD externa permanece sin puerto público del host. Puerto ocupado: elegir otro, persistir el efectivo e informar. H2 persiste en volumen; PostgreSQL/MySQL también conservan datos al detener/reconstruir.

**FR-LOCAL-13.** DDL y semillas se aplican mediante migraciones versionadas coherentes con entidades y motor. No se promete inicialización por bind mounts antiguos ni se usa Hibernate update como prueba de SQL diseñado. Cambios posteriores deben ser aditivos y reproducibles sin borrar datos; aceptación SQL compleja sigue pendiente.

**FR-LOCAL-14.** Recursos de sesión se identifican e inspeccionan antes de operar. Stop/restart conservan datos; cleanup requiere confirmación explícita deleteData. Nunca limpiar globalmente Docker ni operar recursos ajenos.

**FR-LOCAL-15.** Generación conserva activos ajenos/editados y registra propiedad de los que genera. Verificaciones DOCKER nuevas ejecutan una copia aislada y conservan fuentes, informes y JAR sellados mediante SHA256. Deploy empaqueta ese JAR sin recompilar y comprueba imagen/contenedor contra snapshot, fingerprint y hash del JAR. Las fuentes originales modificadas invalidan vigencia; las sesiones históricas requieren nueva verificación para desplegar por API. Atomicidad frente a caídas/múltiples procesos y aceptación integral siguen pendientes. El sello comprueba integridad, no constituye protección criptográfica frente a un usuario que reescriba todos los sellos.

## Estado, contratos y entrega

**FR-LOCAL-16.** Elección, capacidad, verificación y despliegue son conceptos distintos. COMPLETED termina el alcance elegido. VERIFIED exige evidencia real vigente. HEALTHY exige identidad y salud actual; no prueba una suite.

**FR-LOCAL-17.** Verificación: NOT_RUN, SKIPPED_BY_CHOICE, ENVIRONMENT_UNAVAILABLE, INTERRUPTED, PASSED, FAILED, OUTDATED. PASSED requiere suite ejecutada, no vacía, sin fallos ni fallback y fingerprint vigente. Evidencia desactualizada no habilita despliegue verificado.

**FR-LOCAL-18.** Despliegue: IDLE, BUILDING, RUNNING, HEALTHY, DEGRADED, FAILED, STOPPED, DOCKER_UNAVAILABLE, SKIPPED_BY_CHOICE. HTTP 200 puede indicar operación en curso/omisión/fallo de entorno; el cliente lee el estado y resultado.

**FR-LOCAL-19.** Operaciones muestran identidad, fase, inicio/final y solicitud de cancelación. Pedir cancelación no prueba terminación de BuildKit. Exclusión entre procesos, límites de recursos y cancelación integral se validan separadamente.

**FR-LOCAL-20.** Logs redactados con IDs/cursor por sesión permiten snapshot y reconexión SSE mediante header Last-Event-ID. Historial acotado y posible pérdida se informan; no prometer captura sin pérdidas.

**FR-LOCAL-21.** API privada mantiene autenticación local por cookie. Configuración no expone secretos ni rutas arbitrarias. Proxy playground resuelve destino de sesión en localhost; no acepta URL externa arbitraria.

**FR-LOCAL-22.** ZIP entrega fuentes, scripts y estado honesto sin secretos, cachés privados ni JAR inexistente. Scripts independientes preparan/inician/detienen/limpian; SourcesOnly termina antes de consultar Docker. ReuseImage omite nuevas pruebas y no registra nueva verificación.

## Escenarios de aceptación

1. Laboratorio sin Docker/virtualización: crear por cada modo de flujo, completar fuentes auditadas y exportar; cero llamadas Docker. Pruebas como archivos se distinguen de pruebas ejecutadas.
2. DOCKER solicitado y ausente/deshabilitado: explicación y ambas acciones; reintento no inventa PASS, continuar conserva fallos reales.
3. Matriz Maven/Gradle × PostgreSQL/MySQL/H2: build, suite no vacía, readiness, CRUD y persistencia con contenedores reales de fixtures reproducibles sin IA.
4. Configuración/puerto guardados y explícitos, conflicto de puerto, layouts raíz/bootstrap y activos modificados: comportamiento coherente sin sobrescribir trabajo ajeno.
5. Stop/restart/rebuild, recuperación del backend, fallos del daemon, cancelación y sesiones concurrentes: solo recursos propios, datos conservados y estados consistentes.
6. Preparar/transferir a Windows y motor limpios, bloquear red externa, instalar AgentIA nativo y operar microservicios offline sin descargas. IA excluida. Esta aceptación integral todavía está pendiente.
7. CI/CD y Kubernetes: validación local estática y ejecución real documentadas por separado. Generación de plantillas no cierra este escenario.

La matriz básica y varios E2E reales ya tienen evidencia en el estado consolidado. No equivalen a aceptación integral de todos los escenarios ni a suite global sin fallos. Cada tarea parcial permanece abierta hasta satisfacer sus criterios.
