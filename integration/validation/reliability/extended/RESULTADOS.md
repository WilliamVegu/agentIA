# Validación ampliada — 2026-10-09

Estado: pruebas funcionales locales aprobadas; seguridad de los artefactos Java y generación con DeepSeek pendientes. Este informe acompaña el estado posterior a `02f8ef2` solicitado para publicación en `dual-systems-selector`. Este informe no certifica ausencia de errores ni sustituye una ejecución remota de GitHub Actions.

## Pruebas ejecutadas

| Plataforma | Spring | Quarkus | Evidencia |
|---|---:|---:|---|
| Backend completo Windows | 1581 aprobadas / 46 omitidas | 668 aprobadas / 7 omitidas | `springboot-full.xml`, `quarkus-full.xml` |
| Backend completo Linux limpio | 1532 aprobadas / 95 omitidas | 669 aprobadas / 6 omitidas | `linux-spring-verified.xml`, `linux-quarkus-final.xml` |
| Frontend Windows | 113 aprobadas + build | 79 aprobadas + build | `windows-*-ui.log`, `windows-*-ui-build.log` |
| Frontend Linux limpio, npm ci | 113 aprobadas + build | 79 aprobadas + build | `linux-*-ui.log`, `linux-*-ui-build.log` |
| Gherkin español Windows y Linux | 10 escenarios por plataforma, ambos estudios | Incluye manual, guiado, Auto-Pilot y dos rutas ZIP | `bdd-export-verified.xml`, `linux-bdd-export-verified.xml` |
| Flujos y reinicio real | 34 por estudio + 2 reinicios | Sin credenciales externas | `backend/journeys-summary.json` |
| Migraciones y autoridad de revisiones | 13 | 12 | `migration/migration-summary.json` |
| Regresiones de los fallos encontrados | 37 aprobadas / 1 omitida | El enlace simbólico se prueba en Linux | `corrections-final.xml` |

Las omisiones corresponden a capacidades opcionales y plataforma. No cuentan como aprobaciones de Docker o IA. La matriz nativa Java y los contratos HTTP conservan la evidencia previa: el código Java generado no cambió en esta ampliación. Los recuentos de suites y plataformas se solapan; no se suman como casos únicos.

## Correcciones verificadas

- Requisitos recupera el `spec.md` inicial cuando aún no existe una revisión. Una revisión SQLite existente conserva prioridad; los enlaces fuera del workspace se rechazan.
- La proyección del despliegue Spring reintenta únicamente errores transitorios Windows 5/32/33, hasta cinco escrituras; un fallo persistente mantiene el archivo anterior y sigue siendo observable. No se cambia el límite de reparaciones, que permanece en tres.
- El monitor Quarkus dejó de inventar `5/5` pruebas aprobadas y de equiparar COMPLETED con PASSED. Ambos estudios muestran tres intentos, fases completadas y mensajes de entrega sujetos a evidencia. El resumen Quarkus usa `databaseEngine`, el campo real del API.
- Se retiró React Router de ambos frontends: no tenía consumidores y Trivy encontró dos CVE por lockfile. Se actualizaron `source-map-js` y `postcss-selector-parser` en desarrollo.
- Constraints Python corregidos: FastAPI/Starlette, cryptography/cffi, GitPython, langgraph-sdk, pyasn1, Pygments, python-dotenv, python-multipart y urllib3. `pip check`, instalación Linux limpia y suites completas aprobados. Se regeneró OpenAPI desde las rutas reales.
- CI incluye las dependencias BDD y compone PYTHONPATH con el separador del sistema operativo. No se ejecutó el workflow remoto en esta continuación.

## Navegador

Selector, login MVP local, dos creaciones asistidas, recuperación del texto inicial, veinte paneles y Auto-Pilot SOURCE_ONLY de ambos estudios comprobados con backends, bases y workspaces aislados. Evidencia: `browser-panels.json` y capturas `browser-*-prompt.png`, `browser-*-verification.png`.

Spring exige IA real para la síntesis arquitectónica asistida. Su rechazo explícito al proveedor diagnóstico se conserva; no se convierte en una aprobación de IA. Auto-Pilot offline solo acredita el recorrido diagnóstico.

La herramienta de navegación se bloqueó esperando el evento de descarga al pulsar el botón que abre otra ventana. La recepción visual del archivo queda pendiente. Las dos rutas HTTP reales (`/sessions/{id}/export` y `/orchestrator/sessions/{id}/export-bundle`) entregan ZIP válido con Java del dominio y sin `.env`, comprobado en los escenarios BDD. No se declara aprobada la descarga visual.

## DeepSeek: bloqueo externo

Dos consultas de solo lectura: `/models` y `/user/balance`, ambas HTTP 200. La credencial se aceptó; la última comprobación indicó `is_available=false`. No hubo solicitudes de completions, generación ni tokens cobrados. El informe sanitizado `deepseek-preflight.json` no contiene la clave ni importes de saldo.

La generación real completa en ambos estudios sigue pendiente de saldo disponible. La clave se usó solo en memoria mediante entrada oculta; no se añadió a código, archivos de entorno ni argumentos de procesos.

## Trivy: hallazgos pendientes

Trivy 0.69.3 ejecutado localmente con bases oficiales. Un escaneo `fs` del repositorio no cubría los requirements sin resolución ni los JAR; se añadieron versiones Python efectivas y escaneos `rootfs` de los artefactos reales. Un resultado con cero archivos de lenguaje no se contó como aprobación Java.

| Alcance | Resultado actual | Informe |
|---|---|---|
| Python resuelto, compartido por ambos estudios | 0 CVE conocidos detectados después de actualizar; antes 65 | `trivy-resolved.json`, `trivy-resolved-final.json` |
| Frontends, incluyendo desarrollo | 1 aviso HIGH `braces` por lockfile, sin versión corregida publicada | `trivy-resolved-final.json` |
| JAR Spring Boot 3.2.3 verificado | 86 avisos: 8 CRITICAL, 32 HIGH, 32 MEDIUM, 14 LOW | `trivy-java-spring-rootfs.json` |
| Bibliotecas Quarkus 3.15.1 de imagen propia | 71 avisos: 1 CRITICAL, 33 HIGH, 34 MEDIUM, 3 LOW | `trivy-java-quarkus-rootfs.json` |

Estos son avisos de dependencias y no pruebas de explotabilidad en cada servicio. Los duplicados entre artefactos no se consideran CVE únicos. Las versiones base Java no se actualizaron en esta sesión: requieren cambiar los generadores y repetir Maven/Gradle, H2/PostgreSQL/MySQL, contratos HTTP y escaneo de los nuevos binarios. El SAST interno aprobado no sustituye este análisis de dependencias.

Referencias primarias para la corrección pendiente: [Spring Boot 3.5](https://docs.spring.io/spring-boot/3.5/system-requirements.html), [Quarkus y soporte LTS](https://quarkus.io/releases/), [braces sin parche publicado](https://github.com/micromatch/braces/issues/73). Evaluar versiones y compatibilidad; no adoptar una versión solo por su número.

Se conservaron cuatro contenedores del usuario, saludables, y se detuvieron únicamente los servidores de prueba. La publicación de este estado no certifica los pendientes descritos en este informe.
