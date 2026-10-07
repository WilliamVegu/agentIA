# Despliegue local Windows

Docker es opcional para generar y exportar fuentes. Para ejecutar necesita Docker Desktop con contenedores Linux y virtualización disponible.

1. Para PostgreSQL/MySQL copie `.env.example` a `.env` y defina contraseñas locales.
2. Con conexión, ejecute `./prepare-local.ps1` (prepara imágenes y dependencias de este proyecto).
3. Sin conexión, ejecute `./start-local.ps1 -Port 8080`. No requiere Java ni Maven/Gradle instalados en Windows.
4. `./stop-local.ps1` conserva los datos; `./cleanup-local.ps1 -DeleteData` los elimina explícitamente.

Las dependencias nuevas requieren repetir la preparación. El arranque offline compila y ejecuta pruebas dentro del build sin red. Liquibase aplica el SQL y las semillas versionados; Hibernate valida el esquema sin modificarlo. La preparación ejecuta pruebas con red para resolver también sus dependencias: ese resultado no se registra como verificación offline.

CI y Kubernetes se entregan como artefactos; su presencia no acredita una ejecución real.

El esquema y las semillas se aplican mediante Liquibase dentro del JAR, una sola vez por base de datos. Hibernate valida el esquema. Las migraciones publicadas no se editan: los cambios posteriores requieren una nueva versión. `schema.sql` y `data.sql` existentes se conservan; la configuración del datasource no se reemplaza. `db/changelog/LOCAL_MIGRATIONS.json` registra motor y hashes del SQL normalizado. Retirar semillas o cambiar el motor después de publicar se rechaza: conserve el historial y use una migración adicional o un proyecto/base nuevos.

La imagen de aplicación, los contenedores y los volúmenes pertenecen al proyecto Compose de esta carpeta. Dos sesiones con el mismo nombre de servicio usan imágenes distintas. Los scripts fijan el proyecto con `-p`; al usar Compose manualmente conserve ese nombre para operar sobre los mismos datos. Copias con el mismo nombre de carpeta no se consideran automáticamente proyectos distintos.

`restart-local.ps1` reinicia sin build/pull, conserva datos y usa el puerto anterior o uno alternativo si está ocupado. `runtime-common.ps1` debe acompañar a los scripts: inspecciona propiedad antes de operar. La limpieza requiere `-DeleteData`, elimina solo contenedores/volúmenes/redes propios y conserva fuentes, historial e imágenes. Un error no se registra como parada/reinicio/limpieza aprobados.

## Entrega y arranque independiente

`start-local.ps1 -SourcesOnly` finaliza sin consultar Docker: las fuentes se entregan con ejecución omitida. `start-local.ps1 -Port 8080` comprueba dependencias, motor Linux, imágenes preparadas y aislamiento de Compose, construye offline y utiliza el reinicio inspeccionado para readiness/puerto alternativo. `-ReuseImage` omite construcción y nuevas pruebas: requiere la imagen de aplicación existente. Un error detiene el script; no se descarga ni prepara automáticamente. No necesita AgentIA, IA, Java/Maven/Gradle en Windows.

`LOCAL_DELIVERY.json` indica versiones previstas, dependencias y volúmenes propios. El ZIP es de fuentes y scripts: las imágenes pesadas se transfieren por el kit separado; no es un ejecutable autocontenido. La metadata generada comienza con NOT_EXECUTED. En el ZIP, DELIVERY_STATUS.json registra la evidencia actual de la sesión, incluyendo omisiones o resultados obsoletos. La presencia de scripts, un build exitoso o readiness no inventa un resumen de pruebas. Stop/restart conservan appdata y, para PostgreSQL/MySQL, dbdata; cleanup requiere -DeleteData.
