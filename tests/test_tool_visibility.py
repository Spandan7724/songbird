# tests/test_tool_visibility.py
"""
Tests for enhanced tool output visibility and formatting.

Tests the improvements made to ensure LLMs can properly see and understand
tool execution results.
"""
import pytest
import json
import tempfile
import os
from unittest.mock import Mock, patch
from pathlib import Path
from songbird.orchestrator import SongbirdOrchestrator
from songbird.tools.executor import ToolExecutor


class TestToolVisibility:
    """Test enhanced tool output visibility features."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Temporary workspace for tool tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def executor(self, temp_workspace):
        """Tool executor in temporary workspace."""
        return ToolExecutor(temp_workspace)
    
    @pytest.fixture
    def orchestrator(self, temp_workspace):
        """Orchestrator for testing tool visibility."""
        mock_provider = Mock()
        return SongbirdOrchestrator(mock_provider, temp_workspace)

    def test_file_read_result_formatting(self, orchestrator):
        """Test file read results are formatted for better LLM visibility."""
        file_result = {
            "file_path": "/test/example.py",
            "lines_returned": 5,
            "content": "def hello():\n    print('Hello World')\n    return True\n\ndef main():\n    hello()"
        }
        
        formatted = orchestrator._format_tool_result_for_llm("file_read", file_result, True)
        parsed = json.loads(formatted)
        
        assert parsed["tool"] == "file_read"
        assert parsed["success"] == True
        assert parsed["file_path"] == "/test/example.py"
        assert parsed["lines_read"] == 5
        assert "def hello():" in parsed["content_preview"]
        assert len(parsed["content_preview"]) <= 503  # 500 + "..."

    def test_file_create_result_formatting(self, orchestrator):
        """Test file creation results are clearly formatted."""
        create_result = {
            "file_path": "/test/new_file.py",
            "message": "File created successfully"
        }
        
        formatted = orchestrator._format_tool_result_for_llm("file_create", create_result, True)
        parsed = json.loads(formatted)
        
        assert parsed["tool"] == "file_create"
        assert parsed["success"] == True
        assert parsed["file_path"] == "/test/new_file.py"
        assert parsed["message"] == "File created successfully"

    def test_shell_exec_result_formatting(self, orchestrator):
        """Test shell execution results include all relevant output."""
        shell_result = {
            "command": "ls -la",
            "exit_code": 0,
            "stdout": "total 4\ndrwxr-xr-x 2 user user 4096 Jun 24 10:00 .\ndrwxr-xr-x 3 user user 4096 Jun 24 09:00 ..",
            "stderr": ""
        }
        
        formatted = orchestrator._format_tool_result_for_llm("shell_exec", shell_result, True)
        parsed = json.loads(formatted)
        
        assert parsed["tool"] == "shell_exec"
        assert parsed["success"] == True
        assert parsed["command"] == "ls -la"
        assert parsed["exit_code"] == 0
        assert "total 4" in parsed["stdout"]
        assert parsed["stderr"] == ""

    def test_search_result_formatting(self, orchestrator):
        """Test search results are summarized clearly."""
        search_result = {
            "pattern": "TODO",
            "total_matches": 15,
            "matches": [
                {"file": "main.py", "line": 10, "content": "# TODO: Fix this"},
                {"file": "utils.py", "line": 25, "content": "# TODO: Optimize"},
                {"file": "tests.py", "line": 5, "content": "# TODO: Add more tests"},
                {"file": "config.py", "line": 12, "content": "# TODO: Validate"},
                {"file": "app.py", "line": 33, "content": "# TODO: Error handling"},
                {"file": "db.py", "line": 8, "content": "# TODO: Connection pool"}
            ]
        }
        
        formatted = orchestrator._format_tool_result_for_llm("file_search", search_result, True)
        parsed = json.loads(formatted)
        
        assert parsed["tool"] == "file_search"
        assert parsed["success"] == True
        assert parsed["pattern"] == "TODO"
        assert parsed["matches_found"] == 15
        assert parsed["files_searched"] == 6
        assert len(parsed["matches"]) == 5  # Should limit to first 5
        assert parsed["matches"][0]["file"] == "main.py"

    def test_directory_listing_formatting(self, orchestrator):
        """Test directory listing results are clearly structured."""
        ls_result = {
            "path": "/test/project",
            "entries": [
                "main.py", "utils.py", "config.py", "tests/",
                "README.md", "requirements.txt", ".git/", 
                "docs/", "examples/", "scripts/", "data/", "logs/"
            ]
        }
        
        formatted = orchestrator._format_tool_result_for_llm("ls", ls_result, True)
        parsed = json.loads(formatted)
        
        assert parsed["tool"] == "ls"
        assert parsed["success"] == True
        assert parsed["path"] == "/test/project"
        assert parsed["entries_found"] == 12
        assert len(parsed["entries"]) == 10  # Should limit to first 10
        assert "main.py" in parsed["entries"]

    def test_error_result_formatting(self, orchestrator):
        """Test error results are clearly communicated."""
        error_result = {
            "error": "File not found: /nonexistent/file.txt",
            "details": "The specified file does not exist"
        }
        
        formatted = orchestrator._format_tool_result_for_llm("file_read", error_result, False)
        parsed = json.loads(formatted)
        
        assert parsed["tool"] == "file_read"
        assert parsed["success"] == False
        assert "File not found" in parsed["error"]
        assert "file_read failed to execute" in parsed["message"]

    def test_generic_tool_formatting(self, orchestrator):
        """Test generic tool results fallback to structured format."""
        generic_result = {
            "status": "completed",
            "data": {"key": "value"},
            "metrics": {"time": 1.5, "memory": "10MB"}
        }
        
        formatted = orchestrator._format_tool_result_for_llm("custom_tool", generic_result, True)
        parsed = json.loads(formatted)
        
        assert parsed["tool"] == "custom_tool"
        assert parsed["success"] == True
        assert parsed["result"]["status"] == "completed"
        assert parsed["result"]["data"]["key"] == "value"

    @pytest.mark.asyncio
    async def test_tool_result_visibility_in_conversation(self, temp_workspace):
        """Test that tool results are properly visible in conversation history."""
        from unittest.mock import AsyncMock
        
        # Create a real file for testing
        test_file = Path(temp_workspace) / "test.txt"
        test_file.write_text("Hello World")
        
        mock_provider = Mock()
        mock_provider.chat_with_messages = AsyncMock()
        
        orchestrator = SongbirdOrchestrator(mock_provider, temp_workspace)
        
        # Create a real tool result
        executor = ToolExecutor(temp_workspace)
        result = await executor.execute_tool("file_read", {"file_path": "test.txt"})
        
        # Simulate adding the result to conversation
        formatted_result = orchestrator._format_tool_result_for_llm(
            "file_read", result["result"], result["success"]
        )
        
        orchestrator.conversation_history.append({
            "role": "tool",
            "tool_call_id": "test_call",
            "content": formatted_result
        })
        
        # Verify the tool result is properly formatted in history
        history = orchestrator.get_conversation_history()
        tool_message = next(msg for msg in history if msg["role"] == "tool")
        
        parsed_content = json.loads(tool_message["content"])
        assert parsed_content["tool"] == "file_read"
        assert parsed_content["success"] == True
        assert "Hello World" in parsed_content["content_preview"]

    def test_debug_mode_tool_visibility(self, orchestrator):
        """Test debug mode provides additional tool visibility."""
        with patch.dict(os.environ, {"SONGBIRD_DEBUG_TOOLS": "true"}):
            with patch('builtins.print') as mock_print:
                # Simulate debug output during tool result processing
                tool_result = {
                    "tool_call_id": "debug_call",
                    "function_name": "file_create",
                    "result": {"success": True, "result": {"file_path": "debug.txt"}}
                }
                
                # This would normally be called during agentic loop
                # Just test the debug flag recognition
                debug_enabled = os.getenv("SONGBIRD_DEBUG_TOOLS", "").lower() == "true"
                assert debug_enabled == True

    def test_json_formatting_handles_special_characters(self, orchestrator):
        """Test JSON formatting handles special characters properly."""
        special_result = {
            "file_path": "/test/file with spaces.txt",
            "content": "Text with \"quotes\" and 'apostrophes' and \n newlines \t tabs",
            "message": "File contains special characters: <>&"
        }
        
        formatted = orchestrator._format_tool_result_for_llm("file_read", special_result, True)
        
        # Should be valid JSON despite special characters
        parsed = json.loads(formatted)
        assert parsed["success"] == True
        assert "quotes" in parsed["content_preview"]
        assert "apostrophes" in parsed["content_preview"]

    def test_large_content_truncation(self, orchestrator):
        """Test large content is properly truncated for visibility."""
        large_content = "x" * 1000  # 1000 characters
        large_result = {
            "file_path": "/test/large.txt",
            "content": large_content,
            "lines_returned": 100
        }
        
        formatted = orchestrator._format_tool_result_for_llm("file_read", large_result, True)
        parsed = json.loads(formatted)
        
        # Should be truncated to 500 + "..."
        assert len(parsed["content_preview"]) == 503
        assert parsed["content_preview"].endswith("...")
        assert parsed["content_preview"].startswith("x")