#!/usr/bin/env python3
"""
Test script for todo management tools.
Tests todo_read and todo_write functionality.
"""

import asyncio
import sys
import time
import uuid
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from songbird.tools.todo_tools import todo_read, todo_write


async def test_todo_write_basic():
    """Test basic todo writing functionality."""
    print("=" * 60)
    print("TEST: Todo Write - Basic Functionality")
    print("=" * 60)
    
    # Create a test session ID
    test_session_id = f"test_session_{uuid.uuid4().hex[:8]}"
    
    # Create some test todos
    test_todos = [
        {
            "id": "todo_1",
            "content": "Implement user authentication system",
            "status": "pending",
            "priority": "high"
        },
        {
            "id": "todo_2", 
            "content": "Write unit tests for API endpoints",
            "status": "in_progress",
            "priority": "medium"
        },
        {
            "id": "todo_3",
            "content": "Update documentation for deployment",
            "status": "completed",
            "priority": "low"
        }
    ]
    
    start_time = time.time()
    result = await todo_write(test_todos, session_id=test_session_id)
    end_time = time.time()
    
    print(f"Session ID: {test_session_id}")
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    
    if result['success']:
        todos = result.get('todos', [])
        print(f"Todos written: {len(todos)}")
        print(f"File path: {result.get('file_path', 'unknown')}")
        
        # Show todo summary
        status_counts = {}
        priority_counts = {}
        for todo in todos:
            status = todo.get('status', 'unknown')
            priority = todo.get('priority', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        print(f"Status breakdown: {status_counts}")
        print(f"Priority breakdown: {priority_counts}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    print()
    return test_session_id


async def test_todo_read_basic(session_id):
    """Test basic todo reading functionality."""
    print("=" * 60)
    print("TEST: Todo Read - Basic Functionality")
    print("=" * 60)
    
    start_time = time.time()
    result = await todo_read(session_id=session_id)
    end_time = time.time()
    
    print(f"Session ID: {session_id}")
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    
    if result['success']:
        todos = result.get('todos', [])
        print(f"Todos found: {len(todos)}")
        
        # Show todos
        for i, todo in enumerate(todos):
            print(f"  {i+1}. [{todo.get('status', 'unknown')}] {todo.get('content', 'No content')}")
            print(f"     Priority: {todo.get('priority', 'unknown')}, ID: {todo.get('id', 'no-id')}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    print()


async def test_todo_read_with_filters(session_id):
    """Test todo reading with status filters."""
    print("=" * 60)
    print("TEST: Todo Read - Status Filters")
    print("=" * 60)
    
    statuses = ["pending", "in_progress", "completed"]
    
    for status in statuses:
        print(f"\nFilter by status: {status}")
        start_time = time.time()
        result = await todo_read(session_id=session_id, status=status)
        end_time = time.time()
        
        print(f"Execution time: {end_time - start_time:.2f} seconds")
        print(f"Success: {result['success']}")
        
        if result['success']:
            todos = result.get('todos', [])
            print(f"Todos with status '{status}': {len(todos)}")
            
            for todo in todos:
                print(f"  - {todo.get('content', 'No content')}")
    
    print()


async def test_todo_read_with_completed(session_id):
    """Test todo reading showing completed items."""
    print("=" * 60)
    print("TEST: Todo Read - Show Completed")
    print("=" * 60)
    
    print("Without completed todos:")
    result1 = await todo_read(session_id=session_id, show_completed=False)
    if result1['success']:
        todos1 = result1.get('todos', [])
        print(f"  Found: {len(todos1)} todos")
    
    print("\nWith completed todos:")
    result2 = await todo_read(session_id=session_id, show_completed=True)
    if result2['success']:
        todos2 = result2.get('todos', [])
        print(f"  Found: {len(todos2)} todos")
        
        # Show breakdown
        status_counts = {}
        for todo in todos2:
            status = todo.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        print(f"  Status breakdown: {status_counts}")
    
    print()


async def test_todo_update(session_id):
    """Test updating existing todos."""
    print("=" * 60)
    print("TEST: Todo Write - Update Existing")
    print("=" * 60)
    
    # Update the status of some todos
    updated_todos = [
        {
            "id": "todo_1",
            "content": "Implement user authentication system",
            "status": "completed",  # Changed from pending
            "priority": "high"
        },
        {
            "id": "todo_2",
            "content": "Write unit tests for API endpoints", 
            "status": "completed",  # Changed from in_progress
            "priority": "medium"
        },
        {
            "id": "todo_4",  # New todo
            "content": "Deploy to production server",
            "status": "pending",
            "priority": "high"
        }
    ]
    
    start_time = time.time()
    result = await todo_write(updated_todos, session_id=session_id)
    end_time = time.time()
    
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    
    if result['success']:
        todos = result.get('todos', [])
        print(f"Total todos after update: {len(todos)}")
        
        # Read back to verify
        read_result = await todo_read(session_id=session_id, show_completed=True)
        if read_result['success']:
            all_todos = read_result.get('todos', [])
            print(f"Verification - todos in file: {len(all_todos)}")
            
            status_counts = {}
            for todo in all_todos:
                status = todo.get('status', 'unknown')
                status_counts[status] = status_counts.get(status, 0) + 1
            print(f"Final status breakdown: {status_counts}")
    
    print()


async def test_todo_nonexistent_session():
    """Test reading todos from non-existent session."""
    print("=" * 60)
    print("TEST: Todo Read - Non-existent Session")
    print("=" * 60)
    
    fake_session_id = f"nonexistent_session_{uuid.uuid4().hex[:8]}"
    
    start_time = time.time()
    result = await todo_read(session_id=fake_session_id)
    end_time = time.time()
    
    print(f"Session ID: {fake_session_id}")
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    
    if result['success']:
        todos = result.get('todos', [])
        print(f"Todos found: {len(todos)} (should be 0)")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    print()


async def test_todo_invalid_data():
    """Test writing invalid todo data."""
    print("=" * 60)
    print("TEST: Todo Write - Invalid Data")
    print("=" * 60)
    
    test_session_id = f"test_invalid_{uuid.uuid4().hex[:8]}"
    
    # Invalid todos (missing required fields)
    invalid_todos = [
        {
            "id": "invalid_1",
            # Missing content, status, priority
        },
        {
            "content": "Todo without ID or status",
            "priority": "medium"
        }
    ]
    
    start_time = time.time()
    result = await todo_write(invalid_todos, session_id=test_session_id)
    end_time = time.time()
    
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    
    if result['success']:
        print("Unexpected success with invalid data!")
        todos = result.get('todos', [])
        print(f"Todos written: {len(todos)}")
    else:
        print(f"Error (expected): {result.get('error', 'Unknown error')}")
    
    print()


async def test_todo_empty_list():
    """Test writing empty todo list."""
    print("=" * 60)
    print("TEST: Todo Write - Empty List")
    print("=" * 60)
    
    test_session_id = f"test_empty_{uuid.uuid4().hex[:8]}"
    empty_todos = []
    
    start_time = time.time()
    result = await todo_write(empty_todos, session_id=test_session_id)
    end_time = time.time()
    
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    
    if result['success']:
        todos = result.get('todos', [])
        print(f"Todos written: {len(todos)}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    print()


async def cleanup_test_sessions(session_ids):
    """Clean up test session files."""
    print("=" * 60)
    print("CLEANUP: Removing Test Session Files")
    print("=" * 60)
    
    import os
    
    for session_id in session_ids:
        try:
            # Try to find and remove the test session file
            # This is implementation-dependent - adjust based on actual file storage
            test_file_patterns = [
                Path.home() / ".songbird" / "projects" / "songbird" / f"todos-{session_id}.json",
                Path("/tmp") / f"todos-{session_id}.json",
                Path(".") / f"todos-{session_id}.json"
            ]
            
            for file_path in test_file_patterns:
                if file_path.exists():
                    os.unlink(file_path)
                    print(f"Removed: {file_path}")
                    break
            else:
                print(f"Test file for session {session_id} not found (may not have been created)")
                
        except Exception as e:
            print(f"Failed to remove test session {session_id}: {e}")
    
    print()


async def main():
    """Run all todo management tests."""
    print("TODO MANAGEMENT TEST SUITE")
    print("=" * 60)
    print(f"Running tests at: {Path.cwd()}")
    print(f"Test time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    session_ids = []
    
    try:
        # Basic functionality tests
        session_id = await test_todo_write_basic()
        session_ids.append(session_id)
        
        await test_todo_read_basic(session_id)
        await test_todo_read_with_filters(session_id)
        await test_todo_read_with_completed(session_id)
        await test_todo_update(session_id)
        
        # Error handling tests
        await test_todo_nonexistent_session()
        await test_todo_invalid_data()
        await test_todo_empty_list()
        
    finally:
        # Clean up test files
        await cleanup_test_sessions(session_ids)
    
    print("=" * 60)
    print("ALL TODO MANAGEMENT TESTS COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())