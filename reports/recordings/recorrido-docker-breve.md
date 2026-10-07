# Recorrido breve Docker / PostgreSQL — 2026-10-05

Proyecto: `catalogo-docker-demo`.
Sesión: `93133750-89b4-4eb9-b041-949d73471730`.
Motor utilizado: DeepSeek (`deepseek-flash`); clave efímera, fuera de la grabación.

Se creó un proyecto nuevo desde la interfaz, se generaron requisitos, historias BDD,
arquitectura, modelo SQL, Java y pruebas. La versión final pasó 33/33 pruebas en Docker.
Snapshot final verificado y desplegado: `8547bdb85b4d4458ba3bf6ec9b1989ca`.

Durante la prueba real de creación, PostgreSQL devolvió HTTP 500 porque la tabla
exigía `fecha_creacion` y `fecha_actualizacion`, pero el DTO y la entidad generados
solo enviaban `nombre` y `precio`. Se añadió una nueva migración Liquibase
`003-audit-date-defaults.sql` con valores por defecto `CURRENT_TIMESTAMP` para
esas columnas. No se modificaron los checksums de migraciones ya aplicadas.
Se verificaron de nuevo las fuentes y se desplegó el snapshot corregido.
Esta corrección corresponde al microservicio de demostración; no implica que
otros proyectos generados tengan cubiertas todas sus posibles discrepancias.

Resultado observado en la interfaz:
- Aplicación `HEALTHY`, Actuator `UP`, base de datos `POSTGRESQL`.
- Puerto final 8082, seleccionado automáticamente al detectar puertos ocupados.
- POST `/api/v1/productos`: HTTP 201, producto id 4, nombre `Teclado demo Docker`, precio 49.99.
- Reinicio conservando datos: operación terminada.
- GET `/api/v1/productos/4` después del reinicio: HTTP 200, mismos datos.
- Auditoría SAST mostrada: Quality Gate aprobado.

La grabación nueva se hizo con OBS. Se pausaron las esperas y se recortó un bloqueo
del control del navegador. El vídeo entregado es una edición breve de la misma sesión:
las vistas de resultados se agruparon en orden de presentación. No es una toma continua
ni una afirmación de que el primer despliegue funcionó sin la corrección descrita.
Se eliminan la barra del navegador y las franjas exteriores; no aparece el aviso
de guardar contraseña. El archivo original se conserva.

También se ajustó el campo de API de AgentIA para mantener la clave oculta sin
presentarlo al navegador como una contraseña de inicio de sesión. El frontend compiló.

Archivo final: `recorrido-docker-breve-nuevo.mp4`.
El manifiesto contiguo documenta las fuentes y los cortes exactos.
