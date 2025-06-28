# songbird/llm/unified_interface.py
"""Unified interface for standardizing provider interactions and tool call formats."""

from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod

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


class UnifiedToolCall:
    """Standardized tool call format used internally by Songbird."""
    
    def __init__(self, id: str, function_name: str, arguments: Dict[str, Any]):
        self.id = id
        self.function_name = function_name
        self.arguments = arguments
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "id": self.id,
            "function": {
                "name": self.function_name,
                "arguments": self.arguments
            }
        }
    
    @classmethod
    def from_provider_format(cls, tool_call: Dict[str, Any], provider: str) -> 'UnifiedToolCall':
        """Create from provider-specific tool call format."""
        if provider in ["openai", "openrouter", "ollama"]:
            return cls(
                id=tool_call.get("id", ""),
                function_name=tool_call.get("function", {}).get("name", ""),
                arguments=tool_call.get("function", {}).get("arguments", {})
            )
        elif provider == "claude":
            return cls(
                id=tool_call.get("id", ""),
                function_name=tool_call.get("function", {}).get("name", ""),
                arguments=tool_call.get("function", {}).get("arguments", {})
            )
        elif provider == "gemini":
            return cls(
                id=tool_call.get("id", ""),
                function_name=tool_call.get("function", {}).get("name", ""),
                arguments=tool_call.get("function", {}).get("arguments", {})
            )
        else:
            raise ValueError(f"Unknown provider format: {provider}")


class UnifiedProviderInterface(ABC):
    """Unified interface that all providers should implement for consistency."""
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the provider name."""
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """Get the current model name."""
        pass
    
    @abstractmethod
    def format_tools_for_provider(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format tools for this provider's specific format."""
        pass
    
    @abstractmethod
    def parse_response_to_unified(self, response: Any) -> ChatResponse:
        """Parse provider response to unified ChatResponse format."""
        pass
    
    def get_supported_features(self) -> Dict[str, bool]:
        """Get supported features for this provider."""
        return {
            "function_calling": True,
            "streaming": False,
            "usage_tracking": True,
            "temperature_control": True,
            "max_tokens_control": True
        }


class ProviderAdapter:
    """Adapter that provides unified interface for all providers."""
    
    def __init__(self, provider_instance):
        self.provider = provider_instance
        self.provider_name = self._detect_provider_name()
        if TOOL_REGISTRY_AVAILABLE:
            self.tool_registry = get_tool_registry()
        else:
            self.tool_registry = None
    
    def _detect_provider_name(self) -> str:
        """Detect provider name from the instance."""
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
        else:
            return "unknown"
    
    def get_unified_tools_schema(self) -> List[Dict[str, Any]]:
        """Get tools formatted for the current provider."""
        if self.tool_registry:
            return self.tool_registry.get_llm_schemas(self.provider_name)
        else:
            return []  # Return empty list if tool registry not available
    
    def standardize_tool_calls(self, tool_calls: Optional[List[Dict[str, Any]]]) -> List[UnifiedToolCall]:
        """Convert provider-specific tool calls to unified format."""
        if not tool_calls:
            return []
        
        unified_calls = []
        for tool_call in tool_calls:
            try:
                unified_call = UnifiedToolCall.from_provider_format(tool_call, self.provider_name)
                unified_calls.append(unified_call)
            except Exception as e:
                # Log error but continue processing other tool calls
                print(f"Warning: Failed to standardize tool call: {e}")
                continue
        
        return unified_calls
    
    def prepare_messages_for_provider(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prepare messages for provider-specific format requirements."""
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
            # OpenAI, Ollama, OpenRouter use standard format
            return messages
    
    def create_unified_response(self, response: Any) -> ChatResponse:
        """Create a unified response from provider-specific response."""
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
        elif self.provider_name in ["openai", "claude", "gemini", "openrouter"]:
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
            "openrouter": 32768  # Varies by model
        }
        return context_lengths.get(self.provider_name, 8192)
    
    def _get_tool_call_format(self) -> str:
        """Get the tool call format used by this provider."""
        if self.provider_name in ["openai", "ollama", "openrouter"]:
            return "openai_tools"
        elif self.provider_name == "claude":
            return "anthropic_tools"
        elif self.provider_name == "gemini":
            return "gemini_functions"
        else:
            return "unknown"


class UnifiedProviderManager:
    """Manager for working with providers through a unified interface."""
    
    def __init__(self):
        self.adapters: Dict[str, ProviderAdapter] = {}
    
    def register_provider(self, provider_instance, alias: Optional[str] = None) -> ProviderAdapter:
        """Register a provider instance and return its adapter."""
        adapter = ProviderAdapter(provider_instance)
        key = alias or adapter.provider_name
        self.adapters[key] = adapter
        return adapter
    
    def get_adapter(self, provider_key: str) -> Optional[ProviderAdapter]:
        """Get a provider adapter by key."""
        return self.adapters.get(provider_key)
    
    def get_all_capabilities(self) -> Dict[str, Dict[str, Any]]:
        """Get capabilities for all registered providers."""
        return {
            key: adapter.get_provider_capabilities()
            for key, adapter in self.adapters.items()
        }
    
    def compare_providers(self) -> Dict[str, Any]:
        """Compare all registered providers across key metrics."""
        comparison = {
            "providers": [],
            "function_calling_support": {},
            "context_lengths": {},
            "local_vs_remote": {},
            "api_key_requirements": {}
        }
        
        for key, adapter in self.adapters.items():
            caps = adapter.get_provider_capabilities()
            comparison["providers"].append(key)
            comparison["function_calling_support"][key] = caps["supports_function_calling"]
            comparison["context_lengths"][key] = caps["max_context_length"]
            comparison["local_vs_remote"][key] = caps.get("local_execution", False)
            comparison["api_key_requirements"][key] = caps.get("requires_api_key", True)
        
        return comparison


# Global unified manager instance
_unified_manager = UnifiedProviderManager()


def get_unified_manager() -> UnifiedProviderManager:
    """Get the global unified provider manager."""
    return _unified_manager


def create_provider_adapter(provider_instance) -> ProviderAdapter:
    """Create a provider adapter for any provider instance."""
    return ProviderAdapter(provider_instance)