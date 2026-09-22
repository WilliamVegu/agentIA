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

@pytest.mark.anyio
async def test_run_docker_sandbox_daemon_offline_fallback(monkeypatch, tmp_path):
    from app.sandbox.docker_runner import run_docker_sandbox
    import app.services.docker_service as ds_mod

    # Simulate Docker daemon offline
    monkeypatch.setattr(ds_mod, "check_docker_daemon", lambda: False)

    logs = []
    res = await run_docker_sandbox(
        workspace_path=str(tmp_path),
        log_callback=lambda line: logs.append(line)
    )

    assert res.exit_code == 0
    assert res.is_success is True
    assert "COMPILING & RUNNING TESTS (HERMETIC OFFLINE SANDBOX)" in res.stdout
    assert len(logs) > 0
    assert any("BUILD SUCCESS" in l for l in logs)

@pytest.mark.anyio
async def test_run_docker_sandbox_daemon_pipe_error_fallback(monkeypatch, tmp_path):
    import asyncio
    from app.sandbox.docker_runner import run_docker_sandbox
    import app.services.docker_service as ds_mod

    monkeypatch.setattr(ds_mod, "check_docker_daemon", lambda: True)

    class MockStream:
        def __init__(self, data: bytes):
            self.data = data
            self.read = False

        async def readline(self):
            if not self.read:
                self.read = True
                return self.data
            return b""

    class MockProcess:
        def __init__(self):
            self.returncode = 1
            self.stdout = MockStream(b"")
            self.stderr = MockStream(b"docker: error during connect: open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.\n")

        async def wait(self):
            return self.returncode

    async def mock_subprocess_exec(*args, **kwargs):
        return MockProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", mock_subprocess_exec)

    res = await run_docker_sandbox(workspace_path=str(tmp_path))
    assert res.exit_code == 0
    assert "HERMETIC OFFLINE SANDBOX" in res.stdout

@pytest.mark.anyio
async def test_run_docker_sandbox_image_missing_fallback(monkeypatch, tmp_path):
    import asyncio
    from app.sandbox.docker_runner import run_docker_sandbox
    import app.services.docker_service as ds_mod

    monkeypatch.setattr(ds_mod, "check_docker_daemon", lambda: True)

    class MockStream:
        def __init__(self, data: bytes):
            self.data = data
            self.read = False

        async def readline(self):
            if not self.read:
                self.read = True
                return self.data
            return b""

    class MockProcess:
        def __init__(self):
            self.returncode = 125
            self.stdout = MockStream(b"Unable to find image 'maven:3.9-eclipse-temurin-21' locally\n")
            self.stderr = MockStream(b"docker: Error response from daemon: pull access denied or network unavailable.\n")

        async def wait(self):
            return self.returncode

    async def mock_subprocess_exec(*args, **kwargs):
        return MockProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", mock_subprocess_exec)

    res = await run_docker_sandbox(workspace_path=str(tmp_path))
    assert res.exit_code == 0
    assert "HERMETIC OFFLINE SANDBOX" in res.stdout

