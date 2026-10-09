# Plan de implementación: fiabilidad de Spring Boot y Quarkus

**Rama:** `dual-systems-selector` · **Base:** `cd50688c8188b47ba789ec30683a50eabc7bd593`  
**Fecha del plan:** 2026-10-07, America/Lima · **Estado actual:** implementación y revisión local; ver tasks.md y RESULTADOS.md para validaciones y pendientes externos.
**Entrada:** [especificación](spec.md), [hallazgos](audit-summary.md) y análisis previo de la rama de la imagen.

## Resultado previsto

Cerrar H01–H14 y O01–O07 en ambos estudios. Conservar el diseño aprobado, generar tipos/reglas/SQL correctos y mostrar exclusivamente resultados comprobados. Detener sin perder datos, publicar sin sobrescribir historia y confinar reparación/remediación al workspace. Spring y Quarkus mantienen implementaciones, datos y frontends independientes.

El trabajo se descompone en **64 tareas, ocho historias y ocho entregas**. [tasks.md](tasks.md) contiene la secuencia ejecutable; la [matriz de regresión](contracts/regression-matrix.md) determina cuándo puede cerrarse cada hallazgo. Crear este plan no inicia implementación, migraciones, publicación ni llamadas IA.

## Contexto técnico

| Aspecto | Base y decisión |
|---|---|
| Plano de control | Python 3.12, FastAPI, Pydantic, SQLAlchemy/SQLite y LangGraph existentes; validar requirements contra `integration/constraints.txt` antes de fijar una resolución compatible |
| Frontends | React 18, TypeScript, Vite y Vitest; conservar lockfiles y componentes |
| Servicios generados | Java 21, Spring Boot 3.x o Quarkus nativo; Maven y Gradle; Records/DTO y Jakarta Validation |
| Persistencia | SQLite independiente por estudio; H2/PostgreSQL/MySQL para Java; esquema aditivo para revisiones, operaciones y evidencia |
| Pruebas | pytest, Vitest, build TypeScript/Vite, Java/JUnit y HTTP real; Docker cuando corresponda; Git contra bare locales |
| Plataformas | Windows/PowerShell y Linux/CI, rutas profundas; Java en contenedores sin exigir JDK/Maven en host |
| Rendimiento | Un escritor por sesión; SSE sin bloquear workers, buffers/replay/retención acotados y configurables |
| Alcance | Dos estudios, diez paneles por estudio, dos modos y tres DB; doce combinaciones framework × build tool × DB |
| Restricciones | Cero IA real por defecto; no force push; stop conserva volúmenes; no convertir fallo real en skip |

No se propone una actualización masiva ni una biblioteca compartida nueva. Adaptar primitivas de Spring a Quarkus sólo tras separar supuestos de driver, empaquetado y health endpoint.

## Diseño

1. **Fronteras seguras.** Resolver rutas por sesión existente, comprobar contención y enlaces, escribir atómicamente. Preview usa sólo contenido recibido. Inspeccionar propiedad Docker; separar stop de cleanup. Credenciales Git sólo en memoria, cabecera limitada al host y logs saneados.
2. **Autoridad del diseño.** Revisiones inmutables del draft completo, aprobación explícita y configuración versionada. Cada operación captura su revisión; JSON es autoridad, Markdown/SQL son materializaciones. Ediciones invalidan descendientes y evidencia.
3. **Estados y evidencia.** Separar operación, generación, verificación, auditoría y despliegue. Guardar transición y evento en una transacción; publicar después del commit. PASSED exige suite real no vacía, cero errores, sin fallback y fingerprint vigente. Invalidar vigencia conserva resultados históricos. SOURCE_ONLY no adquiere verificación ejecutada. Reparación requiere evidencia nueva; máximo tres intentos automáticos.
4. **Generación fiel.** Descriptor tipado de atributos/ID/restricciones con allowlist, usado en Java, SQL y tests. Mantener Spring/Liquibase. Quarkus genera DDL por motor; ORM valida el esquema inicializado sin competir con otro propietario del esquema. No reinterpretar migraciones publicadas.
5. **Runtime nativo.** Preparar dependencias online y verificar offline contra manifiestos actuales. Adaptadores distintos para Spring executable JAR y Quarkus fast-jar. Identificar Compose, sesión, imagen, contenedores y bindings; esperar resultado terminal real.
6. **Contratos y recuperación.** UI conserva cero/null y no usa ejemplos como fallback. SSE transmite a todos, con replay/resync. Reinicio marca operaciones inconclusas INTERRUPTED; no repite automáticamente publicaciones, despliegues o llamadas IA.

Detalles: [decisiones](research.md), [modelo y migración](data-model.md), [API](contracts/api.md).

## Entregas y puertas de salida

| Entrega | Tareas / historias | Resultado exigido |
|---|---|---|
| E0 — Base y migraciones | T001–T008 | baseline clasificado, entornos/fixtures aislados, esquema aditivo y migración sobre copia probados |
| E1 — Archivos, datos y Git | T009–T016 / US1 | rutas externas bloqueadas, stop preserva registros, cleanup sólo explícito/propio, conflicto Git sin force/PAT persistido |
| E2 — Diseño y evidencia | T017–T030 / US2–US3 | draft sobrevive reinicio, revisión capturada, target/pause/cancel correctos, gates y reparación sin falsos VERIFIED |
| E3 — Java y DB | T031–T037 / US4 | validación real 400, UUID/fechas/decimal/unique/FK correctos, doce combinaciones reales offline pasan |
| E4 — Despliegue nativo | T038–T044 / US5 | health ajeno no acredita sesión; AutoDeploy espera; fallos/colisiones/Docker ausente visibles; empaquetado nativo válido |
| E5 — Paneles y eventos | T045–T054 / US6–US7 | diez paneles coherentes, métricas auténticas, broadcast/replay y recuperación sin perder historia |
| E6 — CI y journeys | T055–T060 / US8 | CI ejecuta scanners/tests, instalación reproducible, E2E manual/guided/Auto-Pilot y ambos modos, cambios de fuentes trazados |
| E7 — Cierre | T061–T064 | suites/builds, migración/reversión y matriz completos, evidencia sin secretos, pendientes ambientales explícitos |

Dependencia general: E0 → E1 → E2 → E3 → E4 → E5 → E6 → E7. Trabajo preparatorio en archivos independientes puede adelantarse; pruebas de escritura/Docker/Git requieren E1. US7 puede desarrollarse tras US3 coordinando archivos compartidos. Las tareas [P] explicitan oportunidades de concurrencia.

## Estructura

```text
specs/017-dual-studio-reliability/
  spec.md, plan.md, audit-summary.md, research.md, data-model.md
  quickstart.md, tasks.md
  contracts/api.md, contracts/regression-matrix.md
backend/app/{api,models,services,orchestrator,sandbox,cost}/
backend/tests/
frontend/src/{views,services,hooks,components,types,test}/
systems/quarkus/backend/app/{api,models,services,orchestrator,sandbox,cost}/
systems/quarkus/backend/tests/
systems/quarkus/frontend/src/{views,services,hooks,components,types,test}/
integration/                          # launcher, constraints y pruebas duales
integration/validation/reliability/    # evidencia futura
```

Rutas de tasks.md relativas a esta raíz; «nuevo» identifica archivos por crear. No modificar legacy, skills ni baseline histórico para ocultar diferencias.

## Migración y compatibilidad

Migraciones versionadas, idempotentes y observables por backend después de backup validado. Mantener columnas/respuestas legacy durante transición: backend aditivo → clientes → validación estricta. Importar sólo evidencia comprobable; «COMPLETED» antiguo sin reportes no se convierte en PASSED. Runtime sin propiedad suficiente queda UNKNOWN, sin adopción automática.

No regenerar proyectos Java existentes en masa. Conservar fuentes/migraciones y ofrecer regeneración explícita con backup. Cambios invalidan evidencia. Reversión de código conserva tablas aditivas; restaurar DB antigua sobre nueva actividad exige procedimiento revisado sobre copia. Ver [data-model.md](data-model.md).

## Validación y trazabilidad

Primero regresiones que demuestren defectos, después corrección y suites pertinentes. Clasificar los tres fallos Spring previos por causa: MAX_PATH del clon diagnóstico, OpenAPI/FastAPI y fixture de modo/gate. No debilitar gates ni atribuir al producto un entorno no equivalente.

Probar corruptos/legacy, concurrencia, caída entre DB y evento, dos clientes, paths externos, secretos centinela, Docker fallido y cero tests. Java real sobre H2 y DDL real sobre PostgreSQL/MySQL. Doce combinaciones cubren Maven/Gradle; journeys cubren caminos críticos sin exigir producto cartesiano de todos los controles UI.

Conservar `integration/source-snapshots.json` histórico. Añadir `integration/source-revisions.json`: baseline, hashes antes/después, tarea y evidencia de cambios autorizados. `verify_sources.py` rechaza modificaciones no listadas. Registrar skips con capacidad pendiente; ninguna ausencia de infraestructura permite certificar ese caso. Guía: [quickstart.md](quickstart.md).

## Revisión constitucional

| Puerta | Comprobación previa y posterior al diseño |
|---|---|
| Capas/DTO | Capas nativas, Records inmutables, validación temprana; sin entidades como respuestas |
| Errores | Spring RestControllerAdvice; Quarkus ExceptionMapper/Panache según constitución propia |
| Modos/offline | SOURCE_ONLY autorizado sin VERIFIED; DOCKER con preparación online separada y Maven/Gradle offline |
| Calidad/reparación | Suite >0, cero fallos, máximo tres reparaciones automáticas y bloqueo persistido |
| Secretos/IA | Credenciales fuera de fuentes/logs; mocks sólo en pruebas; sin fallback inventado de producción Quarkus |
| Compatibilidad | Migración conservadora; no borrar datos ni falsificar evidencia legacy |

Diseño compatible con `.specify/memory/constitution.md` v1.1 y `systems/quarkus/.specify/memory/constitution.md` v2.0, incluida aclaración SOURCE_ONLY. No requiere excepción ni modificación constitucional. Repetir revisión al cerrar cada entrega.

## Riesgos

| Riesgo | Tratamiento |
|---|---|
| Divergencia entre estudios | Especificación de aceptación común, adaptadores nativos y pruebas espejo; evitar port literal Spring |
| Concurrencia/recuperación | CAS, escritor único, checkpoints y pruebas de callbacks obsoletos/caídas |
| DDL/tipos | Descriptor por estudio, verificar firmas/almacenamiento real en tres motores |
| Contratos | Alias temporal documentado, conflictos explícitos, OpenAPI generado con versiones fijadas |
| Dependencias/Windows | Pins comprobados, venv separados, rutas profundas; no cambiar configuración global de Windows |
| Alcance scanner | Publicar reglas y límites reales; scanner básico no se presenta como auditoría exhaustiva |

Primer incremento útil: E1/US1 tras E0. Reduce riesgos antes del resto; el objetivo completo exige E0–E7.
