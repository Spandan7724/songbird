#!/usr/bin/env python3
"""
Test script to verify todo tools are properly integrated and available to the LLM.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from songbird.tools.tool_registry import get_tool_schemas


def test_todo_tools_available():
    """Test that todo tools are in the available tools list."""
    print("=" * 60)
    print("TEST: Todo Tools Available to LLM")
    print("=" * 60)
    
    tools = get_tool_schemas()
    todo_tools = []
    
    for tool in tools:
        function = tool.get('function', {})
        name = function.get('name', '')
        if 'todo' in name:
            todo_tools.append(name)
            print(f"✅ Found tool: {name}")
            print(f"   Description: {function.get('description', 'No description')}")
            print(f"   Parameters: {list(function.get('parameters', {}).get('properties', {}).keys())}")
            print()
    
    print(f"Total todo tools found: {len(todo_tools)}")
    
    expected_tools = ['todo_read', 'todo_write']
    missing_tools = [tool for tool in expected_tools if tool not in todo_tools]
    
    if missing_tools:
        print(f"❌ Missing tools: {missing_tools}")
        return False
    else:
        print("✅ All expected todo tools are available!")
        return True


def test_tool_schemas_format():
    """Test that todo tool schemas are properly formatted for LLM."""
    print("=" * 60)
    print("TEST: Todo Tool Schema Format")
    print("=" * 60)
    
    tools = get_tool_schemas()
    
    for tool in tools:
        function = tool.get('function', {})
        name = function.get('name', '')
        
        if 'todo' in name:
            print(f"Checking {name}:")
            
            # Check required fields
            required_fields = ['name', 'description', 'parameters']
            for field in required_fields:
                if field in function:
                    print(f"  ✅ Has {field}")
                else:
                    print(f"  ❌ Missing {field}")
            
            # Check parameters structure
            params = function.get('parameters', {})
            if 'type' in params and params['type'] == 'object':
                print("  ✅ Parameters structure is valid")
            else:
                print("  ❌ Invalid parameters structure")
                return False
            
            print()
    
    return True


def test_system_prompt_includes_todos():
    """Test that the system prompt mentions todo tools."""
    print("=" * 60)
    print("TEST: System Prompt Includes Todo Tools")
    print("=" * 60)
    
    try:
        from songbird.prompts import get_core_system_prompt
        prompt = get_core_system_prompt()
        
        if 'todo_read' in prompt and 'todo_write' in prompt:
            print("✅ System prompt includes todo tools")
            
            # Show the relevant sections
            lines = prompt.split('\n')
            for i, line in enumerate(lines):
                if 'todo_read' in line or 'todo_write' in line:
                    print(f"  Line {i+1}: {line.strip()}")
            return True
        else:
            print("❌ System prompt missing todo tools")
            print(f"Debug: prompt length = {len(prompt)}")
            print(f"Debug: contains 'todo_read' = {'todo_read' in prompt}")
            print(f"Debug: contains 'todo_write' = {'todo_write' in prompt}")
            return False
            
    except Exception as e:
        print(f"❌ Error reading system prompt: {e}")
        return False
    
    return True


def main():
    """Run all integration tests."""
    print("TODO TOOLS INTEGRATION TEST")
    print("=" * 60)
    print("Testing if todo tools are properly integrated for LLM usage")
    print()
    
    tests = [
        test_todo_tools_available,
        test_tool_schemas_format,
        test_system_prompt_includes_todos
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with error: {e}")
            failed += 1
    
    print("=" * 60)
    print("INTEGRATION TEST SUMMARY")
    print("=" * 60)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0:
        print("🎉 All integration tests passed!")
        print("Todo tools should be available to the LLM.")
    else:
        print("⚠️ Some integration tests failed.")
        print("Todo tools may not be properly available to the LLM.")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)