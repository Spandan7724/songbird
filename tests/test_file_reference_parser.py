"""
Tests for file reference parser functionality.
"""

import tempfile
from pathlib import Path

from songbird.commands.file_reference_parser import FileReferenceParser, parse_file_references


class TestFileReferenceParser:
    """Test file reference parsing functionality."""

    def setup_method(self):
        """Set up test environment with temporary directory and files."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create test files
        (self.temp_path / "test.py").write_text("print('Hello World')")
        (self.temp_path / "config.json").write_text('{"key": "value"}')
        (self.temp_path / "file with spaces.txt").write_text("Content with spaces")
        
        # Create subdirectory with files
        sub_dir = self.temp_path / "src"
        sub_dir.mkdir()
        (sub_dir / "module.py").write_text("def hello(): pass")
        (sub_dir / "utils.py").write_text("def helper(): pass")
        
        self.parser = FileReferenceParser(str(self.temp_path))

    def teardown_method(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_simple_file_reference(self):
        """Test parsing simple @filename references."""
        message = "Please read @test.py and explain it"
        references = self.parser.parse_message(message)
        
        assert len(references) == 1
        ref = references[0]
        assert ref.raw_text == "@test.py"
        assert ref.file_path == "test.py"
        assert ref.exists is True
        assert ref.resolved_path is not None
        assert ref.error is None

    def test_quoted_file_reference(self):
        """Test parsing quoted @filename references."""
        message = 'Check @"file with spaces.txt" for content'
        references = self.parser.parse_message(message)
        
        assert len(references) == 1
        ref = references[0]
        assert ref.raw_text == '@"file with spaces.txt"'
        assert ref.file_path == "file with spaces.txt"
        assert ref.exists is True
        assert ref.error is None

    def test_subdirectory_file_reference(self):
        """Test parsing @subdirectory/filename references."""
        message = "Review @src/module.py implementation"
        references = self.parser.parse_message(message)
        
        assert len(references) == 1
        ref = references[0]
        assert ref.raw_text == "@src/module.py"
        assert ref.file_path == "src/module.py"
        assert ref.exists is True
        assert ref.error is None

    def test_relative_path_reference(self):
        """Test parsing @./path/filename references."""
        message = "Look at @./src/utils.py"
        references = self.parser.parse_message(message)
        
        assert len(references) == 1
        ref = references[0]
        assert ref.raw_text == "@./src/utils.py"
        assert ref.file_path == "./src/utils.py"
        assert ref.exists is True
        assert ref.error is None

    def test_multiple_file_references(self):
        """Test parsing multiple @filename references in one message."""
        message = "Compare @test.py and @config.json files"
        references = self.parser.parse_message(message)
        
        assert len(references) == 2
        
        # Check first reference
        ref1 = references[0]
        assert ref1.raw_text == "@test.py"
        assert ref1.file_path == "test.py"
        assert ref1.exists is True
        
        # Check second reference
        ref2 = references[1]
        assert ref2.raw_text == "@config.json"
        assert ref2.file_path == "config.json"
        assert ref2.exists is True

    def test_nonexistent_file_reference(self):
        """Test parsing @filename for non-existent files."""
        message = "Read @nonexistent.txt file"
        references = self.parser.parse_message(message)
        
        assert len(references) == 1
        ref = references[0]
        assert ref.raw_text == "@nonexistent.txt"
        assert ref.file_path == "nonexistent.txt"
        assert ref.exists is False
        assert "File does not exist" in ref.error

    def test_directory_reference(self):
        """Test parsing @directory references (should fail)."""
        message = "Check @src directory"
        references = self.parser.parse_message(message)
        
        assert len(references) == 1
        ref = references[0]
        assert ref.raw_text == "@src"
        assert ref.file_path == "src"
        assert ref.exists is False
        assert "not a file" in ref.error

    def test_absolute_path_rejection(self):
        """Test that absolute paths are rejected for security."""
        message = "Read @/etc/passwd file"
        references = self.parser.parse_message(message)
        
        assert len(references) == 1
        ref = references[0]
        assert ref.raw_text == "@/etc/passwd"
        assert ref.file_path == "/etc/passwd"
        assert ref.exists is False
        assert "Absolute paths not allowed" in ref.error

    def test_parent_directory_traversal_rejection(self):
        """Test that parent directory traversal is rejected for security."""
        message = "Read @../../../etc/passwd file"
        references = self.parser.parse_message(message)
        
        assert len(references) == 1
        ref = references[0]
        assert ref.raw_text == "@../../../etc/passwd"
        assert ref.file_path == "../../../etc/passwd"
        assert ref.exists is False
        assert "Parent directory access (..) not allowed" in ref.error

    def test_extract_file_paths(self):
        """Test extracting valid file paths only."""
        message = "Check @test.py and @nonexistent.txt files"
        paths = self.parser.extract_file_paths(message)
        
        # Only existing files should be returned
        assert len(paths) == 1
        assert str(self.temp_path / "test.py") in paths[0]

    def test_remove_file_references(self):
        """Test removing file references from message."""
        message = "Please read @test.py and @config.json then analyze them"
        clean_message = self.parser.remove_file_references(message)
        
        assert clean_message == "Please read and then analyze them"

    def test_reference_summary(self):
        """Test generating reference summary."""
        message = "Check @test.py and @nonexistent.txt files"
        references = self.parser.parse_message(message)
        summary = self.parser.get_reference_summary(references)
        
        assert "Found 1 file(s): test.py" in summary
        assert "Invalid references: nonexistent.txt" in summary

    def test_convenience_functions(self):
        """Test convenience functions."""
        message = "Read @test.py file"
        
        # Test parse_file_references function
        references = parse_file_references(message, str(self.temp_path))
        assert len(references) == 1
        assert references[0].exists is True
        
        # Test extract_valid_file_paths function
        from songbird.commands.file_reference_parser import extract_valid_file_paths
        paths = extract_valid_file_paths(message, str(self.temp_path))
        assert len(paths) == 1
        assert "test.py" in paths[0]

    def test_no_file_references(self):
        """Test message with no file references."""
        message = "This is a regular message with no special references"
        references = self.parser.parse_message(message)
        
        assert len(references) == 0
        
        # Test summary for no references
        summary = self.parser.get_reference_summary(references)
        assert summary == "No file references found."

    def test_at_symbol_not_reference(self):
        """Test @ symbols that are not file references."""
        message = "Send email to user@example.com and check @ symbol usage"
        references = self.parser.parse_message(message)
        
        # Should not match email addresses or standalone @ symbols
        assert len(references) == 0

    def test_case_sensitivity(self):
        """Test case sensitivity in file matching."""
        # Create uppercase file
        (self.temp_path / "TEST.PY").write_text("print('uppercase')")
        
        message = "Read @test.py file"
        references = self.parser.parse_message(message)
        
        assert len(references) == 1
        ref = references[0]
        assert ref.file_path == "test.py"
        # Should find the lowercase file, not the uppercase one
        assert ref.exists is True

    def test_edge_cases(self):
        """Test various edge cases."""
        # Empty filename
        message = "Check @ file"
        references = self.parser.parse_message(message)
        assert len(references) == 0  # Should not match standalone @
        
        # @ at end of message
        message = "Read file @"
        references = self.parser.parse_message(message)
        assert len(references) == 0  # Should not match @ without filename
        
        # Multiple @ in filename (invalid)
        message = "Read @test@@file.py"
        references = self.parser.parse_message(message)
        # Should match both @test and @file.py as separate references
        assert len(references) == 2
        assert references[0].file_path == "test"
        assert references[1].file_path == "file.py"