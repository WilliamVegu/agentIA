# Migración y recuperación conservadora

El startup de cada backend ejecuta una migración aditiva, versionada y con checksum. No modifica el esquema por importar modelos. Antes de migrar una SQLite existente se crea un backup; la segunda ejecución es idempotente. Un error detiene la migración y las mutaciones dependientes, con diagnóstico visible.

## Procedimiento

1. Detener los procesos backend propios. Registrar versión de código, ubicación de SQLite y workspace, y operaciones abiertas. Conservar una copia de SQLite consistente y de las fuentes; no imprimir variables que contienen credenciales.
2. Ensayar el startup con una copia de la base y un workspace aislado, usando `DATABASE_URL` y `WORKSPACE_DIR` explícitos. Ejecutar la suite `migration` del quickstart y repetir el startup para comprobar idempotencia.
3. Comprobar el registro SchemaMigration y conservar su checksum y backup. Revisiones legacy incompletas requieren revisión humana; no se inventa aprobación, PASSED ni propiedad Docker.
4. Ejecutar el nuevo backend sobre la ubicación prevista y revisar las sesiones. Operaciones inconclusas pasan a INTERRUPTED; el historial y las fuentes se conservan. La recuperación no inicia efectos externos automáticamente.

## Reversión y fallos

La migración añade tablas/columnas y conserva datos legacy. Revertir el código debe ensayarse sobre una copia: el código anterior puede ignorar información nueva y no debe emplearse para escribir durante una operación nueva. No borrar columnas ni restaurar una base vieja sobre registros posteriores. Una restauración del backup solo procede sobre una ubicación nueva o tras resolver expresamente qué datos posteriores deben conservarse.

Si el checksum no coincide o la migración falla, detener escrituras, conservar base, backup y diagnóstico, y corregir la causa. No editar el historial de migraciones para aparentar éxito. Recursos Docker legacy sin identidad completa quedan UNKNOWN; no se asignan a una sesión por nombre de puerto o carpeta.

## Evidencia

`integration/validation/reliability/migration/migration-summary.json` registra doce pruebas aprobadas por estudio: creación, legacy, repetición, fallo y autoridad del draft/proyección. `journeys/real-restart.xml` registra dos caídas reales de proceso y recuperación sin efectos externos. Las pruebas de conservación PostgreSQL/MySQL tienen informes separados. Son ensayos sobre recursos propios; no constituyen una migración de datos del usuario ni autorización para destruirlos.
