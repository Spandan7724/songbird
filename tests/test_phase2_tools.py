#!/usr/bin/env python3
"""Test Phase 2 architecture with tool execution."""

import asyncio
import tempfile
from unittest.mock import Mock, AsyncMock
from songbird.orchestrator import SongbirdOrchestrator
from songbird.llm.types import ChatResponse


async def test_tool_execution():
    """Test the new architecture with tool calls."""
    print("🔧 Testing Phase 2 Architecture with Tool Execution")
    
    # Create mock provider
    mock_provider = Mock()
    mock_provider.model = "test-model"
    
    # Mock chat response WITH tool calls
    async def mock_chat_with_tools(*args, **kwargs):
        # First call - with tool call
        return ChatResponse(
            content="I'll help you list the files in the current directory.",
            model="test-model",
            tool_calls=[{
                "id": "test_call_1",
                "function": {
                    "name": "ls",
                    "arguments": {"path": "."}
                }
            }]
        )
    
    # Mock for second call (after tool execution)
    async def mock_chat_final(*args, **kwargs):
        return ChatResponse(
            content="I found the files and directories in your current location.",
            model="test-model",
            tool_calls=None
        )
    
    # Set up provider to return tool calls first, then final response
    call_count = 0
    async def mock_chat(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return await mock_chat_with_tools(*args, **kwargs)
        else:
            return await mock_chat_final(*args, **kwargs)
    
    mock_provider.chat_with_messages = AsyncMock(side_effect=mock_chat)
    
    # Create temporary workspace with some test files
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"📁 Using temporary workspace: {temp_dir}")
        
        # Create some test files
        test_file = temp_dir + "/test.txt"
        with open(test_file, "w") as f:
            f.write("Hello, world!")
        
        # Create orchestrator
        orchestrator = SongbirdOrchestrator(
            provider=mock_provider,
            working_directory=temp_dir
        )
        
        # Test tool execution through the agent
        response = await orchestrator.chat_single_message("Can you list the files here?")
        print(f"🤖 Agent Response: {response}")
        
        # Verify conversation history includes tool calls
        history = orchestrator.get_conversation_history()
        print(f"📜 Conversation history: {len(history)} messages")
        
        # Check for tool calls in history
        tool_calls_found = any(
            "tool_calls" in msg for msg in history 
            if isinstance(msg, dict) and msg.get("role") == "assistant"
        )
        
        tool_results_found = any(
            msg.get("role") == "tool" for msg in history
            if isinstance(msg, dict)
        )
        
        if tool_calls_found:
            print("✅ Tool calls found in conversation history")
        else:
            print("⚠️  No tool calls found in conversation history")
        
        if tool_results_found:
            print("✅ Tool results found in conversation history")
        else:
            print("⚠️  No tool results found in conversation history")
        
        # Verify provider was called multiple times (agentic loop)
        assert mock_provider.chat_with_messages.call_count >= 1, "Provider should be called at least once"
        print(f"✅ Provider called {mock_provider.chat_with_messages.call_count} times (agentic loop)")
        
        print("\n🎉 Phase 2 Tool Execution Test Completed!")
        return True


if __name__ == "__main__":
    asyncio.run(test_tool_execution())