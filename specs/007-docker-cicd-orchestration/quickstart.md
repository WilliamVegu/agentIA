# Guía Windows: generación y despliegue local

**Actualizada:** 04/10/2026. **Estado:** implementación en curso; despliegue Docker real y operación offline completa pendientes de demostración.

Esta guía sustituye la anterior de Streamlit. La plataforma usa FastAPI y React/Vite. Docker solo se solicita para los microservicios de las sesiones que lo elijan.

## Arranque de AgentIA

La preparación inicial puede usar internet. Instale las dependencias de `backend/requirements.txt` en un entorno Python local y las del frontend con `npm ci`. La distribución offline reproducible de Python/Node y paquetes sigue pendiente (T54).

Desde la raíz, con el entorno Python activo:

```powershell
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

En otra terminal:

```powershell
Set-Location frontend
npm.cmd run dev
```

Abra `http://localhost:3000`. La configuración nueva escucha en localhost. AgentIA sigue necesitando Python/Node; no se requiere Java, Maven o Gradle del host para generar fuentes ni para los scripts Docker.

## Laboratorio sin virtualización

1. Elija **Sin Docker** en creación rápida o ingesta. Es la opción predeterminada y se guarda por sesión.
2. Complete el flujo guiado o Auto-Pilot. Se generan fuentes, pruebas como archivos y manifiestos; se mantiene la auditoría estática.
3. Compruebe que la sesión termina en el alcance de fuentes, con ejecución omitida por elección, sin afirmar `VERIFIED`, pruebas aprobadas ni despliegue saludable.
4. Exporte el ZIP permitido por la auditoría. No incluye `.env`, registros privados del despliegue, cachés ni un JAR inexistente.

`DOCKER_ENABLED` es un límite administrativo del servidor. Una sesión en fuentes no invoca Docker aunque ese límite permita usarlo en otras sesiones.

## Si se eligió Docker y no está disponible

La sesión queda pendiente y ofrece **Reintentar** o **Continuar sin Docker**. Reintentar verifica las fuentes actuales. Continuar cambia explícitamente el alcance y permite preparar la entrega de fuentes auditadas. Un fallo real anterior de compilación/pruebas conserva su evidencia; cambiar el modo no lo convierte en aprobación ni en omisión.

La sección DevOps permite solicitar preparación inicial online y verificar después con Docker. La preparación no acredita una ejecución offline. No se modifican virtualización, WSL, permisos administrativos ni políticas de ejecución de Windows.

## Proyecto exportado con Docker

Requiere Docker con motor Linux operativo. Estas instrucciones describen los scripts generados; su ejecución real todavía no se ha validado en este equipo.

1. Para PostgreSQL/MySQL copie `.env.example` a `.env` y defina contraseñas locales. H2 no necesita un contenedor de base de datos externo.
2. Con conexión, ejecute `./prepare-local.ps1` para preparar builder, runtime y base de datos de este proyecto.
3. Para la construcción y arranque posterior ejecute `./start-local.ps1 -Port 8080`. La construcción compila y ejecuta pruebas con Maven/Gradle offline; Compose arranca sin build ni pull implícitos y espera salud.
4. Si el puerto está ocupado, el script selecciona otro dentro del rango y lo informa. La aplicación se publica exclusivamente en `127.0.0.1`; la base de datos no publica puertos al host.
5. `./stop-local.ps1` conserva datos. `./cleanup-local.ps1 -DeleteData` los elimina mediante una acción explícita.

Si Windows prohíbe ejecutar estos scripts, respete la política del laboratorio: use el flujo de fuentes o un equipo autorizado. No se cambia la política de ejecución automáticamente.

Las dependencias nuevas requieren preparación nueva. Los scripts `export-offline-kit.ps1 -Path C:\kits\proyecto` e `import-offline-kit.ps1 -Path C:\kits\proyecto` transfieren imágenes preparadas con manifiesto, fingerprint, SHA256 y controles de identidad/arquitectura. Guarde el kit fuera de las fuentes y use una carpeta nueva al exportar. Su ejecución PowerShell está comprobada con Docker simulado; la transferencia real sigue pendiente. Este kit no incluye Python/Node, scanners ni Kubernetes. H2 usa un volumen de archivos en la plantilla actual. La inicialización de DDL y semillas está pendiente: Hibernate `update` no demuestra que se haya aplicado el SQL diseñado. CI/CD y Kubernetes continúan pendientes de corrección y validación local; no publique sus plantillas como si estuvieran verificadas.

## Verificación y evidencia

- `PASSED`: pruebas realmente ejecutadas, suite no vacía, sin fallos y fingerprint vigente.
- `SKIPPED_BY_CHOICE`: compilación/pruebas omitidas porque se eligieron fuentes.
- `ENVIRONMENT_UNAVAILABLE`: ejecución solicitada que no pudo realizarse; requiere decisión.
- `FAILED` / `OUTDATED`: fallo real / evidencia que ya no corresponde al workspace.
- `HEALTHY`: contenedor de la sesión identificado por etiquetas, puerto localhost inspeccionado y Actuator actual `UP`. HTTP 200 con JSON inválido no es una aprobación.

La matriz de aceptación es Maven/Gradle × PostgreSQL/MySQL/H2. Debe probar build, pruebas, salud, CRUD y persistencia con Docker real; las pruebas de generación sin Docker no sustituyen esa evidencia. Los resultados y pendientes se mantienen en `docs/ESTADO_DESPLIEGUE_LOCAL_DOCKER.md` y `docs/PLAN_IMPLEMENTACION_DESPLIEGUE_LOCAL.md`.
