import json
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

root = Path(__file__).parent
results = {}
failures = []
skipped = []
for label in ['backend', 'frontend']:
    tree = ET.parse(root / f'{label}.xml')
    cases = list(tree.iter('testcase'))
    totals = Counter()
    for case in cases:
        status = next((s for s in ['failure', 'error', 'skipped'] if case.find(s) is not None), 'passed')
        totals[status] += 1
        if status in ['failure', 'error']:
            node = case.find(status)
            failures.append({'suite': label, 'module': case.get('classname'), 'test': case.get('name'), 'status': status, 'message': node.get('message'), 'trace': node.text})
        elif status == 'skipped':
            node = case.find(status)
            skipped.append({'suite': label, 'module': case.get('classname'), 'test': case.get('name'), 'reason': node.get('message')})
    results[label] = dict(totals)
results['smoke'] = {}
for label in ['development', 'production']:
    checks = json.loads((root / f'{label}-smoke.json').read_text(encoding='utf-8'))
    results['smoke'][label] = {'passed': sum(c['passed'] for c in checks), 'failed': sum(not c['passed'] for c in checks)}
(root / 'summary.json').write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')
(root / 'failures.json').write_text(json.dumps(failures, indent=2, ensure_ascii=False), encoding='utf-8')
(root / 'skipped.json').write_text(json.dumps(skipped, indent=2, ensure_ascii=False), encoding='utf-8')
lines = ['# Validación local — 7 de octubre de 2026', '', 'La validación completa NO está aprobada: la suite backend tiene fallos. La aplicación local sí responde y el frontend supera sus pruebas, compilación y comprobaciones de navegador.', '', '| Comprobación | Resultado |', '|---|---|']
for label in ['backend', 'frontend']:
    counts = results[label]
    lines.append(f"| {label} | {counts.get('passed', 0)} aprobadas; {counts.get('failure', 0)} fallidas; {counts.get('error', 0)} errores; {counts.get('skipped', 0)} omitidas |")
lines.extend(['| Compilación frontend (TypeScript + Vite) | Aprobada; advertencia de bundle JS de 577,20 kB |'])
for label, counts in results['smoke'].items():
    lines.append(f"| HTTP y navegador real ({label}) | {counts['passed']} aprobadas; {counts['failed']} fallidas |")
lines += ['', '## Alcance', '', 'HTTP contra backend :8000 y proxy frontend :3000; navegador Microsoft Edge headless contra desarrollo :3000 y producción :3001. Acceso local MVP, rechazo de origen externo y clientes sin sesión, consulta de sesiones, 404, validación de payload, logout y revocación. Navegación por las diez pestañas sin sesión de proyecto seleccionada, recarga autenticada, ausencia de excepciones JavaScript y HTTP 5xx. Sin interceptar ni simular las respuestas del servidor en estas comprobaciones.', '', 'Las suites automatizadas incluyen pruebas unitarias e integraciones con dobles de proveedores externos. Un resultado aprobado de estas suites no acredita una llamada a IA, publicación Git, compilación Java ni despliegue Docker reales.', '', '## Límites del entorno', '', '- Docker CLI no disponible en PATH ni en la ubicación habitual; Docker SDK no logra conectar al motor (named pipe inexistente). No se realizaron nuevas pruebas reales de contenedores, SQL en contenedor ni Kubernetes.', '- MLflow :5000 no está disponible; /healthz declara tracing=false y registra el error. La API sigue UP.', '- No se realizaron llamadas pagadas a proveedores IA ni publicaciones Git remotas.', '- Los conteos omitidos son casos no ejecutados, no aprobaciones.', '', '## Fallos por módulo', '', '| Módulo | Fallos/errores |', '|---|---|']
lines[lines.index('## Fallos por módulo'):lines.index('## Fallos por módulo')] = [
    '## Diagnóstico y prioridades', '',
    '1. Revisar los 500 del endpoint de reparación: `test_quickstart_feature_005_e2e` y `test_repair_endpoint_success_and_boundary`. Estos resultados requieren diagnóstico; las comprobaciones HTTP sanas no cubren esa operación.',
    '2. Revisar generación, cola, pausa/reanudación, SSE y estados persistidos: varios tests dejan sesiones QUEUED o no reciben los eventos previstos. No atribuir todos estos fallos a fixtures sin reproducir cada caso.',
    '3. Actualizar o corregir contratos de autenticación y evidencia de entrega. Hay casos que esperan 200/201 y reciben 401/403. El ejemplo de publicación reproducido crea una sesión COMPLETED/VERIFIED sin evidencia suficiente; la política actual exige evidencia. Mantener los controles mientras se determina el contrato correcto.',
    '4. Revisar fixtures Git: seis tests intentan push y fallan porque origin no es un repositorio válido; no hubo publicación exitosa.',
    '5. Revisar diferencias de OpenAPI, modo SOURCE_ONLY/Docker, recuperación de identidad, generación DevOps, guards de especificación y límite de reparación histórico de cinco intentos.', '',
    'No se cambiaron controles ni código de aplicación para forzar resultados verdes. Se conservó el cambio preexistente de `frontend/package-lock.json`; se revirtió únicamente la regeneración incidental de un informe histórico producida por la suite.', '',
]
for module, count in Counter(f['module'] for f in failures).most_common():
    lines.append(f'| `{module}` | {count} |')
lines += ['', '## Fallos individuales', '']
for f in failures:
    message = (f['message'] or '').replace('\n', ' ')[:600]
    lines.append(f"- `{f['module']}::{f['test']}`: {message}")
lines += ['', '## Evidencia y reproducción', '', '- `backend.log`, `backend.xml`, `frontend-tests.log`, `frontend.xml`, `frontend-build.log`.', '- `development-smoke.json`, `production-smoke.json`, `local_smoke.py`, capturas y textos del navegador.', '- `failures.json` contiene trazas completas; `skipped.json` conserva motivos de omisión.', '', '```powershell', 'python -m pytest backend/tests -q --tb=short --junitxml=reports/validation-20261007/backend.xml', 'cd frontend', 'npm.cmd test', 'npm.cmd run build', '```', '', 'Versiones: Python 3.12.8; Node 22.15.1; npm 10.9.2; FastAPI 0.115.9; Pydantic 2.13.5; pytest 9.1.1; Playwright 1.52.0.', '']
(root / 'RESULTADOS.md').write_text('\n'.join(lines), encoding='utf-8')
print(json.dumps(results, indent=2))
print('Failure modules:', Counter(f['module'] for f in failures).most_common())
