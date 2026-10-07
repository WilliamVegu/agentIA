# Correcciones y recuperación de la sesión Docker

05/10/2026. **Resultado final de recuperación: PASS**. Se conservaron el resultado y los logs del fallo inicial; no se generó otro proyecto ni se hicieron nuevas llamadas a DeepSeek.

## Cambios

1. `source_snapshot.py` usa rutas extendidas de Windows al leer/escribir informes y JAR, validar sus hashes y limpiar copias temporales. No requiere modificar registro, políticas ni permisos de Windows. El caso reproducido mide más de 260 caracteres; la prueba también comprueba que la corrupción del informe se rechaza.
2. La normalización de entidades/tests se aplica al workspace original antes de preparar, calcular fingerprints y capturar el snapshot. La copia sellada no se normaliza de nuevo. Preparación, fuentes exportadas y ejecución usan el mismo código: `MockitoBean` se sustituye por `MockBean` compatible con el perfil Spring Boot 3.2.3.
3. Si falla conservar evidencia después de ejecutar Docker, la verificación mantiene salida y conteos, marca `evidenceError`, devuelve resultado fallido sin fallback y bloquea la aceptación. Grafo, pipeline y verificación manual no lo convierten en infraestructura ausente ni autorizan reparación automática del código por un error de almacenamiento. La política de aprobación rechaza ese campo incluso con conteos aprobados.
4. El comprobador de recuperación aporta una contraseña aleatoria de PostgreSQL mediante `.env` temporal. El despliegue ya admitía `--env-file` externo al snapshot; no fue necesario modificar ese código. El archivo de prueba se eliminó tras detener los contenedores. Nunca se solicitó ni reutilizó la clave DeepSeek para esta recuperación.

## Validación

- Regresión final conjunta, 13 archivos backend: **195 PASS / 2 SKIP en 68.85 s**. Los skips son perfiles de ejecución opt-in. Incluye modos de ejecución, snapshot, integridad, normalización, operaciones, preparación, pipeline y entrega. No equivale a aprobar toda la suite global del repositorio.
- Preparación Docker real del proyecto original: COMPLETE.
- Verificación real: **28/28 tests aprobados**, `allPassed=true`, `fallback_used=false`, snapshot `f272eaaabf1249709a975d09ef51654e`, sin `evidenceError`.
- Runtime Maven/PostgreSQL del mismo snapshot: HEALTHY; Actuator HTTP 200/UP en localhost:8080.
- API real mediante FastAPI TestClient y Docker real: POST 201, GET 200, PUT 200, entrada inválida 400, DELETE 204 y lectura posterior 404.
- Parada y reinicio sin rebuild: el registro creado conservó su cantidad actualizada (12).
- Exportación fuentes: `recovered-sources.zip`, 60,559 bytes. El test exportado contiene MockBean, coincide con el código normalizado y no contiene `.env`.
- Exportación ejecutable: `recovered-executable.zip`, 124,001,758 bytes.
- Integridad CRC de ambos ZIP comprobada. `git diff --check` sin errores.
- Parada final STOPPED; consulta Docker por etiqueta del proyecto sin contenedores activos. Contenedores detenidos, imagen y volúmenes propios se conservan. No se borraron datos ni recursos ajenos.

La recuperación posterior al fallo de despliegue por contraseña ausente duró 79.47 s. La preparación/verificación corregidas se realizaron antes y están registradas en `recovery-execution.log`; el recorrido posterior está en `recovery-deployment.log` y `recovery-result.json`.

No fue una nueva generación Auto-Pilot completa ni un recorrido de navegador: se reutilizaron y verificaron las fuentes de la sesión original. La aceptación real acredita esta combinación Maven/PostgreSQL y este modelo; no amplía por sí sola la garantía a todas las combinaciones/modelos.
