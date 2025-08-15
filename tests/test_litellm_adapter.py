# tests/test_litellm_adapter.py
"""
Comprehensive test suite for LiteLLM adapter implementation.

Tests all aspects of the LiteLLM adapter including:
- Initialization and configuration
- Non-streaming and streaming chat completion
- Tool calling functionality
- Error handling and classification
- Resource management and cleanup
- Model switching and state management
- Environment variable validation
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from songbird.llm.litellm_adapter import (
    LiteLLMAdapter,
    LiteLLMError, LiteLLMConnectionError, LiteLLMAuthenticationError,
    LiteLLMRateLimitError, LiteLLMModelError
)
from songbird.llm.providers import create_litellm_provider
from songbird.llm.types import ChatResponse


class TestLiteLLMAdapterInitialization:
    """Test LiteLLM adapter initialization and configuration."""
    
    def test_adapter_initialization_with_model_string(self):
        """Test adapter initializes correctly with LiteLLM model string."""
        adapter = LiteLLMAdapter("openai/gpt-4o")
        
        assert adapter.model == "openai/gpt-4o"
        assert adapter.vendor_prefix == "openai"
        assert adapter.model_name == "gpt-4o"
        assert adapter.api_base is None
        assert adapter._last_model == "openai/gpt-4o"
    
    def test_adapter_initialization_with_api_base(self):
        """Test adapter initializes with custom API base URL."""
        adapter = LiteLLMAdapter(
            "openrouter/anthropic/claude-3.5-sonnet", 
            api_base="https://openrouter.ai/api/v1"
        )
        
        assert adapter.api_base == "https://openrouter.ai/api/v1"
        assert adapter.kwargs["api_base"] == "https://openrouter.ai/api/v1"
        assert adapter.vendor_prefix == "openrouter"
        assert adapter.model_name == "anthropic/claude-3.5-sonnet"
    
    def test_adapter_initialization_without_prefix(self):
        """Test adapter defaults to OpenAI when no prefix provided."""
        adapter = LiteLLMAdapter("gpt-4o")
        
        assert adapter.vendor_prefix == "openai"
        assert adapter.model_name == "gpt-4o"
    
    def test_adapter_provider_name(self):
        """Test adapter returns correct provider name."""
        adapter = LiteLLMAdapter("anthropic/claude-3.5-sonnet")
        assert adapter.get_provider_name() == "anthropic"
        
    def test_adapter_model_name(self):
        """Test adapter returns correct model name."""
        adapter = LiteLLMAdapter("gemini/gemini-2.0-flash-001")
        assert adapter.get_model_name() == "gemini-2.0-flash-001"
    
    def test_adapter_supported_features(self):
        """Test adapter reports correct supported features."""
        adapter = LiteLLMAdapter("openai/gpt-4o")
        features = adapter.get_supported_features()
        
        assert features["function_calling"] is True
        assert features["streaming"] is True
        assert features["usage_tracking"] is True
        assert features["temperature_control"] is True
        assert features["max_tokens_control"] is True


class TestLiteLLMAdapterChatCompletion:
    """Test LiteLLM adapter chat completion functionality."""
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_chat_with_messages_basic(self, mock_acompletion):
        """Test basic chat completion without tools."""
        # Mock LiteLLM response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Hello! How can I help you?"
        mock_response.choices[0].message.tool_calls = None
        mock_response.model = "openai/gpt-4o"
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 8
        mock_response.usage.total_tokens = 18
        
        mock_acompletion.return_value = mock_response
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        messages = [{"role": "user", "content": "Hello"}]
        
        response = await adapter.chat_with_messages(messages)
        
        assert isinstance(response, ChatResponse)
        assert response.content == "Hello! How can I help you?"
        assert response.model == "openai/gpt-4o"
        assert response.usage["prompt_tokens"] == 10
        assert response.usage["completion_tokens"] == 8
        assert response.usage["total_tokens"] == 18
        assert response.tool_calls is None
        
        # Verify LiteLLM was called correctly
        mock_acompletion.assert_called_once()
        call_args = mock_acompletion.call_args[1]
        assert call_args["model"] == "openai/gpt-4o"
        assert call_args["messages"] == messages
        assert "tools" not in call_args
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_chat_with_messages_and_tools(self, mock_acompletion):
        """Test chat completion with tool calling."""
        # Mock LiteLLM response with tool calls
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "I'll help you create a file."
        mock_response.choices[0].message.tool_calls = [Mock()]
        mock_response.choices[0].message.tool_calls[0].id = "call_123"
        mock_response.choices[0].message.tool_calls[0].function = Mock()
        mock_response.choices[0].message.tool_calls[0].function.name = "file_create"
        mock_response.choices[0].message.tool_calls[0].function.arguments = '{"file_path": "test.txt", "content": "Hello"}'
        mock_response.model = "openai/gpt-4o"
        
        mock_acompletion.return_value = mock_response
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        messages = [{"role": "user", "content": "Create a test file"}]
        tools = [{
            "type": "function",
            "function": {
                "name": "file_create",
                "description": "Create a new file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string"},
                        "content": {"type": "string"}
                    },
                    "required": ["file_path", "content"]
                }
            }
        }]
        
        response = await adapter.chat_with_messages(messages, tools)
        
        assert isinstance(response, ChatResponse)
        assert response.content == "I'll help you create a file."
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]["id"] == "call_123"
        assert response.tool_calls[0]["function"]["name"] == "file_create"
        assert response.tool_calls[0]["function"]["arguments"] == '{"file_path": "test.txt", "content": "Hello"}'
        
        # Verify tools were passed correctly
        call_args = mock_acompletion.call_args[1]
        assert "tools" in call_args
        assert call_args["tool_choice"] == "auto"
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_chat_with_model_state_flush(self, mock_acompletion):
        """Test that model changes trigger state flush."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Response"
        mock_response.choices[0].message.tool_calls = None
        
        mock_acompletion.return_value = mock_response
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        
        # Change model to trigger state flush
        adapter.set_model("anthropic/claude-3.5-sonnet")
        
        messages = [{"role": "user", "content": "Hello"}]
        await adapter.chat_with_messages(messages)
        
        # Verify model was updated
        assert adapter.model == "anthropic/claude-3.5-sonnet"
        assert adapter.vendor_prefix == "anthropic"
        assert adapter.model_name == "claude-3.5-sonnet"
        
        # Verify LiteLLM was called with new model
        call_args = mock_acompletion.call_args[1]
        assert call_args["model"] == "anthropic/claude-3.5-sonnet"


class TestLiteLLMAdapterStreaming:
    """Test LiteLLM adapter streaming functionality."""
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_stream_chat_basic(self, mock_acompletion):
        """Test basic streaming chat completion."""
        # Mock streaming response
        async def mock_stream():
            yield {
                "choices": [{
                    "delta": {
                        "role": "assistant",
                        "content": "Hello"
                    }
                }]
            }
            yield {
                "choices": [{
                    "delta": {
                        "content": " there!"
                    }
                }]
            }
        
        mock_stream_obj = Mock()
        mock_stream_obj.__aiter__ = lambda self: mock_stream()
        mock_stream_obj.aclose = AsyncMock()
        
        mock_acompletion.return_value = mock_stream_obj
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        messages = [{"role": "user", "content": "Hello"}]
        tools = []
        
        chunks = []
        async for chunk in adapter.stream_chat(messages, tools):
            chunks.append(chunk)
        
        assert len(chunks) == 2
        assert chunks[0]["role"] == "assistant"
        assert chunks[0]["content"] == "Hello"
        assert chunks[1]["content"] == " there!"
        
        # Verify stream was properly closed
        mock_stream_obj.aclose.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_stream_chat_with_tools(self, mock_acompletion):
        """Test streaming with tool calls."""
        # Mock streaming response with tool calls
        async def mock_stream():
            yield {
                "choices": [{
                    "delta": {
                        "role": "assistant",
                        "content": "I'll create"
                    }
                }]
            }
            yield {
                "choices": [{
                    "delta": {
                        "tool_calls": [{
                            "id": "call_123",
                            "function": {
                                "name": "file_create",
                                "arguments": '{"file_path": "test.txt"}'
                            }
                        }]
                    }
                }]
            }
        
        mock_stream_obj = Mock()
        mock_stream_obj.__aiter__ = lambda self: mock_stream()
        mock_stream_obj.aclose = AsyncMock()
        
        mock_acompletion.return_value = mock_stream_obj
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        messages = [{"role": "user", "content": "Create a file"}]
        tools = [{
            "type": "function",
            "function": {
                "name": "file_create",
                "description": "Create a file",
                "parameters": {"type": "object", "properties": {}}
            }
        }]
        
        chunks = []
        async for chunk in adapter.stream_chat(messages, tools):
            chunks.append(chunk)
        
        assert len(chunks) == 2
        assert chunks[0]["content"] == "I'll create"
        assert len(chunks[1]["tool_calls"]) == 1
        assert chunks[1]["tool_calls"][0]["id"] == "call_123"
        
        # Verify tools were included in call
        call_args = mock_acompletion.call_args[1]
        assert "tools" in call_args
        assert call_args["stream"] is True
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_stream_chat_resource_cleanup_on_error(self, mock_acompletion):
        """Test that stream resources are cleaned up even on error."""
        # Mock stream that raises an error
        async def mock_stream():
            yield {
                "choices": [{
                    "delta": {"role": "assistant", "content": "Hello"}
                }]
            }
            raise Exception("Stream error")
        
        mock_stream_obj = Mock()
        mock_stream_obj.__aiter__ = lambda self: mock_stream()
        mock_stream_obj.aclose = AsyncMock()
        mock_stream_obj.__aenter__ = AsyncMock(return_value=mock_stream_obj)
        mock_stream_obj.__aexit__ = AsyncMock()
        
        mock_acompletion.return_value = mock_stream_obj
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        messages = [{"role": "user", "content": "Hello"}]
        
        # Stream should raise error but still clean up
        with pytest.raises(Exception):
            chunks = []
            async for chunk in adapter.stream_chat(messages, []):
                chunks.append(chunk)
        
        # Verify cleanup was called despite error
        mock_stream_obj.aclose.assert_called_once()


class TestLiteLLMAdapterErrorHandling:
    """Test LiteLLM adapter error handling and classification."""
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_authentication_error_handling(self, mock_acompletion):
        """Test authentication error classification and help."""
        mock_acompletion.side_effect = Exception("401 Unauthorized: Invalid API key")
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        messages = [{"role": "user", "content": "Hello"}]
        
        with pytest.raises(LiteLLMAuthenticationError) as exc_info:
            await adapter.chat_with_messages(messages)
        
        error_msg = str(exc_info.value)
        assert "openai completion" in error_msg
        assert "OPENAI_API_KEY" in error_msg
        assert "https://platform.openai.com/api-keys" in error_msg
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_rate_limit_error_handling(self, mock_acompletion):
        """Test rate limit error classification."""
        mock_acompletion.side_effect = Exception("429 Too Many Requests: Rate limit exceeded")
        
        adapter = LiteLLMAdapter("anthropic/claude-3.5-sonnet")
        messages = [{"role": "user", "content": "Hello"}]
        
        with pytest.raises(LiteLLMRateLimitError) as exc_info:
            await adapter.chat_with_messages(messages)
        
        error_msg = str(exc_info.value)
        assert "anthropic completion" in error_msg
        assert "Rate limit exceeded" in error_msg
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_model_not_found_error_handling(self, mock_acompletion):
        """Test model not found error classification."""
        mock_acompletion.side_effect = Exception("404 Model not found: invalid-model")
        
        adapter = LiteLLMAdapter("openai/invalid-model")
        messages = [{"role": "user", "content": "Hello"}]
        
        with pytest.raises(LiteLLMModelError) as exc_info:
            await adapter.chat_with_messages(messages)
        
        error_msg = str(exc_info.value)
        assert "openai completion" in error_msg
        assert "invalid-model" in error_msg
        assert "not available" in error_msg
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_connection_error_handling(self, mock_acompletion):
        """Test connection error classification."""
        mock_acompletion.side_effect = Exception("Connection timeout")
        
        adapter = LiteLLMAdapter("gemini/gemini-2.0-flash-001")
        messages = [{"role": "user", "content": "Hello"}]
        
        with pytest.raises(LiteLLMConnectionError) as exc_info:
            await adapter.chat_with_messages(messages)
        
        error_msg = str(exc_info.value)
        assert "gemini completion" in error_msg
        assert "Connection failed" in error_msg
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_generic_error_handling(self, mock_acompletion):
        """Test generic error handling for unclassified errors."""
        mock_acompletion.side_effect = Exception("Unexpected error occurred")
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        messages = [{"role": "user", "content": "Hello"}]
        
        with pytest.raises(LiteLLMError) as exc_info:
            await adapter.chat_with_messages(messages)
        
        error_msg = str(exc_info.value)
        assert "openai completion" in error_msg
        assert "Unexpected error" in error_msg


class TestLiteLLMAdapterToolValidation:
    """Test LiteLLM adapter tool validation and formatting."""
    
    def test_tool_validation_valid_tools(self):
        """Test validation of properly formatted tools."""
        adapter = LiteLLMAdapter("openai/gpt-4o")
        
        valid_tools = [{
            "type": "function",
            "function": {
                "name": "test_tool",
                "description": "A test tool",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "arg": {"type": "string"}
                    },
                    "required": ["arg"]
                }
            }
        }]
        
        validated = adapter.format_tools_for_provider(valid_tools)
        
        assert len(validated) == 1
        assert validated[0]["type"] == "function"
        assert validated[0]["function"]["name"] == "test_tool"
    
    def test_tool_validation_invalid_tools(self):
        """Test validation rejects malformed tools."""
        adapter = LiteLLMAdapter("openai/gpt-4o")
        
        invalid_tools = [
            {"type": "invalid"},  # Missing function field
            {"function": {"name": "test"}},  # Missing type field
            {"type": "function", "function": {}},  # Missing name in function
            {"type": "function", "function": {"name": "test"}},  # Missing parameters
            {}  # Empty tool
        ]
        
        validated = adapter.format_tools_for_provider(invalid_tools)
        
        # All tools should be rejected
        assert len(validated) == 0
    
    def test_tool_validation_mixed_tools(self):
        """Test validation with mix of valid and invalid tools."""
        adapter = LiteLLMAdapter("openai/gpt-4o")
        
        mixed_tools = [
            {  # Valid tool
                "type": "function",
                "function": {
                    "name": "valid_tool",
                    "description": "Valid",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {"type": "invalid"},  # Invalid tool
            {  # Another valid tool
                "type": "function",
                "function": {
                    "name": "another_valid_tool",
                    "description": "Also valid",
                    "parameters": {"type": "object", "properties": {}}
                }
            }
        ]
        
        validated = adapter.format_tools_for_provider(mixed_tools)
        
        # Only valid tools should remain
        assert len(validated) == 2
        assert validated[0]["function"]["name"] == "valid_tool"
        assert validated[1]["function"]["name"] == "another_valid_tool"


class TestLiteLLMAdapterStateManagement:
    """Test LiteLLM adapter state management and model switching."""
    
    def test_model_switching_updates_state(self):
        """Test that changing model updates internal state."""
        adapter = LiteLLMAdapter("openai/gpt-4o")
        
        # Initial state
        assert adapter.model == "openai/gpt-4o"
        assert adapter.vendor_prefix == "openai"
        assert adapter.model_name == "gpt-4o"
        
        # Change model
        adapter.set_model("anthropic/claude-3.5-sonnet")
        
        # Verify state updated
        assert adapter.model == "anthropic/claude-3.5-sonnet"
        assert adapter.vendor_prefix == "anthropic"
        assert adapter.model_name == "claude-3.5-sonnet"
        assert adapter._last_model == "anthropic/claude-3.5-sonnet"
    
    def test_api_base_switching(self):
        """Test that changing API base updates configuration."""
        adapter = LiteLLMAdapter("openrouter/anthropic/claude-3.5-sonnet")
        
        # Set API base
        adapter.set_api_base("https://openrouter.ai/api/v1")
        
        assert adapter.api_base == "https://openrouter.ai/api/v1"
        assert adapter.kwargs["api_base"] == "https://openrouter.ai/api/v1"
        
        # Clear API base
        adapter.set_api_base(None)
        
        assert adapter.api_base is None
        assert "api_base" not in adapter.kwargs
    
    def test_state_flush_clears_cache(self):
        """Test that state flush clears internal cache."""
        adapter = LiteLLMAdapter("openai/gpt-4o")
        
        # Add some cache data
        adapter._state_cache["test_key"] = "test_value"
        
        # Flush state
        adapter.flush_state()
        
        # Verify cache was cleared
        assert adapter._state_cache == {}
    
    def test_automatic_state_flush_on_model_change(self):
        """Test that model changes automatically trigger state flush."""
        adapter = LiteLLMAdapter("openai/gpt-4o")
        
        # Add cache data
        adapter._state_cache["test_key"] = "test_value"
        
        # Change model (should trigger flush)
        adapter.set_model("anthropic/claude-3.5-sonnet")
        
        # Verify cache was cleared by automatic flush
        assert adapter._state_cache == {}


class TestLiteLLMAdapterEnvironmentValidation:
    """Test LiteLLM adapter environment variable validation."""
    
    @patch.dict('os.environ', {'OPENAI_API_KEY': 'sk-test-key-1234567890abcdef'})
    def test_environment_validation_with_key(self):
        """Test environment validation when API key is present."""
        adapter = LiteLLMAdapter("openai/gpt-4o")
        status = adapter.check_environment_readiness()
        
        assert status["provider"] == "openai"
        assert status["env_ready"] is True
        assert status["env_status"] == "configured"
        assert status["env_var"] == "OPENAI_API_KEY"
    
    @patch.dict('os.environ', {}, clear=True)
    def test_environment_validation_missing_key(self):
        """Test environment validation when API key is missing."""
        adapter = LiteLLMAdapter("anthropic/claude-3.5-sonnet")
        status = adapter.check_environment_readiness()
        
        assert status["provider"] == "anthropic"
        assert status["env_ready"] is False
        assert status["env_status"] == "missing"
        assert status["env_var"] == "ANTHROPIC_API_KEY"
    
    def test_environment_validation_no_key_required(self):
        """Test environment validation for providers that don't need API keys."""
        adapter = LiteLLMAdapter("ollama/qwen2.5-coder:7b")
        status = adapter.check_environment_readiness()
        
        assert status["provider"] == "ollama"
        assert status["env_ready"] is True
        assert status["env_status"] == "not_required"
        assert status["env_var"] is None


class TestLiteLLMProviderFactory:
    """Test LiteLLM provider factory function."""
    
    @patch('songbird.config.mapping_loader.load_provider_mapping')
    def test_create_litellm_provider_basic(self, mock_load_config):
        """Test basic provider creation with factory function."""
        # Mock configuration
        mock_config = Mock()
        mock_config.get_default_model.return_value = "gpt-4o"
        mock_config.get_api_base.return_value = None
        mock_load_config.return_value = mock_config
        
        provider = create_litellm_provider("openai", "gpt-4o")
        
        assert isinstance(provider, LiteLLMAdapter)
        assert provider.model == "openai/gpt-4o"
        assert provider.vendor_prefix == "openai"
        assert provider.model_name == "gpt-4o"
        
        # Since model was provided, get_default_model should not be called
        mock_config.get_default_model.assert_not_called()
    
    @patch('songbird.config.mapping_loader.load_provider_mapping')
    def test_create_litellm_provider_with_api_base(self, mock_load_config):
        """Test provider creation with custom API base URL."""
        # Mock configuration
        mock_config = Mock()
        mock_config.get_default_model.return_value = "anthropic/claude-3.5-sonnet"
        mock_config.get_api_base.return_value = "https://openrouter.ai/api/v1"
        mock_load_config.return_value = mock_config
        
        provider = create_litellm_provider(
            "openrouter", 
            "anthropic/claude-3.5-sonnet",
            api_base="https://custom.api.com/v1"
        )
        
        # Explicit api_base should take priority over config
        assert provider.api_base == "https://custom.api.com/v1"
    
    @patch('songbird.config.mapping_loader.load_provider_mapping')
    def test_create_litellm_provider_config_error(self, mock_load_config):
        """Test provider creation handles configuration errors."""
        mock_load_config.side_effect = Exception("Config loading failed")
        
        with pytest.raises(Exception, match="Config loading failed"):
            create_litellm_provider("openai", "gpt-4o")


class TestLiteLLMAdapterCompatibility:
    """Test LiteLLM adapter compatibility with legacy interface."""
    
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    def test_legacy_sync_chat_method(self, mock_acompletion):
        """Test legacy synchronous chat method works."""
        # Mock response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Hello!"
        mock_response.choices[0].message.tool_calls = None
        
        mock_acompletion.return_value = mock_response
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        
        # Call legacy sync method
        response = adapter.chat("Hello")
        
        assert isinstance(response, ChatResponse)
        assert response.content == "Hello!"
    
    def test_parse_response_to_unified_compatibility(self):
        """Test parse_response_to_unified method for compatibility."""
        adapter = LiteLLMAdapter("openai/gpt-4o")
        
        # Mock LiteLLM response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].message.tool_calls = None
        
        result = adapter.parse_response_to_unified(mock_response)
        
        assert isinstance(result, ChatResponse)
        assert result.content == "Test response"


if __name__ == "__main__":
    # Run specific test for development
    pytest.main([__file__, "-v"])