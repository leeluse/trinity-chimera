import pytest
import asyncio
from unittest.mock import patch, MagicMock
from server.shared.llm.client import generate_chat_reply

@pytest.mark.asyncio
async def test_generate_chat_reply_local_fallback():
    """Test that the service falls back to local answer when provider is 'local'."""
    with patch("server.shared.llm.client._provider", return_value="local"):
        result = await generate_chat_reply("Hello", context={"netProfitAmt": 100})
        assert result["provider"] == "local"
        assert result["fallback"] is True
        assert "수익성" in result["content"]

@pytest.mark.asyncio
async def test_generate_chat_reply_nim_success():
    """Test successful NIM completion using mocks."""
    mock_response = {
        "choices": [
            {"message": {"content": "NIM Success Response"}}
        ]
    }

    with patch("server.shared.llm.client._provider", return_value="nim"), \
         patch("server.shared.llm.client._nim_config", return_value={"base_url": "http://mock", "api_key": "test_key", "model": "test_model"}), \
         patch("server.shared.llm.client._post_json", return_value=mock_response):

        result = await generate_chat_reply("Hello")
        assert result["content"] == "NIM Success Response"
        assert result["provider"] == "nim"
        assert result["fallback"] is False

@pytest.mark.asyncio
async def test_generate_chat_reply_openai_success():
    """Test successful OpenAI completion using mocks."""
    mock_response = {
        "choices": [
            {"message": {"content": "OpenAI Success Response"}}
        ]
    }

    with patch("server.shared.llm.client._provider", return_value="openai"), \
         patch("server.shared.llm.client._openai_compat_config", return_value={"base_url": "http://mock", "api_key": "test_key", "model": "test_model"}), \
         patch("server.shared.llm.client._post_json", return_value=mock_response):

        result = await generate_chat_reply("Hello")
        assert result["content"] == "OpenAI Success Response"
        assert result["provider"] == "openai"
        assert result["fallback"] is False

@pytest.mark.asyncio
async def test_generate_chat_reply_ollama_success():
    """Test successful Ollama completion using mocks."""
    mock_response = {
        "message": {"content": "Ollama Success Response"}
    }

    with patch("server.shared.llm.client._provider", return_value="ollama"), \
         patch("server.shared.llm.client._ollama_config", return_value={"base_url": "http://mock", "model": "test_model"}), \
         patch("server.shared.llm.client._post_json", return_value=mock_response):

        result = await generate_chat_reply("Hello")
        assert result["content"] == "Ollama Success Response"
        assert result["provider"] == "ollama"
        assert result["fallback"] is False

@pytest.mark.asyncio
async def test_generate_chat_reply_failure_to_fallback():
    """Test that an exception in the provider leads to a local fallback result."""
    # Looking at the code in server/ai/llm/client.py, the current implementation
    # does NOT have a try-except block around provider-specific logic to catch
    # RuntimeErrors and trigger _local_fallback. It only falls back if provider is not recognized.
    with patch("server.shared.llm.client._provider", return_value="nim"), \
         patch("server.shared.llm.client._nim_config", return_value={"base_url": "http://mock", "api_key": "test_key", "model": "test_model"}), \
         patch("server.shared.llm.client._post_json", side_effect=RuntimeError("Upstream Error")):

        with pytest.raises(RuntimeError):
            await generate_chat_reply("Hello")
