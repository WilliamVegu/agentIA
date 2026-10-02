import json
import sqlite3
from pathlib import Path
import httpx

OUT=Path(__file__).resolve().parent
sid=json.loads((OUT/'graph-session.json').read_text(encoding='utf8'))['sessionId']
c=httpx.Client(base_url='http://127.0.0.1:8011',timeout=30)
data=c.get('/api/v1/sessions/'+sid).json()
conn=sqlite3.connect(OUT/'runtime'/'studio.db')
conn.row_factory=sqlite3.Row
row=conn.execute('SELECT * FROM generation_sessions WHERE id=?',(sid,)).fetchone()
details={k:json.loads(row[k]) if row[k] else None for k in ['generation_journal_json','artifact_provenance_json','verification_metrics_json','cost_record_json']}
ws=OUT/'runtime'/'workspaces'/sid
details['files']=[str(p.relative_to(ws)) for p in ws.rglob('*') if p.is_file()]
details['http']=data
(OUT/'graph-state.json').write_text(json.dumps(details,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(data,ensure_ascii=True))
print('JOURNAL',json.dumps(details['generation_journal_json'],ensure_ascii=True)[:12000])
print('FILES',details['files'])
print('VERIFICATION',details['verification_metrics_json'])
cost_path=OUT/'runtime'/'cost_tracking.db'
if cost_path.exists():
    cost=sqlite3.connect(cost_path)
    tables=cost.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print('COST_TABLES',tables)
    costs={}
    for (table,) in tables:
        cost.row_factory=sqlite3.Row
        costs[table]=[dict(r) for r in cost.execute('SELECT * FROM "'+table+'"').fetchall()]
    (OUT/'cost-results.json').write_text(json.dumps(costs,ensure_ascii=False,indent=2),encoding='utf8')
    print('COST_ROWS',{k:len(v) for k,v in costs.items()})
