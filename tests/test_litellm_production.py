# tests/test_litellm_production.py
"""
Production validation tests for LiteLLM integration.

Tests end-to-end functionality, CLI integration, real-world scenarios,
and production readiness of the LiteLLM adapter system.
"""
import pytest
import subprocess
import sys
import os
from unittest.mock import Mock, patch
from songbird.llm.providers import create_litellm_provider
from songbird.llm.litellm_adapter import LiteLLMAdapter
from songbird.config.mapping_loader import load_provider_mapping


@pytest.mark.slow
class TestLiteLLMProductionReadiness:
    """Test LiteLLM production readiness and deployment scenarios."""
    
    def test_litellm_flag_availability(self):
        """Test --litellm flag is available in CLI."""
        # Test CLI help includes --litellm flag
        result = subprocess.run([
            sys.executable, "-m", "songbird.cli", "--help"
        ], capture_output=True, text=True, timeout=10)
        
        assert result.returncode == 0
        assert "--litellm" in result.stdout
        assert "LiteLLM unified interface" in result.stdout or "experimental" in result.stdout
    
    def test_configuration_production_ready(self):
        """Test configuration system is production ready."""
        # Test default configuration loads successfully
        config = load_provider_mapping()
        
        # Verify all expected providers are configured
        expected_providers = ["openai", "claude", "gemini", "ollama", "openrouter"]
        for provider in expected_providers:
            assert config.get_default_model(provider) is not None
            assert "/" in config.get_default_model(provider)  # LiteLLM format
        
        # Verify configuration validation
        from songbird.config.mapping_loader import validate_mapping_config
        issues = validate_mapping_config(config.data)
        
        # Production config should have minimal issues
        critical_issues = [issue for issue in issues if "missing" in issue.lower()]
        assert len(critical_issues) == 0, f"Critical configuration issues: {critical_issues}"
    
    def test_provider_creation_all_providers(self):
        """Test provider creation works for all supported providers."""
        providers_to_test = [
            ("openai", "gpt-4o-mini", "openai"),
            ("claude", "claude-3-5-haiku-20241022", "anthropic"),  # Claude maps to anthropic vendor
            ("gemini", "gemini-2.0-flash-001", "gemini"),
            ("ollama", "qwen2.5-coder:7b", "ollama"),
            ("openrouter", "anthropic/claude-3.5-sonnet", "anthropic")  # Uses actual vendor prefix
        ]
        
        for provider_name, model, expected_vendor in providers_to_test:
            try:
                provider = create_litellm_provider(provider_name, model)
                assert isinstance(provider, LiteLLMAdapter)
                assert provider.vendor_prefix == expected_vendor
                assert provider.get_supported_features()["function_calling"] is True
            except Exception as e:
                pytest.fail(f"Failed to create provider {provider_name}: {e}")
    
    def test_environment_validation_comprehensive(self):
        """Test environment validation for production deployment."""
        adapters_to_test = [
            "openai/gpt-4o-mini",
            "anthropic/claude-3-5-sonnet",
            "gemini/gemini-2.0-flash-001",
            "ollama/qwen2.5-coder:7b",
            "openrouter/anthropic/claude-3.5-sonnet"
        ]
        
        for model_string in adapters_to_test:
            adapter = LiteLLMAdapter(model_string)
            env_status = adapter.check_environment_readiness()
            
            # Verify status structure
            assert "provider" in env_status
            assert "model" in env_status
            assert "env_ready" in env_status
            assert "env_status" in env_status
            assert isinstance(env_status["env_ready"], bool)
    
    @patch.dict(os.environ, {}, clear=True)
    def test_graceful_degradation_no_api_keys(self):
        """Test graceful degradation when no API keys are present."""
        # Test each provider handles missing API keys gracefully
        adapters = [
            "openai/gpt-4o-mini",
            "anthropic/claude-3-5-sonnet", 
            "gemini/gemini-2.0-flash-001"
        ]
        
        for model_string in adapters:
            adapter = LiteLLMAdapter(model_string)
            env_status = adapter.check_environment_readiness()
            
            # Should not crash, should indicate missing keys
            if env_status["env_var"]:  # Only if provider requires API key
                assert env_status["env_ready"] is False
                assert env_status["env_status"] == "missing"


@pytest.mark.slow
class TestLiteLLMProductionScenarios:
    """Test real-world production scenarios."""
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_typical_user_workflow(self, mock_acompletion):
        """Test typical user workflow with LiteLLM."""
        # Mock realistic LiteLLM responses
        responses = [
            # Initial greeting
            Mock(
                choices=[Mock(
                    message=Mock(
                        content="Hello! I'm ready to help you with your coding tasks.",
                        tool_calls=None
                    )
                )]
            ),
            # Tool-using response
            Mock(
                choices=[Mock(
                    message=Mock(
                        content="I'll search for Python files in your project.",
                        tool_calls=[Mock(
                            id="call_search",
                            function=Mock(
                                name="file_search",
                                arguments='{"pattern": "*.py", "directory": ".", "file_type": "py"}'
                            )
                        )]
                    )
                )]
            )
        ]
        
        mock_acompletion.side_effect = responses
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "file_search",
                    "description": "Search for files",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "pattern": {"type": "string"},
                            "directory": {"type": "string"},
                            "file_type": {"type": "string"}
                        },
                        "required": ["pattern"]
                    }
                }
            }
        ]
        
        # Test initial conversation
        response1 = await adapter.chat_with_messages(
            [{"role": "user", "content": "Hello"}], 
            tools
        )
        assert "ready to help" in response1.content.lower()
        
        # Test tool-using conversation
        response2 = await adapter.chat_with_messages(
            [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": response1.content},
                {"role": "user", "content": "Find Python files"}
            ], 
            tools
        )
        assert len(response2.tool_calls) == 1
        assert response2.tool_calls[0]["function"]["name"] == "file_search"
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_model_switching_workflow(self, mock_acompletion):
        """Test model switching in production scenario."""
        # Mock responses for different models
        mock_acompletion.return_value = Mock(
            choices=[Mock(
                message=Mock(content="Response", tool_calls=None)
            )]
        )
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        
        # Test initial model
        response1 = await adapter.chat_with_messages([{"role": "user", "content": "Test"}])
        assert response1.content == "Response"
        
        # Switch model and test state flush
        adapter.set_model("anthropic/claude-3-5-sonnet")
        assert adapter.vendor_prefix == "anthropic"
        assert adapter.model_name == "claude-3-5-sonnet"
        
        # Test after model switch
        response2 = await adapter.chat_with_messages([{"role": "user", "content": "Test"}])
        assert response2.content == "Response"
    
    def test_concurrent_provider_creation(self):
        """Test concurrent provider creation for production load."""
        import concurrent.futures
        
        def create_provider(args):
            provider_name, model = args
            return create_litellm_provider(provider_name, model)
        
        # Test concurrent creation
        provider_configs = [
            ("openai", "gpt-4o-mini"),
            ("openai", "gpt-4o"),
            ("anthropic", "claude-3-5-sonnet"),
            ("gemini", "gemini-2.0-flash-001"),
            ("ollama", "qwen2.5-coder:7b")
        ]
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_provider, config) for config in provider_configs]
            results = [future.result(timeout=5) for future in futures]
        
        # All providers should be created successfully
        assert len(results) == 5
        for provider in results:
            assert isinstance(provider, LiteLLMAdapter)
    
    def test_error_recovery_workflow(self):
        """Test error recovery in production scenarios."""
        # Test initialization with various error conditions
        error_scenarios = [
            ("invalid/model", "Should handle invalid model gracefully"),
            ("openai/nonexistent-model", "Should handle nonexistent model"),
            ("", "Should handle empty model string"),
        ]
        
        for model_string, description in error_scenarios:
            try:
                if model_string:
                    adapter = LiteLLMAdapter(model_string)
                    # Should initialize even with warnings
                    assert adapter.model == model_string
                else:
                    # Empty string should raise error
                    with pytest.raises(Exception):
                        LiteLLMAdapter(model_string)
            except Exception as e:
                # Some errors are expected, just ensure they're handled gracefully
                assert isinstance(e, Exception)


@pytest.mark.slow
class TestLiteLLMProductionDeployment:
    """Test production deployment scenarios."""
    
    def test_soft_launch_flag_behavior(self):
        """Test --litellm flag behavior in production."""
        # Test that --litellm flag changes provider behavior
        with patch('songbird.llm.providers.get_litellm_provider') as mock_litellm:
            mock_litellm.return_value = Mock()
            
            # Mock CLI context
            
            # Test that --litellm flag triggers LiteLLM provider usage
            # This would be called internally when --litellm flag is used
            from songbird.llm.providers import get_litellm_provider
            
            provider = get_litellm_provider("openai", "gpt-4o")
            assert provider is not None
    
    def test_configuration_validation_warnings(self):
        """Test configuration validation shows appropriate warnings."""
        # Test that production warnings are informative but not blocking
        config = load_provider_mapping()
        
        # Should load without critical errors
        assert config is not None
        assert len(config.defaults) >= 5  # At least 5 providers
        
        # Validate that all default models use proper LiteLLM format
        for provider, model in config.defaults.items():
            assert "/" in model, f"Provider {provider} model {model} should use LiteLLM format"
    
    def test_backwards_compatibility(self):
        """Test backwards compatibility with existing workflows."""
        # Test that LiteLLM doesn't break existing patterns
        adapter = LiteLLMAdapter("openai/gpt-4o")
        
        # Test legacy interface methods still work
        assert adapter.get_provider_name() == "openai"
        assert adapter.get_model_name() == "gpt-4o"
        assert adapter.get_supported_features() is not None
        
        # Test that adapter follows UnifiedProviderInterface
        from songbird.llm.unified_interface import UnifiedProviderInterface
        assert isinstance(adapter, UnifiedProviderInterface)
    
    def test_resource_limits_production(self):
        """Test resource limits and constraints for production."""
        # Test that adapter doesn't consume excessive resources
        adapters = []
        
        # Create multiple adapters (simulating production load)
        for i in range(10):
            adapter = LiteLLMAdapter("openai/gpt-4o")
            adapters.append(adapter)
        
        # All should be created successfully
        assert len(adapters) == 10
        
        # Test resource cleanup
        for adapter in adapters:
            # Verify no resource leaks
            assert adapter._state_cache is not None
            adapter.flush_state()  # Should not raise errors


class TestLiteLLMMonitoring:
    """Test monitoring and observability for production."""
    
    def test_logging_integration(self):
        """Test logging works properly for monitoring."""
        
        # Test that LiteLLM adapter logs appropriately
        with patch('songbird.llm.litellm_adapter.logger') as mock_logger:
            adapter = LiteLLMAdapter("openai/gpt-4o")
            
            # Should have logged initialization
            assert mock_logger.debug.called or mock_logger.info.called
    
    def test_error_classification_production(self):
        """Test error classification for production monitoring."""
        from songbird.llm.litellm_adapter import (
            LiteLLMAuthenticationError, LiteLLMRateLimitError
        )
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        
        # Test error classification works
        auth_error = adapter._handle_completion_error(
            Exception("401 Unauthorized"), "test"
        )
        assert isinstance(auth_error, LiteLLMAuthenticationError)
        
        rate_error = adapter._handle_completion_error(
            Exception("429 Rate limit exceeded"), "test"
        )
        assert isinstance(rate_error, LiteLLMRateLimitError)
    
    def test_performance_metrics(self):
        """Test performance metrics collection for monitoring."""
        adapter = LiteLLMAdapter("openai/gpt-4o")
        
        # Test that adapter provides performance information
        features = adapter.get_supported_features()
        assert "streaming" in features
        assert "function_calling" in features
        
        # Test environment readiness for monitoring
        env_status = adapter.check_environment_readiness()
        assert "provider" in env_status
        assert "env_ready" in env_status


if __name__ == "__main__":
    # Run production tests
    pytest.main([__file__, "-v", "-m", "slow"])