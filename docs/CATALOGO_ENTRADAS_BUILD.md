# Entradas de build y preparación local

La identidad del builder preparado, los manifiestos del kit, la entrega independiente y la vigencia del snapshot usan un selector común de configuración de build. No se consideran suficientes únicamente `pom.xml` o `build.gradle`.

Se incluyen:

- POM, build/settings Gradle y `gradle.properties` de módulos locales.
- Scripts `.gradle`/`.gradle.kts` y archivos `.lockfile`.
- Configuración y wrapper bajo `.mvn`, catálogos/wrapper bajo `gradle` y archivos de `buildSrc`.
- Entradas `mvnw`, `mvnw.cmd`, `gradlew` y `gradlew.bat`.

Se excluyen outputs y caches: `.git`, `target`, `build`, `.gradle`, `.m2`, `node_modules`, `.agentia-runtime`, `.run` y `.venv`. Entradas enlazadas o fuera del proyecto se rechazan. El catálogo no interpreta todas las dependencias posibles de un script ni descubre builds/repositorios externos al workspace.

Añadir, modificar o retirar estas entradas cambia la identidad de preparación. Debe regenerar activos y realizar la preparación explícita o importar un kit compatible. El arranque y la importación rechazan el conjunto anterior antes de construir/cargar imágenes. Nunca habilitan red ni preparan automáticamente para resolver el conflicto.

La preparación de AgentIA captura el catálogo al solicitar la operación y comprueba vigencia entre comandos y antes de declarar éxito. `prepare-local.ps1` comprueba los hashes/conjunto antes de Docker, entre builds/pull y al terminar. Una modificación neta observada aborta los pasos siguientes. El control no congela el filesystem ni garantiza detectar modificaciones transitorias restauradas dentro de un build de preparación. La verificación y el despliegue posteriores utilizan su snapshot aislado y sellado.

`prepare-local.ps1 -SourcesOnly` y `start-local.ps1 -SourcesOnly` retornan antes de leer metadata o invocar Docker; permiten la entrega en laboratorio sin virtualización. Preparar con red requiere una acción explícita. Que un builder esté preparado no acredita una suite offline aprobada.

Los builders de proyectos que solo contienen los manifiestos anteriores mantienen su identidad. Proyectos con entradas adicionales requieren nueva preparación para impedir reutilizar una imagen que no representaba esas entradas. No se migran proyectos históricos automáticamente.

Pruebas cubren identidad, catálogo Python/PowerShell coincidente, rechazo previo a Docker, cambios durante preparación, importación del kit y arranque real Maven/H2 con imágenes existentes. Todavía faltan un catálogo completo de paquetes/versiones soportados, scanners/herramientas Kubernetes, compatibilidad de versiones Gradle y aceptación del kit en entorno limpio con internet externo bloqueado.
