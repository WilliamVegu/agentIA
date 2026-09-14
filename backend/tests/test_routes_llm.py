from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_verify_llm_mock_mode():
    payload = {"apiKey": "mock-key", "provider": "mock"}
    response = client.post("/api/v1/llm/verify", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "mock"
    assert data["status"] == "READY"
    assert data["latencyMs"] == 0
    assert "offline" in data["message"].lower()


def test_verify_llm_empty_key():
    payload = {"apiKey": ""}
    response = client.post("/api/v1/llm/verify", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "mock"
    assert data["status"] == "READY"


def test_verify_llm_connected_mocked():
    mock_chat = MagicMock()
    mock_chat.invoke.return_value = MagicMock(content="PONG")

    with patch("app.services.llm_factory.LLMFactory.get_chat_model", return_value=mock_chat):
        payload = {"apiKey": "AIzaSyFakeKeyTest12345", "provider": "gemini"}
        response = client.post("/api/v1/llm/verify", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "gemini"
        assert data["status"] == "CONNECTED"
        assert "¡Conexión verificada exitosamente" in data["message"]
        assert data["latencyMs"] >= 0


def test_verify_llm_error_handling():
    with patch("app.services.llm_factory.LLMFactory.get_chat_model", side_effect=Exception("API_KEY_INVALID: key not found")):
        payload = {"apiKey": "AIzaSyBadKey999", "provider": "gemini"}
        response = client.post("/api/v1/llm/verify", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "gemini"
        assert data["status"] == "ERROR"
        assert "inválida" in data["message"].lower()

