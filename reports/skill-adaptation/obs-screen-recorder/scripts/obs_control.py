"""Control de OBS-WebSocket v5 para Codex; nunca modifica la configuración."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

DEFAULT_EXE = r"C:\Program Files\obs-studio\bin\64bit\obs64.exe"


def config_path():
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA no está definido; se requiere Windows.")
    return Path(appdata) / "obs-studio/plugin_config/obs-websocket/config.json"


def load_config():
    path = config_path()
    if not path.is_file():
        raise RuntimeError("No existe la configuración de OBS-WebSocket. Habilítalo en Herramientas de OBS.")
    try:
        cfg = json.loads(path.read_text(encoding="utf-8-sig"))
        port = int(cfg.get("server_port", 4455))
        if not 1 <= port <= 65535:
            raise ValueError("port")
        return {"host": "127.0.0.1", "port": port,
                "password": cfg.get("server_password", "") if cfg.get("auth_required", True) else "",
                "enabled": bool(cfg.get("server_enabled", False)),
                "auth_required": bool(cfg.get("auth_required", True))}
    except (ValueError, TypeError, AttributeError):
        raise RuntimeError("La configuración de OBS-WebSocket es inválida.") from None


def running():
    if sys.platform != "win32":
        return False
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command",
         "@(Get-Process obs64 -ErrorAction SilentlyContinue).Count"],
        capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise RuntimeError("No se pudo consultar el proceso de OBS.")
    return int(result.stdout.strip()) > 0


def doctor(exe):
    data = {"windows": sys.platform == "win32", "obs_exe_exists": Path(exe).is_file(),
            "obs_running": running(), "dependency_available": importlib.util.find_spec("obsws_python") is not None}
    try:
        cfg = load_config()
        data.update(websocket_config_exists=True, websocket_enabled=cfg["enabled"],
                    websocket_port=cfg["port"], authentication_required=cfg["auth_required"])
    except RuntimeError as exc:
        data.update(websocket_config_available=False, configuration_error=str(exc))
    return data


def launch(exe):
    if sys.platform != "win32":
        raise RuntimeError("Esta skill requiere Windows.")
    if running():
        return {"status": "already_running"}
    if not Path(exe).is_file():
        raise RuntimeError("No se encontró OBS; especifica --obs-exe.")
    cfg = load_config()
    if not cfg["enabled"]:
        raise RuntimeError("Habilita el servidor WebSocket en Herramientas de OBS.")
    env = os.environ.copy()
    env["CODEX_OBS_EXE"] = str(Path(exe).resolve())
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command",
         "$ErrorActionPreference='Stop'; Start-Process -FilePath $env:CODEX_OBS_EXE "
         "-WorkingDirectory (Split-Path -LiteralPath $env:CODEX_OBS_EXE) -WindowStyle Hidden"],
        env=env, capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise RuntimeError("No se pudo iniciar OBS.")
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if running():
            return {"status": "launched"}
        time.sleep(0.5)
    raise RuntimeError("OBS no apareció como proceso después del lanzamiento.")


def connect(auto_launch, exe):
    if sys.platform != "win32":
        raise RuntimeError("Esta skill requiere Windows.")
    try:
        import obsws_python as obs
    except ImportError:
        raise RuntimeError("Falta obsws-python; instala scripts/requirements.txt con este intérprete.") from None
    cfg = load_config()
    if not cfg["enabled"]:
        raise RuntimeError("Habilita el servidor WebSocket en Herramientas de OBS.")
    launched = False
    if not running():
        if not auto_launch:
            raise RuntimeError("OBS está cerrado. Para grabar usa start --auto-launch o launch.")
        launch(exe)
        launched = True
    for attempt in range(8 if launched else 1):
        try:
            return obs.ReqClient(host=cfg["host"], port=cfg["port"], password=cfg["password"], timeout=3)
        except Exception:
            if not launched or attempt == 7:
                # No propagar excepciones del cliente: pueden contener credenciales.
                raise RuntimeError(f"No se pudo conectar a OBS en el puerto {cfg['port']}; revisa servidor y autenticación.") from None
            time.sleep(1)


def verify_file(path):
    if not path:
        raise RuntimeError("OBS completó la operación pero no devolvió una ruta; archivo no verificado.")
    file = Path(path)
    for _ in range(20):
        if file.is_file() and file.stat().st_size > 0:
            return {"output_path": str(file.resolve()), "size_bytes": file.stat().st_size}
        time.sleep(0.25)
    raise RuntimeError("OBS completó la operación pero el archivo no existe o está vacío; archivo no verificado.")


def record_state(client):
    state = client.get_record_status()
    return {"is_recording": state.output_active, "is_paused": state.output_paused,
            "timecode": state.output_timecode, "duration_ms": state.output_duration}


def wait_state(client, active, paused=None):
    for _ in range(20):
        state = record_state(client)
        if state["is_recording"] == active and (paused is None or state["is_paused"] == paused):
            return state
        time.sleep(0.25)
    raise RuntimeError("OBS no confirmó el estado solicitado; consulta status antes de reintentar.")


def execute(client, args):
    cmd = args.command
    if cmd in ("scenes", "status"):
        scenes = client.get_scene_list()
        data = {"current_scene": scenes.current_program_scene_name,
                "scenes": [scene["sceneName"] for scene in scenes.scenes]}
        if cmd == "status":
            data.update(record_state(client), record_directory=client.get_record_directory().record_directory)
        return data
    if cmd == "set-scene":
        client.set_current_program_scene(args.name)
        actual = client.get_scene_list().current_program_scene_name
        if actual != args.name:
            raise RuntimeError("OBS no confirmó el cambio de escena.")
        return {"status": "scene_changed", "current_scene": actual}
    if cmd == "screenshot":
        source = args.name or client.get_scene_list().current_program_scene_name
        output = Path(args.output or f"obs_screenshot_{time.strftime('%Y%m%d_%H%M%S')}.png").resolve()
        if output.suffix.lower() != ".png":
            raise RuntimeError("La captura requiere una ruta .png.")
        output.parent.mkdir(parents=True, exist_ok=True)
        # La función de conveniencia exige dimensiones; el protocolo permite
        # omitirlas para conservar la resolución original de la fuente.
        client.send("SaveSourceScreenshot", {
            "sourceName": source, "imageFormat": "png", "imageFilePath": str(output)})
        return {"status": "screenshot_saved", "source": source, **verify_file(output)}
    state = record_state(client)
    if cmd == "start":
        if state["is_recording"]:
            return {"status": "already_recording", **state}
        client.start_record()
        return {"status": "recording_started", **wait_state(client, True),
                "record_directory": client.get_record_directory().record_directory}
    if not state["is_recording"]:
        return {"status": "not_recording", **state}
    if cmd == "stop":
        response = client.stop_record()
        stopped = wait_state(client, False)
        return {"status": "recording_stopped", **stopped, "last_timecode": state["timecode"],
                **verify_file(getattr(response, "output_path", None))}
    paused = cmd == "pause"
    if state["is_paused"] == paused:
        return {"status": "already_paused" if paused else "already_resumed", **state}
    (client.pause_record if paused else client.resume_record)()
    return {"status": "recording_paused" if paused else "recording_resumed",
            **wait_state(client, True, paused)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["doctor", "check", "launch", "status", "scenes", "start", "stop", "pause", "resume", "set-scene", "screenshot"])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--name")
    parser.add_argument("--output")
    parser.add_argument("--obs-exe", default=DEFAULT_EXE)
    parser.add_argument("--auto-launch", action="store_true", help="Abrir OBS si está cerrado (solo start)")
    args = parser.parse_args()
    client = None
    try:
        if args.auto_launch and args.command != "start":
            raise RuntimeError("--auto-launch solo se permite con start.")
        if args.command == "set-scene" and not args.name:
            raise RuntimeError("set-scene requiere --name.")
        if args.command == "doctor":
            result = doctor(args.obs_exe)
        elif args.command == "check":
            result = {"obs_running": running()}
        elif args.command == "launch":
            result = launch(args.obs_exe)
        else:
            client = connect(args.auto_launch, args.obs_exe)
            result = execute(client, args)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0
    except Exception as exc:
        message = str(exc) if isinstance(exc, RuntimeError) else "Falló la operación OBS; consulta status antes de reintentar."
        print(json.dumps({"status": "error", "error": message}) if args.json else message, file=sys.stderr)
        return 1
    finally:
        if client:
            try:
                client.disconnect()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
