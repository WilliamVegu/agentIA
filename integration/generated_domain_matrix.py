"""Owned native build matrix. Preparation is opt-in; verification is always network=none."""
import argparse,itertools,json,os,subprocess,sys,time,uuid,hashlib,xml.etree.ElementTree as ET
from pathlib import Path
from integration.reliability_fixtures import assert_isolated
ROOT=Path(__file__).resolve().parents[1]
RESULTS=assert_isolated(Path(os.environ.get('AGENTIA_RELIABILITY_MATRIX_EVIDENCE',ROOT/'integration/validation/reliability')))
RESULTS.mkdir(parents=True,exist_ok=True)
WORK=assert_isolated(Path(os.environ.get('AGENTIA_RELIABILITY_MATRIX_ROOT',ROOT/'.runtime/reliability/java')))

def fixture_fingerprint(workspace):
    from integration.verify_sources import accessible
    root=accessible(Path(workspace).resolve())
    digest=hashlib.sha256()
    excluded={'target','build','.gradle','.git','.agentia-runtime','.operation-locks'}
    for file in sorted(root.rglob('*')):
        relative=file.relative_to(root)
        if any(part in excluded for part in relative.parts) or not file.is_file(): continue
        if file.name.startswith('.env') or file.suffix=='.log': continue
        if file.is_symlink(): raise ValueError('Fixture contains a linked input')
        digest.update(relative.as_posix().encode());digest.update(b'\0');digest.update(file.read_bytes());digest.update(b'\0')
    return digest.hexdigest()

def execute(command,log,*,environment=None,timeout=900):
    with log.open('w',encoding='utf-8') as output:
        process=subprocess.run(command,cwd=ROOT,env=environment,stdout=output,stderr=subprocess.STDOUT,timeout=timeout)
    return process.returncode

def combination(framework,tool,engine,prepare=False,extended=False):
    name=('relational-' if extended else '')+framework+'-'+tool+'-'+engine.lower();workspace=assert_isolated(WORK/name);workspace.mkdir(parents=True,exist_ok=True)
    backend=ROOT/('systems/quarkus/backend' if framework=='quarkus' else 'backend')
    environment={**os.environ,'PYTHONPATH':str(backend)+os.pathsep+str(ROOT)}
    for key in list(environment):
        if key.endswith('API_KEY'): environment.pop(key)
    generated=execute([sys.executable,str(ROOT/'integration/generated_domain_worker.py'),'--workspace',str(workspace),'--build-tool',tool,'--database',engine]+(['--extended'] if extended else []),RESULTS/(name+'-generation.log'),environment=environment)
    if generated: raise AssertionError('Generation failed: '+name)
    source_fingerprint=fixture_fingerprint(workspace)
    cache=assert_isolated(ROOT/'.runtime/reliability/java/cache'/('m2' if tool=='maven' else 'gradle'));cache.mkdir(parents=True,exist_ok=True)
    image='maven:3.9-eclipse-temurin-21' if tool=='maven' else 'gradle:8.10.2-jdk21'
    cache_target='/root/.m2/repository' if tool=='maven' else '/home/gradle/.gradle'
    cache_mount='type=bind,source='+str(cache)+',target='+cache_target
    if tool=='gradle':
        # Gradle's immutable transform renames require the container's Linux filesystem.
        volume='agentia-reliability-gradle-matrix-cache-v1'
        inspected=subprocess.run(['docker','volume','inspect',volume],capture_output=True,text=True)
        if inspected.returncode:
            subprocess.run(['docker','volume','create','--label','agentia.reliability-test=gradle-matrix-cache-v1',volume],check=True,capture_output=True)
            inspected=subprocess.run(['docker','volume','inspect',volume],capture_output=True,text=True,check=True)
        if json.loads(inspected.stdout)[0]['Labels'].get('agentia.reliability-test')!='gradle-matrix-cache-v1':
            raise AssertionError('Foreign Gradle cache volume rejected')
        cache_mount='type=volume,source='+volume+',target='+cache_target

    owner='matrix-'+uuid.uuid4().hex[:12];container='agentia-reliability-'+owner
    arguments=['docker','run','--rm','--pull','never','--name',container,'--label','agentia.reliability-test='+owner,'--mount','type=bind,source='+str(workspace)+',target=/workspace','--mount',cache_mount,'-w','/workspace',image]
    build=['mvn','-B','-ntp','verify'] if tool=='maven' else ['gradle','--no-daemon','--console=plain','build']
    result={'framework':framework,'buildTool':tool,'databaseEngine':engine,'workspace':str(workspace),'liveProviderCalls':0,'workspaceFingerprint':source_fingerprint}
    if prepare:
        result['preparationExitCode']=execute(arguments+build,RESULTS/(name+'-preparation.log'))
        if result['preparationExitCode']: return {**result,'outcome':'PREPARATION_FAILED'}
    # No pull and no external networking in every verification attempt.
    arguments[3:3]=['--network','none']
    build=build+(['-o'] if tool=='maven' else ['--offline'])
    result['verificationExitCode']=execute(arguments+build,RESULTS/(name+'-offline.log'))
    reports=[];totals=[0,0,0,0]
    for file in workspace.rglob('*.xml'):
        if 'surefire-reports' not in file.parts and 'test-results' not in file.parts: continue
        root=ET.parse(file).getroot()
        for suite in ([root] if root.tag=='testsuite' else root.findall('testsuite')):
            totals=[a+int(suite.get(key,'0')) for a,key in zip(totals,['tests','failures','errors','skipped'])]
        reports.append(str(file.relative_to(ROOT)) if file.is_relative_to(ROOT) else str(file))
    result.update(testCounts=dict(zip(['total','failures','errors','skipped'],totals)),reports=reports,sourceUnchanged=fixture_fingerprint(workspace)==source_fingerprint,reportHashes={str(file):hashlib.sha256(file.read_bytes()).hexdigest() for file in workspace.rglob('*.xml') if 'surefire-reports' in file.parts or 'test-results' in file.parts})
    result['outcome']='PASSED' if result['verificationExitCode']==0 and totals[0]>0 and totals[1:]==[0,0,0] and reports and result['sourceUnchanged'] else 'FAILED'
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--extended',action='store_true');parser.add_argument('--prepare',action='store_true');parser.add_argument('--framework',choices=['springboot','quarkus']);parser.add_argument('--tool',choices=['maven','gradle']);parser.add_argument('--engine',choices=['H2','POSTGRESQL','MYSQL']);args=parser.parse_args()
    results=[]
    for framework,tool,engine in itertools.product([args.framework] if args.framework else ['springboot','quarkus'],[args.tool] if args.tool else ['maven','gradle'],[args.engine] if args.engine else ['H2','POSTGRESQL','MYSQL']):
        print('Running',framework,tool,engine,flush=True)
        try: result=combination(framework,tool,engine,args.prepare,args.extended)
        except Exception as error: result={'framework':framework,'buildTool':tool,'databaseEngine':engine,'outcome':'ERROR','error':str(error)}
        results.append(result)
        (RESULTS/('java-matrix-'+('relational-' if args.extended else '')+(args.framework or 'all')+'-'+(args.tool or 'all')+'-'+(args.engine or 'all')+'.json')).write_text(json.dumps(results,indent=2),encoding='utf-8')
        print(result['outcome'],flush=True)
    return 0 if all(item['outcome']=='PASSED' for item in results) else 1

if __name__=='__main__': raise SystemExit(main())
