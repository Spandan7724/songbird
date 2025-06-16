"""LLM provider registry and base classes."""
from abc import ABC, abstractmethod
from typing import Dict, Type, List, Any, Optional
import os
import logging
import ollama

try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
    
    # Comprehensive warning suppression for Gemini SDK
    import warnings
    import sys
    
    # Suppress specific warnings
    warnings.filterwarnings("ignore", message=".*non-text parts.*")
    warnings.filterwarnings("ignore", message=".*function_call.*")
    
    # Redirect stderr temporarily to suppress print statements
    class SuppressWarnings:
        def __enter__(self):
            self._original_stderr = sys.stderr
            sys.stderr = open(os.devnull, 'w')
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            sys.stderr.close()
            sys.stderr = self._original_stderr
    
    # Set logging levels
    logging.getLogger('google.genai').setLevel(logging.CRITICAL)
    logging.getLogger('google.genai.types').setLevel(logging.CRITICAL)
    logging.getLogger().setLevel(logging.CRITICAL)
    
except ImportError:
    GEMINI_AVAILABLE = False

from .types import ChatResponse


class BaseProvider(ABC):
    """Base class for all LLM providers."""
    
    @abstractmethod
    def chat(self, message: str, tools: Optional[List[Dict[str, Any]]] = None) -> ChatResponse:
        """Send a chat message and return the response."""
        pass
    
    @abstractmethod
    def chat_with_messages(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> ChatResponse:
        """Send a conversation with multiple messages and return the response."""
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
    
    def chat_with_messages(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> ChatResponse:
        """Send a conversation with multiple messages to Ollama."""
        try:
            chat_args = {
                "model": self.model,
                "messages": messages
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


class GeminiProvider(BaseProvider):
    """Gemini provider using Google GenAI Python client."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.0-flash-001"):
        if not GEMINI_AVAILABLE:
            raise ImportError("google-genai package not installed. Run: pip install google-genai")
        
        self.model = model
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        
        if not self.api_key:
            raise ValueError("Gemini API key required. Set GOOGLE_API_KEY environment variable or pass api_key parameter")
        
        # Initialize the Gemini client
        self.client = genai.Client(api_key=self.api_key)
    
    def _convert_tools_to_gemini_format(self, tools: List[Dict[str, Any]]) -> List[genai_types.Tool]:
        """Convert Songbird tool schemas to Gemini function declarations."""
        gemini_tools = []
        
        for tool in tools:
            if tool["type"] == "function":
                func_info = tool["function"]
                
                # Convert parameters schema
                params = func_info.get("parameters", {})
                properties = params.get("properties", {})
                required = params.get("required", [])
                
                # Convert properties to Gemini schema format
                gemini_properties = {}
                for prop_name, prop_info in properties.items():
                    gemini_properties[prop_name] = genai_types.Schema(
                        type=prop_info["type"].upper(),
                        description=prop_info.get("description", "")
                    )
                
                # Create function declaration
                function_decl = genai_types.FunctionDeclaration(
                    name=func_info["name"],
                    description=func_info["description"],
                    parameters=genai_types.Schema(
                        type="OBJECT",
                        properties=gemini_properties,
                        required=required
                    )
                )
                
                gemini_tools.append(genai_types.Tool(function_declarations=[function_decl]))
        
        return gemini_tools
    
    def _convert_gemini_response_to_songbird(self, response) -> ChatResponse:
        """Convert Gemini response to Songbird ChatResponse format."""
        content = response.text or ""
        
        # Clean response processing (debug output removed)
        
        # Convert function calls if present
        tool_calls = None
        if hasattr(response, 'function_calls') and response.function_calls:
            tool_calls = []
            for func_call in response.function_calls:
                tool_calls.append({
                    "id": getattr(func_call, 'id', ""),
                    "function": {
                        "name": func_call.name,
                        "arguments": func_call.args
                    }
                })
        else:
            # Check if function calls are in candidates content parts (alternative location)
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate.content, 'parts'):
                    tool_calls = []
                    for part in candidate.content.parts:
                        if hasattr(part, 'function_call') and part.function_call:
                            tool_calls.append({
                                "id": getattr(part.function_call, 'id', ""),
                                "function": {
                                    "name": part.function_call.name,
                                    "arguments": part.function_call.args
                                }
                            })
                    
                    if not tool_calls:
                        tool_calls = None
        
        return ChatResponse(
            content=content,
            model=self.model,
            usage=getattr(response, 'usage_metadata', None),
            tool_calls=tool_calls
        )
    
    def chat(self, message: str, tools: Optional[List[Dict[str, Any]]] = None) -> ChatResponse:
        """Send a chat message to Gemini."""
        try:
            config_kwargs = {}
            
            # Add tools if provided
            if tools:
                gemini_tools = self._convert_tools_to_gemini_format(tools)
                config_kwargs["tools"] = gemini_tools
                # Disable automatic function calling to handle manually like Ollama
                config_kwargs["automatic_function_calling"] = genai_types.AutomaticFunctionCallingConfig(disable=True)
            
            config = genai_types.GenerateContentConfig(**config_kwargs) if config_kwargs else None
            
            response = self.client.models.generate_content(
                model=self.model,
                contents=message,
                config=config
            )
            
            return self._convert_gemini_response_to_songbird(response)
            
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Gemini: {e}")
    
    def chat_with_messages(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> ChatResponse:
            """Send a conversation with multiple messages to Gemini."""
            try:
                # Convert messages to Gemini format
                gemini_contents = []
                
                # Combine system messages with the first user message (Gemini doesn't have separate system role)
                system_content = ""
                
                for msg in messages:
                    role = msg["role"]
                    content = msg["content"]
                    
                    if role == "system":
                        # Accumulate system messages
                        system_content += content + "\n\n"
                    elif role == "user":
                        # If we have system content, prepend it to the first user message
                        if system_content and not gemini_contents:
                            content = system_content + content
                            system_content = ""  # Clear after using
                        
                        gemini_contents.append(genai_types.Content(
                            role="user",
                            parts=[genai_types.Part.from_text(text=content)]
                        ))
                    elif role == "assistant":
                        gemini_contents.append(genai_types.Content(
                            role="model",  # Gemini uses "model" instead of "assistant"
                            parts=[genai_types.Part.from_text(text=content)]
                        ))
                    # Skip tool messages for now - handle them differently if needed
                
                config_kwargs = {}
                
                # Add tools if provided
                if tools:
                    gemini_tools = self._convert_tools_to_gemini_format(tools)
                    config_kwargs["tools"] = gemini_tools
                    # Disable automatic function calling to handle manually like Ollama
                    config_kwargs["automatic_function_calling"] = genai_types.AutomaticFunctionCallingConfig(disable=True)
                
                config = genai_types.GenerateContentConfig(**config_kwargs) if config_kwargs else None
                
                # Suppress warnings during API call
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    response = self.client.models.generate_content(
                        model=self.model,
                        contents=gemini_contents,
                        config=config
                    )
                
                return self._convert_gemini_response_to_songbird(response)
                
            except Exception as e:
                raise ConnectionError(f"Failed to connect to Gemini: {e}")
# Provider registry
_providers: Dict[str, Type[BaseProvider]] = {
    "ollama": OllamaProvider,
}

# Add Gemini provider if available
if GEMINI_AVAILABLE:
    _providers["gemini"] = GeminiProvider


def get_provider(name: str) -> Type[BaseProvider]:
    """Get a provider class by name."""
    if name not in _providers:
        raise ValueError(f"Unknown provider: {name}")
    return _providers[name]


def list_available_providers() -> List[str]:
    """Get list of available provider names."""
    return list(_providers.keys())


def get_default_provider() -> str:
    """Get the default provider name."""
    # Prefer Gemini if available and API key is set, otherwise Ollama
    if GEMINI_AVAILABLE and os.getenv("GOOGLE_API_KEY"):
        return "gemini"
    return "ollama"