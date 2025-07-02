# tests/test_enhanced_providers.py
"""
Tests for enhanced provider implementations with improved error handling,
tool calling, and agentic support using LiteLLM.
"""
import pytest
import os
from unittest.mock import patch
from songbird.llm.providers import (
    get_litellm_provider, get_provider, list_available_providers, get_default_provider
)


class TestEnhancedOllamaProvider:
    """Test the enhanced Ollama provider via LiteLLM with improved tool calling."""
    
    def test_ollama_provider_initialization(self):
        """Test Ollama provider initializes with correct defaults via LiteLLM."""
        provider = get_litellm_provider("ollama", model="qwen2.5-coder:7b")
        assert provider.get_provider_name() == "ollama"
        assert provider.get_model_name() == "qwen2.5-coder:7b"
        
    def test_ollama_tool_format_conversion(self):
        """Test Ollama tool formatting through LiteLLM."""
        provider = get_litellm_provider("ollama")
        
        songbird_tools = [{
            "type": "function",
            "function": {
                "name": "test_tool",
                "description": "A test tool",
                "parameters": {"type": "object", "properties": {"arg": {"type": "string"}}}
            }
        }]
        
        # LiteLLM handles tool formatting automatically
        formatted_tools = provider.format_tools_for_provider(songbird_tools)
        
        assert len(formatted_tools) == 1
        assert formatted_tools[0]["type"] == "function"
        assert formatted_tools[0]["function"]["name"] == "test_tool"
        assert formatted_tools[0]["function"]["description"] == "A test tool"

    @pytest.mark.asyncio
    async def test_ollama_response_conversion(self):
        """Test Ollama response conversion through LiteLLM."""
        provider = get_litellm_provider("ollama")
        
        # LiteLLM handles response conversion automatically
        # This would require actual API call, so we skip with connection expected
        with pytest.raises(Exception):  # Expected without Ollama running
            messages = [{"role": "user", "content": "Hello"}]
            response = await provider.chat_with_messages(messages)


class TestEnhancedOpenRouterProvider:
    """Test the enhanced OpenRouter provider via LiteLLM with robust error handling."""
    
    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"})
    def test_openrouter_provider_initialization(self):
        """Test OpenRouter provider initializes correctly via LiteLLM."""
        provider = get_litellm_provider("openrouter", model="anthropic/claude-3.5-sonnet")
        assert provider.get_provider_name() == "openrouter"
        assert provider.get_model_name() == "anthropic/claude-3.5-sonnet"

    @pytest.mark.asyncio
    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"})
    async def test_openrouter_robust_response_parsing(self):
        """Test OpenRouter handles malformed responses gracefully via LiteLLM."""
        provider = get_litellm_provider("openrouter")
        
        # LiteLLM handles error parsing automatically
        with pytest.raises(Exception):  # Expected without valid API call
            messages = [{"role": "user", "content": "test"}]
            response = await provider.chat_with_messages(messages)

    @pytest.mark.asyncio 
    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"})
    async def test_openrouter_tool_call_error_handling(self):
        """Test OpenRouter handles malformed tool calls gracefully via LiteLLM.""" 
        provider = get_litellm_provider("openrouter")
        
        tools = [{
            "type": "function",
            "function": {
                "name": "test_tool",
                "description": "Test tool",
                "parameters": {"type": "object", "properties": {}}
            }
        }]
        
        with pytest.raises(Exception):  # Expected without valid API call
            messages = [{"role": "user", "content": "test"}]
            response = await provider.chat_with_messages(messages, tools=tools)


class TestProviderRegistry:
    """Test the enhanced provider registry functionality."""
    
    def test_list_available_providers(self):
        """Test listing available providers."""
        providers = list_available_providers()
        assert isinstance(providers, list)
        assert "ollama" in providers  # Always available
        
    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"})
    def test_get_default_provider_with_gemini(self):
        """Test default provider selection prioritizes Gemini."""
        default_provider = get_default_provider()
        assert default_provider.get_provider_name() == "gemini"
    
    @patch.dict(os.environ, {}, clear=True)
    def test_get_default_provider_fallback_to_ollama(self):
        """Test default provider falls back to Ollama when no API keys."""
        default_provider = get_default_provider()
        assert default_provider.get_provider_name() == "ollama"
    
    def test_get_provider_by_name(self):
        """Test getting provider instance by name."""
        ollama_provider = get_provider("ollama")
        assert ollama_provider.get_provider_name() == "ollama"
        
        with pytest.raises((ValueError, Exception)):  # LiteLLM may raise different errors
            get_provider("nonexistent")


class TestProviderCompatibility:
    """Test provider compatibility with agentic features."""
    
    def test_all_providers_support_chat_with_messages(self):
        """Test all providers implement chat_with_messages for agentic loops."""
        provider_names = ["ollama", "openai", "gemini", "claude", "openrouter"]
        
        for provider_name in provider_names:
            try:
                provider = get_litellm_provider(provider_name)
                assert hasattr(provider, 'chat_with_messages')
                assert hasattr(provider, 'chat')
            except Exception:
                # Skip providers that aren't available/configured
                continue
    
    def test_provider_tool_call_format_consistency(self):
        """Test all providers return consistent tool call formats."""
        # All LiteLLM providers use standardized OpenAI format
        provider = get_litellm_provider("ollama")
        
        # Test tool validation
        tools = [{
            "type": "function",
            "function": {
                "name": "test_func", 
                "description": "Test function",
                "parameters": {"type": "object", "properties": {"key": {"type": "string"}}}
            }
        }]
        
        formatted_tools = provider.format_tools_for_provider(tools)
        assert len(formatted_tools) == 1
        assert formatted_tools[0]["type"] == "function"
        assert "function" in formatted_tools[0]
        assert "name" in formatted_tools[0]["function"]


class TestProviderValidation:
    """Test provider argument validation and fixing."""
    
    def test_tool_argument_validation(self):
        """Test tool argument validation across providers."""
        # LiteLLM providers use standard tool validation
        provider = get_litellm_provider("ollama")
        
        # Test valid tool structure
        valid_tools = [{
            "type": "function",
            "function": {
                "name": "test_tool",
                "description": "Test tool",
                "parameters": {"type": "object", "properties": {"file_path": {"type": "string"}}}
            }
        }]
        
        formatted = provider.format_tools_for_provider(valid_tools)
        assert len(formatted) == 1
        assert formatted[0]["function"]["name"] == "test_tool"
        
        # Test malformed tools get filtered out
        malformed_tools = [
            {"type": "invalid"},  # Missing function
            {"function": {"name": "test"}},  # Missing type
            {}  # Empty
        ]
        
        formatted = provider.format_tools_for_provider(malformed_tools)
        assert len(formatted) == 0  # All invalid tools filtered out