import json
from pathlib import Path
import httpx

OUT=Path(__file__).resolve().parent
sid=json.loads((OUT/'graph-session.json').read_text(encoding='utf8'))['sessionId']
specid=json.loads((OUT/'graph-state.json').read_text(encoding='utf8'))['http']['specId']
C=httpx.Client(base_url='http://127.0.0.1:8011',timeout=30)
results={}
for name,url in [('state','/api/v1/sessions/'+sid),('metrics','/api/v1/sessions/'+sid+'/metrics'),('overview','/api/v1/orchestrator/sessions/'+sid+'/overview'),('specification','/api/v1/specifications/'+specid),('repairs','/api/v1/sessions/'+sid+'/repairs')]:
    r=C.get(url)
    results[name]={'status':r.status_code,'response':r.json()}
(OUT/'restart-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
print('STATE',json.dumps(results['state']['response']))
print('METRICS',json.dumps(results['metrics']['response']))
print('TESTS_PASSED',results['overview']['response']['testsPassed'])
print('SPEC_PERSISTED',results['specification']['status'])
