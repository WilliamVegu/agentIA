"""Native Quarkus runtime identity survives backend restart and rejects foreign health."""
import json,time
from fastapi import HTTPException
from app.models.session import SessionLocal,GenerationSessionDB
from app.models.reliability import DeploymentOperation
from app.models.devops import LocalDeploymentSession,DeploymentStatus,SmokeTestResult
from app.services.runtime_lifecycle import owned_resources,compose_project,command
from app.services.workspace_guard import get_validated_workspace_path
from app.services.verification_policy import workspace_fingerprint
from app.services.secret_redaction import redact

def latest(session_id):
    with SessionLocal() as db:
        if not db.get(GenerationSessionDB,session_id): raise HTTPException(404,'Session not found')
        return db.query(DeploymentOperation).filter_by(session_id=session_id).order_by(DeploymentOperation.created_at.desc()).first()

def begin(session_id,fingerprint,snapshot_id,host_port):
    with SessionLocal() as db:
        current=db.query(DeploymentOperation).filter_by(session_id=session_id).order_by(DeploymentOperation.created_at.desc()).first()
        if current and current.state in {'BUILDING','STARTING','PREPARING'}: raise HTTPException(409,'Deployment already active')
        row=DeploymentOperation(session_id=session_id,framework='quarkus',state='BUILDING',fingerprint=fingerprint,
            source_snapshot_id=snapshot_id,compose_project=compose_project(session_id),bindings_json=json.dumps({'hostPort':host_port}),
            labels_json=json.dumps({'io.agentia.owner':compose_project(session_id),'io.agentia.studio':'quarkus'}))
        db.add(row);db.commit();db.refresh(row);return row.operation_id

def update(operation_id,state,*,records=None,error=None):
    with SessionLocal() as db:
        row=db.get(DeploymentOperation,operation_id)
        if not row: raise RuntimeError('Deployment operation disappeared')
        from app.services.operation_repository import transaction
        # Serialize state updates: a terminal outcome cannot be overwritten by a late worker.
        db.rollback()
        transaction(db)
        row=db.get(DeploymentOperation,operation_id)
        if row.state in {'HEALTHY','FAILED','STOPPED','CANCELLED'}:
            db.rollback();return False
        row.state=state;row.error_code=redact(error)[:100] if error else None
        if records is not None:
            app=[item for item in records if (item.get('Config',{}).get('Labels') or {}).get('io.agentia.role')=='application']
            if len(app)!=1: raise RuntimeError('Exactly one owned app container required')
            row.container_ids_json=json.dumps([item['Id'] for item in records]);row.image_id=app[0]['Image']
            bindings=json.loads(row.bindings_json);bindings['actual']=app[0].get('NetworkSettings',{}).get('Ports',{})
            row.bindings_json=json.dumps(bindings)
        db.commit();return True

def observed_identity(session_id):
    row=latest(session_id)
    if not row or not row.image_id: return None
    ws=get_validated_workspace_path(session_id,require_exists=True)
    if workspace_fingerprint(ws)!=row.fingerprint: raise RuntimeError('Runtime sources are OUTDATED')
    records=owned_resources(session_id)
    if set(item['Id'] for item in records)!=set(json.loads(row.container_ids_json)): raise RuntimeError('Container identity changed')
    apps=[item for item in records if (item.get('Config',{}).get('Labels') or {}).get('io.agentia.role')=='application']
    if len(apps)!=1 or apps[0]['Image']!=row.image_id: raise RuntimeError('Runtime image changed')
    expected=json.loads(row.bindings_json)
    if apps[0].get('NetworkSettings',{}).get('Ports',{})!=expected.get('actual'): raise RuntimeError('Port binding changed')
    image=json.loads(command(['docker','image','inspect',row.image_id]).stdout)[0]
    if (image.get('Config',{}).get('Labels') or {}).get('io.agentia.source')!=row.fingerprint: raise RuntimeError('Image is not tied to verified sources')
    bindings=expected.get('actual',{}).get('8080/tcp') or []
    if len(bindings)!=1 or bindings[0]['HostIp']!='127.0.0.1' or int(bindings[0]['HostPort'])!=int(expected['hostPort']): raise RuntimeError('Runtime is not bound to its configured localhost port')
    return row,apps[0],expected

def status(session_id,request_get):
    row=latest(session_id)
    port=json.loads(row.bindings_json).get('hostPort') if row else configuration(session_id)['hostPort']
    if row and row.state in {'FAILED','STOPPED','CANCELLED'}:
        return LocalDeploymentSession(sessionId=session_id,status=DeploymentStatus.FAILED if row.state=='FAILED' else DeploymentStatus.STOPPED,hostPort=port,errorMessage=row.error_code)
    if row and row.state in {'BUILDING','STARTING','PREPARING'}:
        return LocalDeploymentSession(sessionId=session_id,status=DeploymentStatus.BUILDING,hostPort=json.loads(row.bindings_json)['hostPort'])
    try: identity=observed_identity(session_id)
    except Exception as error:
        return LocalDeploymentSession(sessionId=session_id,status=DeploymentStatus.UNKNOWN,hostPort=port,errorMessage=redact(str(error)))
    if not identity: return LocalDeploymentSession(sessionId=session_id,status=DeploymentStatus.UNKNOWN,hostPort=port)
    row,app,bindings=identity
    port=bindings['hostPort'];url='http://127.0.0.1:'+str(port)+'/q/health'
    result=LocalDeploymentSession(sessionId=session_id,containerId=app['Id'],hostPort=port,status=DeploymentStatus.RUNNING,healthStatus='UNKNOWN')
    if not app.get('State',{}).get('Running'):
        result.status=DeploymentStatus.STOPPED;result.healthStatus='DOWN';return result
    try:
        response=request_get(url,timeout=3)
        if response.status_code==200 and response.json().get('status')=='UP':
            result.status=DeploymentStatus.HEALTHY;result.healthStatus='UP';result.testUrl=url
            update(row.operation_id,'HEALTHY')
    except Exception: pass
    return result

def smoke(session_id,request_get,max_retries=15,interval=2,*,cancel_event=None):
    for attempt in range(max_retries):
        if cancel_event is not None and cancel_event.is_set(): break
        started=time.monotonic();observed=status(session_id,request_get)
        if observed.status==DeploymentStatus.HEALTHY:
            return SmokeTestResult(passed=True,statusCode=200,statusPayload={'status':'UP'},latencyMs=(time.monotonic()-started)*1000,testUrl=observed.testUrl,details='Owned Quarkus runtime reports UP')
        if observed.status in {DeploymentStatus.UNKNOWN,DeploymentStatus.STOPPED,DeploymentStatus.FAILED}: break
        time.sleep(interval)
    return SmokeTestResult(passed=False,statusCode=503,statusPayload={'status':'UNKNOWN'},testUrl='',details='No healthy owned Quarkus runtime')


def configuration(session_id):
    from app.models.reliability import SessionConfiguration,DraftRevision
    with SessionLocal() as db:
        session=db.get(GenerationSessionDB,session_id)
        if not session: raise HTTPException(404,'Session not found')
        config=db.query(SessionConfiguration).filter_by(session_id=session_id,version=session.configuration_version).first()
        revision=db.get(DraftRevision,session.revision_id) if session.revision_id else None
        return {'sessionId':session_id,'configurationVersion':session.configuration_version,
            'databaseEngine':config.database_engine if config else None,
            'hostPort':config.host_port if config else None,'buildTool':config.build_tool if config else None,
            'serviceName':json.loads(revision.payload_json)['serviceName'] if revision else None}


def require_runtime_allowed(session_id):
    from app.models.execution import ExecutionMode
    with SessionLocal() as db:
        session=db.get(GenerationSessionDB,session_id)
        if not session: raise HTTPException(404,'Session not found')
        if session.execution_mode!=ExecutionMode.DOCKER:
            raise HTTPException(403,'SOURCE_ONLY does not authorize Docker runtime operations')


def record_stopped(session_id):
    """Called only after an owned-resource stop or cleanup was observed successfully."""
    from app.services.operation_repository import transaction
    with SessionLocal() as db:
        transaction(db)
        row=db.query(DeploymentOperation).filter_by(session_id=session_id).order_by(DeploymentOperation.created_at.desc()).first()
        if row:
            row.state='STOPPED';row.error_code=None
        db.commit()
