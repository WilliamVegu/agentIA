# Migraciones locales y conservación de datos

Docker sigue siendo opcional. Generar SQL y activos no ejecuta una base de datos ni acredita pruebas. En SOURCE_ONLY se puede terminar y exportar el proyecto sin virtualización.

Los proyectos nuevos empaquetan `db/changelog/db.changelog-master.xml` en el classpath. Liquibase aplica esquema y semillas una vez por base; Hibernate usa `validate` y la inicialización SQL de Spring está deshabilitada. PostgreSQL/MySQL tienen volumen de base y H2 usa un archivo en el volumen de aplicación. Parar o reconstruir conserva esos volúmenes.

`LOCAL_MIGRATIONS.json` registra el motor y SHA256 de los textos SQL iniciales normalizados a UTF-8/LF. Las fuentes `schema.sql` y `data.sql` se conservan. Regenerar rechaza una migración inicial modificada, una semilla retirada/vaciada, un motor diferente o propiedades efectivas que contradigan el changelog, `ddl-auto=validate` o `sql.init.mode=never`. No restaura ni borra los datos para resolver el conflicto.

Para cambiar un esquema existente, agregue un SQL nuevo y un changeSet con ID nuevo al changelog, preservando los anteriores. Compruebe el cambio sobre una copia de la base antes de usarlo con datos importantes. Para cambiar de motor, use un proyecto/base nuevos con SQL de ese dialecto; la herramienta no migra datos entre motores. No elimine el registro para simular una nueva migración publicada.

Los conflictos se validan antes de copiar los archivos de migración y propiedades. Esta validación no equivale a una transacción del sistema de archivos ante una caída ni a exclusión entre procesos. El generador de activos mantiene su staging y rollback existentes.

Aceptación reciente: Maven/H2 con semilla, ocho pruebas Maven reales, CRUD/validación, puerto ocupado alternativo, parada/reutilización de imagen y reconstrucción sin duplicar la semilla ni perder la fila editada. Los recursos propios de prueba fueron retirados. Esta prueba usa imágenes preparadas y comandos de build offline; no acredita bloqueo externo de internet ni un equipo limpio.

PostgreSQL/MySQL y Gradle conservan evidencia anterior, pero requieren aceptación actualizada de este bloque. También siguen pendientes la matriz de tipos/relaciones y la unificación completa del diseño Models & SQL con el motor elegido. Consulte la sección 39 del [estado](C:/Users/willi/Downloads/agentIA/docs/ESTADO_DESPLIEGUE_LOCAL_DOCKER.md).
