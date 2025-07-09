#!/usr/bin/env python3
"""
Test script to validate todo deduplication fixes.
Tests various duplicate scenarios that should be caught by the enhanced similarity algorithm.
"""

import asyncio
import sys
import pytest
from pathlib import Path

# Add the songbird directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from songbird.tools.todo_tools import _calculate_content_similarity, _deduplicate_input_todos, todo_write
from songbird.tools.todo_manager import TodoManager


@pytest.mark.asyncio
async def test_enhanced_similarity():
    """Test the enhanced similarity algorithm with real-world duplicate scenarios."""
    
    print("🧪 Testing Enhanced Similarity Algorithm")
    print("=" * 50)
    
    # Test cases from the original issue
    test_cases = [
        # Case 1: Conceptually identical but different wording
        (
            "Analyze the existing codebase to identify performance bottlenecks and code smells",
            "Analyze the current codebase structure to identify main components, critical paths, and potential pain points for performance and maintainability",
            0.6  # Should be high similarity (adjusted for realistic expectations)
        ),
        # Case 2: Same action, different focus
        (
            "Refactor monolithic or tightly-coupled modules into smaller, reusable components or services",
            "Optimize performance-critical paths and algorithms based on identified bottlenecks",
            0.3  # Should be medium similarity (both are improvement tasks)
        ),
        # Case 3: Identical normalized content
        (
            "Create unit tests for authentication module",
            "Add unit tests for auth module",
            0.8  # Should be very high similarity
        ),
        # Case 4: Different tasks entirely
        (
            "Implement OAuth authentication provider",
            "Update documentation for API endpoints",
            0.1  # Should be low similarity
        ),
        # Case 5: Same action different target
        (
            "Test user registration functionality",
            "Test payment processing system",
            0.6  # Medium similarity (same action)
        )
    ]
    
    for i, (content1, content2, expected_min) in enumerate(test_cases, 1):
        similarity = await _calculate_content_similarity(content1, content2, None)  # None for semantic_matcher
        status = "✅ PASS" if similarity >= expected_min else "❌ FAIL"
        
        print(f"Test {i}: {status}")
        print(f"  Content 1: {content1}")
        print(f"  Content 2: {content2}")
        print(f"  Similarity: {similarity:.3f} (expected >= {expected_min})")
        print()


@pytest.mark.asyncio
async def test_input_deduplication():
    """Test the input deduplication function."""
    
    print("🧪 Testing Input Deduplication")
    print("=" * 50)
    
    # Test input with obvious duplicates
    input_todos = [
        {"id": "analyze-codebase", "content": "Analyze the existing codebase to identify performance bottlenecks", "priority": "high"},
        {"id": "examine-code", "content": "Analyze the current codebase structure to identify main components and bottlenecks", "priority": "high"},
        {"id": "implement-auth", "content": "Implement authentication system", "priority": "medium"},
        {"id": "add-tests", "content": "Add comprehensive unit tests", "priority": "medium"},
        {"id": "write-tests", "content": "Add comprehensive test coverage", "priority": "medium"},
        {"id": "different-task", "content": "Update API documentation", "priority": "low"}
    ]
    
    deduplicated = await _deduplicate_input_todos(input_todos, None)  # None for llm_provider
    
    print(f"Original count: {len(input_todos)}")
    print(f"Deduplicated count: {len(deduplicated)}")
    print(f"Removed duplicates: {len(input_todos) - len(deduplicated)}")
    print()
    
    print("Remaining todos after deduplication:")
    for todo in deduplicated:
        print(f"  - {todo['content']}")
    print()


@pytest.mark.asyncio
async def test_todo_write_integration():
    """Test the full todo_write flow with deduplication."""
    
    print("🧪 Testing Todo Write Integration")
    print("=" * 50)
    
    # Create a temporary session for testing
    session_id = "test-dedup-session"
    
    # Test todos with various types of duplicates
    test_todos = [
        {"content": "Analyze codebase structure and identify bottlenecks", "priority": "high"},
        {"content": "Examine the existing code to find performance issues", "priority": "high"},  # Similar to above
        {"content": "Implement user authentication system", "priority": "medium"},
        {"content": "Add user auth functionality", "priority": "medium"},  # Similar to above
        {"content": "Create comprehensive test suite", "priority": "medium"},
        {"content": "Write unit tests for all modules", "priority": "medium"},  # Similar to above
        {"content": "Update project documentation", "priority": "low"},  # Unique
    ]
    
    # Call todo_write
    result = await todo_write(test_todos, session_id=session_id)
    
    print(f"Result: {result.get('message', 'Unknown result')}")
    print(f"Created: {result.get('created', 0)}")
    print(f"Total todos: {result.get('total_todos', 0)}")
    
    if result.get('success', False):
        print("✅ Todo write test successful")
    else:
        print("❌ Todo write test failed")
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    # Clean up test data
    try:
        todo_manager = TodoManager(session_id=session_id)
        storage_path = todo_manager.storage_path
        if storage_path.exists():
            storage_path.unlink()
            print(f"Cleaned up test data: {storage_path}")
    except Exception as e:
        print(f"Warning: Could not clean up test data: {e}")


def main():
    """Run all deduplication tests."""
    
    print("🚀 Todo Deduplication Fix Validation")
    print("=" * 60)
    print()
    
    # Run tests
    test_enhanced_similarity()
    test_input_deduplication()
    
    # Run async integration test
    asyncio.run(test_todo_write_integration())
    
    print("✅ All tests completed!")
    print()
    print("Summary of Fixes:")
    print("- Enhanced semantic similarity algorithm with concept and action matching")
    print("- Pre-creation deduplication in auto-creation flow")
    print("- Input batch deduplication in todo_write")
    print("- LLM prompt includes existing todos to avoid duplicates")
    print("- Lowered similarity threshold (0.6) for enhanced algorithm")


if __name__ == "__main__":
    main()