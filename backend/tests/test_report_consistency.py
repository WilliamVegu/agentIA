from types import SimpleNamespace
from app.services.source_snapshot import SourceSnapshot


def test_stdout_cannot_override_failed_xml_report(tmp_path):
    (tmp_path/'pom.xml').write_text('<project/>')
    snapshot=SourceSnapshot(tmp_path)
    try:
        report=snapshot.working/'target/surefire-reports/TEST-fixture.xml'
        report.parent.mkdir(parents=True)
        report.write_text('<testsuite tests="1" failures="1" errors="0" skipped="0"/>')
        result=SimpleNamespace(stdout='Tests run: 1, Failures: 0, Errors: 0, Skipped: 0',is_success=True,exit_code=0,fallback_used=False,verification_skipped=False,verification_interrupted=False,evidence_error=None)
        snapshot.finish(result,False)
        assert snapshot.manifest['verification']!='PASSED'
        assert result.evidence_error
    finally: snapshot.close()


from test_draft_authority import session


def test_audit_survives_memory_reset_with_standards_findings_and_gate(session):
    from app.services.security_service import audit_workspace
    from app.services.verification_evidence import current_audit
    from app.services.workspace_guard import atomic_write_workspace_file
    atomic_write_workspace_file('draft-authority','src/App.java','public class App { public String getValue() { return "x"; } }')
    report=audit_workspace(str(session),'draft-authority','fixture')
    assert report.violations, 'Fixture must actually exercise standards findings'
    restored=current_audit('draft-authority',session)
    assert restored is not None
    assert restored.model_dump()==report.model_dump()
    (session/'security_audit_report.json').write_text('{"qualityGate":{"status":"PASS","canExport":true}}',encoding='utf-8')
    assert current_audit('draft-authority',session).qualityGate.canExport==report.qualityGate.canExport
    atomic_write_workspace_file('draft-authority','src/App.java','public class App { public String getValue() { return "changed"; } }')
    assert current_audit('draft-authority',session) is None
