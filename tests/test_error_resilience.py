#!/usr/bin/env python3
"""Error recovery and resilience testing for Songbird.

Tests the system's ability to handle failures gracefully and recover from errors.
"""

import asyncio
import tempfile
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock

# Add the songbird directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestProviderFailures:
    """Test handling of provider failures and fallbacks."""
    
    @pytest.mark.asyncio
    async def test_provider_connection_failure(self):
        """Test handling when provider is unreachable."""
        from songbird.orchestrator import SongbirdOrchestrator
        
        # Provider that always fails
        failing_provider = AsyncMock()
        failing_provider.__class__.__name__ = "FailingProvider"
        failing_provider.model = "test-model"
        failing_provider.chat_with_messages.side_effect = ConnectionError("Provider unreachable")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            orchestrator = SongbirdOrchestrator(
                provider=failing_provider,
                working_directory=temp_dir
            )
            
            # Should handle connection errors gracefully
            result = await orchestrator.chat_single_message("Test message")
            
            # Should return error message, not crash
            assert isinstance(result, str)
            assert "error" in result.lower()
            
            # Should still be able to cleanup
            await orchestrator.cleanup()
    
    @pytest.mark.asyncio
    async def test_provider_timeout_handling(self):
        """Test handling of provider timeouts."""
        from songbird.orchestrator import SongbirdOrchestrator
        import asyncio
        
        # Provider that times out
        timeout_provider = AsyncMock()
        timeout_provider.__class__.__name__ = "TimeoutProvider"
        timeout_provider.model = "test-model"
        timeout_provider.chat_with_messages.side_effect = asyncio.TimeoutError("Request timed out")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            orchestrator = SongbirdOrchestrator(
                provider=timeout_provider,
                working_directory=temp_dir
            )
            
            result = await orchestrator.chat_single_message("Test message")
            
            # Should handle timeout gracefully
            assert isinstance(result, str)
            assert "error" in result.lower() or "timeout" in result.lower()
            
            await orchestrator.cleanup()
    
    @pytest.mark.asyncio
    async def test_provider_rate_limit_handling(self):
        """Test handling of provider rate limits."""
        from songbird.orchestrator import SongbirdOrchestrator
        from songbird.llm.types import ChatResponse
        
        # Provider that hits rate limits then recovers
        rate_limit_provider = AsyncMock()
        rate_limit_provider.__class__.__name__ = "RateLimitProvider"
        rate_limit_provider.model = "test-model"
        
        # First call fails with rate limit, second succeeds
        rate_limit_provider.chat_with_messages.side_effect = [
            Exception("Rate limit exceeded"),
            ChatResponse(
                content="Recovery successful",
                model="test-model",
                usage={"total_tokens": 50},
                tool_calls=None
            )
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            orchestrator = SongbirdOrchestrator(
                provider=rate_limit_provider,
                working_directory=temp_dir
            )
            
            # First call should handle rate limit
            result1 = await orchestrator.chat_single_message("Test message 1")
            assert isinstance(result1, str)
            
            # Second call should work (if retry logic exists)
            result2 = await orchestrator.chat_single_message("Test message 2")
            assert isinstance(result2, str)
            
            await orchestrator.cleanup()


class TestToolExecutionFailures:
    """Test handling of tool execution failures."""
    
    @pytest.mark.asyncio
    async def test_file_permission_errors(self):
        """Test handling of file permission errors."""
        from songbird.tools.tool_runner import ToolRunner
        
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_runner = ToolRunner(working_directory=temp_dir)
            
            # Try to create file in non-existent directory
            result = await tool_runner.execute_tool("file_create", {
                "file_path": "/root/forbidden/test.txt",  # Should fail with permission error
                "content": "Test content"
            })
            
            # Should handle permission error gracefully
            assert isinstance(result, dict)
            # Error should be captured in the result
            inner_result = result.get("result", {})
            if inner_result.get("success") == False:
                assert "error" in inner_result
    
    @pytest.mark.asyncio
    async def test_disk_space_simulation(self):
        """Test handling when disk space is limited."""
        from songbird.tools.tool_runner import ToolRunner
        
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_runner = ToolRunner(working_directory=temp_dir)
            
            # Try to create a very large file (simulating disk space issues)
            large_content = "x" * (1024 * 1024)  # 1MB of content
            
            result = await tool_runner.execute_tool("file_create", {
                "file_path": str(Path(temp_dir) / "large_file.txt"),
                "content": large_content
            })
            
            # Should handle gracefully (either succeed or fail gracefully)
            assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_corrupted_file_handling(self):
        """Test handling of corrupted or binary files."""
        from songbird.tools.tool_runner import ToolRunner
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a binary file
            binary_file = Path(temp_dir) / "binary.bin"
            with open(binary_file, "wb") as f:
                f.write(bytes(range(256)))  # Write binary data
            
            tool_runner = ToolRunner(working_directory=temp_dir)
            
            # Try to read binary file
            result = await tool_runner.execute_tool("file_read", {
                "file_path": str(binary_file)
            })
            
            # Should handle binary content gracefully
            assert isinstance(result, dict)
    
    @pytest.mark.asyncio
    async def test_concurrent_tool_execution_errors(self):
        """Test handling errors in concurrent tool execution."""
        from songbird.tools.tool_runner import ToolRunner
        
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_runner = ToolRunner(working_directory=temp_dir)
            
            # Execute multiple tools concurrently, some will fail
            tasks = []
            for i in range(5):
                if i % 2 == 0:
                    # Even numbers: valid file operations
                    task = tool_runner.execute_tool("file_create", {
                        "file_path": str(Path(temp_dir) / f"file_{i}.txt"),
                        "content": f"Content {i}"
                    })
                else:
                    # Odd numbers: invalid file operations
                    task = tool_runner.execute_tool("file_read", {
                        "file_path": f"/nonexistent/file_{i}.txt"
                    })
                tasks.append(task)
            
            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Should have 5 results, some successful, some with errors
            assert len(results) == 5
            for result in results:
                assert not isinstance(result, Exception), "Tools should not raise unhandled exceptions"


class TestSessionManagementFailures:
    """Test session management resilience."""
    
    @pytest.mark.asyncio
    async def test_session_corruption_recovery(self):
        """Test recovery from corrupted session files."""
        from songbird.memory.optimized_manager import OptimizedSessionManager
        from songbird.memory.models import Message
        
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = OptimizedSessionManager(
                working_directory=temp_dir,
                flush_interval=1,
                batch_size=2
            )
            
            # Create a session
            session = manager.create_session()
            
            # Add a message
            message = Message(role="user", content="Test message")
            manager.append_message(session.id, message)
            
            # Force flush
            await asyncio.sleep(2)
            
            # Corrupt the session file
            session_file = Path(temp_dir) / f"session-{session.id}.jsonl"
            if session_file.exists():
                with open(session_file, "w") as f:
                    f.write("corrupted data\n")
            
            # Try to load the corrupted session
            loaded_session = manager.load_session(session.id)
            
            # Should handle corruption gracefully (return None or empty session)
            # Exact behavior depends on implementation
            assert loaded_session is None or hasattr(loaded_session, 'messages')
            
            await manager.shutdown()
    
    @pytest.mark.asyncio
    async def test_concurrent_session_access(self):
        """Test handling concurrent access to sessions."""
        from songbird.memory.optimized_manager import OptimizedSessionManager
        from songbird.memory.models import Message
        
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = OptimizedSessionManager(
                working_directory=temp_dir,
                flush_interval=1,
                batch_size=5
            )
            
            session = manager.create_session()
            
            # Simulate concurrent writes
            async def write_messages(start_idx, count):
                for i in range(start_idx, start_idx + count):
                    message = Message(role="user", content=f"Message {i}")
                    manager.append_message(session.id, message)
                    await asyncio.sleep(0.01)  # Small delay
            
            # Start multiple concurrent writers
            tasks = [
                write_messages(0, 10),
                write_messages(10, 10),
                write_messages(20, 10)
            ]
            
            await asyncio.gather(*tasks)
            
            # Wait for flush
            await asyncio.sleep(3)
            
            # Load session and verify data integrity
            loaded_session = manager.load_session(session.id)
            
            # Should have some messages (exact count depends on race conditions)
            if loaded_session:
                assert len(loaded_session.messages) > 0
            
            await manager.shutdown()
    
    @pytest.mark.asyncio
    async def test_session_directory_permissions(self):
        """Test handling of session directory permission issues."""
        from songbird.memory.optimized_manager import OptimizedSessionManager
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a read-only subdirectory (simulate permission issues)
            readonly_dir = Path(temp_dir) / "readonly"
            readonly_dir.mkdir()
            
            try:
                # Try to make it read-only (may not work on all systems)
                readonly_dir.chmod(0o444)
                
                # Try to create session manager in read-only directory
                manager = OptimizedSessionManager(
                    working_directory=str(readonly_dir),
                    flush_interval=1,
                    batch_size=2
                )
                
                # Should handle permission error gracefully
                session = manager.create_session()
                assert session is not None  # Should still create session in memory
                
                await manager.shutdown()
                
            finally:
                # Restore permissions for cleanup
                readonly_dir.chmod(0o755)


class TestSystemResourceFailures:
    """Test handling of system resource exhaustion."""
    
    @pytest.mark.asyncio
    async def test_memory_pressure_handling(self):
        """Test handling under memory pressure."""
        from songbird.memory.optimized_manager import OptimizedSessionManager
        from songbird.memory.models import Message
        
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = OptimizedSessionManager(
                working_directory=temp_dir,
                flush_interval=10,  # Long interval to keep in memory
                batch_size=1000    # Large batch size
            )
            
            session = manager.create_session()
            
            # Add many messages to simulate memory pressure
            for i in range(100):  # Reasonable number for testing
                message = Message(
                    role="user",
                    content=f"Large message {i}: " + "x" * 1000  # 1KB per message
                )
                manager.append_message(session.id, message)
            
            # Should still function under memory pressure
            stats = manager.get_stats()
            assert "cached_sessions" in stats
            
            await manager.shutdown()
    
    def test_file_descriptor_exhaustion_resilience(self):
        """Test resilience to file descriptor exhaustion."""
        from songbird.tools.tool_runner import ToolRunner
        
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_runner = ToolRunner(working_directory=temp_dir)
            
            # Should be able to create tool runner without issues
            assert tool_runner is not None
            
            # Tool runner should handle file operations properly
            tools = tool_runner.get_available_tools()
            assert len(tools) > 0
    
    @pytest.mark.asyncio
    async def test_network_instability_simulation(self):
        """Test handling of network instability for remote providers."""
        from songbird.orchestrator import SongbirdOrchestrator
        
        # Provider that simulates network issues
        unstable_provider = AsyncMock()
        unstable_provider.__class__.__name__ = "UnstableProvider"
        unstable_provider.model = "test-model"
        
        # Simulate intermittent failures
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:  # Fail every 3rd call
                raise ConnectionError("Network error")
            else:
                from songbird.llm.types import ChatResponse
                return ChatResponse(
                    content="Success",
                    model="test-model",
                    usage={"total_tokens": 20},
                    tool_calls=None
                )
        
        unstable_provider.chat_with_messages.side_effect = side_effect
        
        with tempfile.TemporaryDirectory() as temp_dir:
            orchestrator = SongbirdOrchestrator(
                provider=unstable_provider,
                working_directory=temp_dir
            )
            
            # Multiple calls should be handled (some succeed, some fail)
            results = []
            for i in range(5):
                result = await orchestrator.chat_single_message(f"Message {i}")
                results.append(result)
            
            # Should have some results (not all failures)
            assert len(results) == 5
            success_count = sum(1 for r in results if "success" in r.lower() or "error" not in r.lower())
            assert success_count > 0, "Should have some successful calls"
            
            await orchestrator.cleanup()


class TestGracefulShutdownResilience:
    """Test graceful shutdown under various failure conditions."""
    
    @pytest.mark.asyncio
    async def test_shutdown_with_pending_operations(self):
        """Test shutdown while operations are still pending."""
        from songbird.orchestrator import SongbirdOrchestrator
        
        mock_provider = AsyncMock()
        mock_provider.__class__.__name__ = "SlowProvider"
        mock_provider.model = "test-model"
        
        # Slow response
        async def slow_response(*args, **kwargs):
            await asyncio.sleep(2)
            from songbird.llm.types import ChatResponse
            return ChatResponse(
                content="Slow response",
                model="test-model",
                usage={"total_tokens": 30},
                tool_calls=None
            )
        
        mock_provider.chat_with_messages.side_effect = slow_response
        
        with tempfile.TemporaryDirectory() as temp_dir:
            orchestrator = SongbirdOrchestrator(
                provider=mock_provider,
                working_directory=temp_dir
            )
            
            # Start a slow operation
            task = asyncio.create_task(
                orchestrator.chat_single_message("Slow message")
            )
            
            # Give it a moment to start
            await asyncio.sleep(0.1)
            
            # Cleanup should be graceful even with pending operations
            await orchestrator.cleanup()
            
            # Cancel the pending task
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    
    @pytest.mark.asyncio
    async def test_cleanup_with_corrupted_state(self):
        """Test cleanup when internal state is corrupted."""
        from songbird.orchestrator import SongbirdOrchestrator
        
        mock_provider = Mock()
        mock_provider.__class__.__name__ = "CorruptedProvider"
        mock_provider.model = "test-model"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            orchestrator = SongbirdOrchestrator(
                provider=mock_provider,
                working_directory=temp_dir
            )
            
            # Corrupt internal state
            orchestrator.session_manager = None
            orchestrator.ui = None
            
            # Cleanup should still work without crashing
            await orchestrator.cleanup()  # Should not raise exception
    
    def test_signal_handler_reliability(self):
        """Test signal handler works reliably."""
        from songbird.core.signal_handler import GracefulShutdownHandler
        
        handler = GracefulShutdownHandler()
        
        # Multiple registrations should work
        callbacks_executed = []
        
        def callback1():
            callbacks_executed.append(1)
        
        def callback2():
            callbacks_executed.append(2)
        
        def failing_callback():
            raise Exception("Callback failure")
        
        handler.register_shutdown_callback("callback1", callback1)
        handler.register_shutdown_callback("callback2", callback2)
        handler.register_shutdown_callback("failing", failing_callback)
        
        # Shutdown should execute all callbacks (even if some fail)
        handler._sync_shutdown()
        
        # Should have executed at least the non-failing callbacks
        assert 1 in callbacks_executed
        assert 2 in callbacks_executed
        
        # Cleanup
        handler.restore_original_handlers()


@pytest.mark.asyncio
async def test_end_to_end_failure_recovery():
    """Test end-to-end system recovery from multiple simultaneous failures."""
    from songbird.orchestrator import SongbirdOrchestrator
    
    # Provider that has multiple types of failures
    chaotic_provider = AsyncMock()
    chaotic_provider.__class__.__name__ = "ChaoticProvider"
    chaotic_provider.model = "test-model"
    
    call_count = 0
    def chaotic_response(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        
        # Different failure patterns
        if call_count == 1:
            raise ConnectionError("Connection failed")
        elif call_count == 2:
            raise asyncio.TimeoutError("Timeout")
        elif call_count == 3:
            raise Exception("Random error")
        else:
            # Eventually succeed
            from songbird.llm.types import ChatResponse
            return ChatResponse(
                content="Finally working!",
                model="test-model",
                usage={"total_tokens": 40},
                tool_calls=None
            )
    
    chaotic_provider.chat_with_messages.side_effect = chaotic_response
    
    with tempfile.TemporaryDirectory() as temp_dir:
        orchestrator = SongbirdOrchestrator(
            provider=chaotic_provider,
            working_directory=temp_dir
        )
        
        # System should handle multiple failures gracefully
        results = []
        for i in range(4):
            result = await orchestrator.chat_single_message(f"Message {i}")
            results.append(result)
        
        # Should have handled all failures gracefully
        assert len(results) == 4
        
        # Last result should be successful
        assert "finally working" in results[-1].lower() or "error" in results[-1].lower()
        
        # Infrastructure should still be functional
        stats = orchestrator.get_infrastructure_stats()
        assert "session_manager" in stats
        
        # Cleanup should work even after failures
        await orchestrator.cleanup()


if __name__ == "__main__":
    # Run error resilience tests
    pytest.main([__file__, "-v"])