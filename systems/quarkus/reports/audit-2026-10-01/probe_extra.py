"""Additional HTTP probes; only audit workspaces are modified."""
import io
import json
import os
import time
import zipfile
from pathlib import Path
import httpx

OUT = Path(__file__).resolve().parent
KEY = os.environ["AUDIT_DEEPSEEK_KEY"]
HEADERS = {"X-LLM-API-Key":KEY,"X-LLM-Provider":"deepseek"}
C = httpx.Client(base_url="http://127.0.0.1:8011",timeout=300)
RESULTS = []
def call(name,method,url,payload=None,auth=False):
    t = time.monotonic()
    r = C.request(method,url,json=payload,headers=HEADERS if auth else {})
    try:
        data=r.json()
    except ValueError:
        if r.headers.get('content-type')=='application/zip':
            data={'zipFiles':zipfile.ZipFile(io.BytesIO(r.content)).namelist()}
        else:
            data=r.text[:2000]
    data=json.loads(json.dumps(data).replace(KEY,'[REDACTED]'))
    item={'name':name,'status':r.status_code,'seconds':round(time.monotonic()-t,2),'response':data}
    RESULTS.append(item)
    (OUT/'extra-results.json').write_text(json.dumps(RESULTS,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:item[k] for k in ['name','status','seconds']}),flush=True)
    return data

# Alternative product entry point: actual DeepSeek-authored blueprint, actual graph stages.
draft=json.loads((OUT/'draft.json').read_text(encoding='utf8'))
blueprint={k:draft[k] for k in ['serviceName','packageName','basePort','entities','userStories']}
blueprint['databaseMode']='H2'
blueprint['inputInterface']={'requestVolume':'high','architecturePreference':'hexagonal','buildToolPreference':'gradle','dataNeeds':['relational']}
spec=call('ingest_real_blueprint','POST','/api/v1/specifications',blueprint,True)
if 'specId' in spec:
    session=call('start_real_graph','POST','/api/v1/sessions',{'specId':spec['specId']},True)
    (OUT/'graph-session.json').write_text(json.dumps(session,indent=2),encoding='utf8')

# Quality-gate witness uses a security-test input, never purported AI-generated code.
security_session=call('create_security_probe','POST','/api/v1/sessions/quick-start',
                     {'service_name':'audit-security-probe','prompt':'Un servicio registra informacion de auditoria.','auto_run':False},True)
sid=security_session['sessionId']
ws=OUT/'runtime'/'workspaces'/sid
(ws/'VulnerableController.java').write_text('public class VulnerableController {\n private BookRepository bookRepository;\n}\n',encoding='utf8')
call('security_probe_audit','GET',f'/api/v1/sessions/{sid}/audit')
call('gated_export','GET',f'/api/v1/sessions/{sid}/export')
call('bundle_export_bypasses_gate','GET',f'/api/v1/orchestrator/sessions/{sid}/export-bundle')
call('security_remediate_absolute_read','POST','/api/v1/security/remediate',
     {'findingId':'audit-unsupported','filePath':str(OUT/'runtime'/'outside-sentinel.txt')})
call('empty_security_audit','POST','/api/v1/security/audit',{'files':{},'pomXml':''})
call('undeployed_playground','POST',f'/api/v1/devops/{sid}/playground',{'method':'GET','path':'/api/books'})
call('devops_generate_h2','POST',f'/api/v1/devops/{sid}/generate',{'databaseEngine':'H2'})
call('unknown_models_save','POST','/api/v1/models/sessions/audit-nonexistent/save',{'auditSentinel':True})
print('Additional probes complete',flush=True)
