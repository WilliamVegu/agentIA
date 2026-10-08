import pytest
from app.services.security_service import audit_workspace

@pytest.mark.parametrize('metrics', [
 {'totalTests':0,'passedTests':0,'failedTests':0,'allPassed':True,'fallback_used':False},
 {'totalTests':1,'passedTests':1,'failedTests':0,'allPassed':True,'fallback_used':True},
 {'totalTests':1,'passedTests':1,'failedTests':0,'allPassed':True,'fallback_used':False,'verificationInterrupted':True},
 {'totalTests':1,'passedTests':1,'failedTests':0,'allPassed':True,'fallback_used':False,'verificationSkipped':True},
 {'totalTests':1,'passedTests':1,'failedTests':0,'allPassed':True,'fallback_used':False,'evidenceError':'missing report'},
])
def test_unexecuted_or_unreliable_evidence_never_passes(metrics):
    from app.services.verification_policy import tests_really_passed
    assert not tests_really_passed(metrics)

def test_empty_audit_is_blocked_with_no_fictional_score(tmp_path):
    report=audit_workspace(str(tmp_path), 'not-a-session')
    assert report.qualityGate.status == 'BLOCKED'
    assert report.qualityGate.score is None
    assert not report.qualityGate.canExport
    assert report.metrics.totalLinesOfCode == 0
