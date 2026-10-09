"""Opt-in native regression: removing validation must break the HTTP contract."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

import pytest

from integration.generated_domain_matrix import fixture_fingerprint
from integration.reliability_fixtures import ROOT, assert_isolated
from integration.test_generated_domain import http_contract


@pytest.mark.skipif(os.getenv('AGENTIA_VALIDATION_MUTATION') != '1', reason='Requires explicit owned Docker opt-in and prepared Maven artifacts')
@pytest.mark.parametrize('framework', ['springboot', 'quarkus'])
def test_removed_validation_breaks_native_contract(framework):
    source=assert_isolated(ROOT/'.runtime/reliability/current-matrix/java'/('relational-'+framework+'-maven-h2'))
    before=fixture_fingerprint(source)
    workspace=assert_isolated(ROOT/'.runtime/reliability/validation-mutation'/(framework+'-'+uuid.uuid4().hex[:8]))
    shutil.copytree(source,workspace,ignore=shutil.ignore_patterns('target','build','.git','.gradle'))
    dto=next(workspace.rglob('CreateLedgerEntryRequest.java'))
    original=dto.read_text(encoding='utf-8')
    evidence={'framework':framework,'sourceFingerprint':before,'liveProviderCalls':0,'mutations':[],'outcome':'FAILED'}
    output=ROOT/'integration/validation/reliability'/('validation-mutation-'+framework+'.json')
    try:
        for annotation in ('@Email','@Positive',None):
            import integration.test_generated_domain as native_http
            native_http.EVIDENCE=ROOT/'integration/validation/reliability/validation-mutation-http'/framework/(annotation or 'restored').replace('@','')
            native_http.EVIDENCE.mkdir(parents=True,exist_ok=True)
            assert annotation is None or annotation in original
            dto.write_text(original if annotation is None else original.replace(annotation,''),encoding='utf-8')
            name='agentia-reliability-mutation-'+uuid.uuid4().hex[:12]
            log=output.with_name('validation-mutation-'+framework+'-'+(annotation or 'restored').replace('@','')+'.log')
            command=['docker','run','--rm','--pull','never','--network','none','--name',name,
                '--label','agentia.reliability-test='+name,'--mount','type=bind,source='+str(workspace)+',target=/workspace',
                '--mount','type=bind,source='+str(ROOT/'.runtime/reliability/java/cache/m2')+',target=/root/.m2/repository',
                '-w','/workspace','maven:3.9-eclipse-temurin-21','mvn','-B','-ntp','package','-o','-DskipTests']
            with log.open('w',encoding='utf-8') as stream:
                built=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,timeout=300)
            assert built.returncode==0, 'Mutation fixture build failed: '+str(log)
            try:
                result=http_contract(framework,workspace,'maven','H2',extended=True)
            except AssertionError as error:
                assert annotation is not None, 'Restored validation failed: '+str(error)
                field='email' if annotation=='@Email' else 'balance'
                observed=json.loads((native_http.EVIDENCE/('http-relational-'+framework+'-maven-h2.json')).read_text(encoding='utf-8'))
                check=observed['checks'][-1]
                assert check['check'].startswith('invalid-'+field+'-') and check['status'] in (201,500),error
                evidence['mutations'].append({'removed':annotation,'outcome':'EXPECTED_REJECTION','observedStatus':check['status'],'expectedStatus':400})
            else:
                assert annotation is None, 'Contract accepted missing '+annotation
                assert result['outcome']=='PASSED'
                evidence['restoredContract']='PASSED'
        assert fixture_fingerprint(source)==before
        evidence['outcome']='PASSED'
    finally:
        dto.write_text(original,encoding='utf-8')
        evidence['sourceUnchanged']=fixture_fingerprint(source)==before
        output.write_text(json.dumps(evidence,indent=2),encoding='utf-8')
