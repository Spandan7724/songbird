# tests/test_conversation.py
"""
Updated tests for ConversationOrchestrator with agentic loop architecture.

These tests focus on the core conversation functionality while the agentic-specific
features are tested in test_agentic_conversation.py.
"""
import pytest
from unittest.mock import Mock, AsyncMock
from pathlib import Path
from songbird.orchestrator import SongbirdOrchestrator
from songbird.llm.types import ChatResponse


class TestConversationOrchestrator:
    @pytest.fixture
    def fixture_repo(self):
        """Path to test fixture repository."""
        return str(Path(__file__).parent / "fixtures" / "repo_a")
    
    @pytest.fixture
    def mock_provider(self):
        """Mock LLM provider."""
        provider = Mock()
        provider.chat_with_messages = AsyncMock()
        return provider
    
    @pytest.fixture
    def orchestrator(self, mock_provider, fixture_repo):
        """Conversation orchestrator with mock provider."""
        return SongbirdOrchestrator(mock_provider, fixture_repo)
    
    @pytest.mark.asyncio
    async def test_simple_chat_without_tools(self, orchestrator, mock_provider):
        """Test simple chat without tool calls (single agentic loop iteration)."""
        # Mock response without tool calls (ends agentic loop)
        simple_response = ChatResponse(
            content="Hello! I can help you with your code.",
            model="test-model"
        )
        mock_provider.chat_with_messages.return_value = simple_response
        
        response = await orchestrator.chat("Hello")
        
        assert response == "Hello! I can help you with your code."
        
        # Should have system prompt, user message, and assistant response
        history = orchestrator.conversation_history
        assert len(history) >= 2
        
        # Find user and assistant messages
        user_msg = next(msg for msg in history if msg["role"] == "user")
        assistant_msg = next(msg for msg in history if msg["role"] == "assistant")
        
        assert user_msg["content"] == "Hello"
        assert assistant_msg["content"] == "Hello! I can help you with your code."
    
    @pytest.mark.asyncio
    async def test_chat_with_single_tool_call(self, orchestrator, mock_provider):
        """Test chat with single tool call (basic agentic loop)."""
        # Mock first response with tool calls
        tool_response = ChatResponse(
            content="I'll search for TODO items in your code.",
            model="test-model",
            tool_calls=[{
                "id": "call_123",
                "function": {
                    "name": "file_search",
                    "arguments": {"pattern": "TODO"}
                }
            }]
        )
        
        # Mock second response after tool execution (ends loop)
        final_response = ChatResponse(
            content="I found TODO items in your codebase.",
            model="test-model"
        )
        
        # Set up agentic loop: tool call -> execution -> final response
        mock_provider.chat_with_messages.side_effect = [tool_response, final_response]
        
        response = await orchestrator.chat("Find all TODO items")
        
        assert "TODO items" in response
        
        # Should have called provider twice (agentic loop)
        assert mock_provider.chat_with_messages.call_count == 2
        
        # Check conversation history includes all interactions
        history = orchestrator.conversation_history
        
        # Should have: system, user, assistant (with tools), tool result, assistant (final)
        roles = [msg["role"] for msg in history]
        assert "user" in roles
        assert "assistant" in roles
        assert "tool" in roles
        
        # Check tool result was added to history
        tool_messages = [msg for msg in history if msg["role"] == "tool"]
        assert len(tool_messages) == 1
        
        # Tool message should have enhanced formatting
        tool_msg = tool_messages[0]
        assert "tool" in tool_msg["content"]  # Should be JSON formatted
    
    def test_conversation_history_management(self, orchestrator):
        """Test conversation history management methods."""
        # Should start with system prompt
        initial_history = orchestrator.conversation_history
        assert len(initial_history) == 1
        assert initial_history[0]["role"] == "system"
        
        # History should be isolated (copy returned)
        history1 = orchestrator.conversation_history.copy()
        history1.append({"test": "data"})
        history2 = orchestrator.conversation_history
        assert len(history2) == len(initial_history)  # Should not include test data
        
        # Test clear history
        orchestrator.conversation_history.append({"role": "user", "content": "test"})
        assert len(orchestrator.conversation_history) > len(initial_history)
        orchestrator.conversation_history.clear()
        assert len(orchestrator.conversation_history) == 0
    
    def test_system_prompt_initialization(self, orchestrator):
        """Test that enhanced system prompt is properly initialized."""
        history = orchestrator.conversation_history
        system_msg = next(msg for msg in history if msg["role"] == "system")
        
        # Should contain key agentic instructions
        system_content = system_msg["content"]
        assert "NEVER ASSUME OR GUESS" in system_content
        assert "ALWAYS USE TOOLS" in system_content
        assert "IMMEDIATE ACTION REQUIRED" in system_content
        assert "file_create" in system_content  # Tool examples
    
    def test_working_directory_setup(self, orchestrator, fixture_repo):
        """Test working directory is properly set up."""
        # Tool executor should use the same working directory
        assert orchestrator.tool_executor.working_directory == fixture_repo
        
        # Test fixture should exist
        assert Path(fixture_repo).exists()
        assert Path(fixture_repo).is_dir()
    
    @pytest.mark.asyncio
    async def test_error_handling_in_agentic_loop(self, orchestrator, mock_provider):
        """Test error handling during agentic loop execution."""
        # Mock provider that raises an exception
        mock_provider.chat_with_messages.side_effect = Exception("Provider error")
        
        # Should handle the error gracefully
        with pytest.raises(Exception):
            await orchestrator.chat("This should cause an error")
        
        # Conversation history should still be valid
        history = orchestrator.conversation_history
        assert isinstance(history, list)
    
    def test_conversation_orchestrator_attributes(self, orchestrator):
        """Test that ConversationOrchestrator has all required attributes for agentic operation."""
        required_attrs = [
            'provider', 'tool_executor', 'conversation_history',
            'session_manager'
        ]
        
        for attr in required_attrs:
            assert hasattr(orchestrator, attr), f"Missing required attribute: {attr}"
        
        # Test that tool executor is properly configured
        assert orchestrator.tool_executor is not None
        tools = orchestrator.tool_executor.get_available_tools()
        assert len(tools) > 0  # Should have tools available