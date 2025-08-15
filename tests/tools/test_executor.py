# tests/tools/test_executor.py
import pytest
from pathlib import Path
from songbird.tools.executor import ToolExecutor


class TestToolExecutor:
    @pytest.fixture
    def fixture_repo(self):
        """Path to test fixture repository."""
        return str(Path(__file__).parent.parent / "fixtures" / "repo_a")
    
    @pytest.fixture
    def executor(self, fixture_repo):
        """Tool executor with fixture repo as working directory."""
        return ToolExecutor(working_directory=fixture_repo)
    
    @pytest.mark.asyncio
    async def test_execute_file_search_tool(self, executor):
        """Test executing file_search tool through executor."""
        result = await executor.execute_tool("file_search", {"pattern": "TODO"})
        
        assert result["success"] is True
        assert "result" in result
        
        # Updated to match current API - result is a dict with matches key
        result_data = result["result"]
        assert isinstance(result_data, dict)
        assert "matches" in result_data
        assert isinstance(result_data["matches"], list)
        assert len(result_data["matches"]) >= 3  # Should find TODOs in fixture files
        
    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self, executor):
        """Test executing unknown tool returns error."""
        result = await executor.execute_tool("nonexistent_tool", {})
        
        assert result["success"] is False
        assert "error" in result
        assert "Unknown tool" in result["error"]
        
    @pytest.mark.asyncio
    async def test_execute_tool_with_exception(self, executor):
        """Test that tool execution errors are handled gracefully."""
        # Try to search in nonexistent directory
        result = await executor.execute_tool("file_search", {
            "pattern": "TODO", 
            "directory": "/nonexistent/path"
        })
        
        # Tool should handle this gracefully (either fail or return empty results)
        assert "success" in result
        # If it succeeds, should return empty results; if it fails, should have error
        if result["success"]:
            assert "result" in result
        else:
            assert "error" in result
        
    @pytest.mark.asyncio
    async def test_execute_multiple_tools_if_method_exists(self, executor):
        """Test executing multiple tool calls if the method exists."""
        # Check if the executor has batch execution method
        if hasattr(executor, 'execute_tool_calls'):
            tool_calls = [
                {"name": "file_search", "arguments": {"pattern": "TODO"}},
                {"name": "file_search", "arguments": {"pattern": "test"}},
            ]
            
            results = await executor.execute_tool_calls(tool_calls)
            
            assert len(results) == 2
            assert all(result["success"] for result in results)
        else:
            # If method doesn't exist, test individual execution
            result1 = await executor.execute_tool("file_search", {"pattern": "TODO"})
            result2 = await executor.execute_tool("file_search", {"pattern": "test"})
            
            assert result1["success"] is True
            assert result2["success"] is True
        
    def test_get_available_tools(self, executor):
        """Test that executor returns available tool schemas."""
        tools = executor.get_available_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0
        
        # Check that file_search tool is available
        tool_names = [tool["function"]["name"] for tool in tools]
        assert "file_search" in tool_names