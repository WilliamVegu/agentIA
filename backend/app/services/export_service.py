import io
import os
import zipfile
from pathlib import Path

def create_project_zip(workspace_path: str) -> bytes:
    """
    Packages the generated project into a standalone, clean ZIP archive in-memory.
    Excludes build directories (target/), caches, and VCS files.
    """
    ws_dir = Path(workspace_path).resolve()
    buffer = io.BytesIO()

    ignored_dirs = {".git", "target", ".idea", "__pycache__", ".m2"}
    ignored_files = {".DS_Store", "Thumbs.db"}

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(ws_dir):
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            for file in files:
                if file in ignored_files or file.endswith(".pyc"):
                    continue
                full_path = Path(root) / file
                rel_path = str(full_path.relative_to(ws_dir)).replace("\\", "/")
                zf.write(full_path, arcname=rel_path)

    buffer.seek(0)
    return buffer.getvalue()


def export_full_bundle(workspace_path: str) -> bytes:
    """Packages the complete microservice workspace bundle (specs, stories, architecture,

    models, code, tests, security audits, Dockerfile, CI/CD, and Kubernetes manifests)
    into a clean production ZIP archive.
    """
    return create_project_zip(workspace_path)

