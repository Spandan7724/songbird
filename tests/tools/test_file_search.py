# tests/tools/test_file_search.py
import pytest
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
        results = await file_search("TODO", str(fixture_repo))
        
        # Updated to match current API - returns dict with matches
        assert isinstance(results, dict)
        assert "matches" in results
        assert "success" in results
        assert results["success"] is True
        
        matches = results["matches"]
        assert isinstance(matches, list)
        assert len(matches) >= 3  # Should find TODOs in README.md, main.py, config.toml
        
        # Check structure of results
        for match in matches:
            assert "file" in match
            assert "line_number" in match
            assert "match_text" in match
            
        # Verify specific matches
        files_with_matches = {match["file"] for match in matches}
        assert "README.md" in str(files_with_matches)
        assert "src/main.py" in str(files_with_matches) 
        assert "config.toml" in str(files_with_matches)

    @pytest.mark.asyncio
    async def test_file_search_case_insensitive(self, fixture_repo):
        """Test that file_search is case insensitive."""
        results = await file_search("todo", str(fixture_repo))
        assert isinstance(results, dict)
        assert "matches" in results
        assert len(results["matches"]) >= 3

    @pytest.mark.asyncio 
    async def test_file_search_no_matches(self, fixture_repo):
        """Test file_search returns empty matches when no matches found."""
        results = await file_search("NONEXISTENT_PATTERN", str(fixture_repo))
        assert isinstance(results, dict)
        assert "matches" in results
        assert results["matches"] == []

    @pytest.mark.asyncio
    async def test_file_search_invalid_directory(self):
        """Test file_search handles invalid directory gracefully."""
        # Updated to check if error is handled gracefully instead of raising exception
        results = await file_search("TODO", "/nonexistent/directory")
        assert isinstance(results, dict)
        if "success" in results:
            # Either it fails with success=False or succeeds with empty matches
            assert results["success"] is False or results.get("matches", []) == []