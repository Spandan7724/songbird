"""Provider adapter for capability detection and management."""

from typing import Dict, List, Any

try:
    from ..tools.tool_registry import get_tool_registry
    TOOL_REGISTRY_AVAILABLE = True
except ImportError:
    TOOL_REGISTRY_AVAILABLE = False

try:
    from .types import ChatResponse
    CHAT_RESPONSE_AVAILABLE = True
except ImportError:
    CHAT_RESPONSE_AVAILABLE = False
    # Create a minimal ChatResponse class for testing
    class ChatResponse:
        def __init__(self, content="", model="", usage=None, tool_calls=None):
            self.content = content
            self.model = model
            self.usage = usage
            self.tool_calls = tool_calls


class ProviderAdapter:
    
    def __init__(self, provider_instance):
        self.provider = provider_instance
        self.provider_name = self._detect_provider_name()
        if TOOL_REGISTRY_AVAILABLE:
            self.tool_registry = get_tool_registry()
        else:
            self.tool_registry = None
    
    def _detect_provider_name(self) -> str:
        class_name = self.provider.__class__.__name__.lower()
        if "ollama" in class_name:
            return "ollama"
        elif "openai" in class_name:
            return "openai"
        elif "claude" in class_name or "anthropic" in class_name:
            return "claude"
        elif "gemini" in class_name:
            return "gemini"
        elif "openrouter" in class_name:
            return "openrouter"
        elif "copilot" in class_name:
            return "copilot"
        else:
            return "unknown"
    
    def get_unified_tools_schema(self) -> List[Dict[str, Any]]:
        if self.tool_registry:
            return self.tool_registry.get_llm_schemas(self.provider_name)
        else:
            return []  # Return empty list if tool registry not available
    
    def prepare_messages_for_provider(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.provider_name == "claude":
            # Claude needs special handling for system messages
            processed_messages = []
            for msg in messages:
                if msg.get("role") == "system":
                    # System messages will be handled separately in claude provider
                    processed_messages.append(msg)
                else:
                    processed_messages.append(msg)
            return processed_messages
        
        elif self.provider_name == "gemini":
            # Gemini uses "model" instead of "assistant"
            processed_messages = []
            for msg in messages:
                if msg.get("role") == "assistant":
                    processed_messages.append({**msg, "role": "model"})
                else:
                    processed_messages.append(msg)
            return processed_messages
        
        else:
            # OpenAI, Ollama, OpenRouter, Copilot use standard format
            return messages
    
    def create_unified_response(self, response: Any) -> ChatResponse:
        # Use the provider's existing conversion method
        if hasattr(self.provider, '_convert_ollama_response_to_songbird') and self.provider_name == "ollama":
            return self.provider._convert_ollama_response_to_songbird(response)
        elif hasattr(self.provider, '_convert_openai_response_to_songbird') and self.provider_name == "openai":
            return self.provider._convert_openai_response_to_songbird(response)
        elif hasattr(self.provider, '_convert_anthropic_response_to_songbird') and self.provider_name == "claude":
            return self.provider._convert_anthropic_response_to_songbird(response)
        elif hasattr(self.provider, '_convert_gemini_response_to_songbird') and self.provider_name == "gemini":
            return self.provider._convert_gemini_response_to_songbird(response)
        elif hasattr(self.provider, '_convert_openrouter_response_to_songbird') and self.provider_name == "openrouter":
            return self.provider._convert_openrouter_response_to_songbird(response)
        else:
            # Fallback for unknown providers
            return ChatResponse(
                content=str(response),
                model="unknown",
                usage=None,
                tool_calls=None
            )
    
    def get_provider_capabilities(self) -> Dict[str, Any]:
        """Get comprehensive provider capabilities information."""
        base_capabilities = {
            "provider_name": self.provider_name,
            "model_name": getattr(self.provider, 'model', 'unknown'),
            "supports_function_calling": True,
            "supports_streaming": False,
            "supports_usage_tracking": True,
            "max_context_length": self._get_max_context_length(),
            "tool_call_format": self._get_tool_call_format()
        }
        
        # Provider-specific capabilities
        if self.provider_name == "ollama":
            base_capabilities.update({
                "local_execution": True,
                "requires_api_key": False,
                "cost_per_token": 0.0
            })
        elif self.provider_name in ["openai", "claude", "gemini", "openrouter", "copilot"]:
            base_capabilities.update({
                "local_execution": False,
                "requires_api_key": True,
                "cost_per_token": "varies"
            })
        
        return base_capabilities
    
    def _get_max_context_length(self) -> int:
        """Get estimated max context length for the provider/model."""
        context_lengths = {
            "ollama": 8192,  # Varies by model
            "openai": 32768,  # GPT-4 turbo
            "claude": 200000,  # Claude 3.5 Sonnet
            "gemini": 32768,  # Gemini 2.0 Flash
            "openrouter": 32768,  # Varies by model
            "copilot": 32768  # GitHub Copilot models
        }
        return context_lengths.get(self.provider_name, 8192)
    
    def _get_tool_call_format(self) -> str:
        """Get the tool call format used by this provider."""
        if self.provider_name in ["openai", "ollama", "openrouter", "copilot"]:
            return "openai_tools"
        elif self.provider_name == "claude":
            return "anthropic_tools"
        elif self.provider_name == "gemini":
            return "gemini_functions"
        else:
            return "unknown"


def create_provider_adapter(provider_instance) -> ProviderAdapter:
    """Create a provider adapter for any provider instance."""
    return ProviderAdapter(provider_instance)