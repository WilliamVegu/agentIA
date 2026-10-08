# AgentIA: Spring Boot y Quarkus con una pantalla de selección

La rama `dual-systems-selector` contiene dos estudios independientes. Spring Boot permanece en la raíz con la versión de `no-docker` y los cambios locales autorizados del 7 de octubre de 2026. Quarkus está en `systems/quarkus/`: se recuperó el Studio completo de diez pestañas del commit `5d9b190`, con las plantillas nativas de `c5bda02` adaptadas al generador y correcciones verificadas. Cada uno tiene frontend, backend, dependencias y datos propios.

La pantalla inicial abre el estudio elegido en otra pestaña, conservando el selector. Se pueden usar ambos simultáneamente.

| Servicio | Dirección |
|---|---|
| Selector | http://127.0.0.1:3100 |
| Spring Boot | http://127.0.0.1:3000 |
| API Spring Boot | http://127.0.0.1:8000/docs |
| Quarkus | http://localhost:3001 |
| API Quarkus | http://127.0.0.1:8001/docs |

## Preparación y arranque

Requiere Python 3.11/3.12 y Node.js con npm. Se recomienda Node 22.22.2 o posterior compatible con los lockfiles. Desde la raíz de esta rama:

```powershell
python integration/launch.py --install
python integration/launch.py
```

En Windows también puedes usar `./start-dual.ps1 -Install` y después `./start-dual.ps1`, o `start-dual.bat`. `--no-browser` evita abrir el navegador. Ctrl+C detiene los procesos creados por el lanzador y conserva los datos. Si algún puerto está ocupado o un servicio falla, el lanzador informa el error y revierte sus propios procesos. Los registros están en `.run/dual/`.

El lanzador crea dos `.venv` y dos instalaciones `node_modules`, usa los lockfiles originales y las restricciones backend de `integration/constraints.txt`. Cada backend se ejecuta desde su propio sistema para evitar mezclar sus paquetes Python `app`. La configuración Vite original se conserva; el adaptador configura puerto, dirección y proxy.

Puedes configurar `.env`/`backend/.env` para Spring y `systems/quarkus/.env`/`systems/quarkus/backend/.env` para Quarkus. No se copiaron claves, tokens ni bases de datos del checkout original. SQLite, especificaciones, espacios de trabajo y costes se guardan por separado. Quarkus usa `backend/quarkus_workspaces` y `backend/quarkus_specifications` con el selector; las especificaciones sobreviven a un reinicio.

Conserva las direcciones `127.0.0.1` y `localhost` para separar los datos del navegador. Spring mantiene su autenticación original. Quarkus conserva el acceso demo de su Studio recuperado: su pantalla de acceso no es autenticación de servidor. El lanzador escucha únicamente en la máquina local. Los lanzadores originales siguen disponibles; para ejecución simultánea utiliza el nuevo, ya que ambos usan originalmente 3000/8000.

## Elección de Quarkus

`Quarkus_refact_2` actualmente contiene Spring Boot; sus commits alcanzables no contienen una versión nativa Quarkus. Git conservaba commits recuperables: `5d9b190` incluye el Studio completo e instrucciones IA de Quarkus, mientras `c5bda02` incorpora plantillas nativas en una migración incompleta. Se conservaron las referencias locales `recovery/quarkus-20260930` y `recovery/quarkus-v1-20260929`.

La versión integrada utiliza la infraestructura completa de `5d9b190`, sustituyendo las cuatro plantillas que aún generaban Spring. Se corrigieron identificadores UUID y nombres de claves/tablas, selección H2/PostgreSQL/MySQL, ubicación de dependencias Maven, persistencia de especificaciones, registro obligatorio de rutas y reportes de verificación. Generar pruebas no se presenta como haberlas ejecutado.

Consulta [el análisis de ramas](COMPARACION_RAMAS_QUARKUS.md) y [la recuperación de commits](HISTORIAL_Y_RECUPERACION_QUARKUS.md). No se atribuye una rama original a los commits perdidos sin evidencia.

## Comprobaciones

```powershell
python integration/verify_sources.py
python -m unittest discover -s integration -p test_launcher.py -v
# Con ambos estudios activos; requiere Playwright y Edge:
python integration/browser_smoke.py
python integration/api_smoke.py
```

`source-snapshots.json` conserva las huellas de los 1446 archivos Spring autorizados y registra la base recuperada, los cambios y las huellas finales de Quarkus. No añade datos de ejecución. Se permiten diferencias de finales de línea propias de Git en Windows.

Ejecuta las pruebas backend en procesos separados, desde cada raíz, con `PYTHONPATH=backend`. En cada frontend ejecuta `npm test` y `npm run build`. Los resultados, fallos heredados de Spring y límites están en [RESULTADOS.md](validation/RESULTADOS.md). Para generar/verificar servicios Java se necesita Java 21 y Maven; Docker y credenciales IA se requieren según la operación elegida.


## Fiabilidad y validación actual

Los cambios de fiabilidad conservan `source-snapshots.json` como baseline histórico. `source-revisions.json` registra las modificaciones autorizadas por archivo, hashes, tareas y evidencia; `python integration/verify_sources.py` rechaza cambios posteriores no registrados. Ninguno de esos archivos contiene datos de ejecución o credenciales.

Consulte [modos y comportamiento](../docs/dual-studio-reliability.md), [migración y recuperación](../docs/dual-studio-reliability-migration.md), [quickstart reproducible](../specs/017-dual-studio-reliability/quickstart.md) y [evidencia actual](validation/reliability/RESULTADOS.md). Los informes anteriores se conservan como historia y no acreditan esta revisión.

Las pruebas usan dos venv de fiabilidad independientes, SQLite/temporales propios y cero llamadas IA. Desde la raíz: `python -m integration.reliability_smoke --suite journeys --test-root .runtime/reliability/journeys --evidence-dir integration/validation/reliability/journeys`. Use `--suite migration` para ensayar bases legacy. `runtime` y `java-matrix` requieren `--docker`; ejecútelas secuencialmente y siga la preparación del quickstart.

SOURCE_ONLY exporta fuentes auditadas con estado UNVERIFIED cuando no se ejecutaron tests. DOCKER exige reportes y huellas vigentes para certificar verificación. Stop/restart conservan datos; cleanup necesita confirmación explícita. Una revisión guardada debe aprobarse por separado y los conflictos devuelven 409. La reparación automática tiene tres intentos persistidos por ciclo.
