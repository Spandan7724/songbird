#!/usr/bin/env python3
"""Real provider integration tests using actual API keys."""

import asyncio
import tempfile
import pytest
import os
import sys
from pathlib import Path

# Add the songbird directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from .env file
def load_env_file():
    """Load environment variables from .env file."""
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip().strip('"\'')

# Load environment variables
load_env_file()


# Skip these tests if no API keys are available
def has_gemini_key():
    return os.getenv("GEMINI_API_KEY") is not None

def has_openrouter_key():
    return os.getenv("OPENROUTER_API_KEY") is not None

def has_ollama_available():
    """Check if Ollama is running locally."""
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


@pytest.mark.skipif(not has_gemini_key(), reason="No GEMINI_API_KEY available")
class TestGeminiProvider:
    """Test Gemini provider with real API."""
    
    @pytest.mark.asyncio
    async def test_gemini_simple_conversation(self):
        """Test simple conversation with Gemini."""
        from songbird.llm.providers import GeminiProvider
        from songbird.orchestrator import SongbirdOrchestrator
        
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = GeminiProvider()
            orchestrator = SongbirdOrchestrator(
                provider=provider,
                working_directory=temp_dir
            )
            
            # Simple conversation without tools
            result = await orchestrator.chat_single_message("Say hello and tell me you're working correctly.")
            
            assert isinstance(result, str)
            assert len(result) > 10  # Should be a substantial response
            assert "hello" in result.lower() or "working" in result.lower()
            
            await orchestrator.cleanup()
    
    @pytest.mark.asyncio 
    async def test_gemini_with_file_operations(self):
        """Test Gemini with actual file operations."""
        from songbird.llm.providers import GeminiProvider
        from songbird.orchestrator import SongbirdOrchestrator
        
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = GeminiProvider()
            orchestrator = SongbirdOrchestrator(
                provider=provider,
                working_directory=temp_dir
            )
            
            # Request file creation
            result = await orchestrator.chat_single_message(
                "Create a simple Python file called hello.py that prints 'Hello from Gemini test!'"
            )
            
            assert isinstance(result, str)
            
            # Check if file was created (may or may not happen depending on Gemini's response)
            hello_file = Path(temp_dir) / "hello.py"
            if hello_file.exists():
                content = hello_file.read_text()
                assert "Hello from Gemini test!" in content or "print" in content
            
            await orchestrator.cleanup()


@pytest.mark.skipif(not has_openrouter_key(), reason="No OPENROUTER_API_KEY available")
class TestOpenRouterProvider:
    """Test OpenRouter provider with real API."""
    
    @pytest.mark.asyncio
    async def test_openrouter_simple_conversation(self):
        """Test simple conversation with OpenRouter."""
        from songbird.llm.providers import OpenRouterProvider
        from songbird.orchestrator import SongbirdOrchestrator
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Use a free model for testing
            provider = OpenRouterProvider(model="deepseek/deepseek-chat-v3-0324:free")
            orchestrator = SongbirdOrchestrator(
                provider=provider,
                working_directory=temp_dir
            )
            
            # Simple conversation
            result = await orchestrator.chat_single_message("Hello! Please confirm you can respond.")
            
            assert isinstance(result, str)
            assert len(result) > 5  # Should get some response
            
            await orchestrator.cleanup()
    
    @pytest.mark.asyncio
    async def test_openrouter_capabilities(self):
        """Test OpenRouter provider capabilities."""
        from songbird.llm.providers import OpenRouterProvider
        from songbird.orchestrator import SongbirdOrchestrator
        
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = OpenRouterProvider(model="deepseek/deepseek-chat-v3-0324:free")
            orchestrator = SongbirdOrchestrator(
                provider=provider,
                working_directory=temp_dir
            )
            
            # Test provider info
            provider_info = orchestrator.get_provider_info()
            assert provider_info["provider_name"] == "openrouter"
            assert "deepseek" in provider_info.get("model_name", "").lower()
            
            await orchestrator.cleanup()


@pytest.mark.skipif(not has_ollama_available(), reason="Ollama not available")
class TestOllamaProvider:
    """Test Ollama provider with local instance."""
    
    @pytest.mark.asyncio
    async def test_ollama_simple_conversation(self):
        """Test simple conversation with Ollama."""
        from songbird.llm.providers import OllamaProvider
        from songbird.orchestrator import SongbirdOrchestrator
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Use default model
            provider = OllamaProvider()
            orchestrator = SongbirdOrchestrator(
                provider=provider,
                working_directory=temp_dir
            )
            
            # Simple conversation
            result = await orchestrator.chat_single_message("Hello! Please respond briefly.")
            
            assert isinstance(result, str)
            assert len(result) > 0
            
            await orchestrator.cleanup()
    
    @pytest.mark.asyncio
    async def test_ollama_with_tools(self):
        """Test Ollama with tool usage."""
        from songbird.llm.providers import OllamaProvider
        from songbird.orchestrator import SongbirdOrchestrator
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test file first
            test_file = Path(temp_dir) / "test.txt"
            test_file.write_text("This is a test file for Ollama.")
            
            provider = OllamaProvider()
            orchestrator = SongbirdOrchestrator(
                provider=provider,
                working_directory=temp_dir
            )
            
            # Ask to read the file
            result = await orchestrator.chat_single_message("Please read the file test.txt")
            
            assert isinstance(result, str)
            # May or may not actually read the file depending on model capabilities
            
            await orchestrator.cleanup()


class TestMultiProviderComparison:
    """Test comparing different providers."""
    
    def test_provider_selection_logic(self):
        """Test provider selection logic."""
        from songbird.llm.providers import get_default_provider, list_available_providers
        
        # Should have some providers available
        available = list_available_providers()
        assert len(available) > 0
        assert "ollama" in available  # Always available
        
        # Should select a default
        default = get_default_provider()
        assert default in available
    
    def test_provider_info_consistency(self):
        """Test provider info structure is consistent."""
        from songbird.llm.providers import get_provider_info
        
        provider_info = get_provider_info()
        assert isinstance(provider_info, dict)
        
        # All providers should have consistent structure
        for provider_name, info in provider_info.items():
            assert "available" in info
            assert "models" in info
            assert "description" in info
            assert isinstance(info["available"], bool)
            assert isinstance(info["models"], list)


class TestProviderIntegrationStress:
    """Stress test provider integration."""
    
    @pytest.mark.asyncio
    async def test_session_persistence_across_providers(self):
        """Test session persistence works with different providers."""
        from songbird.memory.optimized_manager import OptimizedSessionManager
        from songbird.memory.models import Message
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test session manager independent of provider
            manager = OptimizedSessionManager(
                working_directory=temp_dir,
                flush_interval=1,
                batch_size=2
            )
            
            # Create session and add messages
            session = manager.create_session()
            
            for i in range(5):
                message = Message(role="user", content=f"Test message {i}")
                manager.append_message(session.id, message)
            
            # Wait for flush
            await asyncio.sleep(2)
            
            # Verify persistence
            loaded_session = manager.load_session(session.id)
            assert loaded_session is not None
            assert len(loaded_session.messages) >= 5
            
            # Cleanup
            await manager.shutdown()
    
    @pytest.mark.asyncio
    async def test_tool_registry_with_all_providers(self):
        """Test tool registry works with all provider formats."""
        from songbird.tools.tool_registry import get_tool_registry
        
        registry = get_tool_registry()
        
        # Test schema generation for all providers
        providers = ["openai", "claude", "gemini", "ollama", "openrouter"]
        
        for provider in providers:
            schemas = registry.get_llm_schemas(provider)
            assert len(schemas) > 0
            
            # Verify basic schema structure
            for schema in schemas:
                if provider == "gemini":
                    assert "name" in schema
                    assert "description" in schema
                    if "parameters" in schema:
                        assert isinstance(schema["parameters"], dict)
                else:
                    assert "type" in schema
                    assert schema["type"] == "function"
                    assert "function" in schema
                    assert "name" in schema["function"]
                    assert "description" in schema["function"]


@pytest.mark.asyncio
async def test_end_to_end_provider_workflow():
    """Test a complete workflow can work with any available provider."""
    from songbird.llm.providers import get_default_provider, get_provider
    from songbird.orchestrator import SongbirdOrchestrator
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Use the best available provider
        provider_name = get_default_provider()
        provider_class = get_provider(provider_name)
        
        try:
            provider = provider_class()
        except Exception as e:
            # If provider initialization fails, skip this test
            pytest.skip(f"Provider {provider_name} not available: {e}")
        
        orchestrator = SongbirdOrchestrator(
            provider=provider,
            working_directory=temp_dir
        )
        
        # Test basic functionality
        result = await orchestrator.chat_single_message("Hello! Can you respond?")
        assert isinstance(result, str)
        
        # Test infrastructure
        stats = orchestrator.get_infrastructure_stats()
        assert "session_manager" in stats
        assert "provider" in stats
        assert "config" in stats
        
        await orchestrator.cleanup()


if __name__ == "__main__":
    # Run with specific markers for available providers
    
    # Check what's available and run appropriate tests
    pytest_args = [__file__, "-v"]
    
    if has_gemini_key():
        print("✅ Gemini API key available")
    else:
        print("⚠️  No Gemini API key - skipping Gemini tests")
    
    if has_openrouter_key():
        print("✅ OpenRouter API key available")
    else:
        print("⚠️  No OpenRouter API key - skipping OpenRouter tests")
    
    if has_ollama_available():
        print("✅ Ollama service available")
    else:
        print("⚠️  Ollama not available - skipping Ollama tests")
    
    pytest.main(pytest_args)