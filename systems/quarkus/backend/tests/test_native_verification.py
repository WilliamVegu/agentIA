import hashlib,json,zipfile
import pytest
from types import SimpleNamespace
from app.services.source_snapshot import SourceSnapshot,materialize_snapshot
from app.services.verification_policy import workspace_fingerprint

@pytest.mark.parametrize('dependency',['dependency.jar','io.quarkus.'+'long-native-dependency.'*8+'jar'])
def test_quarkus_fast_jar_retains_full_native_layout(tmp_path,dependency):
    from app.services.source_snapshot import _io_path
    ws=tmp_path/'native-q';ws.mkdir();(ws/'pom.xml').write_text('<project/>')
    snapshot=SourceSnapshot(ws)
    try:
        artifact=snapshot.working/'target/quarkus-app';(artifact/'lib/main').mkdir(parents=True)
        with zipfile.ZipFile(artifact/'quarkus-run.jar','w') as jar:
            jar.writestr('META-INF/MANIFEST.MF','Manifest-Version: 1.0\nMain-Class: io.quarkus.bootstrap.runner.QuarkusEntryPoint\n')
        _io_path(artifact/'lib/main'/dependency).write_bytes(b'preserved dependency')
        report=snapshot.working/'target/surefire-reports/TEST-native.xml';report.parent.mkdir(parents=True)
        report.write_text('<testsuite tests="1" failures="0" errors="0" skipped="0"><testcase name="native"/></testsuite>')
        result=SimpleNamespace(stdout='Tests run: 1, Failures: 0, Errors: 0, Skipped: 0',is_success=True,exit_code=0,fallback_used=False,verification_skipped=False,verification_interrupted=False,evidence_error=None)
        snapshot.finish(result,False)
        assert snapshot.manifest['artifactLayout']=='quarkus-fast-jar'
        assert len(snapshot.manifest['nativeArtifacts'])==2
        with materialize_snapshot(ws,snapshot.id,workspace_fingerprint(ws)) as (materialized,digest):
            assert _io_path(materialized/'.verified-artifact/quarkus-app/lib/main'/dependency).read_bytes()==b'preserved dependency'
            assert len(digest)==64
    finally: snapshot.close()


def test_graph_never_invents_test_counts(tmp_path,monkeypatch):
    from app.orchestrator.nodes import sandbox_node as module
    from app.sandbox.docker_runner import DockerExecutionResult
    result=DockerExecutionResult(exit_code=0,stdout='BUILD SUCCESS')
    async def legacy(*args,**kwargs): return result
    monkeypatch.setattr(module,'run_docker_sandbox',legacy,raising=False)
    verification=SimpleNamespace(result=result,platform_verified=False,workspace_fingerprint='fixture',snapshot_id=None,source_changed=False)
    monkeypatch.setattr(module,'run_workspace_verification',lambda *a,**k:verification,raising=False)
    output=module.sandbox_node({'workspace_path':str(tmp_path),'logs':[]})
    assert output['test_metrics']['totalTests']==0
    assert not output['build_success']
    assert output['status']=='BLOCKED'
