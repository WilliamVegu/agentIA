"""Windows/localhost assets. Online preparation is separate from offline operation."""
import hashlib
import re
from pathlib import Path
import yaml

MAVEN_IMAGE = "maven:3.9.9-eclipse-temurin-21-alpine"
GRADLE_IMAGE = "gradle:8.10.2-jdk21-alpine"
RUNTIME_IMAGE = "eclipse-temurin:21.0.5_11-jre-alpine"
DATABASE_IMAGES = {"POSTGRESQL": "postgres:16.4-alpine", "MYSQL": "mysql:8.0.40", "H2": None}


def project_identity(ws):
    root = Path(ws)
    digest = hashlib.sha256()
    from app.services.dependency_inputs import dependency_contents
    for relative, content in dependency_contents(root).items():
        digest.update(relative.encode())
        digest.update(content)
    digest.update((MAVEN_IMAGE + GRADLE_IMAGE + RUNTIME_IMAGE).encode())
    return digest.hexdigest()[:24]


def builder_image(ws):
    return "agentia-builder:" + project_identity(ws)


def executable_jar_selection(build_tool):
    pattern = '*/build/libs/*.jar' if build_tool == 'gradle' else '*/target/*.jar'
    return f'''find . -type f -path '{pattern}' ! -name '*-plain.jar' ! -name 'original-*' ! -name '*sources.jar' ! -name '*javadoc.jar' | while IFS= read -r jar; do
  if unzip -tqq "$jar" >/dev/null 2>&1 && unzip -l "$jar" | grep -q 'BOOT-INF/' && unzip -p "$jar" META-INF/MANIFEST.MF | tr -d '\\r' | grep -Eq '^Main-Class: org\\.springframework\\.boot\\.loader\\.(launch\\.)?(JarLauncher|PropertiesLauncher)$'; then
    printf '%s\\n' "$jar";
  fi;
done > /tmp/agentia-executable-jars;
count=$(wc -l < /tmp/agentia-executable-jars);
if [ "$count" -ne 1 ]; then echo "Expected exactly one executable Spring Boot JAR; found $count" >&2; exit 1; fi;
IFS= read -r jar < /tmp/agentia-executable-jars;
cp "$jar" /application.jar'''


def dockerfile(build_tool, prepared_image="agentia-builder:prepare-first", build_directory='.'):
    if build_directory not in {'.', 'bootstrap'}:
        raise ValueError('Directorio de build no admitido')
    if build_tool == "gradle":
        build = "cp -R /opt/agentia-cache/. /tmp/gradle-home/ && GRADLE_USER_HOME=/tmp/gradle-home gradle --no-daemon --offline test bootJar"
        mkdir = "mkdir -p /tmp/gradle-home"
    else:
        build = "cp -R /opt/agentia-cache/. /tmp/m2/ && mvn -B -o -Dmaven.repo.local=/tmp/m2 verify"
        mkdir = "mkdir -p /tmp/m2"
    selection = executable_jar_selection(build_tool).replace('\n', ' \\\n    ')
    working = '/workspace' + ('/bootstrap' if build_directory == 'bootstrap' else '')
    return f'''FROM {prepared_image} AS build
WORKDIR /workspace
COPY . .
WORKDIR {working}
RUN --network=none {mkdir} && {build}
RUN --network=none {selection}

FROM agentia-runtime:21-v1
WORKDIR /app
COPY --from=build --chown=10001:10001 /application.jar /app/application.jar
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75.0" SERVER_PORT=8080
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=60s --retries=5 CMD wget -q -O - http://127.0.0.1:8080/actuator/health | grep -q '"status":"UP"' || exit 1
ENTRYPOINT ["java", "-jar", "/app/application.jar"]
'''


def compose(service_name, db_engine, host_port=8080):
    if not re.fullmatch(r"[a-z][a-z0-9-]*", service_name):
        raise ValueError("Nombre de servicio inválido para despliegue: " + service_name)
    database = db_engine.upper()
    if database not in DATABASE_IMAGES:
        raise ValueError("Base de datos no admitida")
    env = {"SERVER_PORT": "8080", "MANAGEMENT_ENDPOINTS_WEB_EXPOSURE_INCLUDE": "health,info",
           "MANAGEMENT_ENDPOINT_HEALTH_PROBES_ENABLED": "true", "SPRING_JPA_HIBERNATE_DDL_AUTO": "validate",
           "SPRING_LIQUIBASE_ENABLED": "true",
           "SPRING_SQL_INIT_MODE": "never"}
    # Compose supplies this variable from its effective project name (-p wins).
    # Two sessions with the same service name must never overwrite each other's image.
    app = {"image": f"${{COMPOSE_PROJECT_NAME}}-{service_name}:local", "pull_policy": "never", "build": {"context": ".", "network": "none"},
           "ports": [f"127.0.0.1:${{HOST_PORT:-{host_port}}}:8080"], "environment": env,
           "labels": {"io.agentia.role": "application"}, "restart": "unless-stopped"}
    result = {"services": {service_name: app}, "volumes": {"appdata": {}}}
    app["volumes"] = ["appdata:/app/data"]
    if database == "H2":
        env.update({"SPRING_DATASOURCE_URL": "jdbc:h2:file:/app/data/service;DB_CLOSE_ON_EXIT=FALSE", "SPRING_DATASOURCE_DRIVER_CLASS_NAME": "org.h2.Driver", "SPRING_DATASOURCE_USERNAME": "sa", "SPRING_DATASOURCE_PASSWORD": "", "SPRING_JPA_DATABASE_PLATFORM": "org.hibernate.dialect.H2Dialect"})
    else:
        name = service_name.replace("-", "_") + "_db"
        env.update({"SPRING_DATASOURCE_USERNAME": "app", "SPRING_DATASOURCE_PASSWORD": "${DB_PASSWORD:?Defina DB_PASSWORD en .env local}"})
        db = {"image": DATABASE_IMAGES[database], "pull_policy": "never", "volumes": ["dbdata:" + ("/var/lib/postgresql/data" if database == "POSTGRESQL" else "/var/lib/mysql")], "restart": "unless-stopped", "labels": {"io.agentia.role": "database"}}
        if database == "POSTGRESQL":
            env.update({"SPRING_DATASOURCE_URL": f"jdbc:postgresql://db:5432/{name}", "SPRING_DATASOURCE_DRIVER_CLASS_NAME": "org.postgresql.Driver", "SPRING_JPA_DATABASE_PLATFORM": "org.hibernate.dialect.PostgreSQLDialect"})
            db["environment"] = {"POSTGRES_DB": name, "POSTGRES_USER": "app", "POSTGRES_PASSWORD": "${DB_PASSWORD:?Defina DB_PASSWORD}"}
            db["healthcheck"] = {"test": ["CMD-SHELL", f"pg_isready -U app -d {name}"], "interval": "5s", "timeout": "3s", "retries": 20}
        else:
            env.update({"SPRING_DATASOURCE_URL": f"jdbc:mysql://db:3306/{name}?allowPublicKeyRetrieval=true&useSSL=false", "SPRING_DATASOURCE_DRIVER_CLASS_NAME": "com.mysql.cj.jdbc.Driver", "SPRING_JPA_DATABASE_PLATFORM": "org.hibernate.dialect.MySQLDialect"})
            db["environment"] = {"MYSQL_DATABASE": name, "MYSQL_USER": "app", "MYSQL_PASSWORD": "${DB_PASSWORD:?Defina DB_PASSWORD}", "MYSQL_ROOT_PASSWORD": "${DB_ROOT_PASSWORD:?Defina DB_ROOT_PASSWORD}"}
            db["healthcheck"] = {"test": ["CMD-SHELL", 'MYSQL_PWD=$$MYSQL_PASSWORD mysql -h 127.0.0.1 -u app -D ' + name + ' -e "SELECT 1"'], "interval": "5s", "timeout": "3s", "retries": 30}
        app["depends_on"] = {"db": {"condition": "service_healthy"}}
        result["services"]["db"] = db
        result["volumes"]["dbdata"] = {}
    # Named H2 volume needs correct ownership for the runtime user.
    result["services"]["data-init"] = {"image": "agentia-runtime:21-v1", "pull_policy": "never", "user": "0:0", "entrypoint": ["sh", "-c", "chown 10001:10001 /app/data"], "volumes": ["appdata:/app/data"], "network_mode": "none", "restart": "no"}
    app.setdefault("depends_on", {})["data-init"] = {"condition": "service_completed_successfully"}
    return yaml.safe_dump(result, sort_keys=False)


def write_windows_scripts(ws, build_tool, db_engine, host_port=8080):
    ws = Path(ws)
    image = builder_image(ws)
    base = GRADLE_IMAGE if build_tool == "gradle" else MAVEN_IMAGE
    warm = "gradle --no-daemon test bootJar" if build_tool == "gradle" else "mvn -B test package"
    from app.services.build_layout import build_layout
    _, directory, _ = build_layout(ws)
    if directory == 'bootstrap': warm = 'cd bootstrap && ' + warm
    cache = "/home/gradle/.gradle" if build_tool == "gradle" else "/root/.m2/repository"
    prep = f'''FROM {base}
USER root
WORKDIR /warmup
COPY . .
RUN {warm} && mkdir -p /opt/agentia-cache && cp -R {cache}/. /opt/agentia-cache/ && rm -rf /warmup
WORKDIR /workspace
'''
    (ws / "Dockerfile.prepare").write_text(prep, encoding="utf-8")
    (ws / "Dockerfile.runtime").write_text(f'''FROM {RUNTIME_IMAGE}
RUN command -v wget && command -v grep && addgroup -g 10001 -S appgroup && adduser -u 10001 -S appuser -G appgroup && mkdir -p /app/data && chown -R 10001:10001 /app
WORKDIR /app
USER 10001:10001
''', encoding="utf-8")
    (ws / "prepare-local.ps1").write_text(f'''# Preparación inicial online; no constituye prueba offline.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
function Invoke-Docker {{ & docker @args; if ($LASTEXITCODE -ne 0) {{ throw "Docker falló: $args" }} }}
Invoke-Docker info
Invoke-Docker compose version
Invoke-Docker build --pull -f Dockerfile.prepare -t {image} .
Invoke-Docker build --pull -f Dockerfile.runtime -t agentia-runtime:21-v1 .
{('Invoke-Docker pull ' + DATABASE_IMAGES[db_engine]) if DATABASE_IMAGES[db_engine] else ''}
Write-Host 'Preparación completa para las dependencias actuales. Para operar offline ejecute start-local.ps1.'
''', encoding="utf-8")
    (ws / "start-local.ps1").write_text(f'''param([ValidateRange(1024,65535)][int]$Port=8080)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
function Invoke-Docker {{ & docker @args; if ($LASTEXITCODE -ne 0) {{ throw "Docker falló: $args" }} }}
Invoke-Docker info
Invoke-Docker image inspect {image}
Invoke-Docker image inspect agentia-runtime:21-v1
Invoke-Docker compose config --quiet
Invoke-Docker compose build --pull=false --no-cache
$env:HOST_PORT = "$Port"
Invoke-Docker compose up -d --no-build --pull never --wait --wait-timeout 180
Write-Host "Servicio listo en http://localhost:$Port"
''', encoding="utf-8")
    (ws / "stop-local.ps1").write_text("$ErrorActionPreference='Stop'\nSet-Location -LiteralPath $PSScriptRoot\n& docker compose down\nif ($LASTEXITCODE -ne 0) { throw 'No se pudo detener el despliegue' }\n# Los volúmenes y datos se conservan.\n", encoding="utf-8")
    (ws / "cleanup-local.ps1").write_text("param([switch]$DeleteData)\n$ErrorActionPreference='Stop'\nif (-not $DeleteData) { throw 'Esta acción borra datos. Ejecute con -DeleteData para confirmarlo.' }\nSet-Location -LiteralPath $PSScriptRoot\n& docker compose down --volumes\nif ($LASTEXITCODE -ne 0) { throw 'No se pudo limpiar el despliegue' }\n", encoding="utf-8")
    (ws / ".env.example").write_text("# Copie a .env y elija credenciales locales. No publique .env.\nDB_PASSWORD=\nDB_ROOT_PASSWORD=\n", encoding="utf-8")
    (ws / "LOCAL_DEPLOYMENT.md").write_text("# Despliegue local Windows\n\nDocker es opcional para generar y exportar fuentes. Para ejecutar necesita Docker Desktop con contenedores Linux y virtualización disponible.\n\n1. Para PostgreSQL/MySQL copie `.env.example` a `.env` y defina contraseñas locales.\n2. Con conexión, ejecute `./prepare-local.ps1` (prepara imágenes y dependencias de este proyecto).\n3. Sin conexión, ejecute `./start-local.ps1 -Port 8080`. No requiere Java ni Maven/Gradle instalados en Windows.\n4. `./stop-local.ps1` conserva los datos; `./cleanup-local.ps1 -DeleteData` los elimina explícitamente.\n\nLas dependencias nuevas requieren repetir la preparación. El arranque offline compila y ejecuta pruebas dentro del build sin red. El esquema runtime se mantiene mediante Hibernate `update`; la validación de los scripts SQL y semillas sigue siendo independiente. La preparación ejecuta pruebas con red para resolver también sus dependencias: ese resultado no se registra como verificación offline.\n\nCI y Kubernetes se entregan como artefactos; su presencia no acredita una ejecución real.\n", encoding="utf-8")
    guide_path = ws / 'LOCAL_DEPLOYMENT.md'
    guide_path.write_text(guide_path.read_text(encoding='utf-8').replace('El esquema runtime se mantiene mediante Hibernate `update`; la validación de los scripts SQL y semillas sigue siendo independiente.', 'Liquibase aplica el SQL y las semillas versionados; Hibernate valida el esquema sin modificarlo.'), encoding='utf-8')
    with guide_path.open('a', encoding='utf-8') as guide:
        guide.write('\nEl esquema y las semillas se aplican mediante Liquibase dentro del JAR, una sola vez por base de datos. Hibernate valida el esquema. Las migraciones publicadas no se editan: los cambios posteriores requieren una nueva versión. `schema.sql` y `data.sql` existentes se conservan; la configuración del datasource no se reemplaza. `db/changelog/LOCAL_MIGRATIONS.json` registra motor y hashes del SQL normalizado. Retirar semillas o cambiar el motor después de publicar se rechaza: conserve el historial y use una migración adicional o un proyecto/base nuevos.\n')
        guide.write('\nLa imagen de aplicación, los contenedores y los volúmenes pertenecen al proyecto Compose de esta carpeta. Dos sesiones con el mismo nombre de servicio usan imágenes distintas. Los scripts fijan el proyecto con `-p`; al usar Compose manualmente conserve ese nombre para operar sobre los mismos datos. Copias con el mismo nombre de carpeta no se consideran automáticamente proyectos distintos.\n')
    project = re.sub(r'[^a-z0-9_-]', '-', ws.name.lower()).strip('-_') or 'agentia-local'
    for name in ('prepare-local.ps1', 'start-local.ps1', 'stop-local.ps1', 'cleanup-local.ps1'):
        script = ws / name
        content = script.read_text(encoding='utf-8')
        content = content.replace('docker compose ', f'docker compose -p {project} ').replace('Invoke-Docker compose ', f'Invoke-Docker compose -p {project} ')
        if name == 'start-local.ps1':
            content = content.replace('$env:HOST_PORT = "$Port"', '''$requestedPort = $Port
$foundPort = $false
for ($candidatePort=$Port; $candidatePort -lt [Math]::Min($requestedPort+100,65536); $candidatePort++) {
  $portProbe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback,$candidatePort)
  try { $portProbe.Start(); $Port=$candidatePort; $foundPort=$true; break }
  catch [System.Net.Sockets.SocketException] { }
  finally { $portProbe.Stop() }
}
if (-not $foundPort) { throw 'No hay un puerto localhost disponible en el rango solicitado' }
if ($Port -ne $requestedPort) { Write-Host "Puerto $requestedPort ocupado; se usará $Port" }
$env:HOST_PORT = "$Port"''')
        script.write_text(content, encoding='utf-8')
    from app.services.lifecycle_scripts import write_lifecycle_scripts
    write_lifecycle_scripts(ws, project)
    from app.services.standalone_delivery import write_standalone_delivery
    write_standalone_delivery(ws, project, build_tool, db_engine, host_port)
