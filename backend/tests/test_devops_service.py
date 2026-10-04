import pytest
from pathlib import Path
import tempfile
import yaml

from app.models.devops import DatabaseEngine
from app.services.devops_service import (
    generate_all_devops_assets,
    generate_docker_compose,
    generate_dockerfile,
    generate_dockerignore,
    generate_github_actions,
    generate_gitlab_ci,
    generate_kubernetes_manifests,
)


def test_generate_dockerfile():
    dockerfile = generate_dockerfile("order-service")
    assert "FROM agentia-builder:" in dockerfile
    assert "FROM agentia-runtime:21-v1" in dockerfile
    assert "mvn -B -o" in dockerfile and "verify" in dockerfile
    assert "RUN --network=none" in dockerfile
    assert "BOOT-INF/" in dockerfile
    # Verify non-root user
    assert "USER 10001:10001" in dockerfile
    assert "10001" in dockerfile
    # Verify JVM flags
    assert "-XX:MaxRAMPercentage=75.0" in dockerfile
    # Verify healthcheck
    assert "HEALTHCHECK" in dockerfile
    assert "/actuator/health" in dockerfile


def test_generate_dockerignore():
    dockerignore = generate_dockerignore()
    assert ".git" in dockerignore
    assert "target/" in dockerignore
    assert "*.log" in dockerignore


def test_generate_docker_compose_postgresql():
    compose = generate_docker_compose("order-service", "POSTGRESQL", 8080)
    services = yaml.safe_load(compose)['services']
    assert services['db']['image'].startswith('postgres:16.')
    assert 'ports' not in services['db']
    assert 'dbdata:/var/lib/postgresql/data' in services['db']['volumes']
    app = services['order-service']
    assert app['image'] == '${COMPOSE_PROJECT_NAME}-order-service:local'
    assert app['ports'] == ['127.0.0.1:${HOST_PORT:-8080}:8080']
    assert app['pull_policy'] == 'never'
    assert app['environment']['SPRING_DATASOURCE_URL'] == 'jdbc:postgresql://db:5432/order_service_db'
    assert app['depends_on']['db']['condition'] == 'service_healthy'


def test_the_compose_file_does_not_initialise_the_schema_from_a_bind_mount():
    """The schema travels inside the artifact; the database container is not told about it.

    This asserted the opposite until the bind mount was removed, because the mount
    failed on a real host: `docker compose up` creates a missing mount source as a
    DIRECTORY, and even once it was a 0644 regular file the container was refused it --
    root inside the container, SELinux disabled, no ACLs, XFS, fresh volume and
    --force-recreate. Reproduced by the user, so it was not an artefact of one shell.

    Liquibase applies classpath migrations once. Hibernate validates the authored
    schema, and Spring's unversioned SQL initializer remains disabled on restarts.
    """
    compose = generate_docker_compose("order-service", "POSTGRESQL", 8080)

    assert "docker-entrypoint-initdb.d" not in compose, (
        "database initialisation depends on a host bind mount again"
    )
    env = yaml.safe_load(compose)['services']['order-service']['environment']
    assert str(env['SPRING_LIQUIBASE_ENABLED']).lower() == 'true'
    assert env['SPRING_SQL_INIT_MODE'] == 'never'
    assert env['SPRING_JPA_HIBERNATE_DDL_AUTO'] == 'validate'


def test_generate_docker_compose_mysql():
    compose = generate_docker_compose("inventory-service", "MYSQL", 8081)
    services = yaml.safe_load(compose)['services']
    assert services['db']['image'].startswith('mysql:8.0.')
    assert 'ports' not in services['db']
    assert 'dbdata:/var/lib/mysql' in services['db']['volumes']
    assert services['inventory-service']['environment']['SPRING_DATASOURCE_URL'].startswith('jdbc:mysql://db:3306/inventory_service_db')


def test_generate_docker_compose_h2():
    compose = generate_docker_compose("test-service", "H2", 8082)
    services = yaml.safe_load(compose)['services']
    assert services['test-service']['environment']['SPRING_DATASOURCE_URL'].startswith('jdbc:h2:file:')
    assert services['test-service']['volumes'] == ['appdata:/app/data']
    assert 'db' not in services
    # H2 standalone should NOT have a separate db container
    assert "image: postgres" not in compose
    assert "image: mysql" not in compose


def test_generate_github_actions():
    gh = generate_github_actions("payment-service")
    assert "name: \"CI/CD Pipeline - payment-service\"" in gh
    assert "mvn clean test" in gh
    assert "aquasecurity/trivy-action" in gh
    assert "payment-service:latest" in gh


def test_generate_gitlab_ci():
    gl = generate_gitlab_ci("payment-service")
    assert "stages:" in gl
    assert "build-test" in gl
    assert "security-audit" in gl
    assert "container-scan" in gl
    assert "trivy image" in gl


def test_generate_kubernetes_manifests():
    k8s = generate_kubernetes_manifests("order-service", 8080)
    assert "deployment.yaml" in k8s
    assert "service.yaml" in k8s
    assert "configmap.yaml" in k8s
    assert "ingress.yaml" in k8s

    deploy = k8s["deployment.yaml"]
    assert "kind: Deployment" in deploy
    assert "runAsNonRoot: true" in deploy
    assert "runAsUser: 10001" in deploy
    assert "/actuator/health/liveness" in deploy
    assert "/actuator/health/readiness" in deploy

    ingress = k8s["ingress.yaml"]
    assert "ingressClassName: nginx" in ingress
    assert "networking.k8s.io/v1" in ingress


def test_generate_all_devops_assets():
    with tempfile.TemporaryDirectory() as tmpdir:
        bundle = generate_all_devops_assets(
            workspace_dir=tmpdir,
            session_id="test-session-devops",
            service_name="order-service",
            db_engine="POSTGRESQL",
            host_port=8080,
        )

        assert bundle.sessionId == "test-session-devops"
        assert bundle.databaseEngine == DatabaseEngine.POSTGRESQL
        assert Path(tmpdir, "Dockerfile").exists()
        assert Path(tmpdir, ".dockerignore").exists()
        assert Path(tmpdir, "docker-compose.yml").exists()
        assert Path(tmpdir, ".github", "workflows", "ci-cd.yml").exists()
        assert Path(tmpdir, ".gitlab-ci.yml").exists()
        assert Path(tmpdir, "k8s", "deployment.yaml").exists()
        assert Path(tmpdir, "k8s", "service.yaml").exists()
        assert Path(tmpdir, "k8s", "configmap.yaml").exists()
        assert Path(tmpdir, "k8s", "ingress.yaml").exists()

