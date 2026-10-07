# Historial y recuperación de versiones Quarkus

Revisión del 7 de octubre de 2026, con `git fetch origin` y copias de trabajo independientes. Las aplicaciones y los cambios locales del directorio original `agentIA` no se modificaron. No se realizó reset, merge, rebase ni push.

## Resultado

**El historial actualmente accesible de `Quarkus_refact_2` no contiene una implementación Quarkus. Sin embargo, el repositorio local conserva dos historias Quarkus desconectadas de las ramas actuales. Se recuperaron ambas con referencias locales para evitar que Git pueda eliminarlas como objetos sin referencia.**

La versión recuperada más reciente, `5d9b190`, contiene el Studio de diez pestañas orientado a Quarkus, instrucciones de generación Quarkus, BDD en español y correcciones de arquitectura. No es la fábrica de siete pasos de `Quarkus_refact`. Su generación offline todavía produce Spring Boot, por lo que no se puede declarar que funciona íntegramente como sistema Quarkus.

No hay evidencia suficiente para atribuir estas historias recuperadas al nombre antiguo `Quarkus_refact_2`: los objetos Git guardan código y padres, pero no el nombre de la rama a la que pertenecieron. El reflog disponible no conserva esa asociación. Su existencia sí demuestra que hubo trabajo Quarkus que quedó fuera de las referencias actuales.

## Historial visible de Quarkus_refact_2 y merge identificado

- HEAD remoto: `7efbc188888dc80a76fa11b2116555a9340c95d0` (`wq`, 07/10/2026). Solo añade dos líneas a `notita_dip.txt`.
- Se inspeccionaron los **172 commits accesibles**, incluyendo ambos lados de los merges, sus nombres de archivo y cinco rutas específicas de la fábrica Quarkus. Ninguno tiene archivos con `quarkus` en el nombre ni dichas rutas.
- Se revisaron también los cambios históricos de `backend` y `frontend` buscando `io.quarkus`, `quarkus-bom`, `/quarkus/orders` y `QuarkusFactory`; no hay coincidencias.
- Merge: `19627d87e75a25e0178493c73d4c43b7798d032b`, 02/10/2026 a las 12:13:42, **Merge pull request #1 from WilliamVegu/no-docker**.
- Sus padres son `1a9223f` y `000192f`. Ambos carecen de la implementación Quarkus. El merge no tiene como padre ninguna versión recuperada ni el commit `10c10ae` de la fábrica Quarkus.

Por tanto, volver al primer padre de ese merge no recupera Quarkus. La historia visible es consistente con una rama basada en la línea Spring. Una eliminación/recreación de rama o una reescritura de referencias podría explicar la desconexión, pero no puede identificarse al responsable ni el mecanismo con la evidencia disponible. No se demuestra que el merge mencionado haya borrado código Quarkus que estuviera en alguno de sus padres.

## Commits recuperados

Antes de crear referencias nuevas, `git fsck --no-reflogs --unreachable` encontró ocho commits sin referencia. Siete pertenecen a dos historias con cambios Quarkus; el restante, `78b697f`, se titula `api` y no se presenta como candidato Quarkus.

| Historia | Commit | Fecha local | Cambio |
|---|---|---|---|
| V1 independiente | `c5bda02` | 29/09, 16:07 | Correcciones Quakus V1; añade generadores deterministas Quarkus e instrucciones |
| Studio, inicio | `6d4f0d0` | 29/09, 23:50 | Quarkus 3.x, BDD en español y ejecución guiada |
| Studio | `9ffe462` | 30/09, 05:55 | Descripciones y responsabilidades en español |
| Studio | `12b02c7` | 30/09, 06:26 | Reglas para eliminar Spring de la generación con IA |
| Studio | `93eb05b` | 30/09, 07:17 | Limpieza de arquitectura, diagramas y contratos |
| Studio | `bbbabb8` | 30/09, 07:42 | Historias editables y fallback de arquitectura ante 503 |
| Studio, último | `5d9b190` | 30/09, 08:18 | Saneamiento de estereotipos Spring y dependencias cíclicas |

Las dos líneas parten de `1a9223f`. `c5bda02` no es ancestro de `6d4f0d0` ni de `5d9b190`: son alternativas independientes.

Se conservaron sin alterar sus commits:

- `recovery/quarkus-20260930` → `5d9b190019f3bcdf8067ea9c8deb77ad766b3f54` (conserva también sus cinco commits Quarkus anteriores).
- `recovery/quarkus-v1-20260929` → `c5bda02365ff597ca32c835044716d68fd1d1a5c`.

Son ramas **locales**, sin publicación en GitHub. Después de crear esas referencias, esos commits dejan de aparecer como `unreachable`; la evidencia del descubrimiento original se guardó antes de recuperarlos.

## Validación de la versión recuperada 5d9b190

Se ejecutó en `agentIA-quarkus-recovered-audit`, checkout separado y sin modificar archivos fuente, usando dependencias Python ya instaladas en el entorno aislado de la auditoría.

- **115 pruebas backend aprobadas y una omitida**: arquitectura, requisitos, análisis de pruebas, generación offline y con clientes simulados, veracidad de verificación sandbox y DevOps. Es una selección de áreas relevantes, no la suite completa.
- Las pruebas de IA usan clientes simulados; no se hicieron llamadas pagadas ni se verificó el comportamiento de proveedores reales.
- Se ejecutaron las cinco etapas de generación con un blueprint de notas, sin credenciales ni compilación Java. Produjeron 15 archivos: `pom.xml` usa `spring-boot-starter-parent`; seis fuentes Java importan Spring.
- Las instrucciones del scaffolder cargadas correctamente exigen Quarkus. Existe, por tanto, una discrepancia efectiva entre el modo IA y el modo offline. La implementación determinista es idéntica desde `6d4f0d0` hasta `5d9b190`, así que retroceder dentro de esa cadena no corrige esa discrepancia.
- La compilación TypeScript + Vite aprobó. La primera suite frontend tuvo 62 aprobadas y tres timeouts de cinco segundos mientras también se compilaba; las tres suites afectadas se repitieron sin modificar fuentes y aprobaron sus 16 casos. La ejecución final de la suite completa, con dos workers y límite de 30 segundos, aprobó **los 65 tests** y quedó registrada en JUnit. Los primeros timeouts no se presentan como defectos confirmados de la aplicación.

Que pasen las pruebas offline significa que el código conserva su baseline Spring anterior; no demuestra generación Quarkus consistente. Antes de usar esta copia como lado Quarkus del selector hay que resolver explícitamente ambos modos de generación y comprobar sus artefactos.

## Validación de la alternativa c5bda02

Se ejecutó en `agentIA-quarkus-v1-audit`. Aunque añade archivos de generación Quarkus, el conjunto guardado en este commit es incompleto:

- `stages/instructions.py`, `stages/journal.py` y `stages/deterministic/domain.py` no existen en su árbol, aunque el nuevo runner los necesita. También faltan otros componentes de la nueva frontera de generación.
- La suite backend completa no puede recolectarse: dos errores de importación en las suites de generación (`cannot import name 'journal'`).
- El nodo de scaffolding anterior sigue activo y genera un POM Spring Boot y una clase `@SpringBootApplication`. Se reprodujo directamente, sin modificarlo.

No debe tomarse este commit por sí solo como una versión Quarkus funcional solo porque contiene templates Quarkus. No se corrigieron estos problemas en las ramas recuperadas: se conservaron para inspección fiel.

## Otra candidata actual: fábrica Quarkus de Unificado

`origin/Unificado` (`5ebe5ded6b5215357f87d1492bee4c07a54e28f0`) tiene la fábrica de siete pasos y una corrección introducida en `83dc944`: `generate_devops_artifacts` devuelve la tupla que espera el orquestador. `e72e30c` añade publicación Git. Ninguno de estos commits pertenece al historial de `Quarkus_refact_2`.

En `agentIA-quarkus-history-audit`:

- Su test de ciclo completo aprobó, incluyendo publicación Git **simulada**; no se hizo push real.
- Se comprobaron creación, contrato, arquitectura, generación, aprobación final y ZIP tanto con Maven como con Gradle: aprobación final 200 y estado `Entregado`, corrigiendo el fallo de la rama `Quarkus_refact`.
- Persisten problemas reproducidos: seleccionando PostgreSQL se genera configuración de SQL Server; la ruta `/warehouse/items` del contrato aprobado no aparece en recursos concretos; “Sin autenticación” da 400 por `SecurityEnum.OIDC` inexistente.
- `developer_qa_service.py`, `architect_agent.py`, `scaffolder_service.py` y `analyst_agent.py` son idénticos a los de `Quarkus_refact`. Por tanto conserva los reportes calculados de tests/cobertura sin ejecución Java. Los pedidos siguen en un diccionario en memoria; no se añadió persistencia a ese flujo.

Esta candidata mejora la entrega de la fábrica, pero tampoco acredita funcionamiento completo. El selector integrado de `Unificado` comparte código y procesos; no se adoptó automáticamente porque el objetivo del usuario es conservar los dos sistemas independientes.

## Decisión que permite esta auditoría

Sí hay versiones Quarkus históricas recuperables, pero **no se encontró una versión que permita afirmar que todos los caminos funcionan íntegramente como Quarkus**. `5d9b190` es la candidata histórica para conservar el Studio de diez pestañas; la fábrica de `Unificado` es una candidata distinta, con entrega corregida y otros defectos pendientes. No deben sustituirse entre sí sin reconocer la diferencia de flujo.

El snapshot Spring actual, incluidos los cambios locales autorizados, sigue conservado en la rama `dual-systems-selector`. Su copia provisional de `Quarkus_refact_2` no se reemplazó durante esta revisión. Las ramas originales y sus cambios locales permanecen intactos.

Se verificaron nuevamente los snapshots de las dos copias del borrador (1446 archivos Spring y 1171 de la rama remota `Quarkus_refact_2`). Los 1446 archivos correspondientes en el directorio original `agentIA` también coinciden byte a byte con el snapshot autorizado. Las tres copias de auditoría no tienen diferencias en sus archivos fuente rastreados.

## Evidencia

- `validation/quarkus-history.json`: 172 commits, revisión de árboles, merge, padres y consultas de ancestralidad.
- `validation/quarkus-history-recovery.json`: descubrimiento original de objetos sin referencia y comparación de servicios con `Unificado`.
- `validation/quarkus-recovered-5d9b190-generation.json`: archivos y POM generados por las cinco etapas recuperadas.
- `validation/quarkus-recovered-c5bda02-generation.json`: importación incompleta y salida del nodo anterior.
- `validation/quarkus-recovered-focused.xml`: 115 aprobadas y una omitida.
- `validation/quarkus-recovered-v1-backend.xml`: dos errores de colección de la alternativa V1.
- `validation/quarkus-recovered-frontend.xml`: resultado de la suite frontend completa de la versión Studio recuperada, ejecutada directamente con Node para preservar los argumentos del runner.
- `validation/quarkus-unificado-lifecycle.xml` y `quarkus-unificado-audit.json`: ciclo y casos críticos de la fábrica en `Unificado`.

Los scripts `audit_quarkus_history.py`, `audit_quarkus_recovery.py`, `audit_recovered_generation.py` y `audit_quarkus_candidate.py` registran cómo repetir las inspecciones. No se certifican compilación Java, despliegue Docker ni publicación remota: no se ejecutaron. La generación de fuentes y las comprobaciones Python se presentan como tales.
