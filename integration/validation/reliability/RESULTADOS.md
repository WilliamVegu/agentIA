# Validación actual de fiabilidad

Rama `dual-systems-selector`; implementación anterior guardada en `02f8ef2`, con correcciones de cierre locales posteriores. Revisión: 2026-10-09, America/Lima. Cero llamadas a proveedores IA. Bases, fuentes, Git bare y recursos Docker de prueba aislados; los recursos del usuario no se modifican. No se certifica el código local mediante el SHA anterior: los informes posteriores corresponden a las correcciones indicadas abajo.

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
| [closure-http-verified/springboot-native-http.xml](closure-http-verified/springboot-native-http.xml) | 6 | 0 | 0 |
| [final-journeys/springboot-journeys.xml](final-journeys/springboot-journeys.xml) | 34 | 0 | 0 |
| [final-journeys/quarkus-journeys.xml](final-journeys/quarkus-journeys.xml) | 34 | 0 | 0 |
| [final-journeys/real-restart.xml](final-journeys/real-restart.xml) | 2 | 0 | 0 |
| [final-migration/springboot-migration.xml](final-migration/springboot-migration.xml) | 13 | 0 | 0 |
| [final-migration/quarkus-migration.xml](final-migration/quarkus-migration.xml) | 12 | 0 | 0 |
| [final-paths.xml](final-paths.xml) | 7 | 0 | 0 |
| [final-source-io.xml](final-source-io.xml) | 29 | 0 | 0 |
| [closure-first-failure.xml](closure-first-failure.xml) | 1575 | 0 | 45 |
| [quarkus-closure-full.xml](quarkus-closure-full.xml) | 666 | 0 | 6 |
| [final-source-io-verified.xml](final-source-io-verified.xml) | 60 | 0 | 0 |
| [final-atomic-assets.xml](final-atomic-assets.xml) | 19 | 0 | 0 |
| [final-integration.xml](final-integration.xml) | 29 | 0 | 0 |
| [validation-mutation-verified.xml](validation-mutation-verified.xml) | 2 | 0 | 0 |

Frontends: 113 pruebas Spring y 76 Quarkus aprobadas; revisión posterior de contratos/paneles: 23 y 25 pruebas aprobadas. Ambos builds TypeScript/Vite terminan correctamente. Los logs `frontend-*-acceptance-*` y `frontend-*-contract-final.log` permiten comprobarlo. Avisos: tamaño de bundle Vite y warnings de Pydantic; no se presentan como errores de ejecución.

## Java y runtime

La matriz actual compila y ejecuta suites no vacías offline en las doce combinaciones Spring/Quarkus × Maven/Gradle × H2/PostgreSQL/MySQL. `current-matrix/java-matrix-relational-*-all-all.json` incluye huella de entrada, hashes de reportes, conteos y ausencia de modificaciones de fuentes. Quarkus pasa las seis pruebas HTTP actuales. La repetición secuencial de Spring pasó sus seis casos en 184,28 segundos, conservando el timeout anterior de MySQL/Maven bajo carga. Las seis huellas de las fuentes usadas por la repetición coinciden exactamente con la matriz Java vigente; no se cambió el timeout ni se introdujeron retries para aprobar.

Las pruebas HTTP cubren CRUD, UUID/ID propio, fechas, decimal, unique/FK, solicitudes inválidas 400, ausencia 404, restricciones 409 y persistencia tras stop/restart. Los informes anteriores se conservan como historia. El intento `closure-matrix` falló porque Docker Desktop estaba apagado; se inició el daemon y `closure-http-verified` acredita la repetición real.

La prueba negativa `validation-mutation-verified.xml` pasó en ambos frameworks (390,63 segundos): quitar `@Email` y luego `@Positive` de la Request en una copia aislada hizo fallar el contrato 400 esperado, observando 500 por validación tardía en persistencia. Restaurar ambas anotaciones recuperó el contrato HTTP completo. Los JSON `validation-mutation-{springboot,quarkus}.json` registran cuatro defectos detectados, dos contratos restaurados y fuentes originales intactas. `validation-mutation-http/` conserva los diagnósticos por caso. El primer harness fallido se conserva en `validation-mutation.xml` y `*-before.json`: interpretaba incorrectamente el formato de AssertionError reescrito por pytest; se corrigió para leer la evidencia estructurada, sin relajar el contrato HTTP.

Las pruebas PostgreSQL/MySQL de conservación de registro y recursos ajenos pasan en ambos estudios. El escenario ampliado Spring con tres sesiones (incluido Auto-Pilot), colisión, Docker ausente y reinicio de backend pasó en `spring-native-autopilot-final.xml`; Quarkus también pasó en `quarkus-native-autopilot-verified.xml` después de corregir el import ausente en Auto-Pilot. Ambos escenarios verifican tres sesiones, readiness propio, recuperación en un proceso nuevo, colisión, Docker ausente y cleanup exclusivamente de las fixtures. Los intentos bajo carga concurrente se guardan en `*-native-autopilot-current.log/xml`: sus timeouts no certificaron éxito.

## Límites y pendientes

- Revisión de cierre: inyección de prueba de persistencia y lectura de hashes de proveniencia usan rutas extendidas Windows en ambos estudios; lectura del registro de activos Spring también. `final-paths.xml` comprueba las tres operaciones sobre rutas de más de 400 caracteres. `final-source-io.xml` conserva rechazo de registros corruptos, rollback y huellas (29 pruebas). Los primeros intentos fallidos `closure-journeys`, `closure-diagnostic` y `closure-paths` permanecen para trazabilidad.

La suite completa Spring `closure-first-failure.xml` terminó con 1575 aprobadas/45 opt-in omitidas. El primer full con temporales más profundos (`springboot-closure-full.xml`: 1570 aprobadas, 3 fallos, 2 errores, 45 skips) detectó dos escrituras de corrupción de fixtures sin prefijo extendido y bloqueos transitorios Windows al reemplazar activos. Se conservaron las aserciones de corrupción, se corrigió su I/O y se añadieron reintentos exclusivamente para WinError 5/32/33, limitados a cinco intentos; error persistente hace rollback y no devuelve éxito. La revisión posterior de esas familias pasó 60 pruebas; la suite de activos final pasó 19, incluidos bloqueo transitorio y persistente. Estas verificaciones posteriores complementan la suite completa; no se afirma que el full anterior incluyera los dos tests añadidos al final. Quarkus final pasó 666/6. Los avisos Pydantic y deprecaciones no se han eliminado mediante filtros.

`source-revisions.json` registra 186 cambios exactos de archivos históricos con hashes antes/después, TIDs y evidencia. La comprobación final pasó conservando `source-snapshots.json` sin modificación.

- La matriz Windows/Linux de GitHub Actions está preparada; no se ha ejecutado remotamente ni se afirma validación Linux local.
- No se ejecutaron llamadas IA reales, BDD/Gherkin completos ni un escaneo Trivy remoto. Los controles SAST/secret y gates de reportes de CI tienen pruebas locales; ello no acredita un pipeline remoto ni cobertura completa de CVE.
- Los skips backend corresponden a pruebas opt-in/capacidades declaradas. Un skip no certifica runtime. Consultar el detalle en XML y logs.

## Recuperación y documentos

Ver [interfaz](ui.md), [eventos](events.json), [migración](../../../docs/dual-studio-reliability-migration.md), [quickstart](../../../specs/017-dual-studio-reliability/quickstart.md) y [matriz de revisión FR/constituciones](../../../specs/017-dual-studio-reliability/contracts/regression-matrix.md). Las pruebas reales de crash usan procesos nuevos y recuperan INTERRUPTED, eventos y fuentes, sin efectos externos automáticos. No sumar suites solapadas como pruebas únicas.
## Ampliación posterior con Linux, BDD, navegador y Trivy

Consultar [el informe ampliado](extended/RESULTADOS.md): suites completas y builds aprobados en Windows y Linux, regresiones de nuevos fallos corregidas, diez escenarios Gherkin contra HTTP real y veinte paneles visitados. La seguridad Java permanece pendiente (86 avisos Spring / 71 Quarkus), además del aviso de desarrollo braces sin parche. DeepSeek aceptó la credencial y declaró saldo no disponible; cero completions. La recepción visual del ZIP y GitHub Actions remoto no se certificaron. El informe ampliado acompaña el estado solicitado para publicación en `dual-systems-selector`.
