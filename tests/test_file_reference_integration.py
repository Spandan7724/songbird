"""
Integration tests for the complete @file reference feature.
"""

import tempfile
from pathlib import Path
import pytest

from songbird.commands.file_reference_parser import FileReferenceParser
from songbird.agent.context_manager import FileContextManager


class TestFileReferenceIntegration:
    """Test the complete @file reference feature integration."""

    def setup_method(self):
        """Set up test environment with temporary directory and files."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        
        # Create test files
        (self.temp_path / "main.py").write_text(
            "def main():\n"
            "    print('Hello, World!')\n"
            "    return 0\n"
            "\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )
        
        (self.temp_path / "config.json").write_text(
            '{\n'
            '  "name": "test-project",\n'
            '  "version": "1.0.0",\n'
            '  "description": "A test project"\n'
            '}\n'
        )
        
        # Create subdirectory
        (self.temp_path / "src").mkdir()
        (self.temp_path / "src" / "utils.py").write_text(
            "def helper_function():\n"
            "    return 'helper'\n"
        )

    def teardown_method(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir)

    @pytest.mark.asyncio
    async def test_single_file_reference_integration(self):
        """Test complete workflow for single file reference."""
        manager = FileContextManager(str(self.temp_path))
        
        message = "Explain how @main.py works"
        enhanced_message, contexts = await manager.process_message_with_file_context(message)
        
        # Verify context was extracted
        assert len(contexts) == 1
        ctx = contexts[0]
        assert ctx.relative_path == "main.py"
        assert "def main():" in ctx.content
        assert "print('Hello, World!')" in ctx.content
        assert ctx.line_count == 6
        assert ctx.error is None
        
        # Verify enhanced message
        assert "=== main.py ===" in enhanced_message
        assert "```python" in enhanced_message
        assert "def main():" in enhanced_message
        assert "User Request: Explain how works" in enhanced_message

    @pytest.mark.asyncio
    async def test_multiple_file_reference_integration(self):
        """Test complete workflow for multiple file references."""
        manager = FileContextManager(str(self.temp_path))
        
        message = "Compare @main.py and @config.json files"
        enhanced_message, contexts = await manager.process_message_with_file_context(message)
        
        # Verify both contexts were extracted
        assert len(contexts) == 2
        
        # Check contexts
        file_paths = [ctx.relative_path for ctx in contexts]
        assert "main.py" in file_paths
        assert "config.json" in file_paths
        
        # Find each context
        main_ctx = next(ctx for ctx in contexts if ctx.relative_path == "main.py")
        config_ctx = next(ctx for ctx in contexts if ctx.relative_path == "config.json")
        
        assert "def main():" in main_ctx.content
        assert '"name": "test-project"' in config_ctx.content
        
        # Verify enhanced message contains both
        assert "=== main.py ===" in enhanced_message
        assert "=== config.json ===" in enhanced_message
        assert "```python" in enhanced_message
        assert "```json" in enhanced_message

    @pytest.mark.asyncio
    async def test_subdirectory_file_reference_integration(self):
        """Test complete workflow for subdirectory file references."""
        manager = FileContextManager(str(self.temp_path))
        
        message = "Review @src/utils.py implementation"
        enhanced_message, contexts = await manager.process_message_with_file_context(message)
        
        # Verify context was extracted
        assert len(contexts) == 1
        ctx = contexts[0]
        assert ctx.relative_path == "src/utils.py"
        assert "def helper_function():" in ctx.content
        assert ctx.error is None
        
        # Verify enhanced message
        assert "=== src/utils.py ===" in enhanced_message
        assert "def helper_function():" in enhanced_message

    @pytest.mark.asyncio
    async def test_nonexistent_file_handling(self):
        """Test handling of non-existent file references."""
        manager = FileContextManager(str(self.temp_path))
        
        message = "Check @missing.py and @main.py files"
        enhanced_message, contexts = await manager.process_message_with_file_context(message)
        
        # Should only include the existing file
        assert len(contexts) == 1
        assert contexts[0].relative_path == "main.py"
        
        # Enhanced message should only show the existing file
        assert "=== main.py ===" in enhanced_message
        assert "=== missing.py ===" not in enhanced_message

    @pytest.mark.asyncio
    async def test_quoted_filename_integration(self):
        """Test complete workflow for quoted filenames."""
        # Create file with spaces
        (self.temp_path / "file with spaces.txt").write_text("Content with spaces")
        
        manager = FileContextManager(str(self.temp_path))
        
        message = 'Read @"file with spaces.txt" content'
        enhanced_message, contexts = await manager.process_message_with_file_context(message)
        
        # Verify context was extracted
        assert len(contexts) == 1
        ctx = contexts[0]
        assert ctx.relative_path == "file with spaces.txt"
        assert ctx.content == "Content with spaces"
        assert ctx.error is None

    @pytest.mark.asyncio
    async def test_file_summary_integration(self):
        """Test file summary generation."""
        manager = FileContextManager(str(self.temp_path))
        
        message = "Analyze @main.py and @config.json"
        enhanced_message, contexts = await manager.process_message_with_file_context(message)
        
        summary = manager.get_file_summary(contexts)
        assert "Included 2 file(s)" in summary
        assert "main.py" in summary
        assert "config.json" in summary
        assert "lines total" in summary

    @pytest.mark.asyncio
    async def test_security_integration(self):
        """Test security features work in integration."""
        parser = FileReferenceParser(str(self.temp_path))
        
        # Test various security-related inputs
        test_cases = [
            "Read @../../../etc/passwd",  # Path traversal
            "Check @/etc/passwd",         # Absolute path
            "Email me at user@example.com",  # Email address
        ]
        
        for message in test_cases:
            refs = parser.parse_message(message)
            # Should either have no references or only safe ones
            for ref in refs:
                if ref.exists:
                    # If it exists, it should be within the working directory
                    assert str(self.temp_path) in str(ref.resolved_path)

    @pytest.mark.asyncio
    async def test_empty_message_integration(self):
        """Test handling of messages with no file references."""
        manager = FileContextManager(str(self.temp_path))
        
        message = "This is a regular message with no file references"
        enhanced_message, contexts = await manager.process_message_with_file_context(message)
        
        # Should return original message unchanged
        assert enhanced_message == message
        assert len(contexts) == 0

    @pytest.mark.asyncio
    async def test_mixed_valid_invalid_integration(self):
        """Test handling of mixed valid and invalid references."""
        manager = FileContextManager(str(self.temp_path))
        
        message = "Check @main.py, @missing.py, and @config.json"
        enhanced_message, contexts = await manager.process_message_with_file_context(message)
        
        # Should only include valid files
        assert len(contexts) == 2
        file_paths = [ctx.relative_path for ctx in contexts]
        assert "main.py" in file_paths
        assert "config.json" in file_paths
        assert all(ctx.error is None for ctx in contexts)
        
        # Enhanced message should only show valid files
        assert "=== main.py ===" in enhanced_message
        assert "=== config.json ===" in enhanced_message
        assert "=== missing.py ===" not in enhanced_message

    def test_parser_email_filtering(self):
        """Test that parser correctly filters out email addresses."""
        parser = FileReferenceParser(str(self.temp_path))
        
        message = "Send email to user@example.com and also check @main.py"
        refs = parser.parse_message(message)
        
        # Should only match the file reference, not the email
        assert len(refs) == 1
        assert refs[0].file_path == "main.py"

    def test_parser_domain_filtering(self):
        """Test that parser correctly filters out domain names."""
        parser = FileReferenceParser(str(self.temp_path))
        
        message = "Visit @example.com website and check @main.py file"
        refs = parser.parse_message(message)
        
        # Should only match the file reference, not the domain
        assert len(refs) == 1
        assert refs[0].file_path == "main.py"