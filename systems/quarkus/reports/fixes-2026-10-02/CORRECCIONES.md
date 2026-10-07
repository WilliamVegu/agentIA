# Correcciones aplicadas — 2 de octubre de 2026

Rama: `levantando_observaciones`. Base: `61c0f29`. Los cambios están en el árbol de trabajo; no se creó un commit ni se publicó un repositorio.

## Cambios

| Área | Corrección |
|---|---|
| Verificación | Una suite vacía, un fallback o un build sin pruebas ya no producen VERIFIED. Auto-Pilot bloquea cuando el sandbox no puede verificar. Alcanzar una fase parcial mantiene el proyecto PAUSED. |
| Evidencia | Las métricas incluyen una huella del código, configuración de compilación y artefactos de requisitos. Modificar estos archivos invalida la evidencia anterior. Las sesiones antiguas sin esa huella requieren verificar nuevamente. |
| Exportación y publicación | ZIP, bundle y publicación Git comparten la política de verificación real y siguen aplicando el Quality Gate. COMPLETED por sí solo no autoriza exportar. |
| Historial y progreso | El historial no deriva VERIFIED de COMPLETED. Consultar el listado deja de cambiar el estado del proyecto. El overview exige evidencia actual. Generar manifiestos no equivale a desplegar. |
| Cola | Los trabajadores asíncronos y los hilos comparten una única capacidad FIFO. Cancelar conserva el puesto del trabajador hasta que termina. Las reparaciones también reservan capacidad. |
| Pausa y reanudación | Se comprueba que exista un hilo vivo. Reanudar no crea otro hilo mientras el anterior sigue ejecutándose. La cancelación persiste CANCELLED al terminar el trabajador. |
| Autenticación | Login real en el servidor, cookie HttpOnly, caducidad y revocación al cerrar sesión. API privada sin acceso mediante un correo inventado o localStorage. Se eliminó el acceso automático de demostración. Es un estudio de un único operador, no una plataforma multiusuario. |
| Guardados | Arquitectura utiliza el mismo control de rutas que requisitos/modelos. Guardar modelos exige una sesión existente en la base de datos. Aprobar requisitos conserva los metadatos del borrador recibido. |
| Proveedor y modelo | Las vistas y rutas propagan el modelo seleccionado, incluidos modelos/SQL, generación de sesiones y Auto-Pilot. Modelos/SQL y requisitos no ocultan un fallo del proveedor con un resultado local. La refinación de modelos utiliza el proveedor real. |
| Tests y reparaciones | La síntesis guiada y la planificación de reparación usan el proveedor seleccionado cuando está configurado. Se eliminaron los conteos de cinco pruebas supuestamente aprobadas. Una reparación manual vuelve a verificar; una reparación automática persiste los cambios y verifica antes de declarar éxito. |
| Auditoría | Un payload vacío deja de aprobar con score 100. Las vulnerabilidades encontradas conservan sus conteos aunque no haya líneas Java evaluadas. |
| Arquitectura | El perfil hexagonal reemplaza las instrucciones de cuatro capas. La validación rechaza paquetes de la arquitectura equivocada y dependencias del dominio/aplicación hacia infraestructura. Se admiten capas domain y application en el diseño. |
| Gradle | Generación, sandbox, Dockerfile y CI seleccionan Gradle. El sandbox usa ejecución offline y lee reportes XML actuales; elimina reportes anteriores antes de ejecutar. Las dependencias de despliegue se preparan antes de establecer la evidencia. |
| Git | La credencial pasa por el entorno del proceso hijo mediante un encabezado HTTP, sin URL autenticada en argumentos o configuración. Se eliminó la bifurcación que detectaba pruebas dentro del código de producción y el push forzado predeterminado. |
| Despliegue | El ID y puerto se consultan en Compose, se usa el proyecto de la sesión y se eliminan nombres globales de contenedores. Detener no borra los volúmenes. Su funcionamiento real sigue pendiente por Docker inaccesible. |
| Costes | Las llamadas guiadas asociadas a una sesión y las llamadas de Auto-Pilot quedan dentro del contexto de registro. Se comprobó una llamada HTTP real con coste persistido. |

## Comprobaciones realizadas

- **52 pruebas de backend aprobadas; 1 omitida.** Suites: contratos de perfiles, seguridad, montaje del sandbox y honestidad de la verificación. Son pruebas unitarias; no demuestran compilación Java.
- **29 regresiones locales aprobadas**, con almacenamiento aislado: autenticación, exportaciones, huella de archivos, cola mixta, cancelación, auditoría vacía, reparación manual sin Docker, sesión inexistente, manifiestos Gradle y credenciales Git con token ficticio y destino local cerrado.
- **5 comprobaciones en Edge aprobadas**, contra backend y frontend reales aislados: API anónima rechazada, login válido, sesión después de recargar, logout persistente y ausencia de errores de aplicación en la página. Las respuestas HTTP no se sustituyeron.
- **1 prueba de frontend aprobada**: un usuario inventado en localStorage no concede acceso.
- **Build TypeScript/Vite aprobado.** Permanece el aviso de bundle superior a 500 kB.
- **109 módulos Python analizados sintácticamente** y `git diff --check` sin errores.
- **DeepSeek real:** síntesis de modelos, refinación que añade `shelfCode` preservando UUID e ISBN único, pipeline hasta STORIES que termina PAUSED, generación de 20 archivos con Gradle y paquetes hexagonales, y llamada HTTP guiada con coste persistido. Se usó únicamente el proveedor autorizado y requisitos ficticios de biblioteca. No se sustituyeron respuestas de modelos.
- Los archivos Java de esa generación no presentan violaciones de dirección de dependencias en la validación del perfil.
- La verificación de esa generación terminó **BLOCKED**, con cero pruebas aprobadas y fallback marcado, porque Docker no está accesible. Esto comprueba el comportamiento de bloqueo, no la corrección funcional de los archivos Java.
- No se encontraron claves API reales en los nuevos artefactos de prueba.

## Límites y puesta en marcha

**No se ejecutó una compilación Java ni un despliegue saludable.** El daemon Docker devuelve un error de conexión a `dockerDesktopLinuxEngine`; no se encontró Docker Desktop en su ruta de instalación habitual. Por tanto, no se puede afirmar que el código Java generado compile ni que el despliegue funcione completamente.

La sesión del navegador de prueba y sus servicios aislados se cerraron. Los servicios preexistentes en 8000 y 3000 se conservaron; requieren reiniciar para cargar los cambios.

Configura `STUDIO_USER_EMAIL` y `STUDIO_ACCESS_TOKEN` antes de iniciar el backend. La clave del estudio es distinta de la clave de DeepSeek. Las instrucciones están en [acceso-local.md](../../docs/acceso-local.md).

Evidencias reproducibles: `regressions.json`, `browser.json`, `browser-authenticated.png`, `deepseek.json`, `hexagonal.json` y `guided-api.json`, con sus scripts en esta carpeta. Los directorios de ejecución están excluidos de Git.
