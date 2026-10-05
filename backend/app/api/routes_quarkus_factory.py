"""
Rutas API FastAPI para la Fábrica de Agentes Java Quarkus (Lorena - Pedido 2).
Endpoints para el flujo de 8 pasos, 2 controles de aprobación humana y observabilidad.
"""

from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, status, Response, Header
from fastapi.responses import StreamingResponse
import io
from typing import Optional

from app.models.quarkus_factory import (
    FactoryOrder,
    CreateOrderRequest,
    SubmitAnswersRequest,
    ApproveContractRequest,
    SelectArchitectureRequest,
    GenerateArchetypeRequest,
    SuggestExtensionRequest,
    ApproveDeliveryRequest,
    ArchitectureProposal,
    PublishQuarkusGitRequest,
    PublishQuarkusGitResponse
)
from app.services.quarkus_factory.factory_orchestrator import FactoryOrchestrator

router = APIRouter(prefix="/quarkus", tags=["Fábrica de Agentes Quarkus 3.x"])


@router.post("/orders", response_model=FactoryOrder, status_code=status.HTTP_201_CREATED)
def create_order(
    request: CreateOrderRequest,
    x_llm_api_key: Optional[str] = Header(None, alias="X-LLM-API-Key"),
    x_llm_provider: Optional[str] = Header(None, alias="X-LLM-Provider"),
    x_llm_model: Optional[str] = Header(None, alias="X-LLM-Model")
):
    """
    Paso 1: Ingreso de requerimientos de negocio y arquetipo (Maven o Gradle).
    El Agente Analista sintetiza directamente el contrato OpenAPI 3.1, Historias de Usuario BDD y Modelo de Base de Datos para revisión.
    """
    try:
        return FactoryOrchestrator.create_order(
            request,
            api_key=x_llm_api_key,
            provider=x_llm_provider,
            model_name=x_llm_model
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/orders", response_model=List[FactoryOrder])
def list_orders():
    """
    Monitoreo de Tracking: Lista todos los pedidos y sus estados de ciclo de vida.
    """
    return FactoryOrchestrator.list_orders()


@router.get("/orders/{order_id}", response_model=FactoryOrder)
def get_order(order_id: str):
    """
    Obtiene el detalle completo de un pedido, su progreso y auditoría de tokens.
    """
    order = FactoryOrchestrator.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Pedido {order_id} no encontrado")
    return order


@router.post("/orders/{order_id}/answers", response_model=FactoryOrder)
def submit_clarification_answers(
    order_id: str,
    request: SubmitAnswersRequest,
    x_llm_api_key: Optional[str] = Header(None, alias="X-LLM-API-Key"),
    x_llm_provider: Optional[str] = Header(None, alias="X-LLM-Provider"),
    x_llm_model: Optional[str] = Header(None, alias="X-LLM-Model")
):
    """
    Paso 2: Enviar respuestas a las preguntas de aclaración.
    El Agente Analista redacta el contrato OpenAPI 3.1 completo (con IA si hay API Key).
    """
    try:
        return FactoryOrchestrator.submit_clarifications(
            order_id,
            request.answers,
            api_key=x_llm_api_key,
            provider=x_llm_provider,
            model_name=x_llm_model
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/orders/{order_id}/approve-contract", response_model=FactoryOrder)
def approve_contract(
    order_id: str,
    request: ApproveContractRequest,
    x_llm_api_key: Optional[str] = Header(None, alias="X-LLM-API-Key"),
    x_llm_provider: Optional[str] = Header(None, alias="X-LLM-Provider"),
    x_llm_model: Optional[str] = Header(None, alias="X-LLM-Model")
):
    """
    Control Humano 1: El usuario revisa, edita si desea y aprueba el contrato OpenAPI.
    El contrato queda congelado. El Agente Arquitecto genera opciones con IA y comparador Maven/Gradle.
    """
    try:
        return FactoryOrchestrator.approve_contract(
            order_id,
            request,
            api_key=x_llm_api_key,
            provider=x_llm_provider,
            model_name=x_llm_model
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/orders/{order_id}/architecture-proposal", response_model=ArchitectureProposal)
def get_architecture_proposal(order_id: str):
    """
    Obtiene la propuesta del Agente Arquitecto: 3 opciones arquitectónicas y
    el previsualizador comparativo de arquetipos Maven (pom.xml) vs Gradle (build.gradle).
    """
    order = FactoryOrchestrator.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Pedido {order_id} no encontrado")
    if not order.architecture_proposal:
        raise HTTPException(status_code=400, detail="El contrato OpenAPI aún no ha sido aprobado.")
    return order.architecture_proposal


@router.post("/orders/{order_id}/select-architecture", response_model=FactoryOrder)
def select_architecture(order_id: str, request: SelectArchitectureRequest):
    """
    Paso 3: El usuario escoge la opción de arquitectura y confirma Maven o Gradle.
    """
    try:
        return FactoryOrchestrator.select_architecture(order_id, request)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/orders/{order_id}/generate-archetype", response_model=FactoryOrder)
def generate_archetype(order_id: str, request: GenerateArchetypeRequest):
    """
    Genera el arquetipo interactivo con IA (Maven o Gradle) con las extensiones aprobadas por el usuario.
    """
    try:
        return FactoryOrchestrator.generate_archetype(order_id, request)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/orders/{order_id}/suggest-extension")
def suggest_extension(
    order_id: str,
    request: SuggestExtensionRequest,
    x_llm_api_key: Optional[str] = Header(None, alias="X-LLM-API-Key"),
    x_llm_provider: Optional[str] = Header(None, alias="X-LLM-Provider"),
    x_llm_model: Optional[str] = Header(None, alias="X-LLM-Model")
):
    """
    Consulta con IA qué extensión oficial de Quarkus utilizar para una necesidad específica.
    """
    try:
        return FactoryOrchestrator.suggest_extension(
            order_id,
            request.query,
            api_key=x_llm_api_key,
            provider=x_llm_provider,
            model_name=x_llm_model
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/orders/{order_id}/generate-skeleton", response_model=FactoryOrder)
def generate_skeleton(order_id: str):
    """
    Paso 4: Esqueleto Automático.
    Genera el proyecto Quarkus, DTOs inmutables e interfaces JAX-RS / Reactive desde el OpenAPI.
    """
    try:
        return FactoryOrchestrator.generate_skeleton(order_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/orders/{order_id}/build-and-test", response_model=FactoryOrder)
def build_and_test(order_id: str):
    """
    Paso 5 y 6: Construcción de lógica (Desarrollador Java), Pruebas (QA) y Documentación.
    Pasa a estado 'En revisión' esperando la aprobación final (Control 2).
    """
    try:
        return FactoryOrchestrator.build_and_test(order_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/orders/{order_id}/approve-delivery", response_model=FactoryOrder)
def approve_delivery(order_id: str, request: ApproveDeliveryRequest):
    """
    Control Humano 2: El usuario aprueba la entrega tras revisar el código, pruebas y tokens.
    El Agente DevOps prepara Jenkinsfile, Dockerfile y Pull Request. Estado pasa a 'Entregado'.
    """
    try:
        return FactoryOrchestrator.approve_delivery(order_id, request)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/orders/{order_id}/export-zip")
def export_project_zip(order_id: str):
    """
    Descarga el proyecto Quarkus completo en un paquete .ZIP listo para abrir y compilar.
    """
    order = FactoryOrchestrator.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Pedido {order_id} no encontrado")

    zip_bytes = FactoryOrchestrator.export_project_zip(order_id)
    filename = f"{order.basic_data.service_name}-quarkus.zip"

    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/orders/{order_id}/publish-git", response_model=PublishQuarkusGitResponse)
def publish_order_to_git(order_id: str, request: PublishQuarkusGitRequest):
    """
    Publicación atómica a Git: Escribe el proyecto Quarkus y empuja los cambios
    a la rama remota de Git especificada, retornando las URLs de inspección y Pull Request.
    """
    try:
        result = FactoryOrchestrator.publish_order_to_git(
            order_id=order_id,
            repository_url=request.repository_url,
            branch_name=request.branch_name,
            git_token=request.git_token,
            commit_message=request.commit_message
        )
        return PublishQuarkusGitResponse(
            branchUrl=result["branchUrl"],
            commitHash=result["commitHash"],
            pullRequestUrl=result.get("pullRequestUrl"),
            branchName=result["branchName"],
            status="PUBLICADO"
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error en publicación a Git: {str(e)}")


