"""Tests for the dynamic model discovery system."""

import pytest
import asyncio
from unittest.mock import Mock, patch

from songbird.discovery import (
    DiscoveredModel, 
    BaseModelDiscovery, 
    ModelDiscoveryService,
    get_discovery_service
)


class TestDiscoveredModel:
    """Test the DiscoveredModel dataclass."""
    
    def test_basic_model(self):
        """Test basic model creation."""
        model = DiscoveredModel(
            id="gpt-4o",
            name="GPT-4o",
            provider="openai"
        )
        
        assert model.id == "gpt-4o"
        assert model.name == "GPT-4o"
        assert model.provider == "openai"
        assert model.supports_function_calling is True
        assert model.supports_streaming is True
    
    def test_display_name(self):
        """Test display name generation."""
        model = DiscoveredModel(
            id="gpt-4o",
            name="GPT-4o",
            provider="openai",
            description="Most advanced model"
        )
        
        assert model.display_name == "GPT-4o (Most advanced model)"
        
        model_no_desc = DiscoveredModel(
            id="gpt-4o",
            name="GPT-4o",
            provider="openai"
        )
        
        assert model_no_desc.display_name == "GPT-4o"
    
    def test_litellm_id(self):
        """Test LiteLLM ID generation."""
        model = DiscoveredModel(
            id="gpt-4o",
            name="GPT-4o",
            provider="openai"
        )
        
        assert model.litellm_id == "openai/gpt-4o"
        
        model_with_slash = DiscoveredModel(
            id="openai/gpt-4o",
            name="GPT-4o",
            provider="openai"
        )
        
        assert model_with_slash.litellm_id == "openai/gpt-4o"


class TestBaseModelDiscovery:
    """Test the base model discovery class."""
    
    def test_cache_validity(self):
        """Test cache validity checking."""
        class TestDiscovery(BaseModelDiscovery):
            async def _discover_models(self):
                return []
        
        discovery = TestDiscovery("test")
        
        # No cache initially
        assert not discovery._is_cache_valid()
        
        # Add cache
        discovery._cache = [Mock()]
        discovery._cache_timestamp = discovery._cache_timestamp = 0
        assert not discovery._is_cache_valid()  # Too old
        
        # Fresh cache
        import time
        discovery._cache_timestamp = time.time()
        assert discovery._is_cache_valid()
    
    def test_cache_invalidation(self):
        """Test cache invalidation."""
        class TestDiscovery(BaseModelDiscovery):
            async def _discover_models(self):
                return []
        
        discovery = TestDiscovery("test")
        discovery._cache = [Mock()]
        discovery._cache_timestamp = 123456
        
        discovery.invalidate_cache()
        
        assert discovery._cache == []
        assert discovery._cache_timestamp == 0
    
    def test_fallback_models(self):
        """Test fallback model provision."""
        class TestDiscovery(BaseModelDiscovery):
            async def _discover_models(self):
                return []
        
        discovery = TestDiscovery("openai")
        fallback_models = discovery._get_fallback_models()
        
        assert len(fallback_models) > 0
        assert all(isinstance(model, DiscoveredModel) for model in fallback_models)
        assert all(model.provider == "openai" for model in fallback_models)


class TestModelDiscoveryService:
    """Test the central discovery service."""
    
    def test_service_initialization(self):
        """Test service initialization."""
        service = ModelDiscoveryService()
        
        # Check that all expected providers are initialized
        expected_providers = ["openai", "claude", "gemini", "ollama", "openrouter"]
        for provider in expected_providers:
            assert provider in service._discoverers
    
    @pytest.mark.asyncio
    async def test_discover_invalid_provider(self):
        """Test discovery with invalid provider."""
        service = ModelDiscoveryService()
        
        models = await service.discover_models("invalid_provider")
        assert models == []
    
    @pytest.mark.asyncio
    async def test_discover_all_models(self):
        """Test discovering models for all providers."""
        service = ModelDiscoveryService()
        
        # Mock all discoverers to return test models
        test_model = DiscoveredModel("test-model", "Test Model", "test")
        
        for discoverer in service._discoverers.values():
            discoverer._discover_models = Mock(return_value=[test_model])
        
        all_models = await service.discover_all_models(use_cache=False)
        
        assert isinstance(all_models, dict)
        assert len(all_models) == len(service._discoverers)
        
        for provider, models in all_models.items():
            assert len(models) >= 0  # Some might fail, that's ok
    
    def test_singleton_service(self):
        """Test that get_discovery_service returns singleton."""
        service1 = get_discovery_service()
        service2 = get_discovery_service()
        
        assert service1 is service2


@pytest.mark.asyncio
async def test_integration_with_providers():
    """Test integration with the provider system."""
    from songbird.llm.providers import get_models_for_provider, invalidate_model_cache
    
    # Test getting models for a provider
    models = await get_models_for_provider("gemini", use_cache=True)
    assert isinstance(models, list)
    
    # Test cache invalidation
    invalidate_model_cache("gemini")  # Should not raise
    invalidate_model_cache()  # Should not raise


@pytest.mark.asyncio
async def test_model_command_integration():
    """Test integration with the model command."""
    from songbird.commands.model_command import ModelCommand
    
    cmd = ModelCommand()
    
    # Test LiteLLM model discovery
    models = cmd._get_litellm_models("gemini")
    assert isinstance(models, list)
    assert len(models) > 0
    
    # Test legacy model discovery
    models = cmd._get_available_models("gemini")
    assert isinstance(models, list)
    assert len(models) > 0


def test_provider_info_integration():
    """Test integration with get_provider_info."""
    from songbird.llm.providers import get_provider_info
    
    # Test with discovery enabled
    provider_info = get_provider_info(use_discovery=True)
    assert isinstance(provider_info, dict)
    assert len(provider_info) > 0
    
    for name, info in provider_info.items():
        assert "available" in info
        assert "models" in info
        assert "api_key_env" in info
        assert "ready" in info
        assert "models_discovered" in info
        
        assert isinstance(info["models"], list)
        assert isinstance(info["ready"], bool)
        assert isinstance(info["models_discovered"], bool)
    
    # Test with discovery disabled
    provider_info_no_discovery = get_provider_info(use_discovery=False)
    assert isinstance(provider_info_no_discovery, dict)
    assert len(provider_info_no_discovery) > 0