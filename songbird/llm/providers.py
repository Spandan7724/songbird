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

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import httpx  # noqa: F401
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

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


class OpenAIProvider(BaseProvider):
    """OpenAI provider using official OpenAI Python client."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o", base_url: Optional[str] = None):
        if not OPENAI_AVAILABLE:
            raise ImportError("openai package not installed. Run: pip install openai")
        
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY environment variable or pass api_key parameter")
        
        # Initialize the OpenAI client
        client_kwargs = {"api_key": self.api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        
        self.client = openai.OpenAI(**client_kwargs)
    
    def _convert_tools_to_openai_format(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert Songbird tool schemas to OpenAI function format."""
        openai_tools = []
        
        for tool in tools:
            if tool["type"] == "function":
                # OpenAI format is already compatible with our tool schema
                openai_tools.append(tool)
        
        return openai_tools
    
    def _convert_openai_response_to_songbird(self, response) -> ChatResponse:
        """Convert OpenAI response to Songbird ChatResponse format."""
        choice = response.choices[0]
        message = choice.message
        
        content = message.content or ""
        
        # Convert tool calls if present
        tool_calls = None
        if message.tool_calls:
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
        if response.usage:
            usage_dict = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        
        return ChatResponse(
            content=content,
            model=response.model,
            usage=usage_dict,
            tool_calls=tool_calls
        )
    
    def chat(self, message: str, tools: Optional[List[Dict[str, Any]]] = None) -> ChatResponse:
        """Send a chat message to OpenAI."""
        try:
            chat_kwargs = {
                "model": self.model,
                "messages": [{"role": "user", "content": message}]
            }
            
            # Add tools if provided
            if tools:
                openai_tools = self._convert_tools_to_openai_format(tools)
                chat_kwargs["tools"] = openai_tools
                chat_kwargs["tool_choice"] = "auto"
            
            response = self.client.chat.completions.create(**chat_kwargs)
            
            return self._convert_openai_response_to_songbird(response)
            
        except openai.AuthenticationError:
            raise ValueError("Invalid OpenAI API key")
        except openai.RateLimitError:
            raise ConnectionError("OpenAI rate limit exceeded")
        except openai.APIError as e:
            raise ConnectionError(f"OpenAI API error: {e}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to OpenAI: {e}")
    
    def chat_with_messages(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> ChatResponse:
        """Send a conversation with multiple messages to OpenAI."""
        try:
            chat_kwargs = {
                "model": self.model,
                "messages": messages
            }
            
            # Add tools if provided
            if tools:
                openai_tools = self._convert_tools_to_openai_format(tools)
                chat_kwargs["tools"] = openai_tools
                chat_kwargs["tool_choice"] = "auto"
            
            response = self.client.chat.completions.create(**chat_kwargs)
            
            return self._convert_openai_response_to_songbird(response)
            
        except openai.AuthenticationError:
            raise ValueError("Invalid OpenAI API key")
        except openai.RateLimitError:
            raise ConnectionError("OpenAI rate limit exceeded")
        except openai.APIError as e:
            raise ConnectionError(f"OpenAI API error: {e}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to OpenAI: {e}")


class ClaudeProvider(BaseProvider):
    """Anthropic Claude provider using official Anthropic Python client."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-5-sonnet-20241022"):
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")
        
        self.model = model
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        
        if not self.api_key:
            raise ValueError("Anthropic API key required. Set ANTHROPIC_API_KEY environment variable or pass api_key parameter")
        
        # Initialize the Anthropic client
        self.client = anthropic.Anthropic(api_key=self.api_key)
    
    def _convert_tools_to_anthropic_format(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert Songbird tool schemas to Anthropic format."""
        anthropic_tools = []
        
        for tool in tools:
            if tool["type"] == "function":
                func_info = tool["function"]
                anthropic_tools.append({
                    "name": func_info["name"],
                    "description": func_info["description"],
                    "input_schema": func_info.get("parameters", {})
                })
        
        return anthropic_tools
    
    def _convert_anthropic_response_to_songbird(self, response) -> ChatResponse:
        """Convert Anthropic response to Songbird ChatResponse format."""
        # Extract text content
        content = ""
        tool_calls = None
        
        if hasattr(response, 'content') and response.content:
            tool_calls = []
            for block in response.content:
                if hasattr(block, 'type'):
                    if block.type == "text":
                        content += block.text
                    elif block.type == "tool_use":
                        tool_calls.append({
                            "id": block.id,
                            "function": {
                                "name": block.name,
                                "arguments": block.input
                            }
                        })
            
            if not tool_calls:
                tool_calls = None
        
        # Convert usage information
        usage_dict = None
        if hasattr(response, 'usage') and response.usage:
            usage_dict = {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            }
        
        return ChatResponse(
            content=content,
            model=response.model if hasattr(response, 'model') else self.model,
            usage=usage_dict,
            tool_calls=tool_calls
        )
    
    def chat(self, message: str, tools: Optional[List[Dict[str, Any]]] = None) -> ChatResponse:
        """Send a chat message to Claude."""
        try:
            message_kwargs = {
                "model": self.model,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": message}]
            }
            
            # Add tools if provided
            if tools:
                anthropic_tools = self._convert_tools_to_anthropic_format(tools)
                message_kwargs["tools"] = anthropic_tools
            
            response = self.client.messages.create(**message_kwargs)
            
            return self._convert_anthropic_response_to_songbird(response)
            
        except anthropic.AuthenticationError:
            raise ValueError("Invalid Anthropic API key")
        except anthropic.RateLimitError:
            raise ConnectionError("Anthropic rate limit exceeded")
        except anthropic.APIError as e:
            raise ConnectionError(f"Anthropic API error: {e}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Claude: {e}")
    
    def chat_with_messages(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> ChatResponse:
        """Send a conversation with multiple messages to Claude."""
        try:
            # Filter out system messages and combine them into a system parameter
            system_messages = []
            chat_messages = []
            
            for msg in messages:
                if msg["role"] == "system":
                    system_messages.append(msg["content"])
                else:
                    chat_messages.append(msg)
            
            message_kwargs = {
                "model": self.model,
                "max_tokens": 4096,
                "messages": chat_messages
            }
            
            # Add system message if present
            if system_messages:
                message_kwargs["system"] = "\n\n".join(system_messages)
            
            # Add tools if provided
            if tools:
                anthropic_tools = self._convert_tools_to_anthropic_format(tools)
                message_kwargs["tools"] = anthropic_tools
            
            response = self.client.messages.create(**message_kwargs)
            
            return self._convert_anthropic_response_to_songbird(response)
            
        except anthropic.AuthenticationError:
            raise ValueError("Invalid Anthropic API key")
        except anthropic.RateLimitError:
            raise ConnectionError("Anthropic rate limit exceeded")
        except anthropic.APIError as e:
            raise ConnectionError(f"Anthropic API error: {e}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Claude: {e}")


class OpenRouterProvider(BaseProvider):
    """OpenRouter provider for accessing multiple models via OpenRouter API."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "deepseek/deepseek-chat-v3-0324:free"):
        if not OPENAI_AVAILABLE:
            raise ImportError("openai package not installed (required for OpenRouter). Run: pip install openai")
        
        self.model = model
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        
        if not self.api_key:
            raise ValueError("OpenRouter API key required. Set OPENROUTER_API_KEY environment variable or pass api_key parameter")
        
        # Initialize OpenAI client with OpenRouter base URL
        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url="https://openrouter.ai/api/v1"
        )
    
    def _convert_tools_to_openai_format(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert Songbird tool schemas to OpenAI function format."""
        openai_tools = []
        
        for tool in tools:
            if tool["type"] == "function":
                # OpenAI format is already compatible with our tool schema
                openai_tools.append(tool)
        
        return openai_tools
    
    def _convert_openrouter_response_to_songbird(self, response) -> ChatResponse:
        """Convert OpenRouter response to Songbird ChatResponse format."""
        choice = response.choices[0]
        message = choice.message
        
        content = message.content or ""
        
        # Convert tool calls if present
        tool_calls = None
        if message.tool_calls:
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
        if response.usage:
            usage_dict = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        
        return ChatResponse(
            content=content,
            model=response.model,
            usage=usage_dict,
            tool_calls=tool_calls
        )
    
    def chat(self, message: str, tools: Optional[List[Dict[str, Any]]] = None) -> ChatResponse:
        """Send a chat message to OpenRouter."""
        try:
            chat_kwargs = {
                "model": self.model,
                "messages": [{"role": "user", "content": message}]
            }
            
            # Add tools if provided (note: not all OpenRouter models support function calling)
            if tools:
                openai_tools = self._convert_tools_to_openai_format(tools)
                chat_kwargs["tools"] = openai_tools
                chat_kwargs["tool_choice"] = "auto"
            
            response = self.client.chat.completions.create(**chat_kwargs)
            
            return self._convert_openrouter_response_to_songbird(response)
            
        except openai.AuthenticationError:
            raise ValueError("Invalid OpenRouter API key")
        except openai.RateLimitError:
            raise ConnectionError("OpenRouter rate limit exceeded")
        except openai.APIError as e:
            raise ConnectionError(f"OpenRouter API error: {e}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to OpenRouter: {e}")
    
    def chat_with_messages(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> ChatResponse:
        """Send a conversation with multiple messages to OpenRouter."""
        try:
            chat_kwargs = {
                "model": self.model,
                "messages": messages
            }
            
            # Add tools if provided (note: not all OpenRouter models support function calling)
            if tools:
                openai_tools = self._convert_tools_to_openai_format(tools)
                chat_kwargs["tools"] = openai_tools
                chat_kwargs["tool_choice"] = "auto"
            
            response = self.client.chat.completions.create(**chat_kwargs)
            
            return self._convert_openrouter_response_to_songbird(response)
            
        except openai.AuthenticationError:
            raise ValueError("Invalid OpenRouter API key")
        except openai.RateLimitError:
            raise ConnectionError("OpenRouter rate limit exceeded")
        except openai.APIError as e:
            raise ConnectionError(f"OpenRouter API error: {e}")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to OpenRouter: {e}")


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
                    gemini_properties[prop_name] = self._convert_property_to_gemini_schema(prop_info)
                
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

    def _convert_property_to_gemini_schema(self, prop_info: Dict[str, Any]) -> genai_types.Schema:
        """Convert a single property schema to Gemini format, handling nested objects and arrays."""
        prop_type = prop_info["type"].upper()
        description = prop_info.get("description", "")
        
        schema_kwargs = {
            "type": prop_type,
            "description": description
        }
        
        # Handle array items
        if prop_type == "ARRAY" and "items" in prop_info:
            items_schema = prop_info["items"]
            schema_kwargs["items"] = self._convert_property_to_gemini_schema(items_schema)
        
        # Handle object properties (nested objects)
        elif prop_type == "OBJECT" and "properties" in prop_info:
            nested_properties = {}
            for nested_prop_name, nested_prop_info in prop_info["properties"].items():
                nested_properties[nested_prop_name] = self._convert_property_to_gemini_schema(nested_prop_info)
            schema_kwargs["properties"] = nested_properties
            
            # Handle required fields for nested objects
            if "required" in prop_info:
                schema_kwargs["required"] = prop_info["required"]
        
        # Handle enum values
        if "enum" in prop_info:
            schema_kwargs["enum"] = prop_info["enum"]
        
        return genai_types.Schema(**schema_kwargs)
    
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
                if hasattr(candidate, 'content') and candidate.content and hasattr(candidate.content, 'parts') and candidate.content.parts:
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

# Add OpenAI provider if available
if OPENAI_AVAILABLE:
    _providers["openai"] = OpenAIProvider

# Add Anthropic provider if available
if ANTHROPIC_AVAILABLE:
    _providers["claude"] = ClaudeProvider

# Add OpenRouter provider if available (uses OpenAI library)
if OPENAI_AVAILABLE:
    _providers["openrouter"] = OpenRouterProvider

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
    # Provider priority: Gemini > Claude > OpenAI > OpenRouter > Ollama
    # Check for API keys to determine availability
    if GEMINI_AVAILABLE and os.getenv("GOOGLE_API_KEY"):
        return "gemini"
    elif ANTHROPIC_AVAILABLE and os.getenv("ANTHROPIC_API_KEY"):
        return "claude"
    elif OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
        return "openai"
    elif OPENAI_AVAILABLE and os.getenv("OPENROUTER_API_KEY"):
        return "openrouter"
    else:
        return "ollama"


def get_provider_info() -> Dict[str, Dict[str, Any]]:
    """Get information about all available providers."""
    provider_info = {}
    
    for name in _providers.keys():
        info = {"available": True, "models": [], "api_key_env": None}
        
        if name == "ollama":
            # Dynamic for Ollama - try to get actual models
            try:
                import requests
                response = requests.get("http://localhost:11434/api/tags", timeout=2)
                if response.status_code == 200:
                    models = response.json().get('models', [])
                    info["models"] = [model['name'] for model in models[:5]]  # Limit to first 5
                else:
                    info["models"] = ["qwen2.5-coder:7b", "devstral:latest", "llama3.2:latest"]
            except Exception:
                info["models"] = ["qwen2.5-coder:7b", "devstral:latest", "llama3.2:latest"]
            
            info["api_key_env"] = None
            info["description"] = "Local Ollama models"
            
        elif name == "gemini":
            info["models"] = ["gemini-2.0-flash-001", "gemini-1.5-pro", "gemini-1.5-flash"]
            info["api_key_env"] = "GOOGLE_API_KEY"
            info["description"] = "Google Gemini AI models"
            info["available"] = GEMINI_AVAILABLE and bool(os.getenv("GOOGLE_API_KEY"))
            
        elif name == "openai":
            # Dynamic for OpenAI - try to get actual models
            if OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
                try:
                    import openai
                    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                    models_response = client.models.list()
                    
                    chat_models = []
                    for model in models_response.data:
                        if any(prefix in model.id for prefix in ["gpt-4", "gpt-3.5"]):
                            chat_models.append(model.id)
                    
                    info["models"] = sorted(chat_models)[:5] if chat_models else ["gpt-4o", "gpt-4o-mini"]
                except Exception:
                    info["models"] = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]
            else:
                info["models"] = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]
                
            info["api_key_env"] = "OPENAI_API_KEY"
            info["description"] = "OpenAI GPT models"
            info["available"] = OPENAI_AVAILABLE and bool(os.getenv("OPENAI_API_KEY"))
            
        elif name == "claude":
            # Claude doesn't have a models API, so keep hardcoded
            info["models"] = ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"]
            info["api_key_env"] = "ANTHROPIC_API_KEY"
            info["description"] = "Anthropic Claude models"
            info["available"] = ANTHROPIC_AVAILABLE and bool(os.getenv("ANTHROPIC_API_KEY"))
            
        elif name == "openrouter":
            # Dynamic for OpenRouter - fetch tool-capable models from API
            if OPENAI_AVAILABLE and os.getenv("OPENROUTER_API_KEY"):
                try:
                    import httpx
                    headers = {
                        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
                        "Content-Type": "application/json"
                    }
                    response = httpx.get("https://openrouter.ai/api/v1/models", headers=headers, timeout=5.0)
                    
                    if response.status_code == 200:
                        models_data = response.json()
                        
                        # Filter for models that support tools
                        tool_capable_models = []
                        for model in models_data.get("data", []):
                            model_id = model.get("id", "")
                            supported_parameters = model.get("supported_parameters", [])
                            
                            # Only include models that have "tools" in their supported_parameters
                            if model_id and supported_parameters and "tools" in supported_parameters:
                                tool_capable_models.append(model_id)
                        
                        # For provider info, show first few tool-capable models as examples
                        if tool_capable_models:
                            info["models"] = tool_capable_models[:5] 
                        else:
                            info["models"] = ["No tool-capable models found"]
                    else:
                        info["models"] = [f"API error: {response.status_code}"]
                except Exception as e:
                    info["models"] = [f"Error: {str(e)[:30]}..."]
            else:
                info["models"] = ["deepseek/deepseek-chat-v3-0324:free", "anthropic/claude-3.5-sonnet", "openai/gpt-4o"]
                
            info["api_key_env"] = "OPENROUTER_API_KEY"
            info["description"] = "OpenRouter (access to multiple providers)"
            info["available"] = OPENAI_AVAILABLE and bool(os.getenv("OPENROUTER_API_KEY"))
        
        provider_info[name] = info
    
    return provider_info