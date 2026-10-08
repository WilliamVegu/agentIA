"""Graph repairs share the persistent three-attempt budget with API repairs."""
import json
from fastapi import HTTPException
from app.models.session import SessionLocal,GenerationSessionDB,SessionPhase,SessionStatus
from app.models.reliability import RepairAttempt
from app.models.test_analysis import FailureDiagnostic,DiagnosticCategory,DiagnosticSeverity,RepairExecutionRequest
from app.services.automatic_repair_service import automatic_repair
from app.services.workspace_guard import resolve_workspace_file,io_path
from app.services.secret_redaction import redact


def repair_node(state):
    session_id=state.get('session_id')
    logs=list(state.get('logs',[]))
    try:
        with SessionLocal() as db:
            if not db.get(GenerationSessionDB,session_id): raise HTTPException(404,'Session not found')
            count=db.query(RepairAttempt).filter_by(session_id=session_id,automatic=1).count()
        if count>=3: raise HTTPException(409,'Maximum repair attempts (3) exhausted. Human intervention required.')
        raw=state.get('last_diagnostic') or {}
        diagnostics=[]
        if isinstance(raw,FailureDiagnostic): diagnostics=[raw]
        elif raw:
            diagnostics=[FailureDiagnostic(id='GRAPH-'+str(count+1),
                category=DiagnosticCategory.COMPILATION_ERROR if 'compil' in str(raw.get('error_type','')).lower() else DiagnosticCategory.ASSERTION_FAILURE,
                severity=DiagnosticSeverity.HIGH,filePath=raw.get('failed_file') or raw.get('filePath','unknown'),
                errorSummary=raw.get('summary') or raw.get('errorSummary','Sandbox build or test failure'),
                lineNumber=raw.get('line_number') or raw.get('lineNumber'),rawStackTrace=raw.get('raw_trace',''))]
        request=RepairExecutionRequest(sessionId=session_id,iterationNumber=count+1,diagnostics=diagnostics,
            sourceFiles=state.get('generated_files',{}),provider=state.get('llm_provider'),modelName=state.get('llm_model'))
        record=automatic_repair(request,framework='quarkus',effective_key=state.get('llm_api_key'),_operation_id=state.get('repair_operation_id'))
        generated={relative:io_path(resolve_workspace_file(session_id,relative,require_exists=True)).read_text(encoding='utf-8') for relative in request.sourceFiles}
        with SessionLocal() as db:
            session=db.get(GenerationSessionDB,session_id)
            metrics=json.loads(session.verification_metrics_json or '{}')
        verified=record.outcome.value=='SUCCESS'
        blocked=not verified and count+1>=3
        logs.append('[REPAIR] Intento persistido '+str(count+1)+'/3; '+record.outcome.value)
        return {'repair_attempts':count+1,'max_repair_attempts':3,'build_success':verified,
            'status':SessionStatus.COMPLETED.value if verified else SessionStatus.BLOCKED.value if blocked else SessionStatus.RUNNING.value,
            'current_phase':SessionPhase.VERIFIED.value if verified else SessionPhase.FAILED.value if blocked else SessionPhase.SELF_REPAIR_LOOP.value,
            'test_metrics':metrics,'generated_files':generated,'diff_summary':record.diffSummary,
            'error':None if verified else 'Maximum repair attempts (3) exhausted. Human intervention required.' if blocked else None,'logs':logs}
    except HTTPException as error:
        message=redact(str(error.detail))
        logs.append('[REPAIR] '+message)
        return {'status':SessionStatus.BLOCKED.value,'current_phase':SessionPhase.FAILED.value,
            'build_success':False,'error':message,'max_repair_attempts':3,'logs':logs}
