"""Tests for new LLM providers (OpenAI, Claude, OpenRouter)."""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from songbird.llm.providers import (
    OpenAIProvider, ClaudeProvider, OpenRouterProvider,
    get_provider, list_available_providers, get_provider_info
)
from songbird.llm.types import ChatResponse


class TestOpenAIProvider:
    """Test OpenAI provider implementation."""

    @patch('songbird.llm.providers.OPENAI_AVAILABLE', True)
    @patch('songbird.llm.providers.openai')
    def test_init_with_api_key(self, mock_openai):
        """Test OpenAI provider initialization with API key."""
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            provider = OpenAIProvider(model="gpt-4o")
            assert provider.model == "gpt-4o"
            assert provider.api_key == "test-key"
            mock_openai.OpenAI.assert_called_once_with(api_key="test-key")

    @patch('songbird.llm.providers.OPENAI_AVAILABLE', True)
    def test_init_without_api_key(self):
        """Test OpenAI provider initialization without API key raises error."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="OpenAI API key required"):
                OpenAIProvider()

    @patch('songbird.llm.providers.OPENAI_AVAILABLE', False)
    def test_init_when_not_available(self):
        """Test OpenAI provider initialization when library not available."""
        with pytest.raises(ImportError, match="openai package not installed"):
            OpenAIProvider()

    @patch('songbird.llm.providers.OPENAI_AVAILABLE', True)
    @patch('songbird.llm.providers.openai')
    def test_chat(self, mock_openai):
        """Test OpenAI chat functionality."""
        # Setup mock response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Hello, world!"
        mock_response.choices[0].message.tool_calls = None
        mock_response.model = "gpt-4o"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client

        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            provider = OpenAIProvider(model="gpt-4o")
            response = provider.chat("Hello")

            assert isinstance(response, ChatResponse)
            assert response.content == "Hello, world!"
            assert response.model == "gpt-4o"
            assert response.usage["total_tokens"] == 15


class TestClaudeProvider:
    """Test Claude provider implementation."""

    @patch('songbird.llm.providers.ANTHROPIC_AVAILABLE', True)
    @patch('songbird.llm.providers.anthropic')
    def test_init_with_api_key(self, mock_anthropic):
        """Test Claude provider initialization with API key."""
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'}):
            provider = ClaudeProvider(model="claude-3-5-sonnet-20241022")
            assert provider.model == "claude-3-5-sonnet-20241022"
            assert provider.api_key == "test-key"
            mock_anthropic.Anthropic.assert_called_once_with(api_key="test-key")

    @patch('songbird.llm.providers.ANTHROPIC_AVAILABLE', True)
    def test_init_without_api_key(self):
        """Test Claude provider initialization without API key raises error."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Anthropic API key required"):
                ClaudeProvider()

    @patch('songbird.llm.providers.ANTHROPIC_AVAILABLE', False)
    def test_init_when_not_available(self):
        """Test Claude provider initialization when library not available."""
        with pytest.raises(ImportError, match="anthropic package not installed"):
            ClaudeProvider()

    @patch('songbird.llm.providers.ANTHROPIC_AVAILABLE', True)
    @patch('songbird.llm.providers.anthropic')
    def test_chat(self, mock_anthropic):
        """Test Claude chat functionality."""
        # Setup mock response
        mock_response = Mock()
        mock_response.content = [Mock()]
        mock_response.content[0].type = "text"
        mock_response.content[0].text = "Hello from Claude!"
        mock_response.model = "claude-3-5-sonnet-20241022"
        mock_response.usage.input_tokens = 8
        mock_response.usage.output_tokens = 4
        
        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'}):
            provider = ClaudeProvider(model="claude-3-5-sonnet-20241022")
            response = provider.chat("Hello")

            assert isinstance(response, ChatResponse)
            assert response.content == "Hello from Claude!"
            assert response.model == "claude-3-5-sonnet-20241022"
            assert response.usage["total_tokens"] == 12


class TestOpenRouterProvider:
    """Test OpenRouter provider implementation."""

    @patch('songbird.llm.providers.OPENAI_AVAILABLE', True)
    @patch('songbird.llm.providers.openai')
    def test_init_with_api_key(self, mock_openai):
        """Test OpenRouter provider initialization with API key."""
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'test-key'}):
            provider = OpenRouterProvider(model="anthropic/claude-3.5-sonnet")
            assert provider.model == "anthropic/claude-3.5-sonnet"
            assert provider.api_key == "test-key"
            mock_openai.OpenAI.assert_called_once_with(
                api_key="test-key",
                base_url="https://openrouter.ai/api/v1"
            )

    @patch('songbird.llm.providers.OPENAI_AVAILABLE', True)
    def test_init_without_api_key(self):
        """Test OpenRouter provider initialization without API key raises error."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="OpenRouter API key required"):
                OpenRouterProvider()

    @patch('songbird.llm.providers.OPENAI_AVAILABLE', False)
    def test_init_when_not_available(self):
        """Test OpenRouter provider initialization when OpenAI library not available."""
        with pytest.raises(ImportError, match="openai package not installed"):
            OpenRouterProvider()


class TestProviderRegistry:
    """Test provider registry functionality."""

    @patch('songbird.llm.providers.OPENAI_AVAILABLE', True)
    @patch('songbird.llm.providers.ANTHROPIC_AVAILABLE', True)
    @patch('songbird.llm.providers.GEMINI_AVAILABLE', True)
    def test_list_all_providers(self):
        """Test that all providers are listed when available."""
        providers = list_available_providers()
        expected_providers = {"ollama", "openai", "claude", "openrouter", "gemini"}
        assert set(providers) == expected_providers

    @patch('songbird.llm.providers.OPENAI_AVAILABLE', True)
    @patch('songbird.llm.providers.ANTHROPIC_AVAILABLE', True)
    @patch('songbird.llm.providers.GEMINI_AVAILABLE', True)
    def test_get_provider_classes(self):
        """Test getting provider classes by name."""
        assert get_provider("openai") == OpenAIProvider
        assert get_provider("claude") == ClaudeProvider
        assert get_provider("openrouter") == OpenRouterProvider

    def test_get_unknown_provider(self):
        """Test getting unknown provider raises error."""
        with pytest.raises(ValueError, match="Unknown provider: unknown"):
            get_provider("unknown")

    @patch('songbird.llm.providers.OPENAI_AVAILABLE', True)
    @patch('songbird.llm.providers.ANTHROPIC_AVAILABLE', True)
    @patch('songbird.llm.providers.GEMINI_AVAILABLE', True)
    def test_get_provider_info(self):
        """Test getting provider information."""
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'test-key',
            'ANTHROPIC_API_KEY': 'test-key',
            'GOOGLE_API_KEY': 'test-key',
            'OPENROUTER_API_KEY': 'test-key'
        }):
            info = get_provider_info()
            
            # Check that info includes all providers
            assert "openai" in info
            assert "claude" in info
            assert "openrouter" in info
            assert "gemini" in info
            assert "ollama" in info
            
            # Check OpenAI info
            openai_info = info["openai"]
            assert openai_info["available"] is True
            assert "gpt-4o" in openai_info["models"]
            assert openai_info["api_key_env"] == "OPENAI_API_KEY"
            
            # Check Claude info
            claude_info = info["claude"]
            assert claude_info["available"] is True
            assert "claude-3-5-sonnet-20241022" in claude_info["models"]
            assert claude_info["api_key_env"] == "ANTHROPIC_API_KEY"


class TestToolCalling:
    """Test tool calling functionality across providers."""

    @patch('songbird.llm.providers.OPENAI_AVAILABLE', True)
    @patch('songbird.llm.providers.openai')
    def test_openai_tool_calling(self, mock_openai):
        """Test OpenAI tool calling conversion."""
        # Setup mock response with tool calls
        mock_tool_call = Mock()
        mock_tool_call.id = "call_123"
        mock_tool_call.function.name = "test_function"
        mock_tool_call.function.arguments = '{"arg1": "value1"}'
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "I'll use a tool"
        mock_response.choices[0].message.tool_calls = [mock_tool_call]
        mock_response.model = "gpt-4o"
        mock_response.usage = None

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client

        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
            provider = OpenAIProvider()
            tools = [{"type": "function", "function": {"name": "test_function", "description": "Test"}}]
            response = provider.chat("Use a tool", tools=tools)

            assert response.tool_calls is not None
            assert len(response.tool_calls) == 1
            assert response.tool_calls[0]["id"] == "call_123"
            assert response.tool_calls[0]["function"]["name"] == "test_function"

    @patch('songbird.llm.providers.ANTHROPIC_AVAILABLE', True)
    @patch('songbird.llm.providers.anthropic')
    def test_claude_tool_calling(self, mock_anthropic):
        """Test Claude tool calling conversion."""
        # Setup mock response with tool use
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.id = "toolu_123"
        mock_tool_block.name = "test_function"
        mock_tool_block.input = {"arg1": "value1"}
        
        mock_text_block = Mock()
        mock_text_block.type = "text"
        mock_text_block.text = "I'll use a tool"
        
        mock_response = Mock()
        mock_response.content = [mock_text_block, mock_tool_block]
        mock_response.model = "claude-3-5-sonnet-20241022"
        mock_response.usage = None
        
        mock_client = Mock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'test-key'}):
            provider = ClaudeProvider()
            tools = [{"type": "function", "function": {"name": "test_function", "description": "Test"}}]
            response = provider.chat("Use a tool", tools=tools)

            assert response.tool_calls is not None
            assert len(response.tool_calls) == 1
            assert response.tool_calls[0]["id"] == "toolu_123"
            assert response.tool_calls[0]["function"]["name"] == "test_function"
            assert response.content == "I'll use a tool"