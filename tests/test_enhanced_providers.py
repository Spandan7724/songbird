# tests/test_enhanced_providers.py
"""
Tests for enhanced provider implementations with improved error handling,
tool calling, and agentic support.
"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from songbird.llm.providers import (
    OllamaProvider, GeminiProvider, OpenRouterProvider,
    get_provider, list_available_providers, get_default_provider
)
from songbird.llm.types import ChatResponse


class TestEnhancedOllamaProvider:
    """Test the enhanced Ollama provider with improved tool calling."""
    
    def test_ollama_provider_initialization(self):
        """Test Ollama provider initializes with correct defaults."""
        provider = OllamaProvider()
        assert provider.model == "qwen2.5-coder:7b"  # Updated default
        assert provider.base_url == "http://localhost:11434"
        
    def test_ollama_tool_format_conversion(self):
        """Test Ollama converts tool schemas correctly."""
        provider = OllamaProvider()
        
        songbird_tools = [{
            "type": "function",
            "function": {
                "name": "test_tool",
                "description": "A test tool",
                "parameters": {"type": "object", "properties": {"arg": {"type": "string"}}}
            }
        }]
        
        ollama_tools = provider._convert_tools_to_ollama_format(songbird_tools)
        
        assert len(ollama_tools) == 1
        assert ollama_tools[0]["type"] == "function"
        assert ollama_tools[0]["function"]["name"] == "test_tool"
        assert ollama_tools[0]["function"]["description"] == "A test tool"

    def test_ollama_response_conversion(self):
        """Test Ollama response conversion to Songbird format."""
        provider = OllamaProvider()
        
        mock_ollama_response = {
            "message": {
                "content": "Hello from Ollama!",
                "tool_calls": [{
                    "id": "call_123",
                    "function": {
                        "name": "test_function",
                        "arguments": {"arg": "value"}
                    }
                }]
            },
            "model": "qwen2.5-coder:7b",
            "usage": {"tokens": 100}
        }
        
        songbird_response = provider._convert_ollama_response_to_songbird(mock_ollama_response)
        
        assert isinstance(songbird_response, ChatResponse)
        assert songbird_response.content == "Hello from Ollama!"
        assert songbird_response.model == "qwen2.5-coder:7b"
        assert len(songbird_response.tool_calls) == 1
        assert songbird_response.tool_calls[0]["function"]["name"] == "test_function"


class TestEnhancedOpenRouterProvider:
    """Test the enhanced OpenRouter provider with robust error handling."""
    
    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"})
    def test_openrouter_provider_initialization(self):
        """Test OpenRouter provider initializes correctly."""
        with patch('songbird.llm.providers.openai.OpenAI'):
            provider = OpenRouterProvider()
            assert provider.model == "deepseek/deepseek-chat-v3-0324:free"
            assert provider.api_key == "test-key"

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"})
    def test_openrouter_robust_response_parsing(self):
        """Test OpenRouter handles malformed responses gracefully."""
        with patch('songbird.llm.providers.openai.OpenAI'):
            provider = OpenRouterProvider()
            
            # Test missing choices
            bad_response = Mock()
            bad_response.choices = []
            
            result = provider._convert_openrouter_response_to_songbird(bad_response)
            
            assert isinstance(result, ChatResponse)
            assert "Error parsing OpenRouter response" in result.content
            assert result.tool_calls is None

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"})
    def test_openrouter_tool_call_error_handling(self):
        """Test OpenRouter handles malformed tool calls gracefully.""" 
        with patch('songbird.llm.providers.openai.OpenAI'):
            provider = OpenRouterProvider()
            
            # Mock response with malformed tool call
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message = Mock()
            mock_response.choices[0].message.content = "Test response"
            mock_response.choices[0].message.tool_calls = [Mock()]
            
            # Make tool call missing required attributes
            mock_response.choices[0].message.tool_calls[0].function = None
            
            with patch('builtins.print'):  # Suppress warning prints
                result = provider._convert_openrouter_response_to_songbird(mock_response)
            
            assert isinstance(result, ChatResponse)
            assert result.content == "Test response"
            assert result.tool_calls is None or len(result.tool_calls) == 0


class TestProviderRegistry:
    """Test the enhanced provider registry functionality."""
    
    def test_list_available_providers(self):
        """Test listing available providers."""
        providers = list_available_providers()
        assert isinstance(providers, list)
        assert "ollama" in providers  # Always available
        
    @patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"})
    def test_get_default_provider_with_gemini(self):
        """Test default provider selection prioritizes Gemini."""
        with patch('songbird.llm.providers.GEMINI_AVAILABLE', True):
            default = get_default_provider()
            assert default == "gemini"
    
    @patch.dict(os.environ, {}, clear=True)
    def test_get_default_provider_fallback_to_ollama(self):
        """Test default provider falls back to Ollama when no API keys."""
        default = get_default_provider()
        assert default == "ollama"
    
    def test_get_provider_by_name(self):
        """Test getting provider class by name."""
        ollama_class = get_provider("ollama")
        assert ollama_class == OllamaProvider
        
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("nonexistent")


class TestProviderCompatibility:
    """Test provider compatibility with agentic features."""
    
    def test_all_providers_support_chat_with_messages(self):
        """Test all providers implement chat_with_messages for agentic loops."""
        provider_classes = [OllamaProvider]
        
        # Add available providers
        try:
            from songbird.llm.providers import GeminiProvider
            provider_classes.append(GeminiProvider)
        except ImportError:
            pass
            
        try:
            from songbird.llm.providers import OpenRouterProvider  
            provider_classes.append(OpenRouterProvider)
        except ImportError:
            pass
        
        for provider_class in provider_classes:
            assert hasattr(provider_class, 'chat_with_messages')
            assert hasattr(provider_class, 'chat')
    
    def test_provider_tool_call_format_consistency(self):
        """Test all providers return consistent tool call formats."""
        # Mock tool calls from different providers should all convert to same format
        expected_format = {
            "id": str,
            "function": {
                "name": str,
                "arguments": dict
            }
        }
        
        # Test Ollama format conversion
        provider = OllamaProvider()
        mock_response = {
            "message": {
                "content": "Test",
                "tool_calls": [{
                    "id": "test_id",
                    "function": {
                        "name": "test_func", 
                        "arguments": {"key": "value"}
                    }
                }]
            },
            "model": "test"
        }
        
        result = provider._convert_ollama_response_to_songbird(mock_response)
        
        if result.tool_calls:
            tool_call = result.tool_calls[0]
            assert isinstance(tool_call["id"], str)
            assert isinstance(tool_call["function"]["name"], str)
            assert isinstance(tool_call["function"]["arguments"], dict)


class TestProviderValidation:
    """Test provider argument validation and fixing."""
    
    def test_tool_argument_validation(self):
        """Test tool argument validation across providers."""
        from songbird.llm.provider_validators import validate_and_fix_tool_arguments
        
        # Test valid dict arguments
        valid_args = {"file_path": "test.txt", "content": "hello"}
        result = validate_and_fix_tool_arguments(valid_args, "ollama")
        assert result == valid_args
        
        # Test string JSON arguments
        json_args = '{"file_path": "test.txt", "content": "hello"}'
        result = validate_and_fix_tool_arguments(json_args, "gemini")
        assert result == {"file_path": "test.txt", "content": "hello"}
        
        # Test malformed arguments
        bad_args = "not json"
        result = validate_and_fix_tool_arguments(bad_args, "openrouter")
        assert isinstance(result, dict)  # Should return empty dict as fallback