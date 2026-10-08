"""A fresh process recovers a crashed writer and its durable event history."""
import json,subprocess
import pytest
from integration.reliability_smoke import ROOT,python_for,environment

@pytest.mark.parametrize('studio',['springboot','quarkus'])
def test_real_backend_process_restart(studio,tmp_path):
    backend=ROOT/('systems/quarkus/backend' if studio=='quarkus' else 'backend')
    env=environment(tmp_path,backend)
    prepare="""
import os,json
from pathlib import Path
from app.main import initialize_session_schema
initialize_session_schema()
from app.models.session import SessionLocal,GenerationSessionDB
from app.services.operation_repository import begin_operation,transition_operation,checkpoint_operation
from app.services.session_operation_lock import SessionOperationLock
from app.services.session_event_service import publish_event
from app.config import settings
with SessionLocal() as db:
    db.add(GenerationSessionDB(id='restart-owned',spec_id='restart',spec_name='Restart'));db.commit()
lock=SessionOperationLock('restart-owned');assert lock.acquire(False)
operation=begin_operation('restart-owned','CODE_TESTS',options={'apiKey':'credential-sentinel','autoDeploy':True})
operation=transition_operation(operation['operationId'],operation['version'],'RUNNING')
checkpoint_operation(operation['operationId'],operation['version'],'DOMAIN',{'marker':'retained'})
publish_event('restart-owned','build_log',{'message':'committed before crash'})
source=Path(settings.WORKSPACE_DIR)/'restart-owned'/'sentinel.java';source.parent.mkdir(parents=True,exist_ok=True);source.write_text('preserved source')
os._exit(0)
"""
    recover="""
import json,subprocess
from pathlib import Path
# Recovery may read its DB and reclaim its own dead lock; it must not replay actions.
def forbidden(*args,**kwargs): raise AssertionError('Startup replayed an external command')
subprocess.run=forbidden
from app.main import initialize_session_schema
initialize_session_schema()
from app.config import settings
from app.services.operation_repository import get_operation
from app.services.session_event_service import read_events
operation=get_operation('restart-owned')
assert operation['state']=='INTERRUPTED',operation
assert operation['checkpoint']['phase']=='DOMAIN',operation
assert operation['options']['autoDeploy'] is True
first=read_events('restart-owned');second=read_events('restart-owned')
assert first==second and len(first)>=5
assert 'committed before crash' in str(first)
assert 'credential-sentinel' not in str(first)+str(operation)
assert (Path(settings.WORKSPACE_DIR)/'restart-owned'/'sentinel.java').read_text()=='preserved source'
print(json.dumps({'state':operation['state'],'events':len(first),'liveProviderCalls':0}))
"""
    for script in (prepare,recover):
        result=subprocess.run([python_for(studio),'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,timeout=45)
        assert result.returncode==0,result.stderr
    observed=json.loads(result.stdout.strip().splitlines()[-1])
    assert observed['state']=='INTERRUPTED' and observed['events']>=5
