import pytest
from fastapi import HTTPException
from app.models.session import SessionLocal, GenerationSessionDB
from app.models.reliability import PipelineOperation, SessionEvent

@pytest.fixture
def session(tmp_path, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings,"WORKSPACE_DIR",str(tmp_path))
    with SessionLocal() as db:
        db.add(GenerationSessionDB(id='operation-test', spec_id='operation-spec', spec_name='Ledger'))
        db.commit()
    yield 'operation-test'
    with SessionLocal() as db:
        for model in (PipelineOperation, SessionEvent):
            db.query(model).filter_by(session_id='operation-test').delete()
        db.query(GenerationSessionDB).filter_by(id='operation-test').delete(); db.commit()

def test_single_writer_cas_event_and_terminal_control(session):
    from app.services.operation_repository import begin_operation, transition_operation, get_operation
    first=begin_operation(session, 'STORIES', {'autoDeploy': False, 'apiKey': 'sk-secret-example'})
    with pytest.raises(HTTPException) as error:
        begin_operation(session, 'CODE_TESTS', {})
    assert error.value.status_code == 409
    with pytest.raises(HTTPException) as error:
        transition_operation(first['operationId'], 0, 'RUNNING')
    assert error.value.status_code == 409
    running=transition_operation(first['operationId'], 1, 'RUNNING')
    paused_request=transition_operation(first['operationId'], running['version'], 'PAUSE_REQUESTED')
    paused=transition_operation(first['operationId'], paused_request['version'], 'PAUSED', checkpoint={'phase':'STORIES'})
    assert paused['checkpoint']['phase'] == 'STORIES'
    assert 'apiKey' not in paused['options']
    resumed=transition_operation(first['operationId'], paused['version'], 'RUNNING')
    finished=transition_operation(first['operationId'], resumed['version'], 'COMPLETED')
    with pytest.raises(HTTPException) as error:
        transition_operation(first['operationId'], finished['version'], 'CANCEL_REQUESTED')
    assert error.value.status_code == 409
    with SessionLocal() as db:
        event=db.query(SessionEvent).filter_by(session_id=session).order_by(SessionEvent.sequence.desc()).first()
        assert 'COMPLETED' in event.payload_json
        assert 'sk-secret-example' not in event.payload_json
    assert get_operation(session)['state'] == 'COMPLETED'

def test_recovery_does_not_replay_side_effects(session):
    from app.services.operation_repository import begin_operation, transition_operation, recover_interrupted, get_operation
    first=begin_operation(session, 'DEVOPS_DEPLOY', {'autoDeploy':True})
    transition_operation(first['operationId'], 1, 'RUNNING')
    assert recover_interrupted() >= 1
    assert get_operation(session)['state'] == 'INTERRUPTED'


def test_orphaned_legacy_operation_does_not_prevent_startup(session):
    from app.services.operation_repository import begin_operation,recover_interrupted
    first=begin_operation(session,'STORIES')
    with SessionLocal() as db:
        db.query(GenerationSessionDB).filter_by(id=session).delete();db.commit()
    assert recover_interrupted()>=1
    with SessionLocal() as db:
        row=db.get(PipelineOperation,first['operationId'])
        assert row.state=='INTERRUPTED' and row.error_code=='SESSION_MISSING'



def test_worker_releases_writer_even_if_session_disappears(session,monkeypatch):
    from app.services import pipeline_runner as runner
    from app.services.operation_repository import begin_operation
    from app.services.session_operation_lock import SessionOperationLock
    begin_operation(session,'STORIES')
    def disappear(*args):
        with SessionLocal() as db:
            db.query(GenerationSessionDB).filter_by(id=session).delete();db.commit()
    monkeypatch.setattr(runner,'_execute_pipeline_steps',disappear)
    runner._execute_pipeline_with_cost(session)
    lock=SessionOperationLock(session)
    assert lock.acquire(False)
    lock.release()
    assert session not in runner._worker_operations


def test_worker_completion_never_updates_replacement_operation(session,monkeypatch):
    from app.services import pipeline_runner as runner
    from app.services.operation_repository import begin_operation,get_operation,transition_operation
    first=begin_operation(session,'STORIES')
    replacement=[]
    def replace(*args):
        original=get_operation(session,first['operationId'])
        transition_operation(original['operationId'],original['version'],'COMPLETED')
        second=begin_operation(session,'CODE_TESTS')
        replacement.append(second['operationId'])
        runner._pipeline_statuses[session]=runner.PipelineRunStatus.COMPLETED
    monkeypatch.setattr(runner,'_execute_pipeline_steps',replace)
    runner._execute_pipeline_with_cost(session)
    assert get_operation(session,replacement[0])['state']=='QUEUED'


def test_cancelled_graph_request_keeps_lock_until_native_writer_unwinds(session,monkeypatch):
    import asyncio,threading
    from types import SimpleNamespace
    from app.api import routes_session
    from app.services.session_operation_lock import SessionOperationLock
    from app.services.operation_repository import get_operation
    from integration.reliability_fixtures import ledger_draft
    from app.config import settings
    from pathlib import Path
    started=threading.Event();released=threading.Event()
    def stream(state):
        started.set()
        assert released.wait(10)
        yield {'scaffolder':{'status':'BLOCKED','generated_files':{}}}
    monkeypatch.setattr(routes_session,'generation_graph',SimpleNamespace(stream=stream))
    async def scenario():
        task=asyncio.create_task(routes_session.execute_generation_pipeline(session,'graph-test','ledger-service',ledger_draft(), provider='mock'))
        for _ in range(200):
            if started.is_set(): break
            await asyncio.sleep(.01)
        assert started.is_set()
        task.cancel()
        await asyncio.sleep(.05)
        lock=SessionOperationLock(session)
        assert not lock.acquire(False), 'Request cancellation released a live writer'
        assert not task.done()
        released.set()
        with pytest.raises(asyncio.CancelledError): await task
        assert lock.acquire(False)
        lock.release()
        assert get_operation(session)['state']=='INTERRUPTED'
    try:
        asyncio.run(scenario())
    finally:
        released.set()

@pytest.mark.parametrize('step',['Error','Pausa','Cancel'])
def test_control_event_preserves_last_real_checkpoint(session,monkeypatch,step):
    from app.services.operation_repository import begin_operation,transition_operation,checkpoint_operation,get_operation
    from app.services import pipeline_runner as pipeline
    from app.models.orchestrator import LifecyclePhase,PhaseStatus
    operation=begin_operation(session,'COMPLETED')
    operation=transition_operation(operation['operationId'],operation['version'],'RUNNING')
    checkpoint_operation(operation['operationId'],operation['version'],'CODE_TESTS')
    monkeypatch.setattr(pipeline,'_worker_operations',{session:operation['operationId']})
    pipeline._emit_event(session,LifecyclePhase.INITIAL,step,0,'control',PhaseStatus.BLOCKED if step=='Error' else PhaseStatus.IN_PROGRESS)
    assert get_operation(session)['checkpoint']['phase']=='CODE_TESTS'
