import pytest
from pathlib import Path
import tempfile

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
    dockerfile=generate_dockerfile('ledger-service','maven','prepared-native:exact-manifest')
    assert 'FROM prepared-native:exact-manifest AS build' in dockerfile
    assert 'FROM agentia-runtime:21-v1' in dockerfile
    assert 'quarkus-app' in dockerfile and 'quarkus-run.jar' in dockerfile
    assert 'USER 10001:10001' in dockerfile
    assert 'mvn' in dockerfile and 'verify' in dockerfile and ' -o ' in dockerfile
    assert 'RUN --network=none' in dockerfile
    assert 'DskipTests' not in dockerfile and 'BOOT-INF' not in dockerfile


def test_generate_dockerignore():
    dockerignore = generate_dockerignore()
    assert ".git" in dockerignore
    assert "target/" in dockerignore
    assert "*.log" in dockerignore


def test_generate_docker_compose_postgresql():
    compose = generate_docker_compose("order-service", "POSTGRESQL", 8080)
    assert "version:" not in compose
    assert "image: postgres:16.4-alpine" in compose
    assert "5432:5432" not in compose
    assert "docker-entrypoint-initdb.d" not in compose
    assert "io.agentia.owner" in compose and "io.agentia.studio" in compose
    assert "pgdata:/var/lib/postgresql/data" in compose
    assert "condition: service_healthy" in compose
    assert "QUARKUS_DATASOURCE_JDBC_URL=jdbc:postgresql://db:5432/order-service_db" in compose


def test_generate_docker_compose_mysql():
    compose = generate_docker_compose("inventory-service", "MYSQL", 8081)
    assert "image: mysql:8.0.40" in compose
    assert "3306:3306" not in compose
    assert "mysqldata:/var/lib/mysql" in compose
    assert "QUARKUS_DATASOURCE_JDBC_URL=jdbc:mysql://db:3306/inventory-service_db" in compose


def test_generate_docker_compose_h2():
    compose = generate_docker_compose("test-service", "H2", 8082)
    assert "QUARKUS_DATASOURCE_DB_KIND=h2" in compose
    assert "jdbc:h2:mem:test-service_db" in compose
    # H2 standalone should NOT have a separate db container
    assert "image: postgres" not in compose
    assert "image: mysql" not in compose


def test_generate_github_actions():
    workflow=generate_github_actions('payment-service')
    assert 'Local verification - payment-service' in workflow
    assert 'runs-on: [self-hosted, Windows]' in workflow
    assert 'python local-ci.py --docker' in workflow
    assert 'if: inputs.docker' in workflow
    assert 'echo' not in workflow and 'trivy-action' not in workflow


def test_generate_gitlab_ci():
    workflow=generate_gitlab_ci('payment-service')
    assert 'stages: [verify]' in workflow
    assert 'python local-ci.py' in workflow
    assert 'when: manual' in workflow
    assert '.agentia-runtime/local-ci-result.json' in workflow
    assert 'echo' not in workflow


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
    assert "/q/health/live" in deploy
    assert "/q/health/ready" in deploy

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

