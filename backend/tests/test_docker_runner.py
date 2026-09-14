import pytest
from app.sandbox.docker_runner import build_docker_cmd, DockerExecutionResult

def test_build_docker_cmd_structure():
    cmd = build_docker_cmd(
        workspace_host_path="/host/workspace/order-service",
        maven_cache_host_path="/host/.m2/repository",
        docker_image="maven:3.9-eclipse-temurin-21"
    )
    assert "docker" == cmd[0]
    assert "run" == cmd[1]
    assert "--rm" in cmd
    assert "--network" in cmd
    assert "none" in cmd[cmd.index("--network") + 1]
    assert "mvn" in cmd
    assert "test" in cmd
    assert "-o" in cmd  # Constitution Principle IV: offline-first

def test_docker_execution_result_model():
    result = DockerExecutionResult(
        exit_code=0,
        stdout="[INFO] BUILD SUCCESS",
        stderr="",
        duration_ms=2500
    )
    assert result.is_success is True
    assert result.exit_code == 0

