# Comparación de Quarkus_refact y Quarkus_refact_2

Revisión del 7 de octubre de 2026. Se inspeccionaron los commits remotos y se ejecutaron ambas versiones en copias aisladas. No se cambiaron las aplicaciones ni la carpeta original de `no-docker`.

## Conclusión

**`Quarkus_refact` contiene la fábrica Quarkus. `Quarkus_refact_2` contiene Spring Boot.** La segunda tiene una fecha más reciente, pero no conserva el sistema Quarkus de la primera. Para reunir Spring Boot y Quarkus, la fuente correspondiente es `Quarkus_refact`; sin embargo, se reprodujeron fallos que impiden certificar su funcionamiento completo. El selector permanece como borrador local, sin publicación, mientras se resuelve esta diferencia.

| Aspecto | Quarkus_refact | Quarkus_refact_2 |
|---|---|---|
| Commit revisado | `e7511d1d03459d2263b84d38659d45a44e8f4054` | `7efbc188888dc80a76fa11b2116555a9340c95d0` |
| Fecha del commit | 05/10/2026 | 07/10/2026 |
| Tecnología del flujo principal | Quarkus 3.x / Java 21 | Spring Boot 3.x / Java 21 |
| Interfaz principal | Fábrica Quarkus de 7 pasos y dos aprobaciones | Studio de 10 pestañas Spring Boot |
| Archivos específicos de Quarkus | 23 | 0 |
| API `/api/v1/quarkus/*` registrada | 12 rutas | Ninguna |
| Acceso autenticado a `/api/v1/quarkus/orders` | API existente | 404, incluso después de iniciar sesión |
| Compilación TypeScript + Vite | Aprobada | Aprobada |
| Pruebas backend | 143 aprobadas; 6 fallidas | 927 aprobadas; 162 fallidas; 3 omitidas |
| Pruebas frontend | 61 aprobadas; 3 fallidas | 59 aprobadas; 9 fallidas |

Los tamaños y coberturas de las suites son diferentes; sus conteos no constituyen una clasificación directa de calidad. Los JUnit y la auditoría HTTP permiten revisar los casos concretos. La primera suite backend se ejecutó con el Python instalado del equipo; la segunda con un entorno separado y las versiones registradas del entorno fuente, sin la dependencia opcional MLflow.

## Historia y contenido

Ambas ramas comparten `1a9223fd820de77551146b1da87d058817136276` como ancestro común, pero sus líneas posteriores difieren. La primera contiene `10c10ae`, que implementa la fábrica Quarkus. La segunda sigue la línea del merge `19627d8` de `no-docker`. Su último commit, `7efbc18`, únicamente añade dos líneas a `notita_dip.txt`.

La diferencia incluye la ausencia en la segunda rama de `routes_quarkus_factory.py`, los agentes de `services/quarkus_factory/`, `QuarkusContext` y las vistas de `views/quarkus/`. Su constitución e instrucciones del scaffolder exigen Spring Boot. La comprobación en vivo de `/openapi.json` confirma que no registra ninguna ruta Quarkus.

## Fallos reproducidos en la fábrica real Quarkus

Se usaron requests locales con proveedor `mock`, tanto Maven como Gradle, un contrato OpenAPI personalizado y PostgreSQL seleccionado. No se necesitaron llamadas a IA ni publicación Git para reproducir estos problemas.

1. **La aprobación final falla y deja el flujo incompleto.** POST `approve-delivery` devuelve 404 con `too many values to unpack (expected 2)`. `factory_orchestrator.py:672` espera `(artifacts, devops_tokens)`, mientras `documenter_devops_service.py:330` devuelve únicamente un diccionario. La excepción se presenta como 404 aunque el pedido existe. La suite de ciclo completo también falla precisamente en esta operación. El orquestador marca `control_2_approved=True` antes de completar esa operación; falta consistencia ante errores.

2. **Pruebas, cobertura, revisión y auto-reparación se presentan como ejecutadas sin evidencia de ejecución.** La API devolvió `tests_executed=true`, siete tests aprobados, cobertura 94,4 %, `BUILD SUCCESS` y revisión 98. `developer_qa_service.py:309` calcula esas cifras a partir del número de tablas; no ejecuta Java, Maven, Gradle ni Docker. `factory_orchestrator.py:545` marca ejecución, y sus registros de reparación y score también son valores prefijados. Esta aprobación no demuestra compilación ni pruebas reales. En modo de solo fuentes debería informar pruebas generadas/no ejecutadas; una aprobación real requiere exit code y resultados medidos.

3. **El contrato editado no dirige los recursos concretos.** Se aprobó `/warehouse/items`; aparece en la interfaz generada, pero no en los `*Resource.java` concretos. Estos generan rutas desde los nombres de tablas, por ejemplo `/api/v1/clientes`. Tampoco implementan la interfaz del contrato. `developer_qa_service.py:102` deriva la ruta de `table.name`. Además, los recursos aceptan y devuelven entidades de persistencia, a pesar de que la revisión prefijada afirma que están desacopladas. Deben mapear fielmente operaciones, parámetros y DTOs del contrato aprobado.

4. **Se ignora la base de datos elegida al generar configuración.** Con PostgreSQL seleccionado, el `application.properties` producido configura SQLite en desarrollo/pruebas y SQL Server en producción. `scaffolder_service.py:346` lee `db_type`, pero la plantilla de perfiles en 391–404 es fija. El driver y los perfiles deben ser coherentes con la selección y la arquitectura aprobadas.

5. **Los pedidos desaparecen al reiniciar.** Después de detener e iniciar el backend, GET de ambos pedidos devuelve 404 y la lista está vacía. `factory_orchestrator.py:36` guarda pedidos únicamente en `_orders_db`, un diccionario en memoria; el SQLite del sistema genérico no persiste estos pedidos. Se necesita persistencia de pedidos, aprobaciones, contrato, artefactos y estado antes de confiar en continuidad de trabajo.

6. **La opción de seguridad “Sin autenticación” no completa la aprobación del contrato.** Crear el pedido funciona; aprobarlo devuelve 400 con `SecurityEnum has no attribute OIDC`. `architect_agent.py:405` usa `SecurityEnum.OIDC`, pero el enum declara `OAUTH2`. Deben probarse las tres selecciones del formulario sin depender de la rama JWT para evitar esa excepción.

7. **La API acepta un pedido vacío aunque el flujo exige datos propios.** POST `/orders` con `{}` devuelve 201 y servicio `microservice`; la validación de nombre, equipo, groupId y descripción existe en el formulario, pero el backend conserva defaults permisivos. La validación debe corresponder al contrato de entrada también desde la API.

La descarga ZIP devuelve 200 incluso después de fallar la aprobación final. Es una exportación de fuentes, y no debe confundirse con una entrega validada. La generación de artefactos DevOps actual crea archivos y mensajes de “PR preparado”; la ruta de aprobación de la fábrica no realiza por sí misma una publicación real a Git.

## Qué sí se comprobó y qué significan los fallos de las suites

`Quarkus_refact` arranca, renderiza su formulario y navegación de siete pasos sin excepciones JavaScript ni HTTP 5xx iniciales. Se crean pedidos, se aprueban contratos JWT, se selecciona arquitectura, se generan fuentes Quarkus con Maven y Gradle y se descarga el ZIP. Esto acredita un flujo de diseño/generación parcial, sujeto a los problemas descritos.

Sus tres fallos frontend incluyen tests que aún esperan las diez pestañas del Studio anterior y un test de Sidebar sin `QuarkusProvider`. En backend, además del fallo real de entrega, hay desacuerdos entre modelos esperados en tests y la configuración del proveedor, y dos respuestas 500 del flujo de requisitos con proveedores simulados. No se verificó disponibilidad real de esos modelos ni se probaron claves de terceros.

`Quarkus_refact_2` arranca y permite acceso local y navegación del Studio Spring. Las comprobaciones anteriores del selector entre esta copia y `no-docker` pasaron 53 verificaciones en navegador: dos interfaces, cookies separadas, diez pestañas por copia, persistencia y separación de especificaciones, cierre de sesión independiente y ausencia de 5xx. **Son dos copias Spring Boot; estas pruebas no acreditan dos frameworks.** En su suite backend, muchos fallos son tests que llaman rutas protegidas sin sesión y esperan 200/201; esto no justifica eliminar la autenticación. También aparecen fallos de generación, contratos y publicación simulada que requieren revisión individual.

## Tratamiento de Spring Boot actual y propuesta de integración

La versión actual de `no-docker`, incluidos los cambios locales indicados por el usuario, quedó conservada en el nuevo worktree `agentIA-dual-systems`, rama local `dual-systems-selector`. Se guardó su snapshot en el commit `41864b5`; la carpeta original y su rama no se cambiaron. Sus 105 pruebas frontend y su compilación pasan. En la suite backend aislada hubo 1409 aprobadas, 58 fallidas y 42 omitidas; muchos fallos de scripts están asociados a procesos PowerShell con exit code `3221225794`. Un caso se repitió con el Python original del equipo y pasó, por lo que no deben atribuirse automáticamente todos esos fallos al código. La evidencia está incluida.

Para lograr el objetivo original, recomiendo mantener Spring Boot actual y tomar la fábrica real de `Quarkus_refact` en otra carpeta, con entornos, procesos, puertos y datos independientes. Antes de afirmar que ambos funcionan por completo, corregir en la copia Quarkus los bloqueos de entrega, el reporte de pruebas sin ejecución, la fidelidad al contrato/base de datos y la persistencia. Son cambios necesarios en la copia Quarkus, sin mezclarla con Spring Boot ni modificar las ramas originales.

La copia provisional de `Quarkus_refact_2` aún no se sustituyó por `Quarkus_refact`; esta revisión responde a la solicitud de comparar ambas antes de decidir la fuente final. No se publicó el borrador de integración en GitHub.

## Evidencia reproducible

- `validation/suite-counts.json`: conteos derivados de los JUnit de las tres versiones.
- `validation/quarkus-branch-live-audit.json`: respuestas HTTP y contrastes del contrato/base de datos.
- `validation/quarkus-refact-maven-order.json` y `quarkus-refact-gradle-order.json`: estados y fuentes devueltas por la API.
- `validation/quarkus-refact-maven-audit.zip` y `quarkus-refact-gradle-audit.zip`: fuentes exportadas para inspección.
- `validation/quarkus-refact-restart.json`: pérdida de pedidos tras reinicio real.
- `validation/quarkus-refact-browser.json` y `quarkus-refact-studio.png`: navegador real de la fábrica.
- JUnit backend/frontend y logs locales en `.run/dual/`.

No se certifican compilación Java real, despliegue Docker, persistencia SQL de microservicios desplegados, proveedores IA ni publicación Git. Docker/Maven/Gradle/Java no están disponibles en PATH en este entorno. Los resultados de QA devueltos por la fábrica no se usaron como evidencia de ejecución real.
