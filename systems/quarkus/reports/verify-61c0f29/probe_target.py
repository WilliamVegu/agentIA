"""Verify target-phase completion with real DeepSeek and isolated session storage."""
import json,os,time
from pathlib import Path
import httpx
OUT=Path(__file__).resolve().parent
key=os.environ['AUDIT_DEEPSEEK_KEY']
C=httpx.Client(base_url='http://127.0.0.1:8011',timeout=90)
headers={'X-LLM-Provider':'deepseek','X-LLM-API-Key':key}
session=C.post('/api/v1/sessions/quick-start',json={'service_name':'audit-target-stories','prompt':'Un servicio de biblioteca registra libros con ISBN unico, titulo y autor; permite consultar, actualizar y eliminar libros. Valida titulo no vacio y devuelve 404 para libros inexistentes.','auto_run':False}).json()
sid=session['sessionId']
r=C.post('/api/v1/orchestrator/pipeline/run',headers=headers,json={'sessionId':sid,'provider':'deepseek','apiKey':key,'model':'deepseek-flash','targetPhase':'STORIES','autoDeploy':False,'stopOnGate':True})
results={'sessionId':sid,'start_status':r.status_code,'observations':[]}
for _ in range(30):
    time.sleep(5)
    state=C.get('/api/v1/sessions/'+sid).json();results['observations'].append(state)
    if state['status'] not in ['RUNNING','QUEUED']: break
for name,url in [('metrics','/api/v1/sessions/'+sid+'/metrics'),('repairs','/api/v1/sessions/'+sid+'/repairs'),('overview','/api/v1/orchestrator/sessions/'+sid+'/overview')]:
    res=C.get(url);results[name]={'status':res.status_code,'response':res.json()}
results['files']=[str(p.relative_to(OUT/'runtime/workspaces'/sid)) for p in (OUT/'runtime/workspaces'/sid).rglob('*') if p.is_file()]
(OUT/'target-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2).replace(key,'[REDACTED]'),encoding='utf8')
print('TARGET_STATUS',state['status'],state['phase'],flush=True)
print('METRICS',results['metrics']['response'],flush=True)
print('REPAIRS',results['repairs']['response'],flush=True)
print('FILES',results['files'],flush=True)
