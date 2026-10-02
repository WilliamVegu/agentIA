"""Cancel a real DeepSeek graph run and observe whether work actually stops."""
import json
import os
import time
from pathlib import Path
import httpx

OUT=Path(__file__).resolve().parent
specid=json.loads((OUT/'graph-state.json').read_text(encoding='utf8'))['http']['specId']
KEY=os.environ['AUDIT_DEEPSEEK_KEY']
C=httpx.Client(base_url='http://127.0.0.1:8011',timeout=30)
res=C.post('/api/v1/sessions',json={'specId':specid},headers={'X-LLM-Provider':'deepseek','X-LLM-API-Key':KEY}).json()
sid=res['sessionId']
time.sleep(1)
before=C.get(f'/api/v1/sessions/{sid}').json()
cancel=C.delete(f'/api/v1/sessions/{sid}')
immediate=C.get(f'/api/v1/sessions/{sid}').json()
data={'sessionId':sid,'before':before,'cancelHttpStatus':cancel.status_code,'immediate':immediate,'observations':[]}
def save():
    (OUT/'cancel-results.json').write_text(json.dumps(data,indent=2),encoding='utf8')
save()
print('CANCEL_REQUEST '+json.dumps({'http':cancel.status_code,'before':before['status'],'immediate':immediate['status']}),flush=True)
ws=OUT/'runtime'/'workspaces'/sid
start=time.monotonic()
while time.monotonic()-start<480:
    time.sleep(10)
    current=C.get(f'/api/v1/sessions/{sid}').json()
    files=len([p for p in ws.rglob('*') if p.is_file()])
    data['observations'].append({'seconds':round(time.monotonic()-start),'status':current['status'],'fileCount':files})
    save()
    if len(data['observations'])%4==0:
        print('PROGRESS '+json.dumps(data['observations'][-1]),flush=True)
    if current['status']!='CANCELLED':
        data['final']=current
        save()
        print('FINAL '+json.dumps(current),flush=True)
        break
else:
    print('Observation window ended; see generated-file counts',flush=True)
