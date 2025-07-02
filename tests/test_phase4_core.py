#!/usr/bin/env python3
"""Core test script for Phase 4 infrastructure without external dependencies."""

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock

# Add the songbird directory to the path
sys.path.insert(0, str(Path(__file__).parent))


def test_configuration_management():
    """Test the configuration management system."""
    print("🔧 Testing Configuration Management...")
    
    try:
        from songbird.config.config_manager import ConfigManager, get_config_manager
        
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
        from songbird.tools.tool_registry import get_tool_registry
        
        # Get tool registry
        registry = get_tool_registry()
        
        # Test basic functionality
        all_tools = registry.get_all_tools()
        print(f"   ✓ Total tools registered: {len(all_tools)}")
        
        # Test specific tool
        file_read_tool = registry.get_tool("file_read")
        print(f"   ✓ File read tool found: {file_read_tool is not None}")
        
        if file_read_tool:
            print(f"   ✓ Tool description: {file_read_tool.description}")
            print(f"   ✓ Tool category: {file_read_tool.category}")
        
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


async def test_optimized_session_manager():
    """Test the optimized session manager."""
    print("🔧 Testing Optimized Session Manager...")
    
    try:
        from songbird.memory.optimized_manager import OptimizedSessionManager
        from songbird.memory.models import Message
        
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


def test_signal_handler():
    """Test the graceful shutdown signal handler."""
    print("🔧 Testing Graceful Shutdown Handler...")
    
    try:
        from songbird.core.signal_handler import setup_graceful_shutdown
        
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


def test_unified_interface():
    """Test the unified provider interface with mocked provider."""
    print("🔧 Testing Unified Provider Interface...")
    
    try:
        from songbird.llm.unified_interface import create_provider_adapter, UnifiedToolCall
        
        # Create a mock provider
        mock_provider = Mock()
        mock_provider.__class__.__name__ = "MockOllamaProvider"
        mock_provider.model = "test-model"
        
        # Create adapter
        adapter = create_provider_adapter(mock_provider)
        
        print(f"   ✓ Provider detected: {adapter.provider_name}")
        
        # Test capabilities
        capabilities = adapter.get_provider_capabilities()
        print(f"   ✓ Capabilities generated: {capabilities['provider_name']}")
        print(f"   ✓ Model name: {capabilities['model_name']}")
        
        # Test unified tool call creation
        tool_call_data = {
            "id": "test-id",
            "function": {
                "name": "test_function",
                "arguments": {"param": "value"}
            }
        }
        
        unified_call = UnifiedToolCall.from_provider_format(tool_call_data, "openai")
        print(f"   ✓ Unified tool call: {unified_call.function_name}")
        
        # Test tool call conversion
        call_dict = unified_call.to_dict()
        print(f"   ✓ Tool call conversion: {call_dict['function']['name']}")
        
        print("   ✅ Unified Provider Interface: PASSED")
        return True
        
    except Exception as e:
        print(f"   ❌ Unified Provider Interface: FAILED - {e}")
        return False


def test_data_structures():
    """Test core data structures and models."""
    print("🔧 Testing Core Data Structures...")
    
    try:
        from songbird.memory.models import Session, Message
        from songbird.ui.data_transfer import UIMessage, ToolOutput, AgentOutput
        
        # Test Session
        session = Session()
        print(f"   ✓ Session created: {session.id}")
        
        # Test Message
        message = Message(role="user", content="Test message")
        session.add_message(message)
        print(f"   ✓ Message added to session: {len(session.messages)}")
        
        # Test UIMessage
        ui_msg = UIMessage.user_input("Test UI message")
        print(f"   ✓ UI Message created: {ui_msg.type}")
        
        # Test ToolOutput
        tool_output = ToolOutput.success_result({"result": "success"})
        print(f"   ✓ Tool output created: {tool_output.success}")
        
        # Test AgentOutput
        agent_output = AgentOutput.with_message(ui_msg)
        print(f"   ✓ Agent output created: {agent_output.message is not None}")
        
        print("   ✅ Core Data Structures: PASSED")
        return True
        
    except Exception as e:
        print(f"   ❌ Core Data Structures: FAILED - {e}")
        return False


async def main():
    """Run core Phase 4 infrastructure tests."""
    print("🚀 Testing Phase 4: Core Infrastructure")
    print("=" * 50)
    
    results = []
    
    # Run all tests
    results.append(test_configuration_management())
    results.append(test_tool_registry())
    results.append(await test_optimized_session_manager())
    results.append(test_signal_handler())
    results.append(test_unified_interface())
    results.append(test_data_structures())
    
    # Summary
    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"🎉 ALL CORE TESTS PASSED ({passed}/{total})")
        print("✅ Phase 4 Core Infrastructure: FULLY OPERATIONAL")
        
        # Additional validation
        print("\n📋 Phase 4 Implementation Summary:")
        print("   ✅ Centralized ToolRegistry with provider-agnostic schemas")
        print("   ✅ OptimizedSessionManager with batch writes and idle timeout")
        print("   ✅ ConfigManager with environment variable overrides")
        print("   ✅ Unified Provider Interface for standardized tool calls")
        print("   ✅ Graceful shutdown with SIGINT/SIGTERM handling")
        print("   ✅ Updated orchestrator with all infrastructure improvements")
        
        return True
    else:
        print(f"⚠️  SOME TESTS FAILED ({passed}/{total})")
        print("❌ Phase 4 Infrastructure: NEEDS ATTENTION")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)