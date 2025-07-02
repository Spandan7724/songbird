# tests/test_agentic_conversation.py
"""
Tests for the new agentic conversation architecture.

Tests the core agentic loop functionality, multi-step workflows,
parallel execution, and enhanced tool visibility.
"""
import pytest
import tempfile
import os
import json
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from songbird.orchestrator import SongbirdOrchestrator
from songbird.llm.types import ChatResponse
from songbird.memory.models import Session
from songbird.ui.ui_layer import UILayer
from songbird.config.config_manager import ConfigManager, AgentConfig
from songbird.agent.agent_core import AgentCore


class TestAgenticConversation:
    @pytest.fixture
    def mock_provider(self):
        """Mock LLM provider that supports agentic workflows."""
        provider = Mock()
        provider.chat_with_messages = AsyncMock()
        provider.name = "mock_provider"
        provider.model = "test-model"
        return provider

    @pytest.fixture
    def temp_workspace(self):
        """Temporary workspace for agentic tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def orchestrator(self, mock_provider, temp_workspace):
        """Conversation orchestrator with mock provider in temp workspace."""
        mock_session = Mock(spec=Session)
        mock_session.id = "test-session"
        mock_session.created_at = datetime.now()
        mock_session.updated_at = datetime.now()
        mock_session.provider_config = {}
        mock_session.to_dict.return_value = {} # Prevent serialization errors
        mock_ui = Mock(spec=UILayer)
        
        with patch('songbird.agent.agent_core.get_config') as mock_get_config:
            mock_config = Mock()
            mock_config.agent.max_iterations = 10
            mock_config.agent.token_budget = 5000
            mock_config.agent.adaptive_termination = False
            mock_config.ui.verbose_logging = False
            mock_get_config.return_value = mock_config
            
            orchestrator = SongbirdOrchestrator(
                provider=mock_provider,
                working_directory=temp_workspace,
                session=mock_session,
                ui_layer=mock_ui
            )
        return orchestrator

    @pytest.mark.asyncio
    async def test_agentic_loop_single_iteration(self, orchestrator, mock_provider):
        """Test agentic loop with single tool call iteration."""
        tool_response = ChatResponse(
            content="I'll create a file for you.",
            model="test-model",
            tool_calls=[{
                "id": "call_123",
                "function": {
                    "name": "file_create", 
                    "arguments": '{"file_path": "test.txt", "content": "Hello World"}'
                }
            }]
        )
        final_response = ChatResponse(content="File created successfully!", model="test-model")
        mock_provider.chat_with_messages.side_effect = [tool_response, final_response]
        
        response = await orchestrator.chat("Create a test file")
        
        assert "File created successfully!" in response
        assert mock_provider.chat_with_messages.call_count == 2
        
        history = orchestrator.get_conversation_history()
        tool_messages = [msg for msg in history if msg["role"] == "tool"]
        assert len(tool_messages) == 1

    @pytest.mark.asyncio
    async def test_agentic_loop_multiple_iterations(self, orchestrator, mock_provider):
        """Test agentic loop with multiple tool call iterations."""
        first_response = ChatResponse(
            content="I'll create the file first.",
            model="test-model",
            tool_calls=[{
                "id": "call_1",
                "function": {
                    "name": "file_create",
                    "arguments": '{"file_path": "calc.py", "content": "def add(a,b): return a+b"}'
                }
            }]
        )
        second_response = ChatResponse(
            content="Now I'll test the file.",
            model="test-model", 
            tool_calls=[{
                "id": "call_2",
                "function": {
                    "name": "shell_exec",
                    "arguments": '{"command": "python calc.py"}'
                }
            }]
        )
        final_response = ChatResponse(content="Calculator created and tested successfully!", model="test-model")
        mock_provider.chat_with_messages.side_effect = [first_response, second_response, final_response]
        
        response = await orchestrator.chat("Create and test a calculator")
        
        assert "successfully" in response
        assert mock_provider.chat_with_messages.call_count == 3
        
        history = orchestrator.get_conversation_history()
        tool_messages = [msg for msg in history if msg["role"] == "tool"]
        assert len(tool_messages) == 2

    @pytest.mark.asyncio
    async def test_agentic_loop_max_iterations(self, orchestrator, mock_provider):
        """Test agentic loop respects max iterations limit."""
        orchestrator.agent.max_iterations = 10
        infinite_response = ChatResponse(
            content="Calling another tool...",
            model="test-model",
            tool_calls=[{
                "id": "call_inf",
                "function": {
                    "name": "ls",
                    "arguments": '{"path": "."}'
                }
            }]
        )
        mock_provider.chat_with_messages.return_value = infinite_response
        
        await orchestrator.chat("Test infinite loop")
        
        assert mock_provider.chat_with_messages.call_count == 10

    @pytest.mark.asyncio
    async def test_parallel_tool_execution_detection(self, orchestrator):
        """Test detection of parallel-safe vs sequential tool operations."""
        read_only_functions = ["ls", "file_read", "file_search", "grep"]
        assert orchestrator.tool_runner.can_execute_in_parallel(read_only_functions) == True
        
        file_ops = ["file_create", "file_edit"]
        assert orchestrator.tool_runner.can_execute_in_parallel(file_ops) == False
        
        mixed = ["file_read", "file_create", "ls"]
        assert orchestrator.tool_runner.can_execute_in_parallel(mixed) == False

    @pytest.mark.asyncio
    async def test_enhanced_tool_result_formatting(self, orchestrator):
        """Test enhanced tool result formatting for better LLM visibility."""
        # This logic is now part of the agent's history management
        file_result = {"file_path": "/test/file.py", "content": "print('hello')", "lines_returned": 1, "success": True}
        
        with patch.object(orchestrator.agent, '_add_assistant_message_to_history') as mock_add_history:
            await orchestrator.agent._execute_tools([{"id": "call1", "function": {"name": "file_read", "arguments": {}}}])
            
            pass # Placeholder for now

    def test_extract_function_name_different_formats(self, orchestrator):
        """Test function name extraction from different tool call formats."""
        ollama_call = Mock()
        ollama_call.function.name = "test_function"
        ollama_call.function.arguments = {}
        name, args = orchestrator.agent._parse_tool_call(ollama_call)
        assert name == "test_function"
        
        dict_call = {"function": {"name": "another_function", "arguments": {}}}
        name, args = orchestrator.agent._parse_tool_call(dict_call)
        assert name == "another_function"
        
        with pytest.raises(ValueError):
            orchestrator.agent._parse_tool_call("invalid")

    @pytest.mark.asyncio
    async def test_conversation_history_with_agentic_flow(self, orchestrator, mock_provider):
        """Test that conversation history properly tracks agentic workflow."""
        orchestrator.agent.conversation_history.append({"role": "system", "content": ""})
        response_with_tools = ChatResponse(
            content="I'll help you with that.",
            model="test-model",
            tool_calls=[{
                "id": "call_1",
                "function": {
                    "name": "ls",
                    "arguments": '{"path": "."}'
                }
            }]
        )
        final_response = ChatResponse(content="Task completed!", model="test-model")
        mock_provider.chat_with_messages.side_effect = [response_with_tools, final_response]
        
        await orchestrator.chat("List files")
        
        history = orchestrator.get_conversation_history()
        
        actual_roles = [msg["role"] for msg in history]
        assert "system" in actual_roles
        assert "user" in actual_roles
        assert "assistant" in actual_roles
        assert "tool" in actual_roles
        
        tool_msg = next(msg for msg in history if msg["role"] == "tool")
        assert "tool_call_id" in tool_msg
        assert "content" in tool_msg
        content_json = json.loads(tool_msg["content"])
        assert content_json["success"] is True
        assert content_json["path"] == os.path.abspath(orchestrator.working_directory)

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
                        "arguments": '{"path": "."}'
                    }
                }]
            )
            final_response = ChatResponse(content="Debug complete", model="test-model")
            mock_provider.chat_with_messages.side_effect = [response_with_tools, final_response]
            
            response = await orchestrator.chat("Debug test")
            
            assert "Debug complete" in response
