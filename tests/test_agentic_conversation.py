# tests/test_agentic_conversation.py
"""
Tests for the new agentic conversation architecture.

Tests the core agentic loop functionality, multi-step workflows,
parallel execution, and enhanced tool visibility.
"""
import pytest
import asyncio
import tempfile
import os
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
from songbird.conversation import ConversationOrchestrator
from songbird.llm.types import ChatResponse


class TestAgenticConversation:
    @pytest.fixture
    def mock_provider(self):
        """Mock LLM provider that supports agentic workflows."""
        provider = Mock()
        # Use AsyncMock that returns values directly, not coroutines
        provider.chat_with_messages = AsyncMock()
        return provider

    @pytest.fixture
    def temp_workspace(self):
        """Temporary workspace for agentic tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def orchestrator(self, mock_provider, temp_workspace):
        """Conversation orchestrator with mock provider in temp workspace."""
        return ConversationOrchestrator(mock_provider, temp_workspace)

    @pytest.mark.asyncio
    async def test_agentic_loop_single_iteration(self, orchestrator, mock_provider):
        """Test agentic loop with single tool call iteration."""
        # Mock response with tool calls
        tool_response = ChatResponse(
            content="I'll create a file for you.",
            model="test-model",
            tool_calls=[{
                "id": "call_123",
                "function": {
                    "name": "file_create", 
                    "arguments": {"file_path": "test.txt", "content": "Hello World"}
                }
            }]
        )
        
        # Mock final response after tool execution
        final_response = ChatResponse(
            content="File created successfully!",
            model="test-model"
        )
        
        # Configure AsyncMock to return responses in sequence
        mock_provider.chat_with_messages.side_effect = [tool_response, final_response]
        
        response = await orchestrator.chat("Create a test file")
        
        assert "File created successfully!" in response
        
        # Verify agentic loop executed
        assert mock_provider.chat_with_messages.call_count == 2
        
        # Check conversation history contains tool interactions
        history = orchestrator.get_conversation_history()
        tool_messages = [msg for msg in history if msg["role"] == "tool"]
        assert len(tool_messages) == 1

    @pytest.mark.asyncio
    async def test_agentic_loop_multiple_iterations(self, orchestrator, mock_provider):
        """Test agentic loop with multiple tool call iterations."""
        # First iteration: File creation
        first_response = ChatResponse(
            content="I'll create the file first.",
            model="test-model",
            tool_calls=[{
                "id": "call_1",
                "function": {
                    "name": "file_create",
                    "arguments": {"file_path": "calc.py", "content": "def add(a,b): return a+b"}
                }
            }]
        )
        
        # Second iteration: File testing
        second_response = ChatResponse(
            content="Now I'll test the file.",
            model="test-model", 
            tool_calls=[{
                "id": "call_2",
                "function": {
                    "name": "shell_exec",
                    "arguments": {"command": "python calc.py"}
                }
            }]
        )
        
        # Final iteration: No more tools
        final_response = ChatResponse(
            content="Calculator created and tested successfully!",
            model="test-model"
        )
        
        mock_provider.chat_with_messages.side_effect = [
            first_response, second_response, final_response
        ]
        
        response = await orchestrator.chat("Create and test a calculator")
        
        assert "successfully" in response
        
        # Verify multiple iterations
        assert mock_provider.chat_with_messages.call_count == 3
        
        # Check both tool calls were executed
        history = orchestrator.get_conversation_history()
        tool_messages = [msg for msg in history if msg["role"] == "tool"]
        assert len(tool_messages) == 2

    @pytest.mark.asyncio
    async def test_agentic_loop_max_iterations(self, orchestrator, mock_provider):
        """Test agentic loop respects max iterations limit."""
        # Mock infinite tool calling scenario
        infinite_response = ChatResponse(
            content="Calling another tool...",
            model="test-model",
            tool_calls=[{
                "id": "call_inf",
                "function": {
                    "name": "ls",
                    "arguments": {"path": "."}
                }
            }]
        )
        
        # Always return tool calls to trigger infinite loop
        mock_provider.chat_with_messages.return_value = infinite_response
        
        response = await orchestrator.chat("Test infinite loop")
        
        # Should hit max iterations (10) and stop
        assert mock_provider.chat_with_messages.call_count == 10

    @pytest.mark.asyncio
    async def test_parallel_tool_execution_detection(self, orchestrator):
        """Test detection of parallel-safe vs sequential tool operations."""
        # Test parallel-safe tools
        read_only_functions = ["ls", "file_read", "file_search", "grep"]
        assert orchestrator._can_execute_tools_in_parallel(read_only_functions) == True
        
        # Test file operations require sequential execution  
        file_ops = ["file_create", "file_edit"]
        assert orchestrator._can_execute_tools_in_parallel(file_ops) == False
        
        # Test mixed operations
        mixed = ["file_read", "file_create", "ls"]
        assert orchestrator._can_execute_tools_in_parallel(mixed) == False

    @pytest.mark.asyncio
    async def test_enhanced_tool_result_formatting(self, orchestrator):
        """Test enhanced tool result formatting for better LLM visibility."""
        # Test successful file operation formatting
        file_result = {
            "file_path": "/test/file.py",
            "content": "print('hello')",
            "lines_returned": 1
        }
        
        formatted = orchestrator._format_tool_result_for_llm("file_read", file_result, True)
        parsed = eval(formatted)  # Parse JSON
        
        assert parsed["tool"] == "file_read"
        assert parsed["success"] == True
        assert parsed["file_path"] == "/test/file.py"
        assert "hello" in parsed["content_preview"]
        
        # Test error formatting
        error_result = {"error": "File not found"}
        formatted_error = orchestrator._format_tool_result_for_llm("file_read", error_result, False)
        parsed_error = eval(formatted_error)
        
        assert parsed_error["success"] == False
        assert "File not found" in parsed_error["error"]

    def test_extract_function_name_different_formats(self, orchestrator):
        """Test function name extraction from different tool call formats."""
        # Ollama format
        ollama_call = Mock()
        ollama_call.function.name = "test_function"
        assert orchestrator._extract_function_name(ollama_call) == "test_function"
        
        # Dict format (Gemini)
        dict_call = {"function": {"name": "another_function"}}
        assert orchestrator._extract_function_name(dict_call) == "another_function"
        
        # Unknown format
        unknown_call = "invalid"
        assert orchestrator._extract_function_name(unknown_call) == "unknown"

    @pytest.mark.asyncio
    async def test_conversation_history_with_agentic_flow(self, orchestrator, mock_provider):
        """Test that conversation history properly tracks agentic workflow."""
        # Mock multi-step agentic response
        response_with_tools = ChatResponse(
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
            content="Task completed!",
            model="test-model"
        )
        
        mock_provider.chat_with_messages.side_effect = [response_with_tools, final_response]
        
        await orchestrator.chat("List files")
        
        history = orchestrator.get_conversation_history()
        
        # Should have: system, user, assistant with tools, tool result, final assistant
        expected_roles = ["system", "user", "assistant", "tool", "assistant"]
        actual_roles = [msg["role"] for msg in history]
        
        assert actual_roles == expected_roles
        
        # Tool message should have properly formatted content
        tool_msg = next(msg for msg in history if msg["role"] == "tool")
        assert "tool" in tool_msg["content"]  # Should be JSON formatted
        assert "success" in tool_msg["content"]

    @pytest.mark.asyncio 
    async def test_debug_mode_output(self, orchestrator, mock_provider):
        """Test debug mode provides visibility into agentic loop."""
        with patch.dict(os.environ, {"SONGBIRD_DEBUG_TOOLS": "true"}):
            response_with_tools = ChatResponse(
                content="Debug test",
                model="test-model", 
                tool_calls=[{
                    "id": "debug_call",
                    "function": {
                        "name": "ls",
                        "arguments": {"path": "."}
                    }
                }]
            )
            
            final_response = ChatResponse(
                content="Debug complete",
                model="test-model"
            )
            
            mock_provider.chat_with_messages.side_effect = [response_with_tools, final_response]
            
            # This should produce debug output
            response = await orchestrator.chat("Debug test")
            
            assert "Debug complete" in response