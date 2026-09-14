import sys
import subprocess
from app.config import settings

def verify_docker_environment() -> dict:
    """
    Verifies Docker host availability and local existence of
    the required Java 21 / Maven 3.9 base image for offline hermetic execution.
    """
    results = {
        "docker_installed": False,
        "docker_running": False,
        "image_available": False,
        "image_name": settings.DOCKER_IMAGE,
        "maven_cache_dir": settings.MAVEN_CACHE_DIR,
        "message": ""
    }

    try:
        ver_proc = subprocess.run(["docker", "--version"], capture_output=True, text=True, check=False)
        if ver_proc.returncode == 0:
            results["docker_installed"] = True
        else:
            results["message"] = "Docker CLI returned non-zero code."
            return results
    except FileNotFoundError:
        results["message"] = "Docker executable not found on host PATH. Using simulated offline verification."
        return results

    try:
        info_proc = subprocess.run(["docker", "info"], capture_output=True, text=True, check=False)
        if info_proc.returncode == 0:
            results["docker_running"] = True
        else:
            results["message"] = "Docker daemon is not running."
            return results
    except Exception as e:
        results["message"] = f"Error querying Docker daemon: {e}"
        return results

    try:
        img_proc = subprocess.run(
            ["docker", "image", "inspect", settings.DOCKER_IMAGE],
            capture_output=True,
            text=True,
            check=False
        )
        if img_proc.returncode == 0:
            results["image_available"] = True
            results["message"] = f"Base image '{settings.DOCKER_IMAGE}' is pre-cached and ready for offline execution."
        else:
            results["message"] = f"Image '{settings.DOCKER_IMAGE}' not found locally. Run `docker pull {settings.DOCKER_IMAGE}`."
    except Exception as e:
        results["message"] = f"Error inspecting image: {e}"

    return results

if __name__ == "__main__":
    status = verify_docker_environment()
    print("Docker Verification Status:")
    for k, v in status.items():
        print(f"  {k}: {v}")

