"""Verify historical sources and explicit authorized revisions without rewriting history."""
import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def accessible(path):
    return Path('\\\\?\\' + str(path.resolve())) if os.name == 'nt' else path


def _hashes(content):
    normalized=content.replace(b'\r\n',b'\n') if b'\0' not in content else content
    return hashlib.sha256(content).hexdigest(),hashlib.sha256(normalized).hexdigest()


def _relative(value):
    return isinstance(value,str) and bool(value) and not Path(value).is_absolute() and ':' not in value and '\\' not in value and '..' not in Path(value).parts


def check_sources(root=ROOT):
    root=Path(root).resolve()
    baseline=(root/'integration/source-snapshots.json').read_bytes()
    historical=json.loads(baseline)
    errors=[];authorized={}
    revision_file=root/'integration/source-revisions.json'
    if revision_file.is_file():
        try:
            revisions=json.loads(revision_file.read_text(encoding='utf-8'))
            if revisions.get('formatVersion')!=1 or revisions.get('baselineSha256') not in {hashlib.sha256(value).hexdigest() for value in (baseline, baseline.replace(b'\r\n', b'\n'), baseline.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))} or not re.fullmatch('[a-f0-9]{40}',revisions.get('baseCommit','')):
                raise ValueError('identidad del baseline o versión inválida')
            for revision in revisions['revisions']:
                name=revision['studio'];relative=revision['path'];key=(name,relative)
                snapshot=historical.get(name)
                if not snapshot or not _relative(relative) or key in authorized or revision['beforeSha256']!=snapshot['files'].get(relative):
                    raise ValueError('revisión duplicada, ruta o hash anterior inválido')
                if not revision.get('tasks') or any(not re.fullmatch('T[0-9]{3}',task) for task in revision['tasks']):
                    raise ValueError('revisión sin tareas trazables')
                if not revision.get('evidence') or any(not _relative(path) or not path.startswith('integration/validation/reliability/') or not (root/path).is_file() for path in revision['evidence']):
                    raise ValueError('revisión sin evidencia accesible')
                if any(not re.fullmatch('[a-f0-9]{64}',revision.get(field,'')) for field in ['afterSha256','afterNormalizedSha256']):
                    raise ValueError('hash posterior inválido')
                authorized[key]=revision
        except (ValueError,KeyError,TypeError) as error:
            errors.append('Manifest de revisiones inválido: '+str(error))
            authorized={}
    for name,snapshot in historical.items():
        studio_root=root/snapshot['root']
        if not studio_root.resolve().is_relative_to(root):
            errors.append(name+': raíz fuera del proyecto');continue
        for relative,expected in snapshot['files'].items():
            if not _relative(relative):
                errors.append(name+': ruta histórica inválida');continue
            path=accessible(studio_root/relative)
            if not path.is_file() or not path.resolve().is_relative_to(accessible(root).resolve()):
                errors.append(f'{name}: falta o está enlazado {relative}');continue
            raw,normalized=_hashes(path.read_bytes())
            revision=authorized.get((name,relative))
            if revision:
                valid=raw==revision['afterSha256'] or normalized==revision['afterNormalizedSha256']
            else:
                valid=raw==expected or normalized==snapshot.get('normalized_files',{}).get(relative)
            if not valid: errors.append(f'{name}: cambio no autorizado {relative}')
    return errors


def verify():
    errors=check_sources()
    for error in errors: print(error)
    if errors: raise SystemExit(1)
    print('Snapshots históricos intactos; fuentes verificadas contra hashes originales y revisiones autorizadas explícitas.')


if __name__ == '__main__': verify()
