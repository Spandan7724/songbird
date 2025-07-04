#!/usr/bin/env python3
"""
Comprehensive test suite for Songbird CLI functionality.

Tests all CLI commands, options, provider selection, session management,
error handling, and integration with the current v0.1.7 architecture.
"""

import pytest
import subprocess
import sys
import os
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from typer.testing import CliRunner
import typer

# Import the CLI app and related modules
from songbird.cli import app, main, version, help as help_command, default
from songbird import __version__


class TestBasicCLICommands:
    """Test basic CLI commands that should work without external dependencies."""
    
    def setup_method(self):
        """Set up test runner."""
        self.runner = CliRunner()
    
    def test_version_command(self):
        """Test the version command."""
        result = self.runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "Songbird" in result.stdout
        assert __version__ in result.stdout
    
    def test_help_command(self):
        """Test the help command."""
        result = self.runner.invoke(app, ["help"])
        assert result.exit_code == 0
        assert "Songbird" in result.stdout
        assert "commands" in result.stdout.lower()
    
    def test_main_help_flag(self):
        """Test the main --help flag."""
        result = self.runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Songbird" in result.stdout
        assert "provider" in result.stdout.lower()
    
    def test_no_args_shows_help(self):
        """Test that running with no args shows help (no_args_is_help=False but should show usage)."""
        result = self.runner.invoke(app, [])
        # Should not error out, but may start interactive mode
        # In test environment, this should handle gracefully
        assert result.exit_code == 0 or result.exit_code == 1  # Allow for different behaviors


class TestProviderOptions:
    """Test provider-related CLI options."""
    
    def setup_method(self):
        self.runner = CliRunner()
    
    @patch('songbird.cli.get_provider_info')
    def test_list_providers_flag(self, mock_provider_info):
        """Test --list-providers flag."""
        mock_provider_info.return_value = {
            "openai": {"ready": True, "models": ["gpt-4o"], "description": "OpenAI GPT models"},
            "claude": {"ready": False, "models": [], "description": "Anthropic Claude models"},
            "gemini": {"ready": True, "models": ["gemini-2.0-flash"], "description": "Google Gemini models"},
            "ollama": {"ready": True, "models": ["qwen2.5-coder:7b"], "description": "Local Ollama models"}
        }
        
        result = self.runner.invoke(app, ["--list-providers"])
        assert result.exit_code == 0
        assert "openai" in result.stdout
        assert "claude" in result.stdout
        assert "gemini" in result.stdout
        assert "ollama" in result.stdout
    
    @patch('songbird.cli.get_default_provider_name')
    @patch('songbird.cli.chat')
    def test_provider_selection(self, mock_chat, mock_get_default):
        """Test --provider option."""
        mock_get_default.return_value = "ollama"
        mock_chat.return_value = None
        
        result = self.runner.invoke(app, ["--provider", "openai"])
        # Should call chat with provider specified
        mock_chat.assert_called_once()
        call_args = mock_chat.call_args[1]
        assert call_args["provider"] == "openai"
    
    @patch('songbird.cli.get_default_provider_name')
    @patch('songbird.cli.chat')
    def test_provider_short_flag(self, mock_chat, mock_get_default):
        """Test -p short flag for provider."""
        mock_get_default.return_value = "ollama"
        mock_chat.return_value = None
        
        result = self.runner.invoke(app, ["-p", "gemini"])
        mock_chat.assert_called_once()
        call_args = mock_chat.call_args[1]
        assert call_args["provider"] == "gemini"
    
    @patch('songbird.cli.chat')
    def test_provider_url_option(self, mock_chat):
        """Test --provider-url hidden option."""
        mock_chat.return_value = None
        
        result = self.runner.invoke(app, ["--provider-url", "https://api.custom.com/v1"])
        mock_chat.assert_called_once()
        call_args = mock_chat.call_args[1]
        assert call_args["provider_url"] == "https://api.custom.com/v1"


class TestSessionManagement:
    """Test session management CLI options."""
    
    def setup_method(self):
        self.runner = CliRunner()
    
    @patch('songbird.cli.chat')
    def test_continue_flag(self, mock_chat):
        """Test --continue flag."""
        mock_chat.return_value = None
        
        result = self.runner.invoke(app, ["--continue"])
        mock_chat.assert_called_once()
        call_args = mock_chat.call_args[1]
        assert call_args["continue_session"] is True
    
    @patch('songbird.cli.chat')
    def test_continue_short_flag(self, mock_chat):
        """Test -c short flag for continue."""
        mock_chat.return_value = None
        
        result = self.runner.invoke(app, ["-c"])
        mock_chat.assert_called_once()
        call_args = mock_chat.call_args[1]
        assert call_args["continue_session"] is True
    
    @patch('songbird.cli.chat')
    def test_resume_flag(self, mock_chat):
        """Test --resume flag."""
        mock_chat.return_value = None
        
        result = self.runner.invoke(app, ["--resume"])
        mock_chat.assert_called_once()
        call_args = mock_chat.call_args[1]
        assert call_args["resume_session"] is True
    
    @patch('songbird.cli.chat')
    def test_resume_short_flag(self, mock_chat):
        """Test -r short flag for resume."""
        mock_chat.return_value = None
        
        result = self.runner.invoke(app, ["-r"])
        mock_chat.assert_called_once()
        call_args = mock_chat.call_args[1]
        assert call_args["resume_session"] is True


class TestDefaultCommand:
    """Test the default command for setting provider preferences."""
    
    def setup_method(self):
        self.runner = CliRunner()
    
    @patch('songbird.cli.set_default_provider_and_model')
    def test_default_command_with_provider(self, mock_set_default):
        """Test default command with provider argument."""
        result = self.runner.invoke(app, ["default", "openai"])
        assert result.exit_code == 0
        mock_set_default.assert_called_once_with("openai", None)
    
    @patch('songbird.cli.set_default_provider_and_model')
    def test_default_command_with_provider_and_model(self, mock_set_default):
        """Test default command with both provider and model."""
        result = self.runner.invoke(app, ["default", "openai", "gpt-4o-mini"])
        assert result.exit_code == 0
        mock_set_default.assert_called_once_with("openai", "gpt-4o-mini")
    
    @patch('asyncio.run')
    @patch('songbird.cli.interactive_set_default')
    def test_default_command_interactive(self, mock_interactive, mock_asyncio_run):
        """Test default command without arguments (interactive mode)."""
        mock_interactive.return_value = None
        result = self.runner.invoke(app, ["default"])
        assert result.exit_code == 0
        mock_asyncio_run.assert_called_once()
    
    @patch('songbird.cli.interactive_set_default')
    def test_set_default_flag(self, mock_interactive):
        """Test --default flag in main command.""" 
        result = self.runner.invoke(app, ["--default"])
        # Should call interactive set default
        assert result.exit_code == 0


class TestCLIIntegration:
    """Test CLI integration with core components."""
    
    def setup_method(self):
        self.runner = CliRunner()
    
    @patch('songbird.cli.SongbirdOrchestrator')
    @patch('songbird.cli.get_litellm_provider')
    @patch('songbird.cli.OptimizedSessionManager')
    @patch('songbird.cli._chat_loop')
    def test_chat_integration(self, mock_chat_loop, mock_session_manager, 
                             mock_get_provider, mock_orchestrator):
        """Test that chat function properly integrates components."""
        # Setup mocks
        mock_provider = Mock()
        mock_provider.model = "test-model"
        mock_get_provider.return_value = mock_provider
        
        mock_session_mgr = Mock()
        mock_session = Mock()
        mock_session.provider_config = None
        mock_session_mgr.create_session.return_value = mock_session
        mock_session_manager.return_value = mock_session_mgr
        
        mock_orch = Mock()
        mock_orchestrator.return_value = mock_orch
        
        # Mock the async chat loop to avoid actual execution
        mock_chat_loop.return_value = None
        
        # Mock the UI layer and other dependencies
        with patch('songbird.cli.UILayer'), \
             patch('songbird.cli.load_all_commands'), \
             patch('songbird.cli.CommandInputHandler'), \
             patch('songbird.cli.MessageHistoryManager'), \
             patch('songbird.cli.get_default_provider_name', return_value="ollama"), \
             patch('asyncio.new_event_loop'), \
             patch('asyncio.set_event_loop'), \
             patch('songbird.cli.show_banner'):
            
            result = self.runner.invoke(app, ["--provider", "ollama"])
            
            # Verify components were created
            mock_session_manager.assert_called_once()
            mock_get_provider.assert_called_once()
            mock_orchestrator.assert_called_once()


class TestEnvironmentHandling:
    """Test CLI behavior with different environment configurations."""
    
    def setup_method(self):
        self.runner = CliRunner()
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False)
    @patch('songbird.cli.get_provider_info')
    def test_provider_with_api_key(self, mock_provider_info):
        """Test provider selection when API key is available."""
        mock_provider_info.return_value = {
            "openai": {"ready": True, "models": ["gpt-4o"], "description": "OpenAI GPT models"}
        }
        
        result = self.runner.invoke(app, ["--list-providers"])
        assert result.exit_code == 0
        assert "openai" in result.stdout
    
    @patch.dict(os.environ, {}, clear=True)
    @patch('songbird.cli.get_provider_info')
    def test_provider_without_api_keys(self, mock_provider_info):
        """Test provider selection when no API keys are available."""
        mock_provider_info.return_value = {
            "openai": {"ready": False, "models": [], "description": "OpenAI GPT models"},
            "ollama": {"ready": True, "models": ["qwen2.5-coder:7b"], "description": "Local Ollama models"}
        }
        
        result = self.runner.invoke(app, ["--list-providers"])
        assert result.exit_code == 0
        assert "ollama" in result.stdout


class TestErrorHandling:
    """Test CLI error handling and user guidance."""
    
    def setup_method(self):
        self.runner = CliRunner()
    
    @patch('songbird.cli.get_litellm_provider')
    @patch('songbird.cli.OptimizedSessionManager')
    def test_provider_initialization_error(self, mock_session_manager, mock_get_provider):
        """Test handling of provider initialization errors."""
        mock_get_provider.side_effect = Exception("Provider not available")
        mock_session_mgr = Mock()
        mock_session = Mock()
        mock_session.provider_config = None
        mock_session_mgr.create_session.return_value = mock_session
        mock_session_manager.return_value = mock_session_mgr
        
        with patch('songbird.cli.show_banner'), \
             patch('songbird.cli.get_default_provider_name', return_value="openai"):
            
            result = self.runner.invoke(app, ["--provider", "openai"])
            # Should handle error gracefully and show guidance
            assert result.exit_code == 0  # CLI shouldn't crash
            assert "Error" in result.stdout or "error" in result.stdout
    
    @patch('songbird.cli.get_provider_info')
    def test_invalid_provider_name(self, mock_provider_info):
        """Test handling of invalid provider names."""
        mock_provider_info.return_value = {
            "openai": {"ready": True, "models": ["gpt-4o"], "description": "OpenAI"}
        }
        
        # This should still work as the CLI will attempt to use the provider
        # and error handling happens at the provider level
        with patch('songbird.cli.chat'):
            result = self.runner.invoke(app, ["--provider", "nonexistent"])
            assert result.exit_code == 0  # CLI accepts it, provider validation happens later


class TestSubprocessExecution:
    """Test CLI execution as subprocess (integration tests)."""
    
    def test_version_subprocess(self):
        """Test version command via subprocess."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "songbird.cli", "version"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=Path(__file__).parent.parent
            )
            assert result.returncode == 0
            assert "Songbird" in result.stdout
            assert __version__ in result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            pytest.skip(f"Subprocess test skipped: {e}")
    
    def test_help_subprocess(self):
        """Test help command via subprocess."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "songbird.cli", "help"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=Path(__file__).parent.parent
            )
            assert result.returncode == 0
            assert "Songbird" in result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            pytest.skip(f"Subprocess test skipped: {e}")
    
    def test_list_providers_subprocess(self):
        """Test --list-providers via subprocess."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "songbird.cli", "--list-providers"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=Path(__file__).parent.parent
            )
            assert result.returncode == 0
            # Should show available providers
            assert any(provider in result.stdout.lower() for provider in ["openai", "claude", "gemini", "ollama"])
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            pytest.skip(f"Subprocess test skipped: {e}")


class TestSessionConfiguration:
    """Test session and configuration management in CLI."""
    
    def setup_method(self):
        self.runner = CliRunner()
    
    @patch('songbird.cli.OptimizedSessionManager')
    @patch('songbird.cli.display_session_selector')
    def test_session_resume_with_sessions(self, mock_selector, mock_session_manager):
        """Test resuming sessions when sessions exist."""
        # Create mock session manager
        mock_mgr = Mock()
        mock_session_manager.return_value = mock_mgr
        
        # Create mock sessions
        mock_session = Mock()
        mock_session.id = "test-session-1"
        mock_session.summary = "Test session"
        mock_session.provider_config = {"provider": "openai", "model": "gpt-4o"}
        mock_mgr.list_sessions.return_value = [mock_session]
        mock_mgr.load_session.return_value = mock_session
        
        # Mock session selector to return the session
        mock_selector.return_value = mock_session
        
        with patch('songbird.cli.replay_conversation'), \
             patch('songbird.cli.format_time_ago', return_value="1h ago"), \
             patch('songbird.cli.get_default_provider_name', return_value="ollama"), \
             patch('songbird.cli.chat') as mock_chat:
            
            result = self.runner.invoke(app, ["--resume"])
            
            # Verify session selector was called
            mock_selector.assert_called_once()
            mock_chat.assert_called_once()
    
    @patch('songbird.cli.OptimizedSessionManager')
    def test_session_continue_no_sessions(self, mock_session_manager):
        """Test continuing when no sessions exist."""
        mock_mgr = Mock()
        mock_mgr.get_latest_session.return_value = None
        mock_session_manager.return_value = mock_mgr
        
        with patch('songbird.cli.chat') as mock_chat:
            result = self.runner.invoke(app, ["--continue"])
            mock_chat.assert_called_once()


class TestConfigurationPersistence:
    """Test configuration and default persistence."""
    
    def setup_method(self):
        self.runner = CliRunner()
    
    @patch('songbird.cli.get_config_manager')
    def test_config_loading(self, mock_get_config_manager):
        """Test that configuration is properly loaded."""
        # Mock config manager
        mock_config_manager = Mock()
        mock_config = Mock()
        mock_config.llm.default_provider = "gemini"
        mock_config.llm.default_models = {"gemini": "gemini-2.0-flash"}
        mock_config_manager.get_config.return_value = mock_config
        mock_get_config_manager.return_value = mock_config_manager
        
        with patch('songbird.cli.chat'), \
             patch('songbird.cli.OptimizedSessionManager'):
            
            result = self.runner.invoke(app, [])
            # Should use config values
            assert result.exit_code == 0
    
    @patch('pathlib.Path.write_text')
    @patch('pathlib.Path.mkdir')
    @patch('pathlib.Path.exists', return_value=True)
    def test_default_provider_persistence(self, mock_exists, mock_mkdir, mock_write):
        """Test that default provider settings are persisted."""
        with patch('songbird.cli.set_default_provider_and_model') as mock_set_default:
            result = self.runner.invoke(app, ["default", "claude", "claude-3-5-sonnet"])
            mock_set_default.assert_called_once_with("claude", "claude-3-5-sonnet")


class TestAdvancedFeatures:
    """Test advanced CLI features and edge cases."""
    
    def setup_method(self):
        self.runner = CliRunner()
    
    def test_combined_flags(self):
        """Test combining multiple CLI flags."""
        with patch('songbird.cli.chat') as mock_chat:
            result = self.runner.invoke(app, [
                "--provider", "gemini",
                "--provider-url", "https://custom.api.com",
                "--continue"
            ])
            
            mock_chat.assert_called_once()
            call_args = mock_chat.call_args[1]
            assert call_args["provider"] == "gemini"
            assert call_args["provider_url"] == "https://custom.api.com"
            assert call_args["continue_session"] is True
    
    @patch('songbird.cli.get_provider_info')
    def test_provider_status_display(self, mock_provider_info):
        """Test provider status display in --list-providers."""
        mock_provider_info.return_value = {
            "openai": {"ready": True, "models": ["gpt-4o", "gpt-4o-mini"], "description": "OpenAI models"},
            "claude": {"ready": False, "models": [], "description": "Anthropic Claude (API key missing)"},
            "ollama": {"ready": True, "models": ["qwen2.5-coder:7b"], "description": "Local Ollama"}
        }
        
        result = self.runner.invoke(app, ["--list-providers"])
        assert result.exit_code == 0
        
        # Should show provider status
        output = result.stdout.lower()
        assert "openai" in output
        assert "claude" in output
        assert "ollama" in output


class TestCLIRobustness:
    """Test CLI robustness and error recovery."""
    
    def setup_method(self):
        self.runner = CliRunner()
    
    def test_keyboard_interrupt_handling(self):
        """Test graceful handling of keyboard interrupts."""
        with patch('songbird.cli.chat') as mock_chat:
            mock_chat.side_effect = KeyboardInterrupt()
            
            result = self.runner.invoke(app, [])
            # Should handle KeyboardInterrupt gracefully
            assert result.exit_code == 0 or result.exit_code == 1
    
    def test_empty_input_handling(self):
        """Test handling of empty or whitespace input."""
        result = self.runner.invoke(app, [""])
        # Should handle empty commands gracefully
        assert result.exit_code == 0 or result.exit_code == 2  # Click may return 2 for usage errors
    
    @patch('songbird.cli.show_banner')
    def test_banner_display(self, mock_banner):
        """Test that banner is displayed when starting chat."""
        with patch('songbird.cli.chat'):
            result = self.runner.invoke(app, [])
            # Banner should be shown when starting chat
            mock_banner.assert_called_once()


if __name__ == "__main__":
    # Run the tests with pytest
    pytest.main([__file__, "-v"])
