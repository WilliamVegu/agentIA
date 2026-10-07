# AgentIA: selector de Spring Boot y Quarkus

**Estado: borrador pendiente del análisis de las fuentes.** La copia inicial bajo `systems/quarkus/` conserva exactamente `Quarkus_refact_2`, según la primera indicación, pero se comprobó que esa rama contiene Spring Boot y no contiene la fábrica Quarkus. No se publicó esta rama de integración. Antes de usarla como solución Spring Boot + Quarkus, consulta [la comparación de ramas](COMPARACION_RAMAS_QUARKUS.md). Las comprobaciones iniciales del selector acreditan aislamiento entre esas dos copias; todavía no acreditan integración de la fábrica real de `Quarkus_refact`.

Esta rama conserva Spring Boot (`no-docker`, incluidos los cambios locales del 7 de octubre de 2026) en la raíz. Quarkus (`Quarkus_refact_2`, commit `7efbc188888dc80a76fa11b2116555a9340c95d0`) está completo en `systems/quarkus/`. No se fusionaron componentes, modelos, rutas, dependencias ni lógica de generación.

La pantalla adicional abre cada estudio en una pestaña nueva. Permite trabajar en ambos y conservar el selector abierto. El nuevo lanzador carga la configuración Vite original de cada frontend y adapta únicamente el puerto, la dirección local y el proxy. Ejecuta cada backend desde la raíz de su propio sistema, con su propio proceso Python, configuración, base de datos y carpetas de trabajo.

| Servicio | Dirección |
|---|---|
| Pantalla de selección | http://127.0.0.1:3100 |
| Spring Boot | http://127.0.0.1:3000 |
| API Spring Boot | http://127.0.0.1:8000/docs |
| Quarkus | http://localhost:3001 |
| API Quarkus | http://localhost:8001/docs |

**Conserva estas direcciones al abrir las interfaces.** Los navegadores comparten cookies entre puertos del mismo hostname. `127.0.0.1` y `localhost` separan las cookies de acceso existentes sin modificar ninguno de los sistemas.

## Preparación y arranque

Requiere Python 3.11/3.12, Node.js y npm. Desde la raíz de esta rama:

```powershell
python integration/launch.py --install
python integration/launch.py
```

En Windows también puedes usar `./start-dual.ps1 -Install` una vez y después `./start-dual.ps1`, o `start-dual.bat`. El arranque abre el selector cuando las dos interfaces y sus API responden. `--no-browser` evita abrir el navegador. Ctrl+C detiene exclusivamente los procesos creados por ese arranque y conserva los datos. Si un puerto está ocupado o un sistema falla al arrancar, el lanzador informa el error y revierte sus propios procesos; no reemplaza servicios ajenos. Los registros están en `.run/dual/`.

Se crean dos entornos `.venv` y dos instalaciones `node_modules`. `npm ci` usa el lockfile original de cada sistema. `integration/constraints.txt` conserva las versiones de las dependencias backend resueltas en el entorno original, dado que sus `requirements.txt` contienen mínimos abiertos. Los archivos de dependencias originales permanecen intactos.

Cada sistema puede conservar su propia configuración `.env`: `.env`/`backend/.env` para Spring Boot y `systems/quarkus/.env`/`systems/quarkus/backend/.env` para Quarkus. No se copiaron claves, tokens ni bases de datos de la carpeta original. Los datos de esta nueva copia comienzan independientes. El lanzador fuerza rutas independientes para SQLite, especificaciones, espacios de trabajo y registro de costes, incluso si el entorno externo define una ruta común. Los experimentos de MLflow son `agentia-springboot` y `agentia-quarkus`; el servidor de telemetría sigue siendo opcional según cada implementación.

Los lanzadores originales permanecen disponibles para ejecutar cada sistema por separado con su configuración original. No los ejecutes simultáneamente: ambos usan originalmente 3000/8000. Para la ejecución simultánea utiliza el nuevo lanzador.

En Windows, las rutas de algunos informes históricos superan 260 caracteres al incluir la copia de Quarkus. Antes de cambiar a esta rama en otro checkout, habilita el soporte del repositorio con `git config core.longpaths true`. Para clonarlo directamente puedes usar `git -c core.longpaths=true clone --branch dual-systems-selector <URL_DEL_REPOSITORIO>`.

## Comprobaciones

```powershell
python integration/verify_sources.py
python -m unittest discover -s integration -p test_launcher.py -v
# Con los servicios activos; requiere Playwright y Edge:
python integration/browser_smoke.py
```

`source-snapshots.json` registra las huellas de todos los archivos de las dos fuentes seleccionadas. La comprobación permite exclusivamente diferencias de finales de línea del checkout. El gitlink histórico de `reports/recheck-2026-10-02/runtime/git-probe` es una referencia de prueba del repositorio original, y se conserva en Git; no es parte del código de las aplicaciones.

Las pruebas de backend deben ejecutarse en procesos separados y desde la raíz de cada sistema: ambos importan un paquete llamado `app`. Ejecutar ambas carpetas juntas en un único pytest mezclaría sus módulos.

```powershell
python -m pytest backend/tests -o pythonpath=backend
# En otra terminal, desde systems/quarkus:
python -m pytest backend/tests -o pythonpath=backend
# Desde cada frontend:
npm test
npm run build
```

Los resultados y límites de la validación de esta integración se registran en `validation/RESULTADOS.md`. Aprobar navegación, aislamiento y suites automatizadas no acredita llamadas a proveedores IA, compilación Java o despliegues Docker reales.
