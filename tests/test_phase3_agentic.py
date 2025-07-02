#!/usr/bin/env python3
"""Test Phase 3 agentic intelligence with planning and adaptive termination."""

import asyncio
import tempfile
from unittest.mock import Mock, AsyncMock
from songbird.orchestrator import SongbirdOrchestrator
from songbird.llm.types import ChatResponse


async def test_agentic_intelligence():
    """Test the new agentic intelligence with planning."""
    print("🧠 Testing Phase 3 Agentic Intelligence")
    
    # Create mock provider
    mock_provider = Mock()
    mock_provider.model = "test-model"
    
    # Simulate a complex multi-step workflow
    call_count = 0
    responses = [
        # Step 1: Initial planning or direct action
        ChatResponse(
            content="I'll help you create a simple Python project. Let me start by exploring the current directory.",
            model="test-model",
            tool_calls=[{
                "id": "call_1",
                "function": {
                    "name": "ls",
                    "args": {"path": "."}
                }
            }]
        ),
        # Step 2: Create project structure
        ChatResponse(
            content="Now I'll create the main project file.",
            model="test-model", 
            tool_calls=[{
                "id": "call_2",
                "function": {
                    "name": "file_create",
                    "args": {"file_path": "main.py", "content": "#!/usr/bin/env python3\nprint('Hello, World!')\n"}
                }
            }]
        ),
        # Step 3: Create requirements file
        ChatResponse(
            content="Let me add a requirements file for the project.",
            model="test-model",
            tool_calls=[{
                "id": "call_3", 
                "function": {
                    "name": "file_create",
                    "args": {"file_path": "requirements.txt", "content": "# Add your dependencies here\n"}
                }
            }]
        ),
        # Step 4: Verify the project
        ChatResponse(
            content="Let me verify the project structure is correct.",
            model="test-model",
            tool_calls=[{
                "id": "call_4",
                "function": {
                    "name": "ls", 
                    "args": {"path": "."}
                }
            }]
        ),
        # Step 5: Final response (no tools)
        ChatResponse(
            content="Perfect! I've successfully created a simple Python project with main.py and requirements.txt. The project is ready to use.",
            model="test-model",
            tool_calls=None
        ),
        # Step 6: Should terminate due to consecutive no-tools
        ChatResponse(
            content="The task is now complete.",
            model="test-model", 
            tool_calls=None
        )
    ]
    
    async def mock_chat(*args, **kwargs):
        nonlocal call_count
        if call_count < len(responses):
            response = responses[call_count]
            call_count += 1
            return response
        else:
            # Fallback response
            return ChatResponse(
                content="Task completed.",
                model="test-model",
                tool_calls=None
            )
    
    mock_provider.chat_with_messages = AsyncMock(side_effect=mock_chat)
    
    # Create temporary workspace
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"📁 Using temporary workspace: {temp_dir}")
        
        # Create orchestrator
        orchestrator = SongbirdOrchestrator(
            provider=mock_provider,
            working_directory=temp_dir
        )
        
        # Test complex multi-step workflow
        response = await orchestrator.chat_single_message(
            "Create a simple Python project with a main.py file and requirements.txt"
        )
        print(f"🤖 Final Response: {response}")
        
        # Verify conversation history
        history = orchestrator.get_conversation_history()
        print(f"📜 Conversation history: {len(history)} messages")
        
        # Count tool calls and responses
        tool_call_count = sum(1 for msg in history 
                             if isinstance(msg, dict) and msg.get("role") == "assistant" and msg.get("tool_calls"))
        tool_result_count = sum(1 for msg in history 
                               if isinstance(msg, dict) and msg.get("role") == "tool")
        
        print(f"🔧 Tool calls made: {tool_call_count}")
        print(f"📊 Tool results received: {tool_result_count}")
        
        # Verify provider was called multiple times (agentic loop)
        print(f"🔄 Provider called {mock_provider.chat_with_messages.call_count} times")
        
        # Check adaptive termination worked
        if mock_provider.chat_with_messages.call_count <= 6:
            print("✅ Adaptive termination worked (stopped before exhausting all responses)")
        else:
            print("⚠️  Adaptive termination may not have worked optimally")
        
        # Verify multi-step execution
        if tool_call_count >= 3:
            print("✅ Multi-step execution successful")
        else:
            print("⚠️  Multi-step execution may not have worked as expected")
        
        # Check if agent used multiple different tools
        tool_names = set()
        for msg in history:
            if isinstance(msg, dict) and msg.get("role") == "tool":
                tool_names.add(msg.get("name", "unknown"))
        
        print(f"🛠️  Tools used: {', '.join(tool_names)}")
        
        if len(tool_names) >= 2:
            print("✅ Multiple tools used successfully")
        else:
            print("⚠️  Limited tool variety used")
        
        print("\n🎉 Phase 3 Agentic Intelligence Test Completed!")
        return True


async def test_adaptive_termination():
    """Test adaptive termination criteria."""
    print("\n🛑 Testing Adaptive Termination Criteria")
    
    # Create mock provider for termination test
    mock_provider = Mock()
    mock_provider.model = "test-model"
    
    # Simulate an agent that doesn't use tools after 2 responses
    call_count = 0
    
    async def mock_chat_no_tools(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        
        if call_count <= 2:
            return ChatResponse(
                content=f"Response {call_count} without tools.",
                model="test-model",
                tool_calls=None
            )
        else:
            return ChatResponse(
                content="Should not reach this point due to termination.",
                model="test-model", 
                tool_calls=None
            )
    
    mock_provider.chat_with_messages = AsyncMock(side_effect=mock_chat_no_tools)
    
    # Create temporary workspace
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create orchestrator
        orchestrator = SongbirdOrchestrator(
            provider=mock_provider,
            working_directory=temp_dir
        )
        
        # Test termination
        response = await orchestrator.chat_single_message("Just give me a simple response")
        print(f"🤖 Response: {response}")
        
        # Verify termination happened quickly
        if mock_provider.chat_with_messages.call_count <= 2:
            print("✅ Adaptive termination worked - stopped after 2 consecutive no-tool responses")
        else:
            print(f"⚠️  Adaptive termination may have issues - called {mock_provider.chat_with_messages.call_count} times")
        
        print("🎯 Adaptive Termination Test Completed!")
        return True


if __name__ == "__main__":
    async def run_all_tests():
        await test_agentic_intelligence()
        await test_adaptive_termination()
        print("\n🏆 All Phase 3 Tests Completed!")
    
    asyncio.run(run_all_tests())