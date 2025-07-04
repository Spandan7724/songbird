# tests/test_integration.py
"""
Integration tests for the entire Songbird system.

Tests the complete flow from CLI input to file operations,
including provider integration, tool calling, and session management.
"""
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from songbird.llm.providers import (
    get_litellm_provider, list_available_providers, 
    get_default_provider
)
from songbird.llm.types import ChatResponse
from songbird.memory.models import Session
from songbird.orchestrator import SongbirdOrchestrator


class TestSongbirdIntegration:
    """Integration tests for the complete Songbird system."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Clean temporary workspace for integration tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    def test_provider_availability_detection(self):
        """Test that the system correctly detects available providers."""
        providers = list_available_providers()
        assert isinstance(providers, list)
        assert len(providers) > 0
        assert "ollama" in providers  # Always available
        
        # Test default provider selection
        default = get_default_provider()
        assert default in providers
    
    @pytest.mark.asyncio
    async def test_basic_agentic_workflow_with_mocks(self, temp_workspace):
        """Test basic agentic workflow with mocked provider."""
        # Create mock provider
        mock_provider = Mock()
        mock_provider.chat_with_messages = AsyncMock()
        
        # Mock agentic workflow: create file -> list directory -> done
        responses = [
            # First iteration: create file
            ChatResponse(
                content="I'll create the file for you.",
                model="test-model",
                tool_calls=[{
                    "id": "call_1",
                    "function": {
                        "name": "file_create",
                        "arguments": {"file_path": "test.txt", "content": "Hello Integration Test"}
                    }
                }]
            ),
            # Second iteration: list directory  
            ChatResponse(
                content="Now I'll show you the directory contents.",
                model="test-model",
                tool_calls=[{
                    "id": "call_2", 
                    "function": {
                        "name": "ls",
                        "arguments": {"path": "."}
                    }
                }]
            ),
            # Final iteration: no more tools
            ChatResponse(
                content="Task completed! I created test.txt and listed the directory.",
                model="test-model"
            )
        ]
        
        mock_provider.chat_with_messages.side_effect = responses
        
        # Test the full agentic workflow
        orchestrator = SongbirdOrchestrator(mock_provider, temp_workspace)
        
        response = await orchestrator.chat(
            "Please create a file called test.txt with 'Hello Integration Test' and then show me the directory contents"
        )
        
        # Verify agentic behavior
        assert "completed" in response
        assert mock_provider.chat_with_messages.call_count == 3
        
        # Verify file was actually created by tools
        test_file = Path(temp_workspace) / "test.txt"
        assert test_file.exists()
        assert test_file.read_text() == "Hello Integration Test"
        
        # Verify conversation history has all components
        history = orchestrator.get_conversation_history()
        roles = [msg["role"] for msg in history]
        assert "user" in roles
        assert "assistant" in roles
        assert "tool" in roles
        
        # Should have multiple tool executions
        tool_messages = [msg for msg in history if msg["role"] == "tool"]
        assert len(tool_messages) == 2  # file_create and ls

    @pytest.mark.asyncio
    async def test_error_recovery_in_agentic_loop(self, temp_workspace):
        """Test error recovery during agentic workflow."""
        mock_provider = Mock()
        mock_provider.chat_with_messages = AsyncMock()
        
        # Mock workflow with tool error
        responses = [
            ChatResponse(
                content="I'll try to read a file.",
                model="test-model", 
                tool_calls=[{
                    "id": "call_1",
                    "function": {
                        "name": "file_read", 
                        "arguments": {"file_path": "nonexistent.txt"}
                    }
                }]
            ),
            ChatResponse(
                content="The file doesn't exist, so I'll create it instead.",
                model="test-model",
                tool_calls=[{
                    "id": "call_2",
                    "function": {
                        "name": "file_create",
                        "arguments": {"file_path": "recovery.txt", "content": "Error recovery test"}
                    }
                }]
            ),
            ChatResponse(
                content="Successfully recovered from the error by creating a new file.",
                model="test-model"
            )
        ]
        
        mock_provider.chat_with_messages.side_effect = responses
        
        orchestrator = SongbirdOrchestrator(mock_provider, temp_workspace)
        
        response = await orchestrator.chat("Read nonexistent.txt")
        
        # Should complete despite initial error
        assert "recovered" in response or "Successfully" in response
        
        # Verify error recovery created the file
        recovery_file = Path(temp_workspace) / "recovery.txt"
        assert recovery_file.exists()
        
        # Verify error was properly handled in conversation
        history = orchestrator.get_conversation_history()
        tool_messages = [msg for msg in history if msg["role"] == "tool"]
        
        # First tool should show error, second should show success
        assert len(tool_messages) == 2
        
        # Parse the tool results to verify error handling
        import json
        first_result = json.loads(tool_messages[0]["content"])
        second_result = json.loads(tool_messages[1]["content"])
        
        assert first_result["success"] == False  # Read failed
        assert second_result["success"] == True  # Create succeeded

    @pytest.mark.skipif(
        os.system("curl -s http://localhost:11434/api/tags > /dev/null 2>&1") != 0,
        reason="Ollama server not running"
    )
    @pytest.mark.asyncio
    async def test_real_ollama_integration(self, temp_workspace):
        """Test integration with real Ollama server (if available)."""
        try:
            provider = get_litellm_provider(model="qwen2.5-coder:7b")
            orchestrator = SongbirdOrchestrator(provider, temp_workspace)
            
            # Simple test to verify Ollama integration
            response = await orchestrator.chat("Please create a simple Python file called hello.py that prints 'Hello Ollama!'")
            
            # Should get some response
            assert isinstance(response, str)
            assert len(response) > 0
            
            # Check if file was created (depends on model's tool usage)
            hello_file = Path(temp_workspace) / "hello.py"
            if hello_file.exists():
                content = hello_file.read_text()
                assert "Hello Ollama" in content or "print" in content
                
        except Exception as e:
            pytest.skip(f"Ollama integration test failed: {e}")

    def test_tool_availability_integration(self, temp_workspace):
        """Test that all expected tools are available in integration."""
        from songbird.tools.executor import ToolExecutor
        
        executor = ToolExecutor(temp_workspace)
        tools = executor.get_available_tools()
        
        # Verify we have all expected tools
        expected_tools = [
            "file_read", "file_create", "file_edit", 
            "file_search", "shell_exec", "ls", 
            "glob", "grep", "todo_read", "todo_write",
            "multi_edit"
        ]
        
        available_tool_names = [tool["function"]["name"] for tool in tools]
        
        for expected_tool in expected_tools:
            assert expected_tool in available_tool_names, f"Missing tool: {expected_tool}"
        
        # Verify tools have proper schema structure
        for tool in tools:
            assert "type" in tool
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]

    @pytest.mark.asyncio
    async def test_parallel_vs_sequential_execution_integration(self, temp_workspace):
        """Test that parallel vs sequential execution works in integration."""
        mock_provider = Mock()
        mock_provider.chat_with_messages = AsyncMock()
        
        # Test parallel-safe operations
        parallel_response = ChatResponse(
            content="I'll read multiple files in parallel.",
            model="test-model",
            tool_calls=[
                {"id": "call_1", "function": {"name": "ls", "arguments": {"path": "."}}},
                {"id": "call_2", "function": {"name": "file_search", "arguments": {"pattern": "test"}}},
                {"id": "call_3", "function": {"name": "grep", "arguments": {"pattern": "hello"}}}
            ]
        )
        
        final_response = ChatResponse(
            content="Parallel operations completed.",
            model="test-model"
        )
        
        mock_provider.chat_with_messages.side_effect = [parallel_response, final_response]
        
        orchestrator = SongbirdOrchestrator(mock_provider, temp_workspace)
        
        # Enable debug to see parallel execution
        with patch.dict(os.environ, {"SONGBIRD_DEBUG_TOOLS": "true"}):
            response = await orchestrator.chat("Search and list files")
        
        # Should complete successfully with parallel execution
        assert "completed" in response
        
        # Test sequential-required operations
        mock_provider.chat_with_messages.reset_mock()
        
        sequential_response = ChatResponse(
            content="I'll modify files sequentially.",
            model="test-model", 
            tool_calls=[
                {"id": "call_1", "function": {"name": "file_create", "arguments": {"file_path": "test1.txt", "content": "test"}}},
                {"id": "call_2", "function": {"name": "file_edit", "arguments": {"file_path": "test1.txt", "new_content": "edited"}}}
            ]
        )
        
        final_response = ChatResponse(
            content="Sequential operations completed.",
            model="test-model"
        )
        
        mock_provider.chat_with_messages.side_effect = [sequential_response, final_response]
        
        response = await orchestrator.chat("Create and edit a file")
        
        # Should complete successfully with sequential execution
        assert "completed" in response

    def test_enhanced_system_prompt_integration(self, temp_workspace):
        """Test that the enhanced system prompt is properly integrated."""
        mock_provider = Mock()
        orchestrator = SongbirdOrchestrator(mock_provider, temp_workspace)
        
        # Verify system prompt contains agentic instructions
        # In the new architecture, system prompt is stored in agent.system_prompt
        system_content = orchestrator.agent.system_prompt
        
        # Key agentic instructions should be present
        agentic_keywords = [
            "TOOL-FIRST APPROACH",
            "PLAN-THEN-EXECUTE", 
            "SYSTEMATIC EXECUTION",
            "VERIFICATION",
            "file_create", "file_edit", "file_read"  # Tool examples
        ]
        
        for keyword in agentic_keywords:
            assert keyword in system_content, f"Missing agentic instruction: {keyword}"

    @pytest.mark.asyncio
    async def test_conversation_persistence_integration(self, temp_workspace):
        """Test conversation persistence works with agentic workflow."""
        mock_provider = Mock()
        mock_provider.chat_with_messages = AsyncMock()
        
        # Create a session for persistence testing
        session = Session()
        orchestrator = SongbirdOrchestrator(mock_provider, temp_workspace, session=session)
        
        # Mock simple workflow
        response = ChatResponse(
            content="I'll help you with that.",
            model="test-model",
            tool_calls=[{
                "id": "call_1",
                "function": {
                    "name": "ls",
                    "arguments": {"path": "."}
                }
            }]
        )
        
        final_response = ChatResponse(
            content="Task completed.",
            model="test-model"
        )
        
        mock_provider.chat_with_messages.side_effect = [response, final_response]
        
        await orchestrator.chat("List files")
        
        # Verify session captured the conversation
        assert len(session.messages) > 0
        
        # Should have user, assistant, and tool messages
        message_roles = [msg.role for msg in session.messages]
        assert "user" in message_roles
        assert "assistant" in message_roles
        assert "tool" in message_roles