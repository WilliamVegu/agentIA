"""Graba una animación local de pedido con una escena temporal en OBS."""
import importlib.util
import json
from pathlib import Path
import time
import uuid

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('obs_control', r'C:\Users\willi\.codex\skills\obs-screen-recorder\scripts\obs_control.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
client = helper.connect(False, helper.DEFAULT_EXE)
suffix = uuid.uuid4().hex[:8]
scene = 'Codex pedido demo ' + suffix
source = 'Codex pedido browser ' + suffix
original = client.get_scene_list().current_program_scene_name
created_scene = created_source = owned_recording = False
report = {}
try:
    if helper.record_state(client)['is_recording']:
        raise RuntimeError('Hay una grabación activa; no se modificará.')
    client.create_scene(scene)
    created_scene = True
    client.create_input(scene, source, 'browser_source', {
        'is_local_file': True, 'local_file': str(HERE / 'pedido-demo.html'),
        'width': 1920, 'height': 1080, 'shutdown': True, 'restart_when_active': True,
        'fps': 30}, True)
    created_source = True
    client.set_current_program_scene(scene)
    time.sleep(1)
    client.start_record()
    owned_recording = True
    report['started'] = helper.wait_state(client, True)
    time.sleep(7)
    client.send('SaveSourceScreenshot', {'sourceName': scene, 'imageFormat': 'png',
                                        'imageFilePath': str(HERE / 'pedido-writing.png')})
    report['writing_capture'] = helper.verify_file(HERE / 'pedido-writing.png')
    time.sleep(9)
    client.send('SaveSourceScreenshot', {'sourceName': scene, 'imageFormat': 'png',
                                        'imageFilePath': str(HERE / 'pedido-confirmed.png')})
    report['confirmed_capture'] = helper.verify_file(HERE / 'pedido-confirmed.png')
    time.sleep(3)
    before_stop = helper.record_state(client)
    result = client.stop_record()
    helper.wait_state(client, False)
    owned_recording = False
    report['video'] = {**helper.verify_file(result.output_path), 'duration_ms': before_stop['duration_ms']}
finally:
    try:
        if owned_recording:
            result = client.stop_record()
            report['cleanup_video'] = helper.verify_file(result.output_path)
    finally:
        try:
            client.set_current_program_scene(original)
        finally:
            try:
                if created_source:
                    client.remove_input(source)
                if created_scene:
                    client.remove_scene(scene)
            finally:
                client.disconnect()
                (HERE / 'pedido-demo-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
