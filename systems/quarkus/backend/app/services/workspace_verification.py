"""Quarkus verification executes a sealed copy and retains native evidence."""
import asyncio
import concurrent.futures
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import xml.etree.ElementTree as ET
from app.sandbox.docker_runner import DockerExecutionResult, run_docker_sandbox
from app.models.execution import ExecutionMode
from app.services.execution_policy import execution_mode
from app.services.verification_policy import workspace_fingerprint
from app.config import settings

@dataclass(frozen=True)
class WorkspaceVerification:
    result: DockerExecutionResult
    platform_test_path: Optional[str]=None
    stripped: tuple=()
    workspace_fingerprint: Optional[str]=None
    source_changed: bool=False
    snapshot_id: Optional[str]=None

    @property
    def platform_verified(self):
        return self.platform_test_path is not None


def blocking_sandbox(path, log_callback):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(run_docker_sandbox(path, log_callback=log_callback))
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return pool.submit(asyncio.run, run_docker_sandbox(path, log_callback=log_callback)).result()


def run_workspace_verification(workspace_path, log_callback=None, mode=None):
    ws=Path(workspace_path).resolve()
    selected=execution_mode(workspace_path=ws, explicit=mode)
    fingerprint=workspace_fingerprint(ws)
    if selected == ExecutionMode.SOURCE_ONLY:
        (ws/'VERIFICATION_STATUS.md').write_text('# Estado de verificación\n\nNO EJECUTADOS por elección SOURCE_ONLY. Auditoría de fuentes separada.\n', encoding='utf-8')
        verification=WorkspaceVerification(DockerExecutionResult(exit_code=1, fallback_used=True,
            verification_skipped=True, fallback_reason='SOURCE_ONLY elegido explícitamente'),workspace_fingerprint=fingerprint)
    elif not settings.DOCKER_ENABLED:
        verification=WorkspaceVerification(DockerExecutionResult(exit_code=1, fallback_used=True,
            fallback_reason='Docker elegido pero deshabilitado'),workspace_fingerprint=fingerprint)
    else:
        from app.services.source_snapshot import SourceSnapshot
        snapshot=SourceSnapshot(ws)
        try:
            from app.services.platform_verification import inject_contract_test
            platform_test=inject_contract_test(str(snapshot.working))
            result=blocking_sandbox(str(snapshot.working), log_callback)
            totals=[0,0,0,0];reports=[]
            for path in snapshot.working.rglob('*.xml'):
                if 'surefire-reports' not in path.parts and 'test-results' not in path.parts:
                    continue
                if path.is_symlink() or not path.resolve().is_relative_to(snapshot.working):
                    result.evidence_error='Informe enlazado';continue
                reports.append(path)
                try:
                    root=ET.parse(path).getroot()
                    for suite in ([root] if root.tag=='testsuite' else root.findall('testsuite')):
                        values=[int(suite.get(key,'0')) for key in ['tests','failures','errors','skipped']]
                        if any(value<0 for value in values):
                            raise ValueError('Conteos negativos')
                        totals=[a+b for a,b in zip(totals,values)]
                except (ValueError, ET.ParseError, OSError):
                    result.evidence_error='Informe de pruebas inválido'
            if not result.fallback_used:
                if not reports or totals[0] == 0:
                    result.evidence_error='No existe suite no vacía con informe XML'
                result.stdout += '\nTests run: %d, Failures: %d, Errors: %d, Skipped: %d\n' % tuple(totals)
            changed=workspace_fingerprint(ws)!=fingerprint
            if changed or result.evidence_error:
                result.exit_code=result.exit_code or 1
            snapshot.finish(result, changed)
            verification=WorkspaceVerification(result,platform_test_path=platform_test,workspace_fingerprint=fingerprint,source_changed=changed,snapshot_id=snapshot.id)
        finally:
            snapshot.close()
    from app.services.verification_evidence import record_verification
    record_verification(ws.name,verification,'quarkus-offline')
    return verification
