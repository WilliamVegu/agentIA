"""Record the final Quarkus recovery without changing the authorized Spring snapshot."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / 'integration/source-snapshots.json'
manifest = json.loads(path.read_text(encoding='utf-8-sig'))
snapshot = manifest['quarkus']
prefix = 'systems/quarkus/'
tracked = subprocess.check_output(['git', 'ls-files', '-z', '--', prefix], cwd=ROOT).decode().split('\0')
snapshot['files'] = {}
snapshot['normalized_files'] = {}
for name in sorted(filter(None, tracked)):
    content = (ROOT / name).read_bytes()
    relative = name[len(prefix):]
    snapshot['files'][relative] = hashlib.sha256(content).hexdigest()
    normalized = content.replace(b'\r\n', b'\n') if b'\0' not in content else content
    snapshot['normalized_files'][relative] = hashlib.sha256(normalized).hexdigest()
snapshot['changed_from_recovered_base'] = [name for name, digest in snapshot['normalized_files'].items()
    if digest != snapshot['base_normalized_files'].get(name)]
snapshot['removed_from_recovered_base'] = sorted(set(snapshot['base_files']) - set(snapshot['files']))
snapshot['selection'] = 'Complete Studio 5d9b190 with native generators restored from c5bda02 and verified corrections'
path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print('Quarkus files:', len(snapshot['files']), 'changed:', len(snapshot['changed_from_recovered_base']))
