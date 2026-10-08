import os
import queue
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, Optional

import requests

from app.models.devops import DeploymentStatus, LocalDeploymentSession, SmokeTestResult

# In-memory tracking for active deployments and log queues
_active_deployments: Dict[str, LocalDeploymentSession] = {}
_log_queues: Dict[str, queue.Queue] = {}
_raw_log_history: Dict[str, list] = {}
_deployment_controls = {}


class _DeploymentControl:
    def __init__(self, parents=()):
        self.event=threading.Event()
        self.finished=threading.Event()
        self.parents=parents
    def is_set(self):
        return self.event.is_set() or any(event.is_set() for event in self.parents)
    def set(self):
        self.event.set()


def check_docker_daemon() -> bool:
    """Checks if the local Docker daemon is running and reachable within a 2s timeout."""
    try:
        # Use docker info to test daemon communication
        result = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2.0,
            check=False,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return False


def get_deployment_status(session_id: str, host_port: int = 8080) -> LocalDeploymentSession:
    from app.services.local_runtime import status
    return status(session_id,requests.get)


def get_deployment_logs(session_id: str) -> list:
    """Return retained committed runtime logs, including after backend restart."""
    import json
    from app.models.session import SessionLocal, GenerationSessionDB
    from app.models.reliability import SessionEvent
    from fastapi import HTTPException
    with SessionLocal() as db:
        if not db.get(GenerationSessionDB,session_id): raise HTTPException(404,'Session not found')
        rows=db.query(SessionEvent).filter_by(session_id=session_id,event_type='runtime_log').order_by(SessionEvent.sequence).all()
        return [json.loads(row.payload_json)['message'] for row in rows]


def _log_message(session_id: str, message: str):
    from app.services.session_event_service import publish_event
    publish_event(session_id,'runtime_log',{'message':message})


def deploy_local(session_id: str,workspace_dir: str,host_port: int=None,rebuild: bool=False,*,_borrowed=False) -> LocalDeploymentSession:
    """Build only the sealed verified native artifact, then observe this operation's runtime."""
    import json,yaml
    from fastapi import HTTPException
    from app.models.session import SessionLocal,GenerationSessionDB
    from app.models.execution import ExecutionMode
    from app.services.verification_policy import session_has_current_evidence,require_verified_session
    from app.services.workspace_guard import get_validated_workspace_path
    from app.services.source_snapshot import materialize_snapshot
    from app.services.local_runtime import begin,update,latest
    from app.services.runtime_lifecycle import compose_project,owned_resources,command
    from app.services.session_operation_lock import SessionOperationLock
    from app.services.secret_redaction import redact
    ws=get_validated_workspace_path(session_id,require_exists=True)
    if ws.resolve()!=Path(workspace_dir).resolve(): raise HTTPException(400,'Workspace does not match session')
    with SessionLocal() as db:
        row=db.get(GenerationSessionDB,session_id)
        if row.execution_mode!=ExecutionMode.DOCKER: raise HTTPException(403,'SOURCE_ONLY does not authorize Docker deployment')
        if _borrowed:
            if not session_has_current_evidence(row): raise HTTPException(403,'Current native verification required')
        else: require_verified_session(row)
        metrics=json.loads(row.verification_metrics_json or '{}')
        configured=db.query(__import__('app.models.reliability',fromlist=['SessionConfiguration']).SessionConfiguration).filter_by(session_id=session_id).order_by(__import__('app.models.reliability',fromlist=['SessionConfiguration']).SessionConfiguration.version.desc()).first()
        port=host_port or (configured.host_port if configured else None)
        if port is None: raise HTTPException(409,'Persist a host port before deployment')
    lock=SessionOperationLock(session_id)
    if _borrowed and not lock.locked(): raise HTTPException(409,'Parent pipeline writer is required')
    if not _borrowed and not lock.acquire(False): raise HTTPException(409,'Session has an active writer')
    operation_id=None
    try:
        if not check_docker_daemon(): raise HTTPException(503,'Docker is unavailable; execution mode was preserved')
        import socket
        probe=socket.socket()
        try: probe.bind(('127.0.0.1',port))
        except OSError: raise HTTPException(409,'Configured host port is occupied')
        finally: probe.close()
        operation_id=begin(session_id,metrics['workspaceFingerprint'],metrics['sourceSnapshotId'],port)
    except Exception:
        if not _borrowed: lock.release()
        raise
    state=LocalDeploymentSession(sessionId=session_id,status=DeploymentStatus.BUILDING,hostPort=port)
    _active_deployments[session_id]=state
    parents=()
    if _borrowed:
        from app.services import pipeline_runner
        parents=tuple(event for event in (pipeline_runner._stop_events.get(session_id),pipeline_runner._pause_events.get(session_id)) if event is not None)
    control=_DeploymentControl(parents)
    _deployment_controls[operation_id]=control
    def worker():
        start_attempted=False
        def require_active():
            if control.is_set(): raise RuntimeError("Deployment was interrupted")
            observed=latest(session_id)
            if not observed or observed.operation_id!=operation_id or observed.state not in {'BUILDING','STARTING','PREPARING'}:
                raise RuntimeError('Deployment operation no longer active')
        try:
            require_active()
            with materialize_snapshot(ws,metrics['sourceSnapshotId'],metrics['workspaceFingerprint']) as (staged,artifact_hash):
                runtime_image='agentia-runtime:21-v1'
                command(['docker','image','inspect',runtime_image])
                (staged/'Dockerfile.runtime').write_text('FROM '+runtime_image+'\nWORKDIR /app\nCOPY --chown=10001:10001 .verified-artifact/quarkus-app/ /app/\nUSER 10001\nHEALTHCHECK NONE\nENV QUARKUS_HTTP_PORT=8080\nEXPOSE 8080\nENTRYPOINT ["java", "-jar", "/app/quarkus-run.jar"]\n',encoding='utf-8')
                # The source ignore file excludes *.jar. This context contains only the sealed fast-jar tree.
                (staged/'.dockerignore').write_text('*\n!.verified-artifact/\n!.verified-artifact/quarkus-app/\n!.verified-artifact/quarkus-app/**\n!Dockerfile.runtime\n',encoding='utf-8')
                tag=compose_project(session_id)+':'+artifact_hash[:20]
                command(['docker','build','--network','none','--pull=false','--label','io.agentia.source='+metrics['workspaceFingerprint'],'--label','io.agentia.studio=quarkus','-f','Dockerfile.runtime','-t',tag,'.'],cwd=staged,timeout=180,cancel_event=control)
                require_active()
                compose=yaml.safe_load((staged/'docker-compose.yml').read_text(encoding='utf-8'))
                app=[item for name,item in compose['services'].items() if name!='db']
                if len(app)!=1: raise RuntimeError('Exactly one native application service required')
                app[0].pop('build',None);app[0]['image']=tag
                (staged/'docker-compose.runtime.yml').write_text(yaml.safe_dump(compose,sort_keys=False),encoding='utf-8')
                require_active()
                start_attempted=True
                command(['docker','compose','-p',compose_project(session_id),'-f','docker-compose.runtime.yml','up','-d','--no-build','--pull','never'],cwd=staged,env={**os.environ,'HOST_PORT':str(port)},timeout=180,cancel_event=control)
            if not update(operation_id,'RUNNING',records=owned_resources(session_id)): return
            smoke=run_smoke_test(session_id,port,max_retries=30,interval=2,cancel_event=control)
            if not smoke.passed: raise RuntimeError(smoke.details)
            observed=latest(session_id)
            if not observed or observed.operation_id!=operation_id or observed.state!='HEALTHY': return
            state.status=DeploymentStatus.HEALTHY;state.healthStatus='UP';state.testUrl=smoke.testUrl
            _log_message(session_id,'[READY] Owned native Quarkus runtime is healthy')
        except Exception as error:
            state.status=DeploymentStatus.FAILED;state.errorMessage=redact(str(error))
            update(operation_id,'FAILED',error=state.errorMessage)
            if start_attempted and control.is_set():
                try:
                    from app.services.runtime_lifecycle import stop_owned
                    from app.services.local_runtime import record_stopped
                    stop_owned(session_id)
                    record_stopped(session_id)
                except Exception as stop_error:
                    state.errorMessage+=' Parada no confirmada: '+redact(str(stop_error))
            _log_message(session_id,'[FAILED] '+state.errorMessage)
        finally:
            control.finished.set()
            _deployment_controls.pop(operation_id,None)
            if not _borrowed: lock.release()
    if _borrowed:
        worker()
    else:
        try: threading.Thread(target=worker,daemon=True).start()
        except Exception:
            control.finished.set();_deployment_controls.pop(operation_id,None)
            update(operation_id,'FAILED',error='Worker could not start')
            lock.release()
            raise
    return state


def wait_deployment(session_id,timeout=420,*,stop_event=None,pause_event=None):
    from app.services.local_runtime import latest
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if stop_event is not None and stop_event.is_set() or pause_event is not None and pause_event.is_set():
            operation=latest(session_id)
            control=_deployment_controls.get(operation.operation_id) if operation else None
            if control:
                control.set()
                if not control.finished.wait(10): raise RuntimeError('Deployment writer has not confirmed interruption')
            return get_deployment_status(session_id)
        row=latest(session_id)
        if row and row.state in {'HEALTHY','FAILED','STOPPED','UNKNOWN'}:
            if row.state!='HEALTHY': raise RuntimeError(row.error_code or 'Deployment did not become healthy')
            return get_deployment_status(session_id)
        time.sleep(.5)
    from app.services.local_runtime import update
    row=latest(session_id)
    if row and row.state not in {'HEALTHY','FAILED','STOPPED','CANCELLED'}:
        control=_deployment_controls.get(row.operation_id)
        if control:
            control.set()
            if not control.finished.wait(10): raise RuntimeError('Deployment writer has not confirmed timeout')
        update(row.operation_id,'FAILED',error='Deployment operation timed out')
    raise RuntimeError('Deployment operation timed out')


def stream_logs(session_id: str, after: int = 0) -> Generator[str, None, None]:
    """Each client reads the committed log with its own cursor; no shared queue."""
    import json
    from app.services.session_event_service import read_events
    cursor=after
    idle=0
    while idle<30:
        emitted=False
        events=read_events(session_id,cursor)
        for event in events:
            cursor=int(event['id'])
            if event['event']=='runtime_log':
                emitted=True
                message=json.loads(event['data'])['message']
                # Encode one SSE data line per physical log line.
                lines=''.join('data: '+line+'\n' for line in message.splitlines())
                yield 'id: '+event['id']+'\n'+lines+'\n'
            elif event['event']=='resync_required':
                emitted=True
                yield 'id: '+event['id']+'\nevent: resync_required\ndata: '+event['data']+'\n\n'
        if emitted: idle=0
        elif not events:
            idle+=1
            yield ': keep-alive\n\n'
            time.sleep(.5)


def stop_deployment(session_id: str, workspace_dir: str) -> LocalDeploymentSession:
    """Stop inspected containers only; volumes and networks are preserved."""
    from app.services.local_runtime import require_runtime_allowed
    require_runtime_allowed(session_id)
    from app.services.runtime_lifecycle import stop_owned
    from app.services.session_operation_lock import SessionOperationLock
    from app.services.secret_redaction import redact
    session = _active_deployments.get(session_id, LocalDeploymentSession(sessionId=session_id))
    lock = SessionOperationLock(session_id)
    if not lock.acquire(False):
        session.errorMessage = 'An operation is active; stop was not performed'
        return session
    try:
        stop_owned(session_id)
        from app.services.local_runtime import record_stopped
        record_stopped(session_id)
        session.status, session.healthStatus, session.testUrl = DeploymentStatus.STOPPED, 'DOWN', None
        session.errorMessage = None
        _log_message(session_id, '[STOPPED] Owned containers stopped; data preserved.')
    except Exception as exc:
        session.status, session.healthStatus, session.testUrl = DeploymentStatus.FAILED, 'UNKNOWN', None
        session.errorMessage = redact(str(exc))
        _log_message(session_id, '[STOP_FAILED] ' + session.errorMessage)
    finally:
        _active_deployments[session_id] = session
        lock.release()
    return session


def run_smoke_test(session_id: str,host_port: int=8080,max_retries: int=15,interval: float=2.0,*,cancel_event=None) -> SmokeTestResult:
    from app.services.local_runtime import smoke
    return smoke(session_id,requests.get,max_retries,interval,cancel_event=cancel_event)
