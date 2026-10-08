# Validación actual de fiabilidad

Rama `dual-systems-selector`; base `cd50688c8188b47ba789ec30683a50eabc7bd593`. Cambios locales sin commit ni publicación. Fecha: 2026-10-08. Cero llamadas a proveedores IA. Bases, fuentes, Git bare y recursos Docker de prueba aislados; los recursos del usuario no se modifican.

## Informes revisados

| Informe | Aprobadas | Fallos/errores | Skips |
|---|---:|---:|---:|
| [spring-full-final-verified.xml](spring-full-final-verified.xml) | 1572 | 0 | 45 |
| [quarkus-full-final-verified.xml](quarkus-full-final-verified.xml) | 663 | 0 | 6 |
| [integration-current-final.xml](integration-current-final.xml) | 29 | 0 | 0 |
| [spring-checkpoint-final.xml](spring-checkpoint-final.xml) | 51 | 0 | 0 |
| [quarkus-checkpoint-final.xml](quarkus-checkpoint-final.xml) | 14 | 0 | 0 |
| [spring-offline-choice-final.xml](spring-offline-choice-final.xml) | 17 | 0 | 0 |
| [quarkus-offline-choice-final.xml](quarkus-offline-choice-final.xml) | 9 | 0 | 0 |
| [spring-native-autopilot-final.xml](spring-native-autopilot-final.xml) | 1 | 0 | 0 |
| [quarkus-native-autopilot-verified.xml](quarkus-native-autopilot-verified.xml) | 1 | 0 | 0 |
| [standalone-ownership-current.xml](standalone-ownership-current.xml) | 4 | 0 | 0 |
| [spring-db-conservation-current.xml](spring-db-conservation-current.xml) | 3 | 0 | 0 |
| [quarkus-db-conservation-current.xml](quarkus-db-conservation-current.xml) | 6 | 0 | 0 |
| [journeys/springboot-journeys.xml](journeys/springboot-journeys.xml) | 31 | 0 | 0 |
| [journeys/quarkus-journeys.xml](journeys/quarkus-journeys.xml) | 31 | 0 | 0 |
| [journeys/real-restart.xml](journeys/real-restart.xml) | 2 | 0 | 0 |
| [migration/springboot-migration.xml](migration/springboot-migration.xml) | 12 | 0 | 0 |
| [migration/quarkus-migration.xml](migration/quarkus-migration.xml) | 12 | 0 | 0 |
| [current-matrix/quarkus-native-http.xml](current-matrix/quarkus-native-http.xml) | 6 | 0 | 0 |

Frontends: 113 pruebas Spring y 76 Quarkus aprobadas; revisión posterior de contratos/paneles: 23 y 25 pruebas aprobadas. Ambos builds TypeScript/Vite terminan correctamente. Los logs `frontend-*-acceptance-*` y `frontend-*-contract-final.log` permiten comprobarlo. Avisos: tamaño de bundle Vite y warnings de Pydantic; no se presentan como errores de ejecución.

## Java y runtime

La matriz actual compila y ejecuta suites no vacías offline en las doce combinaciones Spring/Quarkus × Maven/Gradle × H2/PostgreSQL/MySQL. `current-matrix/java-matrix-relational-*-all-all.json` incluye huella de entrada, hashes de reportes, conteos y ausencia de modificaciones de fuentes. Quarkus pasa las seis pruebas HTTP actuales. Spring pasó cinco y agotó el timeout de tres segundos al borrar un registro MySQL/Maven bajo carga Docker concurrente; se conserva el fallo original y falta repetirlo sin otras cargas Docker de prueba. No se declara verde esa repetición antes de ejecutarla.

Las pruebas HTTP cubren CRUD, UUID/ID propio, fechas, decimal, unique/FK, solicitudes inválidas 400, ausencia 404, restricciones 409 y persistencia tras stop/restart. Los informes anteriores de doce contratos HTTP aprobados se conservan como historia; no sustituyen el caso pendiente de esta revisión.

Las pruebas PostgreSQL/MySQL de conservación de registro y recursos ajenos pasan en ambos estudios. El escenario ampliado Spring con tres sesiones (incluido Auto-Pilot), colisión, Docker ausente y reinicio de backend pasó en `spring-native-autopilot-final.xml`; Quarkus también pasó en `quarkus-native-autopilot-verified.xml` después de corregir el import ausente en Auto-Pilot. Ambos escenarios verifican tres sesiones, readiness propio, recuperación en un proceso nuevo, colisión, Docker ausente y cleanup exclusivamente de las fixtures. Los intentos bajo carga concurrente se guardan en `*-native-autopilot-current.log/xml`: sus timeouts no certificaron éxito.

## Límites y pendientes

- Repetir HTTP Spring sin concurrencia Docker y finalizar el cierre transversal de la matriz/documentación.

`source-revisions.json` registra 182 cambios exactos de archivos históricos con hashes antes/después, TIDs y evidencia. La comprobación pasó conservando `source-snapshots.json` sin modificación.

- La matriz Windows/Linux de GitHub Actions está preparada; no se ha ejecutado remotamente ni se afirma validación Linux local.
- No se ejecutaron llamadas IA reales, BDD/Gherkin completos ni un escaneo Trivy remoto. Los controles SAST/secret y gates de reportes de CI tienen pruebas locales; ello no acredita un pipeline remoto ni cobertura completa de CVE.
- Los skips backend corresponden a pruebas opt-in/capacidades declaradas. Un skip no certifica runtime. Consultar el detalle en XML y logs.

## Recuperación y documentos

Ver [interfaz](ui.md), [eventos](events.json), [migración](../../../docs/dual-studio-reliability-migration.md) y [quickstart](../../../specs/017-dual-studio-reliability/quickstart.md). Las pruebas reales de crash usan procesos nuevos y recuperan INTERRUPTED, eventos y fuentes, sin efectos externos automáticos.
