import json
import os
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent
FRONTEND = os.environ.get('VALIDATION_FRONTEND_URL', 'http://127.0.0.1:3000')
results = []

def check(name, condition, detail=None):
    results.append({'name': name, 'passed': bool(condition), 'detail': detail})

for base in ['http://127.0.0.1:8000', FRONTEND]:
    with httpx.Client(base_url=base, timeout=30) as client:
        r = client.get('/healthz')
        check(base + ' health', r.status_code == 200 and r.json()['status'] == 'UP', r.json())
        check(base + ' denies anonymous access', client.get('/api/v1/sessions').status_code == 401)
        r = client.post('/api/v1/auth/mvp', headers={'Origin': 'https://external.example'})
        check(base + ' denies external origin', r.status_code == 403)
        r = client.post('/api/v1/auth/mvp')
        check(base + ' local login', r.status_code == 200 and 'agentia_session' in client.cookies)
        check(base + ' authenticated session', client.get('/api/v1/auth/session').status_code == 200)
        r = client.get('/api/v1/sessions')
        check(base + ' session list', r.status_code == 200 and isinstance(r.json(), list))
        r = client.get('/api/v1/sessions/00000000-0000-0000-0000-000000000000')
        check(base + ' missing session', r.status_code == 404)
        r = client.post('/api/v1/sessions', json={})
        check(base + ' invalid payload', r.status_code == 400)
        check(base + ' logout', client.post('/api/v1/auth/logout').status_code == 200)
        check(base + ' revoked session', client.get('/api/v1/sessions').status_code == 401)

with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors = []
    failures = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('response', lambda response: failures.append({'url': response.url, 'status': response.status}) if response.status >= 500 else None)
    page.goto(FRONTEND, wait_until='networkidle', timeout=60000)
    (OUT / 'login-text.txt').write_text(page.locator('body').inner_text(), encoding='utf-8')
    buttons = page.get_by_role('button').all_text_contents()
    mvp = page.get_by_role('button', name='MVP', exact=False)
    if mvp.count():
        mvp.first.click()
    page.get_by_role('button', name='Nuevo Microservicio', exact=True).wait_for(timeout=30000)
    check('browser local login and studio render', True)
    page.screenshot(path=str(OUT / 'studio-desktop.png'), full_page=True)
    (OUT / 'studio-text.txt').write_text(page.locator('body').inner_text(), encoding='utf-8')
    nav = page.get_by_role('navigation')
    names = nav.get_by_role('button').all_text_contents()
    for name in names:
        tab = nav.get_by_role('button', name=name, exact=True)
        tab.click()
        page.wait_for_timeout(250)
        check('browser tab ' + name, tab.get_attribute('aria-current') == 'page' and 'Error al renderizar' not in page.locator('body').inner_text())
    page.reload(wait_until='networkidle')
    check('browser authentication survives reload', page.get_by_role('button', name='Nuevo Microservicio', exact=True).is_visible())
    check('browser no JavaScript exceptions', not errors, errors)
    check('browser no HTTP 5xx', not failures, failures)
    browser.close()

(OUT / 'local-smoke.json').write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(results, indent=2, ensure_ascii=False))
raise SystemExit(0 if all(r['passed'] for r in results) else 1)
