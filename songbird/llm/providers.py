"""LLM provider registry and unified LiteLLM interface."""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import os
from rich.console import Console

from .types import ChatResponse
from .copilot_provider import CopilotProvider

# LiteLLM availability check
try:
    import litellm
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False

console = Console()


class BaseProvider(ABC):
    
    @abstractmethod
    def chat(self, message: str, tools: Optional[List[Dict[str, Any]]] = None) -> ChatResponse:
        pass
    
    @abstractmethod
    async def chat_with_messages(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> ChatResponse:
        """Send a conversation with multiple messages and return the response."""
        pass


# LiteLLM unified provider functions
def create_litellm_provider(provider_name: str, model: str = None, api_base: str = None, **kwargs):
    if not LITELLM_AVAILABLE:
        raise ImportError("LiteLLM is not installed. Install with: pip install litellm")
    
    from .litellm_adapter import LiteLLMAdapter
    from ..config.mapping_loader import load_provider_mapping
    
    # Load configuration
    config = load_provider_mapping()
    
    # If a model is provided, use it directly. Otherwise, get the default.
    model_to_use = model or config.get_default_model(provider_name)
    
    # Handle API base URL priority
    effective_api_base = api_base or config.get_api_base(provider_name)
    
    # Create adapter with optional API base override
    adapter = LiteLLMAdapter(
        provider_name=provider_name,  # Pass provider name to ensure correct prefix
        model=model_to_use,
        api_base=effective_api_base,
        **kwargs
    )
    return adapter


def get_copilot_provider(model: str = None, quiet: bool = False, **kwargs):
    if not model:
        model = "gpt-4o"  # Default model for Copilot
    
    try:
        provider = CopilotProvider(model=model, **kwargs)
        if not quiet:
            console.print(f"[dim]✓ COPILOT_ACCESS_TOKEN configured: {os.getenv('COPILOT_ACCESS_TOKEN', 'Not set')[:10]}...{os.getenv('COPILOT_ACCESS_TOKEN', '')[-4:] if os.getenv('COPILOT_ACCESS_TOKEN') else ''}[/dim]")
        return provider
    except Exception as e:
        if not quiet:
            console.print(f"[red]Failed to initialize GitHub Copilot provider: {e}[/red]")
        raise e


def get_litellm_provider(provider_name: str, model: str = None, api_base: str = None, **kwargs):
    # Special handling for GitHub Copilot
    if provider_name == "copilot":
        return get_copilot_provider(model, **kwargs)
    
    if not LITELLM_AVAILABLE:
        raise ImportError("LiteLLM is required but not installed. Install with: pip install litellm")
    
    return create_litellm_provider(provider_name, model, api_base, **kwargs)





def get_provider(name: str, use_litellm: bool = True) -> BaseProvider:
    return get_litellm_provider(name)


def get_default_provider_name():
    try:
        from ..config.config_manager import get_config_manager
        
        # Get configured default provider
        config_manager = get_config_manager()
        config = config_manager.get_config()
        configured_default = config.llm.default_provider
        
        # Check if configured default is available (has API key/service)
        if configured_default:
            api_key_map = {
                "gemini": "GEMINI_API_KEY",
                "claude": "ANTHROPIC_API_KEY", 
                "openai": "OPENAI_API_KEY",
                "copilot": "COPILOT_ACCESS_TOKEN",
                "openrouter": "OPENROUTER_API_KEY",
                "ollama": None  # No API key needed
            }
            
            required_key = api_key_map.get(configured_default)
            if required_key is None or os.getenv(required_key):
                # For ollama, also check if service is running
                if configured_default == "ollama":
                    try:
                        import requests
                        response = requests.get("http://localhost:11434/api/version", timeout=2)
                        if response.status_code == 200:
                            return configured_default
                    except Exception:
                        pass  # Ollama not running, fall back to priority logic
                else:
                    return configured_default
    
    except Exception:
        # If config loading fails, fall back to original priority logic
        pass
    
    # Fallback to original priority-based selection
    providers_priority = ["gemini", "claude", "openai", "copilot", "openrouter", "ollama"]
    
    for provider in providers_priority:
        try:
            if provider == "gemini" and os.getenv("GEMINI_API_KEY"):
                return "gemini"
            elif provider == "claude" and os.getenv("ANTHROPIC_API_KEY"):
                return "claude"
            elif provider == "openai" and os.getenv("OPENAI_API_KEY"):
                return "openai"
            elif provider == "copilot" and os.getenv("COPILOT_ACCESS_TOKEN"):
                return "copilot"
            elif provider == "openrouter" and os.getenv("OPENROUTER_API_KEY"):
                return "openrouter"
            elif provider == "ollama":
                # Ollama doesn't need API key, just return it as default
                return "ollama"
        except Exception:
            continue
    
    # Fallback to ollama if nothing else is available
    return "ollama"


def get_default_provider():
    provider_name = get_default_provider_name()
    return get_litellm_provider(provider_name)


def list_available_providers() -> List[str]:
    return ["openai", "claude", "gemini", "ollama", "openrouter"]


def list_ready_providers() -> List[str]:
    ready_providers = []
    
    # Check each provider for API key availability
    if os.getenv("GEMINI_API_KEY"):
        ready_providers.append("gemini")
    if os.getenv("ANTHROPIC_API_KEY"):
        ready_providers.append("claude")
    if os.getenv("OPENAI_API_KEY"):
        ready_providers.append("openai")
    if os.getenv("OPENROUTER_API_KEY"):
        ready_providers.append("openrouter")
    
    # Ollama is always available if running
    try:
        get_litellm_provider("ollama")
        ready_providers.append("ollama")
    except Exception:
        pass
    
    return ready_providers


def get_provider_info(use_discovery: bool = True, quiet: bool = False) -> Dict[str, Dict[str, Any]]:
    provider_info = {}
    
    # Static provider configuration
    providers = {
        "openai": {
            "api_key_env": "OPENAI_API_KEY",
            "fallback_models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]
        },
        "claude": {
            "api_key_env": "ANTHROPIC_API_KEY",
            "fallback_models": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"]
        },
        "gemini": {
            "api_key_env": "GEMINI_API_KEY",
            "fallback_models": ["gemini-2.0-flash-001", "gemini-1.5-pro", "gemini-1.5-flash"]
        },
        "openrouter": {
            "api_key_env": "OPENROUTER_API_KEY",
            "fallback_models": ["anthropic/claude-3.5-sonnet", "openai/gpt-4o", "meta-llama/llama-3.2-90b-vision-instruct"]
        },
        "ollama": {
            "api_key_env": None,
            "fallback_models": ["qwen2.5-coder:7b", "devstral:latest", "llama3.2:latest"]
        },
        "copilot": {
            "api_key_env": "COPILOT_ACCESS_TOKEN",
            "fallback_models": ["gpt-4o", "gpt-4o-mini", "claude-3.5-sonnet"]
        }
    }
    
    # Get models using discovery service if enabled
    discovered_models = {}
    if use_discovery:
        try:
            from ..discovery import get_discovery_service
            import asyncio
            
            # Try to discover models for all providers
            discovery_service = get_discovery_service()
            
            # Try to run discovery, handling event loop issues
            try:
                # Check if we're already in an event loop
                try:
                    loop = asyncio.get_running_loop()
                    # We're in an event loop, skip discovery for now
                    if not quiet:
                        console.print("[dim]Skipping discovery (in event loop), using fallback models[/dim]")
                    discovered_models = {}
                except RuntimeError:
                    # No event loop running, safe to create one
                    def run_discovery():
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            return loop.run_until_complete(discovery_service.discover_all_models(use_cache=True))
                        except Exception as e:
                            console.print(f"[yellow]Discovery failed: {e}[/yellow]")
                            return {}
                        finally:
                            loop.close()
                    
                    discovered_models = run_discovery()
            except Exception as e:
                console.print(f"[yellow]Discovery setup failed: {e}[/yellow]")
                discovered_models = {}
            
        except Exception as e:
            console.print(f"[yellow]Model discovery unavailable: {e}[/yellow]")
            discovered_models = {}
    
    # Build provider info with discovered or fallback models
    for name, info in providers.items():
        # Use discovered models if available, otherwise fall back to static list
        if name in discovered_models and discovered_models[name]:
            models = [model.id for model in discovered_models[name]]
            if not quiet:
                console.print(f"[dim]Using {len(models)} discovered models for {name}[/dim]")
        else:
            models = info["fallback_models"]
            if not quiet:
                console.print(f"[dim]Using {len(models)} fallback models for {name}[/dim]")
        
        provider_info[name] = {
            "available": True,
            "models": models,
            "api_key_env": info["api_key_env"],
            "ready": (info["api_key_env"] is None) or bool(os.getenv(info["api_key_env"])),
            "models_discovered": name in discovered_models and bool(discovered_models[name])
        }
    
    return provider_info


async def get_models_for_provider(provider_name: str, use_cache: bool = True) -> List[str]:
    try:
        from ..discovery import get_discovery_service
        
        discovery_service = get_discovery_service()
        discovered_models = await discovery_service.discover_models(provider_name, use_cache=use_cache)
        
        if discovered_models:
            return [model.id for model in discovered_models]
        else:
            # Fall back to static lists
            fallback_models = {
                "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
                "claude": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"],
                "gemini": ["gemini-2.0-flash-001", "gemini-1.5-pro", "gemini-1.5-flash"],
                "openrouter": ["anthropic/claude-3.5-sonnet", "openai/gpt-4o", "meta-llama/llama-3.2-90b-vision-instruct"],
                "ollama": ["qwen2.5-coder:7b", "devstral:latest", "llama3.2:latest"],
                "copilot": ["gpt-4o", "gpt-4o-mini", "claude-3.5-sonnet"]
            }
            return fallback_models.get(provider_name, [])
            
    except Exception as e:
        console.print(f"[yellow]Failed to get models for {provider_name}: {e}[/yellow]")
        return []


def invalidate_model_cache(provider_name: Optional[str] = None):
    """Invalidate the model discovery cache for a specific provider or all providers."""
    try:
        from ..discovery import get_discovery_service
        
        discovery_service = get_discovery_service()
        discovery_service.invalidate_cache(provider_name)
        
        if provider_name:
            console.print(f"[dim]Model cache invalidated for {provider_name}[/dim]")
        else:
            console.print("[dim]Model cache invalidated for all providers[/dim]")
            
    except Exception as e:
        console.print(f"[yellow]Failed to invalidate cache: {e}[/yellow]")