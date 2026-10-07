# Recorrido Docker con OBS: comprobación previa

Fecha: 2026-10-05.

El recorrido solicitado no se ejecutó: el control de Windows y del navegador no pudo inicializarse. Ambos devolvieron `windows sandbox failed: helper_unknown_error: apply deny-read ACLs`. Se reinició el runtime y se repitió la inicialización; el error persistió.

Comprobaciones realizadas fuera del aislamiento:

- Docker cliente y servidor: 29.7.2.
- Backend existente escuchando en 8000; frontend existente en 3000.
- OBS conectado mediante la skill obs-screen-recorder, escena actual `Escena`, WebSocket en 4455.
- OBS no estaba grabando. No se inició grabación ni una nueva generación con DeepSeek.

La captura visual de la escena y el recorrido completo siguen pendientes. Estas comprobaciones no confirman que un nuevo microservicio pueda completar generación, pruebas y despliegue.

No se incluyeron credenciales en este informe.

## Reparación del entorno

Se comprobó que `deny_read_acl_state.json` contenía 22 bytes nulos. Se conservó una copia del archivo corrupto y se apartó únicamente ese archivo; el inicializador nativo de Codex regeneró un JSON válido (`principals`). El registro confirmó la finalización del setup sin errores. No se modificó el perfil de permisos ni se desactivó el sandbox.

La prueba mínima del runtime devolvió `runtime listo`. El control del navegador volvió a funcionar y la conexión con DeepSeek se verificó en la interfaz. La comprobación de la ventana mediante Computer Use se detuvo al no identificar con suficiente confianza la URL activa.

En el siguiente intento el navegador volvió a abrir AgentIA correctamente. Se comprobó que OBS capturaba otra pestaña de Brave; se pidió mostrar AgentIA antes de empezar la grabación. No se inició una nueva generación ni una grabación mientras la captura seguía mostrando otra pestaña.
