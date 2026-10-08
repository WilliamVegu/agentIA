"""Reproducible isolated acceptance runner; credentials are removed from child processes."""
from __future__ import annotations
import argparse,json,os,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
from integration.reliability_fixtures import ROOT,assert_isolated

SUITES={
 'journeys':['test_e2e_flow.py','test_operation_state_machine.py','test_persisted_repair.py','test_artifact_revision.py','test_git_safety.py','test_session_events.py'],
 'migration':['test_session_schema_migrations.py','test_draft_authority.py','test_session_projection.py'],
 'runtime':['test_native_runtime_integration.py','test_runtime_data_safety.py'],
}

def python_for(studio):
    name='.venv-reliability-'+('quarkus' if studio=='quarkus' else 'spring')
    executable=ROOT/name/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    return str(executable) if executable.is_file() else sys.executable

def environment(root,backend):
    env=dict(os.environ)
    for key in list(env):
        if key.endswith('API_KEY') or key in {'GITHUB_TOKEN','GITLAB_TOKEN','GH_TOKEN'}:
            env.pop(key)
    root.mkdir(parents=True,exist_ok=True)
    temporary=root/'tmp';temporary.mkdir(exist_ok=True)
    env.update(PYTHONPATH=str(backend)+os.pathsep+str(ROOT),TEMP=str(temporary),TMP=str(temporary),TMPDIR=str(temporary),
               WORKSPACE_DIR=str(root/'workspaces'),SPECIFICATION_DIR=str(root/'specifications'),
               DATABASE_URL='sqlite:///'+(root/'session.db').as_posix(),COST_STORE_PATH=str(root/'cost.db'),
               ALLOW_OFFLINE_MOCK='false',ALLOW_HERMETIC_FALLBACK='false',MLFLOW_TRACKING_URI=(root/'mlruns').resolve().as_uri())
    return env

def report_counts(report):
    document=ET.parse(report).getroot()
    suites=[document] if document.tag=='testsuite' else document.findall('testsuite')
    return {key:sum(int(suite.get(key,0)) for suite in suites) for key in ('tests','failures','errors','skipped')}

def run_suite(suite,test_root,evidence_dir,studios=('springboot','quarkus'),docker=False):
    test_root=assert_isolated(Path(test_root));evidence_dir=assert_isolated(Path(evidence_dir))
    evidence_dir.mkdir(parents=True,exist_ok=True)
    if suite in {'runtime','java-matrix'} and not docker:
        raise ValueError('This suite requires --docker: only owned Docker resources are used')
    results=[]
    for studio in studios:
        cwd=ROOT/('systems/quarkus' if studio=='quarkus' else '.')
        env=environment(test_root/studio,cwd/'backend')
        report=evidence_dir/(studio+'-'+suite+'.xml')
        if suite=='java-matrix':
            # Run the worker in a fresh process to keep app packages independent.
            env['AGENTIA_RELIABILITY_MATRIX_ROOT']=str(test_root/'java')
            env['AGENTIA_RELIABILITY_MATRIX_EVIDENCE']=str(evidence_dir)
            command=[python_for(studio),'-m','integration.generated_domain_matrix','--framework',studio,'--extended']
            cwd=ROOT
        else:
            if docker: env.update(RUN_NATIVE_RUNTIME='1',RUN_RELIABILITY_DOCKER='1')
            command=[python_for(studio),'-m','pytest',*[str(cwd/'backend/tests'/name) for name in SUITES[suite]],
                     '-q','--tb=short','--junitxml='+str(report)]
        log=evidence_dir/(studio+'-'+suite+'.log')
        with log.open('w',encoding='utf-8') as output:
            result=subprocess.run(command,cwd=cwd,env=env,stdout=output,stderr=subprocess.STDOUT,timeout=3600)
        if suite=='java-matrix' and result.returncode==0:
            env['AGENTIA_RELATIONAL_MATRIX_HTTP']='1'
            report=evidence_dir/(studio+'-native-http.xml')
            http_log=evidence_dir/(studio+'-native-http.log')
            with http_log.open('w',encoding='utf-8') as output:
                result=subprocess.run([python_for(studio),'-m','pytest',str(ROOT/'integration/test_generated_domain.py'),
                    '-k','relational and '+studio,'-q','--tb=short','--junitxml='+str(report)],cwd=ROOT,env=env,
                    stdout=output,stderr=subprocess.STDOUT,timeout=1800)
        counts=report_counts(report) if report.exists() else None
        passed=result.returncode==0 and (counts is None or counts['tests']>counts['skipped'] and counts['errors']==counts['failures']==0)
        item={'studio':studio,'suite':suite,'exitCode':result.returncode,'outcome':'PASSED' if passed else 'FAILED',
              'counts':counts,'log':str(log),'report':str(report) if counts else None,'liveProviderCalls':0}
        results.append(item)
        print(studio,suite,item['outcome'],flush=True)
    if suite=='journeys':
        restart_report=evidence_dir/'real-restart.xml'
        env=environment(test_root/'restart',ROOT/'backend')
        with (evidence_dir/'real-restart.log').open('w',encoding='utf-8') as output:
            restart=subprocess.run([python_for('springboot'),'-m','pytest',str(ROOT/'integration/test_restart_recovery.py'),
                '-q','--tb=short','--junitxml='+str(restart_report)],cwd=ROOT,env=env,stdout=output,stderr=subprocess.STDOUT,timeout=180)
        results.append({'studio':'both','suite':'process-restart','exitCode':restart.returncode,
            'outcome':'PASSED' if restart.returncode==0 else 'FAILED','counts':report_counts(restart_report) if restart_report.exists() else None,'liveProviderCalls':0})
    (evidence_dir/(suite+'-summary.json')).write_text(json.dumps(results,indent=2),encoding='utf-8')
    return 0 if all(row['outcome']=='PASSED' for row in results) else 1

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--test-root',type=Path,required=True)
    parser.add_argument('--evidence-dir',type=Path,required=True)
    parser.add_argument('--suite',choices=[*SUITES,'java-matrix'],required=True)
    parser.add_argument('--studio',choices=['springboot','quarkus'])
    parser.add_argument('--docker',action='store_true')
    args=parser.parse_args()
    return run_suite(args.suite,args.test_root,args.evidence_dir,(args.studio,) if args.studio else ('springboot','quarkus'),args.docker)

if __name__=='__main__': raise SystemExit(main())
