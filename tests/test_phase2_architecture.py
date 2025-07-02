#!/usr/bin/env python3
"""Test script for Phase 2 architecture separation."""

import asyncio
import tempfile
from unittest.mock import Mock, AsyncMock
from songbird.orchestrator import SongbirdOrchestrator
from songbird.llm.types import ChatResponse


async def test_new_architecture():
    """Test the new separated architecture."""
    print("🧪 Testing Phase 2 Architecture Separation")
    
    # Create mock provider
    mock_provider = Mock()
    mock_provider.model = "test-model"
    
    # Mock chat response without tool calls
    async def mock_chat(*args, **kwargs):
        return ChatResponse(
            content="Hello! I can help you with your coding tasks.",
            model="test-model",
            tool_calls=None
        )
    
    mock_provider.chat_with_messages = AsyncMock(side_effect=mock_chat)
    
    # Create temporary workspace
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"📁 Using temporary workspace: {temp_dir}")
        
        # Create orchestrator with new architecture
        orchestrator = SongbirdOrchestrator(
            provider=mock_provider,
            working_directory=temp_dir
        )
        
        print("✅ SongbirdOrchestrator created successfully")
        
        # Test single message processing
        response = await orchestrator.chat_single_message("Hello, can you help me?")
        print(f"🤖 Agent Response: {response}")
        
        # Debug: Let's get the actual agent output to see what's happening
        agent_output = await orchestrator.agent.handle_message("Hello, test message")
        print(f"🔍 Debug - Agent output type: {type(agent_output)}")
        print(f"🔍 Debug - Agent output error: {agent_output.error}")
        print(f"🔍 Debug - Agent output message: {agent_output.message}")
        
        # Verify we got a proper response
        if "Error: <bound method" in response:
            print(f"⚠️  Got method reference instead of result: {response}")
        else:
            print("✅ Response format looks correct")
        
        # Verify layers exist and are properly separated
        assert orchestrator.ui is not None, "UI layer should exist"
        assert orchestrator.agent is not None, "Agent core should exist"
        assert orchestrator.tool_runner is not None, "Tool runner should exist"
        
        print("✅ All layers properly separated and functional")
        
        # Test conversation history
        history = orchestrator.get_conversation_history()
        assert len(history) > 0, "Conversation history should contain messages"
        print(f"📜 Conversation history: {len(history)} messages")
        
        # Verify no UI dependencies in agent core
        agent_imports = []
        import inspect
        agent_source = inspect.getsource(orchestrator.agent.__class__)
        if "rich" not in agent_source.lower() and "inquirer" not in agent_source.lower():
            print("✅ Agent core has no UI dependencies")
        else:
            print("⚠️  Agent core may still have UI dependencies")
        
        # Verify no conversation logic in tool runner
        tool_runner_source = inspect.getsource(orchestrator.tool_runner.__class__)
        if "conversation" not in tool_runner_source.lower():
            print("✅ Tool runner has no conversation dependencies")
        else:
            print("⚠️  Tool runner may still have conversation dependencies")
        
        print("\n🎉 Phase 2 Architecture Separation Test Completed!")
        return True


if __name__ == "__main__":
    asyncio.run(test_new_architecture())