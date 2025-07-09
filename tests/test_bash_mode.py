"""
Tests for bash mode functionality.
"""

from songbird.commands.loader import is_bash_mode_input, parse_bash_input


class TestBashMode:
    """Test bash mode input detection and parsing."""

    def test_is_bash_mode_input(self):
        """Test bash mode detection."""
        # Valid bash mode inputs
        assert is_bash_mode_input("!ls") is True
        assert is_bash_mode_input("!ls -la") is True
        assert is_bash_mode_input("! echo hello") is True
        assert is_bash_mode_input("!pwd") is True
        assert is_bash_mode_input("!") is True
        
        # Invalid bash mode inputs
        assert is_bash_mode_input("ls") is False
        assert is_bash_mode_input("/help") is False
        assert is_bash_mode_input("regular message") is False
        assert is_bash_mode_input("") is False
        assert is_bash_mode_input("echo ! hello") is False  # ! not at start
    
    def test_parse_bash_input(self):
        """Test bash command parsing."""
        # Valid commands
        assert parse_bash_input("!ls") == "ls"
        assert parse_bash_input("!ls -la") == "ls -la"
        assert parse_bash_input("! echo hello") == "echo hello"
        assert parse_bash_input("!pwd") == "pwd"
        assert parse_bash_input("!") == ""
        
        # Invalid inputs (should return empty string)
        assert parse_bash_input("ls") == ""
        assert parse_bash_input("/help") == ""
        assert parse_bash_input("regular message") == ""
        assert parse_bash_input("") == ""
    
    def test_bash_mode_edge_cases(self):
        """Test edge cases for bash mode."""
        # Commands with special characters
        assert is_bash_mode_input("!echo 'hello world'") is True
        assert parse_bash_input("!echo 'hello world'") == "echo 'hello world'"
        
        # Commands with pipes and redirections
        assert is_bash_mode_input("!ls | grep test") is True
        assert parse_bash_input("!ls | grep test") == "ls | grep test"
        
        # Commands with multiple spaces
        assert is_bash_mode_input("!   ls   -la   ") is True
        assert parse_bash_input("!   ls   -la   ") == "ls   -la"
        
        # Only exclamation mark
        assert is_bash_mode_input("!") is True
        assert parse_bash_input("!") == ""
    
    def test_bash_mode_vs_commands(self):
        """Test that bash mode doesn't conflict with slash commands."""
        # Slash commands should not be detected as bash mode
        assert is_bash_mode_input("/help") is False
        assert is_bash_mode_input("/model") is False
        assert is_bash_mode_input("/clear") is False
        
        # Bash commands should not be detected as slash commands
        from songbird.commands.loader import is_command_input
        assert is_command_input("!ls") is False
        assert is_command_input("!echo hello") is False
    
    def test_whitespace_handling(self):
        """Test whitespace handling in bash mode."""
        # Leading/trailing whitespace
        assert is_bash_mode_input("  !ls  ") is True
        assert parse_bash_input("!ls -la  ") == "ls -la"
        
        # Internal whitespace preservation
        assert parse_bash_input("!echo  'hello    world'") == "echo  'hello    world'"