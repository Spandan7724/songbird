#!/usr/bin/env python3
"""Tests for enhanced CLI interface and user experience improvements."""

import tempfile
import pytest
import sys
from pathlib import Path
from io import StringIO
from unittest.mock import Mock, patch, MagicMock

# Add the songbird directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestEnhancedCLIInterface:
    """Test enhanced CLI interface functionality."""
    
    def test_enhanced_cli_initialization(self):
        """Test EnhancedCLI class initialization."""
        from songbird.enhanced_interface import EnhancedCLI
        
        cli = EnhancedCLI()
        assert cli.console is not None
        assert cli.performance_enabled == False
    
    def test_banner_creation(self):
        """Test banner creation functionality."""
        from songbird.enhanced_interface import create_banner
        from rich.panel import Panel
        
        banner = create_banner()
        assert banner is not None
        assert isinstance(banner, Panel)
    
    def test_provider_status_table_creation(self):
        """Test provider status table creation."""
        from songbird.enhanced_interface import create_provider_status_table
        from rich.table import Table
        
        table = create_provider_status_table()
        assert table is not None
        assert isinstance(table, Table)
    
    def test_version_info_creation(self):
        """Test version information creation."""
        from songbird.enhanced_interface import create_version_info
        
        version_info = create_version_info()
        assert "Songbird AI" in version_info
        assert "Features:" in version_info
        assert "Architecture:" in version_info
    
    def test_enhanced_help_creation(self):
        """Test enhanced help text creation."""
        from songbird.enhanced_interface import create_enhanced_help
        
        help_text = create_enhanced_help()
        assert "Songbird AI" in help_text
        assert "Basic Usage:" in help_text
        assert "Available Providers:" in help_text
        assert "In-Chat Commands:" in help_text


class TestCLIUserExperience:
    """Test CLI user experience improvements."""
    
    def test_startup_banner_display(self):
        """Test startup banner display."""
        from songbird.enhanced_interface import EnhancedCLI
        
        cli = EnhancedCLI()
        
        # Should not raise any exceptions
        with patch.object(cli.console, 'print') as mock_print:
            cli.display_startup_banner()
            
            # Should have printed something
            assert mock_print.called
    
    def test_startup_tips_display(self):
        """Test startup tips display."""
        from songbird.enhanced_interface import EnhancedCLI
        
        cli = EnhancedCLI()
        
        with patch.object(cli.console, 'print') as mock_print:
            cli.display_startup_tips()
            
            # Should display a tip
            assert mock_print.called
    
    def test_session_selection_no_sessions(self):
        """Test session selection when no sessions exist."""
        from songbird.enhanced_interface import display_session_menu
        from rich.console import Console
        
        console = Console()
        with patch.object(console, 'print') as mock_print:
            result = display_session_menu([], console)
            
            assert result is None
            assert mock_print.called
    
    def test_session_selection_with_sessions(self):
        """Test session selection with available sessions."""
        from songbird.enhanced_interface import display_session_menu
        from songbird.memory.models import Session, Message
        from rich.console import Console
        from datetime import datetime
        
        # Create mock sessions
        sessions = [
            Session(
                id="session1",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                summary="Test session 1",
                messages=[]
            ),
            Session(
                id="session2", 
                created_at=datetime.now(),
                updated_at=datetime.now(),
                summary="Test session 2",
                messages=[]
            )
        ]
        
        console = Console()
        
        # Mock user input to select session 1
        with patch('rich.prompt.Prompt.ask', return_value='1'), \
             patch.object(console, 'print'):
            
            result = display_session_menu(sessions, console)
            assert result == sessions[0]
        
        # Mock user input to quit
        with patch('rich.prompt.Prompt.ask', return_value='q'), \
             patch.object(console, 'print'):
            
            result = display_session_menu(sessions, console)
            assert result is None
    
    def test_provider_selection_specified(self):
        """Test provider selection with specified provider."""
        from songbird.enhanced_interface import EnhancedCLI
        
        cli = EnhancedCLI()
        
        # Mock successful provider initialization
        with patch('songbird.enhanced_interface.get_provider') as mock_get_provider:
            mock_provider_class = Mock()
            mock_provider = Mock()
            mock_provider_class.return_value = mock_provider
            mock_get_provider.return_value = mock_provider_class
            
            result = cli.handle_provider_selection("gemini")
            
            assert result == mock_provider
            mock_get_provider.assert_called_once_with("gemini")
    
    def test_provider_selection_auto(self):
        """Test automatic provider selection."""
        from songbird.enhanced_interface import EnhancedCLI
        
        cli = EnhancedCLI()
        
        # Mock automatic provider selection
        with patch('songbird.enhanced_interface.get_default_provider', return_value='ollama'), \
             patch('songbird.enhanced_interface.get_provider') as mock_get_provider:
            
            mock_provider_class = Mock()
            mock_provider = Mock()
            mock_provider_class.return_value = mock_provider
            mock_get_provider.return_value = mock_provider_class
            
            result = cli.handle_provider_selection(None)
            
            assert result == mock_provider


class TestCLIErrorHandling:
    """Test enhanced error handling in CLI."""
    
    def test_error_display_with_suggestions(self):
        """Test error display with suggestions."""
        from songbird.enhanced_interface import EnhancedCLI
        
        cli = EnhancedCLI()
        
        error = Exception("Test error")
        suggestions = ["Try this", "Or try that"]
        
        with patch.object(cli.console, 'print') as mock_print:
            cli.display_error_with_suggestions(error, suggestions)
            
            # Should have printed error and suggestions
            assert mock_print.called
    
    def test_success_message_display(self):
        """Test success message display."""
        from songbird.enhanced_interface import EnhancedCLI
        
        cli = EnhancedCLI()
        
        with patch.object(cli.console, 'print') as mock_print:
            cli.display_success_message("Operation successful", "Details here")
            
            assert mock_print.called
    
    def test_dangerous_operation_confirmation(self):
        """Test dangerous operation confirmation."""
        from songbird.enhanced_interface import EnhancedCLI
        
        cli = EnhancedCLI()
        
        # Test confirmation accepted
        with patch('rich.prompt.Confirm.ask', return_value=True), \
             patch.object(cli.console, 'print'):
            
            result = cli.confirm_dangerous_operation("Delete all files")
            assert result == True
        
        # Test confirmation rejected
        with patch('rich.prompt.Confirm.ask', return_value=False), \
             patch.object(cli.console, 'print'):
            
            result = cli.confirm_dangerous_operation("Delete all files")
            assert result == False


class TestPerformanceMonitoring:
    """Test performance monitoring integration in CLI."""
    
    def test_performance_monitoring_enable(self):
        """Test enabling performance monitoring."""
        from songbird.enhanced_interface import EnhancedCLI
        
        cli = EnhancedCLI()
        
        with patch('songbird.enhanced_interface.enable_profiling') as mock_enable:
            cli.enable_performance_monitoring(True)
            
            assert cli.performance_enabled == True
            mock_enable.assert_called_once()
    
    def test_performance_summary_display(self):
        """Test performance summary display."""
        from songbird.enhanced_interface import display_performance_summary
        from rich.console import Console
        
        console = Console()
        
        # Mock profiler with no data
        with patch('songbird.enhanced_interface.get_profiler') as mock_profiler:
            mock_report = Mock()
            mock_report.operations_count = 0
            mock_profiler.return_value.generate_report.return_value = mock_report
            
            # Should handle empty report gracefully
            display_performance_summary(console)
        
        # Mock profiler with data
        with patch('songbird.enhanced_interface.get_profiler') as mock_profiler:
            mock_report = Mock()
            mock_report.operations_count = 5
            mock_report.total_duration = 1.23
            mock_report.avg_duration = 0.246
            mock_profiler.return_value.generate_report.return_value = mock_report
            
            with patch.object(console, 'print') as mock_print:
                display_performance_summary(console)
                
                # Should display performance info
                assert mock_print.called


class TestCLICommandIntegration:
    """Test integration with CLI commands."""
    
    def test_enhanced_help_command(self):
        """Test enhanced help command integration."""
        from songbird.enhanced_interface import display_enhanced_help
        from rich.console import Console
        
        console = Console()
        
        with patch.object(console, 'print') as mock_print:
            display_enhanced_help(console)
            
            # Should display help information
            assert mock_print.called
    
    def test_version_command_integration(self):
        """Test version command integration."""
        from songbird.enhanced_interface import display_version_info
        from rich.console import Console
        
        console = Console()
        
        with patch.object(console, 'print') as mock_print:
            display_version_info(console)
            
            # Should display version information
            assert mock_print.called
    
    def test_goodbye_message_display(self):
        """Test goodbye message display."""
        from songbird.enhanced_interface import EnhancedCLI
        
        cli = EnhancedCLI()
        
        with patch.object(cli.console, 'print') as mock_print:
            cli.display_goodbye_message()
            
            # Should display goodbye message
            assert mock_print.called


class TestCLIAccessibility:
    """Test CLI accessibility and usability features."""
    
    def test_session_handling_continue_recent(self):
        """Test session handling for continuing recent session."""
        from songbird.enhanced_interface import EnhancedCLI
        
        cli = EnhancedCLI()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock session manager
            with patch('songbird.enhanced_interface.OptimizedSessionManager') as mock_manager:
                mock_session = Mock()
                mock_session.created_at.strftime.return_value = "12/25 10:30"
                
                mock_manager.return_value.list_sessions.return_value = [mock_session]
                mock_manager.return_value.load_session.return_value = mock_session
                
                result = cli.handle_session_selection(temp_dir, continue_recent=True)
                
                assert result == mock_session
    
    def test_session_handling_no_sessions(self):
        """Test session handling when no sessions exist."""
        from songbird.enhanced_interface import EnhancedCLI
        
        cli = EnhancedCLI()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('songbird.enhanced_interface.OptimizedSessionManager') as mock_manager:
                mock_manager.return_value.list_sessions.return_value = []
                
                result = cli.handle_session_selection(temp_dir, continue_recent=True)
                
                assert result is None


@pytest.mark.asyncio
async def test_enhanced_cli_integration():
    """Test enhanced CLI integration with core functionality."""
    from songbird.enhanced_interface import EnhancedCLI
    
    cli = EnhancedCLI()
    
    # Test full CLI workflow components
    assert cli.console is not None
    
    # Test performance monitoring integration
    cli.enable_performance_monitoring(False)
    assert cli.performance_enabled == False
    
    # Test provider selection error handling
    with patch('songbird.enhanced_interface.get_provider', side_effect=Exception("Provider error")):
        result = cli.handle_provider_selection("invalid_provider")
        assert result is None


if __name__ == "__main__":
    # Run enhanced CLI tests
    pytest.main([__file__, "-v"])