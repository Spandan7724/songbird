"""Dynamic model discovery service for all LLM providers."""

import asyncio
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Set
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
        """Discover available models for this provider."""
        pass
    
    def _get_fallback_models(self) -> List[DiscoveredModel]:
        """Get hardcoded fallback models if discovery fails."""
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
                DiscoveredModel("gemini-2.0-flash-001", "Gemini 2.0 Flash", "gemini", context_length=1000000),
                DiscoveredModel("gemini-1.5-pro", "Gemini 1.5 Pro", "gemini", context_length=2000000),
                DiscoveredModel("gemini-1.5-flash", "Gemini 1.5 Flash", "gemini", context_length=1000000),
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
        """Check if the cache is still valid."""
        if not self._cache:
            return False
        return (time.time() - self._cache_timestamp) < self._cache_ttl
    
    def invalidate_cache(self):
        """Invalidate the model cache."""
        self._cache = []
        self._cache_timestamp = 0


class OpenAIModelDiscovery(BaseModelDiscovery):
    """OpenAI model discovery using their API."""
    
    async def _discover_models(self) -> List[DiscoveredModel]:
        """Discover OpenAI models via API."""
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
            
            # Sort by creation date (newest first) and take top 10
            if discovered_models:
                discovered_models.sort(key=lambda x: x.created or 0, reverse=True)
                return discovered_models[:10]
            
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
        try:
            import ollama
            
            # Get locally installed models
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
                return discovered_models
            
        except Exception as e:
            logger.debug(f"Ollama discovery failed: {e}")
        
        return self._get_fallback_models()


class OpenRouterModelDiscovery(BaseModelDiscovery):
    """OpenRouter model discovery using their API."""
    
    async def _discover_models(self) -> List[DiscoveredModel]:
        """Discover OpenRouter models via API."""
        import os
        
        # Check if API key is available
        if not os.getenv("OPENROUTER_API_KEY"):
            logger.debug("No OPENROUTER_API_KEY found, using fallback models")
            return self._get_fallback_models()
        
        try:
            import httpx
            
            # Get available models from OpenRouter
            async with httpx.AsyncClient() as client:
                response = await client.get("https://openrouter.ai/api/v1/models")
                response.raise_for_status()
                models_data = response.json()
            
            discovered_models = []
            for model in models_data.get('data', []):
                # Filter for models that support function calling and are reasonably popular
                if model.get('architecture', {}).get('instruct_type') in ['chat', 'instruction'] and \
                   model.get('context_length', 0) >= 4000:  # Reasonable context length
                    
                    discovered_models.append(DiscoveredModel(
                        id=model['id'],
                        name=model.get('name', model['id']),
                        provider="openrouter",
                        supports_function_calling=True,
                        supports_streaming=True,
                        context_length=model.get('context_length'),
                        description=model.get('description'),
                        pricing_per_token=model.get('pricing', {}).get('prompt')
                    ))
            
            # Sort by popularity/pricing and take top 20
            if discovered_models:
                discovered_models.sort(key=lambda x: x.pricing_per_token or 999, reverse=False)
                return discovered_models[:20]
            
        except Exception as e:
            logger.debug(f"OpenRouter API discovery failed: {e}")
        
        return self._get_fallback_models()


class ClaudeModelDiscovery(BaseModelDiscovery):
    """Claude model discovery (uses fallback since no public API)."""
    
    async def _discover_models(self) -> List[DiscoveredModel]:
        """Claude doesn't have a public model listing API, use curated list."""
        return self._get_fallback_models()


class ModelDiscoveryService:
    """Central service for discovering models across all providers."""
    
    def __init__(self):
        self._discoverers = {
            "openai": OpenAIModelDiscovery("openai"),
            "claude": ClaudeModelDiscovery("claude"), 
            "gemini": GeminiModelDiscovery("gemini"),
            "ollama": OllamaModelDiscovery("ollama"),
            "openrouter": OpenRouterModelDiscovery("openrouter"),
        }
    
    async def discover_models(self, provider: str, use_cache: bool = True) -> List[DiscoveredModel]:
        """Discover models for a specific provider."""
        discoverer = self._discoverers.get(provider)
        if not discoverer:
            logger.warning(f"No discoverer available for provider: {provider}")
            return []
        
        return await discoverer.discover_models(use_cache=use_cache)
    
    async def discover_all_models(self, use_cache: bool = True) -> Dict[str, List[DiscoveredModel]]:
        """Discover models for all providers."""
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
        """Invalidate cache for specific provider or all providers."""
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
    """Get the global model discovery service instance."""
    global _discovery_service
    if _discovery_service is None:
        _discovery_service = ModelDiscoveryService()
    return _discovery_service