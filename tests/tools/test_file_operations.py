# tests/tools/test_file_operations.py
import pytest
import tempfile
from pathlib import Path
from songbird.tools.file_operations import file_read, file_edit, apply_file_edit


class TestFileOperations:
    
    @pytest.mark.asyncio
    async def test_file_read_existing_file(self):
        """Test reading an existing file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            test_content = "print('hello world')\n# This is a test\n"
            f.write(test_content)
            f.flush()
            
            result = await file_read(f.name)
            
            assert result["success"] is True
            assert result["content"] == test_content
            assert result["total_lines"] == 2
            assert result["lines_returned"] == 2
            
            # Clean up
            Path(f.name).unlink()
    
    @pytest.mark.asyncio
    async def test_file_read_with_line_range(self):
        """Test reading specific line range."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            test_content = "line 1\nline 2\nline 3\nline 4\n"
            f.write(test_content)
            f.flush()
            
            # Read only 2 lines starting from line 2
            result = await file_read(f.name, lines=2, start_line=2)
            
            assert result["success"] is True
            assert result["content"] == "line 2\nline 3\n"
            assert result["total_lines"] == 4
            assert result["lines_returned"] == 2
            
            # Clean up
            Path(f.name).unlink()
    
    @pytest.mark.asyncio
    async def test_file_read_nonexistent_file(self):
        """Test reading a file that doesn't exist."""
        result = await file_read("/nonexistent/file.txt")
        
        assert result["success"] is False
        assert "not found" in result["error"].lower()
    
    @pytest.mark.asyncio
    async def test_file_edit_new_file(self):
        """Test editing a new file (creation)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "new_file.py"
            new_content = "def hello():\n    print('Hello, World!')\n"
            
            result = await file_edit(str(file_path), new_content)
            
            assert result["success"] is True
            assert result["changes_made"] is True
            assert result["old_content"] == ""
            assert result["new_content"] == new_content
            assert "diff_preview" in result
    
    @pytest.mark.asyncio
    async def test_file_edit_existing_file(self):
        """Test editing an existing file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            original_content = "print('old version')\n"
            f.write(original_content)
            f.flush()
            
            new_content = "print('new version')\nprint('updated!')\n"
            result = await file_edit(f.name, new_content)
            
            assert result["success"] is True
            assert result["changes_made"] is True
            assert result["old_content"] == original_content
            assert result["new_content"] == new_content
            assert "diff_preview" in result
            assert "+" in result["diff_preview"]  # Should show additions
            assert "-" in result["diff_preview"]  # Should show deletions
            
            # Clean up
            Path(f.name).unlink()
    
    @pytest.mark.asyncio
    async def test_file_edit_no_changes(self):
        """Test editing file with same content (no changes)."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            content = "print('same content')\n"
            f.write(content)
            f.flush()
            
            result = await file_edit(f.name, content)
            
            assert result["success"] is True
            assert result["changes_made"] is False
            
            # Clean up
            Path(f.name).unlink()
    
    @pytest.mark.asyncio
    async def test_apply_file_edit(self):
        """Test actually applying file edit."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_file.py"
            new_content = "def test():\n    return 42\n"
            
            result = await apply_file_edit(str(file_path), new_content)
            
            assert result["success"] is True
            assert "created successfully" in result["message"]
            
            # Verify file was actually created with correct content
            assert file_path.exists()
            assert file_path.read_text() == new_content
    
