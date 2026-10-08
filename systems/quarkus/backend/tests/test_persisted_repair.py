import json
import pytest
from fastapi import HTTPException
from test_draft_authority import session
from app.models.session import SessionLocal,GenerationSessionDB
from app.models.reliability import RepairAttempt
from app.models.test_analysis import RepairExecutionRequest


def test_three_attempt_limit_survives_process_memory_reset(session,monkeypatch):
    from app.services.automatic_repair_service import automatic_repair
    from app.services.workspace_guard import atomic_write_workspace_file
    atomic_write_workspace_file('draft-authority','src/App.java','class App {}')
    with SessionLocal() as db:
        for number in range(1,4):
            db.add(RepairAttempt(session_id='draft-authority',relative_path='src/App.java',automatic=1,iteration=number,outcome='FAILED_BLOCKED'))
        db.commit()
    request=RepairExecutionRequest(sessionId='draft-authority',iterationNumber=1,diagnostics=[],sourceFiles={'src/App.java':'class App {}'})
    with pytest.raises(HTTPException) as error: automatic_repair(request)
    assert error.value.status_code==409


def test_stale_sources_do_not_plan_or_write_repairs(session):
    from app.services.automatic_repair_service import automatic_repair
    from app.services.workspace_guard import atomic_write_workspace_file
    atomic_write_workspace_file('draft-authority','src/App.java','class App {}')
    request=RepairExecutionRequest(sessionId='draft-authority',iterationNumber=1,diagnostics=[],sourceFiles={'src/App.java':'class Old {}'})
    with pytest.raises(HTTPException) as error: automatic_repair(request)
    assert error.value.status_code==409
    with SessionLocal() as db: assert db.query(RepairAttempt).filter_by(session_id='draft-authority',automatic=1).count()==0


def test_unexecuted_repair_is_not_verified_and_history_survives_memory_reset(session,monkeypatch):
    from types import SimpleNamespace
    from app.services.automatic_repair_service import automatic_repair,repair_history
    from app.services.workspace_guard import atomic_write_workspace_file
    from app.services.test_analysis_service import test_analysis_service
    from app.models.test_analysis import RepairIterationRecord,RepairOutcome,CodeRepairPatch
    from app.sandbox.docker_runner import DockerExecutionResult
    from app.services import workspace_verification
    atomic_write_workspace_file('draft-authority','src/App.java','class Old {}')
    record=RepairIterationRecord(iterationNumber=1,diagnostics=[],patchesApplied=[CodeRepairPatch(id='fixture',filePath='src/App.java',originalSnippet='class Old {}',replacementSnippet='class New {}',explanation='Fixture edit')],outcome=RepairOutcome.SUCCESS)
    monkeypatch.setattr(test_analysis_service,'execute_repair_iteration',lambda **kwargs:record)
    skipped=SimpleNamespace(result=DockerExecutionResult(exit_code=1,verification_skipped=True,fallback_used=True),workspace_fingerprint='fixture',snapshot_id=None,source_changed=False)
    monkeypatch.setattr(workspace_verification,'run_workspace_verification',lambda *a,**k:skipped)
    request=RepairExecutionRequest(sessionId='draft-authority',iterationNumber=1,diagnostics=[],sourceFiles={'src/App.java':'class Old {}'})
    response=automatic_repair(request)
    assert response.outcome!=RepairOutcome.SUCCESS
    assert (session/'src/App.java').read_text()=='class New {}'
    from app.api.routes_tests import REPAIR_HISTORIES_STORE
    REPAIR_HISTORIES_STORE.clear()
    restored=repair_history('draft-authority')
    assert restored.totalIterations==1
    assert restored.finalState=='BLOCKED'
    assert len(restored.iterations)==1 and restored.iterations[0].outcome!=RepairOutcome.SUCCESS



def test_graph_and_api_share_persistent_budget_despite_zero_memory_counter(session,monkeypatch):
    from types import SimpleNamespace
    from app.services.automatic_repair_service import automatic_repair,repair_history
    from app.services.workspace_guard import atomic_write_workspace_file
    from app.services.test_analysis_service import test_analysis_service
    from app.models.test_analysis import RepairIterationRecord,RepairOutcome
    from app.sandbox.docker_runner import DockerExecutionResult
    from app.services import workspace_verification
    from app.services.operation_repository import begin_operation,transition_operation
    from app.services.session_operation_lock import SessionOperationLock
    from app.orchestrator.nodes.repair_node import repair_node
    atomic_write_workspace_file('draft-authority','src/App.java','class App {}')
    calls=[]
    def plan(**options):
        calls.append(options['iteration_number'])
        return RepairIterationRecord(iterationNumber=options['iteration_number'],diagnostics=[],patchesApplied=[],outcome=RepairOutcome.FAILED_CONTINUE)
    monkeypatch.setattr(test_analysis_service,'execute_repair_iteration',plan)
    skipped=SimpleNamespace(result=DockerExecutionResult(exit_code=1,verification_skipped=True,fallback_used=True),workspace_fingerprint='fixture',snapshot_id=None,source_changed=False)
    monkeypatch.setattr(workspace_verification,'run_workspace_verification',lambda *a,**k:skipped)
    request=RepairExecutionRequest(sessionId='draft-authority',iterationNumber=1,diagnostics=[],sourceFiles={'src/App.java':'class App {}'})
    automatic_repair(request)
    operation=begin_operation('draft-authority','CODE_TESTS',{'entryPoint':'GRAPH'})
    transition_operation(operation['operationId'],operation['version'],'RUNNING')
    lock=SessionOperationLock('draft-authority')
    assert lock.acquire(False)
    state={'session_id':'draft-authority','repair_operation_id':operation['operationId'],'generated_files':request.sourceFiles,'repair_attempts':0,'max_repair_attempts':100,'logs':[]}
    try:
        second=repair_node(state)
        assert second['repair_attempts']==2
        third=repair_node(state)
        assert third['repair_attempts']==3 and third['status']=='BLOCKED'
        fourth=repair_node(state)
        assert fourth['status']=='BLOCKED'
        assert calls==[1,2,3]
        assert lock.locked(), 'A graph repair must not release its parent writer lock'
        assert repair_history('draft-authority').totalIterations==3
    finally:
        lock.release()


def test_graph_repair_rejects_foreign_operation_before_planning(session,monkeypatch):
    from app.services.workspace_guard import atomic_write_workspace_file
    from app.services.operation_repository import begin_operation,transition_operation
    from app.services.session_operation_lock import SessionOperationLock
    from app.orchestrator.nodes.repair_node import repair_node
    from app.services.test_analysis_service import test_analysis_service
    atomic_write_workspace_file('draft-authority','src/App.java','class App {}')
    operation=begin_operation('draft-authority','CODE_TESTS',{'entryPoint':'GRAPH'})
    transition_operation(operation['operationId'],operation['version'],'RUNNING')
    monkeypatch.setattr(test_analysis_service,'execute_repair_iteration',lambda **kw:pytest.fail('Stale operation must not plan a patch'))
    lock=SessionOperationLock('draft-authority');assert lock.acquire(False)
    try:
        result=repair_node({'session_id':'draft-authority','repair_operation_id':'obsolete','generated_files':{'src/App.java':'class App {}'},'logs':[]})
        assert result['status']=='BLOCKED'
        with SessionLocal() as db: assert db.query(RepairAttempt).filter_by(session_id='draft-authority').count()==0
    finally: lock.release()
