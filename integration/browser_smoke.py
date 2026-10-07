"""Exercise the live selector, both unchanged UIs, cookies and persisted specifications.

Run after launch.py starts all services. Requires Playwright and Microsoft Edge.
No HTTP mocking, external LLM calls, Git pushes, or Docker deployments.
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / 'validation'
OUT.mkdir(exist_ok=True)
checks = []


def check(name, condition, detail=None):
    checks.append({'name': name, 'passed': bool(condition), 'detail': detail})
    if not condition:
        raise AssertionError(f'{name}: {detail}')


def blueprint(name):
    return {
        'serviceName': name,
        'packageName': 'com.example.inventory',
        'basePort': 8082,
        'entities': [{'name': 'Item', 'tableName': 'items', 'attributes': [
            {'name': 'id', 'type': 'UUID', 'isPrimaryKey': True},
            {'name': 'sku', 'type': 'String', 'validationRules': ['@NotBlank']},
        ]}],
        'userStories': [{'id': 'US-1', 'priority': 'P1', 'role': 'Warehouse Manager',
            'intent': 'track inventory', 'benefit': 'know stock levels',
            'scenarios': [{'scenarioId': 'AC-1.1', 'given': 'sku exists', 'when': 'query item', 'then': 'return current quantity'}]}],
    }


try:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 1000})
        errors, failures = [], []
        context.on('page', lambda page: page.on('pageerror', lambda error: errors.append(str(error))))
        context.on('response', lambda response: failures.append({'url': response.url, 'status': response.status}) if response.status >= 500 else None)
        portal = context.new_page()
        portal.goto('http://127.0.0.1:3100', wait_until='networkidle')
        check('Selector disponible', portal.get_by_role('heading', name='Elige tu estudio.').is_visible())
        portal.screenshot(path=str(OUT / 'selector-desktop.png'), full_page=True)
        portal.set_viewport_size({'width': 390, 'height': 844})
        check('Selector móvil sin desbordamiento horizontal', portal.evaluate('document.documentElement.scrollWidth <= innerWidth'))
        check('Ambas opciones visibles en móvil', portal.get_by_role('link', name='Abrir Spring Boot').is_visible() and portal.get_by_role('link', name='Abrir Quarkus').is_visible())
        portal.screenshot(path=str(OUT / 'selector-mobile.png'), full_page=True)
        studios = {}
        for name, label in [('springboot', 'Abrir Spring Boot'), ('quarkus', 'Abrir Quarkus')]:
            with context.expect_page() as opened:
                portal.get_by_role('link', name=label).click()
            page = opened.value
            page.wait_for_load_state('networkidle')
            check(f'{name}: enlace abre su frontend', page.url.startswith('http://127.0.0.1:3000' if name == 'springboot' else 'http://localhost:3001'))
            page.get_by_role('button', name='MVP', exact=False).first.click()
            page.get_by_role('button', name='Nuevo Microservicio', exact=True).wait_for(timeout=30000)
            check(f'{name}: acceso local y estudio completo', True)
            page.screenshot(path=str(OUT / f'{name}-studio.png'), full_page=True)
            studios[name] = page
            for base in [page.url.rstrip('/'), 'http://127.0.0.1:' + ('8000' if name == 'springboot' else '8001')]:
                response = page.request.get(base + '/healthz')
                check(f'{name}: salud {base}', response.ok and response.json()['status'] == 'UP')
            nav = page.get_by_role('navigation')
            names = nav.get_by_role('button').all_text_contents()
            check(f'{name}: diez pestañas disponibles', len(names) == 10, names)
            for tab_name in names:
                tab = nav.get_by_role('button', name=tab_name, exact=True)
                tab.click()
                page.wait_for_timeout(150)
                check(f'{name}: pestaña {tab_name}', tab.get_attribute('aria-current') == 'page' and 'Error al renderizar' not in page.locator('body').inner_text())
            page.reload(wait_until='networkidle')
            check(f'{name}: acceso persiste al recargar', page.get_by_role('button', name='Nuevo Microservicio', exact=True).is_visible())
        spring, quarkus = studios['springboot'], studios['quarkus']
        spring_url, quarkus_url = 'http://127.0.0.1:3000', 'http://localhost:3001'
        cookies = [cookie for cookie in context.cookies() if cookie['name'] == 'agentia_session']
        check('Cookies separadas en un mismo navegador', len(cookies) == 2 and {cookie['domain'] for cookie in cookies} == {'127.0.0.1', 'localhost'}, [cookie['domain'] for cookie in cookies])
        check('Entrar en Quarkus conserva el acceso Spring', spring.request.get(spring_url + '/api/v1/auth/session').ok)
        ids = {}
        for name, page, base in [('springboot', spring, spring_url), ('quarkus', quarkus, quarkus_url)]:
            response = page.request.post(base + '/api/v1/specifications', data=blueprint('integration-' + name))
            check(f'{name}: ingesta real de especificación', response.status == 201, response.text() if response.status != 201 else None)
            ids[name] = response.json()['specId']
            check(f'{name}: especificación persistida en su carpeta', (Path(__file__).resolve().parent.parent / ('' if name == 'springboot' else 'systems/quarkus') / 'backend/specifications' / (ids[name] + '.json')).is_file())
        for name, page, base, other in [('springboot', spring, spring_url, 'quarkus'), ('quarkus', quarkus, quarkus_url, 'springboot')]:
            check(f'{name}: lee su propia especificación', page.request.get(base + '/api/v1/specifications/' + ids[name]).ok)
            check(f'{name}: no ve la especificación del otro estudio', page.request.get(base + '/api/v1/specifications/' + ids[other]).status == 404)
        check('Cerrar sesión Spring', spring.request.post(spring_url + '/api/v1/auth/logout').ok)
        check('Spring revoca su propia sesión', spring.request.get(spring_url + '/api/v1/auth/session').status == 401)
        check('Quarkus sigue autenticado tras salir de Spring', quarkus.request.get(quarkus_url + '/api/v1/auth/session').ok)
        check('Nuevo acceso Spring', spring.request.post(spring_url + '/api/v1/auth/mvp').ok)
        check('Cerrar sesión Quarkus', quarkus.request.post(quarkus_url + '/api/v1/auth/logout').ok)
        check('Spring sigue autenticado tras salir de Quarkus', spring.request.get(spring_url + '/api/v1/auth/session').ok)
        check('Sin excepciones JavaScript', not errors, errors)
        check('Sin HTTP 5xx', not failures, failures)
        (OUT / 'specification-ids.json').write_text(json.dumps(ids, indent=2), encoding='utf-8')
        browser.close()
finally:
    (OUT / 'browser-smoke.json').write_text(json.dumps(checks, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'passed': sum(c['passed'] for c in checks), 'failed': sum(not c['passed'] for c in checks)}))
