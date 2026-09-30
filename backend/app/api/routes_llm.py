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


class LLMConfigResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    default_provider: str = Field(..., alias="defaultProvider")
    default_model: str = Field(..., alias="defaultModel")
    has_configured_key: bool = Field(..., alias="hasConfiguredKey")
    configured_providers: list[str] = Field(..., alias="configuredProviders")


@router.get("/config", response_model=LLMConfigResponse)
def get_llm_config():
    """Returns detected active provider/model based on server environment settings."""
    import os
    from app.config import settings
    configured = []
    if getattr(settings, "DEEPSEEK_API_KEY", None) or os.environ.get("DEEPSEEK_API_KEY"):
        configured.append("deepseek")
    if getattr(settings, "GEMINI_API_KEY", None) or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        configured.append("gemini")
    if getattr(settings, "GROQ_API_KEY", None) or os.environ.get("GROQ_API_KEY"):
        configured.append("groq")
    if getattr(settings, "OPENAI_API_KEY", None) or os.environ.get("OPENAI_API_KEY"):
        configured.append("openai")

    default_prov = configured[0] if configured else "mock"
    default_mod = DEFAULT_MODELS.get(default_prov, "offline-mock")

    return LLMConfigResponse(
        defaultProvider=default_prov,
        defaultModel=default_mod,
        hasConfiguredKey=len(configured) > 0,
        configuredProviders=configured,
    )


@router.post("/verify", response_model=LLMVerifyResponse)
def verify_llm_connection(payload: LLMVerifyRequest):
    """
    Validates ephemeral LLM credentials with a lightweight ping invocation,
    measuring latency and confirming provider availability.
    """
    import os
    from app.config import settings

    clean_key = (payload.api_key or "").strip()
    if not clean_key and payload.provider and payload.provider != "mock":
        target_prov = payload.provider.lower()
        if target_prov == "deepseek":
            clean_key = getattr(settings, "DEEPSEEK_API_KEY", None) or os.environ.get("DEEPSEEK_API_KEY") or ""
        elif target_prov == "gemini":
            clean_key = getattr(settings, "GEMINI_API_KEY", None) or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
        elif target_prov == "groq":
            clean_key = getattr(settings, "GROQ_API_KEY", None) or os.environ.get("GROQ_API_KEY") or ""
        elif target_prov == "openai":
            clean_key = getattr(settings, "OPENAI_API_KEY", None) or os.environ.get("OPENAI_API_KEY") or ""

    detected = LLMFactory.detect_provider(clean_key, payload.provider)
    model_name = LLMFactory.resolve_model_name(detected, payload.model)

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
        ping_max_tokens = 25 if detected in (LLMProvider.GROQ.value, LLMProvider.OPENAI.value) else None
        chat_model = LLMFactory.get_chat_model(
            api_key=clean_key,
            provider=payload.provider,
            model_name=model_name,
            temperature=0.0,
            max_tokens=ping_max_tokens,
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
        elif "CERTIFICATE_VERIFY_FAILED" in error_msg or "SSLCertVerificationError" in error_msg:
            hint = "Error de validación SSL con el proxy o firewall corporativo."
        else:
            hint = error_msg[:200]

        return LLMVerifyResponse(
            provider=detected,
            model=model_name,
            status="ERROR",
            message=f"Fallo de conexión: {hint}",
            latencyMs=latency_ms,
        )

