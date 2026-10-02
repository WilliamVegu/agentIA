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
    detected = LLMFactory.detect_provider(clean_key, payload.provider, payload.model)
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
        ping_max_tokens = 25 if detected in (LLMProvider.GROQ.value, LLMProvider.OPENAI.value, LLMProvider.DEEPSEEK.value) else None
        
        # Candidate models to try (starting with the resolved model, then known active models)
        candidate_models = [model_name]
        if detected == LLMProvider.DEEPSEEK.value:
            for alt in ["deepseek-chat", "deepseek-reasoner"]:
                if alt not in candidate_models:
                    candidate_models.append(alt)
        elif detected == LLMProvider.GEMINI.value:
            for alt in ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash"]:
                if alt not in candidate_models:
                    candidate_models.append(alt)

        last_error = None
        working_model = model_name

        from langchain_core.messages import HumanMessage

        for cand in candidate_models:
            try:
                chat_model = LLMFactory.get_chat_model(
                    api_key=clean_key,
                    provider=payload.provider,
                    model_name=cand,
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
                _ = chat_model.invoke([HumanMessage(content="Reply only with the word PONG")])
                working_model = cand
                last_error = None
                break
            except Exception as cand_err:
                last_error = cand_err
                err_str = str(cand_err)
                # If it's an API key error or rate limit, trying another model won't help
                if "API_KEY_INVALID" in err_str or "Invalid API Key" in err_str or "401" in err_str or "429" in err_str:
                    break
                # If it's a 404 model not found, loop to the next candidate model
                continue

        if last_error is not None:
            raise last_error

        latency_ms = int((time.perf_counter() - t0) * 1000)
        provider_display = detected.upper()
        return LLMVerifyResponse(
            provider=detected,
            model=working_model,
            status="CONNECTED",
            message=f"¡Conexión verificada exitosamente con {provider_display} ({working_model})!",
            latencyMs=latency_ms,
        )
    except Exception as e:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        error_msg = str(e)

        if "API_KEY_INVALID" in error_msg or "Invalid API Key" in error_msg or "401" in error_msg:
            hint = "La API Key ingresada es inválida o expiró. Verifica que no tenga espacios adicionales."
        elif "402" in error_msg or "Insufficient Balance" in error_msg or "Payment Required" in error_msg:
            hint = "Saldo insuficiente en la cuenta (HTTP 402). Por favor recarga créditos en la plataforma del proveedor."
        elif "RESOURCE_EXHAUSTED" in error_msg or "429" in error_msg:
            hint = "Límite de cuota alcanzado (Rate Limit HTTP 429). Espera unos segundos o prueba otra clave."
        elif "503" in error_msg or "high demand" in error_msg.lower():
            hint = "Servidores en alta demanda temporal (HTTP 503). Reintenta en unos instantes o cambia de modelo/proveedor."
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

