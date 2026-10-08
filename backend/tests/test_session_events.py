import pytest
from fastapi import HTTPException
from app.models.session import SessionLocal, GenerationSessionDB
from app.models.reliability import SessionEvent

@pytest.fixture
def session():
    with SessionLocal() as db:
        db.add(GenerationSessionDB(id='events-test',spec_id='events-spec',spec_name='Events'));db.commit()
    yield 'events-test'
    with SessionLocal() as db:
        db.query(SessionEvent).filter_by(session_id='events-test').delete()
        db.query(GenerationSessionDB).filter_by(id='events-test').delete();db.commit()

def test_two_clients_replay_same_sequence_without_competing(session):
    from app.services.session_event_service import publish_event, read_events
    publish_event(session,'phase_transition', {'message':'hello','apiKey':'sk-secret-example','modifiedCode':'sensitive full source'})
    publish_event(session,'build_log', {'line':'second'})
    first=read_events(session,0);second=read_events(session,0)
    assert first == second
    assert [event['id'] for event in first] == ['1','2']
    assert 'sk-secret-example' not in str(first)
    assert 'sensitive full source' not in str(first)
    assert read_events(session,1) == first[1:]

def test_expired_or_future_cursor_requests_resync(session):
    from app.services.session_event_service import publish_event, read_events
    for index in range(4):
        publish_event(session,'build_log', {'line':str(index)}, retention=2)
    assert read_events(session,1)[0]['event'] == 'resync_required'
    assert read_events(session,100)[0]['event'] == 'resync_required'

def test_failure_to_persist_never_returns_success(session, monkeypatch):
    from app.services import session_event_service
    def failed(*args,**kwargs):
        raise RuntimeError('SQLite failure')
    monkeypatch.setattr(session_event_service,'append_event',failed)
    with pytest.raises(RuntimeError):
        session_event_service.publish_event(session,'build_log', {'line':'never published'})


def test_pipeline_progress_propagates_persistence_failure(session,monkeypatch):
    from app.services.pipeline_runner import _emit_event
    from app.models.orchestrator import LifecyclePhase,PhaseStatus
    from app.services import session_event_service
    def failed(*args,**kwargs): raise RuntimeError('SQLite unavailable')
    monkeypatch.setattr(session_event_service,'publish_event',failed)
    with pytest.raises(RuntimeError,match='SQLite unavailable'):
        _emit_event(session,LifecyclePhase.REQUIREMENTS,'Requirements',10,'unsaved',PhaseStatus.IN_PROGRESS)


def test_live_stream_subscribers_do_not_steal_events_and_resume_from_cursor(session):
    from app.services.session_event_service import publish_event,stream_events
    first,second=stream_events(session),stream_events(session)
    assert 'keepalive' in next(first) and 'keepalive' in next(second)
    event=publish_event(session,'build_log',{'message':'owned event'})
    assert next(first)==next(second)
    first.close()
    publish_event(session,'build_log',{'message':'while first disconnected'})
    assert 'while first disconnected' in next(second)
    reconnected=stream_events(session,int(event['id']))
    assert 'while first disconnected' in next(reconnected)
    second.close();reconnected.close()
