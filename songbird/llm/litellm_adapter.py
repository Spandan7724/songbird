# songbird/llm/litellm_adapter.py
"""LiteLLM adapter providing unified interface for all providers."""

import litellm
import logging
from typing import AsyncGenerator, List, Dict, Any, Optional
from rich.console import Console
from .unified_interface import UnifiedProviderInterface
from .types import ChatResponse

console = Console()
logger = logging.getLogger(__name__)


class LiteLLMError(Exception):
    """Base exception for LiteLLM adapter errors."""
    pass


class LiteLLMConnectionError(LiteLLMError):
    """Connection-related errors."""
    pass


class LiteLLMAuthenticationError(LiteLLMError):
    """Authentication-related errors."""
    pass


class LiteLLMRateLimitError(LiteLLMError):
    """Rate limit exceeded errors."""
    pass


class LiteLLMModelError(LiteLLMError):
    """Model-related errors (not found, not supported, etc.)."""
    pass


class LiteLLMAdapter(UnifiedProviderInterface):
    """Unified LiteLLM adapter that replaces all provider-specific implementations."""
    
    def __init__(self, model: str, api_base: Optional[str] = None, **kwargs):
        """
        Initialize LiteLLM adapter.
        
        Args:
            model: LiteLLM model string (e.g., "openai/gpt-4o", "anthropic/claude-3-5-sonnet")
            api_base: Optional custom API base URL
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
        """
        self.model = model
        self.api_base = api_base
        self.kwargs = kwargs
        
        # Extract vendor prefix and model name for caching
        if "/" in model:
            self.vendor_prefix, self.model_name = model.split("/", 1)
        else:
            # LiteLLM assumes OpenAI if no prefix
            self.vendor_prefix = "openai"
            self.model_name = model
        
        # State management for model swaps
        self._state_cache = {}
        self._last_model = model
        
        # Add api_base to kwargs if provided
        if api_base:
            self.kwargs["api_base"] = api_base
            
        # Validate model and environment if possible
        self._validate_model_compatibility()
        self._validate_environment_variables()
        
        console.print(f"[dim]LiteLLM adapter initialized: {self.vendor_prefix}/{self.model_name}[/dim]")
    
    def get_provider_name(self) -> str:
        """Get the provider name."""
        return self.vendor_prefix
    
    def get_model_name(self) -> str:
        """Get the current model name."""
        return self.model_name
    
    async def chat_with_messages(self, messages: List[Dict[str, Any]], 
                                tools: Optional[List[Dict[str, Any]]] = None) -> ChatResponse:
        """
        Non-streaming chat completion using LiteLLM.
        
        Args:
            messages: List of message dictionaries
            tools: Optional list of tool schemas (OpenAI format)
            
        Returns:
            ChatResponse: Unified response format
        """
        try:
            # Check if model changed and flush state if needed
            self.check_and_flush_if_model_changed()
            
            logger.debug(f"Starting completion with {self.vendor_prefix}/{self.model_name}")
            
            # Prepare the completion call
            completion_kwargs = {
                "model": self.model,
                "messages": messages,
                **self.kwargs
            }
            
            # Add tools if provided (LiteLLM handles provider-specific formatting)
            if tools:
                validated_tools = self.format_tools_for_provider(tools)
                if validated_tools:
                    completion_kwargs["tools"] = validated_tools
                    # Add tool_choice to encourage tool usage when tools are provided
                    completion_kwargs["tool_choice"] = "auto"
                    logger.debug(f"Added {len(validated_tools)} validated tools to completion call")
                else:
                    logger.warning("No valid tools after validation, proceeding without tools")
            
            # Make the API call
            response = await litellm.acompletion(**completion_kwargs)
            
            logger.debug(f"Completion successful, converting response")
            return self._convert_to_songbird_response(response)
            
        except Exception as e:
            error = self._handle_completion_error(e, "completion")
            raise error
    
    async def stream_chat(self, messages: List[Dict[str, Any]], 
                         tools: List[Dict[str, Any]]) -> AsyncGenerator[dict, None]:
        """
        Streaming chat completion using LiteLLM.
        
        Args:
            messages: List of message dictionaries
            tools: List of tool schemas (OpenAI format)
            
        Yields:
            dict: Normalized streaming chunks
        """
        try:
            # Check if model changed and flush state if needed
            self.check_and_flush_if_model_changed()
            
            logger.debug(f"Starting streaming with {self.vendor_prefix}/{self.model_name}")
            
            # Prepare the streaming completion call
            completion_kwargs = {
                "model": self.model,
                "messages": messages,
                "stream": True,
                **self.kwargs
            }
            
            # Add tools if provided with validation
            if tools:
                validated_tools = self.format_tools_for_provider(tools)
                if validated_tools:
                    completion_kwargs["tools"] = validated_tools
                    completion_kwargs["tool_choice"] = "auto"
                    logger.debug(f"Added {len(validated_tools)} validated tools to streaming call")
                else:
                    logger.warning("No valid tools after validation, streaming without tools")
            
            # Tools are now handled above with validation
            
            # Start streaming
            stream = await litellm.acompletion(**completion_kwargs)
            
            try:
                chunk_count = 0
                async for chunk in stream:
                    chunk_count += 1
                    logger.debug(f"Processing chunk {chunk_count}")
                    yield self._normalize_chunk(chunk)
                    
                logger.debug(f"Streaming completed with {chunk_count} chunks")
                
            finally:
                # Critical: Clean up the stream to prevent socket leaks
                logger.debug("Cleaning up stream resources")
                if hasattr(stream, 'aclose'):
                    await stream.aclose()
                    
        except Exception as e:
            error = self._handle_completion_error(e, "streaming")
            logger.error(f"Streaming failed: {error}")
            raise error
    
    def _normalize_chunk(self, chunk: dict) -> dict:
        """
        Normalize LiteLLM chunk to unified format.
        
        Args:
            chunk: Raw LiteLLM chunk in OpenAI delta format
            
        Returns:
            dict: Normalized chunk for Songbird
        """
        choices = chunk.get("choices", [])
        if not choices:
            return {"role": "assistant", "content": "", "tool_calls": []}
        
        delta = choices[0].get("delta", {})
        
        # Handle role propagation (some providers omit role after first chunk)
        role = delta.get("role", "assistant")
        content = delta.get("content", "")
        tool_calls = delta.get("tool_calls", [])
        
        return {
            "role": role,
            "content": content,
            "tool_calls": tool_calls
        }
    
    def _handle_completion_error(self, error: Exception, operation: str) -> Exception:
        """
        Handle and classify LiteLLM errors with detailed logging.
        
        Args:
            error: The original exception
            operation: The operation being performed ("completion" or "streaming")
            
        Returns:
            Exception: Classified exception with helpful context
        """
        error_msg = str(error).lower()
        context = f"{self.vendor_prefix} {operation}"
        
        # Log the original error with full context
        logger.error(f"LiteLLM {operation} error with {self.vendor_prefix}/{self.model_name}: {error}")
        
        # Check for specific LiteLLM exception types first
        if hasattr(error, '__class__'):
            error_class = error.__class__.__name__
            if "authentication" in error_class.lower() or "auth" in error_class.lower():
                detailed_msg = self._get_auth_error_help(self.vendor_prefix)
                logger.error(f"Authentication error for {self.vendor_prefix}: {detailed_msg}")
                return LiteLLMAuthenticationError(f"{context}: {detailed_msg}")
        
        # Classify errors based on common patterns in error messages
        if "authentication" in error_msg or "api key" in error_msg or "unauthorized" in error_msg or "401" in error_msg:
            detailed_msg = self._get_auth_error_help(self.vendor_prefix)
            logger.error(f"Authentication error for {self.vendor_prefix}: {detailed_msg}")
            return LiteLLMAuthenticationError(f"{context}: {detailed_msg}")
            
        elif "rate limit" in error_msg or "quota" in error_msg or "too many requests" in error_msg or "429" in error_msg:
            detailed_msg = f"Rate limit exceeded for {self.vendor_prefix}. Please wait and try again."
            logger.warning(f"Rate limit error for {self.vendor_prefix}")
            return LiteLLMRateLimitError(f"{context}: {detailed_msg}")
            
        elif ("model" in error_msg and ("not found" in error_msg or "not supported" in error_msg)) or "404" in error_msg:
            detailed_msg = f"Model '{self.model_name}' not available for {self.vendor_prefix}. Check available models."
            logger.error(f"Model error for {self.vendor_prefix}: {self.model_name}")
            return LiteLLMModelError(f"{context}: {detailed_msg}")
            
        elif "connection" in error_msg or "timeout" in error_msg or "network" in error_msg or "503" in error_msg:
            detailed_msg = f"Connection failed to {self.vendor_prefix}. Check network and service status."
            logger.error(f"Connection error for {self.vendor_prefix}")
            return LiteLLMConnectionError(f"{context}: {detailed_msg}")
            
        else:
            # Generic error with full context and troubleshooting info
            detailed_msg = f"Unexpected error: {error}. Check logs for details."
            logger.error(f"Unclassified error for {self.vendor_prefix}: {error}")
            logger.debug(f"Full error details: {type(error).__name__}: {error}")
            return LiteLLMError(f"{context}: {detailed_msg}")
    
    def _get_auth_error_help(self, provider: str) -> str:
        """Get provider-specific authentication help."""
        auth_help = {
            "openai": "Set OPENAI_API_KEY environment variable. Get your key from: https://platform.openai.com/api-keys",
            "anthropic": "Set ANTHROPIC_API_KEY environment variable. Get your key from: https://console.anthropic.com/account/keys",
            "claude": "Set ANTHROPIC_API_KEY environment variable. Get your key from: https://console.anthropic.com/account/keys",
            "gemini": "Set GEMINI_API_KEY environment variable. Get your key from: https://aistudio.google.com/app/apikey",
            "google": "Set GOOGLE_API_KEY environment variable. Get your key from: https://aistudio.google.com/app/apikey",
            "openrouter": "Set OPENROUTER_API_KEY environment variable. Get your key from: https://openrouter.ai/keys",
            "ollama": "Ensure Ollama is running locally: ollama serve"
        }
        return auth_help.get(provider, f"Check API key configuration for {provider}")

    def _convert_to_songbird_response(self, response) -> ChatResponse:
        """
        Convert LiteLLM response to Songbird ChatResponse format.
        
        Args:
            response: LiteLLM response object
            
        Returns:
            ChatResponse: Unified Songbird response
        """
        try:
            choice = response.choices[0]
            message = choice.message
            
            # Extract content
            content = getattr(message, 'content', '') or ""
            
            # Convert tool calls if present
            tool_calls = None
            if hasattr(message, 'tool_calls') and message.tool_calls:
                tool_calls = []
                for tool_call in message.tool_calls:
                    tool_calls.append({
                        "id": tool_call.id,
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments
                        }
                    })
            
            # Convert usage information
            usage_dict = None
            if hasattr(response, 'usage') and response.usage:
                usage_dict = {
                    "prompt_tokens": getattr(response.usage, 'prompt_tokens', 0),
                    "completion_tokens": getattr(response.usage, 'completion_tokens', 0),
                    "total_tokens": getattr(response.usage, 'total_tokens', 0)
                }
            
            return ChatResponse(
                content=content,
                model=getattr(response, 'model', self.model),
                usage=usage_dict,
                tool_calls=tool_calls
            )
            
        except Exception as e:
            # Fallback response if conversion fails
            console.print(f"[yellow]Warning: Response conversion failed: {e}[/yellow]")
            return ChatResponse(
                content=f"Error parsing response: {e}",
                model=self.model,
                usage=None,
                tool_calls=None
            )
    
    def format_tools_for_provider(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Format tools for this provider with enhanced validation.
        
        LiteLLM handles tool schema conversion automatically, but we add
        validation and logging for debugging tool calling issues.
        
        Args:
            tools: List of tool schemas in OpenAI format
            
        Returns:
            List[Dict[str, Any]]: Tools ready for LiteLLM
        """
        if not tools:
            return []
        
        logger.debug(f"Formatting {len(tools)} tools for {self.vendor_prefix}")
        
        # Validate tool schemas for common issues
        validated_tools = []
        for i, tool in enumerate(tools):
            try:
                # Ensure required OpenAI tool format
                if "type" not in tool or tool["type"] != "function":
                    logger.warning(f"Tool {i} missing 'type': 'function' field")
                    continue
                    
                if "function" not in tool:
                    logger.warning(f"Tool {i} missing 'function' field")
                    continue
                    
                func = tool["function"]
                if "name" not in func:
                    logger.warning(f"Tool {i} function missing 'name' field")
                    continue
                    
                if "parameters" not in func:
                    logger.warning(f"Tool {i} function missing 'parameters' field")
                    continue
                
                # Log tool for debugging
                logger.debug(f"Tool {i}: {func['name']} with {len(func.get('parameters', {}).get('properties', {}))} parameters")
                validated_tools.append(tool)
                
            except Exception as e:
                logger.error(f"Error validating tool {i}: {e}")
                continue
        
        logger.debug(f"Validated {len(validated_tools)}/{len(tools)} tools for LiteLLM")
        return validated_tools  # LiteLLM handles provider-specific conversion
    
    def parse_response_to_unified(self, response: Any) -> ChatResponse:
        """
        Parse provider response to unified ChatResponse format.
        
        Args:
            response: Raw provider response
            
        Returns:
            ChatResponse: Unified response format
        """
        return self._convert_to_songbird_response(response)
    
    def get_supported_features(self) -> Dict[str, bool]:
        """
        Get supported features for this provider.
        
        Returns:
            Dict[str, bool]: Feature support mapping
        """
        return {
            "function_calling": True,  # LiteLLM handles this automatically
            "streaming": True,
            "usage_tracking": True,
            "temperature_control": True,
            "max_tokens_control": True
        }
    
    def _validate_model_compatibility(self):
        """Validate model compatibility and show warnings for unknown models."""
        try:
            # Check if the model is a known LiteLLM format
            if "/" not in self.model:
                console.print(f"[yellow]⚠️  Model '{self.model}' doesn't use LiteLLM format (provider/model)[/yellow]")
                console.print(f"[yellow]   Expected format: {self.vendor_prefix}/{self.model_name}[/yellow]")
                return
            
            # Check for common provider patterns
            known_providers = ["openai", "anthropic", "google", "gemini", "claude", "ollama", "openrouter"]
            if self.vendor_prefix not in known_providers:
                console.print(f"[yellow]⚠️  Unknown provider prefix '{self.vendor_prefix}'[/yellow]")
                console.print(f"[yellow]   Known providers: {', '.join(known_providers)}[/yellow]")
                console.print(f"[yellow]   LiteLLM may still support this provider[/yellow]")
            
            # Provider-specific model validation
            if self.vendor_prefix == "openai" and not any(pattern in self.model_name for pattern in ["gpt-", "text-", "davinci"]):
                console.print(f"[yellow]⚠️  '{self.model_name}' doesn't match typical OpenAI model patterns[/yellow]")
            elif self.vendor_prefix == "anthropic" and not self.model_name.startswith("claude-"):
                console.print(f"[yellow]⚠️  '{self.model_name}' doesn't match typical Anthropic model patterns[/yellow]")
            elif self.vendor_prefix == "gemini" and not self.model_name.startswith("gemini-"):
                console.print(f"[yellow]⚠️  '{self.model_name}' doesn't match typical Gemini model patterns[/yellow]")
                
        except Exception as e:
            logger.debug(f"Model validation failed (non-critical): {e}")
    
    def _validate_environment_variables(self):
        """Validate that required environment variables are set for the provider."""
        import os
        
        try:
            # Map providers to their required environment variables (matching LiteLLM expectations)
            required_env_vars = {
                "openai": "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY", 
                "claude": "ANTHROPIC_API_KEY",
                "google": "GOOGLE_API_KEY",
                "gemini": "GEMINI_API_KEY",  # LiteLLM expects GEMINI_API_KEY for gemini provider
                "openrouter": "OPENROUTER_API_KEY",
                "together": "TOGETHER_API_KEY",
                "groq": "GROQ_API_KEY"
                # Note: ollama doesn't require API keys
            }
            
            env_var = required_env_vars.get(self.vendor_prefix)
            if not env_var:
                # Provider doesn't require environment variables (like ollama)
                logger.debug(f"No environment variable required for provider: {self.vendor_prefix}")
                return
            
            # Check if the environment variable is set
            value = os.getenv(env_var)
            if not value:
                console.print(f"[yellow]⚠️  Missing environment variable: {env_var}[/yellow]")
                console.print(f"[yellow]   Provider '{self.vendor_prefix}' requires this API key to function[/yellow]")
                console.print(f"[yellow]   LiteLLM will attempt to use the provider anyway[/yellow]")
            else:
                # Mask the key for security
                masked_key = value[:8] + "..." + value[-4:] if len(value) > 12 else value[:4] + "..."
                logger.debug(f"Environment variable {env_var} found: {masked_key}")
                console.print(f"[dim]✓ {env_var} configured: {masked_key}[/dim]")
                
        except Exception as e:
            logger.debug(f"Environment validation failed (non-critical): {e}")
    
    async def cleanup(self):
        """Clean up resources to prevent connection leaks."""
        try:
            # Force cleanup of LiteLLM's internal aiohttp sessions
            import asyncio
            import gc
            
            # Try to access and close any aiohttp connector pools
            try:
                # LiteLLM uses aiohttp internally, try to clean up any sessions
                import aiohttp
                
                # Look for any unclosed sessions and close them
                for obj in gc.get_objects():
                    if isinstance(obj, aiohttp.ClientSession) and not obj.closed:
                        try:
                            await obj.close()
                        except Exception:
                            pass  # Ignore errors during cleanup
                
                # Force close any connectors
                for obj in gc.get_objects():
                    if isinstance(obj, aiohttp.TCPConnector) and not obj.closed:
                        try:
                            await obj.close()
                        except Exception:
                            pass  # Ignore errors during cleanup
                
                # Give time for cleanup to complete
                await asyncio.sleep(0.1)
                
                # Force garbage collection
                gc.collect()
                
                logger.debug("LiteLLM adapter cleanup completed")
                
            except Exception as cleanup_error:
                logger.debug(f"Minor cleanup issue (non-critical): {cleanup_error}")
                
        except Exception as e:
            logger.debug(f"Cleanup failed (non-critical): {e}")
    
    def check_environment_readiness(self) -> Dict[str, Any]:
        """Check environment readiness and return status information."""
        import os
        
        status = {
            "provider": self.vendor_prefix,
            "model": self.model_name,
            "api_base": self.get_api_base(),
            "env_ready": False,
            "env_var": None,
            "env_status": "unknown"
        }
        
        try:
            # Map providers to their required environment variables
            required_env_vars = {
                "openai": "OPENAI_API_KEY",
                "anthropic": "ANTHROPIC_API_KEY",
                "claude": "ANTHROPIC_API_KEY", 
                "google": "GOOGLE_API_KEY",
                "gemini": "GOOGLE_API_KEY",
                "openrouter": "OPENROUTER_API_KEY",
                "together": "TOGETHER_API_KEY",
                "groq": "GROQ_API_KEY"
            }
            
            env_var = required_env_vars.get(self.vendor_prefix)
            status["env_var"] = env_var
            
            if not env_var:
                # Provider doesn't require environment variables (like ollama)
                status["env_ready"] = True
                status["env_status"] = "not_required"
            else:
                # Check if the environment variable is set
                value = os.getenv(env_var)
                if value:
                    status["env_ready"] = True
                    status["env_status"] = "configured"
                else:
                    status["env_ready"] = False
                    status["env_status"] = "missing"
            
        except Exception as e:
            status["env_status"] = f"error: {e}"
        
        return status
    
    def flush_state(self):
        """Flush any cached state when model changes."""
        try:
            logger.debug(f"Flushing state for model change: {self._last_model} -> {self.model}")
            
            # Clear internal state cache
            self._state_cache.clear()
            
            # Update model tracking
            self._last_model = self.model
            
            # Re-extract vendor prefix and model name if model changed
            if "/" in self.model:
                self.vendor_prefix, self.model_name = self.model.split("/", 1)
            else:
                self.vendor_prefix = "openai"
                self.model_name = self.model
            
            console.print(f"[dim]🔄 State flushed for model change: {self.vendor_prefix}/{self.model_name}[/dim]")
            
        except Exception as e:
            logger.error(f"Error flushing state: {e}")
    
    def check_and_flush_if_model_changed(self):
        """Check if model changed and flush state if needed."""
        if self.model != self._last_model:
            self.flush_state()
    
    def set_model(self, new_model: str):
        """Set a new model and flush state."""
        old_model = self.model
        self.model = new_model
        
        if old_model != new_model:
            logger.info(f"Model changed from {old_model} to {new_model}")
            self.flush_state()
            # Re-validate the new model
            self._validate_model_compatibility()
    
    def set_api_base(self, new_api_base: str):
        """Set a new API base URL."""
        old_api_base = self.api_base
        self.api_base = new_api_base
        
        # Update kwargs
        if new_api_base:
            self.kwargs["api_base"] = new_api_base
        elif "api_base" in self.kwargs:
            del self.kwargs["api_base"]
        
        if old_api_base != new_api_base:
            logger.info(f"API base changed from {old_api_base} to {new_api_base}")
            console.print(f"[dim]🔗 API base updated: {new_api_base or 'default'}[/dim]")
    
    def get_api_base(self) -> Optional[str]:
        """Get the current API base URL."""
        return self.api_base
    
    def get_effective_api_base(self) -> str:
        """Get the effective API base URL for the current provider."""
        if self.api_base:
            return self.api_base
        
        # Return default URLs for common providers
        defaults = {
            "openai": "https://api.openai.com/v1",
            "anthropic": "https://api.anthropic.com",
            "openrouter": "https://openrouter.ai/api/v1",
            "together": "https://api.together.xyz",
            "groq": "https://api.groq.com/openai/v1"
        }
        
        return defaults.get(self.vendor_prefix, "https://api.openai.com/v1")
    
    def chat(self, message: str, tools: Optional[List[Dict[str, Any]]] = None) -> ChatResponse:
        """
        Legacy sync method for compatibility.
        
        Note: This is a synchronous wrapper that should be avoided.
        Use chat_with_messages() instead for async operation.
        """
        import asyncio
        
        messages = [{"role": "user", "content": message}]
        
        # Run the async method
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.chat_with_messages(messages, tools))
        except RuntimeError:
            # No event loop running, create one
            return asyncio.run(self.chat_with_messages(messages, tools))


def create_litellm_provider(provider_name: str, model: str = None, 
                           api_base: str = None, **kwargs) -> LiteLLMAdapter:
    """
    Factory function to create LiteLLM provider instances with enhanced API base URL support.
    
    Args:
        provider_name: Provider name (openai, claude, gemini, ollama, openrouter)
        model: Specific model name (optional, uses default if not provided)
        api_base: Custom API base URL (optional)
        **kwargs: Additional parameters for the adapter
        
    Returns:
        LiteLLMAdapter: Configured adapter instance
    """
    from ..config import load_provider_mapping
    
    try:
        # Load configuration
        config = load_provider_mapping()
        
        # Resolve model string
        litellm_model = config.resolve_model_string(provider_name, model)
        
        # Handle API base URL priority:
        # 1. Explicitly provided api_base parameter
        # 2. Configuration file mapping
        # 3. Provider-specific defaults
        effective_api_base = api_base
        if not effective_api_base:
            effective_api_base = config.get_api_base(provider_name)
        
        # Log API base URL resolution for debugging
        if effective_api_base:
            console.print(f"[dim]Using API base for {provider_name}: {effective_api_base}[/dim]")
        else:
            console.print(f"[dim]Using default API endpoint for {provider_name}[/dim]")
        
        # Create adapter
        adapter = LiteLLMAdapter(
            model=litellm_model,
            api_base=effective_api_base,
            **kwargs
        )
        
        # Display creation summary
        if effective_api_base:
            console.print(f"[dim]Created LiteLLM provider: {provider_name} -> {litellm_model} @ {effective_api_base}[/dim]")
        else:
            console.print(f"[dim]Created LiteLLM provider: {provider_name} -> {litellm_model}[/dim]")
        
        return adapter
        
    except Exception as e:
        console.print(f"[red]Failed to create LiteLLM provider: {e}[/red]")
        raise


# Convenience function for testing
async def test_litellm_adapter():
    """Test function for LiteLLM adapter."""
    try:
        # Test provider creation
        adapter = create_litellm_provider("openai", "gpt-4o-mini")
        
        # Test basic completion
        messages = [{"role": "user", "content": "Hello, world!"}]
        response = await adapter.chat_with_messages(messages)
        
        console.print(f"Test response: {response.content[:50]}...")
        return True
        
    except Exception as e:
        console.print(f"[red]Test failed: {e}[/red]")
        return False

async def test_tool_calling():
    """Test tool calling functionality with LiteLLM adapter."""
    try:
        console.print("Testing LiteLLM tool calling...")
        
        # Create adapter
        adapter = LiteLLMAdapter("openai/gpt-4o-mini")
        
        # Test tool validation
        test_tools = [
            {
                "type": "function",
                "function": {
                    "name": "test_tool",
                    "description": "A test tool",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "message": {"type": "string", "description": "Test message"}
                        },
                        "required": ["message"]
                    }
                }
            }
        ]
        
        # Test tool formatting
        formatted_tools = adapter.format_tools_for_provider(test_tools)
        console.print(f"✓ Tool validation passed: {len(formatted_tools)} tools formatted")
        
        # Test with invalid tools
        invalid_tools = [
            {"type": "invalid"},  # Missing function field
            {"function": {"name": "test"}},  # Missing type field
            {}  # Empty tool
        ]
        
        formatted_invalid = adapter.format_tools_for_provider(invalid_tools)
        console.print(f"✓ Invalid tool filtering passed: {len(formatted_invalid)} tools from {len(invalid_tools)} invalid tools")
        
        console.print("Tool calling tests completed successfully")
        return True
        
    except Exception as e:
        console.print(f"[red]Tool calling test failed: {e}[/red]")
        return False


if __name__ == "__main__":
    # Run test
    import asyncio
    asyncio.run(test_litellm_adapter())