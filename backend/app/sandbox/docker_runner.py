import os
import re
import time
import asyncio
import subprocess
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
    ws_path = str(Path(workspace_host_path).resolve()) if Path(workspace_host_path).exists() else str(workspace_host_path)
    m2_path = str(Path(maven_cache_host_path).resolve()) if Path(maven_cache_host_path).exists() else str(maven_cache_host_path)

    # The host may require a mount option (typically ":Z" on rootless podman with
    # SELinux labels). Without it the bind mount is unreadable inside the
    # container, Maven finds no pom.xml in /workspace, and the session blocks for
    # a reason unrelated to the generated code -- which is indistinguishable from
    # a real build failure at the report level. Empty by default so behaviour is
    # unchanged on hosts that do not need it.
    mount_suffix = getattr(settings, "DOCKER_MOUNT_SUFFIX", "") or ""

    if (Path(workspace_host_path) / "build.gradle").exists() or (Path(workspace_host_path) / "build.gradle.kts").exists():
        cache = os.environ.get("GRADLE_CACHE_DIR", str(Path.home() / ".gradle"))
        return ["docker", "run", "--rm", "--network", "none",
                "-v", mount_spec(ws_path, "/workspace", suffix=mount_suffix),
                "-v", mount_spec(cache, "/opt/gradle-cache", read_only=True, suffix=mount_suffix),
                "-e", "GRADLE_USER_HOME=/tmp/gradle-home", "-w", "/workspace",
                os.environ.get("GRADLE_DOCKER_IMAGE", "gradle:8-jdk21"), "sh", "-c",
                "mkdir -p /tmp/gradle-home && cp -R /opt/gradle-cache/. /tmp/gradle-home/ && gradle --no-daemon --offline test"]

    return [
        "docker", "run", "--rm",
        "--network", "none",
        "-v", mount_spec(ws_path, "/workspace", suffix=mount_suffix),
        "-v", mount_spec(m2_path, "/root/.m2/repository", read_only=True, suffix=mount_suffix),
        "-w", "/workspace",
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



#: "Could not resolve dependencies for project ...: The following artifacts could not be
#: resolved: org.postgresql:postgresql:jar:42.7.1 (...), org.projectlombok:lombok:jar:..."
_MISSING_ARTIFACT = re.compile(r"([\w.\-]+:[\w.\-]+:(?:jar|pom|zip):[\w.\-]+)")

#: Where the local repository may live inside the container, for the message below.
_CONTAINER_M2 = "/root/.m2/repository"


def describe_missing_dependencies(output: str, limit: int = 6) -> Optional[str]:
    """Name the artifacts the offline build could not resolve, if any.

    A cold or partial Maven cache is the most common reason the hermetic sandbox cannot
    verify anything, and the raw Maven text scrolls past in a log panel while saying
    nothing about what to do. Naming the coordinates makes the remedy obvious: prime the
    cache, or add the dependency.

    Measured on a real run: the host cache held spring-boot-starter-web, data-jpa,
    validation, test and h2, and was missing `spring-boot-starter-actuator`, `postgresql`
    and `lombok` -- all three required by the generated `pom.xml`. Every session blocked
    with "la compilación o las pruebas unitarias fallaron", which was never measured.
    """
    # Only the list AFTER the marker. The same sentence contains the project's own
    # coordinates before it ("Could not resolve dependencies for project
    # com.corp.helpdesk:help-desk:jar:1.0.0"), which are not a missing dependency and were
    # reported as one by the first version of this function.
    marker = "the following artifacts could not be resolved"
    lowered = (output or "").lower()
    tail = (output or "")[lowered.index(marker) + len(marker):] if marker in lowered else ""
    if not tail:
        return None

    found = _MISSING_ARTIFACT.findall(tail)
    if not found:
        return None

    unique: List[str] = []
    for coordinate in found:
        if coordinate not in unique:
            unique.append(coordinate)
    shown = unique[:limit]
    remainder = len(unique) - len(shown)
    listed = ", ".join(shown) + (f" (+{remainder} more)" if remainder > 0 else "")
    return (
        f"the offline Maven cache is missing {len(unique)} artifact(s) required by this "
        f"project: {listed}. Prime the cache with an online build of this workspace "
        f"(mvn -B test-compile with network access and {_CONTAINER_M2} mounted), or remove "
        f"the dependency. Verification did NOT run, so the generated code is unmeasured."
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
        # Prefer the specific cause over the generic one. "the output matches the
        # environment pattern 'cannot access central'" is accurate and useless; naming the
        # artifacts that could not be resolved turns a blocked session into a one-command
        # remedy. Falls back to the pattern reason when the output names nothing.
        reason = describe_missing_dependencies(combined) or _environment_pattern_reason(
            matched_pattern
        )
        if log_callback:
            log_callback(f"[SANDBOX] {reason}")
        return _build_hermetic_fallback_result(
            start_time,
            log_callback,
            reason=reason,
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
