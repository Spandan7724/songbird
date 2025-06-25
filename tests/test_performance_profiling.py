#!/usr/bin/env python3
"""Performance profiling and optimization tests for Songbird."""

import asyncio
import tempfile
import pytest
import time
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add the songbird directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPerformanceProfiler:
    """Test performance profiling functionality."""
    
    def test_profiler_basic_functionality(self):
        """Test basic profiler operations."""
        from songbird.performance import PerformanceProfiler, enable_profiling, disable_profiling
        
        profiler = PerformanceProfiler()
        profiler.enable()
        
        # Test synchronous operation profiling
        with profiler.profile_operation("test_operation", param="value"):
            time.sleep(0.01)  # 10ms operation
        
        # Should have recorded one metric
        report = profiler.generate_report()
        assert report.operations_count == 1
        assert report.metrics[0].operation == "test_operation"
        assert report.metrics[0].duration > 0.01  # Should be at least 10ms
        assert "param" in report.metrics[0].metadata
        
        profiler.disable()
    
    @pytest.mark.asyncio
    async def test_async_operation_profiling(self):
        """Test asynchronous operation profiling."""
        from songbird.performance import PerformanceProfiler
        
        profiler = PerformanceProfiler()
        profiler.enable()
        
        # Test asynchronous operation profiling
        async with profiler.profile_async_operation("async_test", type="async"):
            await asyncio.sleep(0.02)  # 20ms async operation
        
        report = profiler.generate_report()
        assert report.operations_count == 1
        assert report.metrics[0].operation == "async_test"
        assert report.metrics[0].duration > 0.02
        assert report.metrics[0].metadata["type"] == "async"
        
        profiler.disable()
    
    def test_function_decorator_profiling(self):
        """Test function decorator profiling."""
        from songbird.performance import PerformanceProfiler
        
        profiler = PerformanceProfiler()
        profiler.enable()
        
        @profiler.profile_function("decorated_function")
        def test_function(x, y):
            time.sleep(0.005)  # 5ms operation
            return x + y
        
        result = test_function(2, 3)
        assert result == 5
        
        report = profiler.generate_report()
        assert report.operations_count == 1
        assert report.metrics[0].operation == "decorated_function"
        assert report.metrics[0].duration > 0.005
        
        profiler.disable()
    
    @pytest.mark.asyncio
    async def test_async_function_decorator_profiling(self):
        """Test async function decorator profiling."""
        from songbird.performance import PerformanceProfiler
        
        profiler = PerformanceProfiler()
        profiler.enable()
        
        @profiler.profile_function("async_decorated_function")
        async def async_test_function(x, y):
            await asyncio.sleep(0.01)
            return x * y
        
        result = await async_test_function(3, 4)
        assert result == 12
        
        report = profiler.generate_report()
        assert report.operations_count == 1
        assert report.metrics[0].operation == "async_decorated_function"
        assert report.metrics[0].duration > 0.01
        
        profiler.disable()
    
    def test_performance_report_analysis(self):
        """Test performance report generation and analysis."""
        from songbird.performance import PerformanceProfiler, PerformanceMetric
        
        profiler = PerformanceProfiler()
        profiler.enable()
        
        # Simulate multiple operations with different performance characteristics
        with profiler.profile_operation("fast_operation"):
            time.sleep(0.001)  # 1ms
        
        with profiler.profile_operation("slow_operation"):
            time.sleep(0.05)   # 50ms
        
        with profiler.profile_operation("medium_operation"):
            time.sleep(0.01)   # 10ms
        
        report = profiler.generate_report()
        
        # Test report structure
        assert report.operations_count == 3
        assert report.total_duration > 0.06  # Should be at least 61ms total
        
        # Test slowest operations
        slowest = report.get_slowest_operations(2)
        assert len(slowest) == 2
        assert slowest[0].operation == "slow_operation"
        assert slowest[1].operation == "medium_operation"
        
        # Test report dictionary conversion
        report_dict = report.to_dict()
        assert "total_duration" in report_dict
        assert "slowest_operations" in report_dict
        assert len(report_dict["slowest_operations"]) <= 5
        
        profiler.disable()
    
    def test_operation_statistics(self):
        """Test operation-specific statistics."""
        from songbird.performance import PerformanceProfiler
        
        profiler = PerformanceProfiler()
        profiler.enable()
        
        # Multiple operations of the same type
        for i in range(3):
            with profiler.profile_operation("repeated_operation", iteration=i):
                time.sleep(0.002)  # 2ms each
        
        stats = profiler.get_operation_stats()
        
        assert "repeated_operation" in stats
        operation_stats = stats["repeated_operation"]
        
        assert operation_stats["count"] == 3
        assert operation_stats["total_duration"] > 0.006  # At least 6ms total
        assert operation_stats["avg_duration"] > 0.002    # Average at least 2ms
        assert operation_stats["min_duration"] > 0        # All operations took some time
        
        profiler.disable()


class TestGlobalProfilerInterface:
    """Test global profiler interface."""
    
    def test_global_profiler_functions(self):
        """Test global profiler convenience functions."""
        from songbird.performance import (
            enable_profiling, disable_profiling, clear_profiling,
            profile_operation, get_profiler
        )
        
        # Clear any existing data
        clear_profiling()
        enable_profiling()
        
        # Use global profiler
        with profile_operation("global_test"):
            time.sleep(0.005)
        
        profiler = get_profiler()
        report = profiler.generate_report()
        
        assert report.operations_count == 1
        assert report.metrics[0].operation == "global_test"
        
        # Clear and disable
        clear_profiling()
        disable_profiling()
        
        # Should be cleared
        report = profiler.generate_report()
        assert report.operations_count == 0
    
    @pytest.mark.asyncio
    async def test_global_async_profiling(self):
        """Test global async profiling interface."""
        from songbird.performance import (
            enable_profiling, disable_profiling, clear_profiling,
            profile_async_operation, get_profiler
        )
        
        clear_profiling()
        enable_profiling()
        
        async with profile_async_operation("global_async_test"):
            await asyncio.sleep(0.01)
        
        profiler = get_profiler()
        report = profiler.generate_report()
        
        assert report.operations_count == 1
        assert report.metrics[0].operation == "global_async_test"
        
        clear_profiling()
        disable_profiling()


class TestOptimizationSuggestions:
    """Test optimization suggestion system."""
    
    def test_slow_operation_detection(self):
        """Test detection of slow operations."""
        from songbird.performance import PerformanceProfiler, OptimizationSuggestions
        
        profiler = PerformanceProfiler()
        profiler.enable()
        
        # Simulate a slow operation
        with profiler.profile_operation("very_slow_operation"):
            time.sleep(1.1)  # More than 1 second
        
        report = profiler.generate_report()
        suggestions = OptimizationSuggestions.analyze_report(report)
        
        # Should suggest optimization for slow operation
        slow_suggestion = any("Slow operation" in s for s in suggestions)
        assert slow_suggestion, f"Expected slow operation suggestion in: {suggestions}"
        
        profiler.disable()
    
    def test_memory_intensive_detection(self):
        """Test detection of memory-intensive operations (simulated)."""
        from songbird.performance import PerformanceProfiler, PerformanceMetric, OptimizationSuggestions
        
        profiler = PerformanceProfiler()
        
        # Manually add a metric with high memory usage for testing
        high_memory_metric = PerformanceMetric(
            operation="memory_intensive_operation",
            duration=0.1,
            memory_delta=60.0,  # 60MB memory increase
            timestamp=time.time(),
            metadata={}
        )
        
        profiler.metrics = [high_memory_metric]
        
        report = profiler.generate_report()
        suggestions = OptimizationSuggestions.analyze_report(report)
        
        # Should suggest memory optimization
        memory_suggestion = any("Memory-intensive" in s for s in suggestions)
        assert memory_suggestion, f"Expected memory optimization suggestion in: {suggestions}"
    
    def test_tool_specific_suggestions(self):
        """Test tool-specific optimization suggestions."""
        from songbird.performance import PerformanceProfiler, OptimizationSuggestions
        
        profiler = PerformanceProfiler()
        profiler.enable()
        
        # Simulate multiple file operations
        for i in range(5):
            with profiler.profile_operation("file_read"):
                time.sleep(0.5)  # 500ms each, total 2.5s
        
        suggestions = OptimizationSuggestions.suggest_tool_optimizations(profiler)
        
        # Should suggest file operation optimization
        file_suggestion = any("File operations" in s for s in suggestions)
        assert file_suggestion, f"Expected file optimization suggestion in: {suggestions}"
        
        profiler.disable()


class TestPerformanceIntegration:
    """Test performance profiling integration with Songbird components."""
    
    @pytest.mark.asyncio
    async def test_tool_execution_profiling(self):
        """Test profiling of tool execution."""
        from songbird.tools.tool_runner import ToolRunner
        from songbird.performance import enable_profiling, get_profiler, clear_profiling
        
        clear_profiling()
        enable_profiling()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_runner = ToolRunner(working_directory=temp_dir)
            
            # Execute a tool operation
            result = await tool_runner.execute_tool("file_create", {
                "file_path": str(Path(temp_dir) / "test.txt"),
                "content": "Test content"
            })
            
            assert result.get("success", True)
            
            # Check if profiling captured the operation
            profiler = get_profiler()
            report = profiler.generate_report()
            
            # Tool execution should have been profiled
            # Note: This test might need adjustment based on actual profiling integration
            
        clear_profiling()
    
    def test_session_manager_profiling_integration(self):
        """Test profiling integration with session manager."""
        from songbird.memory.optimized_manager import OptimizedSessionManager
        from songbird.performance import enable_profiling, get_profiler, clear_profiling
        
        clear_profiling()
        enable_profiling()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = OptimizedSessionManager(
                working_directory=temp_dir,
                flush_interval=10,  # Long interval for testing
                batch_size=5
            )
            
            # Create session and add messages
            session = manager.create_session()
            assert session is not None
            
            # Session operations might be profiled in future integration
            
        clear_profiling()


class TestPerformanceReportPersistence:
    """Test saving and loading performance reports."""
    
    def test_save_and_load_performance_report(self):
        """Test saving and loading performance reports."""
        from songbird.performance import (
            PerformanceProfiler, save_performance_report, load_performance_report
        )
        
        profiler = PerformanceProfiler()
        profiler.enable()
        
        # Generate some performance data
        with profiler.profile_operation("test_save_operation"):
            time.sleep(0.01)
        
        report = profiler.generate_report()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            report_file = f.name
        
        try:
            # Save report
            save_performance_report(report, report_file)
            
            # Load report
            loaded_data = load_performance_report(report_file)
            
            # Verify data integrity
            assert loaded_data["operations_count"] == 1
            assert loaded_data["total_duration"] > 0
            assert len(loaded_data["slowest_operations"]) == 1
            assert loaded_data["slowest_operations"][0]["operation"] == "test_save_operation"
            
        finally:
            # Cleanup
            Path(report_file).unlink(missing_ok=True)
            profiler.disable()


@pytest.mark.asyncio
async def test_end_to_end_performance_monitoring():
    """Test end-to-end performance monitoring in a realistic scenario."""
    from songbird.orchestrator import SongbirdOrchestrator
    from songbird.performance import enable_profiling, get_profiler, clear_profiling, OptimizationSuggestions
    from unittest.mock import AsyncMock
    
    clear_profiling()
    enable_profiling()
    
    # Mock provider for testing
    mock_provider = AsyncMock()
    mock_provider.__class__.__name__ = "TestProvider"
    mock_provider.model = "test-model"
    
    from songbird.llm.types import ChatResponse
    mock_provider.chat_with_messages.return_value = ChatResponse(
        content="Test response",
        model="test-model",
        usage={"total_tokens": 100},
        tool_calls=None
    )
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create orchestrator (this should be profiled in integration)
        orchestrator = SongbirdOrchestrator(
            provider=mock_provider,
            working_directory=temp_dir
        )
        
        # Simulate some operations
        result = await orchestrator.chat_single_message("Test message")
        assert isinstance(result, str)
        
        # Get performance report
        profiler = get_profiler()
        report = profiler.generate_report()
        
        # Should have some metrics if profiling is integrated
        # This test validates the framework works, actual integration TBD
        
        # Generate optimization suggestions
        suggestions = OptimizationSuggestions.analyze_report(report)
        assert isinstance(suggestions, list)
        assert len(suggestions) > 0  # Should always have at least one suggestion
        
        # Cleanup
        await orchestrator.cleanup()
    
    clear_profiling()


if __name__ == "__main__":
    # Run performance profiling tests
    pytest.main([__file__, "-v"])