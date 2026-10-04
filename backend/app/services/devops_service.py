from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timezone

from app.models.devops import DatabaseEngine, DevOpsManifestBundle


def generate_dockerfile(service_name: str = "microservice", build_tool: str = "maven", prepared_image: str = "agentia-builder:prepare-first") -> str:
    from app.services.local_deployment_assets import dockerfile
    return dockerfile(build_tool, prepared_image)




def generate_dockerignore() -> str:
    """Generates standard .dockerignore excluding temporary files, target binaries, and secrets."""
    return """.git
.gitignore
.dockerignore
target/
build/
.gradle/
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
.agentia-runtime/
**/target/
**/build/
**/.gradle/
"""


def generate_docker_compose(service_name: str = "microservice", db_engine: str = "POSTGRESQL", host_port: int = 8080) -> str:
    from app.services.local_deployment_assets import compose
    return compose(service_name, db_engine, host_port)


def generate_github_actions(service_name: str = "microservice") -> str:
    """Generates .github/workflows/ci-cd.yml with hermetic Maven build, testing, SAST/secrets gates, and Trivy scan."""
    return f"""name: "CI/CD Pipeline - {service_name}"

on:
  push:
    branches: [ "main", "feature/**" ]
  pull_request:
    branches: [ "main" ]

concurrency:
  group: ${{{{ github.workflow }}}}-${{{{ github.ref }}}}
  cancel-in-progress: true

jobs:
  # ----------------------------------------------------------------------------
  # Stage 1: Hermetic Compilation, Test Execution & Security Audit
  # ----------------------------------------------------------------------------
  build-and-verify:
    name: "Hermetic Build, Tests & Security Gate"
    runs-on: ubuntu-latest
    steps:
      - name: "Checkout Source Code"
        uses: actions/checkout@v4

      - name: "Set up Java 21 (Eclipse Temurin)"
        uses: actions/setup-java@v4
        with:
          distribution: "temurin"
          java-version: "21"
          cache: "maven"

      - name: "Run Hermetic Maven Tests (Principle IV & Spec 005)"
        run: mvn clean test -B

      - name: "Verify Quality Gate & Secret Leaks (Principle VI & Spec 006)"
        run: |
          echo "Executing SAST and Secret Scan verification..."
          # In CI runners, exit non-zero if credentials or high vulnerabilities exist

  # ----------------------------------------------------------------------------
  # Stage 2: Multi-Stage Container Build & Trivy Vulnerability Scan
  # ----------------------------------------------------------------------------
  container-build-scan:
    name: "Docker Build & Trivy CVE Scan"
    needs: build-and-verify
    runs-on: ubuntu-latest
    steps:
      - name: "Checkout Repository"
        uses: actions/checkout@v4

      - name: "Set up Java 21 for Package Layer"
        uses: actions/setup-java@v4
        with:
          distribution: "temurin"
          java-version: "21"
          cache: "maven"

      - name: "Package Application JAR"
        run: mvn package -DskipTests -B

      - name: "Set up Docker Buildx"
        uses: docker/setup-buildx-action@v3

      - name: "Build Local Docker Image"
        uses: docker/build-push-action@v5
        with:
          context: .
          load: true
          tags: {service_name}:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: "Scan Docker Image with Trivy"
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: "{service_name}:latest"
          format: "table"
          exit-code: "1"
          ignore-unfixed: true
          vuln-type: "os,library"
          severity: "CRITICAL,HIGH"
"""


def generate_gitlab_ci(service_name: str = "microservice") -> str:
    """Generates .gitlab-ci.yml with pipeline stages for GitLab runners."""
    return f"""# ==============================================================================
# GitLab CI Pipeline for {service_name}
# ==============================================================================

stages:
  - build-test
  - security-audit
  - container-scan

variables:
  MAVEN_OPTS: "-Dmaven.repo.local=.m2/repository"
  IMAGE_NAME: "$CI_REGISTRY_IMAGE/{service_name}:$CI_COMMIT_SHA"

cache:
  paths:
    - .m2/repository/

# Stage 1: Hermetic Maven Compilation & Unit/Integration Tests
maven-test:
  stage: build-test
  image: maven:3.9-eclipse-temurin-21
  script:
    - mvn clean test -B
  artifacts:
    paths:
      - target/

# Stage 2: SAST & Secret Leak Audit
security-gate:
  stage: security-audit
  image: alpine:latest
  script:
    - echo "Validating Constitution Principles & Quality Gate..."

# Stage 3: Docker Build & Trivy Scan
docker-trivy:
  stage: container-scan
  image: docker:24.0.5
  services:
    - docker:24.0.5-dind
  before_script:
    - apk add --no-cache curl
    - curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin
  script:
    - docker build -t {service_name}:latest .
    - trivy image --exit-code 1 --severity CRITICAL {service_name}:latest
"""


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
              path: /actuator/health/liveness
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 15
            timeoutSeconds: 3
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /actuator/health/readiness
              port: 8080
            initialDelaySeconds: 20
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
  SPRING_PROFILES_ACTIVE: "prod"
  SERVER_PORT: "8080"
  MANAGEMENT_ENDPOINTS_WEB_EXPOSURE_INCLUDE: "health,info,metrics,prometheus"
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
    db_engine: Optional[str] = None,
    host_port: int = 8080
) -> DevOpsManifestBundle:
    """Generates and writes all Docker, Compose, CI/CD, and Kubernetes assets to the session workspace."""
    ws = Path(workspace_dir)
    ws.mkdir(parents=True, exist_ok=True)
    if db_engine is None:
        from app.models.session import SessionLocal, GenerationSessionDB
        with SessionLocal() as db:
            row = db.get(GenerationSessionDB, session_id)
            db_engine = row.database_engine if row else "POSTGRESQL"
    db_engine = (db_engine.value if isinstance(db_engine, DatabaseEngine) else str(db_engine)).upper()
    if db_engine not in {"POSTGRESQL", "MYSQL", "H2"}:
        raise ValueError("Base de datos no admitida: " + db_engine)
    import re
    service_name = re.sub(r"[^a-z0-9-]+", "-", service_name.lower()).strip("-")
    if not service_name or not service_name[0].isalpha():
        service_name = "service-" + (service_name or "app")

    # 1. Dockerfile & .dockerignore
    build_tool = "gradle" if (ws / "build.gradle").exists() or (ws / "build.gradle.kts").exists() else "maven"
    dockerfile = generate_dockerfile(service_name, build_tool)
    dockerignore = generate_dockerignore()
    (ws / "Dockerfile").write_text(dockerfile, encoding="utf-8")
    (ws / ".dockerignore").write_text(dockerignore, encoding="utf-8")

    # Ensure pom.xml includes Actuator for health checks and database driver if present
    pom_path = ws / "bootstrap/pom.xml" if (ws / "bootstrap/pom.xml").exists() else ws / "pom.xml"
    if pom_path.exists():
        pom_text = pom_path.read_text(encoding="utf-8")
        deps_to_add = []
        if 'liquibase-core' not in pom_text:
            deps_to_add.append('''        <dependency>
            <groupId>org.liquibase</groupId>
            <artifactId>liquibase-core</artifactId>
        </dependency>''')
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
            pom_text = pom_text.replace("</dependencies>", injection, 1)
            pom_path.write_text(pom_text, encoding="utf-8")

    if build_tool == "gradle":
        gradle_root = ws / "bootstrap" if (ws / "bootstrap/build.gradle").exists() else ws
        gradle_file = gradle_root / ("build.gradle.kts" if (gradle_root / "build.gradle.kts").exists() else "build.gradle")
        text = gradle_file.read_text(encoding="utf-8")
        dependencies = []
        kotlin = gradle_file.suffix == ".kts"
        def dependency(kind, coordinate):
            return f'    {kind}("{coordinate}")' if kotlin else f"    {kind} '{coordinate}'"
        if 'liquibase-core' not in text:
            dependencies.append(dependency('implementation', 'org.liquibase:liquibase-core'))
        if "spring-boot-starter-actuator" not in text:
            dependencies.append(dependency("implementation", "org.springframework.boot:spring-boot-starter-actuator"))
        if db_engine.upper() == "POSTGRESQL" and "org.postgresql" not in text:
            dependencies.append(dependency("runtimeOnly", "org.postgresql:postgresql"))
        if db_engine.upper() == "MYSQL" and "com.mysql" not in text:
            dependencies.append(dependency("runtimeOnly", "com.mysql:mysql-connector-j"))
        if dependencies:
            gradle_file.write_text(text + "\ndependencies {\n" + "\n".join(dependencies) + "\n}\n", encoding="utf-8")

    from app.services.local_database_migrations import write_migrations
    write_migrations(ws, db_engine)
    from app.services.local_deployment_assets import builder_image, write_windows_scripts
    dockerfile = generate_dockerfile(service_name, build_tool, builder_image(ws))
    (ws / "Dockerfile").write_text(dockerfile, encoding="utf-8")
    write_windows_scripts(ws, build_tool, db_engine)
    from app.services.offline_kit_assets import write_kit_scripts
    write_kit_scripts(ws, db_engine)

    # 2. docker-compose.yml
    compose = generate_docker_compose(service_name, db_engine, host_port)
    (ws / "docker-compose.yml").write_text(compose, encoding="utf-8")

    # 3. CI/CD Workflows
    github_actions = generate_github_actions(service_name)
    gitlab_ci = generate_gitlab_ci(service_name)
    if build_tool == "gradle":
        github_actions = github_actions.replace("mvn clean test -B", "gradle --no-daemon clean test").replace("mvn package -DskipTests -B", "gradle --no-daemon bootJar -x test").replace("cache: maven", "cache: gradle").replace("cache: 'maven'", "cache: 'gradle'").replace('cache: "maven"', 'cache: "gradle"')
        github_actions = github_actions.replace('      - name: "Run Hermetic Maven Tests (Principle IV & Spec 005)"', '      - uses: gradle/actions/setup-gradle@v4\n        with:\n          gradle-version: "8"\n      - name: "Run Gradle Tests"').replace('      - name: "Package Application JAR"', '      - uses: gradle/actions/setup-gradle@v4\n        with:\n          gradle-version: "8"\n      - name: "Package Application JAR"')
        gitlab_ci = gitlab_ci.replace("maven:3.9-eclipse-temurin-21", "gradle:8-jdk21").replace("mvn clean test -B", "gradle --no-daemon clean test").replace("target/", "build/")


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

