"""Inspect reachable Git history without modifying any source checkout."""
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / 'validation' / 'quarkus-history.json'

def git(*args, input=None):
    return subprocess.check_output(['git', '-C', str(REPO), *args], input=input, text=True, encoding='utf-8').strip()

branch = 'origin/Quarkus_refact_2'
commits = git('rev-list', branch).splitlines()
paths = [
    'backend/app/api/routes_quarkus_factory.py',
    'backend/app/models/quarkus_factory.py',
    'backend/app/services/quarkus_factory/factory_orchestrator.py',
    'frontend/src/context/QuarkusContext.tsx',
    'frontend/src/views/quarkus/QuarkusFactoryStudioView.tsx',
]
queries = [f'{commit}:{path}' for commit in commits for path in paths]
objects = git('cat-file', '--batch-check', input='\n'.join(queries) + '\n').splitlines()
present = [line for line in objects if not line.endswith(' missing')]
quarkus_names = []
for commit in commits:
    names = git('ls-tree', '-r', '--name-only', commit).splitlines()
    matches = [name for name in names if 'quarkus' in name.lower()]
    if matches:
        quarkus_names.append({'commit': commit, 'paths': matches})

merge = git('rev-parse', '19627d8')
parents = git('rev-list', '--parents', '-n', '1', merge).split()[1:]
snapshots = {}
for ref in [branch, *parents, '10c10ae', 'origin/Quarkus_refact', 'origin/Unificado']:
    commit = git('rev-parse', ref)
    names = git('ls-tree', '-r', '--name-only', ref).splitlines()
    snapshots[ref] = {'commit': commit, 'metadata': git('show', '-s', '--format=%ad %s', '--date=iso-strict', ref),
        'quarkus_paths': [name for name in names if 'quarkus' in name.lower()]}

ancestry = {}
for ref in ['10c10ae', 'origin/Quarkus_refact', '83dc944', 'e72e30c', 'origin/Unificado']:
    result = subprocess.run(['git', '-C', str(REPO), 'merge-base', '--is-ancestor', ref, branch])
    if result.returncode not in (0, 1):
        raise RuntimeError(f'Ancestry query failed for {ref}')
    ancestry[ref] = result.returncode == 0

report = {'branch': branch, 'head': git('rev-parse', branch), 'reachable_commits': len(commits),
    'factory_paths_checked': paths, 'factory_path_occurrences': present, 'commits_with_quarkus_filenames': quarkus_names,
    'first_parent_history': git('log', '--first-parent', '--format=%H %P %ad %s', '--date=iso-strict', branch).splitlines(),
    'merge': {'commit': merge, 'parents': parents, 'description': git('show', '-s', '--format=fuller', merge)},
    'snapshots': snapshots, 'quarkus_commits_are_ancestors': ancestry,
    'remote_tracking_reflog': git('reflog', 'show', '--date=iso-strict', branch).splitlines(),
    'original_factory_source_delta': git('diff', '--stat', '10c10ae', 'origin/Quarkus_refact', '--', 'backend', 'frontend')}
OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({key: value for key, value in report.items() if key not in ('snapshots', 'first_parent_history')}, indent=2, ensure_ascii=False))
print('snapshot_quarkus_file_counts:', {ref: len(info['quarkus_paths']) for ref, info in snapshots.items()})
