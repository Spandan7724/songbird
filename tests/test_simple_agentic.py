# tests/test_simple_agentic.py
"""
Simple agentic tests to verify basic functionality.
"""
import pytest
import tempfile
from unittest.mock import Mock, AsyncMock
from songbird.orchestrator import SongbirdOrchestrator
from songbird.llm.types import ChatResponse


class TestSimpleAgentic:
    """Simple tests for agentic functionality."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Temporary workspace."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def mock_provider(self):
        """Simple mock provider."""
        provider = Mock()
        # Configure AsyncMock to return values directly, not coroutines
        async def mock_chat(*args, **kwargs):
            # This will be overridden by return_value in individual tests
            return ChatResponse(content="Default response", model="test-model")
        provider.chat_with_messages = AsyncMock(side_effect=mock_chat)
        return provider
    
    @pytest.fixture
    def orchestrator(self, mock_provider, temp_workspace):
        """Simple orchestrator."""
        return SongbirdOrchestrator(mock_provider, temp_workspace)
    
    @pytest.mark.asyncio
    async def test_simple_chat_no_tools(self, orchestrator, mock_provider):
        """Test simple chat without tools."""
        expected_response = ChatResponse(
            content="Hello! I can help you.",
            model="test-model",
            tool_calls=None  # Explicitly set no tool calls
        )
        
        # Override the mock to return our specific response
        async def mock_chat(*args, **kwargs):
            return expected_response
        mock_provider.chat_with_messages.side_effect = mock_chat
        
        result = await orchestrator.chat("Hello")
        
        assert result == "Hello! I can help you."
        assert mock_provider.chat_with_messages.call_count == 1
    
    @pytest.mark.asyncio
    async def test_agentic_loop_methods_exist(self, orchestrator):
        """Test that agentic loop methods exist."""
        # Test parallel execution methods
        assert hasattr(orchestrator, '_can_execute_tools_in_parallel')
        assert hasattr(orchestrator, '_execute_tools_parallel')
        assert hasattr(orchestrator, '_execute_single_tool_async')
        assert hasattr(orchestrator, '_extract_function_name')
        assert hasattr(orchestrator, '_format_tool_result_for_llm')
        
        # Test basic functionality
        assert orchestrator._can_execute_tools_in_parallel(["file_read"]) == True
        assert orchestrator._can_execute_tools_in_parallel(["file_create"]) == False
        
    def test_tool_result_formatting(self, orchestrator):
        """Test tool result formatting."""
        result = {"file_path": "test.txt", "content": "hello"}
        formatted = orchestrator._format_tool_result_for_llm("file_read", result, True)
        
        import json
        parsed = json.loads(formatted)
        assert parsed["tool"] == "file_read"
        assert parsed["success"] == True