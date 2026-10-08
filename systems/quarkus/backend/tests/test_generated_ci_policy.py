"""Execute generated CI checks and reject adversarial reports without remote execution."""
import json,runpy,subprocess,sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from app.services.local_ci_assets import AUDIT_SCRIPT

@pytest.mark.parametrize('unsafe,rule',[
    ('class Safe {}',None),
    ('class Unsafe { String key="sk-'+ 'sentinel'*6 +'"; }','OPENAI_KEY'),
    ('class Unsafe { void query() { em.createNativeQuery("SELECT * FROM x WHERE id=" + input); } }','SQL_CONCATENATION'),
])
def test_real_source_checks(tmp_path,unsafe,rule):
    script=tmp_path/'local-ci.py';script.write_text(AUDIT_SCRIPT,encoding='utf-8')
    source=tmp_path/'src/main/java/Example.java';source.parent.mkdir(parents=True);source.write_text(unsafe,encoding='utf-8')
    process=subprocess.run([sys.executable,str(script)],cwd=tmp_path,capture_output=True,text=True,timeout=15)
    report=json.loads((tmp_path/'.agentia-runtime/local-ci-result.json').read_text())
    assert process.returncode==(1 if rule else 0)
    assert report['tests']=='NOT_EXECUTED'
    assert report['imageVulnerabilities']=='NOT_EXECUTED'
    assert report['staticAudit']==('FAILED' if rule else 'PASSED')
    if rule: assert any(item['rule']==rule for item in report['findings'])
    assert 'sentinelsentinel' not in json.dumps(report)+process.stdout+process.stderr


@pytest.mark.parametrize('tests,failed,expected',[(0,0,1),(2,1,1),(2,0,0)])
def test_ci_rejects_empty_and_failing_real_junit_xml(tmp_path,monkeypatch,tests,failed,expected):
    script=tmp_path/'local-ci.py';script.write_text(AUDIT_SCRIPT,encoding='utf-8')
    (tmp_path/'Dockerfile').write_text('FROM prepared:1 AS build\nFROM runtime:1\n')
    (tmp_path/'ASSET_CONFIGURATION.json').write_text(json.dumps({'buildDirectory':'.','buildTool':'maven'}))
    source=tmp_path/'src/main/java/Example.java';source.parent.mkdir(parents=True);source.write_text('class Example {}')
    module=runpy.run_path(str(script));commands=[];token=None
    def boundary(arguments,**kwargs):
        nonlocal token
        commands.append(arguments)
        if arguments[1]=='build':
            token=arguments[arguments.index('--label')+1].split('=',1)[1]
        if arguments[1]=='cp' and 'surefire-reports' in arguments[2]:
            destination=Path(arguments[3]);destination.mkdir(parents=True,exist_ok=True)
            (destination/'TEST-real.xml').write_text(f'<testsuite tests="{tests}" failures="{failed}" errors="0" skipped="0"/>')
        if '--format' in arguments:
            output=token if 'io.agentia.ci' in arguments[-1] else 'sha256:'+'a'*64
        elif arguments[1]=='create': output='b'*64
        else: output=''
        return SimpleNamespace(stdout=output,returncode=0)
    monkeypatch.setattr(subprocess,'run',boundary)
    monkeypatch.setattr(sys,'argv',[str(script),'--docker'])
    assert module['main']()==expected
    report=json.loads((tmp_path/'.agentia-runtime/local-ci-result.json').read_text())
    assert report['tests']==('PASSED' if expected==0 else 'FAILED')
    build=next(command for command in commands if command[1]=='build')
    assert '--network=none' in build and '--pull=false' in build
    assert report['cleanup']=='CONFIRMED'
