from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timezone

from app.models.devops import DatabaseEngine, DevOpsManifestBundle


def generate_dockerfile(service_name: str = "microservice", build_tool: str = "maven", prepared_image: str = "agentia-builder:prepare-first", build_directory: str = '.') -> str:
    from app.services.local_deployment_assets import dockerfile
    return dockerfile(build_tool, prepared_image, build_directory)




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
    from app.services.local_ci_assets import github
    return github(service_name)


def generate_gitlab_ci(service_name: str = "microservice") -> str:
    from app.services.local_ci_assets import gitlab
    return gitlab(service_name)


def generate_kubernetes_manifests(service_name: str = "microservice", host_port: int = 8080,
                                  db_engine: str = "POSTGRESQL", image: Optional[str] = None) -> Dict[str, str]:
    from app.services.local_kubernetes import manifests
    return manifests(service_name, db_engine, image)


def generate_all_devops_assets(
    workspace_dir: str,
    session_id: str,
    service_name: str = "microservice",
    db_engine: Optional[str] = None,
    host_port: Optional[int] = None
) -> DevOpsManifestBundle:
    from app.services.asset_generation import generate_safely
    from app.services.local_configuration import resolve_configuration
    config = resolve_configuration(workspace_dir, session_id, db_engine, host_port)
    return generate_safely(workspace_dir, session_id, _write_devops_assets,
                           service_name=service_name, db_engine=config['databaseEngine'], host_port=config['hostPort'])


def _write_devops_assets(
    workspace_dir: str,
    session_id: str,
    service_name: str = "microservice",
    db_engine: Optional[str] = None,
    host_port: int = 8080,
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
    from app.services.build_layout import build_layout
    build_tool, build_directory, build_manifest = build_layout(ws)
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
        elif db_engine.upper() == "H2" and "com.h2database" not in pom_text:
            deps_to_add.append('''        <dependency>
            <groupId>com.h2database</groupId>
            <artifactId>h2</artifactId>
            <scope>runtime</scope>
        </dependency>''')
        if deps_to_add and "</dependencies>" in pom_text:
            injection = "\n" + "\n".join(deps_to_add) + "\n    </dependencies>"
            pom_text = pom_text.replace("</dependencies>", injection, 1)
            pom_path.write_text(pom_text, encoding="utf-8")

    if build_tool == "gradle":
        gradle_file = build_manifest
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
        if db_engine.upper() == "H2" and "com.h2database:h2" not in text:
            dependencies.append(dependency("runtimeOnly", "com.h2database:h2"))
        if dependencies:
            gradle_file.write_text(text + "\ndependencies {\n" + "\n".join(dependencies) + "\n}\n", encoding="utf-8")

    from app.services.local_database_migrations import write_migrations
    write_migrations(ws, db_engine)
    from app.services.local_deployment_assets import builder_image, write_windows_scripts
    dockerfile = generate_dockerfile(service_name, build_tool, builder_image(ws), build_directory)
    (ws / "Dockerfile").write_text(dockerfile, encoding="utf-8")
    write_windows_scripts(ws, build_tool, db_engine, host_port)
    from app.services.offline_kit_assets import write_kit_scripts
    write_kit_scripts(ws, db_engine)

    # 2. docker-compose.yml
    compose = generate_docker_compose(service_name, db_engine, host_port)
    (ws / "docker-compose.yml").write_text(compose, encoding="utf-8")

    # 3. CI/CD Workflows
    github_actions = generate_github_actions(service_name)
    gitlab_ci = generate_gitlab_ci(service_name)
    from app.services.local_ci_assets import AUDIT_SCRIPT
    (ws / "local-ci.py").write_text(AUDIT_SCRIPT, encoding="utf-8")
    tools_script = Path(__file__).resolve().parents[2] / 'scripts' / 'prepare_local_tools.py'
    (ws / 'prepare-tools.py').write_bytes(tools_script.read_bytes())

    gh_dir = ws / ".github" / "workflows"
    gh_dir.mkdir(parents=True, exist_ok=True)
    (gh_dir / "ci-cd.yml").write_text(github_actions, encoding="utf-8")
    (ws / ".gitlab-ci.yml").write_text(gitlab_ci, encoding="utf-8")

    # 4. Kubernetes Manifests
    k8s_manifests = generate_kubernetes_manifests(service_name, host_port, db_engine,
                                                f"{session_id}-{service_name}:local")
    from app.services.local_kubernetes import validate_catalogue
    validate_catalogue(k8s_manifests, db_engine)
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

