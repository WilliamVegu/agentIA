# Análisis actual de AgentIA: sin Docker y con Docker

Revisión: 05/10/2026, America/Lima. Rama `no-docker`, HEAD `e4ca551`. Análisis y verificaciones; sin correcciones de código, cambios de configuración ni publicación.

## Conclusión

El modo sin Docker es funcional para generar, auditar y entregar fuentes. El modo Docker tiene implementación y evidencia real de compilación, pruebas, despliegue y persistencia en las seis combinaciones Maven/Gradle × H2/PostgreSQL/MySQL. El sistema todavía no tiene una regresión backend completamente aprobada ni aceptación integral actual del recorrido de navegador.

Docker se aplica a los microservicios generados. La plataforma AgentIA sigue arrancando de forma nativa con Python/FastAPI y Node/React/Vite; no tiene Dockerfile/Compose propio.

## Entorno comprobado ahora

- Python del entorno `.venv`: 3.12.14; Node: 24.18.0. El comando `python` del PATH apunta al alias WindowsApps; los launchers generales dependen de ese PATH y no seleccionan explícitamente `.venv`.
- Docker cliente/servidor: 29.7.2; Compose: 5.5.1. Motor accesible fuera del sandbox, con builders, runtime Java, PostgreSQL y MySQL preparados. El primer error de acceso era del sandbox y no demuestra indisponibilidad del motor.
- No se encontraron listeners en 3000/8000/8080. AgentIA manual está detenido. El único contenedor activo listado fue `adoring_thompson`, con 8082/tcp sin publicación indicada; no se examinó su contenido ni se alteró.
- Configuración cargada: `DOCKER_ENABLED=True`, `ALLOW_HERMETIC_FALLBACK=False`, `ALLOW_OFFLINE_MOCK=False`, `MAX_REPAIR_ATTEMPTS=5`. Cada sesión debe elegir Docker explícitamente; `SOURCE_ONLY` es el default.

## Modo sin Docker

La política central retorna antes de ejecutar Docker. Genera pruebas como fuentes y registra ejecución omitida; no presenta `VERIFIED` ni pruebas aprobadas. La exportación requiere generación terminada, fingerprint vigente y auditoría estática aceptable. Una IA remota sigue necesitando proveedor, credenciales y conectividad; la aceptación determinista no certifica esa integración.

Verificación nueva: `test_native_source_flow_real.py`, **2 PASS en 23.25 s**, con Docker global permitido y prohibido. Ambos resultados confirman PATH vacío, guard activo en ambos arranques, cero intentos prohibidos, tests generados, ejecución omitida, auditoría/ZIP y recuperación de sesión tras reinicio. Procesos propios detenidos.

Evidencia: `.run/native-source-flow-real/85fdee76-cfa1-4fa6-a4f4-21911b45ef98/result.json` y `.run/native-source-flow-real/356c4978-262f-4a1c-bba2-3e394ad30cbd/result.json`.

## Modo Docker

El código incluye diagnóstico, preparación explícita, build y tests reales, snapshot sellado, vínculo entre fuentes/JAR/imagen, Compose con puerto localhost, identidad por sesión, salud, logs, parada/reinicio y conservación de datos. La entrega ejecutable exige evidencia vigente y runtime saludable.

Evidencia existente más reciente: `.run/docker-sql-matrix-current.txt`, **6 PASS en 812.73 s**; cubre esquema, semillas, CRUD y persistencia en las seis combinaciones. Se revisó el registro, sin repetir esta matriz en esta revisión.

Se revisaron también registros de entrega ejecutable real y cancelación BuildKit en producción (un caso aprobado por cada uno). La sección 43 del documento de estado registra CI local Maven/Gradle y Kubernetes PostgreSQL/MySQL con aceptación real. Estos registros no certifican cada posible modelo generado ni todas las carreras, recuperaciones o proveedores IA.

## Verificaciones nuevas y problemas abiertos

- Frontend: **104 PASS / 15 archivos**; TypeScript y build Vite aprobados. Advertencia: bundle JavaScript de 576.56 kB, 162.55 kB gzip, supera el umbral de 500 kB de Vite.
- Backend seleccionado: **139 PASS / 3 FAIL / 1 SKIP**, 14 archivos, 62.73 s. Incluye modos de ejecución, configuración, migraciones, snapshots, entrega ejecutable, controles de operación, locks, Kubernetes/CI, rutas DevOps/exportación/reparación/orquestación y relaciones SQL. Las pruebas ordinarias incluyen simulaciones; este conteo no equivale a 139 pruebas Docker reales.
- Fallo DevOps: el test espera `postgres:16-alpine`, pero el generador fija `postgres:16.4-alpine`. La respuesta afirma PostgreSQL y contiene el manifiesto; la expectativa de tag está desactualizada.
- Dos fallos de reparación: los fixtures solicitan reparar sesiones que no crean en BD/workspace. El POST devuelve 500 y el historial posterior 404. No prueban por sí solos fallo de reparación para sesiones válidas. Sin embargo, `routes_tests.py` captura `HTTPException` dentro de `except Exception` y la convierte en 500: existe un defecto de clasificación de errores que afecta a rechazos previstos 400/404/409.
- La suite global no se repitió. Su registro anterior es **1255 PASS / 147 FAIL / 41 SKIP / 34 ERROR**; hubo correcciones posteriores. No usar esos conteos como resultado exacto del HEAD actual ni declarar la suite global aprobada.
- Documentación desfasada: la cabecera del estado sigue remitiendo a sección 42 y a 32/54 tareas, aunque sección 43 y logs posteriores añaden entrega ejecutable, CI/Kubernetes y nuevas verificaciones. README conserva referencias a Streamlit y límite de tres reparaciones, mientras el frontend principal es React y el límite efectivo es cinco.
- Falta cerrar aceptación integral en navegador, reparación con sesiones válidas, matriz ampliada de relaciones/tipos SQL y escenarios completos de concurrencia/recuperación. Offline integral y GitLab remoto figuran aplazados en la referencia vigente.

## Prioridad sugerida

1. Corregir clasificación de errores de reparación y actualizar fixtures con sesiones/workspaces reales.
2. Alinear el test PostgreSQL con la versión fijada y ejecutar la regresión backend completa en el HEAD actual.
3. Completar el recorrido React/API en ambos modos, incluida reparación, activación posterior de Docker, cancelación y exportación.
4. Consolidar documentación y tareas a partir de la evidencia más reciente; ampliar SQL y concurrencia según los fallos encontrados.

Las ejecuciones iniciales en sandbox fallaron por acceso a SQLite temporal y `EPERM` de Node; se repitieron fuera del sandbox con autorización. Se reportan los resultados válidos de esas repeticiones, sin atribuir las restricciones del sandbox a la aplicación.
