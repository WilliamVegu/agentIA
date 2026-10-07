---
name: obs-screen-recorder
description: Controla OBS Studio en Windows mediante OBS-WebSocket v5 para iniciar, detener, pausar o reanudar grabaciones, consultar su estado, cambiar escenas y guardar capturas de fuentes de OBS. Úsala para solicitudes de OBS o grabación con OBS.
---

# OBS Studio para Codex

Usa [scripts/obs_control.py](scripts/obs_control.py). Resuelve su ruta desde el directorio de esta skill; no supongas que el proyecto contiene `.agents/skills/obs-screen-recorder`.

## Preparación

El helper requiere Windows y `obsws-python` para conectarse. Si existe `$skill/.venv/Scripts/python.exe`, úsalo: la instalación adaptada incluye ese entorno dedicado. En otra instalación selecciona un Python real (el alias `WindowsApps/python.exe` puede no funcionar): el entorno virtual del proyecto o el runtime obtenido con `load_workspace_dependencies`. Ejecuta `doctor --json` antes del primer uso para comprobar instalación, proceso, dependencia y WebSocket sin iniciar OBS ni modificar su configuración. `--help` y `doctor` funcionan sin instalar dependencias.

Si falta la dependencia, instálala con ese intérprete: `& $python -m pip install -r "$skill/scripts/requirements.txt"`, respetando los permisos de ejecución y red disponibles. Para un entorno dedicado, crea un venv en una ubicación permitida. No instales paquetes durante una simple consulta de diagnóstico.

El helper lee `%APPDATA%/obs-studio/plugin_config/obs-websocket/config.json` y mantiene la contraseña fuera de la salida. Si falta el archivo o WebSocket está desactivado, indica que se habilita en **Herramientas > Configuración del servidor WebSocket** de OBS. No cambia ese archivo ni desactiva la autenticación.

## Operaciones

Ejemplos PowerShell: `$python` es el ejecutable seleccionado y `$skill` la ruta absoluta de esta skill.

```powershell
& $python "$skill/scripts/obs_control.py" doctor --json
& $python "$skill/scripts/obs_control.py" status --json
& $python "$skill/scripts/obs_control.py" scenes --json
& $python "$skill/scripts/obs_control.py" start --json
& $python "$skill/scripts/obs_control.py" pause --json
& $python "$skill/scripts/obs_control.py" resume --json
& $python "$skill/scripts/obs_control.py" stop --json
& $python "$skill/scripts/obs_control.py" set-scene --name 'Escena' --json
& $python "$skill/scripts/obs_control.py" screenshot --output 'C:/ruta/permitida/captura.png' --json
```

`screenshot` captura la escena actual; `--name` selecciona otra escena o fuente. Conserva su resolución original. Una escena de OBS puede contener cámara, ventana u otras fuentes: no la describas como captura de todo el escritorio sin comprobarlo.

Las consultas no abren OBS. Si el usuario pide grabar y está cerrado, `start --auto-launch --json` lo abre y espera la conexión. `launch --json` permite abrirlo explícitamente; `--obs-exe` admite otra ubicación del ejecutable. Los procesos se lanzan con `Start-Process -WindowStyle Hidden`; una aplicación OBS puede presentar su propia ventana. Respeta cualquier escalación requerida para ejecutar aplicaciones GUI.

## Verificación y alcance

- Comprueba código de salida y JSON. Los errores salen por stderr, en JSON si se pidió, y devuelven código distinto de cero.
- El helper consulta el estado después de grabar, pausar, reanudar, detener o cambiar escena. Si una operación falla, consulta el estado antes de reintentar; evita alternar grabación con un toggle.
- `stop` verifica la ruta devuelta por OBS y que el archivo exista y no esté vacío. Acepta MKV, MP4 y otros formatos configurados; no busca el archivo antiguo más reciente ni convierte formatos. Si OBS detuvo la grabación pero no permite verificar el archivo, comunica ambos hechos.
- Las capturas se verifican en disco; usa una ruta permitida. Si hace falta revisar su contenido, usa `view_image`.
- Esta skill no automatiza ratón/teclado ni mantiene un estado artificial de actividad. Para una tarea de interfaz independiente, utiliza únicamente las herramientas de interfaz disponibles y autorizadas en esa sesión. La grabación no autoriza esas acciones adicionales.
