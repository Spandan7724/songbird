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
    
    def test_chat_with_tools(self):
        """Test that OllamaProvider.chat() works with tools parameter."""
        provider = OllamaProvider(
            base_url="http://127.0.0.1:11434", 
            model="qwen2.5-coder:7b"
        )
        
        tools = [{
            "type": "function",
            "function": {
                "name": "test_tool",
                "description": "A test tool",
                "parameters": {"type": "object", "properties": {}}
            }
        }]
        
        response = provider.chat("hi", tools=tools)
        
        assert isinstance(response, ChatResponse)
        assert response.content
        # tool_calls might be None if the model doesn't choose to call tools
        assert response.tool_calls is None or isinstance(response.tool_calls, list)
    
    def test_chat_with_messages(self):
        """Test that OllamaProvider.chat_with_messages() works with conversation history."""
        provider = OllamaProvider(
            base_url="http://127.0.0.1:11434", 
            model="qwen2.5-coder:7b"
        )
        
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there! How can I help you?"},
            {"role": "user", "content": "What's 2+2?"}
        ]
        
        response = provider.chat_with_messages(messages)
        
        assert isinstance(response, ChatResponse)
        assert response.content
        assert "4" in response.content  # Should answer the math question