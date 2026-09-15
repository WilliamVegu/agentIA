import time
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.services.llm_factory import LLMFactory, DEFAULT_MODELS, LLMProvider

router = APIRouter(prefix="/llm", tags=["LLM Provider Management"])


class LLMVerifyRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    api_key: Optional[str] = Field(None, alias="apiKey")
    provider: Optional[str] = None
    model: Optional[str] = None


class LLMVerifyResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provider: str
    model: str
    status: str  # "CONNECTED", "READY", "ERROR"
    message: str
    latency_ms: int = Field(..., alias="latencyMs")


@router.post("/verify", response_model=LLMVerifyResponse)
def verify_llm_connection(payload: LLMVerifyRequest):
    """
    Validates ephemeral LLM credentials with a lightweight ping invocation,
    measuring latency and confirming provider availability.
    """
    clean_key = (payload.api_key or "").strip()
    detected = LLMFactory.detect_provider(clean_key, payload.provider)
    model_name = payload.model or DEFAULT_MODELS.get(detected, "offline-mock")

    if LLMFactory.is_mock(clean_key, payload.provider):
        return LLMVerifyResponse(
            provider="mock",
            model="offline-mock",
            status="READY",
            message="Modo offline (Mock Engine) activo. Generación local sin costo y sin consumo de internet.",
            latencyMs=0,
        )

    t0 = time.perf_counter()
    try:
        chat_model = LLMFactory.get_chat_model(
            api_key=clean_key,
            provider=payload.provider,
            model_name=model_name,
            temperature=0.0,
        )
        if not chat_model:
            return LLMVerifyResponse(
                provider="mock",
                model="offline-mock",
                status="READY",
                message="Modo Mock activo.",
                latencyMs=0,
            )

        from langchain_core.messages import HumanMessage
        # Ultra-lightweight ping invocation
        _ = chat_model.invoke([HumanMessage(content="Reply only with the word PONG")])
        latency_ms = int((time.perf_counter() - t0) * 1000)

        provider_display = detected.upper()
        return LLMVerifyResponse(
            provider=detected,
            model=model_name,
            status="CONNECTED",
            message=f"¡Conexión verificada exitosamente con {provider_display} ({model_name})!",
            latencyMs=latency_ms,
        )
    except Exception as e:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        error_msg = str(e)

        if "API_KEY_INVALID" in error_msg or "Invalid API Key" in error_msg or "401" in error_msg:
            hint = "La API Key ingresada es inválida o expiró. Verifica que no tenga espacios adicionales."
        elif "RESOURCE_EXHAUSTED" in error_msg or "429" in error_msg:
            hint = "Límite de cuota alcanzado (Rate Limit). Espera unos segundos o prueba otra clave."
        else:
            hint = error_msg[:200]

        return LLMVerifyResponse(
            provider=detected,
            model=model_name,
            status="ERROR",
            message=f"Fallo de conexión: {hint}",
            latencyMs=latency_ms,
        )

