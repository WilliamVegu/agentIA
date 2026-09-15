from enum import Enum
import os
from typing import Optional, Any
from langchain_core.language_models.chat_models import BaseChatModel

class LLMProvider(str, Enum):
    GEMINI = "gemini"
    GROQ = "groq"
    OPENAI = "openai"
    MOCK = "mock"

# Default models per provider (all chosen for high quality and generous/free tiers)
DEFAULT_MODELS = {
    LLMProvider.GEMINI: "gemini-3.6-flash",
    LLMProvider.GROQ: "qwen/qwen3.8-27b",
    LLMProvider.OPENAI: "gpt-4o-mini",
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
        explicit_provider: Optional[str] = None
    ) -> str:
        """
        Detects the LLM provider based on explicit choice or API key heuristic prefix.
        """
        if not api_key or not api_key.strip():
            return LLMProvider.MOCK.value

        clean_key = api_key.strip()
        if clean_key in ("mock-key", "test-key", "testing", "mock") or clean_key.startswith("mock-"):
            return LLMProvider.MOCK.value

        if explicit_provider:
            norm = explicit_provider.strip().lower()
            if norm in ("mock", "mock-mode", "offline", "testing"):
                return LLMProvider.MOCK.value
            if norm in ("gemini", "google", "google-gemini"):
                return LLMProvider.GEMINI.value
            if norm in ("groq", "groq-cloud"):
                return LLMProvider.GROQ.value
            if norm in ("openai", "chatgpt"):
                return LLMProvider.OPENAI.value

        # Heuristic detection based on provider-specific API key formats
        # Google AI Studio keys start with 'AIza' or 'AQ.'
        if clean_key.startswith("AIza") or clean_key.startswith("AQ."):
            return LLMProvider.GEMINI.value
        if clean_key.startswith("gsk_"):
            return LLMProvider.GROQ.value
        if clean_key.startswith("sk-") and not clean_key.startswith("gsk_"):
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
    def get_chat_model(
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.2,
    ) -> Optional[BaseChatModel]:
        """
        Instantiates and returns the configured LangChain chat model.
        Returns None if mock mode is triggered.
        """
        detected_provider = LLMFactory.detect_provider(api_key, provider)

        if detected_provider == LLMProvider.MOCK.value:
            return None

        clean_key = (api_key or "").strip()

        if detected_provider == LLMProvider.GEMINI.value:
            from langchain_google_genai import ChatGoogleGenerativeAI
            selected_model = model_name or DEFAULT_MODELS[LLMProvider.GEMINI]
            resolved_key = clean_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            return ChatGoogleGenerativeAI(
                model=selected_model,
                google_api_key=resolved_key,
                temperature=temperature,
                max_retries=2,
                timeout=120.0,
            )

        if detected_provider == LLMProvider.GROQ.value:
            from langchain_groq import ChatGroq
            selected_model = model_name or DEFAULT_MODELS[LLMProvider.GROQ]
            resolved_key = clean_key or os.environ.get("GROQ_API_KEY")
            return ChatGroq(
                model=selected_model,
                groq_api_key=resolved_key,
                temperature=temperature,
                max_retries=2,
                request_timeout=120.0,
            )

        if detected_provider == LLMProvider.OPENAI.value:
            from langchain_openai import ChatOpenAI
            selected_model = model_name or DEFAULT_MODELS[LLMProvider.OPENAI]
            resolved_key = clean_key or os.environ.get("OPENAI_API_KEY")
            return ChatOpenAI(
                model=selected_model,
                api_key=resolved_key,
                temperature=temperature,
                max_retries=2,
                timeout=120.0,
            )

        raise ValueError(f"Unsupported LLM provider: {detected_provider}")
