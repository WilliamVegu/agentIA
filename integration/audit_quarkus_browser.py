"""Inspect the real Quarkus_refact UI without modifying either application."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / 'validation'
observations = {}
with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge', headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors, failures = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('response', lambda response: failures.append({'url': response.url, 'status': response.status}) if response.status >= 500 else None)
    page.goto('http://127.0.0.1:3012', wait_until='networkidle', timeout=60000)
    page.get_by_placeholder('ej: billing-service, inventario-api, citas-service').wait_for(timeout=30000)
    observations['quarkus_form_is_rendered'] = True
    observations['starts_without_real_server_authentication'] = page.get_by_placeholder('ej: billing-service, inventario-api, citas-service').is_visible()
    observations['javascript_errors'] = errors
    observations['http_5xx'] = failures
    page.screenshot(path=str(OUT / 'quarkus-refact-studio.png'), full_page=True)
    body = page.locator('body').inner_text()
    (OUT / 'quarkus-refact-studio-text.txt').write_text(body, encoding='utf-8')
    observations['seven_step_navigation_is_rendered'] = all(label in body for label in ['Pedido', 'Contrato', 'Arquitectura', 'Construcción', 'Docs', 'Control 2', 'DevOps'])
    browser.close()
(OUT / 'quarkus-refact-browser.json').write_text(json.dumps(observations, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(observations, ensure_ascii=False))
