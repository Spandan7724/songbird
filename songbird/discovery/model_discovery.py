"""Dynamic model discovery service for all LLM providers."""

import asyncio
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Optional
from rich.console import Console

console = Console()
logger = logging.getLogger(__name__)


@dataclass
class DiscoveredModel:
    """Represents a discovered model with its capabilities."""
    id: str
    name: str
    provider: str
    supports_function_calling: bool = True
    supports_streaming: bool = True
    context_length: Optional[int] = None
    description: Optional[str] = None
    pricing_per_token: Optional[float] = None
    created: Optional[str] = None
    
    @property
    def display_name(self) -> str:
        """Get a human-readable display name."""
        if self.description:
            return f"{self.name} ({self.description})"
        return self.name
    
    @property
    def litellm_id(self) -> str:
        """Get the LiteLLM model identifier."""
        if "/" in self.id:
            return self.id  # Already in LiteLLM format
        return f"{self.provider}/{self.id}"


class BaseModelDiscovery(ABC):
    """Abstract base class for provider-specific model discovery."""
    
    def __init__(self, provider_name: str, timeout: float = 3.0):
        self.provider_name = provider_name
        self.timeout = timeout
        self._cache: List[DiscoveredModel] = []
        self._cache_timestamp = 0
        self._cache_ttl = 300  # 5 minutes
    
    @abstractmethod
    async def _discover_models(self) -> List[DiscoveredModel]:
        pass
    
    def _get_fallback_models(self) -> List[DiscoveredModel]:
        fallbacks = {
            "openai": [
                DiscoveredModel("gpt-4o", "GPT-4o", "openai", context_length=128000),
                DiscoveredModel("gpt-4o-mini", "GPT-4o Mini", "openai", context_length=128000),
                DiscoveredModel("gpt-4-turbo", "GPT-4 Turbo", "openai", context_length=128000),
                DiscoveredModel("gpt-3.5-turbo", "GPT-3.5 Turbo", "openai", context_length=16000),
            ],
            "claude": [
                DiscoveredModel("claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet", "anthropic", context_length=200000),
                DiscoveredModel("claude-3-5-haiku-20241022", "Claude 3.5 Haiku", "anthropic", context_length=200000),
                DiscoveredModel("claude-3-opus-20240229", "Claude 3 Opus", "anthropic", context_length=200000),
            ],
            "gemini": [
                DiscoveredModel("gemini-2.0-flash", "Gemini 2.0 Flash", "gemini", context_length=1000000),
                DiscoveredModel("gemini-2.0-flash-001", "Gemini 2.0 Flash", "gemini", context_length=1000000),
                DiscoveredModel("gemini-1.5-flash", "Gemini 1.5 Flash", "gemini", context_length=1000000),
                DiscoveredModel("gemini-1.5-flash-002", "Gemini 1.5 Flash", "gemini", context_length=1000000),
                DiscoveredModel("gemini-2.5-flash", "Gemini 2.5 Flash", "gemini", context_length=1000000),
                DiscoveredModel("gemini-1.5-flash-8b", "Gemini 1.5 Flash 8B", "gemini", context_length=1000000),
            ],
            "ollama": [
                DiscoveredModel("qwen2.5-coder:7b", "Qwen2.5 Coder 7B", "ollama"),
                DiscoveredModel("llama3.2:latest", "Llama 3.2", "ollama"),
                DiscoveredModel("codellama:latest", "Code Llama", "ollama"),
            ],
            "openrouter": [
                DiscoveredModel("anthropic/claude-3.5-sonnet", "Claude 3.5 Sonnet", "openrouter"),
                DiscoveredModel("openai/gpt-4o", "GPT-4o", "openrouter"),
                DiscoveredModel("google/gemini-2.0-flash-001", "Gemini 2.0 Flash", "openrouter"),
            ],
            "copilot": [
                DiscoveredModel("gpt-4o", "GPT-4o", "copilot", context_length=128000),
                DiscoveredModel("gpt-4o-mini", "GPT-4o Mini", "copilot", context_length=128000),
                DiscoveredModel("claude-3.5-sonnet", "Claude 3.5 Sonnet", "copilot", context_length=200000),
            ]
        }
        return fallbacks.get(self.provider_name, [])
    
    async def discover_models(self, use_cache: bool = True) -> List[DiscoveredModel]:
        """Discover models with caching and fallback support."""
        # Check cache first
        if use_cache and self._is_cache_valid():
            logger.debug(f"Using cached models for {self.provider_name}")
            return self._cache
        
        try:
            # Try to discover models
            logger.debug(f"Discovering models for {self.provider_name}")
            models = await asyncio.wait_for(self._discover_models(), timeout=self.timeout)
            
            # Update cache
            self._cache = models
            self._cache_timestamp = time.time()
            
            logger.debug(f"Discovered {len(models)} models for {self.provider_name}")
            return models
            
        except asyncio.TimeoutError:
            logger.warning(f"Model discovery timeout for {self.provider_name}, using fallback")
        except Exception as e:
            logger.warning(f"Model discovery failed for {self.provider_name}: {e}, using fallback")
        
        # Fall back to hardcoded models
        fallback_models = self._get_fallback_models()
        logger.debug(f"Using {len(fallback_models)} fallback models for {self.provider_name}")
        return fallback_models
    
    def _is_cache_valid(self) -> bool:
        if not self._cache:
            return False
        return (time.time() - self._cache_timestamp) < self._cache_ttl
    
    def invalidate_cache(self):
        self._cache = []
        self._cache_timestamp = 0


class OpenAIModelDiscovery(BaseModelDiscovery):
    
    async def _discover_models(self) -> List[DiscoveredModel]:
        import os
        
        # Check if API key is available
        if not os.getenv("OPENAI_API_KEY"):
            logger.debug("No OPENAI_API_KEY found, using fallback models")
            return self._get_fallback_models()
        
        try:
            import openai
            
            # Get available models
            client = openai.OpenAI()
            models_response = await asyncio.to_thread(client.models.list)
            
            discovered_models = []
            # Filter for relevant models that support chat completion
            relevant_models = [
                model for model in models_response.data
                if any(keyword in model.id.lower() for keyword in ['gpt', 'davinci', 'babbage', 'ada'])
                and not any(exclude in model.id.lower() for exclude in ['instruct', 'edit', 'embedding', 'whisper', 'tts', 'dall-e'])
            ]
            
            for model in relevant_models:
                discovered_models.append(DiscoveredModel(
                    id=model.id,
                    name=model.id.replace('-', ' ').title(),
                    provider="openai",
                    supports_function_calling=True,
                    supports_streaming=True,
                    created=model.created if hasattr(model, 'created') else None
                ))
            
            # Sort by creation date (newest first) and return all
            if discovered_models:
                discovered_models.sort(key=lambda x: x.created or 0, reverse=True)
                return discovered_models
            
        except Exception as e:
            logger.debug(f"OpenAI API discovery failed: {e}")
        
        return self._get_fallback_models()


class GeminiModelDiscovery(BaseModelDiscovery):
    """Gemini model discovery using Google's API."""
    
    async def _discover_models(self) -> List[DiscoveredModel]:
        """Discover Gemini models via Google API."""
        import os
        
        # Check if API key is available
        if not os.getenv("GEMINI_API_KEY"):
            logger.debug("No GEMINI_API_KEY found, using fallback models")
            return self._get_fallback_models()
        
        try:
            import google.generativeai as genai
            
            # Configure the API
            genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
            
            # Get available models
            models_response = await asyncio.to_thread(genai.list_models)
            
            discovered_models = []
            for model in models_response:
                # Only include models that support generateContent
                if hasattr(model, 'supported_generation_methods') and \
                   'generateContent' in model.supported_generation_methods:
                    
                    model_id = model.name.split('/')[-1]  # Extract model ID from full name
                    
                    # Skip models that actually fail in LiteLLM (based on compatibility test)
                    failed_models = {
                        'gemini-1.0-pro-vision-latest', 'gemini-1.5-pro', 'gemini-1.5-pro-002', 
                        'gemini-1.5-pro-latest', 'gemini-2.0-flash-live-001', 
                        'gemini-2.0-flash-preview-image-generation', 'gemini-2.0-pro-exp',
                        'gemini-2.5-flash-exp-native-audio-thinking-dialog', 'gemini-2.0-pro-exp-02-05',
                        'gemini-2.5-flash-preview-native-audio-dialog', 'gemini-2.5-pro-preview-06-05',
                        'gemini-2.5-pro-preview-tts', 'gemini-2.5-flash-preview-tts', 'gemini-2.5-pro',
                        'gemini-2.5-pro-preview-05-06', 'gemini-2.5-pro-preview-03-25', 'gemini-exp-1206',
                        'gemini-live-2.5-flash-preview', 'gemini-pro-vision', 'gemini-embedding-exp',
                        'gemini-embedding-exp-03-07'
                        # Note: gemini-2.0-flash-001 and other -001 models ARE working
                    }
                    
                    if model_id in failed_models:
                        continue
                    
                    # Skip if we already have this model
                    if any(m.id == model_id for m in discovered_models):
                        continue
                    
                    discovered_models.append(DiscoveredModel(
                        id=model_id,
                        name=model.display_name if hasattr(model, 'display_name') else model_id,
                        provider="gemini",
                        supports_function_calling=True,
                        supports_streaming=True,
                        description=model.description if hasattr(model, 'description') else None
                    ))
            
            if discovered_models:
                return discovered_models
            
        except Exception as e:
            logger.debug(f"Gemini API discovery failed: {e}")
        
        return self._get_fallback_models()


class OllamaModelDiscovery(BaseModelDiscovery):
    """Ollama model discovery for local models."""
    
    async def _discover_models(self) -> List[DiscoveredModel]:
        """Discover locally installed Ollama models."""
        # First check if Ollama service is running
        if not await self._check_ollama_service():
            logger.debug("Ollama service not available")
            return self._get_fallback_models()
        
        try:
            # Try using the ollama Python library first
            try:
                import ollama
                models_response = await asyncio.to_thread(ollama.list)
                
                discovered_models = []
                for model in models_response.get('models', []):
                    model_name = model.get('name', '')
                    if model_name:
                        discovered_models.append(DiscoveredModel(
                            id=model_name,
                            name=model_name.split(':')[0].title(),  # Remove tag for display
                            provider="ollama",
                            supports_function_calling=True,  # Most modern Ollama models support this
                            supports_streaming=True,
                            description=f"Local model ({model.get('size', 'unknown size')})"
                        ))
                
                if discovered_models:
                    logger.debug(f"Discovered {len(discovered_models)} Ollama models via Python library")
                    return discovered_models
                    
            except ImportError:
                logger.debug("ollama Python library not available, trying HTTP API")
            
            # Fallback to HTTP API
            discovered_models = await self._discover_via_http()
            if discovered_models:
                logger.debug(f"Discovered {len(discovered_models)} Ollama models via HTTP API")
                return discovered_models
            
        except Exception as e:
            logger.warning(f"Ollama discovery failed: {e}")
        
        logger.debug("No Ollama models discovered, using fallback")
        return self._get_fallback_models()
    
    async def _check_ollama_service(self) -> bool:
        """Check if Ollama service is running on localhost:11434."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get("http://localhost:11434/api/version")
                return response.status_code == 200
        except Exception:
            return False
    
    async def _discover_via_http(self) -> List[DiscoveredModel]:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get("http://localhost:11434/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = data.get('models', [])
                    
                    discovered_models = []
                    for model in models:
                        model_name = model.get('name', '')
                        if model_name:
                            discovered_models.append(DiscoveredModel(
                                id=model_name,
                                name=model_name.split(':')[0].title(),
                                provider="ollama",
                                supports_function_calling=True,
                                supports_streaming=True,
                                description=f"Local model ({model.get('size', 'unknown size')})"
                            ))
                    
                    return discovered_models
        except Exception as e:
            logger.debug(f"HTTP API discovery failed: {e}")
        
        return []


class OpenRouterModelDiscovery(BaseModelDiscovery):
    
    async def _discover_models(self) -> List[DiscoveredModel]:
        import os
        
        # Check if API key is available
        if not os.getenv("OPENROUTER_API_KEY"):
            logger.debug("No OPENROUTER_API_KEY found, using fallback models")
            return self._get_fallback_models()
        
        try:
            import httpx
            
            # Get available models from OpenRouter with authentication
            headers = {
                "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://openrouter.ai/api/v1/models",
                    headers=headers,
                    timeout=10.0
                )
                response.raise_for_status()
                models_data = response.json()
            
            discovered_models = []
            for model in models_data.get('data', []):
                model_id = model.get('id', '')
                supported_parameters = model.get('supported_parameters', [])
                
                # Only include models that support tools (function calling)
                if model_id and supported_parameters and 'tools' in supported_parameters:
                    # Handle pricing - convert string to float if needed
                    pricing = model.get('pricing', {}).get('prompt')
                    if pricing and isinstance(pricing, str):
                        try:
                            pricing = float(pricing)
                        except (ValueError, TypeError):
                            pricing = None
                    
                    discovered_models.append(DiscoveredModel(
                        id=model_id,
                        name=model.get('name', model_id),
                        provider="openrouter",
                        supports_function_calling=True,
                        supports_streaming=True,
                        context_length=model.get('context_length'),
                        description=model.get('description'),
                        pricing_per_token=pricing
                    ))
            
            # Sort models for better organization (same as model command)
            def sort_key(model):
                model_id = model.id
                if model_id.startswith("anthropic/claude"):
                    return f"0_{model_id}"
                elif model_id.startswith("openai/"):
                    return f"1_{model_id}"
                elif model_id.startswith("google/"):
                    return f"2_{model_id}"
                elif model_id.startswith("meta-llama/"):
                    return f"3_{model_id}"
                elif model_id.startswith("mistralai/"):
                    return f"4_{model_id}"
                else:
                    return f"5_{model_id}"
            
            discovered_models.sort(key=sort_key)
            
            # Return all tool-capable models
            if discovered_models:
                return discovered_models
            
        except Exception as e:
            logger.debug(f"OpenRouter API discovery failed: {e}")
        
        return self._get_fallback_models()


class ClaudeModelDiscovery(BaseModelDiscovery):
    
    async def _discover_models(self) -> List[DiscoveredModel]:
        return self._get_fallback_models()


class CopilotModelDiscovery(BaseModelDiscovery):
    
    async def _discover_models(self) -> List[DiscoveredModel]:
        import os
        
        api_key = os.getenv("COPILOT_ACCESS_TOKEN")
        if not api_key:
            logger.debug("No COPILOT_ACCESS_TOKEN found, using fallback models")
            return self._get_fallback_models()
        
        try:
            import httpx
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                # GitHub Copilot API endpoint for models
                response = await client.get(
                    "https://api.githubcopilot.com/models",
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    models = []
                    
                    # Parse GitHub Copilot models response
                    if "data" in data:
                        for model_info in data["data"]:
                            model_id = model_info.get("id", "")
                            name = model_info.get("name", model_id)
                            
                            # Only include models that support function calling
                            if model_id and self._supports_function_calling(model_info):
                                models.append(DiscoveredModel(
                                    id=model_id,
                                    name=name,
                                    provider="copilot",
                                    supports_function_calling=True,
                                    supports_streaming=True,
                                    context_length=model_info.get("context_length", 128000)
                                ))
                    
                    if models:
                        logger.debug(f"Discovered {len(models)} GitHub Copilot models")
                        return models
                        
                else:
                    logger.debug(f"GitHub Copilot API returned {response.status_code}")
                    
        except Exception as e:
            logger.debug(f"GitHub Copilot API discovery failed: {e}")
        
        return self._get_fallback_models()
    
    def _supports_function_calling(self, model_info: dict) -> bool:
        # GitHub Copilot typically supports function calling for GPT-4 and Claude models
        model_id = model_info.get("id", "").lower()
        return any(keyword in model_id for keyword in ["gpt-4", "claude", "sonnet"])


class ModelDiscoveryService:
    
    def __init__(self):
        self._discoverers = {
            "openai": OpenAIModelDiscovery("openai"),
            "claude": ClaudeModelDiscovery("claude"), 
            "gemini": GeminiModelDiscovery("gemini"),
            "ollama": OllamaModelDiscovery("ollama"),
            "openrouter": OpenRouterModelDiscovery("openrouter"),
            "copilot": CopilotModelDiscovery("copilot"),
        }
    
    async def discover_models(self, provider: str, use_cache: bool = True) -> List[DiscoveredModel]:
        discoverer = self._discoverers.get(provider)
        if not discoverer:
            logger.warning(f"No discoverer available for provider: {provider}")
            return []
        
        return await discoverer.discover_models(use_cache=use_cache)
    
    async def discover_all_models(self, use_cache: bool = True) -> Dict[str, List[DiscoveredModel]]:
        results = {}
        
        # Run discovery for all providers concurrently
        tasks = {
            provider: self.discover_models(provider, use_cache=use_cache)
            for provider in self._discoverers.keys()
        }
        
        for provider, task in tasks.items():
            try:
                results[provider] = await task
            except Exception as e:
                logger.error(f"Failed to discover models for {provider}: {e}")
                results[provider] = []
        
        return results
    
    def invalidate_cache(self, provider: Optional[str] = None):
        if provider:
            discoverer = self._discoverers.get(provider)
            if discoverer:
                discoverer.invalidate_cache()
        else:
            for discoverer in self._discoverers.values():
                discoverer.invalidate_cache()


# Global singleton instance
_discovery_service: Optional[ModelDiscoveryService] = None


def get_discovery_service() -> ModelDiscoveryService:
    global _discovery_service
    if _discovery_service is None:
        _discovery_service = ModelDiscoveryService()
    return _discovery_service