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
    dockerfile = generate_dockerfile("order-service")
    # Verify multi-stage layertools
    assert "FROM eclipse-temurin:21-jre-alpine AS builder" in dockerfile
    assert "java -Djarmode=layertools -jar application.jar extract" in dockerfile
    assert "FROM eclipse-temurin:21-jre-alpine AS runner" in dockerfile
    # Verify non-root user
    assert "USER appuser:appgroup" in dockerfile
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
    assert "version: '3.8'" in compose
    assert "image: postgres:16-alpine" in compose
    assert "5432:5432" in compose
    assert "schema.sql:/docker-entrypoint-initdb.d/01-schema.sql:ro" in compose
    assert "pgdata:/var/lib/postgresql/data" in compose
    assert "condition: service_healthy" in compose
    assert "SPRING_DATASOURCE_URL=jdbc:postgresql://db:5432/order-service_db" in compose


def test_generate_docker_compose_mysql():
    compose = generate_docker_compose("inventory-service", "MYSQL", 8081)
    assert "image: mysql:8.0-debian" in compose
    assert "3306:3306" in compose
    assert "mysqldata:/var/lib/mysql" in compose
    assert "SPRING_DATASOURCE_URL=jdbc:mysql://db:3306/inventory-service_db" in compose


def test_generate_docker_compose_h2():
    compose = generate_docker_compose("test-service", "H2", 8082)
    assert "SPRING_PROFILES_ACTIVE=h2" in compose
    assert "jdbc:h2:mem:test-service_db" in compose
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

