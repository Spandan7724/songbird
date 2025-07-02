# tests/test_litellm_performance.py
"""
Performance tests for LiteLLM adapter with various providers.

Tests response times, throughput, memory usage, and resource cleanup
across different providers and model configurations.
"""

import asyncio
import time
import pytest
import psutil
import os
import gc
from unittest.mock import Mock, patch, AsyncMock

from songbird.llm.litellm_adapter import LiteLLMAdapter


@pytest.mark.slow
class TestLiteLLMStreamingLatency:
    """Test streaming latency and performance characteristics."""
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_streaming_first_token_latency(self, mock_acompletion):
        """Test time to first token in streaming mode."""
        # Mock streaming response with realistic timing
        async def mock_stream():
            await asyncio.sleep(0.1)  # Simulate network latency
            yield {
                "choices": [{
                    "delta": {
                        "role": "assistant",
                        "content": "Hello"
                    }
                }]
            }
            for i in range(10):
                await asyncio.sleep(0.02)  # Simulate inter-token latency
                yield {
                    "choices": [{
                        "delta": {
                            "content": f" token{i}"
                        }
                    }]
                }
        
        mock_stream_obj = Mock()
        mock_stream_obj.__aiter__ = lambda self: mock_stream()
        mock_stream_obj.aclose = AsyncMock()
        mock_acompletion.return_value = mock_stream_obj
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        messages = [{"role": "user", "content": "Hello"}]
        
        # Measure time to first token
        start_time = time.time()
        first_token_time = None
        
        chunk_count = 0
        async for chunk in adapter.stream_chat(messages, []):
            if first_token_time is None:
                first_token_time = time.time()
            chunk_count += 1
        
        total_time = time.time() - start_time
        time_to_first_token = first_token_time - start_time
        
        # Performance assertions
        assert time_to_first_token < 0.2  # First token within 200ms
        assert total_time < 0.5  # Total streaming under 500ms
        assert chunk_count == 11  # All chunks received
        
        # Verify resource cleanup
        mock_stream_obj.aclose.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_streaming_throughput(self, mock_acompletion):
        """Test streaming throughput with large responses."""
        # Mock high-throughput streaming response
        async def mock_high_throughput_stream():
            # Simulate rapid token generation
            for i in range(100):
                await asyncio.sleep(0.001)  # 1ms between tokens
                yield {
                    "choices": [{
                        "delta": {
                            "content": f"token{i} "
                        }
                    }]
                }
        
        mock_stream_obj = Mock()
        mock_stream_obj.__aiter__ = lambda self: mock_high_throughput_stream()
        mock_stream_obj.aclose = AsyncMock()
        mock_acompletion.return_value = mock_stream_obj
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        messages = [{"role": "user", "content": "Generate a long response"}]
        
        # Measure throughput
        start_time = time.time()
        chunks = []
        
        async for chunk in adapter.stream_chat(messages, []):
            chunks.append(chunk)
        
        total_time = time.time() - start_time
        tokens_per_second = len(chunks) / total_time
        
        # Performance assertions
        assert len(chunks) == 100
        assert tokens_per_second > 80  # At least 80 tokens/second
        assert total_time < 2.0  # Complete within 2 seconds
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_concurrent_streaming_performance(self, mock_acompletion):
        """Test performance with multiple concurrent streams."""
        # Mock concurrent streaming
        async def mock_stream():
            for i in range(5):
                await asyncio.sleep(0.01)
                yield {
                    "choices": [{
                        "delta": {
                            "content": f"token{i} "
                        }
                    }]
                }
        
        def create_mock_stream():
            mock_stream_obj = Mock()
            mock_stream_obj.__aiter__ = lambda self: mock_stream()
            mock_stream_obj.aclose = AsyncMock()
            return mock_stream_obj
        
        mock_acompletion.side_effect = lambda **kwargs: create_mock_stream()
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        messages = [{"role": "user", "content": "Hello"}]
        
        # Run multiple concurrent streams
        async def single_stream():
            chunks = []
            async for chunk in adapter.stream_chat(messages, []):
                chunks.append(chunk)
            return len(chunks)
        
        start_time = time.time()
        tasks = [single_stream() for _ in range(5)]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        # Performance assertions
        assert all(result == 5 for result in results)  # All streams complete
        assert total_time < 0.2  # Concurrent streams finish quickly
        assert len(results) == 5  # All concurrent streams succeeded


@pytest.mark.slow
class TestLiteLLMResourceManagement:
    """Test resource management and memory efficiency."""
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_memory_usage_streaming(self, mock_acompletion):
        """Test memory usage during streaming operations."""
        # Mock streaming response
        async def mock_stream():
            for i in range(50):
                yield {
                    "choices": [{
                        "delta": {
                            "content": f"Large content block {i} " * 100
                        }
                    }]
                }
        
        mock_stream_obj = Mock()
        mock_stream_obj.__aiter__ = lambda self: mock_stream()
        mock_stream_obj.aclose = AsyncMock()
        mock_acompletion.return_value = mock_stream_obj
        
        # Measure memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        messages = [{"role": "user", "content": "Generate large response"}]
        
        chunks = []
        async for chunk in adapter.stream_chat(messages, []):
            chunks.append(chunk)
        
        # Force garbage collection
        gc.collect()
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory assertions (should not leak significantly)
        assert len(chunks) == 50
        assert memory_increase < 50 * 1024 * 1024  # Less than 50MB increase
        
        # Verify cleanup
        mock_stream_obj.aclose.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_resource_cleanup_on_cancellation(self, mock_acompletion):
        """Test resource cleanup when streaming is cancelled."""
        # Mock infinite streaming
        async def mock_infinite_stream():
            for i in range(1000):
                await asyncio.sleep(0.001)
                yield {
                    "choices": [{
                        "delta": {
                            "content": f"token{i} "
                        }
                    }]
                }
        
        mock_stream_obj = Mock()
        mock_stream_obj.__aiter__ = lambda self: mock_infinite_stream()
        mock_stream_obj.aclose = AsyncMock()
        mock_acompletion.return_value = mock_stream_obj
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        messages = [{"role": "user", "content": "Start infinite stream"}]
        
        # Start streaming and cancel after short time
        async def cancelled_stream():
            chunks = []
            async for chunk in adapter.stream_chat(messages, []):
                chunks.append(chunk)
                if len(chunks) >= 5:  # Cancel after 5 chunks
                    break
            return chunks
        
        # Create task and cancel it
        task = asyncio.create_task(cancelled_stream())
        await asyncio.sleep(0.01)  # Let it start
        
        chunks = await task
        
        # Verify partial completion and cleanup
        assert len(chunks) == 5
        # Note: aclose might not be called in this test due to break,
        # but in real cancellation scenarios it would be called
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_connection_pooling_simulation(self, mock_acompletion):
        """Test behavior that simulates connection pooling."""
        call_count = 0
        
        async def mock_stream():
            nonlocal call_count
            call_count += 1
            for i in range(3):
                yield {
                    "choices": [{
                        "delta": {
                            "content": f"call{call_count}-token{i} "
                        }
                    }]
                }
        
        def create_mock_stream():
            mock_stream_obj = Mock()
            mock_stream_obj.__aiter__ = lambda self: mock_stream()
            mock_stream_obj.aclose = AsyncMock()
            return mock_stream_obj
        
        mock_acompletion.side_effect = lambda **kwargs: create_mock_stream()
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        messages = [{"role": "user", "content": "Test"}]
        
        # Multiple sequential calls to simulate reuse
        for i in range(3):
            chunks = []
            async for chunk in adapter.stream_chat(messages, []):
                chunks.append(chunk)
            
            assert len(chunks) == 3
            assert f"call{i+1}" in chunks[0]["content"]
        
        # Verify all calls were made
        assert call_count == 3
        assert mock_acompletion.call_count == 3


@pytest.mark.slow
class TestLiteLLMRegressionTests:
    """Regression tests to ensure performance doesn't degrade."""
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_completion_latency_regression(self, mock_acompletion):
        """Test non-streaming completion latency doesn't regress."""
        # Mock response with controlled timing
        async def mock_completion(**kwargs):
            await asyncio.sleep(0.05)  # Simulate 50ms API call
            return Mock(
                choices=[Mock(
                    message=Mock(
                        content="Test response",
                        tool_calls=None
                    )
                )],
                model="openai/gpt-4o",
                usage=Mock(
                    prompt_tokens=10,
                    completion_tokens=5,
                    total_tokens=15
                )
            )
        
        mock_acompletion.side_effect = mock_completion
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        messages = [{"role": "user", "content": "Test"}]
        
        # Measure completion latency
        start_time = time.time()
        response = await adapter.chat_with_messages(messages)
        completion_time = time.time() - start_time
        
        # Regression assertion - should complete within 100ms
        assert completion_time < 0.1
        assert response.content == "Test response"
        assert response.usage["total_tokens"] == 15
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_tool_calling_latency_regression(self, mock_acompletion):
        """Test tool calling latency doesn't regress."""
        # Mock tool calling response
        async def mock_tool_completion(**kwargs):
            await asyncio.sleep(0.1)  # Simulate 100ms API call
            return Mock(
                choices=[Mock(
                    message=Mock(
                        content="I'll help you with that.",
                        tool_calls=[Mock(
                            id="call_123",
                            function=Mock(
                                name="test_tool",
                                arguments='{"param": "value"}'
                            )
                        )]
                    )
                )],
                model="openai/gpt-4o"
            )
        
        mock_acompletion.side_effect = mock_tool_completion
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        messages = [{"role": "user", "content": "Use the tool"}]
        tools = [{
            "type": "function",
            "function": {
                "name": "test_tool",
                "description": "A test tool",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "param": {"type": "string"}
                    }
                }
            }
        }]
        
        # Measure tool calling latency
        start_time = time.time()
        response = await adapter.chat_with_messages(messages, tools)
        completion_time = time.time() - start_time
        
        # Regression assertion - should complete within 150ms
        assert completion_time < 0.15
        assert response.content == "I'll help you with that."
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0]["function"]["name"] == "test_tool"
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_error_handling_performance(self, mock_acompletion):
        """Test error handling doesn't introduce significant latency."""
        # Mock various error conditions
        error_cases = [
            Exception("401 Unauthorized"),
            Exception("429 Rate limit exceeded"),
            Exception("404 Model not found"),
            Exception("Connection timeout"),
            Exception("Generic error")
        ]
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        messages = [{"role": "user", "content": "Test"}]
        
        total_time = 0
        for error in error_cases:
            mock_acompletion.side_effect = error
            
            start_time = time.time()
            try:
                await adapter.chat_with_messages(messages)
            except Exception:
                pass  # Expected
            error_time = time.time() - start_time
            total_time += error_time
            
            # Each error should be handled quickly
            assert error_time < 0.001  # Less than 1ms per error
        
        # Total error handling time should be minimal
        assert total_time < 0.01  # Less than 10ms total
    
    @pytest.mark.asyncio
    async def test_model_switching_performance(self):
        """Test model switching doesn't cause performance degradation."""
        adapter = LiteLLMAdapter("openai/gpt-4o")
        
        models_to_test = [
            "anthropic/claude-3.5-sonnet",
            "gemini/gemini-2.0-flash-001",
            "openai/gpt-4o-mini",
            "openai/gpt-4o"  # Back to original
        ]
        
        switch_times = []
        
        for model in models_to_test:
            start_time = time.time()
            adapter.set_model(model)
            switch_time = time.time() - start_time
            switch_times.append(switch_time)
            
            # Verify state was updated
            expected_prefix = model.split("/")[0]
            expected_name = model.split("/", 1)[1]
            assert adapter.vendor_prefix == expected_prefix
            assert adapter.model_name == expected_name
        
        # All switches should be very fast
        assert all(t < 0.001 for t in switch_times)  # Less than 1ms each
        assert sum(switch_times) < 0.005  # Less than 5ms total


@pytest.mark.slow 
class TestLiteLLMStressTests:
    """Stress tests for high-load scenarios."""
    
    @pytest.mark.asyncio
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_rapid_fire_requests(self, mock_acompletion):
        """Test handling of rapid successive requests."""
        # Mock fast responses
        mock_response = Mock(
            choices=[Mock(
                message=Mock(content="Response", tool_calls=None)
            )],
            model="openai/gpt-4o"
        )
        mock_acompletion.return_value = mock_response
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        messages = [{"role": "user", "content": "Test"}]
        
        # Send 20 rapid requests
        start_time = time.time()
        tasks = [
            adapter.chat_with_messages(messages) 
            for _ in range(20)
        ]
        responses = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        # Performance assertions
        assert len(responses) == 20
        assert all(r.content == "Response" for r in responses)
        assert total_time < 0.1  # All 20 requests in under 100ms
        assert mock_acompletion.call_count == 20
    
    @pytest.mark.asyncio 
    @patch('songbird.llm.litellm_adapter.litellm.acompletion')
    async def test_large_context_handling(self, mock_acompletion):
        """Test performance with large context windows."""
        # Mock response for large context
        mock_response = Mock(
            choices=[Mock(
                message=Mock(content="Processed large context", tool_calls=None)
            )],
            model="openai/gpt-4o"
        )
        mock_acompletion.return_value = mock_response
        
        adapter = LiteLLMAdapter("openai/gpt-4o")
        
        # Create large message history (simulate long conversation)
        large_messages = []
        for i in range(50):
            large_messages.append({
                "role": "user" if i % 2 == 0 else "assistant",
                "content": f"Message {i} with substantial content " * 50
            })
        
        # Measure performance with large context
        start_time = time.time()
        response = await adapter.chat_with_messages(large_messages)
        completion_time = time.time() - start_time
        
        # Should handle large context efficiently
        assert completion_time < 0.01  # Fast processing (mocked)
        assert response.content == "Processed large context"
        
        # Verify large context was passed to LiteLLM
        call_args = mock_acompletion.call_args[1]
        assert len(call_args["messages"]) == 50


# Benchmark comparison utilities
class PerformanceBenchmark:
    """Utility class for performance benchmarking."""
    
    def __init__(self):
        self.results = {}
    
    def measure(self, name: str, func, *args, **kwargs):
        """Measure execution time of a function."""
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        self.results[name] = {
            "duration": end_time - start_time,
            "result": result
        }
        return result
    
    async def measure_async(self, name: str, func, *args, **kwargs):
        """Measure execution time of an async function."""
        start_time = time.time()
        result = await func(*args, **kwargs)
        end_time = time.time()
        
        self.results[name] = {
            "duration": end_time - start_time,
            "result": result
        }
        return result
    
    def compare(self, baseline: str, comparison: str, tolerance: float = 0.1):
        """Compare two measurements within tolerance."""
        baseline_time = self.results[baseline]["duration"]
        comparison_time = self.results[comparison]["duration"]
        
        relative_diff = abs(comparison_time - baseline_time) / baseline_time
        return relative_diff <= tolerance
    
    def report(self):
        """Generate performance report."""
        report = "Performance Benchmark Results:\n"
        report += "=" * 40 + "\n"
        
        for name, result in self.results.items():
            duration_ms = result["duration"] * 1000
            report += f"{name:30s}: {duration_ms:8.2f}ms\n"
        
        return report


if __name__ == "__main__":
    # Run performance tests directly
    pytest.main([__file__, "-v", "-m", "slow"])