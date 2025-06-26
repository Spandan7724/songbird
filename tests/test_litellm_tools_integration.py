# tests/test_litellm_tools_integration.py
"""
Comprehensive integration tests for all 11 Songbird tools with LiteLLM adapter.

Tests tool calling functionality, parameter handling, error cases, and
tool execution workflow to ensure complete compatibility between
LiteLLM adapter and the Songbird tool system.
"""
import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from songbird.llm.litellm_adapter import LiteLLMAdapter
from songbird.tools.registry import get_tool_schemas, get_tool_function, TOOL_SCHEMAS
from songbird.orchestrator import SongbirdOrchestrator


@pytest.mark.slow
class TestLiteLLMToolsIntegration:
    """Test all 11 tools with LiteLLM adapter integration."""
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_file_search_tool_integration(self, mock_acompletion, sample_project_files):
        """Test file_search tool with LiteLLM adapter."""
        # Mock LiteLLM response with file_search tool call
        mock_tool_call = Mock()
        mock_tool_call.id = "call_file_search"
        mock_tool_call.function = Mock()
        mock_tool_call.function.name = "file_search"
        mock_tool_call.function.arguments = '{"pattern": "*.py", "directory": ".", "file_type": "py"}'
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "I'll search for Python files."
        mock_response.choices[0].message.tool_calls = [mock_tool_call]
        mock_acompletion.return_value = mock_response
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        tools = [TOOL_SCHEMAS["file_search"]]
        messages = [{"role": "user", "content": "Find all Python files"}]
        
        # Test tool call
        response = await adapter.chat_with_messages(messages, tools)
        
        assert response.content == "I'll search for Python files."
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]["function"]["name"] == "file_search"
        
        # Verify tool was passed correctly to LiteLLM
        call_args = mock_acompletion.call_args[1]
        assert "tools" in call_args
        assert call_args["tools"][0]["function"]["name"] == "file_search"
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_file_operations_tools_integration(self, mock_acompletion, isolated_workspace):
        """Test file_read, file_create, file_edit tools with LiteLLM adapter."""
        # Mock LiteLLM response with file operations
        mock_response = Mock(
            choices=[Mock(
                message=Mock(
                    content="I'll create, read, and edit files for you.",
                    tool_calls=[
                        Mock(
                            id="call_file_create",
                            function=Mock(
                                name="file_create",
                                arguments='{"file_path": "test.py", "content": "print(\\"hello\\")"}'
                            )
                        ),
                        Mock(
                            id="call_file_read",
                            function=Mock(
                                name="file_read",
                                arguments='{"file_path": "test.py"}'
                            )
                        ),
                        Mock(
                            id="call_file_edit",
                            function=Mock(
                                name="file_edit",
                                arguments='{"file_path": "test.py", "new_content": "print(\\"hello world\\")"}'
                            )
                        )
                    ]
                )
            )]
        )
        mock_acompletion.return_value = mock_response
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        tools = [
            TOOL_SCHEMAS["file_create"],
            TOOL_SCHEMAS["file_read"],
            TOOL_SCHEMAS["file_edit"]
        ]
        messages = [{"role": "user", "content": "Create, read, and edit a test file"}]
        
        # Test multiple tool calls
        response = await adapter.chat_with_messages(messages, tools)
        
        assert response.content == "I'll create, read, and edit files for you."
        assert len(response.tool_calls) == 3
        
        tool_names = [tc["function"]["name"] for tc in response.tool_calls]
        assert "file_create" in tool_names
        assert "file_read" in tool_names
        assert "file_edit" in tool_names
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_shell_exec_tool_integration(self, mock_acompletion):
        """Test shell_exec tool with LiteLLM adapter."""
        # Mock LiteLLM response with shell command
        mock_response = Mock(
            choices=[Mock(
                message=Mock(
                    content="I'll list the current directory contents.",
                    tool_calls=[Mock(
                        id="call_shell_exec",
                        function=Mock(
                            name="shell_exec",
                            arguments='{"command": "ls -la", "timeout": 10}'
                        )
                    )]
                )
            )]
        )
        mock_acompletion.return_value = mock_response
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        tools = [TOOL_SCHEMAS["shell_exec"]]
        messages = [{"role": "user", "content": "List files in current directory"}]
        
        # Test shell command tool call
        response = await adapter.chat_with_messages(messages, tools)
        
        assert response.content == "I'll list the current directory contents."
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]["function"]["name"] == "shell_exec"
        
        # Verify command parameters
        arguments = response.tool_calls[0]["function"]["arguments"]
        assert '"command": "ls -la"' in arguments
        assert '"timeout": 10' in arguments
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_todo_tools_integration(self, mock_acompletion):
        """Test todo_read and todo_write tools with LiteLLM adapter."""
        # Mock LiteLLM response with todo operations
        mock_response = Mock(
            choices=[Mock(
                message=Mock(
                    content="I'll manage your todo list.",
                    tool_calls=[
                        Mock(
                            id="call_todo_write",
                            function=Mock(
                                name="todo_write",
                                arguments='{"todos": [{"content": "Test task", "status": "pending", "priority": "high"}]}'
                            )
                        ),
                        Mock(
                            id="call_todo_read",
                            function=Mock(
                                name="todo_read",
                                arguments='{"show_completed": false}'
                            )
                        )
                    ]
                )
            )]
        )
        mock_acompletion.return_value = mock_response
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        tools = [TOOL_SCHEMAS["todo_read"], TOOL_SCHEMAS["todo_write"]]
        messages = [{"role": "user", "content": "Add a test task and show my todos"}]
        
        # Test todo management
        response = await adapter.chat_with_messages(messages, tools)
        
        assert response.content == "I'll manage your todo list."
        assert len(response.tool_calls) == 2
        
        tool_names = [tc["function"]["name"] for tc in response.tool_calls]
        assert "todo_write" in tool_names
        assert "todo_read" in tool_names
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_search_tools_integration(self, mock_acompletion):
        """Test glob, grep, and ls tools with LiteLLM adapter."""
        # Mock LiteLLM response with search tools
        mock_response = Mock(
            choices=[Mock(
                message=Mock(
                    content="I'll search for files and content.",
                    tool_calls=[
                        Mock(
                            id="call_glob",
                            function=Mock(
                                name="glob",
                                arguments='{"pattern": "**/*.py", "recursive": true}'
                            )
                        ),
                        Mock(
                            id="call_grep",
                            function=Mock(
                                name="grep",
                                arguments='{"pattern": "function", "file_pattern": "*.py", "context_lines": 2}'
                            )
                        ),
                        Mock(
                            id="call_ls",
                            function=Mock(
                                name="ls",
                                arguments='{"path": ".", "long_format": true, "sort_by": "modified"}'
                            )
                        )
                    ]
                )
            )]
        )
        mock_acompletion.return_value = mock_response
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        tools = [TOOL_SCHEMAS["glob"], TOOL_SCHEMAS["grep"], TOOL_SCHEMAS["ls"]]
        messages = [{"role": "user", "content": "Search for Python files, find functions, and list directory"}]
        
        # Test search tools
        response = await adapter.chat_with_messages(messages, tools)
        
        assert response.content == "I'll search for files and content."
        assert len(response.tool_calls) == 3
        
        tool_names = [tc["function"]["name"] for tc in response.tool_calls]
        assert "glob" in tool_names
        assert "grep" in tool_names
        assert "ls" in tool_names
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_multi_edit_tool_integration(self, mock_acompletion):
        """Test multi_edit tool with LiteLLM adapter."""
        # Mock LiteLLM response with multi-edit
        mock_response = Mock(
            choices=[Mock(
                message=Mock(
                    content="I'll perform multiple file edits atomically.",
                    tool_calls=[Mock(
                        id="call_multi_edit",
                        function=Mock(
                            name="multi_edit",
                            arguments='{"edits": [{"file_path": "file1.py", "new_content": "content1", "operation": "edit"}, {"file_path": "file2.py", "new_content": "content2", "operation": "create"}], "atomic": true}'
                        )
                    )]
                )
            )]
        )
        mock_acompletion.return_value = mock_response
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        tools = [TOOL_SCHEMAS["multi_edit"]]
        messages = [{"role": "user", "content": "Edit multiple files at once"}]
        
        # Test multi-edit tool
        response = await adapter.chat_with_messages(messages, tools)
        
        assert response.content == "I'll perform multiple file edits atomically."
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]["function"]["name"] == "multi_edit"
        
        # Verify complex parameters
        arguments = response.tool_calls[0]["function"]["arguments"]
        assert '"atomic": true' in arguments
        assert '"operation": "edit"' in arguments
        assert '"operation": "create"' in arguments


@pytest.mark.slow
class TestLiteLLMToolsValidation:
    """Test tool schema validation and error handling with LiteLLM adapter."""
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_all_tool_schemas_validation(self, mock_acompletion):
        """Test that all 11 tool schemas are properly validated by LiteLLM adapter."""
        adapter = LiteLLMAdapter("openai/gpt-4o")
        
        # Get all tool schemas
        all_tools = get_tool_schemas()
        
        # Verify we have all 11 tools
        expected_tools = [
            "file_search", "file_read", "file_create", "file_edit", "shell_exec",
            "todo_read", "todo_write", "glob", "grep", "ls", "multi_edit"
        ]
        tool_names = [tool["function"]["name"] for tool in all_tools]
        
        assert len(all_tools) == 11
        for expected_tool in expected_tools:
            assert expected_tool in tool_names
        
        # Test tool validation
        validated_tools = adapter.format_tools_for_provider(all_tools)
        
        # All tools should pass validation
        assert len(validated_tools) == 11
        
        # Verify each tool has required structure
        for tool in validated_tools:
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_invalid_tool_calls_handling(self, mock_acompletion):
        """Test handling of invalid tool calls with LiteLLM adapter."""
        # Mock LiteLLM response with invalid tool calls
        mock_response = Mock(
            choices=[Mock(
                message=Mock(
                    content="I'll try to call tools.",
                    tool_calls=[
                        Mock(
                            id="call_invalid",
                            function=Mock(
                                name="nonexistent_tool",
                                arguments='{"invalid": "parameter"}'
                            )
                        ),
                        Mock(
                            id="call_malformed",
                            function=Mock(
                                name="file_read",
                                arguments='invalid json'
                            )
                        ),
                        Mock(
                            id="call_valid",
                            function=Mock(
                                name="file_read",
                                arguments='{"file_path": "test.txt"}'
                            )
                        )
                    ]
                )
            )]
        )
        mock_acompletion.return_value = mock_response
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        tools = [TOOL_SCHEMAS["file_read"]]
        messages = [{"role": "user", "content": "Test invalid tool calls"}]
        
        # Test response handling with invalid tool calls
        response = await adapter.chat_with_messages(messages, tools)
        
        assert response.content == "I'll try to call tools."
        assert len(response.tool_calls) == 3  # All tool calls preserved
        
        # Verify tool calls are returned as-is (validation happens at execution)
        tool_names = [tc["function"]["name"] for tc in response.tool_calls]
        assert "nonexistent_tool" in tool_names
        assert "file_read" in tool_names
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_tool_parameter_types_handling(self, mock_acompletion):
        """Test handling of various parameter types in tool calls."""
        # Mock LiteLLM response with diverse parameter types
        mock_response = Mock(
            choices=[Mock(
                message=Mock(
                    content="Testing parameter types.",
                    tool_calls=[
                        Mock(
                            id="call_file_search",
                            function=Mock(
                                name="file_search",
                                arguments='{"pattern": "*.py", "case_sensitive": true, "max_results": 50}'
                            )
                        ),
                        Mock(
                            id="call_ls",
                            function=Mock(
                                name="ls",
                                arguments='{"path": "/home", "show_hidden": false, "sort_by": "size", "reverse": true}'
                            )
                        ),
                        Mock(
                            id="call_shell_exec",
                            function=Mock(
                                name="shell_exec",
                                arguments='{"command": "python script.py", "timeout": 30.5, "working_dir": "/tmp"}'
                            )
                        )
                    ]
                )
            )]
        )
        mock_acompletion.return_value = mock_response
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        tools = [TOOL_SCHEMAS["file_search"], TOOL_SCHEMAS["ls"], TOOL_SCHEMAS["shell_exec"]]
        messages = [{"role": "user", "content": "Test parameter types"}]
        
        # Test parameter types handling
        response = await adapter.chat_with_messages(messages, tools)
        
        assert len(response.tool_calls) == 3
        
        # Verify parameter types are preserved in JSON
        for tool_call in response.tool_calls:
            arguments = tool_call["function"]["arguments"]
            assert isinstance(arguments, str)  # Should be JSON string
            
            # Verify specific parameter types in JSON
            if tool_call["function"]["name"] == "file_search":
                assert '"case_sensitive": true' in arguments
                assert '"max_results": 50' in arguments
            elif tool_call["function"]["name"] == "ls":
                assert '"show_hidden": false' in arguments
                assert '"reverse": true' in arguments
            elif tool_call["function"]["name"] == "shell_exec":
                assert '"timeout": 30.5' in arguments


@pytest.mark.slow
class TestLiteLLMToolsStreaming:
    """Test tool calling in streaming mode with LiteLLM adapter."""
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_streaming_with_tool_calls(self, mock_acompletion):
        """Test streaming responses that include tool calls."""
        # Mock streaming response with tool calls
        async def mock_stream():
            yield {
                "choices": [{
                    "delta": {
                        "role": "assistant",
                        "content": "I'll help you"
                    }
                }]
            }
            yield {
                "choices": [{
                    "delta": {
                        "content": " with file operations."
                    }
                }]
            }
            yield {
                "choices": [{
                    "delta": {
                        "tool_calls": [{
                            "id": "call_file_read",
                            "function": {
                                "name": "file_read",
                                "arguments": '{"file_path": "test.txt"}'
                            }
                        }]
                    }
                }]
            }
        
        mock_stream_obj = Mock()
        mock_stream_obj.__aiter__ = lambda self: mock_stream()
        mock_stream_obj.aclose = AsyncMock()
        mock_acompletion.return_value = mock_stream_obj
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        tools = [TOOL_SCHEMAS["file_read"]]
        messages = [{"role": "user", "content": "Read a file"}]
        
        # Collect streaming chunks
        chunks = []
        async for chunk in adapter.stream_chat(messages, tools):
            chunks.append(chunk)
        
        # Verify streaming worked with tools
        assert len(chunks) == 3
        assert chunks[0]["content"] == "I'll help you"
        assert chunks[1]["content"] == " with file operations."
        assert len(chunks[2]["tool_calls"]) == 1
        assert chunks[2]["tool_calls"][0]["function"]["name"] == "file_read"
        
        # Verify cleanup
        mock_stream_obj.aclose.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_streaming_multiple_tool_calls(self, mock_acompletion):
        """Test streaming responses with multiple tool calls."""
        # Mock streaming response with multiple tool calls
        async def mock_stream():
            yield {
                "choices": [{
                    "delta": {
                        "role": "assistant",
                        "content": "Processing multiple operations."
                    }
                }]
            }
            yield {
                "choices": [{
                    "delta": {
                        "tool_calls": [{
                            "id": "call_1",
                            "function": {
                                "name": "file_search",
                                "arguments": '{"pattern": "*.py"}'
                            }
                        }]
                    }
                }]
            }
            yield {
                "choices": [{
                    "delta": {
                        "tool_calls": [{
                            "id": "call_2",
                            "function": {
                                "name": "ls",
                                "arguments": '{"path": "."}'
                            }
                        }]
                    }
                }]
            }
        
        mock_stream_obj = Mock()
        mock_stream_obj.__aiter__ = lambda self: mock_stream()
        mock_stream_obj.aclose = AsyncMock()
        mock_acompletion.return_value = mock_stream_obj
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        tools = [TOOL_SCHEMAS["file_search"], TOOL_SCHEMAS["ls"]]
        messages = [{"role": "user", "content": "Search and list"}]
        
        # Collect streaming chunks
        chunks = []
        async for chunk in adapter.stream_chat(messages, tools):
            chunks.append(chunk)
        
        # Verify multiple tool calls in streaming
        assert len(chunks) == 3
        assert chunks[0]["content"] == "Processing multiple operations."
        
        # Verify tool calls were streamed separately
        tool_call_chunks = [chunk for chunk in chunks if chunk.get("tool_calls")]
        assert len(tool_call_chunks) == 2
        
        all_tool_names = []
        for chunk in tool_call_chunks:
            for tool_call in chunk["tool_calls"]:
                all_tool_names.append(tool_call["function"]["name"])
        
        assert "file_search" in all_tool_names
        assert "ls" in all_tool_names


@pytest.mark.slow
class TestLiteLLMToolsEndToEnd:
    """End-to-end tests with actual tool execution simulation."""
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_complete_tool_workflow(self, mock_acompletion, isolated_workspace):
        """Test complete workflow: LLM calls tool, tool executes, results flow back."""
        # Create test environment
        test_file = Path("test_workflow.py")
        test_file.write_text("print('Hello, World!')")
        
        # Mock LiteLLM response asking to read the file
        mock_response = Mock(
            choices=[Mock(
                message=Mock(
                    content="I'll read the file for you.",
                    tool_calls=[Mock(
                        id="call_file_read",
                        function=Mock(
                            name="file_read",
                            arguments='{"file_path": "test_workflow.py"}'
                        )
                    )]
                )
            )]
        )
        mock_acompletion.return_value = mock_response
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        tools = [TOOL_SCHEMAS["file_read"]]
        messages = [{"role": "user", "content": "Read the test_workflow.py file"}]
        
        # Get LLM response with tool call
        response = await adapter.chat_with_messages(messages, tools)
        
        # Verify tool call was made
        assert len(response.tool_calls) == 1
        tool_call = response.tool_calls[0]
        assert tool_call["function"]["name"] == "file_read"
        
        # Simulate tool execution (normally done by orchestrator)
        from songbird.tools.registry import get_tool_function
        tool_function = get_tool_function("file_read")
        
        # Parse tool arguments and execute
        import json
        tool_args = json.loads(tool_call["function"]["arguments"])
        tool_result = await tool_function(**tool_args)
        
        # Verify tool execution results
        assert tool_result["success"] is True
        assert "Hello, World!" in tool_result["result"]["content"]
        assert tool_result["result"]["file_path"] == "test_workflow.py"
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_tool_error_handling_workflow(self, mock_acompletion):
        """Test workflow when tools encounter errors."""
        # Mock LLM response calling non-existent file
        mock_response = Mock(
            choices=[Mock(
                message=Mock(
                    content="I'll try to read a non-existent file.",
                    tool_calls=[Mock(
                        id="call_file_read",
                        function=Mock(
                            name="file_read",
                            arguments='{"file_path": "nonexistent_file.txt"}'
                        )
                    )]
                )
            )]
        )
        mock_acompletion.return_value = mock_response
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        tools = [TOOL_SCHEMAS["file_read"]]
        messages = [{"role": "user", "content": "Read nonexistent_file.txt"}]
        
        # Get LLM response
        response = await adapter.chat_with_messages(messages, tools)
        
        # Execute tool and verify error handling
        from songbird.tools.registry import get_tool_function
        import json
        
        tool_call = response.tool_calls[0]
        tool_function = get_tool_function("file_read")
        tool_args = json.loads(tool_call["function"]["arguments"])
        
        tool_result = await tool_function(**tool_args)
        
        # Verify error is properly handled
        assert tool_result["success"] is False
        assert "error" in tool_result
        assert "not found" in tool_result["error"].lower() or "does not exist" in tool_result["error"].lower()


if __name__ == "__main__":
    # Run tool integration tests
    pytest.main([__file__, "-v", "-m", "slow"])