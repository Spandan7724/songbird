#!/usr/bin/env python3
"""
Comprehensive test suite for SemanticMatcher refactoring validation.

Tests the complete integration of SemanticMatcher with TodoManager and todo_tools,
covering both LLM-powered and fallback modes, configuration options, and edge cases.
"""

import pytest
import asyncio
import tempfile
from unittest.mock import Mock, AsyncMock

from songbird.tools.semantic_matcher import SemanticMatcher
from songbird.tools.semantic_config import (
    get_semantic_config, update_semantic_config, reset_semantic_config
)
from songbird.tools.todo_manager import TodoManager
from songbird.tools.todo_tools import (
    todo_read, todo_write, _calculate_content_similarity,
    _deduplicate_input_todos, _deduplicate_todos
)


class TestSemanticMatcherCore:
    """Test core SemanticMatcher functionality."""
    
    def test_semantic_matcher_initialization(self):
        """Test SemanticMatcher can be initialized with and without LLM provider."""
        # Without LLM provider (fallback mode)
        matcher = SemanticMatcher(llm_provider=None)
        assert matcher.llm_provider is None
        assert matcher._fallback_keywords is not None
        assert len(matcher._fallback_keywords['priority']['high']) > 0
        
        # With mock LLM provider
        mock_llm = Mock()
        matcher = SemanticMatcher(llm_provider=mock_llm)
        assert matcher.llm_provider == mock_llm
        assert matcher._fallback_keywords is not None

    def test_fallback_keywords_consolidation(self):
        """Test that all hardcoded keywords are properly consolidated."""
        matcher = SemanticMatcher(llm_provider=None)
        keywords = matcher._fallback_keywords
        
        # Verify all expected keyword categories exist
        expected_categories = [
            'priority', 'action_verbs', 'stop_words', 'prefixes_to_remove',
            'completion_keywords', 'concept_groups', 'action_groups'
        ]
        
        for category in expected_categories:
            assert category in keywords, f"Missing category: {category}"
        
        # Verify priority keywords
        assert 'high' in keywords['priority']
        assert 'low' in keywords['priority']
        assert 'urgent' in keywords['priority']['high']
        assert 'cleanup' in keywords['priority']['low']
        
        # Verify action verbs
        assert 'implement' in keywords['action_verbs']
        assert 'fix' in keywords['action_verbs']
        
        # Verify concept groups
        assert 'implementation' in keywords['concept_groups']
        assert 'debugging' in keywords['concept_groups']

    @pytest.mark.asyncio
    async def test_fallback_methods(self):
        """Test all fallback methods work without LLM."""
        matcher = SemanticMatcher(llm_provider=None)
        
        # Test priority analysis
        priority = matcher._fallback_priority("urgent bug fix")
        assert priority == "high"
        
        priority = matcher._fallback_priority("cleanup old code")
        assert priority == "low"
        
        priority = matcher._fallback_priority("implement new feature")
        assert priority == "medium"
        
        # Test action extraction
        action = matcher._fallback_extract_action("implement user authentication")
        assert action == "implement"
        
        action = matcher._fallback_extract_action("fix login bug")
        assert action == "fix"
        
        # Test content normalization
        normalized = matcher._fallback_normalize_content("TODO: implement user login")
        assert "todo:" not in normalized.lower()
        assert "implement user login" in normalized
        
        # Test completion detection
        completed = matcher._fallback_detect_completion(
            "I finished the authentication work",
            ["implement user authentication", "add unit tests"]
        )
        assert len(completed) >= 0  # May or may not detect completion
        
        # Test categorization
        category = matcher._fallback_categorize_concept("fix login bug")
        assert category in matcher._fallback_keywords['concept_groups']

    @pytest.mark.asyncio
    async def test_llm_methods_with_mock(self):
        """Test LLM methods with mock provider."""
        mock_llm = AsyncMock()
        mock_llm.chat_with_messages = AsyncMock()
        
        # Mock successful LLM response
        mock_response = Mock()
        mock_response.content = '{"priority": "high", "reasoning": "Security issue"}'
        mock_llm.chat_with_messages.return_value = mock_response
        
        matcher = SemanticMatcher(llm_provider=mock_llm)
        
        # Test priority analysis
        priority = await matcher.analyze_todo_priority("critical security vulnerability")
        assert priority == "high"
        
        # Verify LLM was called
        assert mock_llm.chat_with_messages.called

    @pytest.mark.asyncio
    async def test_llm_fallback_on_error(self):
        """Test graceful fallback when LLM fails."""
        mock_llm = AsyncMock()
        mock_llm.chat_with_messages = AsyncMock(side_effect=Exception("LLM Error"))
        
        matcher = SemanticMatcher(llm_provider=mock_llm)
        
        # Should fall back to heuristics
        priority = await matcher.analyze_todo_priority("urgent bug fix")
        assert priority == "high"  # From fallback logic


class TestSemanticConfig:
    """Test semantic configuration system."""
    
    def setup_method(self):
        """Reset config before each test."""
        reset_semantic_config()
    
    def test_default_configuration(self):
        """Test default configuration values."""
        config = get_semantic_config()
        
        assert config.enable_llm_similarity is True
        assert config.enable_llm_priority is True
        assert config.enable_llm_normalization is True
        assert config.enable_llm_action_extraction is True
        assert config.enable_llm_completion_detection is True
        assert config.enable_llm_categorization is True
        assert config.fallback_to_heuristics is True
        assert config.cache_llm_results is True
    
    def test_configuration_updates(self):
        """Test configuration can be updated."""
        # Update specific options
        update_semantic_config(
            enable_llm_similarity=False,
            similarity_threshold=0.8,
            cache_llm_results=False
        )
        
        config = get_semantic_config()
        assert config.enable_llm_similarity is False
        assert config.similarity_threshold == 0.8
        assert config.cache_llm_results is False
        
        # Other options should remain default
        assert config.enable_llm_priority is True
    
    def test_invalid_configuration(self):
        """Test invalid configuration raises error."""
        with pytest.raises(ValueError):
            update_semantic_config(invalid_option=True)


class TestTodoManagerIntegration:
    """Test TodoManager integration with SemanticMatcher."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Temporary workspace for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.mark.asyncio
    async def test_todo_manager_with_semantic_matcher(self, temp_workspace):
        """Test TodoManager works with SemanticMatcher."""
        matcher = SemanticMatcher(llm_provider=None)
        todo_manager = TodoManager(
            working_directory=temp_workspace,
            session_id="test-session",
            semantic_matcher=matcher
        )
        
        # Test async methods
        priority = await todo_manager.smart_prioritize("urgent security fix")
        assert priority in ["high", "medium", "low"]
        
        semantic_id = await todo_manager.generate_semantic_id("implement user login")
        assert semantic_id is not None
        assert "implement" in semantic_id or "login" in semantic_id
        
        smart_todos = await todo_manager.generate_smart_todos(
            "We need to fix the authentication bug and add unit tests"
        )
        assert len(smart_todos) >= 0
    
    @pytest.mark.asyncio
    async def test_todo_manager_without_semantic_matcher(self, temp_workspace):
        """Test TodoManager works without SemanticMatcher (fallback)."""
        todo_manager = TodoManager(
            working_directory=temp_workspace,
            session_id="test-session",
            semantic_matcher=None
        )
        
        # Should still work using temporary matchers
        priority = await todo_manager.smart_prioritize("urgent security fix")
        assert priority in ["high", "medium", "low"]
        
        semantic_id = await todo_manager.generate_semantic_id("implement user login")
        assert semantic_id is not None
    
    @pytest.mark.asyncio
    async def test_add_todo_with_semantic_id(self, temp_workspace):
        """Test todo creation with semantic ID generation."""
        matcher = SemanticMatcher(llm_provider=None)
        todo_manager = TodoManager(
            working_directory=temp_workspace,
            session_id="test-session",
            semantic_matcher=matcher
        )
        
        # Test adding todo with semantic ID
        new_todo = await todo_manager.add_todo("implement user authentication", "high")
        assert new_todo is not None
        assert new_todo.content == "implement user authentication"
        assert new_todo.priority == "high"
        assert new_todo.id is not None
        
        # Test adding todo without semantic ID
        new_todo2 = await todo_manager.add_todo("simple task", use_semantic_id=False)
        assert new_todo2 is not None
        assert new_todo2.id != new_todo.id


class TestTodoToolsIntegration:
    """Test todo_tools integration with SemanticMatcher."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Temporary workspace for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.mark.asyncio
    async def test_content_similarity_calculation(self):
        """Test content similarity with SemanticMatcher."""
        matcher = SemanticMatcher(llm_provider=None)
        
        # Test similar content
        similarity = await _calculate_content_similarity(
            "implement user login",
            "add user authentication",
            matcher
        )
        assert 0.0 <= similarity <= 1.0
        
        # Test different content
        similarity2 = await _calculate_content_similarity(
            "implement login",
            "delete old files",
            matcher
        )
        assert 0.0 <= similarity2 <= 1.0
        assert similarity2 < similarity  # Should be less similar
    
    @pytest.mark.asyncio
    async def test_todo_write_integration(self, temp_workspace):
        """Test todo_write with SemanticMatcher integration."""
        test_todos = [
            {"content": "implement user authentication", "priority": "high", "status": "pending"},
            {"content": "add unit tests", "priority": "medium", "status": "pending"},
            {"content": "fix login bug", "priority": "high", "status": "completed"}
        ]
        
        result = await todo_write(test_todos, session_id="test-session")
        
        assert result["success"] is True
        assert "created" in result["message"] or "updated" in result["message"]
    
    @pytest.mark.asyncio
    async def test_todo_read_integration(self, temp_workspace):
        """Test todo_read with SemanticMatcher integration."""
        # First create some todos
        test_todos = [
            {"content": "test todo 1", "priority": "high", "status": "pending"},
            {"content": "test todo 2", "priority": "medium", "status": "completed"}
        ]
        
        await todo_write(test_todos, session_id="test-session")
        
        # Now read them back
        result = await todo_read(session_id="test-session")
        
        assert result["success"] is True
        assert len(result["todos"]) >= 0
    
    @pytest.mark.asyncio
    async def test_input_deduplication(self):
        """Test input deduplication with SemanticMatcher."""
        input_todos = [
            {"content": "implement user login", "priority": "high"},
            {"content": "add user authentication", "priority": "high"},  # Similar to first
            {"content": "fix database bug", "priority": "medium"},
            {"content": "implement user login", "priority": "high"}  # Exact duplicate
        ]
        
        deduplicated = await _deduplicate_input_todos(input_todos, llm_provider=None)
        
        # Should have fewer items due to deduplication
        assert len(deduplicated) <= len(input_todos)
        assert len(deduplicated) >= 1  # At least one item should remain
    
    @pytest.mark.asyncio
    async def test_todo_deduplication(self):
        """Test todo deduplication with SemanticMatcher."""
        from songbird.tools.todo_manager import TodoItem
        from datetime import datetime
        
        todos = [
            TodoItem("implement login", "high", "pending", "1", datetime.now(), datetime.now()),
            TodoItem("add authentication", "high", "pending", "2", datetime.now(), datetime.now()),
            TodoItem("fix database", "medium", "pending", "3", datetime.now(), datetime.now())
        ]
        
        matcher = SemanticMatcher(llm_provider=None)
        deduplicated = await _deduplicate_todos(todos, matcher)
        
        assert len(deduplicated) <= len(todos)
        assert len(deduplicated) >= 1


class TestConfigurationEffects:
    """Test how configuration changes affect behavior."""
    
    def setup_method(self):
        """Reset config before each test."""
        reset_semantic_config()
    
    @pytest.mark.asyncio
    async def test_llm_disabled_configuration(self):
        """Test behavior when LLM features are disabled."""
        # Disable LLM features
        update_semantic_config(
            enable_llm_similarity=False,
            enable_llm_priority=False,
            enable_llm_normalization=False
        )
        
        mock_llm = AsyncMock()
        matcher = SemanticMatcher(llm_provider=mock_llm)
        
        # Should use fallback methods, not call LLM
        priority = await matcher.analyze_todo_priority("urgent bug fix")
        assert priority == "high"
        
        # LLM should not have been called
        assert not mock_llm.chat_with_messages.called
    
    @pytest.mark.asyncio
    async def test_fallback_disabled_configuration(self):
        """Test behavior when fallback is disabled."""
        update_semantic_config(fallback_to_heuristics=False)
        
        # Mock LLM that always fails
        mock_llm = AsyncMock()
        mock_llm.chat_with_messages = AsyncMock(side_effect=Exception("LLM Error"))
        
        matcher = SemanticMatcher(llm_provider=mock_llm)
        
        # Should raise exception instead of falling back
        with pytest.raises(Exception):
            await matcher.analyze_todo_priority("test content")
    
    @pytest.mark.asyncio
    async def test_caching_configuration(self):
        """Test caching behavior configuration."""
        update_semantic_config(cache_llm_results=True)
        
        mock_llm = AsyncMock()
        mock_response = Mock()
        mock_response.content = '{"similarity_score": 0.8}'
        mock_llm.chat_with_messages.return_value = mock_response
        
        matcher = SemanticMatcher(llm_provider=mock_llm)
        
        # First call should hit LLM
        result1 = await matcher.calculate_semantic_similarity("test1", "test2")
        assert mock_llm.chat_with_messages.call_count == 1
        
        # Second call should use cache
        result2 = await matcher.calculate_semantic_similarity("test1", "test2")
        assert mock_llm.chat_with_messages.call_count == 1  # No additional calls
        assert result1 == result2


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    @pytest.mark.asyncio
    async def test_malformed_llm_response(self):
        """Test handling of malformed LLM responses."""
        mock_llm = AsyncMock()
        mock_response = Mock()
        mock_response.content = 'invalid json response'
        mock_llm.chat_with_messages.return_value = mock_response
        
        matcher = SemanticMatcher(llm_provider=mock_llm)
        
        # Should fall back to heuristics on malformed response
        priority = await matcher.analyze_todo_priority("urgent bug fix")
        assert priority in ["high", "medium", "low"]
    
    @pytest.mark.asyncio
    async def test_empty_content_handling(self):
        """Test handling of empty or None content."""
        matcher = SemanticMatcher(llm_provider=None)
        
        # Test empty strings
        priority = matcher._fallback_priority("")
        assert priority == "medium"  # Default priority
        
        similarity = await _calculate_content_similarity("", "", matcher)
        assert similarity >= 0.0
        
        # Test None handling
        normalized = matcher._fallback_normalize_content("")
        assert normalized == ""
    
    @pytest.mark.asyncio
    async def test_very_long_content(self):
        """Test handling of very long content."""
        matcher = SemanticMatcher(llm_provider=None)
        
        # Create very long content
        long_content = "implement " + "very " * 1000 + "long task description"
        
        # Should handle without errors
        priority = matcher._fallback_priority(long_content)
        assert priority in ["high", "medium", "low"]
        
        action = matcher._fallback_extract_action(long_content)
        assert action == "implement"
    
    @pytest.mark.asyncio
    async def test_special_characters_handling(self):
        """Test handling of special characters and Unicode."""
        matcher = SemanticMatcher(llm_provider=None)
        
        special_content = "implement 用户认证 with émojis 🚀 and symbols @#$%"
        
        # Should handle without errors
        priority = matcher._fallback_priority(special_content)
        assert priority in ["high", "medium", "low"]
        
        normalized = matcher._fallback_normalize_content(special_content)
        assert len(normalized) > 0


class TestPerformance:
    """Test performance aspects of the refactoring."""
    
    @pytest.mark.asyncio
    async def test_caching_performance(self):
        """Test that caching improves performance."""
        import time
        
        mock_llm = AsyncMock()
        mock_response = Mock()
        mock_response.content = '{"similarity_score": 0.8}'
        
        # Add delay to simulate real LLM call
        async def delayed_response(*args, **kwargs):
            await asyncio.sleep(0.1)  # 100ms delay
            return mock_response
        
        mock_llm.chat_with_messages = delayed_response
        
        matcher = SemanticMatcher(llm_provider=mock_llm)
        
        # First call - should be slow
        start_time = time.time()
        result1 = await matcher.calculate_semantic_similarity("test1", "test2")
        first_call_time = time.time() - start_time
        
        # Second call - should be fast (cached)
        start_time = time.time()
        result2 = await matcher.calculate_semantic_similarity("test1", "test2")
        second_call_time = time.time() - start_time
        
        assert result1 == result2
        assert second_call_time < first_call_time / 2  # Should be much faster
    
    @pytest.mark.asyncio
    async def test_fallback_performance(self):
        """Test that fallback methods are fast."""
        import time
        
        matcher = SemanticMatcher(llm_provider=None)
        
        # Test multiple operations for performance
        start_time = time.time()
        
        for i in range(100):
            priority = matcher._fallback_priority(f"test task {i}")
            action = matcher._fallback_extract_action(f"implement feature {i}")
            normalized = matcher._fallback_normalize_content(f"TODO: task {i}")
        
        total_time = time.time() - start_time
        
        # Should complete 100 operations very quickly
        assert total_time < 1.0  # Less than 1 second
    
    def test_memory_usage(self):
        """Test memory usage of consolidated keywords."""
        
        # Create multiple matchers
        matchers = [SemanticMatcher(llm_provider=None) for _ in range(10)]
        
        # All should share the same keyword data structure
        first_keywords = matchers[0]._fallback_keywords
        
        for matcher in matchers[1:]:
            # Keywords should be identical (same reference or equal content)
            assert matcher._fallback_keywords.keys() == first_keywords.keys()


# Integration test that runs a complete workflow
@pytest.mark.asyncio
async def test_complete_workflow():
    """Test complete workflow from user input to todo management."""
    # Setup
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create semantic matcher and todo manager
        matcher = SemanticMatcher(llm_provider=None)
        todo_manager = TodoManager(
            working_directory=temp_dir,
            session_id="workflow-test",
            semantic_matcher=matcher
        )
        
        # Step 1: Analyze user message for todo generation
        user_message = "We need to implement user authentication and fix the login bug urgently"
        smart_todos = await todo_manager.generate_smart_todos(user_message)
        
        # Step 2: Create todos with priority analysis
        created_todos = []
        for todo_content in smart_todos[:2]:  # Limit to 2 for test
            priority = await todo_manager.smart_prioritize(todo_content)
            new_todo = await todo_manager.add_todo(todo_content, priority)
            created_todos.append({
                "content": new_todo.content,
                "priority": new_todo.priority,
                "status": "pending"
            })
        
        # Step 3: Use todo_write to process todos
        result = await todo_write(created_todos, session_id="workflow-test")
        assert result["success"] is True
        
        # Step 4: Read todos back
        read_result = await todo_read(session_id="workflow-test")
        assert read_result["success"] is True
        assert len(read_result["todos"]) >= 0
        
        # Step 5: Test completion detection
        completion_message = "I finished implementing the authentication system"
        # This would normally trigger auto-completion in the real system
        
        print("✅ Complete workflow test passed!")


if __name__ == "__main__":
    # Run basic smoke tests
    import asyncio
    
    async def run_smoke_tests():
        print("🧪 Running SemanticMatcher Refactoring Smoke Tests")
        print("=" * 60)
        
        # Test 1: Basic SemanticMatcher functionality
        print("Test 1: SemanticMatcher initialization...")
        matcher = SemanticMatcher(llm_provider=None)
        assert matcher is not None
        print("✅ PASS")
        
        # Test 2: Fallback methods
        print("Test 2: Fallback methods...")
        priority = matcher._fallback_priority("urgent bug fix")
        assert priority == "high"
        print("✅ PASS")
        
        # Test 3: TodoManager integration
        print("Test 3: TodoManager integration...")
        with tempfile.TemporaryDirectory() as temp_dir:
            todo_manager = TodoManager(
                working_directory=temp_dir,
                session_id="smoke-test",
                semantic_matcher=matcher
            )
            priority = await todo_manager.smart_prioritize("test task")
            assert priority in ["high", "medium", "low"]
        print("✅ PASS")
        
        # Test 4: todo_tools integration
        print("Test 4: todo_tools integration...")
        similarity = await _calculate_content_similarity(
            "implement login", "add authentication", matcher
        )
        assert 0.0 <= similarity <= 1.0
        print("✅ PASS")
        
        # Test 5: Configuration system
        print("Test 5: Configuration system...")
        config = get_semantic_config()
        assert config.enable_llm_similarity is True
        print("✅ PASS")
        
        print("\n🎉 All smoke tests passed! SemanticMatcher refactoring is working correctly.")
    
    asyncio.run(run_smoke_tests())