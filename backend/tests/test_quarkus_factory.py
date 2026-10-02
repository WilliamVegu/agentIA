"""
Suite de Pruebas Unitarias para la Fábrica de Agentes Quarkus (Java 21 LTS / Quarkus 3.x).
Valida el ciclo de vida 100% optimizado:
1. Requisitos de negocio & arquetipo -> Contrato OpenAPI 3.1 generado directamente (sin módulo de preguntas)
2. Revisión dinámica del contrato -> Aprobación humana y congelamiento
3. Arquitectura & Aprobación/Reemplazo de extensiones Quarkus con versiones exactas
4. Generación dinámica de esqueleto y DTOs Java Records inmutables
5. Construcción de código, pruebas, auto-corrección (Self-Healing) y Code Review
6. Aprobación final DevOps, Dockerfile/Jenkinsfile y descarga en ZIP
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
import zipfile
import io

client = TestClient(app)


def test_quarkus_factory_full_lifecycle():
    # 1. PASO 1: Creación del pedido con requisitos de negocio y arquetipo
    order_payload = {
        "basic_data": {
            "service_name": "orders-service",
            "team": "Ventas",
            "group_id": "com.empresa.orders",
            "java_version": "21",
            "build_tool": "maven"
        },
        "business": {
            "description": "registrar pedidos con cliente e ítems, consultarlos por estado y cancelarlos si aún no fueron despachados."
        },
        "technical": {
            "database": "SQLite (Demo local portable)",
            "security": "JWT (SmallRye JWT)",
            "enable_kafka": False,
            "integraciones": []
        },
        "ai_mode": {
            "mode": "Medio",
            "estimated_tokens_min": 100000,
            "estimated_tokens_max": 200000
        },
        "attachments": {
            "existing_openapi": None,
            "support_docs": []
        }
    }

    res_create = client.post("/api/v1/quarkus/orders", json=order_payload, headers={"X-LLM-Provider": "mock"})
    assert res_create.status_code == 201
    order_data = res_create.json()
    order_id = order_data["id"]

    # El flujo ahora pasa DIRECTAMENTE a 'Contrato en revisión' (sin cuestionario de aclaración)
    assert order_data["status"] == "Contrato en revisión"
    assert order_data["basic_data"]["service_name"] == "orders-service"
    assert order_data["clarifications_completed"] is True
    assert order_data["openapi_contract"] is not None
    assert "openapi: 3.1.0" in order_data["openapi_contract"]
    assert len(order_data.get("user_stories", [])) >= 2
    assert order_data.get("database_model") is not None
    assert order_data["tokens_audit"]["by_agent"]["analista"] > 0
    assert order_data["tokens_audit"]["by_agent"]["requirements"] > 0
    assert order_data["tokens_audit"]["by_agent"]["database"] > 0
    assert order_data["tokens_audit"]["by_agent"]["architecture"] > 0
    assert order_data["tokens_audit"]["total_consumed"] > 0
    assert len(order_data.get("specialized_agents", [])) == 8
    assert order_data["specialized_agents"][0]["name"] == "🧠 Requirements Agent"
    assert order_data["specialized_agents"][0]["status"] == "Completado"

    # 2. CONTROL HUMANO 1: Aprobación y congelación del contrato OpenAPI (y modelo relacional)
    # Cualquier cambio que el usuario hace en el contrato es recibido aquí para conducir la API
    approval_payload = {
        "approved_by": "Lorena (Product Owner / Líder Técnico)",
        "comments": "Contrato OpenAPI revisado, modificado y congelado para el sprint.",
        "modified_openapi": order_data["openapi_contract"],
        "approve_database_model": True
    }

    res_approve = client.post(f"/api/v1/quarkus/orders/{order_id}/approve-contract", json=approval_payload)
    assert res_approve.status_code == 200
    order_after_approval = res_approve.json()
    assert order_after_approval["status"] == "Aprobado"
    assert order_after_approval["control_1_approved"] is True
    assert order_after_approval["database_model_approved"] is True

    # El Agente Arquitecto propone opciones arquitectónicas y extensiones con versiones
    arch_proposal = order_after_approval["architecture_proposal"]
    assert arch_proposal is not None
    assert len(arch_proposal["options"]) == 3
    assert len(arch_proposal["quarkus_extensions"]) >= 7
    # Validar que cada extensión Quarkus tiene versión explícita (Quarkus 3.15 LTS)
    for ext in arch_proposal["quarkus_extensions"]:
        assert ext["version"] == "3.15.1"
        assert ":" in ext["id"]

    assert arch_proposal["maven_preview"]["config_file_name"] == "pom.xml"
    assert "quarkus-bom" in arch_proposal["maven_preview"]["config_file_content"]
    assert arch_proposal["gradle_preview"]["config_file_name"] == "build.gradle"

    # 3. PASO 3: Selección de arquitectura y Aprobación/Reemplazo de extensiones Quarkus
    select_arch_payload = {
        "selected_pattern": "layered",
        "chosen_build_tool": "maven",
        "extensions": arch_proposal["recommended_extensions"],
        "selected_extensions": arch_proposal["quarkus_extensions"]
    }
    res_select = client.post(f"/api/v1/quarkus/orders/{order_id}/select-architecture", json=select_arch_payload)
    assert res_select.status_code == 200
    order_after_select = res_select.json()
    assert order_after_select["chosen_architecture"]["pattern"] == "layered"
    assert order_after_select["chosen_architecture"]["build_tool"] == "maven"
    assert len(order_after_select["quarkus_extensions"]) >= 7

    # 4. PASO 4: Generación dinámica del Esqueleto y DTOs Records inmutables
    res_skeleton = client.post(f"/api/v1/quarkus/orders/{order_id}/generate-skeleton")
    assert res_skeleton.status_code == 200
    order_after_skeleton = res_skeleton.json()
    assert order_after_skeleton["status"] == "Generando"
    assert order_after_skeleton["skeleton_generated"] is True
    files = order_after_skeleton["generated_files"]
    assert "pom.xml" in files
    assert "src/main/resources/application.properties" in files
    assert "src/main/resources/openapi/openapi.yaml" in files

    # Validar observabilidad y perfiles en application.properties
    app_props = files["src/main/resources/application.properties"]
    assert "quarkus.smallrye-health.root-path=/q/health" in app_props
    assert "quarkus.micrometer.export.prometheus.path=/q/metrics" in app_props
    assert "quarkus.opentelemetry.enabled=true" in app_props
    assert "%dev.quarkus.datasource.db-kind=sqlite" in app_props

    # 5. PASO 5 y 6: Construcción de lógica, pruebas, auto-corrección (Self-Healing) y Code Review
    res_build = client.post(f"/api/v1/quarkus/orders/{order_id}/build-and-test")
    assert res_build.status_code == 200
    order_after_build = res_build.json()
    assert order_after_build["status"] == "En revisión"
    assert order_after_build["code_generated"] is True
    assert order_after_build["tests_executed"] is True
    assert order_after_build["tests_summary"]["passed"] > 0

    # Validar bucle Self-Healing y reporte de Code Review
    assert len(order_after_build.get("self_healing_log", [])) >= 3
    assert order_after_build.get("code_review_report") is not None
    assert order_after_build["code_review_report"]["verdict"] == "APROBADO"

    # Validar atribución de tokens a los 8 agentes especializados
    by_agent = order_after_build["tokens_audit"]["by_agent"]
    assert by_agent["requirements"] > 0
    assert by_agent["architecture"] > 0
    assert by_agent["coding"] > 0
    assert by_agent["database"] > 0
    assert by_agent["security"] > 0
    assert by_agent["testing_debug"] > 0
    assert by_agent["code_review"] > 0
    assert by_agent["devops"] > 0

    # Validar que los 8 agentes están registrados y actualizados con estados correctos
    agents_map = {a["id"]: a for a in order_after_build.get("specialized_agents", [])}
    assert len(agents_map) == 8
    assert agents_map["requirements"]["status"] == "Completado"
    assert agents_map["architecture"]["status"] == "Completado"
    assert agents_map["coding"]["status"] == "Completado"
    assert agents_map["database"]["status"] == "Completado"
    assert agents_map["security"]["status"] == "Completado"
    assert agents_map["testing_debug"]["status"] == "Completado"
    assert agents_map["code_review"]["status"] == "Completado"

    # Validar suite de documentación generada
    docs = order_after_build["documentation"]
    assert "README.md" in docs
    assert "DOCUMENTACION_API.md" in docs
    assert "ADR_001_DECISIONES_ARQUITECTURA.md" in docs
    assert "GUIA_PRUEBAS_COBERTURA.md" in docs
    assert "GUIA_OPERACION_SERVICIO.md" in docs

    # 6. CONTROL HUMANO 2: Aprobación de Entrega Final y DevOps
    delivery_payload = {
        "approved_by": "Lorena (Product Owner)",
        "comments": "Código, pruebas y auditoría de calidad validadas. Aprobado para PR.",
        "target_git_repo": "https://github.com/empresa/orders-service.git",
        "branch_name": "feat/orders-microservice-quarkus"
    }

    res_delivery = client.post(f"/api/v1/quarkus/orders/{order_id}/approve-delivery", json=delivery_payload)
    assert res_delivery.status_code == 200
    order_delivered = res_delivery.json()
    assert order_delivered["status"] == "Entregado"
    assert order_delivered["control_2_approved"] is True
    assert "Jenkinsfile" in order_delivered["devops_artifacts"]
    assert "Dockerfile.jvm" in order_delivered["devops_artifacts"]

    # 7. Descarga de ZIP
    res_zip = client.get(f"/api/v1/quarkus/orders/{order_id}/export-zip")
    assert res_zip.status_code == 200
    assert res_zip.headers["content-type"] == "application/zip"

    # Verificar contenido del ZIP
    zip_in_mem = io.BytesIO(res_zip.content)
    with zipfile.ZipFile(zip_in_mem, "r") as zf:
        namelist = zf.namelist()
        assert any("pom.xml" in name for name in namelist)
        assert any("Jenkinsfile" in name for name in namelist)
        assert any("README.md" in name for name in namelist)
