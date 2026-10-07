"""Download checksum-verified portable Java/Maven for local build validation."""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen
import zipfile
import truststore

truststore.inject_into_ssl()
ROOT = Path(__file__).resolve().parents[1] / '.run/tools'
ROOT.mkdir(parents=True, exist_ok=True)

def read(url):
    with urlopen(url, timeout=60) as response:
        return response.read()

def package(url, name, digest, algorithm):
    archive = ROOT / name
    if not archive.exists() or hashlib.new(algorithm, archive.read_bytes()).hexdigest() != digest:
        print('Downloading:', name, flush=True)
        with urlopen(url, timeout=180) as response, archive.open('wb') as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
    if hashlib.new(algorithm, archive.read_bytes()).hexdigest() != digest:
        raise RuntimeError('Checksum mismatch: ' + name)
    with zipfile.ZipFile(archive) as files:
        top = files.namelist()[0].split('/')[0]
        for entry in files.namelist():
            target = (ROOT / entry).resolve()
            if not target.is_relative_to(ROOT.resolve()):
                raise RuntimeError('Archive path leaves tools directory')
        if not (ROOT / top / 'bin').exists():
            files.extractall(ROOT)
    return ROOT / top

jdk_url = 'https://aka.ms/download-jdk/microsoft-jdk-21.0.12.1-windows-x64.zip'
jdk_sha = read(jdk_url + '.sha256sum.txt').decode().strip().split()[0]
java_root = package(jdk_url, 'microsoft-jdk-21.0.12.1-windows-x64.zip', jdk_sha, 'sha256')
maven_url = 'https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/3.9.11/apache-maven-3.9.11-bin.zip'
maven_sha = read(maven_url + '.sha512').decode().strip().split()[0]
maven_root = package(maven_url, 'apache-maven-3.9.11-bin.zip', maven_sha, 'sha512')
result = {'java_home': str(java_root), 'maven_home': str(maven_root), 'java_source': jdk_url, 'maven_source': maven_url}
(ROOT / 'paths.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
