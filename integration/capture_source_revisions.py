"""Record exact authorized source revisions; the historical manifest stays read-only."""
from __future__ import annotations
import argparse, hashlib, json, subprocess
from pathlib import Path
from integration.verify_sources import ROOT, _hashes, accessible, check_sources
from integration.reliability_smoke import report_counts


def tasks_for(path):
    if 'frontend/' in path:
        return ['T045','T046','T047','T048','T049','T050','T054']
    if any(name in path for name in ('requirements','blueprint','draft','artifact')):
        return ['T013','T017','T018','T019','T020','T021','T022']
    if any(name in path for name in ('docker','devops','runtime','local_','lifecycle_scripts','standalone')):
        return ['T014','T038','T039','T040','T041','T042','T043','T044']
    if any(name in path for name in ('domain','model_sql','deterministic','scaffolder','generation')):
        return ['T031','T032','T033','T034','T035','T036','T037','T059']
    if 'git' in path or 'publish' in path:
        return ['T010','T015','T050']
    if any(name in path for name in ('security','export','verification','snapshot','repair','tests')):
        return ['T013','T023','T024','T026','T028','T029','T030','T056','T057','T059']
    if any(name in path for name in ('session','pipeline','orchestrator','queue','main.py')):
        return ['T005','T006','T007','T025','T027','T051','T052','T053','T054']
    return ['T055','T058','T059']


def capture(evidence):
    evidence=[Path(value) for value in evidence]
    for file in evidence:
        if not file.is_file() or not file.resolve().is_relative_to(ROOT/'integration/validation/reliability'):
            raise ValueError('Evidence must exist inside integration/validation/reliability')
        if file.suffix=='.xml':
            counts=report_counts(file)
            if counts['failures'] or counts['errors'] or counts['tests']<=counts['skipped']:
                raise ValueError('Failed or empty evidence cannot authorize a source revision')
    if not evidence: raise ValueError('Explicit evidence is required')
    baseline=(ROOT/'integration/source-snapshots.json').read_bytes()
    revisions=[]
    for studio,snapshot in json.loads(baseline).items():
        for relative,before in snapshot['files'].items():
            file=accessible(ROOT/snapshot['root']/relative)
            raw,normalized=_hashes(file.read_bytes())
            if raw==before or normalized==snapshot.get('normalized_files',{}).get(relative): continue
            revisions.append({'studio':studio,'path':relative,'beforeSha256':before,
                'afterSha256':raw,'afterNormalizedSha256':normalized,'tasks':tasks_for(relative),
                'evidence':[value.resolve().relative_to(ROOT).as_posix() for value in evidence]})
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    document={'formatVersion':1,'baselineSha256':hashlib.sha256(baseline).hexdigest(),
        'baseCommit':commit,'revisions':revisions,'liveProviderCalls':0}
    output=ROOT/'integration/source-revisions.json'
    output.write_text(json.dumps(document,indent=2)+'\n',encoding='utf-8')
    errors=check_sources()
    if errors: raise ValueError('\n'.join(errors))
    return len(revisions)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence',action='append',required=True,type=Path)
    args=parser.parse_args();print('Exact source revisions recorded:',capture(args.evidence))


if __name__=='__main__': main()
