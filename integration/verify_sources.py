"""Verify preserved source snapshots; runtime files are outside this manifest."""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def accessible(path):
    # Historical report names exceed MAX_PATH after nesting on Windows.
    return Path('\\\\?\\' + str(path.resolve())) if os.name == 'nt' else path


def verify():
    manifest = json.loads((ROOT / 'integration/source-snapshots.json').read_text(encoding='utf-8'))
    errors = []
    for name, snapshot in manifest.items():
        checked = 0
        for relative, expected in snapshot['files'].items():
            path = accessible(ROOT / snapshot['root'] / relative)
            if not path.is_file():
                errors.append(f'{name}: falta {relative}')
                continue
            content = path.read_bytes()
            raw = hashlib.sha256(content).hexdigest()
            normalized = hashlib.sha256(content.replace(b'\r\n', b'\n') if b'\0' not in content else content).hexdigest()
            if raw != expected and normalized != snapshot['normalized_files'].get(relative):
                errors.append(f'{name}: cambió {relative}')
            checked += 1
        print(f'{name}: {checked} archivos comprobados')
    for error in errors:
        print(error)
    if errors:
        raise SystemExit(1)
    print('Ambos sistemas conservan sus fuentes originales (se permiten finales de línea del checkout).')


if __name__ == '__main__':
    verify()
