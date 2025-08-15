"""
Tests for file context manager functionality.
"""

import tempfile
import os
from pathlib import Path
import pytest

from songbird.agent.context_manager import FileContextManager, FileContext, process_file_references


class TestFileContextManager:
    """Test file context management functionality."""

    def setup_method(self):
        """Set up test environment with temporary directory and files."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create test files with different content
        (self.temp_path / "small.py").write_text("print('hello')\nprint('world')")
        (self.temp_path / "config.json").write_text('{\n  "key": "value",\n  "number": 42\n}')
        (self.temp_path / "large.txt").write_text("x" * 200000)  # Large file for size testing
        
        # Create subdirectory with files
        sub_dir = self.temp_path / "src"
        sub_dir.mkdir()
        (sub_dir / "module.py").write_text(
            "def fibonacci(n):\n"
            "    if n <= 1:\n"
            "        return n\n"
            "    return fibonacci(n-1) + fibonacci(n-2)\n"
        )
        
        self.manager = FileContextManager(str(self.temp_path), max_file_size=100_000)

    def teardown_method(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir)

    @pytest.mark.asyncio
    async def test_process_message_with_single_file(self):
        """Test processing message with single file reference."""
        message = "Explain @small.py functionality"
        enhanced_message, contexts = await self.manager.process_message_with_file_context(message)
        
        assert len(contexts) == 1
        ctx = contexts[0]
        assert ctx.relative_path == "small.py"
        assert ctx.content == "print('hello')\nprint('world')"
        assert ctx.line_count == 2
        assert ctx.error is None
        
        # Check enhanced message format
        assert "=== small.py ===" in enhanced_message
        assert "```python" in enhanced_message
        assert "print('hello')" in enhanced_message
        assert "User Request: Explain functionality" in enhanced_message

    @pytest.mark.asyncio
    async def test_process_message_with_multiple_files(self):
        """Test processing message with multiple file references."""
        message = "Compare @small.py and @config.json files"
        enhanced_message, contexts = await self.manager.process_message_with_file_context(message)
        
        assert len(contexts) == 2
        
        # Check both files are included
        file_paths = [ctx.relative_path for ctx in contexts]
        assert "small.py" in file_paths
        assert "config.json" in file_paths
        
        # Check enhanced message contains both files
        assert "=== small.py ===" in enhanced_message
        assert "=== config.json ===" in enhanced_message
        assert "```python" in enhanced_message
        assert "```json" in enhanced_message

    @pytest.mark.asyncio
    async def test_file_too_large(self):
        """Test handling of files that are too large."""
        message = "Read @large.txt content"
        enhanced_message, contexts = await self.manager.process_message_with_file_context(message)
        
        assert len(contexts) == 1
        ctx = contexts[0]
        assert ctx.relative_path == "large.txt"
        assert ctx.content == ""  # No content for large files
        assert ctx.error is not None
        assert "File too large" in ctx.error
        assert "200000 bytes" in ctx.error
        
        # Check enhanced message shows error
        assert "=== large.txt ===" in enhanced_message
        assert "Error:" in enhanced_message

    @pytest.mark.asyncio
    async def test_nonexistent_file(self):
        """Test handling of non-existent files."""
        message = "Read @missing.py file"
        enhanced_message, contexts = await self.manager.process_message_with_file_context(message)
        
        # Should return original message since no valid files  
        assert enhanced_message == "Read @missing.py file"
        assert len(contexts) == 0

    @pytest.mark.asyncio
    async def test_subdirectory_file(self):
        """Test processing files in subdirectories."""
        message = "Review @src/module.py implementation"
        enhanced_message, contexts = await self.manager.process_message_with_file_context(message)
        
        assert len(contexts) == 1
        ctx = contexts[0]
        assert ctx.relative_path == "src/module.py"
        assert "def fibonacci" in ctx.content
        assert ctx.line_count == 4
        assert ctx.error is None

    @pytest.mark.asyncio
    async def test_language_hint_detection(self):
        """Test language hint detection for different file types."""
        test_cases = [
            ("small.py", "python"),
            ("config.json", "json"),
        ]
        
        for filename, expected_lang in test_cases:
            message = f"Check @{filename}"
            enhanced_message, contexts = await self.manager.process_message_with_file_context(message)
            
            assert len(contexts) == 1
            assert f"```{expected_lang}" in enhanced_message

    @pytest.mark.asyncio
    async def test_file_summary(self):
        """Test file summary generation."""
        message = "Check @small.py and @missing.py files"
        enhanced_message, contexts = await self.manager.process_message_with_file_context(message)
        
        summary = self.manager.get_file_summary(contexts)
        assert "Included 1 file(s)" in summary
        assert "small.py" in summary
        assert "(2 lines total)" in summary

    @pytest.mark.asyncio
    async def test_no_file_references(self):
        """Test processing message with no file references."""
        message = "This is a regular message"
        enhanced_message, contexts = await self.manager.process_message_with_file_context(message)
        
        assert enhanced_message == message  # Should be unchanged
        assert len(contexts) == 0

    @pytest.mark.asyncio
    async def test_convenience_function(self):
        """Test convenience function."""
        message = "Read @small.py file"
        enhanced_message, contexts = await process_file_references(message, str(self.temp_path))
        
        assert len(contexts) == 1
        assert contexts[0].relative_path == "small.py"
        assert "print('hello')" in contexts[0].content

    @pytest.mark.asyncio
    async def test_file_context_metadata(self):
        """Test file context metadata calculation."""
        message = "Read @config.json"
        enhanced_message, contexts = await self.manager.process_message_with_file_context(message)
        
        assert len(contexts) == 1
        ctx = contexts[0]
        
        # Check metadata
        assert ctx.line_count == 4  # JSON file has 4 lines
        assert ctx.size_bytes > 0
        assert ctx.size_bytes == len('{\n  "key": "value",\n  "number": 42\n}')

    @pytest.mark.asyncio
    async def test_quoted_filename_handling(self):
        """Test handling of quoted filenames."""
        # Create file with spaces
        (self.temp_path / "file with spaces.txt").write_text("content")
        
        message = 'Read @"file with spaces.txt" content'
        enhanced_message, contexts = await self.manager.process_message_with_file_context(message)
        
        assert len(contexts) == 1
        ctx = contexts[0]
        assert ctx.relative_path == "file with spaces.txt"
        assert ctx.content == "content"

    @pytest.mark.asyncio
    async def test_empty_file_handling(self):
        """Test handling of empty files."""
        (self.temp_path / "empty.txt").write_text("")
        
        message = "Read @empty.txt"
        enhanced_message, contexts = await self.manager.process_message_with_file_context(message)
        
        assert len(contexts) == 1
        ctx = contexts[0]
        assert ctx.relative_path == "empty.txt"
        assert ctx.content == ""
        assert ctx.line_count == 0
        assert ctx.error is None

    @pytest.mark.asyncio
    async def test_security_path_traversal(self):
        """Test security - path traversal should be handled by parser."""
        message = "Read @../../../etc/passwd"
        enhanced_message, contexts = await self.manager.process_message_with_file_context(message)
        
        # Parser should reject this, so no contexts returned
        assert len(contexts) == 0
        assert enhanced_message == "Read @../../../etc/passwd"

    @pytest.mark.asyncio
    async def test_file_read_error_handling(self):
        """Test handling of file read errors."""
        # Create a file and then make it unreadable (if possible)
        test_file = self.temp_path / "protected.txt"
        test_file.write_text("protected content")
        
        # Try to make it unreadable (may not work on all systems)
        try:
            os.chmod(test_file, 0o000)
            
            message = "Read @protected.txt"
            enhanced_message, contexts = await self.manager.process_message_with_file_context(message)
            
            # Should handle the permission error gracefully
            if len(contexts) == 1:
                ctx = contexts[0]
                # Either succeeds (if OS allows) or fails gracefully
                if ctx.error:
                    assert "Error reading file" in ctx.error or "Permission denied" in str(ctx.error)
        finally:
            # Restore permissions for cleanup
            try:
                os.chmod(test_file, 0o644)
            except:
                pass

    @pytest.mark.asyncio
    async def test_mixed_valid_invalid_files(self):
        """Test processing mix of valid and invalid file references."""
        message = "Check @small.py, @missing.py, and @config.json"
        enhanced_message, contexts = await self.manager.process_message_with_file_context(message)
        
        # Should only include valid files
        assert len(contexts) == 2
        file_paths = [ctx.relative_path for ctx in contexts]
        assert "small.py" in file_paths
        assert "config.json" in file_paths
        assert all(ctx.error is None for ctx in contexts)

    @pytest.mark.asyncio
    async def test_language_hint_edge_cases(self):
        """Test language hint detection for edge cases."""
        # Test unknown extension - use underscores to avoid domain detection
        (self.temp_path / "unknown_file.xyz").write_text("unknown content")
        
        message = "Check @unknown_file.xyz"
        enhanced_message, contexts = await self.manager.process_message_with_file_context(message)
        
        assert len(contexts) == 1
        # Should use empty language hint for unknown extensions
        assert "```\n" in enhanced_message  # Empty language after ```

    def test_file_summary_edge_cases(self):
        """Test file summary for edge cases."""
        # No files
        summary = self.manager.get_file_summary([])
        assert summary == "No files included in context."
        
        # Only failed files
        failed_context = FileContext(
            file_path="/fake/path",
            relative_path="fake.txt",
            content="",
            line_count=0,
            size_bytes=0,
            error="File not found"
        )
        summary = self.manager.get_file_summary([failed_context])
        assert "Failed to include: fake.txt (File not found)" in summary