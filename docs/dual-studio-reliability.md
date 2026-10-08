# Fiabilidad de Spring Boot y Quarkus

Los estudios mantienen backend, frontend, SQLite, workspace, costes y procesos independientes. El lanzador de `integration/README.md` conserva esa separación. No importar los dos paquetes Python `app` dentro del mismo proceso.

## Draft y operaciones

La revisión estructurada guardada en SQLite es la entrada de generación. Guardar no aprueba: se requiere aprobar la revisión exacta. Las escrituras utilizan versión esperada; un conflicto responde 409. Cambiar el draft invalida los artefactos derivados. La regeneración de un proyecto existente necesita una acción explícita y conserva una copia de las fuentes anteriores.

Cada sesión admite una sola operación escritora. Target limita las fases ejecutadas; pausa se confirma en un checkpoint. Cancelación no equivale a completar. Tras reiniciar el backend, una operación inconclusa queda INTERRUPTED: no se repiten automáticamente generación, Git ni Docker. Los eventos se guardan antes de notificarse y admiten replay o resync.

## Modos y evidencia

SOURCE_ONLY permite generar, revisar y exportar fuentes auditadas; informa UNVERIFIED cuando no se ejecutaron pruebas. Conserva los fallos históricos. DOCKER exige una suite real no vacía, todos los tests aprobados, salida correcta, reportes y huella vigentes. Un fallback, interrupción, informe ausente o fuente modificada impide certificar PASSED. Compilar no acredita ejecutar BDD ni validar un proveedor IA.

El modo de generación y el de ejecución son independientes. Generar con IA requiere una credencial y un cliente válido. La ausencia o fallo de configuración no selecciona plantillas silenciosamente: devuelve error. La generación offline se elige explícitamente como diagnóstico; las fixtures de prueba también declaran esa elección y nunca acreditan generación por un proveedor real.

Reparación manual exige código y acepta `guidanceHint` (`promptHint` es alias compatible). Solo un hint devuelve 422. Escribir código invalida evidencia: no declara diagnósticos resueltos sin nueva ejecución. La reparación automática admite tres intentos persistidos por ciclo; reiniciar no repone el contador y un fallo de infraestructura no consume un intento.

## Runtime y datos

La identidad runtime incluye sesión, estudio, propietario, imagen y bindings inspeccionados. HEALTHY exige un recurso propio vigente y readiness nativo: `/actuator/health` en Spring, `/q/health/ready` en Quarkus. Un servicio ajeno que responde en el puerto no prueba salud.

Stop y restart conservan volúmenes. Cleanup requiere preview y confirmación sobre identidades vigentes; eliminar datos es explícito. Recursos sin etiquetas de propietario y estudio no se adoptan automáticamente. Los scripts PowerShell exportados aplican la misma frontera. No usar prune ni limpieza global para recuperar una sesión.

## Entrega, calidad y validación

Publicación Git conserva historia y rechaza divergencia; no hace force push. Los tokens no se incorporan a URL, argumentos o configuración persistida. El ZIP identifica el tipo de entrega y su evidencia. Una auditoría vacía informa NOT_RUN y score null; métricas medidas en cero se conservan.

El análisis de fuentes y la base de vulnerabilidades incluida tienen alcance limitado. El CI generado ejecuta controles y pruebas; su mera presencia no acredita una ejecución remota. Consulte los resultados actuales en `integration/validation/reliability/RESULTADOS.md` y los comandos en `specs/017-dual-studio-reliability/quickstart.md`. Allí se distinguen pruebas locales, Docker real y capacidades pendientes. Las pruebas de fiabilidad no necesitan credenciales IA.
