import importlib.util
import json

spec = importlib.util.spec_from_file_location('obs_control', r'C:\Users\willi\.codex\skills\obs-screen-recorder\scripts\obs_control.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
client = helper.connect(False, helper.DEFAULT_EXE)
try:
    print(json.dumps(client.get_scene_item_list('Escena').scene_items, indent=2))
    for item in client.get_input_list().inputs:
        if item['inputKind'] in ('window_capture', 'monitor_capture'):
            print(json.dumps({'input': item, 'settings': client.get_input_settings(item['inputName']).input_settings}, indent=2))
finally:
    client.disconnect()
