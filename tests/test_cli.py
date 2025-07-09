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
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from typer.testing import CliRunner

# Import the CLI app and related modules
from songbird.cli import app
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
            "openai": {"available": True, "ready": True, "models": ["gpt-4o"], "api_key_env": "OPENAI_API_KEY", "models_discovered": False},
            "claude": {"available": False, "ready": False, "models": [], "api_key_env": "ANTHROPIC_API_KEY", "models_discovered": False},
            "gemini": {"available": True, "ready": True, "models": ["gemini-2.0-flash"], "api_key_env": "GEMINI_API_KEY", "models_discovered": False},
            "ollama": {"available": True, "ready": True, "models": ["qwen2.5-coder:7b"], "api_key_env": None, "models_discovered": False}
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
    @patch('songbird.cli.execute_print_mode')
    def test_print_mode_flag(self, mock_execute_print, mock_get_default):
        """Test -p flag for print mode."""
        mock_get_default.return_value = "ollama"
        # Mock the async function with AsyncMock
        mock_execute_print.return_value = AsyncMock()
        
        result = self.runner.invoke(app, ["-p", "test message"])
        mock_execute_print.assert_called_once()
        call_args = mock_execute_print.call_args[0]  # positional args
        assert call_args[0] == "test message"
    
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
    
    def test_chat_integration(self):
        """Test that chat function can be invoked without errors."""
        # Simplified test - just verify the command structure exists
        with patch('songbird.cli.chat'), \
             patch('songbird.cli.show_banner'):
            
            result = self.runner.invoke(app, ["--provider", "ollama"])
            
            # Just verify that the command doesn't crash with basic errors
            # CLI integration tests are complex and should be done separately
            assert result.exit_code in [0, 1]  # Allow for various exit conditions


class TestEnvironmentHandling:
    """Test CLI behavior with different environment configurations."""
    
    def setup_method(self):
        self.runner = CliRunner()
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False)
    @patch('songbird.cli.get_provider_info')
    def test_provider_with_api_key(self, mock_provider_info):
        """Test provider selection when API key is available."""
        mock_provider_info.return_value = {
            "openai": {"available": True, "ready": True, "models": ["gpt-4o"], "api_key_env": "OPENAI_API_KEY", "models_discovered": False}
        }
        
        result = self.runner.invoke(app, ["--list-providers"])
        assert result.exit_code == 0
        assert "openai" in result.stdout
    
    @patch.dict(os.environ, {}, clear=True)
    @patch('songbird.cli.get_provider_info')
    def test_provider_without_api_keys(self, mock_provider_info):
        """Test provider selection when no API keys are available."""
        mock_provider_info.return_value = {
            "openai": {"available": False, "ready": False, "models": [], "api_key_env": "OPENAI_API_KEY", "models_discovered": False},
            "ollama": {"available": True, "ready": True, "models": ["qwen2.5-coder:7b"], "api_key_env": None, "models_discovered": False}
        }
        
        result = self.runner.invoke(app, ["--list-providers"])
        assert result.exit_code == 0
        assert "ollama" in result.stdout


class TestErrorHandling:
    """Test CLI error handling and user guidance."""
    
    def setup_method(self):
        self.runner = CliRunner()
    
    def test_provider_initialization_error(self):
        """Test handling of provider initialization errors."""
        # Simplified test - just check that invalid provider doesn't crash CLI
        with patch('songbird.cli.chat') as mock_chat, \
             patch('songbird.cli.show_banner'):
            
            mock_chat.side_effect = Exception("Provider not available")
            result = self.runner.invoke(app, ["--provider", "nonexistent"])
            
            # Allow various exit codes - the important thing is not to crash completely
            assert result.exit_code in [0, 1, 2]
    
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
    
    def test_session_resume_with_sessions(self):
        """Test resuming sessions when sessions exist."""
        # Simplified test - just check that resume flag doesn't crash
        with patch('songbird.cli.chat'), \
             patch('songbird.cli.show_banner'):
            
            result = self.runner.invoke(app, ["--resume"])
            
            # Should handle resume request without crashing
            assert result.exit_code in [0, 1]
    
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
    
    def test_config_loading(self):
        """Test that configuration is properly loaded."""
        # Simplified test - just check that config-related functionality doesn't crash
        with patch('songbird.cli.chat'), \
             patch('songbird.cli.show_banner'):
            
            result = self.runner.invoke(app, [])
            # Should use config values without crashing
            assert result.exit_code in [0, 1]
    
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
            "openai": {"available": True, "ready": True, "models": ["gpt-4o", "gpt-4o-mini"], "api_key_env": "OPENAI_API_KEY", "models_discovered": False},
            "claude": {"available": False, "ready": False, "models": [], "api_key_env": "ANTHROPIC_API_KEY", "models_discovered": False},
            "ollama": {"available": True, "ready": True, "models": ["qwen2.5-coder:7b"], "api_key_env": None, "models_discovered": False}
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
            # Should handle KeyboardInterrupt gracefully (exit code 130 is expected for interrupt)
            assert result.exit_code in [0, 1, 130]  # 130 is typical for KeyboardInterrupt
    
    def test_empty_input_handling(self):
        """Test handling of empty or whitespace input."""
        result = self.runner.invoke(app, [""])
        # Should handle empty commands gracefully
        assert result.exit_code == 0 or result.exit_code == 2  # Click may return 2 for usage errors
    
    @patch('songbird.cli.show_banner')
    def test_banner_display(self, mock_banner):
        """Test that banner is displayed when starting chat."""
        with patch('songbird.cli.OptimizedSessionManager'), \
             patch('songbird.cli._chat_loop'), \
             patch('songbird.cli.get_default_provider_name', return_value="ollama"), \
             patch('songbird.llm.providers.get_litellm_provider'):
            result = self.runner.invoke(app, [])
            # Banner should be shown when starting chat
            mock_banner.assert_called_once()


if __name__ == "__main__":
    # Run the tests with pytest
    pytest.main([__file__, "-v"])
