# tests/tools/test_file_search.py
import pytest
import json
from pathlib import Path
from songbird.tools.file_search import file_search


class TestFileSearch:
    @pytest.fixture
    def fixture_repo(self):
        """Path to test fixture repository."""
        return Path(__file__).parent.parent / "fixtures" / "repo_a"

    @pytest.mark.asyncio
    async def test_file_search_finds_todo_matches(self, fixture_repo):
        """Test that file_search finds TODO comments in fixture files."""
        # This test should fail initially since file_search doesn't exist yet
        results = await file_search("TODO", str(fixture_repo))
        
        # Parse JSON results
        assert isinstance(results, list)
        assert len(results) >= 3  # Should find TODOs in README.md, main.py, config.toml
        
        # Check structure of results
        for result in results:
            assert "file" in result
            assert "line" in result  
            assert "column" in result
            assert "text" in result
            
        # Verify specific matches
        files_with_matches = {result["file"] for result in results}
        assert "README.md" in str(files_with_matches)
        assert "src/main.py" in str(files_with_matches) 
        assert "config.toml" in str(files_with_matches)

    @pytest.mark.asyncio
    async def test_file_search_case_insensitive(self, fixture_repo):
        """Test that file_search is case insensitive."""
        results = await file_search("todo", str(fixture_repo))
        assert len(results) >= 3

    @pytest.mark.asyncio 
    async def test_file_search_no_matches(self, fixture_repo):
        """Test file_search returns empty list when no matches found."""
        results = await file_search("NONEXISTENT_PATTERN", str(fixture_repo))
        assert results == []

    @pytest.mark.asyncio
    async def test_file_search_invalid_directory(self):
        """Test file_search handles invalid directory gracefully."""
        with pytest.raises(FileNotFoundError):
            await file_search("TODO", "/nonexistent/directory")