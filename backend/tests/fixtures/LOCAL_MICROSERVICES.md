# Catálogo de fixtures locales, versión 2

El generador compartido está en `backend/scripts/local_microservice_fixture.py`. Crea fuentes nuevas para Maven/Gradle × H2/PostgreSQL/MySQL sin IA, Java del host, Docker ni descargas. Rechaza destinos no vacíos y opciones ajenas al catálogo. No migra proyectos históricos.

Desde la raíz, con Python del proyecto:

```powershell
$env:PYTHONPATH = "$PWD\backend"
.\.venv\Scripts\python.exe -m scripts.local_microservice_fixture --destination .run\fixture-maven-h2 --build maven --database H2
.\.venv\Scripts\python.exe -m scripts.local_microservice_fixture --destination .run\fixture-gradle-mysql --build gradle --database MYSQL --seed
```

Use un destino nuevo en cada comando. La elección de build/BD está limitada a los seis pares del catálogo. `--layout bootstrap` genera el módulo allí; las pruebas también pueden solicitar `assets=False` para fuentes sin manifiestos Docker.

## Contenido y evidencia

- Entidad Item con ID persistente y nombre obligatorio; SQL del motor y configuración local coherente.
- POST/listado/GET/DELETE generados normalmente. El generador genérico aún carece de actualización: FixtureUpdateController añade PUT exclusivamente al fixture, mediante ItemService y su implementación, sin acceso directo a repositorios desde el controlador. La versión 2 corrige esa frontera para mantener el gate SAST real. No modifica la generación del producto ni acredita actualización en todo microservicio generado.
- Tests Java generados de servicio y controlador; generarlos no significa ejecutarlos.
- Variante `--seed`: tabla inventory_records, BigDecimal/LocalDateTime, DDL y semilla fija. Payload válido/ inválido en FIXTURE_MANIFEST.json.
- Manifiesto con versión, parámetros, SHA256 de las fuentes/build/SQL, ejecución NOT_EXECUTED y offlineVerified=false. La generación no escribe PASS de compilación/despliegue. Los hashes cambian si cambia el generador; se deben preparar otra vez dependencias cuando cambia su fingerprint. No es el snapshot inmutable pendiente de T20.
- Identidad/puerto de assets pueden variar por sesión; los hashes de fuentes del mismo par/variante se reproducen en destinos diferentes.

Las credenciales de PostgreSQL/MySQL se proporcionan aparte en ejecución. No se guardan contraseñas de prueba en fuentes ni en el manifiesto.

## Pruebas y consumidores

`test_local_microservice_fixtures.py` comprueba los seis pares, ambas variantes, layout bootstrap, hashes reproducibles y rechazo de sobrescritura, con procesos externos prohibidos. No sustituye build/CRUD reales de cada combinación.

La prueba independiente de entrega, la transferencia real de kit y el sandbox bootstrap generan fuentes nuevas en lugar de copiar un workspace histórico de `.run`. `scripts/verify_local_database.py` comparte este catálogo, verifica también PUT y devuelve salida distinta de cero cuando falla su reporte.

Las pruebas Docker siguen siendo opt-in. No preparan ni descargan automáticamente al ejecutarse, salvo el probe `verify_local_database.py`, cuya preparación inicial online es explícita en su secuencia. Use imágenes/dependencias preparadas para entrega/sandbox/kit. La matriz real completa, las dependencias y los límites de cada ejecución se registran en `docs/ESTADO_DESPLIEGUE_LOCAL_DOCKER.md`.
