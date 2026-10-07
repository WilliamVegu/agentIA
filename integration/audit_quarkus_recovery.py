"""Inspect locally retained unreachable commits and differences in the candidate."""
import json
import subprocess
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
def git(*args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True, encoding='utf-8').strip()

lost = [line.split()[-1] for line in git('fsck', '--no-reflogs', '--unreachable').splitlines() if line.startswith('unreachable commit ')]
commits = []
for commit in lost:
    paths = git('ls-tree', '-r', '--name-only', commit).splitlines()
    commits.append({'commit': commit, 'metadata': git('show', '-s', '--format=%ad %s', '--date=iso-strict', commit),
        'quarkus_paths': [path for path in paths if 'quarkus' in path.lower()]})
unchanged = {}
for service in ('analyst_agent.py', 'architect_agent.py', 'developer_qa_service.py', 'scaffolder_service.py'):
    path = 'backend/app/services/quarkus_factory/' + service
    unchanged[service] = not git('diff', 'origin/Quarkus_refact', 'origin/Unificado', '--', path)
report = {'unreachable_commits': commits, 'candidate_unchanged_services': unchanged,
    'factory_marker_history_in_quarkus_refact_2': git('log', 'origin/Quarkus_refact_2', '--format=%h %s', '-G', r'io\.quarkus|quarkus-bom|/quarkus/orders|QuarkusFactory', '--', 'backend', 'frontend'),
    'candidate_services_delta': git('diff', 'origin/Quarkus_refact', 'origin/Unificado', '--', 'backend/app/services/quarkus_factory'),
    'delivery_correction_commit': git('log', 'origin/Unificado', '--format=%h %ad %s', '--date=iso-strict', '--', 'backend/app/services/quarkus_factory/documenter_devops_service.py')}
out = Path(__file__).resolve().parent / 'validation' / 'quarkus-history-recovery.json'
# Keep the initial discovery: after recovery branches are created, fsck correctly
# stops listing the preserved commits as unreachable.
if out.exists():
    out = out.with_name('quarkus-history-recovery-current.json')
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({key: value for key, value in report.items() if key != 'candidate_services_delta'}, ensure_ascii=False, indent=2))
