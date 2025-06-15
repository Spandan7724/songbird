"""LLM provider registry and base classes."""
from abc import ABC, abstractmethod
from typing import Dict, Type, List, Any, Optional
import ollama

from .types import ChatResponse


class BaseProvider(ABC):
    """Base class for all LLM providers."""
    
    @abstractmethod
    def chat(self, message: str, tools: Optional[List[Dict[str, Any]]] = None) -> ChatResponse:
        """Send a chat message and return the response."""
        pass


class OllamaProvider(BaseProvider):
    """Ollama provider using official Ollama Python client."""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2"):
        self.base_url = base_url
        self.model = model
        self.client = ollama.Client(host=base_url)
    
    def chat(self, message: str, tools: Optional[List[Dict[str, Any]]] = None) -> ChatResponse:
        """Send a chat message to Ollama."""
        try:
            chat_args = {
                "model": self.model,
                "messages": [{"role": "user", "content": message}]
            }
            
            # Add tools if provided (Ollama supports function calling)
            if tools:
                chat_args["tools"] = tools
            
            response = self.client.chat(**chat_args)
            
            return ChatResponse(
                content=response['message']['content'],
                model=response.get('model'),
                usage=response.get('usage'),
                tool_calls=response['message'].get('tool_calls')
            )
            
        except ollama.ResponseError as e:
            if e.status_code == 404:
                raise ValueError(f"Model '{self.model}' not found. Try running: ollama pull {self.model}")
            raise ConnectionError(f"Ollama error: {e.error}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Ollama: {e}")


# Provider registry
_providers: Dict[str, Type[BaseProvider]] = {
    "ollama": OllamaProvider,
}


def get_provider(name: str) -> Type[BaseProvider]:
    """Get a provider class by name."""
    if name not in _providers:
        raise ValueError(f"Unknown provider: {name}")
    return _providers[name]