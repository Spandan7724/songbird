import sys
import pytest

# Add the songbird package to Python path
sys.path.insert(0, '/home/spandan/projects/songbird')

from songbird.llm.copilot_provider import CopilotProvider


@pytest.mark.asyncio
async def test_copilot_provider_initialization():
    """Test GitHub Copilot provider initialization."""
    provider = CopilotProvider(model="gpt-4o")
    
    assert provider.get_provider_name() is not None
    assert provider.get_model_name() == "gpt-4o"


@pytest.mark.asyncio
async def test_copilot_chat_basic():
    """Test GitHub Copilot provider with a simple chat."""
    # Initialize provider
    provider = CopilotProvider(model="gpt-4o")
    
    # Test basic chat
    messages = [
        {"role": "user", "content": "Hello! Please respond with exactly: 'GitHub Copilot is working!'"}
    ]

    response = await provider.chat_with_messages(messages)
    
    # Assertions
    assert response is not None
    assert response.content is not None
    assert len(response.content) > 0
    assert response.model is not None
    
    # Check if the response contains expected content (case-insensitive)
    assert "copilot" in response.content.lower() or "working" in response.content.lower()


@pytest.mark.asyncio
async def test_copilot_chat_with_usage():
    """Test GitHub Copilot provider chat and verify usage information."""
    provider = CopilotProvider(model="gpt-4o")
    
    messages = [
        {"role": "user", "content": "What is 2+2?"}
    ]

    response = await provider.chat_with_messages(messages)
    
    # Assertions
    assert response is not None
    assert response.content is not None
    assert response.model is not None
    
    # Usage might be None depending on the provider implementation
    # So we just check if it exists, we don't assert it's not None
    if response.usage:
        assert hasattr(response.usage, '__dict__') or isinstance(response.usage, dict)


@pytest.mark.asyncio
async def test_copilot_chat_error_handling():
    """Test GitHub Copilot provider error handling with invalid input."""
    provider = CopilotProvider(model="gpt-4o")
    
    # Test with empty messages
    with pytest.raises(Exception):
        await provider.chat_with_messages([])


if __name__ == "__main__":
    # Allow running the file directly for debugging
    pytest.main([__file__, "-v"])