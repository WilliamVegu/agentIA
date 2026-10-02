"""Verify consistency of the real generated session after unavailable sandbox."""
import io
import json
import zipfile
from pathlib import Path
import httpx

OUT=Path(__file__).resolve().parent
sid=json.loads((OUT/'graph-session.json').read_text(encoding='utf8'))['sessionId']
C=httpx.Client(base_url='http://127.0.0.1:8011',timeout=30)
results=[]
def call(name,method,url,data=None):
    r=C.request(method,url,json=data)
    try:
        payload=r.json()
    except ValueError:
        payload={'zipFiles':zipfile.ZipFile(io.BytesIO(r.content)).namelist()} if 'application/zip' in r.headers.get('content-type','') else r.text[:3000]
    record={'name':name,'status':r.status_code,'response':payload}
    results.append(record)
    (OUT/'final-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'name':name,'http':r.status_code,'response':payload if name not in ['overview_before','overview_after','generate_devops_real','list_promotes_blocked'] else 'see final-results.json'},ensure_ascii=True),flush=True)
    return payload

state=call('state_before','GET',f'/api/v1/sessions/{sid}')
if state['status']=='RUNNING':
    raise SystemExit('Generation still running; retry after completion')
call('overview_before','GET',f'/api/v1/orchestrator/sessions/{sid}/overview')
call('metrics_before','GET',f'/api/v1/sessions/{sid}/metrics')
call('generate_devops_real','POST',f'/api/v1/devops/{sid}/generate',{'databaseEngine':'H2'})
call('overview_after','GET',f'/api/v1/orchestrator/sessions/{sid}/overview')
call('list_promotes_blocked','GET','/api/v1/sessions')
call('state_after_list','GET',f'/api/v1/sessions/{sid}')
call('metrics_after_list','GET',f'/api/v1/sessions/{sid}/metrics')
call('repairs_real_graph','GET',f'/api/v1/sessions/{sid}/repairs')
call('export_unverified','GET',f'/api/v1/sessions/{sid}/export')
