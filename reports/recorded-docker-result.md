# Recorrido Docker grabado — 5 de octubre de 2026

Resultado: un microservicio nuevo generado con DeepSeek, verificado en Docker y desplegado localmente con PostgreSQL. Se conserva en ejecución.

- Servicio: `inventario-docker-demo`.
- Sesión: `5748a742-752a-4f0f-af53-99ee08ccfe2a`.
- Stack: Java 21, Spring Boot 3, Maven y PostgreSQL.
- Generación: COMPLETED / VERIFIED, 24 pruebas aprobadas de 24, sin fallback, cero iteraciones de reparación.
- Snapshot verificado: `0a6e97298c194699983f962a2f0cc5ab`.
- Despliegue: HEALTHY, Actuator UP, PostgreSQL confirmado; URL `http://localhost:8080`.
- Creación mediante consola REST de la interfaz: POST `/api/v1/items` respondió 201; registro id 2, nombre `Articulo de demostracion`, cantidad 7.
- Reinicio desde la interfaz conservando datos: operación RESTART / COMPLETE con finalización persistida. GET `/api/v1/items/2` respondió 200 después del reinicio y otra vez al cerrar el recorrido.
- Smoke test desde la interfaz: Actuator UP.

## Errores corregidos

1. Estado nativo de ACL del sandbox corrupto (22 bytes NUL). Se conservó una copia y el inicializador nativo regeneró su estado válido; no se desactivó el sandbox.
2. Una consulta de salud tardía sobrescribía la finalización de la misma operación Docker, dejando la interfaz bloqueada en READINESS aunque el servicio estaba saludable. La persistencia ahora conserva la finalización de esa operación; una operación nueva puede avanzar normalmente. Se reinició el backend y se comprobó el reinicio del servicio desde la interfaz.
3. El explorador de código mostraba “Sin datos” porque no solicitaba las métricas persistidas. Ahora consulta la API, valida los conteos y evita aplicar respuestas de sesiones anteriores. Se comprobó visualmente “24 / 24 Pasadas (100%)”.
4. El selector mostraba instrucciones de modo sin Docker aun con Docker seleccionado. Ahora presenta el texto del modo elegido.

Verificación de las correcciones: 24 pruebas backend (`test_local_operation_controls.py` y `test_runtime_lifecycle.py`), 17 pruebas frontend (`views_generation_explorer.test.tsx` y `verification_views.test.tsx`) y compilación de producción correcta. Vite mantiene su advertencia de tamaño del bundle.

## Grabación y límites observados

Se utilizó la skill OBS Screen Recorder, con una sola grabación continua desde antes de crear el proyecto hasta la comprobación final. Incluye esperas, diagnóstico y recuperación del backend; no es una demostración editada sin incidencias. La ventana de Brave se abrió automáticamente, sin requerir intervención manual del usuario.

- [Vídeo completo](<C:/Users/willi/Videos/2026-10-05 13-03-47.mp4>)
- Archivo verificado por OBS al detenerse: 514953443 bytes.
- Último timecode informado: `01:58:52.433`.
- [Captura final](recorded-docker-current-scene.png): servicio saludable y consulta HTTP 200; aparece también un aviso de Brave para guardar contraseña, con su contenido enmascarado. No se aceptó guardar credenciales.

Las fechas obligatorias del DTO se enviaron en la consola REST; el formulario CRUD con campos de fecha no quedó validado por este recorrido. Hubo una lectura transitoria DOCKER_UNAVAILABLE que se recuperó en la siguiente consulta; no se cambió su timeout. Las pruebas automáticas de persistencia utilizan H2 en modo PostgreSQL; el despliegue y la consulta del registro se realizaron contra PostgreSQL real en Docker.

La contraseña de PostgreSQL permanece en el `.env` local de esta sesión, excluido del repositorio y de la exportación. El informe no contiene claves API ni contraseñas.
