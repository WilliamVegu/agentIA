"""Summarize the completed correction run without replacing its failed baseline."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import httpx

root = Path(__file__).parent


def counts(name):
    cases = list(ET.parse(root / name).getroot().iter('testcase'))
    failed = sum(c.find('failure') is not None for c in cases)
    errors = sum(c.find('error') is not None for c in cases)
    skipped = sum(c.find('skipped') is not None for c in cases)
    return f'{len(cases) - failed - errors - skipped} aprobadas; {failed} fallidas; {errors} errores; {skipped} omitidas'


smoke = json.loads((root / 'final-smoke.json').read_text(encoding='utf-8'))
health = httpx.get('http://127.0.0.1:8000/healthz', timeout=30).json()
(root / 'final-health.json').write_text(json.dumps(health, ensure_ascii=False, indent=2), encoding='utf-8')
report = f'''# Correcciones y validación final — 7 de octubre de 2026

Este informe corresponde a la ejecución posterior a las correcciones. `RESULTADOS.md` y `backend.xml` conservan el diagnóstico inicial de 67 fallos.

| Comprobación | Resultado |
|---|---|
| Backend, suite completa | {counts('backend-final.xml')} |
| Frontend, suite completa | {counts('frontend-final.xml')} |
| HTTP y navegador Edge, aplicación local corregida | {sum(bool(c['passed']) for c in smoke)} aprobadas; {sum(not c['passed'] for c in smoke)} fallidas |
| Compilación TypeScript y Vite | Aprobada en la validación inicial; no se modificó código del frontend |
| API `/healthz` | {health['status']}; tracing={str(health['mlflow']['tracing']).lower()}; {len(health['mlflow']['failures'])} errores de MLflow |

## Cambios de aplicación

- Reparación: preservar respuestas HTTP 404/409, validar la existencia del workspace antes de planificar y respetar el máximo de tres intentos de la constitución.
- Generación: persistir la fase FAILED al bloquear una sesión por error. En modo determinista, derivar SQL de las entidades cuando no hay una respuesta de modelo; los errores del modo MODEL siguen bloqueando la sesión.
- Publicación atómica de activos: usar rutas extendidas de Windows para temporales que superan el límite convencional. Se mantiene la comprobación de identidad y la restauración ante un error.
- Telemetría local: arrancar MLflow en 127.0.0.1:5000 y reiniciar el backend para activar las trazas.

## Pruebas y contratos

Se actualizaron fixtures antiguos para autenticar mediante el endpoint real de acceso local, mantener vivo el cliente durante tareas de fondo y crear sesiones/workspaces con evidencia de entrega. Las expectativas distinguen SOURCE_ONLY, verificación real y despliegue Docker. Se actualizó el contrato OpenAPI desde la aplicación.

Se añadieron regresiones para rutas largas, sesión inexistente, fuentes desactualizadas y reparación concurrente. Los dobles Git actúan sobre el punto real de push para evitar intentos de publicación remota durante la suite.

La comprobación de navegador usa la aplicación real, sin interceptar respuestas: acceso local MVP, rechazo de origen externo, autorización, validación de payload, consulta de sesiones, logout, revocación, diez pestañas y recarga. No hubo excepciones JavaScript ni respuestas HTTP 5xx en ese recorrido.

## Estado local y límites

- Aplicación: http://127.0.0.1:3000 ; API: http://127.0.0.1:8000 ; MLflow: http://127.0.0.1:5000 . Los servicios escuchan en loopback.
- Docker no está instalado/disponible en este entorno y su motor no responde. No se acredita un despliegue real de contenedores ni una prueba SQL en contenedor.
- Las pruebas omitidas no cuentan como aprobadas. Las suites incluyen dobles de proveedores; no acreditan llamadas reales a IA, publicación Git remota ni compilación Java real.
- MLflow avisa que la ejecución de jobs no está soportada en Windows; el servidor de tracking y las trazas sí están activos.
- Se conserva el cambio preexistente de `frontend/package-lock.json`.

Evidencia: `backend-final.xml`, `backend-final.log`, `frontend-final.xml`, `frontend-final.log`, `final-smoke.json`, `final-health.json` y `studio-desktop.png`. Los archivos de la ejecución inicial se conservan como referencia.
'''
(root / 'CORRECCIONES.md').write_text(report, encoding='utf-8')
print(report)
