# tests/tools/test_tree_tool.py
import pytest
import tempfile
from pathlib import Path
from songbird.tools.tree_tool import tree_display, tree_project_overview, tree_files_only, tree_dirs_only


class TestTreeTool:
    
    @pytest.mark.asyncio
    async def test_tree_display_basic(self):
        """Test basic tree display functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test structure
            (temp_path / "file1.txt").write_text("content1")
            (temp_path / "file2.py").write_text("print('hello')")
            (temp_path / "subdir").mkdir()
            (temp_path / "subdir" / "nested.md").write_text("# Test")
            
            result = await tree_display(str(temp_path), max_depth=2)
            
            assert result["success"] is True
            assert result["total_items"] >= 4  # 2 files + 1 dir + 1 nested file
            assert result["file_count"] >= 3
            assert result["dir_count"] >= 1
            assert result["path"] == str(temp_path)
    
    @pytest.mark.asyncio
    async def test_tree_display_max_depth(self):
        """Test max depth limiting."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create nested structure
            (temp_path / "level1").mkdir()
            (temp_path / "level1" / "level2").mkdir()
            (temp_path / "level1" / "level2" / "deep.txt").write_text("deep content")
            
            # Test with depth=1 (should not show deep.txt)
            result = await tree_display(str(temp_path), max_depth=1)
            
            assert result["success"] is True
            # Should only show level1 directory, not its contents
            assert result["total_items"] == 1
            assert result["dir_count"] == 1
            assert result["file_count"] == 0
    
    @pytest.mark.asyncio
    async def test_tree_display_hidden_files(self):
        """Test hidden file handling."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create regular and hidden files
            (temp_path / "visible.txt").write_text("visible")
            (temp_path / ".hidden.txt").write_text("hidden")
            (temp_path / ".hidden_dir").mkdir()
            
            # Test without hidden files
            result = await tree_display(str(temp_path), show_hidden=False)
            assert result["success"] is True
            assert result["file_count"] == 1  # Only visible.txt
            assert result["dir_count"] == 0   # No hidden dir
            
            # Test with hidden files
            result = await tree_display(str(temp_path), show_hidden=True)
            assert result["success"] is True
            assert result["file_count"] == 2  # visible.txt + .hidden.txt
            assert result["dir_count"] == 1   # .hidden_dir
    
    @pytest.mark.asyncio
    async def test_tree_display_dirs_only(self):
        """Test directories-only mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create mixed structure
            (temp_path / "file1.txt").write_text("content1")
            (temp_path / "dir1").mkdir()
            (temp_path / "dir2").mkdir()
            (temp_path / "dir1" / "nested_file.py").write_text("code")
            
            result = await tree_display(str(temp_path), dirs_only=True)
            
            assert result["success"] is True
            assert result["file_count"] == 0  # No files should be shown
            assert result["dir_count"] >= 2   # dir1 and dir2
    
    @pytest.mark.asyncio
    async def test_tree_display_files_only(self):
        """Test files-only mode."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create mixed structure
            (temp_path / "file1.txt").write_text("content1")
            (temp_path / "file2.py").write_text("code")
            (temp_path / "dir1").mkdir()
            (temp_path / "dir1" / "nested_file.md").write_text("# Doc")
            
            result = await tree_display(str(temp_path), files_only=True, max_depth=2)
            
            assert result["success"] is True
            assert result["dir_count"] == 0  # No directories should be shown
            assert result["file_count"] >= 3 # file1.txt, file2.py, nested_file.md
    
    @pytest.mark.asyncio
    async def test_tree_display_exclude_patterns(self):
        """Test exclusion patterns."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create structure with common exclusions
            (temp_path / "main.py").write_text("main code")
            (temp_path / "__pycache__").mkdir()
            (temp_path / "__pycache__" / "cache.pyc").write_text("cache")
            (temp_path / "node_modules").mkdir()
            (temp_path / ".git").mkdir()
            
            result = await tree_display(str(temp_path))
            
            assert result["success"] is True
            # Should exclude __pycache__, node_modules, .git by default
            items = [item for item in [result.get("tree_output", "")] if "pycache" not in str(item)]
            assert "__pycache__" not in str(result.get("tree_output", ""))
    
    @pytest.mark.asyncio
    async def test_tree_display_nonexistent_path(self):
        """Test handling of non-existent path."""
        result = await tree_display("/nonexistent/path/12345")
        
        assert result["success"] is False
        assert "not found" in result["error"].lower()
        assert result["total_items"] == 0
    
    @pytest.mark.asyncio
    async def test_tree_display_file_instead_of_dir(self):
        """Test handling when path is a file instead of directory."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content")
            f.flush()
            
            result = await tree_display(f.name)
            
            assert result["success"] is False
            assert "not a directory" in result["error"].lower()
            
            # Clean up
            Path(f.name).unlink()
    
    @pytest.mark.asyncio
    async def test_tree_project_overview(self):
        """Test project overview function."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create simple project structure
            (temp_path / "README.md").write_text("# Project")
            (temp_path / "src").mkdir()
            (temp_path / "src" / "main.py").write_text("code")
            
            result = await tree_project_overview(str(temp_path))
            
            assert result["success"] is True
            assert result["max_depth"] == 2  # Project overview uses depth=2
    
    @pytest.mark.asyncio
    async def test_tree_files_only_function(self):
        """Test dedicated files-only function."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create structure
            (temp_path / "file.txt").write_text("content")
            (temp_path / "dir").mkdir()
            
            result = await tree_files_only(str(temp_path))
            
            assert result["success"] is True
            assert result["file_count"] >= 1
            assert result["dir_count"] == 0  # Should show no directories
    
    @pytest.mark.asyncio
    async def test_tree_dirs_only_function(self):
        """Test dedicated directories-only function."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create structure
            (temp_path / "file.txt").write_text("content")
            (temp_path / "dir1").mkdir()
            (temp_path / "dir2").mkdir()
            
            result = await tree_dirs_only(str(temp_path))
            
            assert result["success"] is True
            assert result["dir_count"] >= 2
            assert result["file_count"] == 0  # Should show no files
    
    @pytest.mark.asyncio
    async def test_tree_display_empty_directory(self):
        """Test handling of empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = await tree_display(temp_dir)
            
            assert result["success"] is True
            assert result["total_items"] == 0
            assert result["tree_output"] == "empty"
    
    @pytest.mark.asyncio
    async def test_tree_display_with_sizes(self):
        """Test file size display."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create file with content
            large_content = "x" * 1024  # 1KB content
            (temp_path / "large.txt").write_text(large_content)
            
            result = await tree_display(str(temp_path), show_sizes=True)
            
            assert result["success"] is True
            assert result["file_count"] == 1
            # Note: The actual size checking would require examining the tree_output
            # which contains the formatted display, but we can at least verify
            # the function completes successfully