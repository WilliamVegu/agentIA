"""Explicit online Windows tool preparation; never runs during source generation."""
import argparse
import hashlib
import json
import shutil
import subprocess
import urllib.request
import zipfile
import tempfile
from pathlib import Path
from datetime import datetime, timezone

KIND_VERSION = '0.33.0'
KUBECTL_VERSION = '1.35.8'
TRIVY_VERSION = '0.75.0'
NODE_IMAGE = 'kindest/node:v1.35.8@sha256:07b2536e30b803ed61d1677a79df6115f798ce64c80f9e22f6ed45afd09323c0'


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def download(url, destination):
    with urllib.request.urlopen(url, timeout=90) as response, destination.open('wb') as output:
        shutil.copyfileobj(response, output)


def validate(root):
    root = Path(root).resolve()
    manifest = json.loads((root / 'TOOLS_MANIFEST.json').read_text(encoding='utf-8'))
    if manifest['formatVersion'] != 1 or manifest['platform'] != 'windows-amd64':
        raise ValueError('Unsupported tool kit')
    expected = set(manifest['files']) | {'TOOLS_MANIFEST.json'}
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if expected != actual:
        raise ValueError('Tool kit catalogue changed')
    for name, info in manifest['files'].items():
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError('Unsafe tool path')
        if path.stat().st_size != info['bytes'] or digest(path) != info['sha256']:
            raise ValueError('Tool kit integrity failed: ' + name)
    return manifest


def export_kit(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    validate(root)
    if output.exists() or output.is_relative_to(root):
        raise ValueError('Export must be a new file outside the kit')
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(root.rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(root).as_posix())
    return str(output)


def import_kit(archive_path, destination, load_node=False):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('Import destination must be new')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='agentia-tools-import-', dir=destination.parent) as temporary:
        stage = Path(temporary)
        with zipfile.ZipFile(archive_path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or len(names) > 100:
                raise ValueError('Invalid kit archive catalogue')
            for item in archive.infolist():
                name = item.filename
                target = stage / name
                if '\\' in name or ':' in name or not target.resolve().is_relative_to(stage) or name.startswith('/') or (item.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError('Unsafe archive entry')
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(item) as source, target.open('xb') as output:
                    shutil.copyfileobj(source, output)
        manifest = validate(stage)
        shutil.copytree(stage, destination)
    if load_node:
        if not manifest['kindNodeImageId']:
            raise ValueError('Kit has no prepared node image')
        subprocess.run(['docker', 'load', '-i', str(destination / 'kind-node.tar')], check=True, timeout=900)
        actual = json.loads(subprocess.check_output(['docker', 'image', 'inspect', manifest['kindNodeReference']], text=True, timeout=30))[0]['Id']
        if actual != manifest['kindNodeImageId']:
            raise ValueError('Imported node image identity differs from manifest')
    return manifest


def prepare(root, scanner_database=False, node_image=False, reuse_scanner=None):
    root = Path(root).resolve()
    if root.exists():
        raise ValueError('Preparation destination must be new; existing kit is preserved')
    root.mkdir(parents=True)
    sources = {}
    kind_url = f'https://github.com/kubernetes-sigs/kind/releases/download/v{KIND_VERSION}/kind-windows-amd64'
    download(kind_url, root / 'kind.exe')
    download(kind_url + '.sha256sum', root / 'kind.sha256sum')
    kubectl_url = f'https://dl.k8s.io/release/v{KUBECTL_VERSION}/bin/windows/amd64/kubectl.exe'
    download(kubectl_url, root / 'kubectl.exe')
    download(kubectl_url + '.sha256', root / 'kubectl.sha256')
    archive_name = f'trivy_{TRIVY_VERSION}_windows-64bit.zip'
    trivy_url = f'https://github.com/aquasecurity/trivy/releases/download/v{TRIVY_VERSION}/'
    if reuse_scanner:
        reuse_scanner = Path(reuse_scanner).resolve()
        prior = validate(reuse_scanner)
        if TRIVY_VERSION not in prior['versions']['trivy']:
            raise ValueError('Reusable Trivy version differs')
        for filename in [archive_name, 'trivy-checksums.txt']:
            shutil.copyfile(reuse_scanner / filename, root / filename)
    else:
        download(trivy_url + archive_name, root / archive_name)
        download(trivy_url + f'trivy_{TRIVY_VERSION}_checksums.txt', root / 'trivy-checksums.txt')
    for binary, checksum in [('kind.exe', 'kind.sha256sum'), ('kubectl.exe', 'kubectl.sha256')]:
        expected = (root / checksum).read_text().split()[0].lower()
        if digest(root / binary) != expected:
            raise ValueError('Official checksum mismatch: ' + binary)
    lines = (root / 'trivy-checksums.txt').read_text().splitlines()
    matching = [line.split()[0] for line in lines if line.split()[-1] == archive_name]
    if len(matching) != 1 or digest(root / archive_name) != matching[0]:
        raise ValueError('Official Trivy checksum mismatch')
    with zipfile.ZipFile(root / archive_name) as archive:
        # Extract the executable only, never arbitrary paths/symlinks from an archive.
        matches = [item for item in archive.infolist() if item.filename == 'trivy.exe']
        if len(matches) != 1:
            raise ValueError('Trivy executable missing or duplicated')
        (root / 'trivy.exe').write_bytes(archive.read(matches[0]))
    versions = {}
    for name, arguments in [('kind', ['version']), ('kubectl', ['version', '--client', '-o', 'json']), ('trivy', ['--version'])]:
        versions[name] = subprocess.check_output([str(root / (name + '.exe')), *arguments], text=True, timeout=30).strip()
    if 'v' + KIND_VERSION not in versions['kind'] or KUBECTL_VERSION not in versions['kubectl'] or TRIVY_VERSION not in versions['trivy']:
        raise ValueError('Installed version differs from frozen profile')
    if scanner_database:
        cache = root / 'trivy-cache'
        if reuse_scanner and prior['scannerDatabasePrepared']:
            shutil.copytree(reuse_scanner / 'trivy-cache', cache)
        else:
            for flag in ['--download-db-only', '--download-java-db-only']:
                subprocess.run([str(root / 'trivy.exe'), 'image', flag, '--cache-dir', str(cache)], check=True, timeout=900)
    image = None
    if node_image:
        subprocess.run(['docker', 'pull', NODE_IMAGE], check=True, timeout=900)
        image = json.loads(subprocess.check_output(['docker', 'image', 'inspect', NODE_IMAGE], text=True, timeout=30))[0]['Id']
        subprocess.run(['docker', 'save', '-o', str(root / 'kind-node.tar'), NODE_IMAGE], check=True, timeout=900)
    sources.update(kind=kind_url, kubectl=kubectl_url, trivy=trivy_url + archive_name)
    manifest = {'formatVersion': 1, 'platform': 'windows-amd64', 'preparedAt': datetime.now(timezone.utc).isoformat(),
                'versions': versions, 'sources': sources, 'kindNodeReference': NODE_IMAGE,
                'kindNodeImageId': image, 'scannerDatabasePrepared': scanner_database,
                'files': {p.relative_to(root).as_posix(): {'sha256': digest(p),
                    'bytes': p.stat().st_size} for p in sorted(root.rglob('*')) if p.is_file()}}
    (root / 'TOOLS_MANIFEST.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return validate(root)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('destination', type=Path)
    parser.add_argument('--scanner-database', action='store_true')
    parser.add_argument('--kind-image', action='store_true')
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--export', type=Path)
    parser.add_argument('--import-from', type=Path)
    parser.add_argument('--load-node', action='store_true')
    parser.add_argument('--reuse-scanner-kit', type=Path)
    args = parser.parse_args()
    if args.import_from:
        result = import_kit(args.import_from, args.destination, args.load_node)
    elif args.export:
        result = export_kit(args.destination, args.export)
    else:
        result = validate(args.destination) if args.validate_only else prepare(args.destination, args.scanner_database, args.kind_image, args.reuse_scanner_kit)
    print(json.dumps(result, indent=2))
