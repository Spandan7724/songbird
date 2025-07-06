"""
Tests for file completion functionality in prompt toolkit.
"""

import tempfile
import os
from pathlib import Path
import pytest
from unittest.mock import Mock

from songbird.commands.prompt_toolkit_input import SongbirdCompleter
from songbird.commands.registry import CommandRegistry


class MockDocument:
    """Mock document for testing completion."""
    
    def __init__(self, text_before_cursor):
        self.text_before_cursor = text_before_cursor


class TestFileCompletion:
    """Test file completion functionality."""

    def setup_method(self):
        """Set up test environment with temporary directory and files."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create test files and directories
        (self.temp_path / "test.py").write_text("print('hello')")
        (self.temp_path / "config.json").write_text('{"key": "value"}')
        (self.temp_path / "README.md").write_text("# Project")
        (self.temp_path / "file with spaces.txt").write_text("content")
        
        # Create subdirectories
        (self.temp_path / "src").mkdir()
        (self.temp_path / "src" / "main.py").write_text("def main(): pass")
        (self.temp_path / "src" / "utils.py").write_text("def helper(): pass")
        
        (self.temp_path / "tests").mkdir()
        (self.temp_path / "tests" / "test_main.py").write_text("def test(): pass")
        
        # Create hidden files
        (self.temp_path / ".gitignore").write_text("*.pyc")
        (self.temp_path / ".hidden").write_text("hidden content")
        
        # Mock command registry
        self.registry = Mock(spec=CommandRegistry)
        self.registry.get_all_commands.return_value = []
        
        self.completer = SongbirdCompleter(self.registry, str(self.temp_path))

    def teardown_method(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_basic_file_completion(self):
        """Test basic file completion for @filename."""
        document = MockDocument("Check @te")
        completions = list(self.completer.get_completions(document, None))
        
        # Should suggest files starting with "te"
        completion_texts = [c.text for c in completions]
        assert "test.py" in completion_texts
        
        # Check completion details
        test_completion = next(c for c in completions if c.text == "test.py")
        assert test_completion.display == "@test.py"
        assert "py code" in test_completion.display_meta

    def test_json_file_completion(self):
        """Test completion for JSON files."""
        document = MockDocument("Read @con")
        completions = list(self.completer.get_completions(document, None))
        
        completion_texts = [c.text for c in completions]
        assert "config.json" in completion_texts
        
        # Check JSON file metadata
        json_completion = next(c for c in completions if c.text == "config.json")
        assert "json config" in json_completion.display_meta

    def test_directory_completion(self):
        """Test completion for directories."""
        document = MockDocument("Check @s")
        completions = list(self.completer.get_completions(document, None))
        
        # Should suggest src directory
        completion_texts = [c.text for c in completions]
        assert "src/" in completion_texts
        
        # Check directory metadata
        src_completion = next(c for c in completions if c.text == "src/")
        assert src_completion.display == "@src/"
        assert src_completion.display_meta == "directory"

    def test_subdirectory_file_completion(self):
        """Test completion for files in subdirectories."""
        document = MockDocument("Review @src/")
        completions = list(self.completer.get_completions(document, None))
        
        # Should suggest files in src directory
        completion_texts = [c.text for c in completions]
        assert "src/main.py" in completion_texts
        assert "src/utils.py" in completion_texts
        
        # Check file path display
        main_completion = next(c for c in completions if c.text == "src/main.py")
        assert main_completion.display == "@src/main.py"

    def test_partial_filename_in_subdirectory(self):
        """Test completion for partial filename in subdirectory."""
        document = MockDocument("Check @src/ma")
        completions = list(self.completer.get_completions(document, None))
        
        completion_texts = [c.text for c in completions]
        assert "src/main.py" in completion_texts
        assert "src/utils.py" not in completion_texts  # Doesn't start with "ma"

    def test_no_hidden_files_by_default(self):
        """Test that hidden files are not suggested by default."""
        document = MockDocument("Check @.")
        completions = list(self.completer.get_completions(document, None))
        
        completion_texts = [c.text for c in completions]
        assert ".gitignore" not in completion_texts
        assert ".hidden" not in completion_texts

    def test_hidden_files_when_requested(self):
        """Test that hidden files are suggested when explicitly requested."""
        document = MockDocument("Check @.git")
        completions = list(self.completer.get_completions(document, None))
        
        completion_texts = [c.text for c in completions]
        assert ".gitignore" in completion_texts

    def test_case_insensitive_completion(self):
        """Test case-insensitive file completion."""
        document = MockDocument("Check @READ")
        completions = list(self.completer.get_completions(document, None))
        
        completion_texts = [c.text for c in completions]
        assert "README.md" in completion_texts

    def test_file_with_spaces_completion(self):
        """Test completion for files with spaces."""
        document = MockDocument("Check @file")
        completions = list(self.completer.get_completions(document, None))
        
        completion_texts = [c.text for c in completions]
        assert "file with spaces.txt" in completion_texts

    def test_no_completion_after_space(self):
        """Test that completion doesn't work after space in @ reference."""
        document = MockDocument("Check @test.py and explain")
        completions = list(self.completer.get_completions(document, None))
        
        # Should not provide file completions since there's already a space after @test.py
        assert len(completions) == 0

    def test_completion_start_position(self):
        """Test that completion start position is calculated correctly."""
        document = MockDocument("Check @te")
        completions = list(self.completer.get_completions(document, None))
        
        if completions:
            # Start position should replace "te" part
            test_completion = next(c for c in completions if c.text == "test.py")
            assert test_completion.start_position == -2  # Length of "te"

    def test_multiple_at_symbols(self):
        """Test completion with multiple @ symbols in message."""
        document = MockDocument("Compare @test.py and @con")
        completions = list(self.completer.get_completions(document, None))
        
        # Should complete the last @ reference
        completion_texts = [c.text for c in completions]
        assert "config.json" in completion_texts

    def test_quoted_completion(self):
        """Test completion within quoted @ references."""
        document = MockDocument('Check @"file')
        completions = list(self.completer.get_completions(document, None))
        
        completion_texts = [c.text for c in completions]
        assert "file with spaces.txt" in completion_texts

    def test_no_absolute_path_completion(self):
        """Test that absolute paths are not completed."""
        document = MockDocument("Check @/etc/")
        completions = list(self.completer.get_completions(document, None))
        
        # Should not provide completions for absolute paths
        assert len(completions) == 0

    def test_file_size_metadata(self):
        """Test file size in completion metadata."""
        document = MockDocument("Check @test")
        completions = list(self.completer.get_completions(document, None))
        
        test_completion = next(c for c in completions if c.text == "test.py")
        # Should show file size in metadata
        assert "B" in test_completion.display_meta or "KB" in test_completion.display_meta

    def test_command_completion_still_works(self):
        """Test that command completion still works alongside file completion."""
        # Mock a command
        mock_command = Mock()
        mock_command.name = "help"
        mock_command.description = "Show help"
        mock_command.aliases = ["h"]
        
        self.registry.get_all_commands.return_value = [mock_command]
        
        document = MockDocument("/hel")
        completions = list(self.completer.get_completions(document, None))
        
        # Should suggest the command
        completion_texts = [c.text for c in completions]
        assert "help" in completion_texts

    def test_no_completion_for_regular_text(self):
        """Test that regular text without @ or / doesn't trigger completion."""
        document = MockDocument("This is regular text")
        completions = list(self.completer.get_completions(document, None))
        
        assert len(completions) == 0

    def test_completion_error_handling(self):
        """Test that completion errors are handled gracefully."""
        # Create completer with invalid directory
        invalid_completer = SongbirdCompleter(self.registry, "/nonexistent/directory")
        
        document = MockDocument("Check @test")
        completions = list(invalid_completer.get_completions(document, None))
        
        # Should not crash, just return no completions
        assert len(completions) == 0

    def test_empty_directory_completion(self):
        """Test completion in empty directory."""
        empty_dir = self.temp_path / "empty"
        empty_dir.mkdir()
        
        empty_completer = SongbirdCompleter(self.registry, str(empty_dir))
        
        document = MockDocument("Check @test")
        completions = list(empty_completer.get_completions(document, None))
        
        assert len(completions) == 0

    def test_permission_error_handling(self):
        """Test handling of permission errors during completion."""
        # Create a directory with restricted permissions (if possible)
        restricted_dir = self.temp_path / "restricted"
        restricted_dir.mkdir()
        
        try:
            os.chmod(restricted_dir, 0o000)  # No permissions
            
            document = MockDocument("Check @restricted/")
            completions = list(self.completer.get_completions(document, None))
            
            # Should handle permission error gracefully
            restricted_completions = [c for c in completions if "restricted" in c.text]
            # May or may not suggest the directory depending on OS
            
        finally:
            # Restore permissions for cleanup
            try:
                os.chmod(restricted_dir, 0o755)
            except:
                pass