from enum import Enum
import os
from typing import Optional, Any
from langchain_core.language_models.chat_models import BaseChatModel

class LLMProvider(str, Enum):
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    GROQ = "groq"
    OPENAI = "openai"
    MOCK = "mock"

# Default models per provider (all verified active tiers)
DEFAULT_MODELS = {
    LLMProvider.GEMINI: "gemini-3.5-flash-lite",
    LLMProvider.DEEPSEEK: "deepseek-chat",
    LLMProvider.GROQ: "llama-3.3-70b-versatile",
    LLMProvider.OPENAI: "gpt-4o-mini",
}

# Verified active models per provider
SUPPORTED_MODELS = {
    LLMProvider.GEMINI: [
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
        "gemini-3.8-flash",
    ],
    LLMProvider.DEEPSEEK: [
        "deepseek-chat",
        "deepseek-reasoner",
    ],
    LLMProvider.GROQ: [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
        "gemma2-9b-it",
    ],
    LLMProvider.OPENAI: [
        "gpt-4o-mini",
        "gpt-4o",
    ],
    LLMProvider.MOCK: [
        "offline-mock",
    ],
}

# Resilient fallback mapping for deprecated models
DEPRECATED_MODEL_FALLBACKS = {
    # DeepSeek aliases
    "deepseek-v3": "deepseek-chat",
    "deepseek-r1": "deepseek-reasoner",
    # Gemini retired models -> active current models
    "gemini-1.5-flash": "gemini-3.5-flash-lite",
    "gemini-2.5-flash": "gemini-3.5-flash-lite",
    "gemini-2.5-flash-lite": "gemini-3.5-flash-lite",
    "gemini-2.0-flash": "gemini-3.5-flash-lite",
    "gemini-1.5-pro": "gemini-3.5-flash",
    "gemini-1.0-pro": "gemini-3.5-flash-lite",
    "gemini-3.6-flash": "gemini-3.5-flash-lite",
    # Groq legacy model fallbacks
    "llama3-70b-8192": "llama-3.3-70b-versatile",
    "llama3-8b-8192": "llama-3.1-8b-instant",
    "qwen/qwen3.8-27b": "llama-3.3-70b-versatile",
}

class LLMFactory:
    """
    Unified Multi-Provider LLM Factory.
    Enables seamless operation with 100% free-tier providers (Google Gemini & Groq),
    OpenAI, and offline Mock mode.
    """

    @staticmethod
    def detect_provider(
        api_key: Optional[str] = None,
        explicit_provider: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> str:
        """
        Detects the LLM provider based on explicit choice, model name, or API key heuristic prefix.
        """
        if explicit_provider:
            norm = explicit_provider.strip().lower()
            if norm in ("mock", "mock-mode", "offline", "offline-mock", "testing") or "mock" in norm:
                return LLMProvider.MOCK.value
            if norm in ("deepseek", "deep-seek", "deepseek-ai"):
                return LLMProvider.DEEPSEEK.value
            if norm in ("gemini", "google", "google-gemini"):
                return LLMProvider.GEMINI.value
            if norm in ("groq", "groq-cloud"):
                return LLMProvider.GROQ.value
            if norm in ("openai", "chatgpt"):
                return LLMProvider.OPENAI.value

        if model_name:
            norm_m = model_name.strip().lower()
            if "deepseek" in norm_m:
                return LLMProvider.DEEPSEEK.value
            if "gemini" in norm_m:
                return LLMProvider.GEMINI.value
            if "llama" in norm_m or "mixtral" in norm_m or "gemma" in norm_m:
                return LLMProvider.GROQ.value
            if "gpt-" in norm_m:
                return LLMProvider.OPENAI.value

        if not api_key or not api_key.strip():
            return LLMProvider.MOCK.value

        clean_key = api_key.strip()
        if (
            clean_key in ("mock-key", "test-key", "testing", "mock", "offline-mock")
            or clean_key.startswith("mock-")
            or clean_key.startswith("offline-")
            or "mock" in clean_key.lower()
        ):
            return LLMProvider.MOCK.value

        # Heuristic detection based on provider-specific API key formats
        # Google AI Studio keys start with 'AIza' or 'AQ.'
        if clean_key.startswith("AIza") or clean_key.startswith("AQ."):
            return LLMProvider.GEMINI.value
        if clean_key.startswith("gsk_"):
            return LLMProvider.GROQ.value
        if clean_key.startswith("sk-") and not clean_key.startswith("gsk_"):
            # Check if explicit or environment hints deepseek
            if os.environ.get("DEEPSEEK_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
                return LLMProvider.DEEPSEEK.value
            return LLMProvider.OPENAI.value

        # Check environment variables fallback
        if os.environ.get("DEEPSEEK_API_KEY"):
            return LLMProvider.DEEPSEEK.value
        if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
            return LLMProvider.GEMINI.value
        if os.environ.get("GROQ_API_KEY"):
            return LLMProvider.GROQ.value

        return LLMProvider.OPENAI.value

    @staticmethod
    def is_mock(api_key: Optional[str] = None, explicit_provider: Optional[str] = None) -> bool:
        """Returns True if the request should use offline mock generation."""
        return LLMFactory.detect_provider(api_key, explicit_provider) == LLMProvider.MOCK.value

    @staticmethod
    def resolve_model_name(
        provider: str,
        model_name: Optional[str] = None
    ) -> str:
        """
        Resolves model name, mapping deprecated/decommissioned models to active supported models.
        """
        clean_model = (model_name or "").strip()
        if not clean_model:
            return DEFAULT_MODELS.get(provider, "default")

        # Automatically translate legacy/decommissioned model requests
        if clean_model in DEPRECATED_MODEL_FALLBACKS:
            return DEPRECATED_MODEL_FALLBACKS[clean_model]

        return clean_model

    @staticmethod
    def get_supported_models(provider: str) -> list[str]:
        """Returns the list of verified supported models for the provider."""
        return SUPPORTED_MODELS.get(provider, [])

    @staticmethod
    def get_chat_model(
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> Optional[BaseChatModel]:
        """
        Instantiates and returns the configured LangChain chat model.
        Returns None if mock mode is triggered.
        """
        detected_provider = LLMFactory.detect_provider(api_key, provider)

        if detected_provider == LLMProvider.MOCK.value:
            return None

        clean_key = (api_key or "").strip()
        resolved_model = LLMFactory.resolve_model_name(detected_provider, model_name)

        if detected_provider == LLMProvider.GEMINI.value:
            from langchain_google_genai import ChatGoogleGenerativeAI
            resolved_key = clean_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            return ChatGoogleGenerativeAI(
                model=resolved_model,
                google_api_key=resolved_key,
                temperature=temperature,
                max_retries=2,
                timeout=120.0,
            )

        if detected_provider == LLMProvider.GROQ.value:
            from langchain_groq import ChatGroq
            resolved_key = clean_key or os.environ.get("GROQ_API_KEY")
            kwargs: dict[str, Any] = {
                "model": resolved_model,
                "groq_api_key": resolved_key,
                "temperature": temperature,
                "max_retries": 2,
                "request_timeout": 120.0,
            }
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens
            return ChatGroq(**kwargs)

        if detected_provider == LLMProvider.DEEPSEEK.value:
            from langchain_openai import ChatOpenAI
            resolved_key = clean_key or os.environ.get("DEEPSEEK_API_KEY")
            kwargs_ds: dict[str, Any] = {
                "model": resolved_model or "deepseek-chat",
                "api_key": resolved_key,
                "base_url": "https://api.deepseek.com",
                "temperature": temperature,
                "max_retries": 2,
                "timeout": 120.0,
            }
            if max_tokens is not None:
                kwargs_ds["max_tokens"] = max_tokens
            return ChatOpenAI(**kwargs_ds)

        if detected_provider == LLMProvider.OPENAI.value:
            from langchain_openai import ChatOpenAI
            resolved_key = clean_key or os.environ.get("OPENAI_API_KEY")
            kwargs_oa: dict[str, Any] = {
                "model": resolved_model,
                "api_key": resolved_key,
                "temperature": temperature,
                "max_retries": 2,
                "timeout": 120.0,
            }
            if max_tokens is not None:
                kwargs_oa["max_tokens"] = max_tokens
            return ChatOpenAI(**kwargs_oa)

        raise ValueError(f"Unsupported LLM provider: {detected_provider}")

    @staticmethod
    def call_gemini_direct(
        prompt: str,
        system_prompt: str = "",
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        response_mime_type: Optional[str] = None
    ) -> str:
        """
        Invoca la API de Google Gemini directamente vía REST HTTPS de alta velocidad.
        No bloquea hilos de gRPC y mapea los errores detalladamente (400, 401, 403, 404, 429, 503).
        """
        import json
        import urllib.request
        import urllib.error

        resolved_key = (api_key or "").strip() or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not resolved_key:
            raise ValueError("No se proporcionó API Key de Google Gemini ni está configurada en las variables de entorno.")

        # Orden de modelos resilientes y ultra-rápidos
        preferred = model_name if model_name else "gemini-3.5-flash-lite"
        candidates = [preferred, "gemini-3.5-flash"]
        seen = set()
        models_to_try = [m for m in candidates if m and not (m in seen or seen.add(m))]

        last_error = None
        for model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={resolved_key}"

            parts = []
            if system_prompt:
                parts.append({"text": f"INSTRUCCIÓN DEL SISTEMA:\n{system_prompt}\n\n"})
            parts.append({"text": prompt})

            generation_config = {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
            if response_mime_type:
                generation_config["responseMimeType"] = response_mime_type

            payload = {
                "contents": [{"parts": parts}],
                "generationConfig": generation_config
            }

            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

            try:
                with urllib.request.urlopen(req, timeout=90) as resp:
                    body = resp.read().decode("utf-8")
                    parsed = json.loads(body)
                    candidates_resp = parsed.get("candidates", [])
                    if candidates_resp and "content" in candidates_resp[0]:
                        return candidates_resp[0]["content"]["parts"][0]["text"]
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8")
                try:
                    msg = json.loads(err_body)["error"]["message"]
                except Exception:
                    msg = err_body

                if e.code == 429:
                    raise RuntimeError(f"⚠️ Cuota de Gemini excedida (Rate Limit HTTP 429): {msg}. Por favor espera 60 segundos antes de reintentar.")
                elif e.code in (401, 403):
                    raise RuntimeError(f"⚠️ API Key de Gemini inválida o no autorizada (HTTP {e.code}): {msg}")
                elif e.code == 404:
                    last_error = f"Modelo Gemini '{model}' no disponible (HTTP 404): {msg}"
                    continue
                elif e.code == 503:
                    last_error = f"Modelo Gemini '{model}' en alta demanda temporal (HTTP 503): {msg}"
                    continue
                else:
                    raise RuntimeError(f"Google Gemini Error HTTP {e.code}: {msg}")
            except (TimeoutError, urllib.error.URLError) as e:
                err_str = str(e).lower()
                if "timed out" in err_str or "timeout" in err_str:
                    raise RuntimeError(
                        f"⏱️ Tiempo de espera agotado con Google Gemini ({model} timeout tras 90s): "
                        "El modelo tardó más de 90 segundos en responder. Se han ajustado los parámetros de generación; por favor reintenta en unos instantes."
                    )
                last_error = f"Error de red/conexión con Gemini en modelo '{model}': {str(e)}"
                continue
            except Exception as e:
                err_str = str(e).lower()
                if "timed out" in err_str or "timeout" in err_str:
                    raise RuntimeError(
                        f"⏱️ Tiempo de espera agotado con Google Gemini ({model} timeout tras 90s): "
                        "El modelo tardó más de 90 segundos en responder. Se han ajustado los parámetros de generación; por favor reintenta en unos instantes."
                    )
                last_error = f"Error de conexión con Gemini en modelo '{model}': {str(e)}"
                continue

        raise RuntimeError(last_error or "No se pudo obtener respuesta de Google Gemini.")

    @staticmethod
    def call_deepseek_direct(
        prompt: str,
        system_prompt: str = "",
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        response_mime_type: Optional[str] = None
    ) -> str:
        """
        Invoca la API de DeepSeek vía REST HTTPS de alta velocidad.
        Soporta deepseek-chat (DeepSeek-V3) y deepseek-reasoner (DeepSeek-R1).
        Mapea errores HTTP (401, 402, 429, 503, timeouts).
        """
        import json
        import urllib.request
        import urllib.error

        resolved_key = (api_key or "").strip() or os.environ.get("DEEPSEEK_API_KEY")
        if not resolved_key:
            raise ValueError("No se proporcionó API Key de DeepSeek ni está configurada en la variable DEEPSEEK_API_KEY.")

        model = (model_name or "deepseek-chat").strip()
        if model in DEPRECATED_MODEL_FALLBACKS:
            model = DEPRECATED_MODEL_FALLBACKS[model]

        url = "https://api.deepseek.com/chat/completions"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False
        }

        # deepseek-reasoner (R1) no admite temperature ni response_format json_object
        if model != "deepseek-reasoner":
            payload["temperature"] = temperature
            payload["max_tokens"] = max_tokens
            if response_mime_type == "application/json":
                payload["response_format"] = {"type": "json_object"}
        else:
            payload["max_tokens"] = max_tokens

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {resolved_key}"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                body = resp.read().decode("utf-8")
                parsed = json.loads(body)
                choices = parsed.get("choices", [])
                if choices and "message" in choices[0]:
                    msg = choices[0]["message"]
                    content = msg.get("content", "")
                    if not content and "reasoning_content" in msg:
                        content = msg.get("reasoning_content", "")
                    return content
                raise RuntimeError("Respuesta de DeepSeek vacía o sin contenido en choices.")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            try:
                err_json = json.loads(err_body)
                msg = err_json.get("error", {}).get("message", err_body)
            except Exception:
                msg = err_body

            if e.code == 401:
                raise RuntimeError(f"⚠️ API Key de DeepSeek inválida o no autorizada (HTTP 401): {msg}")
            elif e.code == 402:
                raise RuntimeError(f"⚠️ Saldo insuficiente en la cuenta de DeepSeek (HTTP 402 Payment Required): {msg}. Por favor recarga créditos en platform.deepseek.com.")
            elif e.code == 429:
                raise RuntimeError(f"⚠️ Cuota o límite de tasa de DeepSeek excedido (Rate Limit HTTP 429): {msg}. Por favor espera unos momentos antes de reintentar.")
            elif e.code == 503:
                raise RuntimeError(f"⚠️ Servidores de DeepSeek temporalmente sobrecargados (HTTP 503): {msg}. Por favor reintenta en unos instantes.")
            else:
                raise RuntimeError(f"DeepSeek Error HTTP {e.code}: {msg}")
        except (TimeoutError, urllib.error.URLError) as e:
            err_str = str(e).lower()
            if "timed out" in err_str or "timeout" in err_str:
                raise RuntimeError(
                    f"⏱️ Tiempo de espera agotado con DeepSeek ({model} timeout tras 90s): "
                    "El modelo tardó más de 90 segundos en responder. Por favor reintenta en unos instantes."
                )
            raise RuntimeError(f"Error de red/conexión con DeepSeek en modelo '{model}': {str(e)}")
        except Exception as e:
            err_str = str(e).lower()
            if "timed out" in err_str or "timeout" in err_str:
                raise RuntimeError(
                    f"⏱️ Tiempo de espera agotado con DeepSeek ({model} timeout tras 90s): "
                    "El modelo tardó más de 90 segundos en responder. Por favor reintenta en unos instantes."
                )
            raise RuntimeError(f"Error inesperado al invocar DeepSeek ({model}): {str(e)}")

    @staticmethod
    def call_chat(
        prompt: str,
        system_prompt: str = "",
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        response_mime_type: Optional[str] = None
    ) -> str:
        """
        Punto de entrada unificado y de alta velocidad para invocación directa de LLMs.
        Enruta automáticamente a Gemini o DeepSeek según el proveedor detectado.
        """
        detected = LLMFactory.detect_provider(api_key=api_key, explicit_provider=provider, model_name=model_name)

        if detected == LLMProvider.DEEPSEEK.value:
            return LLMFactory.call_deepseek_direct(
                prompt=prompt,
                system_prompt=system_prompt,
                api_key=api_key,
                model_name=model_name or "deepseek-chat",
                temperature=temperature,
                max_tokens=max_tokens,
                response_mime_type=response_mime_type
            )
        elif detected == LLMProvider.GEMINI.value or (api_key and (api_key.startswith("AIza") or api_key.startswith("AQ."))):
            return LLMFactory.call_gemini_direct(
                prompt=prompt,
                system_prompt=system_prompt,
                api_key=api_key,
                model_name=model_name or "gemini-3.5-flash-lite",
                temperature=temperature,
                max_tokens=max_tokens,
                response_mime_type=response_mime_type
            )
        else:
            # Si hay DEEPSEEK_API_KEY en variables de entorno, preferir DeepSeek
            if os.environ.get("DEEPSEEK_API_KEY") and not os.environ.get("GEMINI_API_KEY"):
                return LLMFactory.call_deepseek_direct(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    api_key=api_key,
                    model_name=model_name or "deepseek-chat",
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_mime_type=response_mime_type
                )
            return LLMFactory.call_gemini_direct(
                prompt=prompt,
                system_prompt=system_prompt,
                api_key=api_key,
                model_name=model_name or "gemini-3.5-flash-lite",
                temperature=temperature,
                max_tokens=max_tokens,
                response_mime_type=response_mime_type
            )

