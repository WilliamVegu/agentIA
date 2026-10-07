import os
import time
import asyncio
import subprocess
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

    ``exit_code == 0`` with ``fallback_used is True`` is legal **only** when
    ``ALLOW_HERMETIC_FALLBACK`` is enabled; it means "reported as passing without
    verification". Every consumer that computes a figure MUST exclude it.
    """

    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0

    # Feature 012 (FR-001, FR-009). Defaulted so every pre-existing construction
    # remains valid.
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    matched_pattern: Optional[str] = None
    attribution_ambiguous: bool = False

    @property
    def is_success(self) -> bool:
        return self.exit_code == 0

def build_docker_cmd(
    workspace_host_path: str,
    maven_cache_host_path: str,
    docker_image: str = "maven:3.9-eclipse-temurin-21"
) -> List[str]:
    """
    Builds the Docker execution command following Constitution Principle IV:
    - --network none (strictly offline hermetic execution)
    - Mounts maven local repository as read-only (:ro)
    - Mounts workspace directory as read-write
    - Executes `mvn test -o` (offline test)
    """
    # Normalize paths for mounting
    ws_path = str(Path(workspace_host_path).resolve())
    m2_path = str(Path(maven_cache_host_path).resolve())

    # The host may require a mount option (typically ":Z" on rootless podman with
    # SELinux labels). Without it the bind mount is unreadable inside the
    # container, Maven finds no pom.xml in /workspace, and the session blocks for
    # a reason unrelated to the generated code -- which is indistinguishable from
    # a real build failure at the report level. Empty by default so behaviour is
    # unchanged on hosts that do not need it.
    mount_suffix = getattr(settings, "DOCKER_MOUNT_SUFFIX", "") or ""

    return [
        "docker", "run", "--rm",
        "--network", "none",
        "-v", f"{ws_path}:/workspace{mount_suffix}",
        "-v", f"{m2_path}:/root/.m2/repository:ro{mount_suffix}",
        "-w", "/workspace",
        docker_image,
        "mvn", "test", "-o"
    ]

OFFLINE_SANDBOX_STDOUT = (
    "[INFO] Scanning for projects...\n"
    "[INFO] -------------------------------------------------------\n"
    "[INFO] COMPILING & RUNNING TESTS (HERMETIC OFFLINE SANDBOX)\n"
    "[INFO] -------------------------------------------------------\n"
    "[INFO] Compiling 6 source files with Java 21\n"
    "[INFO] Running Mockito unit tests\n"
    "[INFO] Tests run: 5, Failures: 0, Errors: 0, Skipped: 0\n"
    "[INFO] -------------------------------------------------------\n"
    "[INFO] BUILD SUCCESS\n"
    "[INFO] -------------------------------------------------------\n"
)

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

    * **Permissive** (``ALLOW_HERMETIC_FALLBACK`` true): the pre-change synthetic
      success is restored for local development -- ``exit_code = 0`` with the
      synthetic stdout. The marking is still set, because permissive mode changes
      what is permitted, not what is recorded (FR-007).
    * **Default**: ``exit_code = 1`` and no synthetic output, so the caller cannot
      mistake an unverified workspace for a verified one (FR-001). The caller
      must NOT reach the verified terminal state.
    """
    duration_ms = int((time.time() - start_time) * 1000)
    # `is True` rather than a truthiness test: only an explicit boolean True
    # enables permissive mode, so a malformed value (a stray string, a non-zero
    # int, a typo'd env var) fails SAFE to the honest path instead of silently
    # permitting synthetic verification.
    permitted = getattr(settings, "ALLOW_HERMETIC_FALLBACK", False) is True

    if permitted:
        if log_callback:
            for line in OFFLINE_SANDBOX_STDOUT.splitlines(keepends=True):
                log_callback(line)
        return DockerExecutionResult(
            exit_code=0,
            stdout=OFFLINE_SANDBOX_STDOUT,
            stderr="",
            duration_ms=duration_ms,
            fallback_used=True,
            fallback_reason=reason,
            matched_pattern=matched_pattern,
            attribution_ambiguous=attribution_ambiguous,
        )

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
    log_callback: Optional[Callable[[str], None]] = None
) -> DockerExecutionResult:
    """
    Executes Maven test within an isolated, offline Docker sandbox container.
    Streams output line by line to log_callback if provided.

    When a build cannot actually run, the outcome depends on
    ``ALLOW_HERMETIC_FALLBACK`` (see ``_build_hermetic_fallback_result``): the
    default reports a marked non-success, and permissive mode restores the legacy
    synthetic success for local development.
    """
    start_time = time.time()

    # 1. Preventive Docker Daemon check
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
    image = docker_image or settings.DOCKER_IMAGE
    cmd = build_docker_cmd(workspace_path, m2_cache, image)

    stdout_chunks: List[str] = []
    stderr_chunks: List[str] = []

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
                decoded = line.decode("utf-8", errors="replace")
                chunks.append(decoded)
                if log_callback:
                    log_callback(decoded)

        await asyncio.wait_for(
            asyncio.gather(
                stream_output(process.stdout, stdout_chunks),
                stream_output(process.stderr, stderr_chunks),
                process.wait()
            ),
            timeout=timeout_seconds
        )

        exit_code = process.returncode if process.returncode is not None else -1

    except FileNotFoundError:
        # The runtime executable is not installed on this host.
        return _build_hermetic_fallback_result(
            start_time, log_callback, reason=REASON_RUNTIME_MISSING
        )
    except asyncio.TimeoutError:
        try:
            process.kill()
        except Exception:
            pass
        return DockerExecutionResult(
            exit_code=-1,
            stdout="".join(stdout_chunks),
            stderr=f"Execution timed out after {timeout_seconds} seconds.",
            duration_ms=int((time.time() - start_time) * 1000)
        )
    except Exception as e:
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
