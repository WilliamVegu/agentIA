import io
import zipfile
import pytest
from pathlib import Path
from app.services.export_service import create_project_zip

def test_create_project_zip(tmp_path):
    # Setup dummy project files
    project_dir = tmp_path / "order-service"
    project_dir.mkdir()

    pom_file = project_dir / "pom.xml"
    pom_file.write_text("<project></project>", encoding="utf-8")

    src_file = project_dir / "src" / "Main.java"
    src_file.parent.mkdir(parents=True)
    src_file.write_text("class Main {}", encoding="utf-8")

    # Hidden or temporary files to ignore
    target_dir = project_dir / "target"
    target_dir.mkdir()
    (target_dir / "app.jar").write_text("binary", encoding="utf-8")

    zip_bytes = create_project_zip(str(project_dir))
    assert isinstance(zip_bytes, bytes)
    assert len(zip_bytes) > 0

    # Verify ZIP contents
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        namelist = zf.namelist()
        assert any("pom.xml" in name for name in namelist)
        assert any("src/Main.java" in name.replace("\\", "/") for name in namelist)
        assert not any("target" in name for name in namelist)


def test_export_full_bundle(tmp_path):
    project_dir = tmp_path / "payment-service"
    project_dir.mkdir()

    (project_dir / "spec.md").write_text("# Spec", encoding="utf-8")
    (project_dir / "user_stories.json").write_text("[]", encoding="utf-8")
    (project_dir / "architecture.json").write_text("{}", encoding="utf-8")
    (project_dir / "schema.sql").write_text("CREATE TABLE t (id INT);", encoding="utf-8")
    (project_dir / "Dockerfile").write_text("FROM eclipse-temurin:21-jre-alpine", encoding="utf-8")
    (project_dir / "docker-compose.yml").write_text("version: '3.8'", encoding="utf-8")

    from app.services.export_service import export_full_bundle
    zip_bytes = export_full_bundle(str(project_dir))
    assert isinstance(zip_bytes, bytes)
    assert len(zip_bytes) > 0

    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        namelist = [n.replace("\\", "/") for n in zf.namelist()]
        assert "spec.md" in namelist
        assert "Dockerfile" in namelist
        assert "docker-compose.yml" in namelist

