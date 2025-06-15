"""Tests for Ollama provider implementation."""
import pytest
from songbird.llm.providers import OllamaProvider
from songbird.llm.types import ChatResponse


class TestOllamaProvider:
    def test_chat_returns_response(self):
        """Test that OllamaProvider.chat() returns a ChatResponse."""
        # Use 127.0.0.1 instead of localhost for WSL compatibility
        provider = OllamaProvider(
            base_url="http://127.0.0.1:11434", 
            model="qwen2.5-coder:7b"
        )
        response = provider.chat("hi")
        
        assert isinstance(response, ChatResponse)
        assert response.content
        assert isinstance(response.content, str)
        assert len(response.content) > 0
        assert response.model == "qwen2.5-coder:7b"
    
    def test_nonexistent_model_error(self):
        """Test that using a nonexistent model raises ValueError."""
        provider = OllamaProvider(
            base_url="http://127.0.0.1:11434",
            model="nonexistent-model"
        )
        
        with pytest.raises(ValueError) as exc_info:
            provider.chat("test")
        
        assert "not found" in str(exc_info.value)
        assert "ollama pull" in str(exc_info.value)