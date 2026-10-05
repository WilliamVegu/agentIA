# Guía Windows: fuentes y despliegue local

**Revisión:** 5 de octubre de 2026. Despliegues reales y transferencia de imágenes comprobados en el motor existente; aceptación integral en equipo/motor limpio y con red externa bloqueada pendiente. Consulte [estado](../../docs/ESTADO_DESPLIEGUE_LOCAL_DOCKER.md) y [plan](../../docs/PLAN_IMPLEMENTACION_DESPLIEGUE_LOCAL.md).

## AgentIA nativo

Prepare inicialmente Python con backend/requirements.txt y Node/npm con frontend/package-lock.json. Para preparación e instalación nativa offline consulte [guía del kit Windows](../../docs/GUIA_KIT_NATIVO_OFFLINE_WINDOWS.md). El kit nativo es independiente de Docker; T54 continúa parcial y no acredita aún todo el recorrido en otro laboratorio limpio.

Desde la raíz, con el entorno Python activo:

```powershell
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

En otra terminal:

```powershell
Set-Location frontend
npm.cmd run dev
```

Abra http://localhost:3000 y use la autenticación local configurada. Python/Node son necesarios para AgentIA; Java/Maven/Gradle del host no son necesarios para entregar fuentes ni para los scripts Docker. La instancia manual usada anteriormente está detenida.

## Laboratorio sin virtualización

1. Elija **Sin Docker** al crear la sesión: es la opción predeterminada persistida.
2. Complete flujo guiado o AutoPilot. Se generan código, pruebas como archivos y manifiestos; la auditoría estática sigue vigente.
3. Compruebe finalización del alcance de fuentes y ejecución omitida por elección. COMPLETED no significa VERIFIED ni HEALTHY.
4. Exporte el ZIP permitido por auditoría. No incluye secretos .env, cachés privados ni JAR inexistente.

DOCKER_ENABLED limita administrativamente el uso del motor; no obliga a una sesión en fuentes a invocarlo. Las herramientas ausentes se presentan como no ejecutadas y no se instalan automáticamente.

## Docker solicitado pero no disponible

Use **Reintentar** tras corregir/preparar el entorno, o **Continuar sin Docker** para cambiar explícitamente el alcance. Un fallo real anterior de compilación/pruebas permanece registrado. No se cambian políticas de Windows ni virtualización. Si las políticas prohíben ejecutar scripts, use fuentes o un equipo autorizado.

## Microservicio exportado

Requiere Docker Linux operativo únicamente para ejecución con Docker. Use PowerShell en la carpeta del proyecto exportado:

```powershell
# PostgreSQL/MySQL: crear .env y establecer contraseñas locales antes de preparar.
Copy-Item .env.example .env
# Preparación inicial con conexión, explícita:
.\prepare-local.ps1
# Compilar/pruebas offline y arrancar con el puerto guardado:
.\start-local.ps1
# Puerto explícito alternativo:
.\start-local.ps1 -Port 8090
# Solo fuentes, sin consultar Docker:
.\start-local.ps1 -SourcesOnly
```

Para H2 no se necesita un contenedor de BD externo; no copie .env.example si el proyecto no lo incluye. Tras crear .env, edite sus valores; no distribuya credenciales. Ejecute una sola variante de arranque a la vez.

Sin -Port, start toma hostPort de LOCAL_DELIVERY.json. Si está ocupado elige otro y muestra localhost efectivo. Construye y ejecuta pruebas Maven/Gradle con imágenes/dependencias preparadas, y después arranca sin build/pull implícitos. No publica la BD externa al host. Ausencia de imágenes/dependencias provoca error explicativo; cambios de dependencias requieren regenerar activos y preparar otra vez.

```powershell
.\stop-local.ps1
# Reutilizar imagen existente: sin nuevas pruebas/build; conserva datos.
.\start-local.ps1 -ReuseImage
# Eliminación explícita de recursos/datos propios:
.\cleanup-local.ps1 -DeleteData
```

Stop y reconstrucción conservan volúmenes. Cleanup no es limpieza global. SQL diseñado y semillas usan migraciones Liquibase versionadas en el proyecto; no se inicializan mediante antiguos bind mounts. La aceptación de SQL complejo continúa pendiente.

## Kit de imágenes

Tras preparación, exporte a una carpeta nueva fuera de las fuentes y transfiera ese kit:

```powershell
.\export-offline-kit.ps1 -Path C:\kits\proyecto
.\import-offline-kit.ps1 -Path C:\kits\proyecto
```

Manifiesto/fingerprint/SHA256 y controles de identidad/plataforma verifican integridad. Transferencia real comprobada en el mismo motor con imágenes existentes (sección 29 del estado); no acredita motor limpio ni bloqueo externo de red. No incluye Python/Node, scanners ni Kubernetes. Consulte la guía nativa para AgentIA y conserve ambos kits separados.

## Interpretar resultados

- PASSED: suite real no vacía, sin fallos y fingerprint vigente.
- SKIPPED_BY_CHOICE: ejecución omitida por elegir fuentes.
- ENVIRONMENT_UNAVAILABLE/INTERRUPTED: entorno ausente o ejecución interrumpida; no aprobación.
- FAILED/OUTDATED: fallo real o evidencia que ya no corresponde al proyecto.
- HEALTHY: runtime propio identificado y Actuator actual UP; no acredita suite ni CI.

Las verificaciones DOCKER nuevas conservan un snapshot sellado con informes y JAR; deploy utiliza ese JAR sin recompilar. Si una sesión anterior carece de sourceSnapshotId, ejecute nuevamente Verificar antes de desplegar. Cambios de fuentes o corrupción del sello requieren nueva verificación. La exportación aprobada contiene las fuentes capturadas; credenciales e imagen ejecutable siguen fuera de ese ZIP. Elegir SOURCE_ONLY continúa sin Docker ni obligación de crear ese snapshot.

Generar manifiestos CI/CD/Kubernetes no demuestra ejecutarlos: su corrección y validación local siguen pendientes. GitLab remoto permanece aplazado. Contratos y recuperación están en [contracts/README.md](contracts/README.md); la API OpenAPI se deriva del código y puede verificarse con el exportador allí indicado.
