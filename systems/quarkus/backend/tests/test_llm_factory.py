import pytest
from app.services.llm_factory import (
    LLMFactory,
    LLMProvider,
    AmbiguousProviderError,
    DEEPSEEK_BASE_URL,
)
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI


@pytest.fixture(autouse=True)
def isolate_provider_env(monkeypatch):
    """Neutralize ambient provider credentials for every test in this module.

    DeepSeek keys share the ``sk-`` prefix with OpenAI, so provider detection for
    an ``sk-`` key now consults ``DEEPSEEK_API_KEY`` / ``OPENAI_API_KEY``. Without
    this fixture a developer or CI runner with those variables exported would get
    different detection results than a clean checkout — the existing heuristic
    tests would silently become environment-dependent.
    """
    for var in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    yield

def test_detect_provider_mock_keys():
    for key in ("mock-key", "test-key", "testing", "mock", "mock-custom-123", "offline-mock"):
        assert LLMFactory.detect_provider(api_key=key) == LLMProvider.MOCK.value
        assert LLMFactory.is_mock(api_key=key) is True

    assert LLMFactory.detect_provider(api_key=None) == LLMProvider.MOCK.value
    assert LLMFactory.detect_provider(api_key="") == LLMProvider.MOCK.value
    assert LLMFactory.is_mock(api_key=None) is True
    assert LLMFactory.is_mock("offline-mock", None) is True
    assert LLMFactory.is_mock("any-key", "mock") is True
    assert LLMFactory.is_mock("any-key", "offline") is True

def test_detect_provider_heuristics():
    # Gemini keys start with AIza
    assert LLMFactory.detect_provider("AIzaSyB1234567890abcdef") == LLMProvider.GEMINI.value
    assert LLMFactory.is_mock("AIzaSyB1234567890abcdef") is False

    # Groq keys start with gsk_
    assert LLMFactory.detect_provider("gsk_abcd1234efgh5678ijkl") == LLMProvider.GROQ.value
    assert LLMFactory.is_mock("gsk_abcd1234efgh5678ijkl") is False

    # OpenAI keys start with sk-
    assert LLMFactory.detect_provider("sk-proj-1234567890abcdef") == LLMProvider.OPENAI.value
    assert LLMFactory.is_mock("sk-proj-1234567890abcdef") is False

def test_detect_provider_explicit():
    assert LLMFactory.detect_provider("any-random-key", explicit_provider="gemini") == LLMProvider.GEMINI.value
    assert LLMFactory.detect_provider("any-random-key", explicit_provider="groq") == LLMProvider.GROQ.value
    assert LLMFactory.detect_provider("any-random-key", explicit_provider="openai") == LLMProvider.OPENAI.value
    assert LLMFactory.detect_provider("any-random-key", explicit_provider="mock") == LLMProvider.MOCK.value

def test_get_chat_model_mock():
    model = LLMFactory.get_chat_model("mock-key")
    assert model is None

def test_get_chat_model_gemini():
    model = LLMFactory.get_chat_model("AIzaSyDummyGeminiKey", provider="gemini")
    assert isinstance(model, ChatGoogleGenerativeAI)
    assert model.model in ("gemini-3.6-flash", "gemini-3.5-flash-lite")

    # Test AQ. prefix detection
    model_aq = LLMFactory.get_chat_model("AQ.Ab8RN6DummyKey")
    assert isinstance(model_aq, ChatGoogleGenerativeAI)
    assert model_aq.model == "gemini-3.6-flash"

def test_get_chat_model_gemini_custom():
    model = LLMFactory.get_chat_model("AIzaSyDummyGeminiKey", model_name="gemini-3.5-flash-lite")
    assert isinstance(model, ChatGoogleGenerativeAI)
    assert model.model == "gemini-3.5-flash-lite"

def test_get_chat_model_groq():
    model = LLMFactory.get_chat_model("gsk_dummyGroqKey")
    assert isinstance(model, ChatGroq)
    assert model.model_name in ("qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b")

def test_get_chat_model_groq_custom():
    model = LLMFactory.get_chat_model("gsk_dummyGroqKey", model_name="openai/gpt-oss-120b")
    assert isinstance(model, ChatGroq)
    assert model.model_name == "openai/gpt-oss-120b"

def test_get_chat_model_openai():
    model = LLMFactory.get_chat_model("sk-dummyOpenAIKey")
    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "gpt-4o-mini"

def test_deprecated_model_fallbacks():
    # Gemini decommissioned fallbacks
    assert LLMFactory.resolve_model_name("gemini", "gemini-1.5-flash") == "gemini-3.6-flash"
    assert LLMFactory.resolve_model_name("gemini", "gemini-1.5-pro") == "gemini-3.6-flash"
    assert LLMFactory.resolve_model_name("gemini", "gemini-2.0-flash") == "gemini-3.6-flash"
    assert LLMFactory.resolve_model_name("gemini", "gemini-2.0-flash-lite") == "gemini-3.5-flash-lite"
    assert LLMFactory.resolve_model_name("gemini", "gemini-2.5-flash") == "gemini-3.6-flash"

    # Groq decommissioned / unavailable fallbacks
    assert LLMFactory.resolve_model_name("groq", "llama-3.3-70b-versatile") == "qwen/qwen3.8-27b"
    assert LLMFactory.resolve_model_name("groq", "llama-3.1-8b-instant") == "qwen/qwen3.8-27b"
    assert LLMFactory.resolve_model_name("groq", "llama3-70b-8192") == "qwen/qwen3.8-27b"
    assert LLMFactory.resolve_model_name("groq", "mixtral-8x7b-32768") == "qwen/qwen3.8-27b"

    # Preserves active supported models
    assert LLMFactory.resolve_model_name("gemini", "gemini-3.6-flash") == "gemini-3.6-flash"
    assert LLMFactory.resolve_model_name("gemini", "gemini-3.5-flash-lite") == "gemini-3.5-flash-lite"
    assert LLMFactory.resolve_model_name("groq", "qwen/qwen3.8-27b") == "qwen/qwen3.8-27b"
    assert LLMFactory.resolve_model_name("groq", "openai/gpt-oss-120b") == "openai/gpt-oss-120b"



# =========================================================================
# DeepSeek provider (provider #4)
#
# DeepSeek's OpenAI-compatible base URL and model identifiers were verified
# against the official documentation rather than assumed:
#   base_url (OpenAI format): https://api.deepseek.com
#   models: deepseek-flash, deepseek-v4-pro
#   (the names deepseek-chat / deepseek-coder are NOT current)
# Temperature is documented as range 0..2 with default 1, so the factory's 0.2
# is in range.
# =========================================================================

def test_detect_provider_explicit_deepseek():
    """An explicit provider argument wins, as it does for every other provider."""
    assert LLMFactory.detect_provider("any-random-key", explicit_provider="deepseek") == LLMProvider.DEEPSEEK.value
    assert LLMFactory.detect_provider("sk-anything", explicit_provider="deepseek") == LLMProvider.DEEPSEEK.value
    assert LLMFactory.detect_provider("sk-anything", explicit_provider="DeepSeek") == LLMProvider.DEEPSEEK.value
    assert LLMFactory.detect_provider("sk-anything", explicit_provider=" deepseek ") == LLMProvider.DEEPSEEK.value
    assert LLMFactory.is_mock("sk-anything", "deepseek") is False


def test_detect_provider_deepseek_from_environment(monkeypatch):
    """DEEPSEEK_API_KEY set and OPENAI_API_KEY unset resolves the sk- ambiguity."""
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseekkey000000000000000000")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert LLMFactory.detect_provider("sk-deepseekkey000000000000000000") == LLMProvider.DEEPSEEK.value


def test_detect_provider_ambiguous_environment_raises(monkeypatch):
    """Both sk- providers configured and no explicit argument -> refuse to guess.

    The documented resolution is to RAISE rather than fall back: silently picking
    either provider would send a request to the wrong endpoint with the wrong key.
    """
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseekkey000000000000000000")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openaikey0000000000000000000")

    with pytest.raises(AmbiguousProviderError):
        LLMFactory.detect_provider("sk-ambiguous000000000000000000")

    # is_mock() routes through detect_provider, so it must surface the same error
    # rather than swallowing it and reporting a false "not mock" result.
    with pytest.raises(AmbiguousProviderError):
        LLMFactory.is_mock("sk-ambiguous000000000000000000")

    # An explicit argument always resolves the ambiguity.
    assert LLMFactory.detect_provider(
        "sk-ambiguous000000000000000000", explicit_provider="deepseek"
    ) == LLMProvider.DEEPSEEK.value
    assert LLMFactory.detect_provider(
        "sk-ambiguous000000000000000000", explicit_provider="openai"
    ) == LLMProvider.OPENAI.value


def test_detect_provider_sk_still_defaults_to_openai_without_deepseek_env():
    """No DeepSeek signal -> the pre-existing sk- behaviour is unchanged."""
    assert LLMFactory.detect_provider("sk-proj-1234567890abcdef") == LLMProvider.OPENAI.value


def test_deepseek_models_are_registered():
    """Model identifiers come from the documentation, not from guessing."""
    assert LLMFactory.get_supported_models(LLMProvider.DEEPSEEK.value) == [
        "deepseek-flash",
        "deepseek-v4-pro",
    ]
    assert LLMFactory.resolve_model_name(LLMProvider.DEEPSEEK.value) == "deepseek-flash"
    # An explicit supported model is preserved verbatim.
    assert LLMFactory.resolve_model_name(
        LLMProvider.DEEPSEEK.value, "deepseek-v4-pro"
    ) == "deepseek-v4-pro"


def test_get_chat_model_deepseek_uses_deepseek_base_url():
    """The DeepSeek client is a ChatOpenAI pointed at DeepSeek's endpoint."""
    model = LLMFactory.get_chat_model(
        "sk-deepseekkey000000000000000000", provider="deepseek"
    )
    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "deepseek-flash"

    # langchain_openai stores the base URL on `openai_api_base`. Assert that exact
    # attribute rather than an `or` chain, so a missing attribute fails the test
    # instead of silently falling through to the other name.
    assert model.openai_api_base is not None, "DeepSeek client must set a base URL"
    assert str(model.openai_api_base).rstrip("/") == DEEPSEEK_BASE_URL
    assert DEEPSEEK_BASE_URL == "https://api.deepseek.com"

    # Per-provider defaults match the other providers (DeepSeek documents a
    # temperature range of 0..2, so 0.2 is valid).
    assert model.max_retries == 2
    assert float(model.request_timeout) == 120.0
