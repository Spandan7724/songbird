# tests/test_conversation.py
import pytest
from unittest.mock import Mock, AsyncMock
from pathlib import Path
from songbird.conversation import ConversationOrchestrator
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
        provider.chat.return_value = ChatResponse(
            content="Hello! I can help you with your code.",
            model="test-model"
        )
        provider.chat_with_messages.return_value = ChatResponse(
            content="Hello! I can help you with your code.",
            model="test-model"
        )
        return provider
    
    @pytest.fixture
    def orchestrator(self, mock_provider, fixture_repo):
        """Conversation orchestrator with mock provider."""
        return ConversationOrchestrator(mock_provider, fixture_repo)
    
    @pytest.mark.asyncio
    async def test_simple_chat_without_tools(self, orchestrator, mock_provider):
        """Test simple chat without tool calls."""
        response = await orchestrator.chat("Hello")
        
        assert response == "Hello! I can help you with your code."
        assert len(orchestrator.get_conversation_history()) == 2
        
        history = orchestrator.get_conversation_history()
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello"
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "Hello! I can help you with your code."
    
    @pytest.mark.asyncio
    async def test_chat_with_tool_calls(self, orchestrator, mock_provider):
        """Test chat that triggers tool calls."""
        # Mock first response with tool calls
        first_response = ChatResponse(
            content="I'll search for TODO items in your code.",
            model="test-model",
            tool_calls=[{
                "id": "call_123",
                "function": {
                    "name": "file_search",
                    "arguments": '{"pattern": "TODO"}'
                }
            }]
        )
        
        # Mock second response after tool execution
        second_response = ChatResponse(
            content="I found 6 TODO items in your codebase. Here are the results...",
            model="test-model"
        )
        
        # Set up side_effect for multiple calls
        mock_provider.chat_with_messages.side_effect = [first_response, second_response]
        
        response = await orchestrator.chat("Find all TODO items")
        
        assert "I found 6 TODO items" in response
        
        # Check conversation history includes tool interactions
        history = orchestrator.get_conversation_history()
        assert len(history) >= 3  # user, assistant, tool result
        
        # Check tool result was added to history
        tool_messages = [msg for msg in history if msg["role"] == "tool"]
        assert len(tool_messages) == 1
    
    def test_conversation_history_management(self, orchestrator):
        """Test conversation history management methods."""
        assert len(orchestrator.get_conversation_history()) == 0
        
        # History should be isolated (copy returned)
        history1 = orchestrator.get_conversation_history()
        history1.append({"test": "data"})
        history2 = orchestrator.get_conversation_history()
        assert len(history2) == 0
        
        # Test clear history
        orchestrator.conversation_history.append({"role": "user", "content": "test"})
        assert len(orchestrator.get_conversation_history()) == 1
        orchestrator.clear_history()
        assert len(orchestrator.get_conversation_history()) == 0