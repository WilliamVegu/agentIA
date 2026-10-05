# Gradle y cachés de ejecución local

El perfil preparado usa Gradle **8.10.2** con Java 21. Si no hay wrapper declarado, se usa esa versión instalada. Si el proyecto incluye `gradle-wrapper.properties`, debe declarar una única distribución 8.10.2 (bin o all). Una versión distinta, valor ilegible o clave duplicada se rechaza antes de consultar Docker en el sandbox y los scripts de preparación/arranque.

El builder comprueba también `gradle --version` antes de ejecutar pruebas, para impedir que una etiqueta local que apunte a otra versión certifique el perfil. El arranque no ejecuta `gradlew` ni descarga distribuciones. Las dependencias se resuelven mediante preparación explícita; ejecución posterior usa `--offline` y `--network none`.

Ante incompatibilidad, mantenga su versión si la necesita y continúe entregando fuentes, o ajuste explícitamente el proyecto al perfil soportado, regenere activos y prepare las dependencias. No se cambia el wrapper de forma automática. `-SourcesOnly` permite generar/exportar sin comprobar esa compatibilidad ni invocar Docker. Otros perfiles de versión requieren una implementación y preparación nuevas.

La imagen preparada contiene `/opt/agentia-cache`. Cada sandbox/build copia esa base a su filesystem temporal: `/tmp/m2` para Maven, `/tmp/gradle-home` para Gradle. Maven apunta a su repositorio privado y Gradle a su `GRADLE_USER_HOME` privado. No se comparte un directorio host modificable entre las ejecuciones nuevas preparadas. Las capas base Docker permanecen separadas de las escrituras de cada contenedor/build.

Aceptación real comprobó dos contenedores concurrentes por herramienta con caché privada, marcador independiente, JAR disponibles, versión real correcta e ID de imagen base inalterado. Fueron retirados únicamente los contenedores etiquetados de prueba. Esa prueba de caché no equivale a dos builds completos simultáneos ni certifica locks entre procesos de AgentIA, cancelación BuildKit o recuperación del daemon; esas pruebas siguen en T25/T27/T52.

Las etiquetas locales de imágenes pueden ser reemplazadas por un operador. El kit registra y valida identidades/digests; este control de versión no autentica por sí mismo una imagen modificada. Para las verificaciones nuevas, fuentes e informes/JAR tienen su snapshot sellado y el despliegue comprueba la identidad de su imagen de aplicación.
