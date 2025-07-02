#!/usr/bin/env python3
"""Integration tests for end-to-end workflows in Songbird."""

import tempfile
import pytest
import sys
from pathlib import Path

# Add the songbird directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))


class MockProvider:
    """Mock provider for testing that simulates LLM responses."""
    
    def __init__(self, model="test-model"):
        self.model = model
        self._response_queue = []
        self._call_count = 0
    
    def queue_response(self, content, tool_calls=None):
        """Queue a response to be returned by chat methods."""
        from songbird.llm.types import ChatResponse
        self._response_queue.append(ChatResponse(
            content=content,
            model=self.model,
            usage={"total_tokens": 100},
            tool_calls=tool_calls
        ))
    
    async def chat(self, message, tools=None):
        """Mock chat method."""
        return self._get_next_response()
    
    async def chat_with_messages(self, messages, tools=None):
        """Mock chat with messages method."""
        return self._get_next_response()
    
    def _get_next_response(self):
        """Get the next queued response."""
        self._call_count += 1
        if self._response_queue:
            return self._response_queue.pop(0)
        else:
            # Default response if queue is empty
            from songbird.llm.types import ChatResponse
            return ChatResponse(
                content=f"Mock response {self._call_count}",
                model=self.model,
                usage={"total_tokens": 50},
                tool_calls=None
            )


class TestSimpleWorkflows:
    """Test simple end-to-end workflows."""
    
    @pytest.mark.asyncio
    async def test_simple_file_read_workflow(self):
        """Test reading a file end-to-end."""
        from songbird.orchestrator import SongbirdOrchestrator
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test file
            test_file = Path(temp_dir) / "test.txt"
            test_file.write_text("Hello, World!")
            
            # Setup mock provider
            provider = MockProvider()
            provider.queue_response(
                content="I'll read the test file for you.",
                tool_calls=[{
                    "id": "call_1",
                    "function": {
                        "name": "file_read",
                        "arguments": {"file_path": str(test_file)}
                    }
                }]
            )
            provider.queue_response(
                content="I've successfully read the file. It contains 'Hello, World!'."
            )
            
            # Create orchestrator
            orchestrator = SongbirdOrchestrator(
                provider=provider,
                working_directory=temp_dir
            )
            
            # Execute workflow
            result = await orchestrator.chat_single_message("Read the test.txt file")
            
            # Verify result
            assert isinstance(result, str)
            assert len(result) > 0
            
            # Cleanup
            await orchestrator.cleanup()
    
    @pytest.mark.asyncio
    async def test_simple_file_creation_workflow(self):
        """Test creating a file end-to-end."""
        from songbird.orchestrator import SongbirdOrchestrator
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup mock provider
            provider = MockProvider()
            provider.queue_response(
                content="I'll create a new file for you.",
                tool_calls=[{
                    "id": "call_1",
                    "function": {
                        "name": "file_create",
                        "arguments": {
                            "file_path": str(Path(temp_dir) / "new_file.py"),
                            "content": "print('Hello from new file!')"
                        }
                    }
                }]
            )
            provider.queue_response(
                content="I've successfully created the new Python file."
            )
            
            # Create orchestrator
            orchestrator = SongbirdOrchestrator(
                provider=provider,
                working_directory=temp_dir
            )
            
            # Execute workflow
            result = await orchestrator.chat_single_message("Create a Python file that prints hello")
            
            # Verify result
            assert isinstance(result, str)
            
            # Verify file was created
            new_file = Path(temp_dir) / "new_file.py"
            assert new_file.exists()
            assert "Hello from new file!" in new_file.read_text()
            
            # Cleanup
            await orchestrator.cleanup()


class TestMultiStepWorkflows:
    """Test complex multi-step workflows."""
    
    @pytest.mark.asyncio
    async def test_search_and_analyze_workflow(self):
        """Test searching files and analyzing results."""
        from songbird.orchestrator import SongbirdOrchestrator
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            (Path(temp_dir) / "file1.py").write_text("# TODO: Fix this bug\nprint('file1')")
            (Path(temp_dir) / "file2.py").write_text("print('file2')")
            (Path(temp_dir) / "file3.js").write_text("// TODO: Refactor this\nconsole.log('file3')")
            
            # Setup mock provider with multi-step plan
            provider = MockProvider()
            
            # Step 1: Search for TODO items
            provider.queue_response(
                content="I'll search for TODO items in your codebase.",
                tool_calls=[{
                    "id": "call_1",
                    "function": {
                        "name": "file_search",
                        "arguments": {
                            "pattern": "TODO",
                            "directory": temp_dir
                        }
                    }
                }]
            )
            
            # Step 2: Read files with TODOs
            provider.queue_response(
                content="Found TODO items. Let me read those files to analyze them.",
                tool_calls=[{
                    "id": "call_2",
                    "function": {
                        "name": "file_read",
                        "arguments": {"file_path": str(Path(temp_dir) / "file1.py")}
                    }
                }, {
                    "id": "call_3", 
                    "function": {
                        "name": "file_read",
                        "arguments": {"file_path": str(Path(temp_dir) / "file3.js")}
                    }
                }]
            )
            
            # Final response
            provider.queue_response(
                content="Analysis complete: Found 2 TODO items - one in Python file (bug fix needed) and one in JavaScript file (refactoring needed)."
            )
            
            # Create orchestrator
            orchestrator = SongbirdOrchestrator(
                provider=provider,
                working_directory=temp_dir
            )
            
            # Execute complex workflow
            result = await orchestrator.chat_single_message("Find and analyze all TODO items in the codebase")
            
            # Verify result includes analysis
            assert isinstance(result, str)
            assert len(result) > 50  # Should be a substantial analysis
            
            # Cleanup
            await orchestrator.cleanup()
    
    @pytest.mark.asyncio
    async def test_file_modification_workflow(self):
        """Test reading, modifying, and creating files in sequence."""
        from songbird.orchestrator import SongbirdOrchestrator
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create initial file
            config_file = Path(temp_dir) / "config.py"
            config_file.write_text("DEBUG = False\nVERSION = '1.0.0'")
            
            # Setup mock provider for multi-step workflow
            provider = MockProvider()
            
            # Step 1: Read config
            provider.queue_response(
                content="I'll read the current config and then create an updated version.",
                tool_calls=[{
                    "id": "call_1",
                    "function": {
                        "name": "file_read",
                        "arguments": {"file_path": str(config_file)}
                    }
                }]
            )
            
            # Step 2: Create updated config
            provider.queue_response(
                content="Now I'll create an updated configuration file.",
                tool_calls=[{
                    "id": "call_2",
                    "function": {
                        "name": "file_create",
                        "arguments": {
                            "file_path": str(Path(temp_dir) / "config_new.py"),
                            "content": "DEBUG = True\nVERSION = '2.0.0'\nNEW_FEATURE = True"
                        }
                    }
                }]
            )
            
            # Final response
            provider.queue_response(
                content="I've successfully created an updated configuration file with DEBUG enabled and version bumped to 2.0.0."
            )
            
            # Create orchestrator
            orchestrator = SongbirdOrchestrator(
                provider=provider,
                working_directory=temp_dir
            )
            
            # Execute workflow
            result = await orchestrator.chat_single_message("Read the config file and create an updated version with DEBUG=True and version 2.0.0")
            
            # Verify result
            assert isinstance(result, str)
            
            # Verify new file was created correctly
            new_config = Path(temp_dir) / "config_new.py"
            assert new_config.exists()
            content = new_config.read_text()
            assert "DEBUG = True" in content
            assert "VERSION = '2.0.0'" in content
            
            # Cleanup
            await orchestrator.cleanup()


class TestSessionPersistence:
    """Test session persistence and recovery."""
    
    @pytest.mark.asyncio
    async def test_session_creation_and_persistence(self):
        """Test that sessions are created and persisted properly."""
        from songbird.orchestrator import SongbirdOrchestrator
        from songbird.memory.models import Message
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup mock provider
            provider = MockProvider()
            provider.queue_response("Hello! I'm ready to help.")
            
            # Create orchestrator
            orchestrator = SongbirdOrchestrator(
                provider=provider,
                working_directory=temp_dir
            )
            
            # Should have a session manager
            assert orchestrator.session_manager is not None
            
            # Create a session
            session = orchestrator.session_manager.create_session()
            assert session is not None
            assert session.id is not None
            
            # Add a message
            message = Message(role="user", content="Test message")
            orchestrator.session_manager.append_message(session.id, message)
            
            # Verify session can be loaded
            loaded_session = orchestrator.session_manager.load_session(session.id)
            assert loaded_session is not None
            assert loaded_session.id == session.id
            assert len(loaded_session.messages) > 0
            
            # Cleanup
            await orchestrator.cleanup()
    
    @pytest.mark.asyncio
    async def test_session_manager_statistics(self):
        """Test session manager provides useful statistics."""
        from songbird.orchestrator import SongbirdOrchestrator
        
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = MockProvider()
            
            orchestrator = SongbirdOrchestrator(
                provider=provider,
                working_directory=temp_dir
            )
            
            # Get statistics
            stats = orchestrator.session_manager.get_stats()
            
            # Should have required stats
            assert "cached_sessions" in stats
            assert "flush_interval" in stats
            assert "batch_size" in stats
            assert isinstance(stats["cached_sessions"], int)
            
            # Cleanup
            await orchestrator.cleanup()


class TestProviderIntegration:
    """Test provider integration and switching."""
    
    def test_provider_adapter_creation(self):
        """Test provider adapter is created correctly."""
        from songbird.orchestrator import SongbirdOrchestrator
        
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = MockProvider()
            
            orchestrator = SongbirdOrchestrator(
                provider=provider,
                working_directory=temp_dir
            )
            
            # Should have provider adapter
            assert orchestrator.provider_adapter is not None
            
            # Should provide capabilities
            capabilities = orchestrator.get_provider_info()
            assert isinstance(capabilities, dict)
            assert "provider_name" in capabilities
    
    def test_tool_schema_generation(self):
        """Test that tool schemas are generated for providers."""
        from songbird.tools.tool_registry import get_tool_registry
        
        registry = get_tool_registry()
        
        # Should generate schemas for different providers
        openai_schemas = registry.get_llm_schemas("openai")
        gemini_schemas = registry.get_llm_schemas("gemini")
        
        assert len(openai_schemas) > 0
        assert len(gemini_schemas) > 0
        assert len(openai_schemas) == len(gemini_schemas)  # Same tools, different formats
        
        # Schemas should have required fields
        for schema in openai_schemas:
            assert "type" in schema
            assert "function" in schema
            assert "name" in schema["function"]
            assert "description" in schema["function"]


class TestErrorHandling:
    """Test error handling in workflows."""
    
    @pytest.mark.asyncio
    async def test_tool_execution_error_handling(self):
        """Test handling of tool execution errors."""
        from songbird.orchestrator import SongbirdOrchestrator
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup mock provider that tries to read non-existent file
            provider = MockProvider()
            provider.queue_response(
                content="I'll try to read the file.",
                tool_calls=[{
                    "id": "call_1",
                    "function": {
                        "name": "file_read",
                        "arguments": {"file_path": "/nonexistent/file.txt"}
                    }
                }]
            )
            provider.queue_response(
                content="I encountered an error reading the file, but I handled it gracefully."
            )
            
            orchestrator = SongbirdOrchestrator(
                provider=provider,
                working_directory=temp_dir
            )
            
            # Should handle the error gracefully
            result = await orchestrator.chat_single_message("Read nonexistent file")
            
            # Should still get a response (error handled)
            assert isinstance(result, str)
            assert len(result) > 0
            
            # Cleanup
            await orchestrator.cleanup()
    
    @pytest.mark.asyncio
    async def test_orchestrator_cleanup_under_error(self):
        """Test orchestrator cleanup works even when errors occur."""
        from songbird.orchestrator import SongbirdOrchestrator
        
        with tempfile.TemporaryDirectory() as temp_dir:
            provider = MockProvider()
            
            orchestrator = SongbirdOrchestrator(
                provider=provider,
                working_directory=temp_dir
            )
            
            # Cleanup should work even if nothing was done
            await orchestrator.cleanup()
            
            # Should be able to cleanup multiple times
            await orchestrator.cleanup()


@pytest.mark.asyncio
async def test_full_integration_workflow():
    """Test a comprehensive workflow that exercises multiple components."""
    from songbird.orchestrator import SongbirdOrchestrator
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a realistic project structure
        (Path(temp_dir) / "src").mkdir()
        (Path(temp_dir) / "src" / "main.py").write_text("def main():\n    print('Hello World')")
        (Path(temp_dir) / "README.md").write_text("# Test Project\nA simple test project.")
        
        # Setup comprehensive workflow
        provider = MockProvider()
        
        # Multi-step plan: analyze project, find files, create summary
        provider.queue_response(
            content="I'll analyze your project structure.",
            tool_calls=[{
                "id": "call_1",
                "function": {
                    "name": "ls",
                    "arguments": {"path": temp_dir}
                }
            }]
        )
        
        provider.queue_response(
            content="Now I'll read the main source file.",
            tool_calls=[{
                "id": "call_2",
                "function": {
                    "name": "file_read",
                    "arguments": {"file_path": str(Path(temp_dir) / "src" / "main.py")}
                }
            }]
        )
        
        provider.queue_response(
            content="Let me also read the README.",
            tool_calls=[{
                "id": "call_3",
                "function": {
                    "name": "file_read",
                    "arguments": {"file_path": str(Path(temp_dir) / "README.md")}
                }
            }]
        )
        
        provider.queue_response(
            content="Finally, I'll create a project summary.",
            tool_calls=[{
                "id": "call_4",
                "function": {
                    "name": "file_create",
                    "arguments": {
                        "file_path": str(Path(temp_dir) / "ANALYSIS.md"),
                        "content": "# Project Analysis\n\nThis is a simple Python project with:\n- Main entry point in src/main.py\n- README documentation\n- Clean structure"
                    }
                }
            }]
        )
        
        provider.queue_response(
            content="Complete! I've analyzed your project and created a comprehensive summary in ANALYSIS.md."
        )
        
        # Execute comprehensive workflow
        orchestrator = SongbirdOrchestrator(
            provider=provider,
            working_directory=temp_dir
        )
        
        result = await orchestrator.chat_single_message(
            "Analyze this project: list the files, read the source code and README, then create a summary"
        )
        
        # Verify comprehensive workflow completed
        assert isinstance(result, str)
        assert "Complete!" in result or "summary" in result.lower()
        
        # Verify analysis file was created
        analysis_file = Path(temp_dir) / "ANALYSIS.md"
        assert analysis_file.exists()
        content = analysis_file.read_text()
        assert "Project Analysis" in content
        assert "src/main.py" in content
        
        # Verify session persistence worked
        stats = orchestrator.get_infrastructure_stats()
        assert "session_manager" in stats
        assert "provider" in stats
        
        # Cleanup
        await orchestrator.cleanup()


if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v"])