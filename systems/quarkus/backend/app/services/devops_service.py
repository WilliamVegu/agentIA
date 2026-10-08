from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timezone

from app.models.devops import DatabaseEngine, DevOpsManifestBundle


def generate_dockerfile(service_name="microservice",build_tool="maven",prepared_image="agentia-quarkus-builder:prepare-first"):
    build="gradle --no-daemon --console=plain --offline build" if build_tool=='gradle' else "mvn -B -ntp -o -Dmaven.repo.local=/tmp/cache verify"
    cache="export GRADLE_USER_HOME=/tmp/cache && " if build_tool=='gradle' else ""
    output="build" if build_tool=='gradle' else "target"
    return f"""FROM {prepared_image} AS build
USER root
WORKDIR /workspace
COPY . .
RUN --network=none mkdir -p /tmp/cache && cp -R /opt/agentia-cache/. /tmp/cache/ && {cache}{build}
RUN --network=none test -f {output}/quarkus-app/quarkus-run.jar && cp -R {output}/quarkus-app /quarkus-app

FROM agentia-runtime:21-v1
WORKDIR /app
COPY --from=build --chown=10001:10001 /quarkus-app/ /app/
USER 10001:10001
ENV QUARKUS_HTTP_PORT=8080
EXPOSE 8080
HEALTHCHECK NONE
ENTRYPOINT ["java", "-jar", "/app/quarkus-run.jar"]
"""


def generate_dockerignore() -> str:
    """Generates standard .dockerignore excluding temporary files, target binaries, and secrets."""
    return """.git
.gitignore
.dockerignore
target/
*.log
*.class
*.jar
.mvn/
.idea/
.vscode/
*.swp
.DS_Store
Thumbs.db
.env*
secrets/
"""


def _generate_docker_compose_template(
    service_name: str = "microservice",
    db_engine: str = "POSTGRESQL",
    host_port: int = 8080
) -> str:
    """Generates docker-compose.yml orchestrating the microservice with its detected database engine."""
    db_engine_upper = db_engine.upper()

    if db_engine_upper == "H2":
        return f"""version: '3.8'

services:
  {service_name}:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: {service_name}
    ports:
      - "{host_port}:8080"
    environment:
      - QUARKUS_PROFILE=prod
      - QUARKUS_HTTP_PORT=8080
      - QUARKUS_DATASOURCE_DB_KIND=h2
      - QUARKUS_DATASOURCE_JDBC_URL=jdbc:h2:mem:{service_name}_db;MODE=PostgreSQL
      - QUARKUS_HIBERNATE_ORM_DATABASE_GENERATION=validate
    networks:
      - app-network
    restart: unless-stopped

networks:
  app-network:
    driver: bridge
"""

    elif db_engine_upper == "MYSQL":
        return f"""version: '3.8'

services:
  {service_name}:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: {service_name}
    ports:
      - "{host_port}:8080"
    environment:
      - QUARKUS_PROFILE=prod
      - QUARKUS_HTTP_PORT=8080
      - QUARKUS_DATASOURCE_DB_KIND=mysql
      - QUARKUS_DATASOURCE_JDBC_URL=jdbc:mysql://db:3306/{service_name}_db?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC
      - QUARKUS_DATASOURCE_USERNAME=root
      - QUARKUS_DATASOURCE_PASSWORD=${{DB_PASSWORD:-root}}
      - QUARKUS_HIBERNATE_ORM_DATABASE_GENERATION=validate
    depends_on:
      db:
        condition: service_healthy
    networks:
      - app-network
    restart: unless-stopped

  db:
    image: mysql:8.0.40
    container_name: {service_name}-mysql
    ports:
      - "3306:3306"
    environment:
      - MYSQL_ROOT_PASSWORD=${{DB_PASSWORD:-root}}
      - MYSQL_DATABASE={service_name}_db
    volumes:
      - mysqldata:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - app-network
    restart: unless-stopped

volumes:
  mysqldata:
    driver: local

networks:
  app-network:
    driver: bridge
"""

    else:  # Default to PostgreSQL
        return f"""version: '3.8'

services:
  {service_name}:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: {service_name}
    ports:
      - "{host_port}:8080"
    environment:
      - QUARKUS_PROFILE=prod
      - QUARKUS_HTTP_PORT=8080
      - QUARKUS_DATASOURCE_DB_KIND=postgresql
      - QUARKUS_DATASOURCE_JDBC_URL=jdbc:postgresql://db:5432/{service_name}_db
      - QUARKUS_DATASOURCE_USERNAME=postgres
      - QUARKUS_DATASOURCE_PASSWORD=${{DB_PASSWORD:-postgres}}
      - QUARKUS_HIBERNATE_ORM_DATABASE_GENERATION=validate
    depends_on:
      db:
        condition: service_healthy
    networks:
      - app-network
    restart: unless-stopped

  db:
    image: postgres:16.4-alpine
    container_name: {service_name}-postgres
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_DB={service_name}_db
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=${{DB_PASSWORD:-postgres}}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d {service_name}_db"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - app-network
    restart: unless-stopped

volumes:
  pgdata:
    driver: local

networks:
  app-network:
    driver: bridge
"""


def generate_docker_compose(service_name="microservice", db_engine="POSTGRESQL", host_port=8080):
    import yaml
    manifest = yaml.safe_load(_generate_docker_compose_template(service_name, db_engine, host_port))
    manifest.pop('version', None)
    owner = {'io.agentia.owner': chr(36) + '{COMPOSE_PROJECT_NAME}', 'io.agentia.studio': 'quarkus'}
    for name, service in manifest['services'].items():
        service.pop('container_name', None)
        service['labels'] = {**owner, 'io.agentia.role': 'database' if name == 'db' else 'application'}
        if name == 'db':
            service.pop('ports', None)
        else:
            service['ports'] = ['127.0.0.1:' + chr(36) + '{HOST_PORT:-' + str(host_port) + '}:8080']
    for kind in ('volumes', 'networks'):
        for name in manifest.get(kind, {}):
            definition = manifest[kind][name] or {}
            definition['labels'] = owner.copy()
            manifest[kind][name] = definition
    return yaml.safe_dump(manifest, sort_keys=False)


def generate_github_actions(service_name="microservice"):
    from app.services.local_ci_assets import github
    return github(service_name)


def generate_gitlab_ci(service_name="microservice"):
    from app.services.local_ci_assets import gitlab
    return gitlab(service_name)


def generate_kubernetes_manifests(
    service_name: str = "microservice",
    host_port: int = 8080
) -> Dict[str, str]:
    """Generates declarative production Kubernetes manifests: deployment, service, configmap, and ingress."""
    deployment_yaml = f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {service_name}
  labels:
    app.kubernetes.io/name: {service_name}
    app.kubernetes.io/part-of: microservices-platform
spec:
  replicas: 2
  selector:
    matchLabels:
      app: {service_name}
  template:
    metadata:
      labels:
        app: {service_name}
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        runAsGroup: 10001
        fsGroup: 10001
      containers:
        - name: {service_name}
          image: {service_name}:latest
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8080
              name: http
          envFrom:
            - configMapRef:
                name: {service_name}-config
          resources:
            requests:
              cpu: "200m"
              memory: "512Mi"
            limits:
              cpu: "1000m"
              memory: "1024Mi"
          livenessProbe:
            httpGet:
              path: /q/health/live
              port: 8080
            initialDelaySeconds: 20
            periodSeconds: 15
            timeoutSeconds: 3
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /q/health/ready
              port: 8080
            initialDelaySeconds: 10
            periodSeconds: 10
            timeoutSeconds: 3
            failureThreshold: 2
"""

    service_yaml = f"""apiVersion: v1
kind: Service
metadata:
  name: {service_name}-service
  labels:
    app.kubernetes.io/name: {service_name}
spec:
  type: ClusterIP
  ports:
    - port: 80
      targetPort: 8080
      protocol: TCP
      name: http
  selector:
    app: {service_name}
"""

    configmap_yaml = f"""apiVersion: v1
kind: ConfigMap
metadata:
  name: {service_name}-config
data:
  QUARKUS_PROFILE: "prod"
  QUARKUS_HTTP_PORT: "8080"
  QUARKUS_SMALLRYE_HEALTH_ROOT_PATH: "/q/health"
"""

    ingress_yaml = f"""apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {service_name}-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/proxy-body-size: "16m"
spec:
  ingressClassName: nginx
  rules:
    - host: {service_name}.local
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: {service_name}-service
                port:
                  number: 80
"""

    return {
        "deployment.yaml": deployment_yaml,
        "service.yaml": service_yaml,
        "configmap.yaml": configmap_yaml,
        "ingress.yaml": ingress_yaml,
    }


def generate_all_devops_assets(
    workspace_dir: str,
    session_id: str,
    service_name: str = "microservice",
    db_engine: str = "POSTGRESQL",
    host_port: int = 8080
) -> DevOpsManifestBundle:
    """Generates and writes all Docker, Compose, CI/CD, and Kubernetes assets to the session workspace."""
    ws = Path(workspace_dir)
    ws.mkdir(parents=True, exist_ok=True)

    # 1. Dockerfile & .dockerignore
    dockerignore = generate_dockerignore()
    (ws / ".dockerignore").write_text(dockerignore, encoding="utf-8")

    # Ensure pom.xml includes Actuator for health checks and database driver if present
    pom_path = ws / "pom.xml"
    if pom_path.exists():
        pom_text = pom_path.read_text(encoding="utf-8")
        deps_to_add = []
        is_quarkus = "quarkus" in pom_text.lower()
        if is_quarkus:
            if "quarkus-smallrye-health" not in pom_text:
                deps_to_add.append("""        <dependency>
            <groupId>io.quarkus</groupId>
            <artifactId>quarkus-smallrye-health</artifactId>
        </dependency>""")
            if db_engine.upper() == "POSTGRESQL" and "quarkus-jdbc-postgresql" not in pom_text:
                deps_to_add.append("""        <dependency>
            <groupId>io.quarkus</groupId>
            <artifactId>quarkus-jdbc-postgresql</artifactId>
            <scope>runtime</scope>
        </dependency>""")
            elif db_engine.upper() == "MYSQL" and "quarkus-jdbc-mysql" not in pom_text:
                deps_to_add.append("""        <dependency>
            <groupId>io.quarkus</groupId>
            <artifactId>quarkus-jdbc-mysql</artifactId>
        </dependency>""")
        else:
            if "spring-boot-starter-actuator" not in pom_text:
                deps_to_add.append("""        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>""")
            if db_engine.upper() == "POSTGRESQL" and "postgresql" not in pom_text:
                deps_to_add.append("""        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
            <scope>runtime</scope>
        </dependency>""")
            elif db_engine.upper() == "MYSQL" and "mysql-connector-j" not in pom_text:
                deps_to_add.append("""        <dependency>
            <groupId>com.mysql</groupId>
            <artifactId>mysql-connector-j</artifactId>
            <scope>runtime</scope>
        </dependency>""")
        if deps_to_add and "</dependencies>" in pom_text:
            injection = "\n" + "\n".join(deps_to_add) + "\n    </dependencies>"
            # The first closing tag belongs to the platform BOM. Runtime
            # extensions must go in the project's direct dependencies instead.
            management_end = pom_text.find("</dependencyManagement>")
            search_start = management_end + len("</dependencyManagement>") if management_end >= 0 else 0
            dependencies_end = pom_text.find("</dependencies>", search_start)
            if dependencies_end < 0:
                raise ValueError("Project dependencies section is missing")
            pom_text = pom_text[:dependencies_end] + injection + pom_text[dependencies_end + len("</dependencies>"):]
            pom_path.write_text(pom_text, encoding="utf-8")

    import hashlib,json
    from app.services.build_layout import build_layout
    from app.services.local_ci_assets import AUDIT_SCRIPT
    tool,directory,manifest=build_layout(ws)
    if directory!='.': raise ValueError('Quarkus requires a native root build manifest')
    inputs=[path for path in ws.rglob('*') if path.is_file() and path.name in {'pom.xml','build.gradle','build.gradle.kts','settings.gradle','settings.gradle.kts','gradle.properties','gradle.lockfile'} and not any(part in {'target','build','.agentia-runtime','.gradle'} for part in path.relative_to(ws).parts)]
    fingerprint=hashlib.sha256(b''.join(path.relative_to(ws).as_posix().encode()+b'\0'+path.read_bytes() for path in sorted(inputs))).hexdigest()
    builder='agentia-quarkus-builder:'+fingerprint[:20]
    dockerfile = generate_dockerfile(service_name,tool,builder)
    preparation_image='gradle:8.10.2-jdk21' if tool=='gradle' else 'maven:3.9-eclipse-temurin-21'
    preparation_build='gradle --no-daemon --console=plain build' if tool=='gradle' else 'mvn -B -ntp verify'
    preparation_cache='/home/gradle/.gradle' if tool=='gradle' else '/root/.m2/repository'
    (ws/'Dockerfile.prepare').write_text(f'FROM {preparation_image}\nUSER root\nWORKDIR /workspace\nCOPY . .\nRUN {preparation_build} && mkdir -p /opt/agentia-cache && cp -R {preparation_cache}/. /opt/agentia-cache/\nLABEL io.agentia.dependencies="{fingerprint}"\n',encoding='utf-8')
    preparation_script="""import argparse,json,subprocess
from pathlib import Path
parser=argparse.ArgumentParser(description='Explicit dependency preparation; never a verification verdict')
parser.add_argument('--allow-network',action='store_true')
args=parser.parse_args()
if not args.allow_network: parser.error('Preparation requires explicit --allow-network authorization')
root=Path(__file__).resolve().parent
config=json.loads((root/'ASSET_CONFIGURATION.json').read_text(encoding='utf-8'))
subprocess.run(['docker','build','--pull=false','-f','Dockerfile.prepare','-t',config['preparedBuilder'],'.'],cwd=root,check=True)
print('Dependencies prepared. Run python local-ci.py --docker for offline verification.')
"""
    (ws/'prepare-builder.py').write_text(preparation_script,encoding='utf-8')
    (ws/'local-ci.py').write_text(AUDIT_SCRIPT,encoding='utf-8')
    (ws/'ASSET_CONFIGURATION.json').write_text(json.dumps({'framework':'quarkus','buildTool':tool,'buildDirectory':'.','preparedBuilder':builder,'dependencyFingerprint':fingerprint,'databaseEngine':db_engine,'hostPort':host_port},indent=2),encoding='utf-8')
    (ws / 'Dockerfile').write_text(dockerfile,encoding='utf-8')
    # 2. docker-compose.yml
    compose = generate_docker_compose(service_name, db_engine, host_port)
    (ws / "docker-compose.yml").write_text(compose, encoding="utf-8")

    # 3. CI/CD Workflows
    github_actions = generate_github_actions(service_name)
    gitlab_ci = generate_gitlab_ci(service_name)

    gh_dir = ws / ".github" / "workflows"
    gh_dir.mkdir(parents=True, exist_ok=True)
    (gh_dir / "ci-cd.yml").write_text(github_actions, encoding="utf-8")
    (ws / ".gitlab-ci.yml").write_text(gitlab_ci, encoding="utf-8")

    # 4. Kubernetes Manifests
    k8s_manifests = generate_kubernetes_manifests(service_name, host_port)
    k8s_dir = ws / "k8s"
    k8s_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in k8s_manifests.items():
        (k8s_dir / filename).write_text(content, encoding="utf-8")

    engine_enum = DatabaseEngine.POSTGRESQL
    if db_engine.upper() == "MYSQL":
        engine_enum = DatabaseEngine.MYSQL
    elif db_engine.upper() == "H2":
        engine_enum = DatabaseEngine.H2

    return DevOpsManifestBundle(
        sessionId=session_id,
        serviceName=service_name,
        databaseEngine=engine_enum,
        dockerfileContent=dockerfile,
        dockerignoreContent=dockerignore,
        dockerComposeContent=compose,
        githubActionsWorkflow=github_actions,
        gitlabCiWorkflow=gitlab_ci,
        kubernetesManifests=k8s_manifests,
        generatedAt=datetime.now(timezone.utc).isoformat(),
    )

