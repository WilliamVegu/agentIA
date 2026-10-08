"""Explicit additive capture; historical corpus and baseline remain untouched.

Run separately with the studio's pinned interpreter and PYTHONPATH. This utility
is never called by a test or CI to rewrite expected output automatically.
"""
import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from app.orchestrator.stages.runner import STAGE_ORDER, run_stages


def digest(data):
    return hashlib.sha256(data).hexdigest()


def capture(studio):
    repository=Path(__file__).resolve().parents[1]
    root=repository if studio=='springboot' else repository/'systems/quarkus'
    historical=root/'reports/baselines/011-pre-migration-generation-baseline.json'
    inputs=root/'backend/tests/fixtures/reliability_blueprints'
    baseline={'formatVersion':1,'studio':studio,'baseCommit':'cd50688c8188b47ba789ec30683a50eabc7bd593',
        'historicalBaselineSha256':digest(historical.read_bytes()),'taskIds':['T031','T032','T033','T034','T035','T059'],
        'reason':'Native schema migrations, exact IDs/columns and executable validation annotations replace defective output. Original incomplete annotations remain rejected.',
        'evidence':['integration/validation/reliability/generated-ci-'+('spring' if studio=='springboot' else 'quarkus')+'.xml'],
        'per_blueprint':[]}
    with TemporaryDirectory(prefix='generation-revisions-',dir=repository/'.runtime/reliability/tmp') as temporary:
        for source in sorted(inputs.glob('*.json')):
            blueprint=json.loads(source.read_text(encoding='utf-8'))
            original=root/'backend/tests/fixtures/baseline_blueprints'/source.name
            workspace=Path(temporary)/source.stem;workspace.mkdir()
            state=run_stages({'session_id':'capture-'+source.stem,'blueprint':blueprint,'workspace_path':str(workspace),
                'generated_files':{},'logs':[],'generation_mode':'DETERMINISTIC'},stages=STAGE_ORDER)
            assert state.get('status')!='BLOCKED'
            assert state['generation_journal']['total_requests']==0
            files={path.relative_to(workspace).as_posix():path.read_text(encoding='utf-8') for path in workspace.rglob('*') if path.is_file()}
            baseline['per_blueprint'].append({'blueprint_id':source.stem,'terminal_status':'COMPLETED',
                'historicalInputSha256':digest(original.read_bytes()),'inputSha256':digest(source.read_bytes()),
                'artifact_digests':{name:digest(content.encode()) for name,content in sorted(files.items())},
                'comparison_subset_content':{name:{'content':content,'sha256':digest(content.encode())} for name,content in sorted(files.items())}})
    output=root/'backend/tests/fixtures/reliability_generation_revisions.json'
    output.write_text(json.dumps(baseline,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('Captured',len(baseline['per_blueprint']),'explicit generation revisions for',studio)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--studio',required=True,choices=['springboot','quarkus'])
    capture(parser.parse_args().studio)
