# Acceso al estudio local

## Acceso automático del MVP

Abre `http://localhost:3000` o `http://127.0.0.1:3000`: aparecerá la pantalla de login. Pulsa **Entrar al MVP** para abrir el estudio como **MVP local**, sin correo ni contraseña. El botón está habilitado por defecto para conexiones locales. Reinicia el backend después de actualizar el código.

El backend permite este acceso cuando la conexión y el destino son locales, y los encabezados Origin/Referer, si están presentes, también corresponden a localhost. Las conexiones con encabezados de proxy Forwarded/X-Forwarded-For requieren autenticación normal. Este modo comparte los proyectos de la instancia entre sus usuarios locales. La interfaz muestra «Acceso sin contraseña · MVP local». Cerrar sesión vuelve al login. La sesión se conserva al recargar, dura ocho horas y se revoca al reiniciar el backend.

Puedes declarar explícitamente el modo en tu entorno o en `backend/.env`:

```dotenv
STUDIO_AUTO_LOGIN=true
```

La clave de DeepSeek se introduce por separado en la configuración de IA; el acceso automático no configura ni simula el proveedor.

## Acceso con contraseña

Para exigir login, configura en tu entorno o en `backend/.env` y reinicia el backend:

```dotenv
STUDIO_AUTO_LOGIN=false
STUDIO_USER_EMAIL=operador@ejemplo.com
STUDIO_ACCESS_TOKEN=una-clave-privada-de-al-menos-16-caracteres
```

Usa ese correo y esa clave en el formulario de acceso. `STUDIO_ACCESS_TOKEN` es la clave del estudio; la clave de DeepSeek se introduce por separado en la configuración de IA. No subas el archivo `.env` a Git.

En este modo, la sesión dura ocho horas, usa una cookie HttpOnly y se revoca al cerrar sesión. Reiniciar el backend también revoca sus sesiones. La API devuelve 401 sin autenticación y el login devuelve 503 si no se ha configurado el operador. El correo enviado como encabezado y los datos de `localStorage` no son credenciales.

Esta configuración corresponde a un estudio de un solo operador, que administra todos los proyectos de esta instancia. No proporciona aislamiento entre múltiples usuarios ni autenticación institucional de TCS.

## Verificación y exportación

Una generación parcial queda pausada. La ausencia de Docker, una suite vacía, un fallback o una compilación sin evidencia de pruebas no permiten declarar VERIFIED ni exportar/publicar. Las métricas antiguas sin huella de los archivos requieren volver a ejecutar la verificación. Editar código o configuración de compilación invalida la evidencia anterior.

Para Gradle, configura `GRADLE_CACHE_DIR` si su caché está en otra carpeta y `GRADLE_DOCKER_IMAGE` si necesitas otra imagen con Java 21 y Gradle. La ejecución del sandbox usa `--network none` y `--offline`; la imagen y las dependencias deben estar disponibles previamente. Los reportes XML de la ejecución actual suministran el conteo de pruebas.
