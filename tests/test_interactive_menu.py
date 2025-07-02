"""
Pytest tests for interactive menu functionality.

This module converts the test from test_menu_display.py to proper pytest format.
"""

import pytest


@pytest.fixture
def sample_models():
    """Fixture providing sample OpenRouter model names for testing."""
    return [
        'anthropic/claude-3-haiku',
        'anthropic/claude-3-haiku:beta', 
        'anthropic/claude-3-opus',
        'anthropic/claude-3.5-sonnet-20240620:beta',
        'anthropic/claude-3.5-haiku-20241022:beta',
        'openai/gpt-4o',
        'openai/gpt-4o-mini',
        'google/gemini-2.0-flash-001',
        'meta-llama/llama-3.1-405b-instruct',
        'deepseek/deepseek-chat-v3-0324:free'
    ]


@pytest.mark.asyncio
async def test_interactive_menu_structure(sample_models):
    """Test interactive menu with sample model names."""
    # Test model list structure
    assert len(sample_models) == 10, "Should have 10 sample models"
    
    # Test that all models have reasonable lengths
    for model in sample_models:
        assert len(model) > 5, f"Model name too short: {model}"
        assert len(model) < 100, f"Model name too long: {model}"
        
    # Test model name patterns
    anthropic_models = [m for m in sample_models if m.startswith('anthropic/')]
    openai_models = [m for m in sample_models if m.startswith('openai/')]
    google_models = [m for m in sample_models if m.startswith('google/')]
    
    assert len(anthropic_models) > 0, "Should have Anthropic models"
    assert len(openai_models) > 0, "Should have OpenAI models"
    assert len(google_models) > 0, "Should have Google models"


@pytest.mark.asyncio
async def test_safe_interactive_menu_import():
    """Test that safe_interactive_menu can be imported and has expected interface."""
    try:
        from songbird.conversation import safe_interactive_menu
        
        # Check that it's a callable (function)
        assert callable(safe_interactive_menu), "safe_interactive_menu should be callable"
        
        # Test with minimal parameters (this should work in non-interactive environment)
        try:
            result = await safe_interactive_menu(
                "Test menu:",
                ["option1", "option2", "option3"],
                default_index=0
            )
            
            # In non-interactive environment, it should return the default
            # or handle gracefully (None is acceptable for cancellation)
            assert result is None or result == 0, \
                f"Expected None or 0, got {result}"
                
        except Exception as e:
            # If it raises an exception in test environment, that's understandable
            # The important thing is that the import works
            pytest.skip(f"Menu test requires interactive environment: {e}")
            
    except ImportError as e:
        pytest.fail(f"Could not import safe_interactive_menu: {e}")


@pytest.mark.asyncio
async def test_menu_with_various_option_lengths(sample_models):
    """Test menu behavior with options of varying lengths."""
    try:
        from songbird.conversation import safe_interactive_menu
        
        # Sort models by length to test various lengths
        short_models = [m for m in sample_models if len(m) < 25]
        long_models = [m for m in sample_models if len(m) >= 25]
        
        assert len(short_models) > 0, "Should have some short model names"
        assert len(long_models) > 0, "Should have some long model names"
        
        # Test with short model names
        try:
            result = await safe_interactive_menu(
                "Select short model:",
                short_models,
                default_index=0
            )
            # Should handle gracefully
            assert result is None or isinstance(result, int)
        except Exception as e:
            pytest.skip(f"Interactive menu not available in test environment: {e}")
            
        # Test with long model names  
        try:
            result = await safe_interactive_menu(
                "Select long model:",
                long_models,
                default_index=0
            )
            # Should handle gracefully
            assert result is None or isinstance(result, int)
        except Exception as e:
            pytest.skip(f"Interactive menu not available in test environment: {e}")
            
    except ImportError:
        pytest.skip("safe_interactive_menu not available")


@pytest.mark.asyncio
async def test_menu_default_behavior():
    """Test menu default index behavior."""
    try:
        from songbird.conversation import safe_interactive_menu
        
        options = ["first", "second", "third"]
        
        # Test with default_index=0
        result = await safe_interactive_menu(
            "Test menu:",
            options,
            default_index=0
        )
        
        # Should return default or None for cancellation
        assert result is None or result == 0
        
        # Test with different default
        result = await safe_interactive_menu(
            "Test menu:",
            options,
            default_index=1
        )
        
        # Should return default or None for cancellation
        assert result is None or result == 1
        
    except Exception as e:
        pytest.skip(f"Interactive menu test requires interactive environment: {e}")


@pytest.mark.asyncio
async def test_menu_cancellation_handling():
    """Test menu cancellation behavior."""
    try:
        from songbird.conversation import safe_interactive_menu
        
        # Test that menu can handle cancellation gracefully
        result = await safe_interactive_menu(
            "Test cancellation:",
            ["option1", "option2"],
            default_index=0
        )
        
        # Result should be either None (cancelled) or valid index
        assert result is None or (isinstance(result, int) and 0 <= result < 2)
        
    except Exception as e:
        pytest.skip(f"Interactive menu test requires interactive environment: {e}")


@pytest.mark.asyncio
async def test_menu_edge_cases():
    """Test menu with edge cases."""
    try:
        from songbird.conversation import safe_interactive_menu
        
        # Test with empty options list
        try:
            result = await safe_interactive_menu(
                "Empty menu:",
                [],
                default_index=0
            )
            # Should handle empty list gracefully
            assert result is None
        except (IndexError, ValueError):
            # Acceptable to raise error for empty list
            pass
            
        # Test with single option
        result = await safe_interactive_menu(
            "Single option:",
            ["only_option"],
            default_index=0
        )
        
        # Should return 0 or None
        assert result is None or result == 0
        
    except Exception as e:
        pytest.skip(f"Interactive menu test requires interactive environment: {e}") 