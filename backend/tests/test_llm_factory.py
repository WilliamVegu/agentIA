import pytest
from app.services.llm_factory import LLMFactory, LLMProvider
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

def test_detect_provider_mock_keys():
    for key in ("mock-key", "test-key", "testing", "mock", "mock-custom-123"):
        assert LLMFactory.detect_provider(api_key=key) == LLMProvider.MOCK.value
        assert LLMFactory.is_mock(api_key=key) is True

    assert LLMFactory.detect_provider(api_key=None) == LLMProvider.MOCK.value
    assert LLMFactory.detect_provider(api_key="") == LLMProvider.MOCK.value
    assert LLMFactory.is_mock(api_key=None) is True

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
    assert model.model in ("gemini-3.6-flash", "gemini-2.0-flash")

    # Test AQ. prefix detection
    model_aq = LLMFactory.get_chat_model("AQ.Ab8RN6DummyKey")
    assert isinstance(model_aq, ChatGoogleGenerativeAI)
    assert model_aq.model == "gemini-3.6-flash"

def test_get_chat_model_gemini_custom():
    model = LLMFactory.get_chat_model("AIzaSyDummyGeminiKey", model_name="gemini-1.5-flash")
    assert isinstance(model, ChatGoogleGenerativeAI)
    assert model.model == "gemini-1.5-flash"

def test_get_chat_model_groq():
    model = LLMFactory.get_chat_model("gsk_dummyGroqKey")
    assert isinstance(model, ChatGroq)
    assert model.model_name in ("qwen/qwen3.8-27b", "llama-3.1-8b-instant", "llama-3.3-70b-versatile")

def test_get_chat_model_groq_custom():
    model = LLMFactory.get_chat_model("gsk_dummyGroqKey", model_name="llama-3.1-8b-instant")
    assert isinstance(model, ChatGroq)
    assert model.model_name == "llama-3.1-8b-instant"

def test_get_chat_model_openai():
    model = LLMFactory.get_chat_model("sk-dummyOpenAIKey")
    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "gpt-4o-mini"

