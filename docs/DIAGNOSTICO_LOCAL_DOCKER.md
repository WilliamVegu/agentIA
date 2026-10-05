# Diagnóstico Docker bajo demanda

En DevOps solicite el diagnóstico de una sesión, o consulte el endpoint privado `GET /api/v1/devops/{session_id}/diagnostics` con autenticación local. Leer el estado de una sesión no activa estas comprobaciones. En SOURCE_ONLY se devuelve SKIPPED_BY_CHOICE antes de consultar CLI, paths o Docker; no exige virtualización ni herramientas sustitutas.

Cuando se eligió DOCKER, el diagnóstico comprueba:

- Permiso administrativo DOCKER_ENABLED, CLI, contexto, Compose y plugin Buildx.
- Builder seleccionado mediante buildx inspect, sin --bootstrap: nodos operativos o estado no verificable.
- Motor Linux, escritura temporal del workspace y espacio libre del disco host.
- Imágenes requeridas con ID SHA256 y arquitectura compatible con el motor; no descarga imágenes ausentes.
- Caché host alternativa Maven/Gradle: directorio legible/no vacío, sin prometer dependencias completas. Su ausencia no impide usar el builder preparado.
- Caché del builder preparado: directorio legible y al menos un JAR, mediante contenedor temporal UUID sin red, pulls, mounts, escritura de rootfs ni build. La comprobación no compila/prueba el microservicio.

El contenedor de caché usa --rm, memoria 64 MiB, CPU 0.5, límite 32 procesos, cap-drop ALL y no-new-privileges. Ante interrupción solo se retira un recurso cuya etiqueta io.agentia.diagnostic coincida con el UUID generado. Si no se confirma su final/limpieza, la caché queda UNKNOWN. Nunca se limpia globalmente Docker ni se retiran contenedores de otras sesiones.

## Interpretación

readyForPreparation exige infraestructura operativa, workspace escribible y mínimo de espacio host. No estima el almacenamiento interno de Docker ni el tamaño completo del build. preparedImagesAvailable acredita imágenes locales compatibles; no significa caché completa. offlineVerified permanece false incluso si todos los checks son AVAILABLE.

Una caché AVAILABLE demuestra lectura básica de artefactos, no cobertura de todas las dependencias/plugins. La aceptación se obtiene ejecutando la verificación offline del proyecto vigente con suite no vacía y evidencia real. Dependencias nuevas requieren preparación explícita nueva.

Si falta infraestructura, las acciones son Reintentar y Continuar sin Docker. No se arrancan builders automáticamente, instalan herramientas, cambian permisos/virtualización ni habilita red para resolver fallos.

## Límites configurables del backend

LOCAL_DIAGNOSTIC_CACHE_TIMEOUT: 15 segundos por defecto, entre 1 y 60. Las demás consultas CLI están acotadas a 4 segundos cada una; hay consultas adicionales por imagen y para comprobar limpieza. No es un límite global de toda la petición.

LOCAL_MIN_FREE_BYTES: 536870912 bytes (512 MiB) por defecto, ajustable desde 0. Es un umbral preventivo, no una estimación de todo el espacio que requieren imágenes/builds. Un disco cuya lectura falla no se anuncia como preparado.

El diagnóstico no comprueba todas las restricciones de bind mounts de Docker Desktop ni sustituye el arranque/CRUD/persistencia real. No certifica equipo/motor limpio ni bloqueo de red externa. Resultados y aceptación están en ESTADO_DESPLIEGUE_LOCAL_DOCKER.md.
