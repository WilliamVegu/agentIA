"""Generate offline sources from a recovered commit; never claim a Java build."""
import json
import os
from pathlib import Path
import subprocess
import sys

root = Path(sys.argv[1]).resolve()
label = sys.argv[2]
out = Path(__file__).resolve().parent / 'validation' / f'quarkus-recovered-{label}-generation.json'
os.chdir(root)
os.environ['DATABASE_URL'] = 'sqlite://'
os.environ['WORKSPACE_DIR'] = str(root / '.run/generation/workspaces')
os.environ['COST_STORE_PATH'] = str(root / '.run/generation/cost.db')
os.environ['MLFLOW_TRACKING_URI'] = (root / '.run/generation/mlruns').as_uri()
os.environ['ALLOW_OFFLINE_MOCK'] = 'true'
os.environ['DOCKER_ENABLED'] = 'false'
sys.path.insert(0, str(root / 'backend'))

blueprint = {'serviceName': 'notes-audit', 'packageName': 'com.example.notes', 'basePort': 8081,
    'databaseMode': 'PostgreSQL', 'entities': [{'name': 'Note', 'tableName': 'notes', 'attributes': [
        {'name': 'id', 'type': 'Long', 'nullable': False, 'isPrimaryKey': True, 'validationRules': []},
        {'name': 'body', 'type': 'String', 'nullable': True, 'isPrimaryKey': False, 'validationRules': []}]}],
    'userStories': [{'id': 'US-1', 'priority': 'P3', 'role': 'user', 'intent': 'save a note', 'benefit': 'retain the note',
        'scenarios': [{'scenarioId': 'AC-1.1', 'given': 'a note', 'when': 'save is requested', 'then': 'the note is stored'}]}]}
workspace = root / '.run/generation/generated-notes'
workspace.mkdir(parents=True, exist_ok=True)
state = {'session_id': 'historical-generation-audit', 'blueprint': blueprint, 'workspace_path': str(workspace),
    'generated_files': {}, 'logs': [], 'generation_mode': 'DETERMINISTIC'}
import_error = None
instructions = None
try:
    from app.orchestrator.stages.instructions import load_instruction_set
    from app.orchestrator.stages.runner import STAGE_ORDER, run_stages
    instructions = load_instruction_set()
    result = run_stages(state, stages=STAGE_ORDER)
except ImportError as exc:
    import_error = str(exc)
    from app.orchestrator.nodes.scaffolder_node import scaffolder_node
    result = scaffolder_node(state)
files = result['generated_files']
imports = {path: [line.strip() for line in text.splitlines() if 'import org.springframework' in line]
    for path, text in files.items() if path.endswith('.java') and 'import org.springframework' in text}
report = {'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'stage_import_error': import_error,
    'execution_path': 'legacy_scaffolder_node' if import_error else 'five_stage_execution_boundary',
    'generation_mode': result.get('generation_journal', {}).get('generation_mode'),
    'file_count': len(files), 'pom_has_quarkus_bom': 'quarkus-bom' in files.get('pom.xml', ''),
    'pom_has_spring_boot_parent': 'spring-boot-starter-parent' in files.get('pom.xml', ''),
    'spring_java_imports': imports, 'instructions_require_quarkus': 'Quarkus' in instructions.for_stage('SCAFFOLDER') if instructions else None,
    'instruction_revision': instructions.revision if instructions else None, 'compiled_or_executed_java_tests': False,
    'pom_xml': files.get('pom.xml'), 'generated_paths': sorted(files)}
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({key: value for key, value in report.items() if key not in ('pom_xml', 'generated_paths')}, ensure_ascii=False, indent=2))
