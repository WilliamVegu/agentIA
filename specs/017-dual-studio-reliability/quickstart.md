# Guía de implementación y validación

Describe los runners implementados y las comprobaciones locales. Consultar `integration/validation/reliability/RESULTADOS.md` para los resultados y capacidades pendientes; los comandos no sustituyen sus informes. No pegar API keys en comandos/archivos.

## 1. Base y aislamiento

Desde `C:/Users/willi/Downloads/agentIA`, comprobar rama/commit y `git status --short`; capturar Python/Node/npm y dependencias reales. Python global puede resolver WindowsApps: usar un ejecutable comprobado. La `.venv` auditada ejecuta Python, pero carecía de pip.

T001–T004 guardan baseline y fixtures en `integration/validation/reliability/` y usan SQLite/workspaces separados. Harness rechaza DB/workspace de usuario y Docker sin etiqueta de prueba. Comparar hashes originales antes/después. No usar sesiones de usuario para reparación/cleanup.

## 2. Instalación reproducible

Resolver requirements/constraints en T002/T055 antes de instalar. Crear `.venv-reliability-spring` y `.venv-reliability-quarkus` sin reemplazar `.venv`, con Python 3.12 funcional y pip comprobado:

```powershell
# cwd: C:/Users/willi/Downloads/agentIA
& '.\.venv-reliability-spring\Scripts\python.exe' -m pip install -r backend/requirements.txt -c integration/constraints.txt
& '.\.venv-reliability-quarkus\Scripts\python.exe' -m pip install -r systems/quarkus/backend/requirements.txt -c integration/constraints.txt
```

Ejecutar `npm ci`, `npm test`, `npm run build` desde cada frontend por separado. Linux usa `bin/python`; aplicar markers de plataforma a dependencias Windows. Guardar locks/resoluciones/salidas. Conflicto de instalación se diagnostica, no se resuelve quitando constraints sin revisión.

## 3. Suites por estudio

Desde raíz Spring, con fixtures aisladas de T004:

```powershell
$env:PYTHONPATH = 'C:/Users/willi/Downloads/agentIA/backend'
& 'C:/Users/willi/Downloads/agentIA/.venv-reliability-spring/Scripts/python.exe' -m pytest backend/tests --junitxml=integration/validation/reliability/spring-backend.xml
& 'C:/Users/willi/Downloads/agentIA/.venv-reliability-spring/Scripts/python.exe' -m pytest integration/test_launcher.py --junitxml=integration/validation/reliability/launcher.xml
```

Cambiar cwd a `C:/Users/willi/Downloads/agentIA/systems/quarkus`:

```powershell
$env:PYTHONPATH = 'C:/Users/willi/Downloads/agentIA/systems/quarkus/backend'
& 'C:/Users/willi/Downloads/agentIA/.venv-reliability-quarkus/Scripts/python.exe' -m pytest backend/tests --junitxml=C:/Users/willi/Downloads/agentIA/integration/validation/reliability/quarkus-backend.xml
```

No importar ambos paquetes `app` en el mismo proceso. Restaurar PYTHONPATH. Guardar Vitest/builds. Clasificar los tres fallos Spring anteriores en T003; ajustar fixture incorrecta a política estricta, nunca al contrario.

## 4. Java real y Docker

`integration/reliability_smoke.py` implementa el runner con `--test-root`, `--suite` (`java-matrix`, `journeys`, `migration`, `runtime`) y `--evidence-dir`. Crea sesiones propias, rechaza datos originales, registra recursos. Ejecutar tras US1:

```powershell
# cwd raíz. Ejecutar las suites Docker secuencialmente para evitar saturación.
& '.\.venv-reliability-spring\Scripts\python.exe' -m integration.reliability_smoke --suite java-matrix --docker --test-root .runtime/reliability/isolated --evidence-dir integration/validation/reliability/java
& '.\.venv-reliability-spring\Scripts\python.exe' -m integration.reliability_smoke --suite journeys --test-root .runtime/reliability/isolated --evidence-dir integration/validation/reliability/journeys
& '.\.venv-reliability-spring\Scripts\python.exe' -m integration.reliability_smoke --suite migration --test-root .runtime/reliability/isolated --evidence-dir integration/validation/reliability/migration
```

Matriz: ambos frameworks × Maven/Gradle × H2/PostgreSQL/MySQL. Preparar imagen/cache online según manifiestos; después Maven `verify -o` o Gradle `test --offline` y empaquetado offline sin acceso externo. Red privada para PostgreSQL/MySQL admisible: no usar `--network none` en casos que necesitan DB externa al contenedor. Capturar ausencia de descargas.

Probar health nativo, CRUD, UUID/clave personalizada, fechas, decimal, unique/FK, correo inválido, importe negativo/cero => 400 y ausencia => 404. Exigir suite >0, exit code e informes/fingerprint vigentes. Compilación sola no certifica BDD.

La regresión negativa de validación trabaja sobre copias propias de la matriz Maven preparada: elimina cada anotación, exige que el contrato HTTP detecte el defecto y restaura las fuentes antes de repetir el contrato. No modifica proyectos del usuario ni las fixtures originales:

```powershell
$env:AGENTIA_VALIDATION_MUTATION = '1'
& '.\.venv-reliability-spring\Scripts\python.exe' -m pytest integration/test_validation_mutation.py -q --junitxml=integration/validation/reliability/validation-mutation.xml
Remove-Item Env:AGENTIA_VALIDATION_MUTATION
```

Es opt-in y requiere Docker disponible, imagen Maven/Java 21 y cache preparado. Un fallo de build/infraestructura no acredita detección del defecto. Los JSON conservan el status inesperado por anotación y el contrato restaurado.

Insertar registro, stop sin `-v`, restart y leerlo. Ocupar 8080 con servicio ajeno: no debe acreditar salud. Probar Compose fallido, Docker ausente, colisión y stale image. Cleanup sólo sobre recursos etiquetados/registrados; sin prune ni detención global.

El runner elimina credenciales de los procesos de prueba, separa paquetes `app`, SQLite y temporales y no admite fallback. `--studio springboot` o `--studio quarkus` selecciona un estudio. Las pruebas de runtime son opt-in:

```powershell
& '.\.venv-reliability-spring\Scripts\python.exe' -m integration.reliability_smoke --suite runtime --docker --test-root .runtime/reliability/isolated-runtime --evidence-dir integration/validation/reliability/runtime
```

La preparación inicial puede descargar dependencias. La ejecución de la matriz y sus tests offline no tiene acceso a proveedores IA. No ejecutar varios runners Docker simultáneamente. Los recursos y resultados pertenecen a fixtures: no reutilizar rutas/bases de usuario.

## 5. Journeys y migración

Cada estudio: manual/guided/Auto-Pilot y ambos modos; LedgerEntry personalizado, target REQUIREMENTS, pause/resume, cancel terminal, gate, reparación y cambio de modo tras FAILED. SOURCE_ONLY exporta fuentes auditadas con pruebas no ejecutadas; DOCKER requiere evidencia real para entregar como verificado.

Dos clientes SSE reciben todas las secuencias; replay o resync al reconectar. Reinicio deja INTERRUPTED sin repetición automática. Copias DB legacy: migración dos veces, fallo intermedio y reversión de código conservando datos. Git bare local: push, divergencia y PAT centinela ausente de disco/logs/respuesta.

## 6. Evidencia

Cada caso de [matriz](contracts/regression-matrix.md) registra framework, commit, revisión, configuración, fixture, esperado/observado, exit code, informes/fingerprint y skip explícito si corresponde. H01–H14 no cierran sólo con mocks si requieren runtime. Adjuntar diez paneles, CI con defectos centinela y revisiones de fuentes autorizadas; conservar baseline.

IA real es opt-in manual fuera del CI, con límite de llamadas/coste definido antes de ejecutarla y credencial sólo en memoria/entorno. Normalmente cero llamadas; resultados mock no se presentan como validación de proveedor real.

Revisión del 2026-10-09: contratos HTTP Spring repetidos sin otra carga Docker, seis aprobados; recorridos finales 34 por estudio y dos reinicios en procesos nuevos. Migración final 13/12. La comprobación de rutas profundas incluye generación, prueba de persistencia y hash de proveniencia; no acorta artificialmente la ruta para hacer pasar el producto. Linux/CI remoto, IA real, BDD completo y Trivy remoto se mantienen identificados como capacidades pendientes en la matriz.
