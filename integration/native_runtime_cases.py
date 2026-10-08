"""Owned native acceptance: two concurrent sessions, collisions, crash recovery, unavailable Docker."""
import json,os,socket,subprocess,uuid
from contextlib import nullcontext
from pathlib import Path
from integration.reliability_fixtures import ROOT,assert_isolated,ledger_draft


def free_port():
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1',0))
        return reservation.getsockname()[1]


def run_native_case(framework,tmp_path,monkeypatch):
    from app.config import settings
    from app.models.session import SessionLocal,GenerationSessionDB,SessionStatus,SessionPhase
    from app.models.execution import ExecutionMode
    from app.services.draft_revision_service import save_revision,approve_revision
    from app.services.devops_service import generate_all_devops_assets
    from app.services.workspace_verification import run_workspace_verification
    from app.services.verification_evidence import verification_metrics
    from app.services.session_operation_lock import SessionOperationLock
    from app.services import docker_service as runtime
    from app.services import runtime_lifecycle as lifecycle
    from app.services.playground_proxy import forward,discover_resources
    from app.orchestrator.stages.runner import run_stages
    from fastapi import HTTPException
    import pytest
    quarkus=framework=='quarkus'
    parent=assert_isolated(ROOT/'.runtime/reliability/native-platform')
    parent.mkdir(parents=True,exist_ok=True)
    monkeypatch.setattr(settings,'WORKSPACE_DIR',str(parent))
    monkeypatch.setattr(settings,'MAVEN_CACHE_DIR',str(ROOT/'.runtime/reliability/java/cache/m2'))
    monkeypatch.setattr(settings,'DOCKER_ENABLED',True)
    monkeypatch.setattr(settings,'ALLOW_HERMETIC_FALLBACK',False)
    identities=[]
    results=[]
    try:
        for index in range(2):
            identity='reliability-native-'+uuid.uuid4().hex;identities.append(identity)
            workspace=parent/identity;port=free_port()
            draft=ledger_draft();draft['basePort']=port;draft['databaseMode']='H2'
            with SessionLocal() as db:
                db.add(GenerationSessionDB(id=identity,spec_id=identity,spec_name='Ledger',execution_mode=ExecutionMode.DOCKER));db.commit()
            assert lifecycle.owned_resources(identity)==[]
            revision=save_revision(identity,draft);approve_revision(identity,revision['revisionId'])
            generated=run_stages({'session_id':identity,'workspace_path':str(workspace),'blueprint':draft,'generation_mode':'DETERMINISTIC','generated_files':{},'logs':[]})
            assert generated.get('status')!='BLOCKED',generated.get('error')
            generate_all_devops_assets(str(workspace),identity,draft['serviceName'],db_engine='H2',host_port=port)
            with (workspace/'native-verification-build.log').open('w',encoding='utf-8') as log:
                verification=run_workspace_verification(workspace,mode=ExecutionMode.DOCKER,log_callback=lambda line:(log.write(line),log.flush()))
            assert verification.platform_verified and verification.result.exit_code==0,verification.result.stderr+'\n'+verification.result.stdout[-6000:]
            assert not verification.result.fallback_used
            metrics=verification_metrics(verification)
            assert metrics['totalTests']>0 and metrics['allPassed'],metrics
            with SessionLocal() as db:
                row=db.get(GenerationSessionDB,identity);row.verification_metrics_json=json.dumps(metrics)
                row.status=SessionStatus.COMPLETED;row.phase=SessionPhase.VERIFIED;row.error_message=None;db.commit()
            if index==1:
                # An unavailable daemon must preserve choice and must not start anything.
                with monkeypatch.context() as patch:
                    patch.setattr(runtime,'check_docker_daemon',lambda:False)
                    if quarkus:
                        with pytest.raises(HTTPException) as unavailable: runtime.deploy_local(identity,str(workspace))
                        assert unavailable.value.status_code==503
                    else:
                        from app.services.local_operations import borrowed_lock
                        parent_lock=SessionOperationLock(identity);assert parent_lock.acquire(False)
                        try:
                            with borrowed_lock(identity): unavailable=runtime.deploy_local(identity,str(workspace))
                            assert unavailable.status.value in {'FAILED','DOCKER_UNAVAILABLE'}
                        finally: parent_lock.release()
                assert lifecycle.owned_resources(identity)==[]
                with SessionLocal() as db: assert db.get(GenerationSessionDB,identity).execution_mode==ExecutionMode.DOCKER
                # Keep an unrelated listener alive while testing the configured port.
                with socket.socket() as foreign:
                    foreign.bind(('127.0.0.1',port));foreign.listen()
                    if quarkus:
                        with pytest.raises(HTTPException) as collision: runtime.deploy_local(identity,str(workspace))
                        assert collision.value.status_code==409
                        assert lifecycle.owned_resources(identity)==[]
                    else:
                        from app.services.local_operations import borrowed_lock
                        parent_lock=SessionOperationLock(identity);assert parent_lock.acquire(False)
                        try:
                            with borrowed_lock(identity): launched=runtime.deploy_local(identity,str(workspace))
                            assert parent_lock.locked() and launched.status.value=='HEALTHY',launched
                            assert launched.hostPort!=port
                        finally: parent_lock.release()
                    assert foreign.getsockname()[1]==port
                if quarkus:
                    parent_lock=SessionOperationLock(identity);assert parent_lock.acquire(False)
                    try:
                        launched=runtime.deploy_local(identity,str(workspace),_borrowed=True)
                        assert parent_lock.locked() and launched.status.value=='HEALTHY',launched
                    finally: parent_lock.release()
            else:
                launched=runtime.deploy_local(identity,str(workspace))
                assert launched.status.value=='BUILDING'
                wait=runtime.wait_deployment if quarkus else runtime.wait_for_deployment
                launched=wait(identity,timeout=180)
            assert launched.status.value=='HEALTHY',launched
            resources=lifecycle.owned_resources(identity)
            assert resources
            for item in resources:
                role=item.get('Config',{}).get('Labels',{}).get('io.agentia.role')
                if role in {'application','database'}: assert item['State']['Running'],item['State']
                else: assert item['State']['Running'] or item['State']['ExitCode']==0,item['State']
            routes=discover_resources(identity,str(workspace));assert len(routes)==1
            response=forward(identity,'GET',routes[0]);assert response['statusCode']==200,response
            results.append({'sessionId':identity,'hostPort':launched.hostPort,'containers':[item['Id'] for item in resources],
                            'revisionId':revision['revisionId'],'fingerprint':metrics['workspaceFingerprint'],'tests':metrics['totalTests']})
            if index: assert runtime.get_deployment_status(identities[0]).status.value=='HEALTHY'
        assert set(results[0]['containers']).isdisjoint(results[1]['containers'])
        assert results[0]['hostPort']!=results[1]['hostPort']
        # Full Auto-Pilot: begin with an approved draft and no generated files.
        from app.services import pipeline_runner
        from app.models.orchestrator import LifecyclePhase
        from app.services.operation_repository import get_operation
        automatic='reliability-native-'+uuid.uuid4().hex;identities.append(automatic)
        draft=ledger_draft();draft['basePort']=free_port();draft['databaseMode']='H2'
        with SessionLocal() as db:
            db.add(GenerationSessionDB(id=automatic,spec_id=automatic,spec_name='ledger-service',execution_mode=ExecutionMode.DOCKER));db.commit()
        revision=save_revision(automatic,draft);approve_revision(automatic,revision['revisionId'])
        assert pipeline_runner.run_pipeline(automatic,target_phase=LifecyclePhase.COMPLETED,auto_deploy=True,provider='mock',model_name='offline-mock')
        pipeline_runner._active_threads[automatic].join(timeout=420)
        assert not pipeline_runner._active_threads[automatic].is_alive(),'Auto-Pilot writer did not settle'
        operation=get_operation(automatic)
        with SessionLocal() as db:
            row=db.get(GenerationSessionDB,automatic)
            assert operation['state']=='COMPLETED' and row.status==SessionStatus.COMPLETED,(operation,row.error_message)
            metrics=json.loads(row.verification_metrics_json)
            assert metrics['totalTests']>0 and metrics['allPassed'] and not metrics.get('fallback_used')
        observed=runtime.get_deployment_status(automatic);assert observed.status.value=='HEALTHY',observed
        results.append({'sessionId':automatic,'entryPoint':'AUTO_PILOT','hostPort':observed.hostPort,
            'containers':[item['Id'] for item in lifecycle.owned_resources(automatic)],
            'revisionId':revision['revisionId'],'fingerprint':metrics['workspaceFingerprint'],'tests':metrics['totalTests']})
        # A fresh Python backend reads the same disposable DB, then observes both owned runtimes.
        from integration.reliability_smoke import python_for
        env=dict(os.environ)
        for key in list(env):
            if key.endswith('API_KEY'): env.pop(key)
        with SessionLocal() as db: database_url=str(db.get_bind().url)
        env.update(DATABASE_URL=database_url,WORKSPACE_DIR=str(parent),DOCKER_ENABLED='true',PYTHONPATH=str(ROOT/('systems/quarkus/backend' if quarkus else 'backend'))+os.pathsep+str(ROOT))
        script="from app.main import initialize_session_schema;initialize_session_schema();from app.services.docker_service import get_deployment_status;"+";".join("row=get_deployment_status("+repr(identity)+");assert row.status.value=='HEALTHY',row.model_dump()" for identity in identities)
        observed=subprocess.run([python_for(framework),'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,timeout=60)
        assert observed.returncode==0,observed.stderr
        for identity in identities:
            stopped=runtime.stop_deployment(identity,str(parent/identity));assert stopped.status.value=='STOPPED',stopped
            assert runtime.get_deployment_status(identity).status.value=='STOPPED'
        evidence=ROOT/'integration/validation/reliability'/(framework+'-native-identity-current.json')
        evidence.write_text(json.dumps({'framework':framework,'liveProviderCalls':0,'twoSessions':results,'freshBackendRecovery':'PASSED','collision':'PASSED','dockerUnavailable':'PASSED','stop':'PASSED','autoPilot':'PASSED'},indent=2),encoding='utf-8')
    finally:
        for identity in identities:
            preview=lifecycle.cleanup_preview(identity)
            cleanup=lifecycle.cleanup_owned if quarkus else lifecycle.cleanup_local
            cleanup(identity,delete_data=True,confirmation=preview['confirmationToken'])
            assert lifecycle.owned_resources(identity)==[]
