#!/usr/bin/env python3
"""Simplified integration tests focusing on component integration."""

import tempfile
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock

# Add the songbird directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestComponentIntegration:
    """Test integration between major components."""
    
    @pytest.mark.asyncio
    async def test_orchestrator_agent_integration(self):
        """Test orchestrator properly integrates with agent."""
        from songbird.orchestrator import SongbirdOrchestrator
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock provider that returns simple responses
            mock_provider = AsyncMock()
            mock_provider.__class__.__name__ = "MockProvider"
            mock_provider.model = "test-model"
            
            # Mock response without tool calls
            from songbird.llm.types import ChatResponse
            mock_response = ChatResponse(
                content="I understand your request.",
                model="test-model",
                usage={"total_tokens": 50},
                tool_calls=None
            )
            mock_provider.chat_with_messages.return_value = mock_response
            
            orchestrator = SongbirdOrchestrator(
                provider=mock_provider,
                working_directory=temp_dir
            )
            
            # Should have all components integrated
            assert orchestrator.agent is not None
            assert orchestrator.tool_runner is not None
            assert orchestrator.session_manager is not None
            assert orchestrator.config_manager is not None
            
            # Should handle simple message
            result = await orchestrator.chat_single_message("Hello")
            assert isinstance(result, str)
            assert len(result) > 0
            
            await orchestrator.cleanup()
    
    def test_agent_tool_runner_integration(self):
        """Test agent properly integrates with tool runner."""
        from songbird.agent.agent_core import AgentCore
        from songbird.tools.tool_runner import ToolRunner
        
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_provider = Mock()
            tool_runner = ToolRunner(working_directory=temp_dir)
            
            agent = AgentCore(
                provider=mock_provider,
                tool_runner=tool_runner
            )
            
            # Agent should have tool runner
            assert agent.tool_runner is not None
            assert agent.tool_runner.working_directory == temp_dir
            
            # Tool runner should have available tools
            tools = tool_runner.get_available_tools()
            assert len(tools) > 0
    
    def test_tool_registry_integration(self):
        """Test tool registry integrates with tool runner."""
        from songbird.tools.tool_runner import ToolRunner
        from songbird.tools.tool_registry import get_tool_registry
        
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_runner = ToolRunner(working_directory=temp_dir)
            registry = get_tool_registry()
            
            # Should have same number of tools
            runner_tools = tool_runner.get_available_tools()
            registry_tools = registry.get_all_tools()
            
            assert len(runner_tools) == len(registry_tools)
            
            # Should have parallel safety info
            parallel_safe = registry.get_parallel_safe_tools()
            assert isinstance(parallel_safe, list)
    
    @pytest.mark.asyncio
    async def test_session_manager_integration(self):
        """Test session manager integrates with orchestrator."""
        from songbird.orchestrator import SongbirdOrchestrator
        from songbird.memory.models import Message
        
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_provider = AsyncMock()
            mock_provider.__class__.__name__ = "MockProvider"
            mock_provider.model = "test-model"
            
            orchestrator = SongbirdOrchestrator(
                provider=mock_provider,
                working_directory=temp_dir
            )
            
            # Should create session manager
            assert orchestrator.session_manager is not None
            
            # Should create sessions
            session = orchestrator.session_manager.create_session()
            assert session is not None
            
            # Should handle message persistence
            message = Message(role="user", content="Test message")
            orchestrator.session_manager.append_message(session.id, message)
            
            # Should load session back
            loaded = orchestrator.session_manager.load_session(session.id)
            assert loaded is not None
            assert loaded.id == session.id
            
            await orchestrator.cleanup()
    
    def test_config_manager_integration(self):
        """Test config manager integrates with orchestrator."""
        from songbird.orchestrator import SongbirdOrchestrator
        
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_provider = Mock()
            mock_provider.__class__.__name__ = "MockProvider"
            mock_provider.model = "test-model"
            
            orchestrator = SongbirdOrchestrator(
                provider=mock_provider,
                working_directory=temp_dir
            )
            
            # Should have config manager
            assert orchestrator.config_manager is not None
            assert orchestrator.config is not None
            
            # Config should affect session manager settings
            assert orchestrator.session_manager.flush_interval == orchestrator.config.session.flush_interval
            assert orchestrator.session_manager.batch_size == orchestrator.config.session.batch_size


class TestToolExecution:
    """Test tool execution integration."""
    
    @pytest.mark.asyncio
    async def test_file_tool_execution(self):
        """Test file tools can be executed through tool runner."""
        from songbird.tools.tool_runner import ToolRunner
        
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_runner = ToolRunner(working_directory=temp_dir)
            
            # Test file creation
            result = await tool_runner.execute_tool("file_create", {
                "file_path": str(Path(temp_dir) / "test.txt"),
                "content": "Hello, World!"
            })
            
            assert result.get("success", True)
            
            # Verify file was created
            test_file = Path(temp_dir) / "test.txt"
            assert test_file.exists()
            assert test_file.read_text() == "Hello, World!"
            
            # Test file reading
            read_result = await tool_runner.execute_tool("file_read", {
                "file_path": str(test_file)
            })
            
            assert read_result.get("success", True)
            # Tool results are nested under 'result'
            assert "Hello, World!" in read_result.get("result", {}).get("content", "")
    
    @pytest.mark.asyncio
    async def test_search_tool_execution(self):
        """Test search tools work through tool runner."""
        from songbird.tools.tool_runner import ToolRunner
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            (Path(temp_dir) / "file1.py").write_text("print('hello')")
            (Path(temp_dir) / "file2.txt").write_text("world text")
            
            tool_runner = ToolRunner(working_directory=temp_dir)
            
            # Test file search
            result = await tool_runner.execute_tool("file_search", {
                "pattern": "*.py",
                "directory": temp_dir
            })
            
            assert result.get("success", True)
            # Check if matches were found in result
            matches = result.get("result", {}).get("matches", [])
            files = result.get("result", {}).get("files", [])
            total_found = len(matches) + len(files)
            assert total_found > 0
    
    @pytest.mark.asyncio
    async def test_ls_tool_execution(self):
        """Test ls tool works through tool runner."""
        from songbird.tools.tool_runner import ToolRunner
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test structure
            (Path(temp_dir) / "subdir").mkdir()
            (Path(temp_dir) / "test.txt").write_text("test")
            
            tool_runner = ToolRunner(working_directory=temp_dir)
            
            # Test directory listing
            result = await tool_runner.execute_tool("ls", {
                "path": temp_dir
            })
            
            assert result.get("success", True)
            # LS tool result structure has 'entries'
            ls_result = result.get("result", {})
            assert "entries" in ls_result
            assert ls_result.get("dir_count", 0) >= 1  # subdir
            assert ls_result.get("file_count", 0) >= 1  # test.txt


class TestProviderIntegration:
    """Test provider integration patterns."""
    
    def test_provider_adapter_capabilities(self):
        """Test provider adapter provides capabilities."""
        from songbird.llm.unified_interface import create_provider_adapter
        
        mock_provider = Mock()
        mock_provider.__class__.__name__ = "TestProvider"
        mock_provider.model = "test-model"
        
        adapter = create_provider_adapter(mock_provider)
        
        # Should provide capabilities
        capabilities = adapter.get_provider_capabilities()
        assert isinstance(capabilities, dict)
        assert "provider_name" in capabilities
        assert "model_name" in capabilities
        assert capabilities["model_name"] == "test-model"
    
    def test_tool_schema_conversion(self):
        """Test tool schemas can be converted for different providers."""
        from songbird.tools.tool_registry import get_tool_registry
        
        registry = get_tool_registry()
        
        # Should generate schemas for all supported providers
        providers = ["openai", "claude", "gemini", "ollama", "openrouter"]
        
        for provider in providers:
            schemas = registry.get_llm_schemas(provider)
            assert len(schemas) > 0
            
            # All schemas should have basic structure
            for schema in schemas:
                if provider == "gemini":
                    assert "name" in schema
                    assert "description" in schema
                else:
                    assert "type" in schema
                    assert "function" in schema


class TestErrorResilience:
    """Test error handling and resilience."""
    
    @pytest.mark.asyncio
    async def test_tool_error_handling(self):
        """Test tool execution handles errors gracefully."""
        from songbird.tools.tool_runner import ToolRunner
        
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_runner = ToolRunner(working_directory=temp_dir)
            
            # Test reading non-existent file
            result = await tool_runner.execute_tool("file_read", {
                "file_path": "/nonexistent/file.txt"
            })
            
            # Should handle error gracefully - tool executor wraps errors
            assert isinstance(result, dict)
            # The outer result is success=True, but inner result has the error
            inner_result = result.get("result", {})
            assert inner_result.get("success") == False
            assert "error" in inner_result
    
    @pytest.mark.asyncio
    async def test_orchestrator_error_resilience(self):
        """Test orchestrator handles errors without crashing."""
        from songbird.orchestrator import SongbirdOrchestrator
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Provider that raises errors
            mock_provider = AsyncMock()
            mock_provider.__class__.__name__ = "ErrorProvider"
            mock_provider.model = "test-model"
            mock_provider.chat_with_messages.side_effect = Exception("Test error")
            
            orchestrator = SongbirdOrchestrator(
                provider=mock_provider,
                working_directory=temp_dir
            )
            
            # Should handle provider errors gracefully
            result = await orchestrator.chat_single_message("Test message")
            assert isinstance(result, str)
            assert "error" in result.lower()
            
            # Should still be able to cleanup
            await orchestrator.cleanup()


@pytest.mark.asyncio
async def test_infrastructure_integration():
    """Test all infrastructure components work together."""
    from songbird.orchestrator import SongbirdOrchestrator
    
    with tempfile.TemporaryDirectory() as temp_dir:
        mock_provider = AsyncMock()
        mock_provider.__class__.__name__ = "InfraProvider"
        mock_provider.model = "test-model"
        
        # Create orchestrator with all infrastructure
        orchestrator = SongbirdOrchestrator(
            provider=mock_provider,
            working_directory=temp_dir
        )
        
        # Should have all infrastructure components
        assert orchestrator.config_manager is not None
        assert orchestrator.session_manager is not None
        assert orchestrator.provider_adapter is not None
        assert orchestrator.shutdown_handler is not None
        
        # Should provide comprehensive stats
        stats = orchestrator.get_infrastructure_stats()
        assert "session_manager" in stats
        assert "provider" in stats
        assert "config" in stats
        
        # Config should have all expected sections
        config = orchestrator.config
        assert hasattr(config, 'llm')
        assert hasattr(config, 'session') 
        assert hasattr(config, 'tools')
        assert hasattr(config, 'agent')
        assert hasattr(config, 'ui')
        
        # Session manager should use config values
        assert orchestrator.session_manager.flush_interval == config.session.flush_interval
        assert orchestrator.session_manager.batch_size == config.session.batch_size
        
        # Cleanup should work
        await orchestrator.cleanup()


if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v"])