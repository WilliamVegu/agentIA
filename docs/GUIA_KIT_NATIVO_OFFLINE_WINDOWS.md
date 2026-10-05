# Preparación nativa offline de AgentIA en Windows

Este kit prepara AgentIA (Python/FastAPI y Node/React) independientemente de Docker. En el laboratorio permite instalar las dependencias y completar el flujo de fuentes sin Java, Maven/Gradle ni virtualización. La IA sigue requiriendo conexión y credenciales cuando se usa un proveedor remoto.

## Preparación inicial con conexión

Use un entorno Python donde `backend/requirements.txt` ya esté instalado y Node/npm disponibles. La preparación verifica esos requisitos y fija las versiones Python realmente instaladas; npm utiliza `frontend/package-lock.json`. No cambia las instalaciones globales.

```powershell
.venv\Scripts\python.exe scripts/native_offline_kit.py prepare --kit C:\kits\agentia-windows
```

La carpeta de kit debe ser nueva. Se copian los runtimes Python/Node, wheels y caché npm; el manifiesto registra plataforma, arquitectura, versiones, hashes de los archivos de dependencias, tamaños y SHA256 de los archivos transferibles. La preparación no se anuncia como una prueba offline aprobada.

Puede reutilizar descargas de un kit íntegro con exactamente el mismo lock Python y los mismos manifiestos del proyecto:

```powershell
.venv\Scripts\python.exe scripts/native_offline_kit.py prepare --kit C:\kits\agentia-nuevo --reuse-downloads C:\kits\agentia-windows
```

No reutilice automáticamente dependencias nuevas propuestas por IA: cambios en requirements/package-lock requieren una preparación nueva. Use un kit de procedencia confiable; SHA256 detecta corrupción, no firma al autor. No se incluyen claves API ni `.env` del proyecto. Runtimes y dependencias conservan los archivos de licencia presentes en sus distribuciones; esta utilidad no instala componentes del sistema.

## Transferencia e instalación sin registros de paquetes

Transfiera el proyecto de fuentes y el kit. La subcarpeta `preparation` contiene el calentamiento y logs; no es necesaria en el destino y puede omitirse al transferir. El resto del catálogo y `manifest.json` deben conservarse íntegros.

No necesita Python/Node instalados globalmente en el destino: puede ejecutar el helper con el Python del propio kit. El directorio de instalación debe ser nuevo y escribible por el usuario.

```powershell
& 'D:\kit\python\python.exe' -B 'D:\kit\native_offline_kit.py' install --project 'D:\agentIA' --kit 'D:\kit' --destination 'D:\agentia-local'
```

Antes de crear la instalación se validan todos los hashes, el catálogo, la plataforma/arquitectura y los manifiestos de dependencias del proyecto. Python instala con `--no-index` y wheels locales. npm instala con `--offline`, sin auditorías/fund ni scripts de paquetes, desde una copia privada de su caché. Se compila TypeScript y el frontend mediante el Node incluido. Los temporales y configuraciones vacías de npm quedan dentro de la instalación, sin leer las configuraciones personales ni alterar permisos.

`installation-result.json` solo se escribe como PASS al finalizar todos esos pasos. Un error produce salida distinta de cero y logs por paso; no se cambia a modo online automáticamente. No se sobrescribe un directorio existente ni se elimina su contenido para reintentar: use una carpeta nueva.

## Arranque local

Abra dos terminales y use los scripts generados en la instalación:

```powershell
# Primera terminal
D:\agentia-local\start-backend.ps1 -Project D:\agentIA
# Segunda terminal
D:\agentia-local\start-frontend.ps1
```

Backend: http://localhost:8000. Frontend: http://localhost:3000. Si esos puertos están ocupados, el arranque informa el error; no detiene procesos ajenos. No cambie políticas de PowerShell automáticamente: puede ejecutar directamente los comandos Python/Node indicados en los scripts si su entorno permite ejecutarlos. Detenga los servicios con Ctrl+C en sus terminales.

Seleccione **Sin Docker / fuentes** al crear el microservicio. La instalación del kit no cambia esa preferencia ni inicia Docker. La generación de IA remota, Git remoto, auditorías/scanners externos y ejecución Docker/Kubernetes no están preparados por este kit.

## Verificación reproducible

Después de instalar:

```powershell
D:\agentia-local\venv\Scripts\python.exe scripts/verify_native_install.py --project D:\agentIA --installation D:\agentia-local
```

La prueba utiliza PATH vacío, puertos localhost temporales y claves IA vacías. Comprueba backend, frontend HTTP y proxy de salud; detiene únicamente sus procesos y conserva logs/resultado. No modifica el firewall ni acredita una desconexión global de Windows. Tampoco sustituye una prueba de navegador completa ni una instalación en otro equipo/imagen Windows limpia.

El kit es para la plataforma y arquitectura registradas. La disponibilidad de librerías de sistema requeridas por los runtimes sigue dependiendo del equipo. Ante un bloqueo administrativo no se sortea la restricción: se documenta el componente no disponible.

## Aceptación del flujo sin Docker

Con una instalación nativa completa puede comprobar el backend actual y su flujo de fuentes:

```powershell
D:\agentia-local\venv\Scripts\python.exe scripts/verify_native_source_flow.py --project D:\agentIA --installation D:\agentia-local --destination D:\pruebas\fuentes-1
# Segunda carpeta nueva, también con prohibición administrativa global de Docker:
D:\agentia-local\venv\Scripts\python.exe scripts/verify_native_source_flow.py --project D:\agentIA --installation D:\agentia-local --destination D:\pruebas\fuentes-2 --docker-disabled
```

La aceptación crea DB/workspaces independientes y usa autenticación local real, generación determinista sin IA, pruebas generadas, verificación explícitamente omitida, manifiestos, auditoría/ZIP de fuentes y recuperación tras reiniciar el backend. PATH está vacío. Un guard confirmado en ambos arranques registra/rechaza descubrimiento Docker, CLI/SDK y conexiones externas del proceso. Cualquier intento invalida la aceptación; el guard no simula resultados de las rutas ni de la auditoría.

`result.json`, logs y `sources.zip` quedan en el destino nuevo. La prueba retira únicamente sus árboles de procesos; no requiere que AgentIA permanezca abierta. En Windows comprueba la identidad del hijo del launcher Python y usa parada de su árbol propio. No desinstala Docker ni modifica firewall/ACL/virtualización. Esta aceptación por API no sustituye el recorrido de navegador, una IA remota real ni las restricciones adicionales de otro equipo del laboratorio.
