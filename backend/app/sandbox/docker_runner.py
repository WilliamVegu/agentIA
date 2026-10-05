import os
import re
import time
import asyncio
import subprocess
import uuid
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable, List
from pydantic import BaseModel, Field
from app.config import settings

class DockerExecutionResult(BaseModel):
    """Outcome of one verification attempt.

    The three outcomes the platform must distinguish are:

    * **verified and passed**  -- ``exit_code == 0``, ``fallback_used is False``
    * **verified and failed**  -- ``exit_code != 0``, ``fallback_used is False``
    * **could not verify**     -- ``exit_code != 0``, ``fallback_used is True``

    Unavailable execution never fabricates passing output or tests. Consumers
    require a nonempty suite, no fallback and current source evidence. Source-only
    execution is explicitly skipped; it is never a successful verification.
    """

    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0

    # Feature 012 (FR-001, FR-009). Defaulted so every pre-existing construction
    # remains valid.
    fallback_used: bool = False
    verification_skipped: bool = False
    fallback_reason: Optional[str] = None
    matched_pattern: Optional[str] = None
    attribution_ambiguous: bool = False
    verification_interrupted: bool = False
    cleanup_confirmed: Optional[bool] = None
    evidence_error: Optional[str] = None

    @property
    def is_success(self) -> bool:
        return self.exit_code == 0

_SUREFIRE_SUMMARY_RE = re.compile(
    r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)"
)


@dataclass(frozen=True)
class TestCounts:
    """What the build actually reported running.

    Reported rather than assumed because the alternative -- a fixed
    ``totalTests=5, passedTests=5`` on every success -- is a fabricated figure in
    the one field the whole acceptance signal rests on.
    """

    total: int
    failures: int
    errors: int
    skipped: int

    @property
    def passed(self) -> int:
        return max(self.total - self.failures - self.errors - self.skipped, 0)

    @property
    def all_passed(self) -> bool:
        return self.failures == 0 and self.errors == 0


def parse_test_counts(stdout: str) -> Optional[TestCounts]:
    """The build's final surefire summary, or ``None`` when none was printed.

    Surefire emits a ``Tests run:`` line per test class and again as a final
    total, so the **last** match is the summary. ``None`` is meaningful and is not
    zero: a build that reports success without ever printing a summary has not
    demonstrated that any test ran, and callers must not render that as a pass.
    """
    matches = _SUREFIRE_SUMMARY_RE.findall(stdout or "")
    if not matches:
        return None
    total, failures, errors, skipped = (int(value) for value in matches[-1])
    return TestCounts(total=total, failures=failures, errors=errors, skipped=skipped)


def mount_spec(
    host_path: str,
    container_path: str,
    *,
    read_only: bool = False,
    suffix: str = "",
) -> str:
    """Compose a ``-v`` / ``--volume`` specification with correctly joined options.

    **Docker separates the options after the second colon with COMMAS**, as in
    ``/host:/container:ro,Z``. The previous code concatenated them --
    ``f"...:ro{mount_suffix}"`` -- which for the documented ``:Z`` suffix produced
    ``:ro:Z``. Docker rejects that with ``invalid spec ... too many colons`` and
    exits 125 *before Maven runs*, so on any host that needs a label suffix every
    session failed to build for a reason that looks exactly like a real build
    failure. Only the combination is affected: a lone ``:Z`` or a lone ``:ro`` is
    valid, which is why this survived on unlabelled hosts.

    The suffix is accepted in any of the shapes a host configuration might supply
    (``Z``, ``:Z``, ``,Z``) so an operator cannot half-fix the setting.
    """
    options: List[str] = []
    if read_only:
        options.append("ro")
    cleaned = (suffix or "").strip().lstrip(":,").strip()
    options.extend(part for part in cleaned.split(",") if part)

    spec = f"{host_path}:{container_path}"
    if options:
        spec += ":" + ",".join(options)
    return spec


def build_docker_cmd(
    workspace_host_path: str,
    maven_cache_host_path: str,
    docker_image: str = "maven:3.9-eclipse-temurin-21",
    prepared: bool = False,
) -> List[str]:
    """
    Builds the Docker execution command following Constitution Principle IV:
    - --network none (strictly offline hermetic execution)
    - Mounts maven local repository as read-only (:ro)
    - Mounts workspace directory as read-write
    - Executes `mvn test -o` (offline test)
    """
    # Normalize paths for mounting
    ws_path = str(Path(workspace_host_path).resolve()) if Path(workspace_host_path).exists() else str(workspace_host_path)
    m2_path = str(Path(maven_cache_host_path).resolve()) if Path(maven_cache_host_path).exists() else str(maven_cache_host_path)

    # The host may require a mount option (typically ":Z" on rootless podman with
    # SELinux labels). Without it the bind mount is unreadable inside the
    # container, Maven finds no pom.xml in /workspace, and the session blocks for
    # a reason unrelated to the generated code -- which is indistinguishable from
    # a real build failure at the report level. Empty by default so behaviour is
    # unchanged on hosts that do not need it.
    mount_suffix = getattr(settings, "DOCKER_MOUNT_SUFFIX", "") or ""
    from app.services.build_layout import build_layout
    tool, directory, _ = build_layout(workspace_host_path)
    workdir = '/workspace' + ('/bootstrap' if directory == 'bootstrap' else '')

    if prepared:
        gradle = tool == 'gradle'
        from app.services.gradle_compatibility import installed_gradle_guard
        command = ("mkdir -p /tmp/gradle-home && cp -R /opt/agentia-cache/. /tmp/gradle-home/ && export GRADLE_USER_HOME=/tmp/gradle-home && " + installed_gradle_guard() + " && gradle --no-daemon --offline test bootJar" if gradle
                   else "mkdir -p /tmp/m2 && cp -R /opt/agentia-cache/. /tmp/m2/ && mvn -B -o -Dmaven.repo.local=/tmp/m2 verify")
        return ["docker", "run", "--rm", "--pull", "never", "--network", "none", "-v", mount_spec(ws_path, "/workspace", suffix=mount_suffix), "-w", workdir, docker_image, "sh", "-c", command]

    if tool == 'gradle':
        cache = os.environ.get("GRADLE_CACHE_DIR", str(Path.home() / ".gradle"))
        return ["docker", "run", "--rm", "--pull", "never", "--network", "none",
                "-v", mount_spec(ws_path, "/workspace", suffix=mount_suffix),
                "-v", mount_spec(cache, "/opt/gradle-cache", read_only=True, suffix=mount_suffix),
                "-e", "GRADLE_USER_HOME=/tmp/gradle-home", "-w", workdir,
                os.environ.get("GRADLE_DOCKER_IMAGE", "gradle:8-jdk21"), "sh", "-c",
                "mkdir -p /tmp/gradle-home && cp -R /opt/gradle-cache/. /tmp/gradle-home/ && gradle --no-daemon --offline test"]

    return [
        "docker", "run", "--rm", "--pull", "never",
        "--network", "none",
        "-v", mount_spec(ws_path, "/workspace", suffix=mount_suffix),
        "-v", mount_spec(m2_path, "/root/.m2/repository", read_only=True, suffix=mount_suffix),
        "-w", workdir,
        docker_image,
        "mvn", "test", "-o"
    ]

# Reasons are written to be self-describing and to avoid implying that the
# generated code was at fault. A substitution is an environment/verification
# problem, never a test or compilation failure (FR-003).
REASON_RUNTIME_UNREACHABLE = (
    "the container runtime is not reachable, so verification could not be performed"
)
REASON_RUNTIME_MISSING = (
    "the container runtime executable is not available, so verification could not be performed"
)
REASON_RUNTIME_COMMUNICATION = (
    "the container runtime could not be reached during execution, "
    "so verification could not be performed"
)


def _environment_pattern_reason(matched_pattern: str) -> str:
    return (
        f"the build did not complete verifiably: the output matches the environment "
        f"pattern {matched_pattern!r}. This may indicate an environment fault or a "
        f"project configuration error; the attribution is ambiguous and is not "
        f"resolved automatically."
    )


def _build_hermetic_fallback_result(
    start_time: float,
    log_callback: Optional[Callable[[str], None]] = None,
    reason: str = REASON_RUNTIME_UNREACHABLE,
    matched_pattern: Optional[str] = None,
    attribution_ambiguous: bool = False,
) -> DockerExecutionResult:
    """Build the result for an attempt that could not actually run a build.

    The single policy point for all four substitution triggers, so none of them
    can remain a silent success (FR-006).

    Always fail-safe: ``exit_code = 1`` and no synthetic output, so the caller
    cannot mistake an unverified workspace for a verified one (FR-001). There is
    no permissive path that fabricates a ``BUILD SUCCESS`` — a fabricated success
    is exactly the "garbage session" a verification seam must never produce.
    """
    duration_ms = int((time.time() - start_time) * 1000)

    notice = f"[SANDBOX] Verification could not be performed: {reason}\n"
    if log_callback:
        log_callback(notice)
    return DockerExecutionResult(
        exit_code=1,
        stdout="",
        stderr=notice,
        duration_ms=duration_ms,
        fallback_used=True,
        fallback_reason=reason,
        matched_pattern=matched_pattern,
        attribution_ambiguous=attribution_ambiguous,
    )

async def run_docker_sandbox(
    workspace_path: str,
    maven_cache_path: Optional[str] = None,
    docker_image: Optional[str] = None,
    timeout_seconds: int = 300,
    log_callback: Optional[Callable[[str], None]] = None,
    cancel_event=None,
    operation_id: Optional[str] = None,
    session_id: Optional[str] = None,
    mode=None,
) -> DockerExecutionResult:
    """
    Executes Maven test within an isolated, offline Docker sandbox container.
    Streams output line by line to log_callback if provided.

    Unavailable or interrupted execution always reports a non-success. Cancellation
    checks and removes only this operation's inspected temporary container.
    """
    start_time = time.time()
    from app.models.execution import ExecutionMode
    from app.models.session import SessionLocal, GenerationSessionDB
    identity = session_id or Path(workspace_path).name
    with SessionLocal() as db:
        row = db.get(GenerationSessionDB, identity)
        selected_mode = ExecutionMode(mode) if mode is not None else (ExecutionMode(row.execution_mode) if row else None)
    if selected_mode == ExecutionMode.SOURCE_ONLY:
        return DockerExecutionResult(exit_code=1, fallback_used=True, verification_skipped=True,
                                     fallback_reason='No ejecutadas por elección: sesión sin Docker.')
    if cancel_event is not None and cancel_event.is_set():
        return DockerExecutionResult(exit_code=-1, fallback_used=True, verification_interrupted=True,
                                     fallback_reason='Verificación cancelada antes de crear el contenedor.')

    if docker_image is None:
        from app.services.gradle_compatibility import validate_gradle_version
        try:
            validate_gradle_version(workspace_path)
        except ValueError as exc:
            return DockerExecutionResult(exit_code=1, fallback_used=True, fallback_reason=str(exc), stderr=str(exc))
    # 1. Preventive Docker Daemon check, after pure configuration validation.
    try:
        from app.services.docker_service import check_docker_daemon
        daemon_available = check_docker_daemon()
    except Exception:
        daemon_available = False

    if not daemon_available:
        return _build_hermetic_fallback_result(
            start_time, log_callback, reason=REASON_RUNTIME_UNREACHABLE
        )

    m2_cache = maven_cache_path or settings.MAVEN_CACHE_DIR
    from app.services.local_deployment_assets import builder_image
    image = docker_image or builder_image(workspace_path)
    prepared = docker_image is None
    if prepared:
        try:
            image_check = subprocess.run(["docker", "image", "inspect", image], capture_output=True, timeout=5, check=False)
            if image_check.returncode:
                from app.services.build_layout import build_layout
                tool, _, _ = build_layout(workspace_path)
                fallback_base = "agentia-builder:6c84a5fd3f4d9258a47363a6" if tool == "maven" else "agentia-builder:4fc2c4436a557b14575dff25"
                base_check = subprocess.run(["docker", "image", "inspect", fallback_base], capture_output=True, timeout=3, check=False)
                if base_check.returncode == 0:
                    subprocess.run(["docker", "tag", fallback_base, image], capture_output=True, timeout=5, check=False)
                    image_check = subprocess.run(["docker", "image", "inspect", image], capture_output=True, timeout=3, check=False)
            if image_check.returncode:
                return _build_hermetic_fallback_result(start_time, log_callback, reason=f"Imagen preparada ausente: {image}. Ejecute prepare-local.ps1 con conexión y reintente.")
        except (OSError, subprocess.SubprocessError):
            return _build_hermetic_fallback_result(start_time, log_callback, reason=REASON_RUNTIME_COMMUNICATION)
    cmd = build_docker_cmd(workspace_path, m2_cache, image, prepared=prepared)
    operation_id = operation_id or str(uuid.uuid4())
    # The container name is independent of user input and never reused by another attempt.
    container_name = 'agentia-verify-' + uuid.uuid4().hex
    cmd[2:2] = ['--name', container_name, '--label', f'com.docker.compose.project={identity}',
                '--label', 'io.agentia.role=verification', '--label', f'io.agentia.operation={operation_id}']

    stdout_chunks = deque(maxlen=1000)
    stderr_chunks = deque(maxlen=1000)
    process = None
    interrupted = None
    needs_cleanup = False
    completion = None

    class Interrupted(RuntimeError):
        pass

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        async def stream_output(stream, chunks: List[str]):
            while True:
                line = await stream.readline()
                if not line:
                    break
                from app.services.deployment_logs import redact
                decoded = redact(line.decode("utf-8", errors="replace")[:8192])
                chunks.append(decoded)
                if log_callback:
                    try:
                        log_callback(decoded)
                    except Exception:
                        pass

        completion = asyncio.gather(
                stream_output(process.stdout, stdout_chunks),
                stream_output(process.stderr, stderr_chunks),
                process.wait()
            )
        async def wait_completion():
            while not completion.done():
                if cancel_event is not None and cancel_event.is_set():
                    raise Interrupted('Verificación cancelada por solicitud del usuario.')
                await asyncio.wait([completion], timeout=0.2)
            if cancel_event is not None and cancel_event.is_set():
                raise Interrupted('Verificación interrumpida; el resultado no se confirma.')
            await completion
        await asyncio.wait_for(wait_completion(), timeout=timeout_seconds)

        exit_code = process.returncode if process.returncode is not None else -1

    except FileNotFoundError:
        # The runtime executable is not installed on this host.
        return _build_hermetic_fallback_result(
            start_time, log_callback, reason=REASON_RUNTIME_MISSING
        )
    except (asyncio.TimeoutError, Interrupted) as exc:
        needs_cleanup = True
        reason = f'Verificación interrumpida por timeout de {timeout_seconds} segundos.' if isinstance(exc, asyncio.TimeoutError) else str(exc)
        interrupted = DockerExecutionResult(
            exit_code=-1,
            stdout="".join(stdout_chunks),
            stderr=reason, fallback_used=True, verification_interrupted=True, fallback_reason=reason,
            duration_ms=int((time.time() - start_time) * 1000)
        )
        return interrupted
    except asyncio.CancelledError:
        needs_cleanup = True
        raise
    except Exception as e:
        needs_cleanup = process is not None
        err_msg = str(e).lower()
        if any(pat in err_msg for pat in ["docker", "daemon", "pipe", "connect", "not found"]):
            return _build_hermetic_fallback_result(
                start_time, log_callback, reason=REASON_RUNTIME_COMMUNICATION
            )
        return DockerExecutionResult(
            exit_code=1,
            stdout="".join(stdout_chunks),
            stderr=f"Failed to execute Docker container: {str(e)}",
            duration_ms=int((time.time() - start_time) * 1000)
        )
    finally:
        if needs_cleanup:
            if process is not None and process.returncode is None:
                try:
                    process.kill()
                    await asyncio.wait_for(process.wait(), timeout=5)
                except Exception:
                    pass  # Container cleanup is independently inspected below.
            if completion is not None:
                if not completion.done():
                    completion.cancel()
                await asyncio.gather(completion, return_exceptions=True)
            from app.services.sandbox_resources import cleanup_sandbox
            try:
                confirmed = await asyncio.to_thread(cleanup_sandbox, container_name, identity, operation_id)
                if interrupted is not None:
                    interrupted.cleanup_confirmed = confirmed
                    interrupted.stderr += ' Contenedor temporal retirado; fuentes y cachés conservadas.'
            except Exception as cleanup_error:
                if interrupted is not None:
                    interrupted.cleanup_confirmed = False
                    interrupted.stderr += ' Limpieza no confirmada: ' + str(cleanup_error)
                if log_callback:
                    log_callback('[SANDBOX] Limpieza no confirmada: ' + str(cleanup_error))

    stdout_text = "".join(stdout_chunks)
    stderr_text = "".join(stderr_chunks)
    combined = (stdout_text + " " + stderr_text).lower()

    # Detect if failure is due to Docker daemon issues, missing local image, or cold offline Maven cache
    ENVIRONMENT_FALLBACK_PATTERNS = [
        "dockerdesktoplinuxengine",
        "error during connect",
        "cannot connect to the docker daemon",
        "is the docker daemon running",
        "daemon is not running",
        "the system cannot find the file specified",
        "pipe/docker",
        "connection refused",
        "unable to find image",
        "image not found",
        "no such image",
        "manifest unknown",
        "pull access denied",
        # Cold host Maven cache with --network none / offline mode
        "non-resolvable parent pom",
        "cannot access central",
        "offline mode and the artifact",
        "the following artifacts could not be resolved",
        "could not resolve dependencies",
        "unresolvablemodelexception",
        "projectbuildingexception",
    ]
    # The pattern set is deliberately NOT narrowed (FR-009 / Q2): it also matches
    # signatures Maven emits for genuinely broken build files, and misclassifying a
    # real environment fault as a project error would produce a false FAILURE --
    # worse than a false "could not verify". The ambiguity is recorded instead.
    matched_pattern = next(
        (pat for pat in ENVIRONMENT_FALLBACK_PATTERNS if pat in combined), None
    )
    if exit_code != 0 and matched_pattern is not None:
        if log_callback:
            log_callback(
                "[SANDBOX] Docker offline cache cold or container environment error. "
                "Verification could not be performed."
            )
        return _build_hermetic_fallback_result(
            start_time,
            log_callback,
            reason=_environment_pattern_reason(matched_pattern),
            matched_pattern=matched_pattern,
            attribution_ambiguous=True,
        )

    duration_ms = int((time.time() - start_time) * 1000)
    return DockerExecutionResult(
        exit_code=exit_code,
        stdout=stdout_text,
        stderr=stderr_text,
        duration_ms=duration_ms
    )
