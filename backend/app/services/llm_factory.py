from enum import Enum
import os
from typing import Optional, Any
from langchain_core.language_models.chat_models import BaseChatModel

class LLMProvider(str, Enum):
    GEMINI = "gemini"
    GROQ = "groq"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    MOCK = "mock"


class AmbiguousProviderError(ValueError):
    """Raised when a key could belong to more than one provider and no explicit
    provider was supplied.

    Raised instead of guessing: DeepSeek and OpenAI API keys share the ``sk-``
    prefix, and silently choosing either one would send the request to the wrong
    endpoint with the wrong credential.
    """


# DeepSeek speaks the OpenAI wire format, so it is served by ChatOpenAI with a
# custom base URL. Verified against the official documentation rather than
# assumed: https://api-docs.deepseek.com/ lists the OpenAI-format base URL as
# https://api.deepseek.com (the Anthropic format uses /anthropic).
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# Default models per provider (all chosen for high quality and verified active tiers)
DEFAULT_MODELS = {
    LLMProvider.GEMINI: "gemini-3.6-flash",
    LLMProvider.GROQ: "qwen/qwen3.8-27b",
    LLMProvider.OPENAI: "gpt-4o-mini",
    LLMProvider.DEEPSEEK: "deepseek-flash",
}

# Verified active models per provider
SUPPORTED_MODELS = {
    LLMProvider.GEMINI: [
        "gemini-3.6-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.8-flash",
    ],
    LLMProvider.GROQ: [
        "qwen/qwen3.8-27b",
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
        "groq/compound",
    ],
    LLMProvider.OPENAI: [
        "gpt-4o-mini",
        "gpt-4o",
    ],
    # Verified against https://api-docs.deepseek.com/quick_start/pricing.
    # NOTE: deepseek-chat / deepseek-coder are NOT current model names. They are
    # deliberately absent from both this list and the legacy fallback map: the
    # documentation does not state that they are accepted, so mapping them would
    # be guessing at their successors.
    LLMProvider.DEEPSEEK: [
        "deepseek-flash",
        "deepseek-v4-pro",
    ],
    LLMProvider.MOCK: [
        "offline-mock",
    ],
}

# Resilient fallback mapping for deprecated or decommissioned models
DEPRECATED_MODEL_FALLBACKS = {
    # Gemini decommissioned models -> active models
    "gemini-1.0-pro": "gemini-3.6-flash",
    "gemini-1.5-flash": "gemini-3.6-flash",
    "gemini-1.5-pro": "gemini-3.6-flash",
    "gemini-2.0-flash": "gemini-3.6-flash",
    "gemini-2.0-flash-lite": "gemini-3.5-flash-lite",
    "gemini-2.5-flash": "gemini-3.6-flash",
    "gemini-2.5-pro": "gemini-3.6-flash",
    # Groq decommissioned / unavailable models -> active models
    "llama-3.3-70b-versatile": "qwen/qwen3.8-27b",
    "llama-3.1-8b-instant": "qwen/qwen3.8-27b",
    "llama3-70b-8192": "qwen/qwen3.8-27b",
    "llama3-8b-8192": "qwen/qwen3.8-27b",
    "mixtral-8x7b-32768": "qwen/qwen3.8-27b",
    "gemma2-9b-it": "qwen/qwen3.8-27b",
    "qwen-2.5-32b": "qwen/qwen3.8-27b",
    "deepseek-r1-distill-llama-70b": "qwen/qwen3.8-27b",
    # DeepSeek retired names -> current model. The documentation states these
    # two legacy names are still accepted but their models are retired and served
    # by DeepSeek-V4.1-Flash. Only names the documentation explicitly accepts are
    # listed: mapping other historical names would be guesswork about successors.
    "deepseek-v4-flash": "deepseek-flash",
    "deepseek-v4-flash-vision-exp": "deepseek-flash",
}


def _has_shared_sk_prefix(clean_key: str) -> bool:
    """True when the key uses the ``sk-`` prefix that OpenAI and DeepSeek share.

    The ``gsk_`` exclusion is unnecessary at the single call site (which sits
    after the ``gsk_`` early return) but is kept as a guard so the predicate is
    correct in isolation rather than only in its current position.
    """
    return clean_key.startswith("sk-") and not clean_key.startswith("gsk_")


class LLMFactory:
    """
    Unified Multi-Provider LLM Factory.
    Enables seamless operation with 100% free-tier providers (Google Gemini & Groq),
    OpenAI, DeepSeek, and offline Mock mode.

    DeepSeek is served through the OpenAI-compatible client with a DeepSeek base
    URL. Note when tuning sampling: DeepSeek enables thinking mode by default and
    documents that ``temperature`` has no effect in that mode (range 0..2,
    default 1). The value here therefore only takes effect if thinking mode is
    disabled via the request body.
    """

    @staticmethod
    def detect_provider(
        api_key: Optional[str] = None,
        explicit_provider: Optional[str] = None
    ) -> str:
        """
        Detects the LLM provider based on explicit choice or API key heuristic prefix.

        :raises AmbiguousProviderError: when the key uses the ``sk-`` prefix shared
            by OpenAI and DeepSeek, both ``DEEPSEEK_API_KEY`` and ``OPENAI_API_KEY``
            are set, and no explicit provider was supplied. Callers reachable from
            an HTTP route should map this to a 4xx with the message intact rather
            than letting a generic handler turn it into a 500.
        """
        if explicit_provider:
            norm = explicit_provider.strip().lower()
            if norm in ("mock", "mock-mode", "offline", "offline-mock", "testing") or "mock" in norm:
                return LLMProvider.MOCK.value

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

        if explicit_provider:
            norm = explicit_provider.strip().lower()
            if norm in ("gemini", "google", "google-gemini"):
                return LLMProvider.GEMINI.value
            if norm in ("groq", "groq-cloud"):
                return LLMProvider.GROQ.value
            if norm in ("openai", "chatgpt"):
                return LLMProvider.OPENAI.value
            if norm in ("deepseek", "deep-seek", "deepseek-ai"):
                return LLMProvider.DEEPSEEK.value

        # Heuristic detection based on provider-specific API key formats
        # Google AI Studio keys start with 'AIza' or 'AQ.'
        if clean_key.startswith("AIza") or clean_key.startswith("AQ."):
            return LLMProvider.GEMINI.value
        if clean_key.startswith("gsk_"):
            return LLMProvider.GROQ.value

        # --- DeepSeek / OpenAI disambiguation ---------------------------------
        # "sk-" is shared by both providers, so the prefix alone cannot decide.
        # Explicit selection already won above. What is left is resolved from the
        # environment, and when the environment is itself ambiguous we refuse to
        # guess rather than silently sending the key to the wrong endpoint.
        #
        # The environment resolution is deliberately gated on the ambiguous "sk-"
        # prefix. Applying it unconditionally would hijack the unambiguous
        # AIza/AQ. and gsk_ key formats whenever DEEPSEEK_API_KEY happened to be
        # exported, changing behaviour for providers this change must not touch.
        if _has_shared_sk_prefix(clean_key):
            deepseek_env = os.environ.get("DEEPSEEK_API_KEY")
            openai_env = os.environ.get("OPENAI_API_KEY")
            if deepseek_env and openai_env:
                raise AmbiguousProviderError(
                    "Both DEEPSEEK_API_KEY and OPENAI_API_KEY are set and the API key "
                    "starts with 'sk-', which DeepSeek and OpenAI share. Pass an explicit "
                    "provider ('deepseek' or 'openai') to resolve it; refusing to guess "
                    "because a wrong choice would send the key to the wrong endpoint."
                )
            if deepseek_env and not openai_env:
                return LLMProvider.DEEPSEEK.value
            return LLMProvider.OPENAI.value

        # Check environment variables fallback
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

        if detected_provider == LLMProvider.DEEPSEEK.value:
            # DeepSeek exposes an OpenAI-compatible API, so the same client is
            # reused with a DeepSeek base URL rather than adding a new dependency.
            from langchain_openai import ChatOpenAI
            resolved_key = clean_key or os.environ.get("DEEPSEEK_API_KEY")
            kwargs_ds: dict[str, Any] = {
                "model": resolved_model,
                "api_key": resolved_key,
                "base_url": DEEPSEEK_BASE_URL,
                "temperature": temperature,
                "max_retries": 2,
                "timeout": 120.0,
            }
            if max_tokens is not None:
                # Documented range is 1..393216 (384K); the parameter is omitted
                # entirely when unset so DeepSeek applies its own default rather
                # than the factory inventing one.
                kwargs_ds["max_tokens"] = max_tokens
            return ChatOpenAI(**kwargs_ds)

        raise ValueError(f"Unsupported LLM provider: {detected_provider}")
