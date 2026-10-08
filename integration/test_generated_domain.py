"""Real native HTTP contracts. Opt in explicitly; containers always carry fixture ownership."""
import json,os,subprocess,time,urllib.request,urllib.error,uuid
from pathlib import Path
import pytest
from integration.reliability_fixtures import assert_isolated
ROOT=Path(__file__).resolve().parents[1]
LABEL='agentia.reliability-test'
MATRIX_WORK=assert_isolated(Path(os.environ.get('AGENTIA_RELIABILITY_MATRIX_ROOT',ROOT/'.runtime/reliability/java')))
EVIDENCE=assert_isolated(Path(os.environ.get('AGENTIA_RELIABILITY_MATRIX_EVIDENCE',ROOT/'integration/validation/reliability')))
EVIDENCE.mkdir(parents=True,exist_ok=True)

def docker(*args):
    completed=subprocess.run(['docker',*args],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
    if completed.returncode: raise RuntimeError(completed.stderr)
    return completed.stdout.strip()

def remove_owned(name,owner):
    details=json.loads(docker('inspect',name))[0]
    assert details['Config']['Labels'].get(LABEL)==owner
    docker('rm','-f',name)

def request(base,path,method='GET',payload=None):
    req=urllib.request.Request(base+path,data=json.dumps(payload).encode() if payload is not None else None,method=method,headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=3) as response: return response.status,json.loads(response.read() or b'null')
    except urllib.error.HTTPError as error:
        raw=error.read();return error.code,json.loads(raw or b'null')

def http_contract(framework,workspace,tool="maven",engine="H2",extended=False):
    ws=assert_isolated(workspace);owner='http-'+uuid.uuid4().hex[:12];name='agentia-reliability-'+owner
    output_directory='target' if tool=='maven' else 'build'
    artifact=ws/output_directory/'quarkus-app/quarkus-run.jar' if framework=='quarkus' else next((ws/(output_directory if tool=='maven' else 'build/libs')).glob('*SNAPSHOT.jar'))
    assert artifact.is_file()
    network=name+'-network';database=name+'-db';volume=name+'-data';created_db=False;created_network=False;created_volume=False
    command=['run','-d','--pull','never','--name',name,'--label',LABEL+'='+owner,'-p','127.0.0.1::8080',
        '--mount','type=bind,source='+str(ws)+',target=/workspace,readonly','-w','/workspace',
        '-e','QUARKUS_HTTP_PORT=8080','-e','SERVER_PORT=8080','maven:3.9-eclipse-temurin-21','java','-jar',artifact.relative_to(ws).as_posix()]
    from integration.generated_domain_matrix import fixture_fingerprint
    evidence={'outcome':'FAILED','liveProviderCalls':0,'workspaceFingerprint':fixture_fingerprint(ws),'framework':framework,'buildTool':tool,'databaseEngine':engine,'workspace':str(ws),'checks':[]}
    started_app=False
    try:
        if engine!='H2':
            docker('network','create','--label',LABEL+'='+owner,network);created_network=True
            docker('volume','create','--label',LABEL+'='+owner,volume);created_volume=True
            db_image='postgres:16.4-alpine' if engine=='POSTGRESQL' else 'mysql:8.0.40'
            database_args=['run','-d','--pull','never','--name',database,'--label',LABEL+'='+owner,'--network',network,'--network-alias','db']
            if engine=='POSTGRESQL':
                database_args+=['-e','POSTGRES_DB=ledger_service','-e','POSTGRES_USER=fixture','-e','POSTGRES_PASSWORD=fixture-password','--mount','type=volume,source='+volume+',target=/var/lib/postgresql/data']
                db_url='jdbc:postgresql://db:5432/ledger_service';username='fixture'
                ready=['exec',database,'pg_isready','-U','fixture','-d','ledger_service']
            else:
                database_args+=['-e','MYSQL_DATABASE=ledger_service','-e','MYSQL_ROOT_PASSWORD=fixture-password','--mount','type=volume,source='+volume+',target=/var/lib/mysql']
                db_url='jdbc:mysql://db:3306/ledger_service?allowPublicKeyRetrieval=true&useSSL=false&serverTimezone=UTC';username='root'
                ready=['exec',database,'mysqladmin','ping','-h','127.0.0.1','-pfixture-password']
            docker(*(database_args+[db_image]));created_db=True
            for _ in range(90):
                try:
                    if 'alive' in docker(*ready) or engine=='POSTGRESQL' and 'accepting connections' in docker(*ready): break
                except RuntimeError: pass
                time.sleep(1)
            else: raise AssertionError('Owned database failed to become ready')
            image_index=command.index('maven:3.9-eclipse-temurin-21')
            command[image_index:image_index]=['--network',network,'-e','DB_URL='+db_url,'-e','DB_USER='+username,'-e','DB_PASSWORD=fixture-password','-e','SPRING_PROFILES_ACTIVE=prod','-e','QUARKUS_PROFILE=prod']
        docker(*command);started_app=True
        details=json.loads(docker('inspect',name))[0]
        bindings=details['NetworkSettings']['Ports'].get('8080/tcp') or []
        assert bindings, 'Missing owned runtime port binding: '+docker('logs',name)[-6000:]
        port=bindings[0]['HostPort']
        base='http://127.0.0.1:'+port;resource='/api/v1/ledgerentrys'
        for _ in range(90):
            running=json.loads(docker('inspect',name))[0]['State'].get('Running')
            assert running, 'Native application exited during startup: '+docker('logs',name)[-6000:]
            try:
                status,_=request(base,resource)
                if status==200: break
            except (OSError,ValueError): pass
            time.sleep(1)
        else: raise AssertionError('Native application failed to start: '+docker('logs',name)[-6000:])
        valid={'email':'native@example.com','balance':12.34,'bookedAt':'2024-01-01T12:00:00Z'}
        if extended:
            status,account=request(base,'/api/v1/ledgeraccounts','POST',{'name':'Native account'})
            assert status==201,(status,account)
            account_id=account['accountId']
            valid.update(accountKey=account_id,effectiveDate='2024-02-29',recordedAt='2024-02-29T13:14:15')
            for field,value in [('accountKey',str(uuid.uuid4())),('effectiveDate','2024-02-30'),('recordedAt','invalid')]:
                status,body=request(base,resource,'POST',{**valid,field:value})
                expected=409 if field=='accountKey' else 400
                assert status==expected,(field,status,body)
                evidence['checks'].append({'check':'relational-invalid-'+field,'status':status})
        for field,value in [('email','invalid'),('balance',0),('balance',-1),('email',None)]:
            status,body=request(base,resource,'POST',{**valid,field:value})
            evidence['checks'].append({'check':'invalid-'+field+'-'+str(value),'status':status})
            assert status==400,(field,value,status,body)
        status,created=request(base,resource,'POST',valid);assert status==201,(status,created)
        entry=created['entryId'];assert str(uuid.UUID(entry))==entry
        assert float(created['balance'])==12.34
        status,loaded=request(base,resource+'/'+entry);assert status==200 and loaded['entryId']==entry
        if extended:
            assert loaded['accountKey']==account_id
            assert loaded['effectiveDate']=='2024-02-29'
            assert loaded['recordedAt'].startswith('2024-02-29T13:14:15')
            status,blocked_delete=request(base,'/api/v1/ledgeraccounts/'+account_id,'DELETE')
            assert status==409,(status,blocked_delete)
            status,retained=request(base,resource+'/'+entry)
            assert status==200 and retained['entryId']==entry
            evidence['checks'].append({'check':'parent-delete-does-not-cascade','status':'PASSED'})
        status,duplicate=request(base,resource,'POST',valid)
        evidence['checks'].append({'check':'unique-email','status':status})
        assert status==409,(status,duplicate)
        if engine!='H2':
            # Stop/start the same owned runtime and database; the created UUID must survive.
            docker('stop',name);docker('stop',database);docker('start',database)
            for _ in range(90):
                try:
                    docker(*ready);break
                except RuntimeError: time.sleep(1)
            docker('start',name)
            restarted=json.loads(docker('inspect',name))[0]['NetworkSettings']['Ports'].get('8080/tcp') or []
            assert restarted, 'Restart lost the owned runtime port binding'
            base='http://127.0.0.1:'+restarted[0]['HostPort']
            for _ in range(90):
                try:
                    status,restored=request(base,resource+'/'+entry)
                    if status==200: break
                except (OSError,ValueError): pass
                time.sleep(1)
            else: raise AssertionError('Restart failed to preserve runtime data: '+docker('logs',name)[-6000:])
            assert restored['entryId']==entry
            evidence['checks'].append({'check':'stop-restart-data-preserved','status':'PASSED'})
        status,_=request(base,resource+'/'+entry,'DELETE');assert status==204
        status,_=request(base,resource+'/'+entry);assert status==404
        evidence['checks'].append({'check':'CRUD-UUID-date-decimal','status':'PASSED'})
        assert fixture_fingerprint(ws)==evidence['workspaceFingerprint']
        evidence['outcome']='PASSED'
        return evidence
    finally:
        output=EVIDENCE/('http-'+('relational-' if extended else '')+framework+'-'+tool+'-'+engine.lower()+'.json')
        output.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
        if started_app: remove_owned(name,owner)
        if created_db: remove_owned(database,owner)
        for kind,identity,created in [('volume',volume,created_volume),('network',network,created_network)]:
            if created:
                inspected=json.loads(docker(kind,'inspect',identity))[0]
                assert inspected['Labels'].get(LABEL)==owner
                docker(kind,'rm',identity)

@pytest.mark.skipif(os.getenv('AGENTIA_NATIVE_HTTP')!='1',reason='Requires explicit Docker fixture opt-in')
@pytest.mark.parametrize('framework',['springboot','quarkus'])
def test_native_http_h2(framework):
    http_contract(framework,MATRIX_WORK/(framework+'-maven-h2'))


@pytest.mark.skipif(os.getenv('AGENTIA_GENERATED_MATRIX_HTTP')!='1',reason='Requires built native matrix and explicit owned Docker fixture opt-in')
@pytest.mark.parametrize('framework',['springboot','quarkus'])
@pytest.mark.parametrize('tool',['maven','gradle'])
@pytest.mark.parametrize('engine',['H2','POSTGRESQL','MYSQL'])
def test_native_http_full_matrix(framework,tool,engine):
    http_contract(framework,MATRIX_WORK/(framework+'-'+tool+'-'+engine.lower()),tool,engine)


@pytest.mark.skipif(os.getenv('AGENTIA_RELATIONAL_MATRIX_HTTP')!='1',reason='Requires extended native matrix and explicit owned Docker opt-in')
@pytest.mark.parametrize('framework',['springboot','quarkus'])
@pytest.mark.parametrize('tool',['maven','gradle'])
@pytest.mark.parametrize('engine',['H2','POSTGRESQL','MYSQL'])
def test_native_relational_http_matrix(framework,tool,engine):
    http_contract(framework,MATRIX_WORK/('relational-'+framework+'-'+tool+'-'+engine.lower()),tool,engine,extended=True)
