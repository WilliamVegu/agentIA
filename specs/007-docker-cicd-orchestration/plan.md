# Plan técnico vigente: despliegue local opcional

**Actualizado:** 05/10/2026. **Estado:** implementación iniciada, aceptación integral pendiente.

El plan detallado y su seguimiento están en `docs/PLAN_IMPLEMENTACION_DESPLIEGUE_LOCAL.md`; el diagnóstico y las evidencias, en `docs/ESTADO_DESPLIEGUE_LOCAL_DOCKER.md`. Este documento sustituye el plan de septiembre basado en Streamlit, montajes SQL y fallback implícito.

## Alcance y arquitectura

- Plataforma nativa FastAPI/Python y React/Vite/Node, escuchando en localhost. No se conteneriza AgentIA.
- Microservicios Java 21/Spring Boot 3, Maven o Gradle, PostgreSQL/MySQL/H2; Windows como host principal.
- Preferencia persistida `SOURCE_ONLY` (default) o `DOCKER`. La configuración global solo permite/prohíbe ejecución Docker.
- Política central de elección y evidencia para grafo, flujo guiado, Auto-Pilot, reparación, overview, DevOps y exportación.
- Auditoría estática y exportación de fuentes completables sin virtualización, Docker ni herramientas Java del host.
- Preparación online explícita separada de verificación/build offline. Dependencias nuevas requieren repetir preparación.
- Dockerfile con builder preparado, caché privada de escritura, JAR ejecutable y runtime no root. Compose construye primero y arranca después sin pulls implícitos; la aplicación se publica exclusivamente en localhost.
- Operaciones por sesión, identidad por etiquetas, puerto efectivo, estado durable y reconciliación de salud. AutoDeploy espera el estado final.
- Scripts PowerShell independientes de AgentIA para preparar, iniciar, detener y limpiar explícitamente datos.
- GitLab remoto aplazado. Corrección y validación local de CI/CD/Kubernetes siguen en el alcance, pendientes.

## Dependencias de implementación

1. P0: contratos, especificación, constitución y fixtures.
2. P1: elección por sesión y flujo completo en laboratorio sin Docker; prioridad máxima.
3. P2: diagnóstico, preparación, catálogo/kit offline con integridad y dependencias de AgentIA.
4. P3: configuración de build/BD, snapshot, Docker/Compose, DDL y semillas coherentes.
5. P4: operaciones, cancelación, límites, puertos, identidad, salud, persistencia y AutoDeploy.
6. P5: UI, estado, logs durables y reconexión.
7. P6: entrega y scripts de un comando.
8. P7: corrección de CI/CD y Kubernetes; validación estática local y ejecución real separadas.
9. P8: matriz de seis combinaciones, fallos, concurrencia, offline con red externa bloqueada y documentación.

## Reglas de aceptación

La generación de archivos y pruebas con dependencias simuladas no acreditan un despliegue real. `COMPLETED` termina el alcance elegido; `VERIFIED` requiere evidencia real vigente y `HEALTHY` requiere identidad y salud actual. Si Docker solicitado no está disponible, esperar Reintentar o Continuar sin Docker. Conservar fallos anteriores al cambiar a fuentes.

No migrar ni borrar proyectos históricos. Preservar datos al detener/reconstruir; borrado solo explícito. Sin Docker, herramientas externas ausentes se reportan como no ejecutadas y no bloquean la entrega por ausencia de infraestructura. El inicio no cambia permisos, políticas de Windows ni virtualización.

Las 54 tareas conservan sus identificadores en el plan detallado. Las tareas parciales permanecen abiertas y toda evidencia debe indicar si se obtuvo leyendo código, ejecutando generación, simulando dependencias o usando contenedores reales.

## Referencias actuales

Especificación, quickstart y contratos se alinearon con las rutas reales el 5 de octubre. La API se exporta con backend/scripts/export_devops_contract.py y se comprueba con --check. El plan detallado conserva tareas parciales abiertas; este contrato no acredita snapshot, cancelación BuildKit, CI/CD/Kubernetes ni aceptación offline integral.
