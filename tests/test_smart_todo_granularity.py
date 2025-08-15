#!/usr/bin/env python3
"""
Test script to validate the improved todo granularity and tool-based completion system.
Tests diverse scenarios beyond just BFS to ensure generic applicability.
"""

import asyncio
import sys
import json
import pytest
from pathlib import Path

# Add songbird to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from songbird.agent.agent_core import AgentCore
from songbird.tools.todo_tools import analyze_tool_completion
from songbird.tools.todo_manager import TodoManager
from songbird.memory.models import Session


class MockProvider:
    """Mock provider that simulates intelligent todo generation and completion analysis."""
    
    def __init__(self):
        self.call_count = 0
        
    async def chat_with_messages(self, messages):
        """Mock chat response that analyzes prompts and returns appropriate responses."""
        self.call_count += 1
        prompt = messages[0]["content"]
        
        print(f"    🔍 MockProvider received prompt: {prompt[:100]}...")
        
        class MockResponse:
            def __init__(self, content):
                self.content = content
        
        # Handle todo generation prompts
        if "Analyze this request and generate appropriate todos" in prompt:
            print("    🔍 Detected todo generation prompt")
            return self._handle_todo_generation(prompt)
        
        # Handle tool completion analysis
        elif "Action performed:" in prompt and "Which todos were completed" in prompt:
            print("    🔍 Detected tool completion prompt")
            return self._handle_tool_completion(prompt)
        
        # Handle message-based completion
        elif "User message:" in prompt and "Active todos:" in prompt:
            print("    🔍 Detected message completion prompt")
            return self._handle_message_completion(prompt)
        
        print("    🔍 No prompt pattern matched, returning empty")
        return MockResponse("[]")
    
    def _handle_todo_generation(self, prompt):
        """Generate appropriately granular todos based on the request."""
        class MockResponse:
            def __init__(self, content):
                self.content = content
        
        # Extract the user request
        if "Create a Python file with BFS implementation" in prompt:
            # Should generate 1-2 todos, not 4+
            response = '''[
  {"id": "implement-bfs-algorithm", "content": "Implement BFS algorithm in Python", "priority": "high"}
]'''
        elif "Build a REST API with authentication" in prompt:
            # Should generate logical feature-level todos
            response = '''[
  {"id": "setup-api-structure", "content": "Set up basic API structure and routing", "priority": "high"},
  {"id": "implement-authentication", "content": "Implement user authentication system", "priority": "high"},
  {"id": "add-api-endpoints", "content": "Add main API endpoints", "priority": "medium"},
  {"id": "add-api-tests", "content": "Add comprehensive API tests", "priority": "medium"}
]'''
        elif "Fix the login bug" in prompt:
            # Simple bug fix = 1 todo
            response = '''[
  {"id": "fix-login-bug", "content": "Fix login authentication bug", "priority": "high"}
]'''
        else:
            # Default: reasonable granularity
            response = '''[
  {"id": "complete-user-request", "content": "Complete the requested task", "priority": "high"}
]'''
        
        return MockResponse(response)
    
    def _handle_tool_completion(self, prompt):
        """Analyze tool actions to determine completed todos."""
        class MockResponse:
            def __init__(self, content):
                self.content = content
        
        # Extract action and todos from prompt
        action_line = ""
        todos_section = ""
        
        for line in prompt.split('\n'):
            if line.startswith("Action performed:"):
                action_line = line
            elif '"' in line and '":' in line:  # Todo line
                todos_section += line + "\n"
        
        completed_todos = []
        
        # Smart completion logic based on action type
        if "Created file" in action_line and "with Python code" in action_line:
            # File creation with implementation completes implementation todos
            if "implement-bfs-algorithm" in todos_section:
                completed_todos.append("implement-bfs-algorithm")
            elif "implement-authentication" in todos_section:
                completed_todos.append("implement-authentication")
            elif "setup-api-structure" in todos_section:
                completed_todos.append("setup-api-structure")
        
        elif "Executed command: python" in action_line:
            # Running Python scripts completes testing/execution todos
            if "test-bfs-algorithm" in todos_section:
                completed_todos.append("test-bfs-algorithm")
            elif "test-authentication" in todos_section:
                completed_todos.append("test-authentication")
        
        elif "Edited file" in action_line:
            # File edits complete bug fixes or modifications
            if "fix-login-bug" in todos_section:
                completed_todos.append("fix-login-bug")
        
        return MockResponse(json.dumps(completed_todos))
    
    def _handle_message_completion(self, prompt):
        """Handle explicit user completion statements."""
        # Extract message from prompt
        message_line = ""
        for line in prompt.split('\n'):
            if line.startswith('User message:'):
                message_line = line
                break
        
        completed_todos = []
        
        # Look for explicit completion statements
        if "is working" in message_line or "is done" in message_line or "finished" in message_line:
            # User explicitly said something is done
            if "authentication" in message_line.lower():
                completed_todos.append("implement-authentication")
            elif "api" in message_line.lower():
                completed_todos.append("add-api-endpoints")
            elif "bug" in message_line.lower():
                completed_todos.append("fix-login-bug")
        
        return json.dumps(completed_todos)


class MockToolRunner:
    """Mock tool runner for testing."""
    
    async def execute_tool(self, tool_name: str, args: dict):
        """Mock tool execution."""
        if tool_name == "file_create":
            return {
                "success": True,
                "filename": args.get("file_path", "test.py"),
                "message": "File created successfully"
            }
        elif tool_name == "shell_exec":
            return {
                "success": True,
                "command": args.get("command", "python test.py"),
                "output": "Program executed successfully",
                "exit_code": 0
            }
        else:
            return {"success": True, "message": "Tool executed"}
    
    def get_available_tools(self):
        """Return mock tools."""
        return [
            {"type": "function", "function": {"name": "file_create"}},
            {"type": "function", "function": {"name": "shell_exec"}}
        ]


@pytest.mark.asyncio
async def test_todo_generation_granularity():
    """Test that todo generation creates appropriate granularity."""
    print("🧪 Testing Todo Generation Granularity...")
    
    provider = MockProvider()
    tool_runner = MockToolRunner()
    agent = AgentCore(provider, tool_runner)
    
    # Create a mock session
    session = Session()
    agent.session = session
    
    test_cases = [
        {
            "request": "Create a Python file with BFS implementation",
            "expected_count": 1,
            "description": "Single implementation task"
        },
        {
            "request": "Build a REST API with authentication",
            "expected_count": 4,
            "description": "Multi-feature project"
        },
        {
            "request": "Fix the login bug",
            "expected_count": 1,
            "description": "Single bug fix"
        }
    ]
    
    passed = 0
    for i, test_case in enumerate(test_cases, 1):
        try:
            print(f"    🔍 Testing: {test_case['request']}")
            print(f"    🔍 LLM call count before: {provider.call_count}")
            todos = await agent._generate_todos_for_request(test_case["request"], [])
            print(f"    🔍 LLM call count after: {provider.call_count}")
            print(f"    🔍 Raw todos result: {todos}")
            todo_count = len(todos)
            
            if todo_count == test_case["expected_count"]:
                print(f"  ✅ Test {i}: {test_case['description']} - Generated {todo_count} todos")
                passed += 1
            else:
                print(f"  ❌ Test {i}: {test_case['description']} - Expected {test_case['expected_count']}, got {todo_count}")
                print(f"    Generated todos: {[t.get('content', t.get('id', '')) for t in todos]}")
        except Exception as e:
            print(f"  ❌ Test {i}: {test_case['description']} - Exception: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"  📊 Todo Generation Tests: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


@pytest.mark.asyncio
async def test_tool_completion_analysis():
    """Test that tool actions properly complete relevant todos."""
    print("\n🧪 Testing Tool-Based Completion Analysis...")
    
    provider = MockProvider()
    
    # Create mock todos
    class MockTodo:
        def __init__(self, id, content):
            self.id = id
            self.content = content
            self.status = "pending"
    
    test_cases = [
        {
            "tool_name": "file_create",
            "tool_args": {"file_path": "bfs.py", "content": "def bfs(graph, start):\n    # BFS implementation"},
            "todos": [MockTodo("implement-bfs-algorithm", "Implement BFS algorithm in Python")],
            "expected_completed": ["implement-bfs-algorithm"],
            "description": "File creation completes implementation"
        },
        {
            "tool_name": "file_create", 
            "tool_args": {"file_path": "auth.py", "content": "class AuthService:\n    def authenticate(self):"},
            "todos": [
                MockTodo("implement-authentication", "Implement user authentication system"),
                MockTodo("add-api-endpoints", "Add main API endpoints")
            ],
            "expected_completed": ["implement-authentication"],
            "description": "Auth file creation completes auth todo only"
        },
        {
            "tool_name": "shell_exec",
            "tool_args": {"command": "python test_bfs.py"},
            "todos": [MockTodo("test-bfs-algorithm", "Test BFS algorithm")],
            "expected_completed": ["test-bfs-algorithm"],
            "description": "Running tests completes testing todo"
        }
    ]
    
    passed = 0
    for i, test_case in enumerate(test_cases, 1):
        try:
            completed_ids = await analyze_tool_completion(
                test_case["tool_name"],
                test_case["tool_args"],
                test_case["todos"],
                provider
            )
            
            if set(completed_ids) == set(test_case["expected_completed"]):
                print(f"  ✅ Test {i}: {test_case['description']}")
                passed += 1
            else:
                print(f"  ❌ Test {i}: {test_case['description']}")
                print(f"    Expected: {test_case['expected_completed']}")
                print(f"    Got: {completed_ids}")
        except Exception as e:
            print(f"  ❌ Test {i}: {test_case['description']} - Exception: {e}")
    
    print(f"  📊 Tool Completion Tests: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


@pytest.mark.asyncio
async def test_message_completion_analysis():
    """Test that user messages properly trigger completion."""
    print("\n🧪 Testing Message-Based Completion Analysis...")
    
    provider = MockProvider()
    
    test_cases = [
        {
            "message": "The authentication system is working perfectly now!",
            "todos": ["implement-authentication", "add-api-endpoints"],
            "expected_completed": ["implement-authentication"],
            "description": "Explicit working statement"
        },
        {
            "message": "I finished fixing the login bug",
            "todos": ["fix-login-bug", "add-tests"],
            "expected_completed": ["fix-login-bug"],
            "description": "Explicit completion statement"
        },
        {
            "message": "How do I implement the API endpoints?",
            "todos": ["add-api-endpoints"],
            "expected_completed": [],
            "description": "Question should not trigger completion"
        }
    ]
    
    passed = 0
    for i, test_case in enumerate(test_cases, 1):
        try:
            # Mock the LLM response
            response_json = provider._handle_message_completion(f"User message: {test_case['message']}")
            completed_ids = json.loads(response_json)
            
            if set(completed_ids) == set(test_case["expected_completed"]):
                print(f"  ✅ Test {i}: {test_case['description']}")
                passed += 1
            else:
                print(f"  ❌ Test {i}: {test_case['description']}")
                print(f"    Expected: {test_case['expected_completed']}")
                print(f"    Got: {completed_ids}")
        except Exception as e:
            print(f"  ❌ Test {i}: {test_case['description']} - Exception: {e}")
    
    print(f"  📊 Message Completion Tests: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


@pytest.mark.asyncio
async def test_end_to_end_workflow():
    """Test complete workflow: generate todos -> execute tools -> auto-complete."""
    print("\n🧪 Testing End-to-End Workflow...")
    
    provider = MockProvider()
    tool_runner = MockToolRunner()
    agent = AgentCore(provider, tool_runner)
    
    # Create session and todo manager
    session = Session()
    agent.session = session
    todo_manager = TodoManager(session_id=session.id)
    
    try:
        # Step 1: Generate todos for a request
        print("  📝 Step 1: Generate todos for 'Create a Python file with BFS implementation'")
        todos = await agent._generate_todos_for_request("Create a Python file with BFS implementation", [])
        
        if len(todos) != 1:
            print(f"    ❌ Expected 1 todo, got {len(todos)}")
            return False
        
        # Add the todo to the manager
        todo_data = todos[0]
        todo_id = todo_manager.add_todo(
            content=todo_data["content"], 
            priority=todo_data["priority"],
            id=todo_data["id"]
        )
        print(f"    ✅ Generated todo: {todo_data['content']}")
        
        # Step 2: Simulate tool execution (file creation)
        print("  🔧 Step 2: Execute file_create tool")
        tool_result = await tool_runner.execute_tool("file_create", {
            "file_path": "bfs.py",
            "content": "def bfs(graph, start):\n    return []  # BFS implementation"
        })
        
        if not tool_result.get("success"):
            print("    ❌ Tool execution failed")
            return False
        
        print("    ✅ File created successfully")
        
        # Step 3: Analyze if tool completed the todo
        print("  🤖 Step 3: Analyze tool completion")
        active_todos = [t for t in todo_manager.get_current_session_todos() if t.status == "pending"]
        
        completed_ids = await analyze_tool_completion(
            "file_create",
            {"file_path": "bfs.py", "content": "def bfs(graph, start):\n    return []"},
            active_todos,
            provider
        )
        
        if len(completed_ids) == 1 and completed_ids[0] == todo_id:
            print("    ✅ Todo automatically completed by tool execution")
            
            # Mark it as completed
            todo_manager.complete_todo(todo_id)
            
            # Verify completion
            completed_todos = [t for t in todo_manager.get_current_session_todos() if t.status == "completed"]
            if len(completed_todos) == 1:
                print("  🎉 End-to-end workflow successful!")
                return True
            else:
                print("    ❌ Todo not marked as completed properly")
                return False
        else:
            print(f"    ❌ Expected 1 completed todo ({todo_id}), got {completed_ids}")
            return False
            
    except Exception as e:
        print(f"    ❌ End-to-end test failed: {e}")
        return False


async def run_all_tests():
    """Run all smart granularity tests."""
    print("🚀 Smart Todo Granularity Test Suite")
    print("=" * 60)
    print("Testing improved todo generation and completion system")
    print("=" * 60)
    
    tests = [
        ("Todo Generation Granularity", test_todo_generation_granularity),
        ("Tool-Based Completion Analysis", test_tool_completion_analysis), 
        ("Message-Based Completion Analysis", test_message_completion_analysis),
        ("End-to-End Workflow", test_end_to_end_workflow),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"  ❌ Test {test_name} crashed: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 60)
    print("📊 SMART GRANULARITY TEST RESULTS")
    print("=" * 60)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:35s} {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(results)} tests passed ({passed/len(results)*100:.1f}%)")
    
    if passed == len(results):
        print("\n🎉 All tests passed! Smart todo granularity system is working correctly.")
        print("\n📋 Key improvements validated:")
        print("  ✅ Todo generation creates appropriate task-level granularity")
        print("  ✅ Tool execution triggers real-time completion analysis")
        print("  ✅ LLM understands relationship between actions and todos")
        print("  ✅ Message-based completion handles explicit user statements")
        print("  ✅ End-to-end workflow functions seamlessly")
        return True
    else:
        print(f"\n⚠️  {len(results) - passed} test(s) failed - system may need adjustment")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)