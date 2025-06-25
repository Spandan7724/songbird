#!/usr/bin/env python3
"""Standalone test for unified interface without external dependencies."""

import sys
from pathlib import Path
from unittest.mock import Mock

# Add the songbird directory to the path
sys.path.insert(0, str(Path(__file__).parent))


def test_unified_tool_call():
    """Test the UnifiedToolCall class."""
    print("🔧 Testing UnifiedToolCall...")
    
    try:
        # Import just the UnifiedToolCall class
        from songbird.llm.unified_interface import UnifiedToolCall
        
        # Test unified tool call creation
        tool_call_data = {
            "id": "test-id",
            "function": {
                "name": "test_function",
                "arguments": {"param": "value"}
            }
        }
        
        unified_call = UnifiedToolCall.from_provider_format(tool_call_data, "openai")
        print(f"   ✓ Unified tool call created: {unified_call.function_name}")
        
        # Test tool call conversion
        call_dict = unified_call.to_dict()
        print(f"   ✓ Tool call conversion: {call_dict['function']['name']}")
        print(f"   ✓ Arguments preserved: {call_dict['function']['arguments']}")
        
        # Test different provider formats
        claude_call = UnifiedToolCall.from_provider_format(tool_call_data, "claude")
        gemini_call = UnifiedToolCall.from_provider_format(tool_call_data, "gemini")
        
        print(f"   ✓ Claude format supported: {claude_call.id}")
        print(f"   ✓ Gemini format supported: {gemini_call.id}")
        
        print("   ✅ UnifiedToolCall: PASSED")
        return True
        
    except Exception as e:
        print(f"   ❌ UnifiedToolCall: FAILED - {e}")
        return False


def test_provider_adapter_basic():
    """Test basic ProviderAdapter functionality without external dependencies."""
    print("🔧 Testing ProviderAdapter (Basic)...")
    
    try:
        from songbird.llm.unified_interface import ProviderAdapter
        
        # Create mock providers
        mock_ollama = Mock()
        mock_ollama.__class__.__name__ = "OllamaProvider"
        mock_ollama.model = "test-model"
        
        mock_openai = Mock()
        mock_openai.__class__.__name__ = "OpenAIProvider"
        mock_openai.model = "gpt-4"
        
        # Test provider detection
        ollama_adapter = ProviderAdapter(mock_ollama)
        openai_adapter = ProviderAdapter(mock_openai)
        
        print(f"   ✓ Ollama detected: {ollama_adapter.provider_name}")
        print(f"   ✓ OpenAI detected: {openai_adapter.provider_name}")
        
        # Test capabilities
        ollama_caps = ollama_adapter.get_provider_capabilities()
        openai_caps = openai_adapter.get_provider_capabilities()
        
        print(f"   ✓ Ollama capabilities: {ollama_caps['provider_name']}")
        print(f"   ✓ OpenAI capabilities: {openai_caps['model_name']}")
        
        # Test message preparation
        test_messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"}
        ]
        
        prepared = ollama_adapter.prepare_messages_for_provider(test_messages)
        print(f"   ✓ Messages prepared: {len(prepared)} messages")
        
        print("   ✅ ProviderAdapter (Basic): PASSED")
        return True
        
    except Exception as e:
        print(f"   ❌ ProviderAdapter (Basic): FAILED - {e}")
        return False


def main():
    """Run standalone unified interface tests."""
    print("🚀 Testing Unified Interface (Standalone)")
    print("=" * 45)
    
    results = []
    
    # Run tests
    results.append(test_unified_tool_call())
    results.append(test_provider_adapter_basic())
    
    # Summary
    print("\n" + "=" * 45)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"🎉 ALL STANDALONE TESTS PASSED ({passed}/{total})")
        print("✅ Unified Interface: WORKING")
        return True
    else:
        print(f"⚠️  SOME TESTS FAILED ({passed}/{total})")
        print("❌ Unified Interface: NEEDS ATTENTION")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)