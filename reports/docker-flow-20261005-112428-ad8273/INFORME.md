# Única prueba de flujo con Docker y DeepSeek

Fecha: 05/10/2026. Resultado: **FALLÓ; no completó el recorrido hasta despliegue y entrega**.

- Una sola sesión: `4c849f7c-4240-4aa2-8dca-83ae9a4a837d`.
- Servicio: `flow-inventory-service`, inventario CRUD de una entidad Item.
- Proveedor: DeepSeek; herramienta solicitada/materializada: Maven; BD elegida: PostgreSQL.
- Duración del recorrido: 294.42 segundos.
- API real mediante FastAPI TestClient, autenticación local real, llamadas IA reales y procesos Docker reales. No fue un recorrido de navegador.
- DB/workspaces aislados dentro de esta carpeta. Clave recibida mediante entrada oculta, usada en memoria y excluida de los archivos del probe. Sin cambios del código de aplicación para hacer pasar el flujo.

## Resultados por etapa

| Etapa | Resultado |
|---|---|
| Autenticación y creación de sesión Docker | Aprobadas |
| Requisitos, historias, arquitectura y modelo de datos con IA | Generados |
| Generación de Java/tests | 17 artefactos materializados; journal del generador registra MODEL |
| Compilación/tests en sandbox Docker | BUILD SUCCESS; 28 tests, cero fallos, cero errores, cero omitidos |
| Sellado de informes del snapshot | Falló con FileNotFoundError al escribir XML JUnit |
| Preparación explícita en la misma sesión | Falló compilando tests originales: MockitoBean no encontrado |
| Despliegue/health PostgreSQL, CRUD HTTP, persistencia tras reinicio | No alcanzados |
| Exportación aprobada de fuentes/imagen | No alcanzada |
| Parada | API respondió STOPPED; consultas Docker posteriores por etiqueta de esta sesión/operación no devolvieron contenedores |

Los 28 tests corresponden a controlador (12), servicio (12), repositorio (2), contexto de aplicación (1) y contrato de persistencia (1). No equivalen a una aceptación real del runtime PostgreSQL: la aplicación no llegó a desplegarse.

## Hallazgos

**1. Fallo al conservar evidencia de snapshot.** Tras BUILD SUCCESS, `SourceSnapshot.finish()` intenta escribir `TEST-com.example.flowinventory.controller.ItemControllerTest.xml` en el directorio de informes del snapshot y produce FileNotFoundError. La ruta completa mide 280 caracteres. El tamaño de la ruta es una causa probable en Windows; no se confirmó cambiando políticas ni repitiendo el flujo en una ruta corta. La ubicación aislada de este probe contribuye a su longitud.

**2. Normalización incoherente entre verificación y preparación.** El proyecto original utiliza Spring Boot 3.2.3 e importa/aplica `MockitoBean`. `_verify_workspace()` captura el snapshot y `_verify_workspace_live()` normaliza los tests en la copia temporal, incluyendo la sustitución por MockBean. Los tests de esa copia pasan. `Dockerfile.prepare` construye las fuentes originales del workspace, donde la anotación incompatible permanece, y falla en la compilación de tests. Los resultados de la copia normalizada no acreditan que las fuentes originales compilen.

**3. Clasificación del fallo de verificación.** El pipeline registra la excepción de sellado como `fallback_used=True` y `ENVIRONMENT_UNAVAILABLE`, pese a que Docker sí ejecutó la compilación y las 28 pruebas. La sesión queda PAUSED/FAILED con acciones RETRY/CONTINUE_WITHOUT_DOCKER. Se pierde en sus métricas finales la distinción entre indisponibilidad del entorno y fallo al persistir evidencia.

Se ejecutó la preparación ofrecida para esa misma sesión y se conservó su fallo; no se creó otra generación ni se corrigieron fuentes para convertir la prueba en PASS.

## Evidencia

- `result.json`: secuencia, tiempos, estados API y errores completos, redactados.
- `execution.log`: salida del proceso de aceptación.
- `docker-logs.json`: captura de logs de Docker disponibles al finalizar.
- `workspaces/4c849f7c-4240-4aa2-8dca-83ae9a4a837d/`: fuentes generadas, manifiestos, estado operativo y snapshot parcial.

No se ejecutaron pruebas posteriores para corregir/revalidar estos hallazgos. No se acredita la entrega completa del sistema con esta sesión.

## Continuación posterior autorizada

Después de este resultado inicial, el usuario pidió resolver los errores. Se corrigieron y se recuperó **la misma sesión**, sin una nueva generación ni llamadas a DeepSeek. La recuperación pasó verificación, despliegue PostgreSQL, CRUD, persistencia y exportación. Consulte [correcciones y validación](CORRECCIONES.md) y `recovery-result.json`. El texto anterior conserva el estado del primer intento.
