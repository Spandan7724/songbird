# tests/test_parallel_execution.py
"""
Tests for parallel tool execution capabilities.

Tests the intelligent parallel vs sequential execution logic
to ensure safety and performance optimization.
"""
import pytest
import asyncio
import tempfile
import time
from unittest.mock import Mock, AsyncMock
from songbird.orchestrator import SongbirdOrchestrator


class TestParallelExecution:
    """Test parallel tool execution features."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Temporary workspace for parallel execution tests."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def orchestrator(self, temp_workspace):
        """Orchestrator for testing parallel execution."""
        mock_provider = Mock()
        return SongbirdOrchestrator(mock_provider, temp_workspace)
    
    def test_parallel_safe_tool_detection(self, orchestrator):
        """Test detection of tools that can run in parallel safely."""
        # Read-only operations should be parallel-safe
        read_only_tools = ["file_read", "ls", "file_search", "grep", "glob"]
        assert orchestrator._can_execute_tools_in_parallel(read_only_tools) == True
        
        # Shell operations (read-only) should be parallel-safe
        shell_tools = ["shell_exec", "file_read", "ls"]
        assert orchestrator._can_execute_tools_in_parallel(shell_tools) == True
        
        # Empty list should be parallel-safe
        assert orchestrator._can_execute_tools_in_parallel([]) == True

    def test_sequential_required_tool_detection(self, orchestrator):
        """Test detection of tools that require sequential execution."""
        # File modification operations require sequential execution
        file_ops = ["file_create", "file_edit", "file_delete"]
        assert orchestrator._can_execute_tools_in_parallel(file_ops) == False
        
        # Multi-edit operations require sequential execution
        multi_ops = ["multi_edit"]
        assert orchestrator._can_execute_tools_in_parallel(multi_ops) == False
        
        # Mixed operations require sequential execution
        mixed = ["file_read", "file_create", "ls"]
        assert orchestrator._can_execute_tools_in_parallel(mixed) == False

    @pytest.mark.asyncio
    async def test_parallel_execution_performance(self, orchestrator):
        """Test that parallel execution is actually faster than sequential."""
        # Create mock tool calls that simulate time-consuming operations
        mock_tool_calls = []
        for i in range(3):
            mock_call = Mock()
            mock_call.function.name = "file_read"
            mock_call.function.arguments = {"file_path": f"test{i}.txt"}
            mock_call.id = f"call_{i}"
            mock_tool_calls.append(mock_call)
        
        # Mock the single tool execution to take some time
        async def slow_tool_execution(tool_call):
            await asyncio.sleep(0.1)  # 100ms delay
            return {
                "tool_call_id": tool_call.id,
                "function_name": "file_read",
                "result": {"success": True, "error": None}
            }
        
        orchestrator._execute_single_tool_async = slow_tool_execution
        
        # Test parallel execution time
        start_time = time.time()
        results = await orchestrator._execute_tools_parallel(mock_tool_calls)
        parallel_time = time.time() - start_time
        
        # Should complete in roughly 0.1 seconds (parallel) not 0.3 (sequential)
        assert parallel_time < 0.2  # Allow some overhead
        assert len(results) == 3
        assert all(result["result"]["success"] for result in results)

    @pytest.mark.asyncio 
    async def test_parallel_execution_error_handling(self, orchestrator):
        """Test error handling during parallel tool execution."""
        # Create tool calls where one will fail
        mock_tool_calls = []
        for i in range(3):
            mock_call = Mock()
            mock_call.function.name = "file_read"
            mock_call.function.arguments = {"file_path": f"test{i}.txt"}
            mock_call.id = f"call_{i}"
            mock_tool_calls.append(mock_call)
        
        # Mock single tool execution with one failure
        async def mixed_tool_execution(tool_call):
            if "1" in tool_call.id:  # Second call fails
                raise ValueError("Simulated error")
            return {
                "tool_call_id": tool_call.id,
                "function_name": "file_read", 
                "result": {"success": True}
            }
        
        orchestrator._execute_single_tool_async = mixed_tool_execution
        
        results = await orchestrator._execute_tools_parallel(mock_tool_calls)
        
        assert len(results) == 3
        
        # Check success and failure results
        success_count = sum(1 for r in results if r["result"]["success"])
        failure_count = sum(1 for r in results if not r["result"]["success"])
        
        assert success_count == 2
        assert failure_count == 1
        
        # Failed result should contain error info
        failed_result = next(r for r in results if not r["result"]["success"])
        assert "error" in failed_result["result"]
        assert "Simulated error" in failed_result["result"]["error"]

    def test_extract_function_name_for_parallel_detection(self, orchestrator):
        """Test function name extraction for parallel detection."""
        # Test Ollama format
        ollama_call = Mock()
        ollama_call.function.name = "file_read"
        assert orchestrator._extract_function_name(ollama_call) == "file_read"
        
        # Test dict format (Gemini)
        dict_call = {"function": {"name": "file_create"}}
        assert orchestrator._extract_function_name(dict_call) == "file_create"
        
        # Test unknown format
        unknown_call = "invalid"
        assert orchestrator._extract_function_name(unknown_call) == "unknown"

    @pytest.mark.asyncio
    async def test_single_tool_async_execution(self, orchestrator, temp_workspace):
        """Test single tool async execution wrapper."""
        # Create a real file for testing
        test_file = f"{temp_workspace}/async_test.txt"
        with open(test_file, "w") as f:
            f.write("Async test content")
        
        # Create mock tool call
        mock_call = Mock()
        mock_call.function.name = "file_read"
        mock_call.function.arguments = {"file_path": "async_test.txt"}
        mock_call.id = "async_call"
        
        result = await orchestrator._execute_single_tool_async(mock_call)
        
        assert result["tool_call_id"] == "async_call"
        assert result["function_name"] == "file_read"
        assert result["result"]["success"] == True

    @pytest.mark.asyncio
    async def test_single_tool_async_error_handling(self, orchestrator):
        """Test error handling in single tool async execution."""
        # Create tool call with invalid arguments
        mock_call = Mock()
        mock_call.function.name = "file_read"
        mock_call.function.arguments = {"invalid": "arguments"}
        mock_call.id = "error_call"
        
        result = await orchestrator._execute_single_tool_async(mock_call)
        
        assert result["tool_call_id"] == "error_call"
        assert result["function_name"] == "file_read"
        assert result["result"]["success"] == False
        assert "error" in result["result"]

    def test_tool_call_format_handling_in_parallel(self, orchestrator):
        """Test different tool call formats work with parallel execution."""
        # Test various tool call formats
        formats = [
            # Ollama format
            Mock(function=Mock(name="test1", arguments={}), id="call1"),
            # Dict format
            {"function": {"name": "test2", "arguments": {}}, "id": "call2"},
            # Invalid format
            "invalid_call"
        ]
        
        # Should extract function names properly for parallel detection
        names = [orchestrator._extract_function_name(call) for call in formats]
        assert names == ["test1", "test2", "unknown"]

    @pytest.mark.asyncio
    async def test_parallel_vs_sequential_execution_choice(self, orchestrator):
        """Test the logic for choosing parallel vs sequential execution."""
        mock_provider = Mock()
        orchestrator.provider = mock_provider
        
        # Mock responses for different scenarios
        
        # Scenario 1: Parallel-safe tools
        parallel_response = Mock()
        parallel_response.tool_calls = [
            Mock(function=Mock(name="file_read")),
            Mock(function=Mock(name="ls"))
        ]
        
        # Mock the parallel execution path
        orchestrator._execute_tools_parallel = AsyncMock(return_value=[])
        
        # Should choose parallel execution
        can_parallel = orchestrator._can_execute_tools_in_parallel(["file_read", "ls"])
        assert can_parallel == True
        
        # Scenario 2: Sequential-required tools
        sequential_response = Mock()
        sequential_response.tool_calls = [
            Mock(function=Mock(name="file_create")),
            Mock(function=Mock(name="file_edit"))
        ]
        
        # Should choose sequential execution
        can_parallel = orchestrator._can_execute_tools_in_parallel(["file_create", "file_edit"])
        assert can_parallel == False

    @pytest.mark.asyncio
    async def test_concurrent_execution_with_asyncio_gather(self, orchestrator):
        """Test that parallel execution properly uses asyncio.gather."""
        # Create multiple tool calls
        tool_calls = [Mock() for _ in range(5)]
        for i, call in enumerate(tool_calls):
            call.id = f"gather_call_{i}"
            call.function.name = "test_tool"
            call.function.arguments = {}
        
        # Mock execution that tracks call order
        execution_order = []
        
        async def track_execution(tool_call):
            execution_order.append(tool_call.id)
            await asyncio.sleep(0.01)  # Small delay
            return {
                "tool_call_id": tool_call.id,
                "function_name": "test_tool",
                "result": {"success": True}
            }
        
        orchestrator._execute_single_tool_async = track_execution
        
        results = await orchestrator._execute_tools_parallel(tool_calls)
        
        # All tools should have been executed
        assert len(results) == 5
        assert len(execution_order) == 5
        
        # All should be successful
        assert all(r["result"]["success"] for r in results)