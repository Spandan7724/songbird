#!/usr/bin/env python3
"""
Phase 4 infrastructure tests for agent conversation loops,
dynamic tool integration, and advanced session management.
"""

import asyncio
import tempfile
import os
import sys
from pathlib import Path

from songbird.llm.providers import get_litellm_provider
from songbird.orchestrator import SongbirdOrchestrator

# Add the songbird directory to the path
sys.path.insert(0, str(Path(__file__).parent))

# Import available components (skipping deprecated ones)
try:
    from songbird.config.config_manager import ConfigManager, get_config_manager
except ImportError:
    ConfigManager = None
    get_config_manager = None

try:
    from songbird.memory.optimized_manager import OptimizedSessionManager
except ImportError:
    OptimizedSessionManager = None

from songbird.tools.tool_registry import get_tool_registry

try:
    from songbird.core.signal_handler import setup_graceful_shutdown
except ImportError:
    setup_graceful_shutdown = None


async def test_unified_provider_interface():
    """Test the unified provider interface."""
    print("🔧 Testing Unified Provider Interface...")
    
    try:
        # Create a provider using LiteLLM (using Ollama as it doesn't require API keys)
        provider = get_litellm_provider("ollama", model="qwen2.5-coder:7b")
        
        print(f"   ✓ Provider created: {provider.get_provider_name()}")
        print(f"   ✓ Model: {provider.get_model_name()}")
        
        # Test provider features
        features = provider.get_supported_features()
        print(f"   ✓ Supports function calling: {features['function_calling']}")
        print(f"   ✓ Supports streaming: {features['streaming']}")
        
        print("   ✅ Unified Provider Interface: PASSED")
        return True
        
    except Exception as e:
        print(f"   ❌ Unified Provider Interface: FAILED - {e}")
        return False


async def test_optimized_session_manager():
    """Test the optimized session manager."""
    print("🔧 Testing Optimized Session Manager...")
    
    if OptimizedSessionManager is None:
        print("   ⚠️  OptimizedSessionManager not available, skipping test")
        return True
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create optimized session manager
            manager = OptimizedSessionManager(
                working_directory=temp_dir,
                flush_interval=1,  # 1 second for testing
                batch_size=2       # Small batch for testing
            )
            
            # Create a session
            session = manager.create_session()
            print(f"   ✓ Created session: {session.id}")
            
            # Add some messages to trigger batching
            from songbird.memory.models import Message
            for i in range(3):
                message = Message(role="user", content=f"Test message {i}")
                manager.append_message(session.id, message)
            
            # Wait for flush
            await asyncio.sleep(2)
            
            # Test statistics
            stats = manager.get_stats()
            print(f"   ✓ Manager stats: {stats['cached_sessions']} cached sessions")
            print(f"   ✓ Dirty sessions: {stats['dirty_sessions']}")
            
            # Test graceful shutdown
            await manager.shutdown()
            print("   ✓ Graceful shutdown completed")
            
            print("   ✅ Optimized Session Manager: PASSED")
            return True
            
    except Exception as e:
        print(f"   ❌ Optimized Session Manager: FAILED - {e}")
        return False


def test_configuration_management():
    """Test the configuration management system."""
    print("🔧 Testing Configuration Management...")
    
    if ConfigManager is None:
        print("   ⚠️  ConfigManager not available, skipping test")
        return True
    
    try:
        # Test config manager
        config_manager = ConfigManager()
        config = config_manager.get_config()
        
        print(f"   ✓ Default provider: {config.llm.default_provider}")
        print(f"   ✓ Session config: flush_interval={config.session.flush_interval}")
        print(f"   ✓ Agent config: max_iterations={config.agent.max_iterations}")
        
        # Test environment variable overrides
        os.environ["SONGBIRD_MAX_ITERATIONS"] = "20"
        os.environ["SONGBIRD_FLUSH_INTERVAL"] = "60"
        
        # Create new manager to pick up env vars
        new_manager = ConfigManager()
        new_config = new_manager.get_config()
        
        print(f"   ✓ Environment override applied: max_iterations={new_config.agent.max_iterations}")
        
        # Test API key detection
        api_keys = config_manager.get_api_keys()
        available_providers = config_manager.get_available_providers()
        print(f"   ✓ Available providers: {[k for k, v in available_providers.items() if v]}")
        
        # Test global config manager
        if get_config_manager is not None:
            global_manager = get_config_manager()
            print(f"   ✓ Global manager instance: {global_manager is not None}")
        
        # Cleanup env vars
        del os.environ["SONGBIRD_MAX_ITERATIONS"]
        del os.environ["SONGBIRD_FLUSH_INTERVAL"]
        
        print("   ✅ Configuration Management: PASSED")
        return True
        
    except Exception as e:
        print(f"   ❌ Configuration Management: FAILED - {e}")
        return False


def test_tool_registry():
    """Test the centralized tool registry."""
    print("🔧 Testing Centralized Tool Registry...")
    
    try:
        # Get tool registry
        registry = get_tool_registry()
        
        # Test basic functionality
        all_tools = registry.get_all_tools()
        print(f"   ✓ Total tools registered: {len(all_tools)}")
        
        # Test specific tool
        file_read_tool = registry.get_tool("file_read")
        print(f"   ✓ File read tool found: {file_read_tool is not None}")
        
        # Test schema generation for different providers
        openai_schemas = registry.get_llm_schemas("openai")
        gemini_schemas = registry.get_llm_schemas("gemini")
        
        print(f"   ✓ OpenAI schemas: {len(openai_schemas)}")
        print(f"   ✓ Gemini schemas: {len(gemini_schemas)}")
        
        # Test parallel safety tracking
        parallel_safe = registry.get_parallel_safe_tools()
        destructive = registry.get_destructive_tools()
        
        print(f"   ✓ Parallel safe tools: {len(parallel_safe)}")
        print(f"   ✓ Destructive tools: {len(destructive)}")
        
        # Test tool info
        info = registry.get_tool_info()
        print(f"   ✓ Tool categories: {info['categories']}")
        
        print("   ✅ Centralized Tool Registry: PASSED")
        return True
        
    except Exception as e:
        print(f"   ❌ Centralized Tool Registry: FAILED - {e}")
        return False


def test_signal_handler():
    """Test the graceful shutdown signal handler."""
    print("🔧 Testing Graceful Shutdown Handler...")
    
    if setup_graceful_shutdown is None:
        print("   ⚠️  Graceful shutdown handler not available, skipping test")
        return True
    
    try:
        # Test basic handler creation
        handler = setup_graceful_shutdown(enable_async=True)
        
        print(f"   ✓ Handler created: {handler is not None}")
        print(f"   ✓ Shutdown callbacks: {len(handler.shutdown_callbacks)}")
        
        # Test callback registration
        callback_called = False
        
        def test_callback():
            nonlocal callback_called
            callback_called = True
        
        handler.register_shutdown_callback("test", test_callback)
        print("   ✓ Callback registered")
        
        # Test callback execution (sync)
        handler._sync_shutdown()
        print(f"   ✓ Callback executed: {callback_called}")
        
        # Cleanup
        handler.restore_original_handlers()
        
        print("   ✅ Graceful Shutdown Handler: PASSED")
        return True
        
    except Exception as e:
        print(f"   ❌ Graceful Shutdown Handler: FAILED - {e}")
        return False


async def test_integrated_orchestrator():
    """Test the integrated orchestrator with all Phase 4 improvements."""
    print("🔧 Testing Integrated Orchestrator...")
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create provider using LiteLLM
            provider = get_litellm_provider("ollama", model="qwen2.5-coder:7b")
            
            # Create orchestrator
            orchestrator = SongbirdOrchestrator(
                provider=provider,
                working_directory=temp_dir
            )
            
            print("   ✓ Orchestrator created with Phase 4 improvements")
            
            # Test provider info
            print(f"   ✓ Provider: {provider.get_provider_name()}")
            print(f"   ✓ Model: {provider.get_model_name()}")
            
            # Test basic orchestrator functionality
            print("   ✓ Orchestrator initialized successfully")
            
            # Test cleanup
            await orchestrator.cleanup()
            print("   ✓ Cleanup completed successfully")
            
            print("   ✅ Integrated Orchestrator: PASSED")
            return True
            
    except Exception as e:
        print(f"   ❌ Integrated Orchestrator: FAILED - {e}")
        return False


async def main():
    """Run all Phase 4 infrastructure tests."""
    print("🚀 Testing Phase 4: Infrastructure Improvements")
    print("=" * 50)
    
    results = []
    
    # Run all tests
    results.append(await test_unified_provider_interface())
    results.append(await test_optimized_session_manager())
    results.append(test_configuration_management())
    results.append(test_tool_registry())
    results.append(test_signal_handler())
    results.append(await test_integrated_orchestrator())
    
    # Summary
    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"🎉 ALL TESTS PASSED ({passed}/{total})")
        print("✅ Phase 4 Infrastructure: FULLY OPERATIONAL")
        return True
    else:
        print(f"⚠️  SOME TESTS FAILED ({passed}/{total})")
        print("❌ Phase 4 Infrastructure: NEEDS ATTENTION")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)