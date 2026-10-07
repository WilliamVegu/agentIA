from pathlib import Path
import json
import subprocess
import imageio_ffmpeg

root = Path(__file__).resolve().parent
source = root / 'recorrido-docker-completo.mp4'
output = root / 'drive-parts'
output.mkdir(exist_ok=True)
result = subprocess.run([
    imageio_ffmpeg.get_ffmpeg_exe(), '-hide_banner', '-nostdin',
    '-i', str(source), '-map', '0', '-c', 'copy', '-f', 'segment',
    '-segment_time', '600', '-reset_timestamps', '1',
    '-segment_format_options', 'movflags=+faststart',
    str(output / 'recorrido-docker-parte-%02d.mp4'),
], capture_output=True, text=True)
if result.returncode:
    raise RuntimeError(result.stderr[-3000:])
parts = sorted(output.glob('*.mp4'))
assert parts and all(p.stat().st_size < 104857600 for p in parts)
manifest = [{'name': p.name, 'path': str(p), 'bytes': p.stat().st_size} for p in parts]
(output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(json.dumps(manifest, indent=2))
