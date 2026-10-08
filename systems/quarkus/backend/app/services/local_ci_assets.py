"""Self-contained local audit runner and opt-in Windows CI wrappers."""

AUDIT_SCRIPT = r'''"""Offline source checks; external execution requires explicit --docker."""
import argparse
import json
import re
import subprocess
import tempfile
import shutil
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--docker', action='store_true')
    parser.add_argument('--trivy', type=Path)
    parser.add_argument('--trivy-cache', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    findings = []
    rules = {
        'PRIVATE_KEY': r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
        'AWS_ACCESS_KEY': r'\bAKIA[0-9A-Z]{16}\b',
        'OPENAI_KEY': r'\bsk-(?:proj-)?[a-zA-Z0-9_-]{30,}',
        'SQL_CONCATENATION': r'(?:createNativeQuery|executeQuery|executeUpdate)\s*\([^;\n]*\+',
        'PROCESS_EXECUTION': r'Runtime\.getRuntime\(\)\.exec\(|new\s+ProcessBuilder\(',
        'INSECURE_RANDOM': r'new\s+Random\(\)',
    }
    excluded = {'.git', '.agentia-runtime', '.run', 'target', 'build', '.gradle', '.m2', 'node_modules'}
    for path in sorted(root.rglob('*')):
        if not path.is_file() or any(p in excluded for p in path.relative_to(root).parts):
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError('Linked input is not accepted')
        if path == Path(__file__).resolve() or path.name.startswith('.env'):
            continue
        if path.suffix not in {'.java', '.sql', '.xml', '.properties', '.yaml', '.yml', '.json', '.gradle', '.kts'}:
            continue
        text = path.read_text(encoding='utf-8')
        for rule, pattern in rules.items():
            for match in re.finditer(pattern, text):
                findings.append({'rule': rule, 'file': path.relative_to(root).as_posix(),
                                 'line': text.count('\n', 0, match.start()) + 1})
    report = {'formatVersion': 1, 'staticAudit': 'FAILED' if findings else 'PASSED',
              'auditScope': list(rules), 'findings': findings, 'tests': 'NOT_EXECUTED',
              'imageVulnerabilities': 'NOT_EXECUTED', 'runtime': 'NOT_EXECUTED'}
    output = root / '.agentia-runtime' / 'local-ci-result.json'
    output.parent.mkdir(exist_ok=True)
    def save():
        output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    save()
    if findings:
        return 1
    if not args.docker:
        print('Static audit passed; tests, container and CVE scan NOT_EXECUTED (source mode).')
        return 0
    token = uuid.uuid4().hex
    tag = 'agentia-ci:' + token
    name = 'agentia-ci-' + token
    container = None
    image_id = None
    def run(command):
        return subprocess.run(command, check=True, text=True, encoding='utf-8', errors='replace', capture_output=True, timeout=900).stdout
    try:
        # Check all stages before building: a missing FROM must not trigger a pull.
        for line in (root / 'Dockerfile').read_text(encoding='utf-8').splitlines():
            if line.startswith('FROM '):
                run(['docker', 'image', 'inspect', line.split()[1]])
        # Tests execute inside the prepared builder, with RUN --network=none.
        build = run(['docker', 'build', '--network=none', '--pull=false', '--target', 'build',
                     '--label', 'io.agentia.ci=' + token, '-t', tag, str(root)])
        image_id = run(['docker', 'image', 'inspect', tag, '--format', '{{.Id}}']).strip()
        container = run(['docker', 'create', '--name', name, '--network', 'none',
                         '--label', 'io.agentia.ci=' + token, tag, 'true']).strip()
        config = json.loads((root / 'ASSET_CONFIGURATION.json').read_text(encoding='utf-8'))
        build_dir = config['buildDirectory']
        if build_dir not in {'.', 'bootstrap'}:
            raise ValueError('Unsupported build directory')
        report_path = '/workspace' + ('/bootstrap' if build_dir == 'bootstrap' else '')
        report_path += '/build/test-results/test' if config['buildTool'] == 'gradle' else '/target/surefire-reports'
        with tempfile.TemporaryDirectory(prefix='agentia-ci-') as temporary:
            run(['docker', 'cp', container + ':' + report_path, temporary])
            suites = [ET.parse(p).getroot() for p in Path(temporary).rglob('TEST-*.xml')]
            total = sum(int(s.get('tests', '0')) for s in suites)
            failures = sum(int(s.get('failures', '0')) + int(s.get('errors', '0')) + int(s.get('skipped', '0')) for s in suites)
            if total == 0 or failures:
                raise ValueError('No complete passing JUnit suite: total=%s unsuccessful=%s' % (total, failures))
            report.update(tests='PASSED', totalTests=total, unsuccessfulTests=failures, imageId=image_id)
        artifact = output.parent / 'ci-build'
        artifact.mkdir(exist_ok=True)
        run(['docker', 'cp', container + ':/quarkus-app', str(artifact / 'quarkus-app')])
        if args.trivy:
            if not args.trivy.is_file() or not args.trivy_cache or not args.trivy_cache.is_dir():
                raise ValueError('Explicit prepared Trivy executable/cache required')
            report['scannerMetadata'] = json.loads((args.trivy_cache / 'db' / 'metadata.json').read_text(encoding='utf-8'))
            scan_file = output.with_name('trivy-result.json')
            report['dependencyVulnerabilities'] = 'FAILED'
            with tempfile.TemporaryDirectory(prefix='agentia-scanner-cache-') as private:
                private_cache = Path(private) / 'cache'
                shutil.copytree(args.trivy_cache.resolve(), private_cache)
                run([str(args.trivy.resolve()), 'fs', '--offline-scan', '--skip-version-check', '--skip-db-update',
                     '--skip-java-db-update', '--cache-dir', str(private_cache),
                     '--scanners', 'vuln', '--severity', 'HIGH,CRITICAL', '--exit-code', '1',
                     '--format', 'json', '--output', str(scan_file), str(artifact)])
            report['dependencyVulnerabilities'] = 'PASSED'
        report['execution'] = 'PASSED'
        save()
        return 0
    except Exception as exc:
        report.update(tests='FAILED' if report['tests'] != 'PASSED' else report['tests'],
                      execution='FAILED', cause=type(exc).__name__)
        save()
        print('Local execution failed; detailed commands do not expose credentials.')
        return 1
    finally:
        # Remove only resources whose creation identity is still confirmed.
        if container:
            label = run(['docker', 'inspect', container, '--format', '{{index .Config.Labels "io.agentia.ci"}}']).strip()
            if label != token:
                raise ValueError('Container identity changed; cleanup refused')
            run(['docker', 'rm', '-f', container])
        if image_id:
            label = run(['docker', 'image', 'inspect', image_id, '--format', '{{index .Config.Labels "io.agentia.ci"}}']).strip()
            if label != token:
                raise ValueError('Image identity changed; cleanup refused')
            run(['docker', 'image', 'rm', image_id])
        report['cleanup'] = 'CONFIRMED'
        save()

if __name__ == '__main__':
    raise SystemExit(main())
'''


def github(service_name):
    return f'''name: "Local verification - {service_name}"
on:
  workflow_dispatch:
    inputs:
      docker:
        type: boolean
        default: false
        description: Execute prepared offline Docker tests
permissions:
  contents: read
jobs:
  local-verification:
    runs-on: [self-hosted, Windows]
    steps:
      - uses: actions/checkout@v4
      - name: Static source audit
        run: python local-ci.py
      - name: Prepared offline build and real JUnit reports
        if: inputs.docker
        run: python local-ci.py --docker
# Runner provisioning and checkout need initial connectivity. No hosted runner,
# registry publishing, scanner downloads or remote execution are certified here.
'''


def gitlab(service_name):
    return f'''# Optional local Windows shell runner; GitLab.com execution is deferred.
stages: [verify]
local-verification:
  stage: verify
  tags: [windows, agentia-local]
  rules:
    - if: '$CI_PIPELINE_SOURCE == "web"'
      when: manual
    - when: never
  script:
    - python local-ci.py
  artifacts:
    when: always
    paths: [.agentia-runtime/local-ci-result.json]
# To run Docker explicitly on a prepared runner: python local-ci.py --docker
# {service_name}: source checks do not assert executed tests or CVE approval.
'''
