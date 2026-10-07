# Verificación de correcciones — 2 de octubre de 2026

## Veredicto

**No están todos los errores solucionados.** Hay correcciones efectivas, pero permanecen defectos importantes y se introdujo una regresión en la selección del proveedor de requisitos. Modelos & SQL ahora llama a DeepSeek, pero falla al procesar su respuesta y oculta el fallo mediante una salida prefabricada.

Se verificó la rama `levantando_observaciones`, commit **`d0e6784`**, comparada con la auditoría del commit `3e696a4`. El árbol de la aplicación estaba limpio al comenzar. Solo se añadieron archivos de esta verificación en `reports/recheck-2026-10-02/`; no se aplicaron correcciones al código.

## Comprobaciones ejecutadas

- Reproducciones HTTP contra FastAPI real en 8011, con base de datos y workspaces nuevos y aislados.
- Edge/Playwright: diez pestañas, conexión real DeepSeek, cambio de modelo, aprobación/cambio de sesión y cierre de sesión seguido de recarga. Sin errores JavaScript registrados.
- Una generación real completa de las cinco etapas con `deepseek-flash`; otra generación real cancelada al inicio. Ambas registraron proveedor y modo `MODEL`.
- Llamada real de Modelos & SQL observando las excepciones del servicio original, sin sustituir el modelo ni su respuesta.
- Exportaciones, quality gate, guardado/recarga, escape de rutas, historial de reparación, auditoría vacía y pausa.
- Reinicio del backend aislado y lectura de sus métricas persistidas.
- Git original contra un remoto local inalcanzable, con un token ficticio; sin publicación externa.
- `npm run build`: **pasó**, incluyendo TypeScript y Vite. Solo aviso de bundle JavaScript superior a 500 kB.
- Análisis sintáctico de 127 módulos Python: sin errores.

Docker sigue inaccesible. No se compiló ni ejecutó el proyecto Java, ni se validó un despliegue saludable. Las suites que sustituyen el LLM no se ejecutaron. Algunas comprobaciones de persistencia reutilizan las salidas reales de DeepSeek guardadas en la primera auditoría; están identificadas en `probe_contracts.py`.

La autorización explícita del usuario permitió enviar a DeepSeek requisitos ficticios de biblioteca y sus artefactos de prueba. Una solicitud marcada como DeepSeek fue desviada por el código a OpenAI y obtuvo 401, sin generar contenido. No se repitió esa ruta una vez identificada la regresión. Las demás llamadas reales se hicieron por rutas que conservaron el proveedor DeepSeek.

## Estado de los 25 hallazgos anteriores

“Corregido” significa que la reproducción indicada dejó de fallar; no constituye una garantía sobre todas las rutas del sistema. “Parcial” indica que se arregló una parte y permanece otra. Las observaciones basadas exclusivamente en código se señalan expresamente.

| ID | Hallazgo anterior | Estado actual | Comprobación |
|---|---|---|---|
| H01 | Auto-Pilot falla al crear requisitos | **No resuelto; regresión** | Se corrigieron los argumentos incompatibles, pero el servicio descarta proveedor/modelo resueltos. La transformación HTTP solicitada con DeepSeek devuelve 500 por llamada a OpenAI. Auto-Pilot usa el mismo servicio. |
| H02 | Borrador de otra sesión | **Corregido en el recorrido probado** | Tras aprobar en A y cambiar a B vacía, generar arquitectura muestra que falta el borrador; no se envía ninguna solicitud de diseño. El contexto se limpia al cambiar. No se ejercitaron carreras con respuestas pendientes. |
| H03 | Escritura absoluta en reparación | **Corregido en la ruta probada** | Ruta absoluta y `../` rechazados con 400; testigo externo intacto. Persiste otro escape de escritura, descrito como N01. |
| H04 | Lecturas fuera de sesión | **Corregido en las reproducciones originales** | Escape a carpeta hermana y remediación con ruta absoluta rechazados con 400. |
| H05 | Login sin protección del backend | **Parcial** | Logout/recarga permanece desconectado. API de sesiones y modificaciones siguen accesibles sin autenticación. Añadir `X-User-Email` al cliente no autentica al usuario en backend. |
| H06 | Modelos & SQL prefabricado | **Parcial, sigue incumpliendo la generación real** | Hace una llamada real, luego `EntityAttribute` provoca `NameError`; el servicio lo oculta y devuelve la salida determinista. Refinación y síntesis de pruebas siguen usando reglas/plantillas. |
| H07 | GET convierte BLOCKED en VERIFIED | **Parcial** | La sesión bloqueada real ya conserva `BLOCKED/FAILED` después de generar DevOps y consultar la lista. Pero el GET aún modifica otros estados por presencia de archivos; `testsPassed` aún confía en `VERIFIED` incluso si sus métricas indican cero pruebas. |
| H08 | Cinco pruebas ficticias tras reiniciar | **Corregido en la reproducción** | Antes/después del reinicio: cero pruebas, `allPassed=false`, duración y motivo real de fallback conservados. |
| H09 | Cancelación ignorada | **Parcial** | Se conserva `CANCELLED` y solo se ejecuta SCAFFOLDER, no las cinco etapas. La operación en curso completa archivos después de cancelar. El puesto de cola aún se libera inmediatamente, antes de acabar el trabajador. |
| H10 | Exportación elude quality gate | **Parcial** | Exportación normal y bundle rechazan SAST bloqueado con 403. Proyecto real `BLOCKED/FAILED` por ausencia de verificación sigue exportándose con 200. |
| H11 | Preferencias ignoradas | **No resuelto** | Blueprint real con hexagonal/Gradle produjo `pom.xml` y controller/service/repository/model. Se amplió el payload, pero las instrucciones siguen imponiendo Maven y cuatro capas. |
| H12 | Modelo elegido no se propaga | **Parcial** | Cambiar modelo invalida la verificación en navegador. Las vistas no pasan el modelo seleccionado a generación; el servicio de requisitos tampoco usa la variable resuelta. |
| H13 | Token Git en disco | **No resuelto** | La traza del servicio original vuelve a observar el token ficticio en `.git/config`. El comentario nuevo dice que no se guarda, pero `set_url(auth_url)` y `create_remote(..., auth_url)` permanecen. |
| H14 | Pérdida del borrador al guardar | **Parcial** | Guardado/GET de API conserva exactamente el borrador completo. El guardado no genera markdown cuando falta; el serializador importado no se usa. El cliente sigue reconstruyendo datos y paquetes al aprobar/transferir. |
| H15 | SQL aprobado no se guarda | **Corregido en la reproducción** | La API escribe `domain_model.json`, `schema.sql` y los datos SQL presentes, y avanza la fase. Sigue sin validar la existencia/aislamiento de sesión: N01. |
| H16 | Reparación afirma éxito sin verificar | **Parcial** | Sesión inexistente devuelve 404; reparación real devuelve `diagnosticsResolved=false` y verificación pendiente. No programa ni ejecuta esa verificación; el historial de la sesión realmente bloqueada informa `INITIAL`. |
| H17 | Auditoría vacía PASS 100 | **No resuelto** | Entrada vacía continúa devolviendo PASS, 100 y permiso de exportación. |
| H18 | Pausa de sesión inactiva | **No resuelto** | Una sesión sin trabajador puede pausarse con HTTP 200. |
| H19 | Diagrama con datos fijos | **Parcial** | Por revisión del código, ER ahora extrae atributos del texto. La representación de arquitectura continúa dibujando cuatro capas fijas independientemente del diagrama. |
| H20 | Monitor inventa intentos agotados | **Corrección localizada por revisión** | El mensaje de agotamiento ahora depende del contador; por debajo del límite informa causa o intervención. Build pasa. No se reprodujo otra ejecución fallida de Auto-Pilot porque la selección de proveedor está defectuosa. |
| H21 | Costes sin agregado final | **Parcial** | La generación bloqueada y la cancelada ahora tienen agregado de sesión y `cost_record_json`. Sigue faltando cobertura uniforme de llamadas guiadas. Las salidas anticipadas por fase objetivo no agregan ni finalizan el registro en DB, por revisión. |
| H22 | Auto-Pilot verifica pese a fallar sandbox | **No resuelto en todas las rutas** | Por revisión: ahora detiene fallo normal, pero permite continuar si `fallback_used=true`, marca esa etapa COMPLETED y puede acabar `VERIFIED` sin ejecutar pruebas. No se alcanzó funcionalmente debido a la regresión H01. |
| H23 | Fase objetivo ignorada | **Parcial por revisión** | Se añadieron límites por fase, pero esos retornos solo actualizan estado en memoria/eventos; dejan la fila de sesión en RUNNING, sin finalización/coste. No se ejecutó esta ruta con el proveedor defectuoso. |
| H24 | Auto-Pilot evita cola común | **No resuelto por revisión** | Sigue arrancando su propio hilo sin adquirir puesto de `queue_manager`. |
| H25 | Playground sin containerId | **Parcial y no validado con Docker** | Se añadió parsing de logs y un identificador ficticio `${session_id}-api` como fallback. No consulta el contenedor real para demostrar existencia/pertenencia. Docker inaccesible impide validar un despliegue efectivo. |

## Defectos que impiden aceptar el conjunto de cambios

### 1. Requisitos descarta DeepSeek y usa otro proveedor — P1

El servicio calcula `chosen_prov` y `chosen_mod`, pero llama al cliente con `chosen_provider` y `chosen_model`, que son parámetros distintos y quedan en `None` cuando el endpoint/Auto-Pilot usan `provider` y `model_name`. La fábrica infiere OpenAI a partir del formato de la clave.

**Reproducción:** solicitud con proveedor DeepSeek y modelo Flash → HTTP 500 con rechazo 401 de OpenAI. No hubo salida de otro modelo. Es una regresión respecto de la primera auditoría, donde esta misma solicitud generó requisitos con DeepSeek.

Código: [requirements_service.py:246](/C:/Users/willi/Downloads/agentIA/backend/app/services/requirements_service.py:246), [requirements_service.py:254](/C:/Users/willi/Downloads/agentIA/backend/app/services/requirements_service.py:254). Evidencia: [api-results.json](C:/Users/willi/Downloads/agentIA/reports/recheck-2026-10-02/api-results.json).

### 2. Modelos & SQL oculta NameError y fabrica la respuesta — P1

La llamada real a DeepSeek regresó, pero al convertir sus entidades el servicio intenta usar `EntityAttribute`, que no está importado. La excepción se captura con `except Exception` y se devuelve `_mock_domain_model_response(draft)`. `DomainEntity` tampoco está importado, por lo que arreglar solo la primera referencia no basta. Además, `isUnique` de la respuesta LLM no se conserva en la conversión.

**Reproducción:** traza de Python sobre el servicio original, con DeepSeek real: `NameError: name 'EntityAttribute' is not defined`, línea 585; respuesta externa aparentemente válida. No se sustituyó el cliente ni la salida del modelo.

Código: [model_sql_service.py:585](/C:/Users/willi/Downloads/agentIA/backend/app/services/model_sql_service.py:585), [model_sql_service.py:605](/C:/Users/willi/Downloads/agentIA/backend/app/services/model_sql_service.py:605). Evidencia: [real-model-results.json](C:/Users/willi/Downloads/agentIA/reports/recheck-2026-10-02/real-model-results.json).

### 3. N01: otro guardado escribe fuera del workspace — P1

El nuevo guardado SQL sigue concatenando un identificador de sesión sin validarlo. **`POST /api/v1/models/sessions/%2e%2e/save`** devuelve 200 con `sessionId=".."` y escribe `domain_model.json` en `runtime/`, fuera de `runtime/workspaces/`. Se usó exclusivamente un testigo en el directorio de esta verificación.

La reparación manual sí rechaza las rutas antiguas, pero el sistema todavía carece de una validación central para todos sus guardados. Este defecto ya era visible como aceptación de sesiones inexistentes en la primera auditoría; aquí se verificó el escape de ruta.

Código: [routes_models_sql.py:105](/C:/Users/willi/Downloads/agentIA/backend/app/api/routes_models_sql.py:105). Evidencia: [save-traversal-results.json](C:/Users/willi/Downloads/agentIA/reports/recheck-2026-10-02/save-traversal-results.json).

### 4. Git todavía persiste credenciales — P1

La modificación mejora el mensaje de error, pero conserva la escritura de la URL autenticada en el remoto. La prueba observó el token ficticio en disco en siete puntos de ejecución. Se limpia después del fallo normal, pero no se cumple la promesa de no persistirlo durante el proceso.

Código: [git_service.py:68](/C:/Users/willi/Downloads/agentIA/backend/app/services/git_service.py:68). Evidencia: [git-results.json](C:/Users/willi/Downloads/agentIA/reports/recheck-2026-10-02/git-results.json).

### 5. Preferencias reales siguen contradiciendo las instrucciones — P1

Agregar claves al payload y permitir rutas Gradle no cambia el contrato de las instrucciones. `scaffolder.md` sigue declarando Maven obligatorio, salida exacta `pom.xml` y capas estrictas. La generación real lo obedeció pese al input hexagonal/Gradle.

Código: [scaffolder.md:14](/C:/Users/willi/Downloads/agentIA/backend/app/resources/instructions/scaffolder.md:14), [runner.py:594](/C:/Users/willi/Downloads/agentIA/backend/app/orchestrator/stages/runner.py:594). Evidencia: [graph-state.json](C:/Users/willi/Downloads/agentIA/reports/recheck-2026-10-02/graph-state.json), `probe_extra.py`, workspace `cb498e76-dab8-4dee-9aa4-f51937caf980`.

### 6. Persisten resultados incompatibles y falta de autorización — P1

La sesión real bloqueada ya no se convierte en verificada al listar, pero aún se exporta sin pruebas. En una fila testigo con el estado heredado `VERIFIED` y métricas de cero pruebas/fallback, el overview responde `testsPassed=true` mientras el endpoint de métricas responde `allPassed=false`. No se migran ni invalidan los falsos estados anteriores.

Las API continúan aceptando cambios sin credenciales de usuario; el logout corregido es una mejora del navegador, no una protección de acceso a los proyectos.

Código: [lifecycle_service.py:388](/C:/Users/willi/Downloads/agentIA/backend/app/services/lifecycle_service.py:388), [routes_publish.py:45](/C:/Users/willi/Downloads/agentIA/backend/app/api/routes_publish.py:45). Evidencia: [contract-results.json](C:/Users/willi/Downloads/agentIA/reports/recheck-2026-10-02/contract-results.json), [final-results.json](C:/Users/willi/Downloads/agentIA/reports/recheck-2026-10-02/final-results.json).

## Evidencia de mejoras relevantes

- **Métricas persistidas:** tras reiniciar, `totalTests=0`, `passedTests=0`, `allPassed=false`, `fallback_used=true`; no reaparecen los cinco tests de ejemplo. `restart-results.json`.
- **Estado bloqueado:** tras DevOps y GET de sesiones sigue `BLOCKED/FAILED`, con `testsPassed=false`. `final-results.json`.
- **Cancelación:** se mantiene `CANCELLED`, diario con una sola etapa SCAFFOLDER; se registró el coste. La observación de 140 segundos detecta creación de archivos de esa operación en curso. `cancel-results.json`, `cancel-final-state.json`.
- **Quality gate:** ambos mecanismos de exportación responden 403 para el testigo SAST bloqueado. `extra-results.json`, `contract-results.json`.
- **Proveedor verificado:** DeepSeek devuelve CONNECTED y cambiar el modelo quita esa marca. Logout/recarga conserva desconexión; clave ausente de storage. `browser-recheck.json`.
- **Persistencia del borrador:** guardado/GET exactamente iguales para el borrador real anterior. `contract-results.json`.

## Recomendación

No considerar cerrado el informe anterior. Corregir primero la selección del proveedor, el procesamiento/fallback de Modelos & SQL, la validación común de rutas/sesiones y las credenciales de Git. Después, unificar estados y evidencias de verificación, ejecutar las reproducciones pendientes de Auto-Pilot y repetir las pruebas Java/despliegue con Docker disponible.

Todos los scripts y resultados de esta repetición se encuentran junto a este informe. Los archivos de la primera auditoría se conservaron. Las conclusiones funcionales se basan en ejecuciones nuevas; los hallazgos restantes por código están marcados como tales.
