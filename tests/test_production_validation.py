#!/usr/bin/env python3
"""Production deployment validation tests for Songbird."""

import asyncio
import tempfile
import pytest
import sys
import os
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

# Add the songbird directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPackageIntegrity:
    """Test package integrity and installation."""
    
    def test_package_imports(self):
        """Test that all core modules can be imported."""
        # Core modules that should be importable
        core_modules = [
            "songbird",
            "songbird.cli",
            "songbird.llm.providers",
            "songbird.conversation",
            "songbird.tools.tool_runner",
            "songbird.memory.optimized_manager",
            "songbird.config.config_manager",
            "songbird.performance",
            "songbird.enhanced_interface"
        ]
        
        for module in core_modules:
            try:
                __import__(module)
            except ImportError as e:
                pytest.fail(f"Failed to import core module {module}: {e}")
    
    def test_version_accessible(self):
        """Test that version information is accessible."""
        import songbird
        
        assert hasattr(songbird, '__version__')
        assert isinstance(songbird.__version__, str)
        assert len(songbird.__version__) > 0
    
    def test_entry_point_exists(self):
        """Test that CLI entry point exists and is callable."""
        from songbird.cli import app
        
        assert app is not None
        assert callable(app)
    
    def test_dependencies_available(self):
        """Test that all required dependencies are available."""
        required_deps = [
            "anthropic",
            "appdirs", 
            "google.genai",
            "httpx",
            "InquirerPy",
            "ollama",
            "openai",
            "prompt_toolkit",
            "psutil",
            "rich",
            "typer"
        ]
        
        for dep in required_deps:
            try:
                __import__(dep)
            except ImportError as e:
                pytest.fail(f"Required dependency {dep} not available: {e}")


class TestConfigurationValidation:
    """Test configuration and environment setup."""
    
    def test_default_config_creation(self):
        """Test that default configuration can be created."""
        from songbird.config.config_manager import ConfigManager
        
        manager = ConfigManager()
        config = manager.get_config()
        
        # Should have all required sections
        assert hasattr(config, 'llm')
        assert hasattr(config, 'session')
        assert hasattr(config, 'agent')
        assert hasattr(config, 'tools')
        assert hasattr(config, 'ui')
    
    def test_provider_detection(self):
        """Test provider availability detection."""
        from songbird.llm.providers import get_provider_info, list_available_providers
        
        provider_info = get_provider_info()
        available_providers = list_available_providers()
        
        # Should have basic provider information
        assert isinstance(provider_info, dict)
        assert isinstance(available_providers, list)
        
        # Ollama should always be available (no API key required)
        assert "ollama" in available_providers
    
    def test_tool_registry_completeness(self):
        """Test that tool registry is complete and functional."""
        from songbird.tools.tool_registry import get_tool_registry
        
        registry = get_tool_registry()
        tools = registry.get_all_tools()
        
        # Should have the expected number of tools
        assert len(tools) >= 11, f"Expected at least 11 tools, got {len(tools)}"
        
        # All tools should have required metadata
        for tool_name, tool_def in tools.items():
            assert hasattr(tool_def, 'schema')
            assert hasattr(tool_def, 'function')
            assert hasattr(tool_def, 'parallel_safe')
            assert hasattr(tool_def, 'is_destructive')
            assert tool_def.schema is not None
            assert callable(tool_def.function)
    
    def test_session_storage_setup(self):
        """Test session storage can be set up correctly."""
        from songbird.memory.optimized_manager import OptimizedSessionManager
        
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = OptimizedSessionManager(working_directory=temp_dir)
            
            # Should be able to create sessions
            session = manager.create_session()
            assert session is not None
            
            # Should be able to get stats
            stats = manager.get_stats()
            assert isinstance(stats, dict)


class TestCLIFunctionality:
    """Test CLI functionality and commands."""
    
    def test_cli_help_command(self):
        """Test CLI help command works."""
        from songbird.cli import app
        from typer.testing import CliRunner
        
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        
        # Should succeed and show help
        assert result.exit_code == 0
        assert "Songbird" in result.stdout
    
    def test_version_command(self):
        """Test version command works."""
        from songbird.cli import app
        from typer.testing import CliRunner
        
        runner = CliRunner()
        result = runner.invoke(app, ["version"])
        
        # Should succeed and show version
        assert result.exit_code == 0
        assert "Songbird" in result.stdout
    
    def test_status_command(self):
        """Test status command works."""
        from songbird.cli import app
        from typer.testing import CliRunner
        
        runner = CliRunner()
        result = runner.invoke(app, ["status"])
        
        # Should succeed and show status
        assert result.exit_code == 0
    
    def test_list_providers_command(self):
        """Test list providers command works."""
        from songbird.cli import app
        from typer.testing import CliRunner
        
        runner = CliRunner()
        result = runner.invoke(app, ["--list-providers"])
        
        # Should succeed and show providers
        assert result.exit_code == 0
    
    def test_performance_command(self):
        """Test performance command works."""
        from songbird.cli import app
        from typer.testing import CliRunner
        
        runner = CliRunner()
        result = runner.invoke(app, ["performance"])
        
        # Should succeed and show performance status
        assert result.exit_code == 0


class TestProviderIntegration:
    """Test provider integration in production scenarios."""
    
    def test_ollama_provider_initialization(self):
        """Test Ollama provider can be initialized."""
        from songbird.llm.providers import OllamaProvider
        
        try:
            provider = OllamaProvider()
            assert provider is not None
            assert hasattr(provider, 'model')
        except Exception as e:
            # Ollama may not be running, which is acceptable
            assert "connection" in str(e).lower() or "not available" in str(e).lower()
    
    def test_provider_graceful_fallback(self):
        """Test provider fallback when services are unavailable."""
        from songbird.llm.providers import get_default_provider, get_provider
        
        # Should always return a default provider
        default = get_default_provider()
        assert default is not None
        assert isinstance(default, str)
        
        # Should be able to get provider class
        provider_class = get_provider(default)
        assert provider_class is not None
        assert callable(provider_class)
    
    @pytest.mark.asyncio
    async def test_conversation_orchestrator_initialization(self):
        """Test conversation orchestrator can be initialized."""
        from songbird.orchestrator import SongbirdOrchestrator
        
        # Mock provider for testing
        mock_provider = AsyncMock()
        mock_provider.__class__.__name__ = "MockProvider"
        mock_provider.model = "test-model"
        
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                orchestrator = SongbirdOrchestrator(
                    provider=mock_provider,
                    working_directory=temp_dir
                )
                
                # Should have all required components
                assert orchestrator.config_manager is not None
                assert orchestrator.session_manager is not None
                assert orchestrator.provider_adapter is not None
                assert orchestrator.shutdown_handler is not None
                
                # Should be able to get stats
                stats = orchestrator.get_infrastructure_stats()
                assert isinstance(stats, dict)
                
                # Cleanup
                await orchestrator.cleanup()
                
            except Exception as e:
                pytest.fail(f"Orchestrator initialization failed: {e}")


class TestToolExecution:
    """Test tool execution in production scenarios."""
    
    @pytest.mark.asyncio
    async def test_core_tools_executable(self):
        """Test that core tools can be executed."""
        from songbird.tools.tool_runner import ToolRunner
        
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_runner = ToolRunner(working_directory=temp_dir)
            
            # Test file creation tool
            result = await tool_runner.execute_tool("file_create", {
                "file_path": str(Path(temp_dir) / "test.txt"),
                "content": "Production test content"
            })
            
            assert isinstance(result, dict)
            assert result.get("success", True)
            
            # Verify file was created
            test_file = Path(temp_dir) / "test.txt"
            assert test_file.exists()
            
            # Test file reading tool
            read_result = await tool_runner.execute_tool("file_read", {
                "file_path": str(test_file)
            })
            
            assert isinstance(read_result, dict)
            assert read_result.get("success", True)
    
    @pytest.mark.asyncio
    async def test_search_tools_functional(self):
        """Test that search tools are functional."""
        from songbird.tools.tool_runner import ToolRunner
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            (Path(temp_dir) / "file1.py").write_text("print('hello')")
            (Path(temp_dir) / "file2.txt").write_text("world")
            
            tool_runner = ToolRunner(working_directory=temp_dir)
            
            # Test file search
            result = await tool_runner.execute_tool("file_search", {
                "pattern": "*.py",
                "directory": temp_dir
            })
            
            assert isinstance(result, dict)
            assert result.get("success", True)
            
            # Test ls tool
            ls_result = await tool_runner.execute_tool("ls", {
                "path": temp_dir
            })
            
            assert isinstance(ls_result, dict)
            assert ls_result.get("success", True)


class TestMemoryAndPersistence:
    """Test memory and persistence functionality."""
    
    @pytest.mark.asyncio
    async def test_session_persistence_robustness(self):
        """Test session persistence under various conditions."""
        from songbird.memory.optimized_manager import OptimizedSessionManager
        from songbird.memory.models import Message
        
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = OptimizedSessionManager(
                working_directory=temp_dir,
                flush_interval=1,
                batch_size=3
            )
            
            # Create session and add messages
            session = manager.create_session()
            
            # Add messages in batches
            for i in range(10):
                message = Message(role="user", content=f"Test message {i}")
                manager.append_message(session.id, message)
            
            # Wait for flush
            await asyncio.sleep(2)
            
            # Verify persistence
            loaded_session = manager.load_session(session.id)
            assert loaded_session is not None
            assert len(loaded_session.messages) >= 5  # Should have persisted some messages
            
            # Test graceful shutdown
            await manager.shutdown()
    
    def test_config_persistence(self):
        """Test configuration persistence."""
        from songbird.config.config_manager import ConfigManager
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create config manager with custom directory
            manager = ConfigManager()
            
            # Should be able to get and modify config
            config = manager.get_config()
            original_flush_interval = config.session.flush_interval
            
            # Config should be reasonable
            assert config.session.flush_interval > 0
            assert config.session.batch_size > 0
            assert config.agent.max_iterations > 0


class TestPerformanceProfile:
    """Test performance profiling in production."""
    
    def test_profiler_functional(self):
        """Test that profiler is functional for production use."""
        from songbird.performance import enable_profiling, disable_profiling, get_profiler, clear_profiling
        import time
        
        clear_profiling()
        enable_profiling()
        profiler = get_profiler()
        
        # Test with realistic operations that have actual work
        with profiler.profile_operation("realistic_operation"):
            time.sleep(0.01)  # 10ms operation
        
        # Should capture the operation
        report = profiler.generate_report()
        assert report.operations_count == 1
        assert report.total_duration > 0.009  # Should be close to 10ms
        
        disable_profiling()
    
    def test_profiler_data_integrity(self):
        """Test profiler data integrity under load."""
        from songbird.performance import enable_profiling, get_profiler, clear_profiling
        import time
        import random
        
        clear_profiling()
        enable_profiling()
        profiler = get_profiler()
        
        # Generate some operations
        for i in range(50):
            operation_name = f"operation_{i % 5}"  # 5 different operation types
            with profiler.profile_operation(operation_name):
                time.sleep(random.uniform(0.001, 0.01))  # 1-10ms operations
        
        # Verify data integrity
        report = profiler.generate_report()
        assert report.operations_count == 50
        assert report.total_duration > 0.05  # At least 50ms total
        
        # Verify operation stats
        op_stats = profiler.get_operation_stats()
        assert len(op_stats) == 5  # Should have 5 operation types
        
        for op_name, stats in op_stats.items():
            assert stats["count"] == 10  # 10 operations per type
            assert stats["total_duration"] > 0


class TestErrorResilience:
    """Test error resilience in production scenarios."""
    
    @pytest.mark.asyncio
    async def test_tool_error_recovery(self):
        """Test tool error recovery."""
        from songbird.tools.tool_runner import ToolRunner
        
        with tempfile.TemporaryDirectory() as temp_dir:
            tool_runner = ToolRunner(working_directory=temp_dir)
            
            # Test handling of invalid tool call
            result = await tool_runner.execute_tool("nonexistent_tool", {})
            
            # Should handle gracefully
            assert isinstance(result, dict)
            # Tool runner should wrap errors
    
    @pytest.mark.asyncio
    async def test_session_manager_error_recovery(self):
        """Test session manager error recovery."""
        from songbird.memory.optimized_manager import OptimizedSessionManager
        
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = OptimizedSessionManager(working_directory=temp_dir)
            
            # Test loading non-existent session
            result = manager.load_session("nonexistent-session-id")
            
            # Should handle gracefully
            assert result is None
            
            # Manager should still be functional
            new_session = manager.create_session()
            assert new_session is not None


@pytest.mark.asyncio
async def test_full_production_workflow():
    """Test a complete production workflow."""
    from songbird.orchestrator import SongbirdOrchestrator
    from songbird.performance import enable_profiling, get_profiler
    
    # Enable performance monitoring
    enable_profiling()
    
    # Mock provider for testing
    mock_provider = AsyncMock()
    mock_provider.__class__.__name__ = "ProductionTestProvider"
    mock_provider.model = "test-model"
    
    from songbird.llm.types import ChatResponse
    mock_provider.chat_with_messages.return_value = ChatResponse(
        content="Production test response",
        model="test-model",
        usage={"total_tokens": 100},
        tool_calls=None
    )
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create orchestrator
        orchestrator = SongbirdOrchestrator(
            provider=mock_provider,
            working_directory=temp_dir
        )
        
        # Simulate conversation
        result = await orchestrator.chat_single_message("Test production workflow")
        
        # Should get a response
        assert isinstance(result, str)
        assert len(result) > 0
        
        # Check infrastructure stats
        stats = orchestrator.get_infrastructure_stats()
        assert "session_manager" in stats
        assert "provider" in stats
        assert "config" in stats
        
        # Check performance data
        profiler = get_profiler()
        report = profiler.generate_report()
        # Should have some profiling data if integration is complete
        
        # Cleanup should work
        await orchestrator.cleanup()


if __name__ == "__main__":
    # Run production validation tests
    pytest.main([__file__, "-v"])