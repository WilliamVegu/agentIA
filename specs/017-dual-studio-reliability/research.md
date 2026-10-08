# Decisiones de investigación

Investigación estática en ambos backends y revisión de la auditoría. No se iniciaron servicios ni se consumieron APIs durante la planificación. Las decisiones siguientes cierran los supuestos técnicos del plan.

## R01 — Conservar independencia

**Decisión:** mantener dos paquetes app, dos SQLite, workspaces y frontends. Compartir especificación y fixtures de conformidad en integration, no imports entre backends ni una nueva librería transversal en esta entrega.  
**Motivo:** aislamiento ya operativo; evita mezclar app, configuración, datos y dependencias Java.  
**Alternativa descartada:** portar todo Spring a Quarkus o unificar ambos pipelines de una vez.

## R02 — Repositorio de revisiones como autoridad

**Decisión:** draft completo en revisión SQLite inmutable con JSON canónico/hash; revisión elegida por ejecución. Archivos del workspace son materializaciones atómicas. Aprobación humana, generación automática y recuperación legacy tienen orígenes distintos.  
**Motivo:** save/GET/pipeline hoy tienen autoridades incompatibles.  
**Alternativa descartada:** volver a inferir siempre desde markdown o rellenar campos legacy silenciosamente.

## R03 — Estados separados y migración aditiva

**Decisión:** mantener SessionStatus como resumen compatible; añadir operación, generationState, VerificationOutcome, auditoría y runtime persistentes. Compare-and-set por versión/operationId y lock por sesión. Extender enums de forma explícita; no renombrar masivamente los actuales.  
**Motivo:** COMPLETED de generación no implica PASSED/HEALTHY; workers en memoria y callbacks antiguos no son autoridad.  
**Legacy:** importar evidencia sólo si puede verificarse; sin informes => NOT_RUN, recursos sin identidad => UNKNOWN. Fallo previo no se borra. Draft incompleto => NEEDS_REVIEW. Copia de DB antes de migrar, sin incluir credenciales; migración idempotente y error visible.  
**Alternativa descartada:** derivar evidencia de phase, adoptar puertos o sobrescribir DB.

## R04 — Primitivas Spring con adaptadores Quarkus

**Decisión:** reproducir principios de verification_policy, SessionOperationLock, snapshot y local_runtime con adaptadores nativos.  
**Motivo:** source_snapshot.finish comprueba BOOT-INF/loader Spring; inspect_session lee SPRING_DATASOURCE_DRIVER_CLASS_NAME; platform_verification inserta pruebas Spring. Copiarlos íntegros rompería fast-jar, JDBC y REST Quarkus.  
**Adaptadores:** artefacto, health, datasource, ejecución de tests y descubrimiento de reportes.

## R05 — Guardas de archivos completas

**Decisión:** ampliar workspace_guard Spring y añadir equivalente Quarkus para sesión existente + archivo relativo. Rechazar absolutos, UNC, dispositivos, ADS, traversal, enlaces/reparse no seguros; comprobar raíz/padres antes de escribir, con lock y reemplazo atómico. Preview de remediación en memoria separado de persistencia.  
**Motivo:** Spring routes_security también tiene búsqueda global sin sessionId y errores de escritura silenciados; no es una referencia íntegramente segura.  
**Alternativa descartada:** sanitizar sólo cadenas o buscar el primer archivo con el nombre pedido.

## R06 — Restricciones tipadas, nunca Java arbitrario

**Decisión:** normalizar atributos y constraints en cada backend. Traducir legacy validationRules mediante parser cerrado: NotNull, NotBlank, Email, Positive y otras reglas compatibles; Size/Min/Max/DecimalMin/DecimalMax/Digits/Pattern requieren argumentos tipados válidos. Escape dedicado para literales. Sin imports, llamadas Java ni anotaciones desconocidas.  
**Motivo:** interpolación directa permite inyección; ignorarlas pierde reglas. Un @Min/@Pattern incompleto genera diagnóstico y bloquea esa generación, no inventa parámetros.  
**IDs:** descriptor compartido por emisores de entidad/DTO/repositorio/servicio/controller/tests/SQL. Long/Integer identidad, UUID estrategia UUID, String sólo estrategia explícita supported; PK compuesta rechazada si no implementada.

## R07 — Motor DB único y dialecto explícito

**Decisión:** databaseEngine canónico, alias database temporal con 422 si contradice; estado persistido y ORM/SQL/seeds/Compose derivados del mismo descriptor. Dialectos H2/PostgreSQL/MySQL.  
**Motivo:** driver correcto no salva un init DDL incompatible; heurísticas por VARCHAR no identifican DB.  
**Esquema:** Quarkus usa migración/bootstrap SQL explícito y ORM validate en la prueba/producción preparada; no deja Hibernate update compitiendo con init SQL. Adaptar H2 para cargar el mismo esquema. Spring mantiene su Liquibase actual; preservar migraciones ya publicadas y añadir nuevas versiones.  
**Riesgo:** UUID físico (UUID/BINARY(16)), timestamps, seeds e índices deben validarse contra el ORM real antes de declarar soporte.

## R08 — Operaciones Git y Docker seguras

**Decisión Git:** remote limpio temporal o origin preservado; PAT por cabecera acotada al host en entorno efímero, sin helpers persistentes, sin force y sin checkout -B destructivo de una rama existente. Esquemas y nombres validados, errores redactados; repositorio bare local para integración. No se crea un PR al construir un enlace.  
**Decisión Docker:** proyecto Compose por sesión, labels, puertos obtenidos de bindings inspeccionados; worker persistente con timeout/cancelación. Stop conserva volúmenes; deleteData explícito sólo sobre recursos propios.  
**Legacy:** un recurso sin identidad verificable no se gestiona automáticamente.

## R09 — Reparación y controles previsibles

**Decisión:** guardar código válido bajo lock, invalidar evidencia, verificar esas fuentes y persistir intento/resultado. diagnosticsResolved sólo con PASSED vigente. Pistas sin código se rechazan claramente (no agente nuevo); canonical guidanceHint y alias promptHint. Máximo tres intentos, valor único backend/config/UI/BDD conforme a ambas constituciones.  
**Motivo:** no simular reparación, no consumir iteraciones por falta de Docker y no regenerar draft al reintentar.  
**Alternativa descartada:** borrar el bloqueo al recibir la petición o elevar el límite a cinco sin autorización.

## R10 — UI, eventos y CI con evidencia

**Decisión:** DTO por contrato, ceros conservados, ausencia null/“No evaluado”, acciones derivadas de availableActions. SSE broadcast con registro por sesión y Last-Event-ID; retención/buffers acotados, snapshot si cursor expiró. Transición y registro SessionEvent en una transacción; dispatcher publica tras commit, recupera pendientes y clientes deduplican secuencia. Ninguna llamada de status crea una aprobación.  
**CI:** script autónomo de auditoría con scope explícito, salida distinta de cero y reportes; Maven/Gradle verify con suite no vacía; Trivy fijado. Preparación online explícita y pruebas offline. No presentar regex como SonarQube exhaustivo.  
**Telemetría:** fallo MLflow es degradación visible, no éxito ficticio ni bloqueo del servicio.

## R11 — Evidencia y versiones

**Decisión:** baseline del audit y source-snapshots.json inmutables. Nuevo source-revisions.json documenta diferencias autorizadas (before/after/task/evidence); verifier reconoce únicamente esas modificaciones. Tests de equivalencia afectados se actualizan por comportamiento corregido, con diff y prueba semántica.  
**Entorno:** repetir suites con constraints/lockfiles; diagnosticar los tres fallos Spring antes de corregir. No upgrade masivo, no hashes reescritos para ocultar modificaciones.

## Constitución y autoridad

Aplican .specify/memory/constitution.md para Spring y systems/quarkus/.specify/memory/constitution.md para Quarkus. Se mantienen Records/Jakarta, arquitectura nativa, excepciones centralizadas, sandbox y cero secretos. SOURCE_ONLY explicita entrega sin afirmar aprobación; DOCKER requiere evidencia real. Quarkus mantiene AI-first: ningún fallback mock silencioso en flujo normal, mocks sólo en tests/diagnóstico explícito. Esta reparación no modifica las constituciones.

