from pathlib import Path
import json
import subprocess
import imageio_ffmpeg

root = Path(__file__).resolve().parent
raw = Path('C:/Users/willi/Videos/2026-10-05 15-22-18.mp4')
end = Path('C:/Users/willi/Videos/2026-10-05 15-51-59.mp4')
diagrams = Path('C:/Users/willi/Videos/2026-10-05 15-54-40.mp4')
cuts = [(raw, 0, 40), (end, 38, 46), (diagrams, 0, 18.5),
        (end, 17.75, 31.35), (raw, 139.5, 151.4),
        (raw, 171.5, 191.5), (raw, 210, 215), (end, 0, 17.7)]
parts = root / 'brief-parts'
parts.mkdir(exist_ok=True)
ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
def run(args):
    r = subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-nostdin', *args],
                       capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-2500:])
for i, (source, start, stop) in enumerate(cuts):
    run(['-ss', str(start), '-i', str(source), '-t', str(stop-start),
         '-vf', 'crop=1900:826:20:184', '-an', '-r', '30',
         '-c:v', 'libx264', '-preset', 'fast', '-crf', '21', '-pix_fmt', 'yuv420p',
         '-y', str(parts / f'{i:02}.mp4')])
manifest = parts / 'concat.txt'
manifest.write_text(''.join(f"file '{i:02}.mp4'\n" for i in range(len(cuts))), encoding='utf-8')
output = root / 'recorrido-docker-breve-nuevo.mp4'
run(['-f', 'concat', '-safe', '0', '-i', str(manifest), '-c', 'copy',
     '-movflags', '+faststart', '-metadata',
     'comment=Recorrido real con OBS. Edicion breve: esperas omitidas; vistas de resultados agrupadas. Se corrigio una migracion de fechas antes del despliegue final.',
     '-y', str(output)])
run(['-i', str(output), '-f', 'null', '-'])
assert 0 < output.stat().st_size < 104857600
info = {'path': str(output), 'bytes': output.stat().st_size,
        'expectedDurationSeconds': sum(stop-start for _,start,stop in cuts),
        'cuts': [{'source':str(s),'start':a,'end':b} for s,a,b in cuts]}
(root/'recorrido-docker-breve-manifest.json').write_text(json.dumps(info, indent=2), encoding='utf-8')
print(json.dumps(info, indent=2))
