#!/usr/bin/env python3
"""
Test script for search tools.
Tests file_search, glob, and grep functionality.
"""

import asyncio
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from songbird.tools.file_search import file_search
from songbird.tools.glob_tool import glob_pattern
from songbird.tools.grep_tool import grep_search


async def test_file_search_content():
    """Test file search for content."""
    print("=" * 60)
    print("TEST: File Search - Content Search")
    print("=" * 60)
    
    # Search for a common term in Python files
    search_term = "def"
    
    start_time = time.time()
    result = await file_search(search_term, directory=".", file_type="py", max_results=10)
    end_time = time.time()
    
    print(f"Searching for: '{search_term}' in Python files")
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    
    if result['success']:
        matches = result.get('matches', [])
        print(f"Found {len(matches)} matches")
        
        # Show first few matches
        for i, match in enumerate(matches[:5]):
            print(f"  {i+1}. {match.get('file', 'unknown')}:{match.get('line', 0)}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    print()


async def test_file_search_glob():
    """Test file search with glob patterns."""
    print("=" * 60)
    print("TEST: File Search - Glob Pattern (*.py)")
    print("=" * 60)
    
    pattern = "*.py"
    
    start_time = time.time()
    result = await file_search(pattern, directory=".", max_results=15)
    end_time = time.time()
    
    print(f"Searching for pattern: '{pattern}'")
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    
    if result['success']:
        files = result.get('files', [])
        print(f"Found {len(files)} Python files")
        
        # Show first few files
        for i, file_info in enumerate(files[:10]):
            file_path = file_info.get('file', 'unknown')
            size = file_info.get('size', 0)
            print(f"  {i+1}. {file_path} ({size} bytes)")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    print()


async def test_glob_basic():
    """Test basic glob functionality."""
    print("=" * 60)
    print("TEST: Glob - Basic Pattern")
    print("=" * 60)
    
    pattern = "**/*.py"
    
    start_time = time.time()
    result = await glob_pattern(pattern, directory=".", max_results=20)
    end_time = time.time()
    
    print(f"Glob pattern: '{pattern}'")
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    
    if result['success']:
        files = result.get('files', [])
        print(f"Found {len(files)} files")
        
        # Show first few files
        for i, file_path in enumerate(files[:10]):
            print(f"  {i+1}. {file_path}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    print()


async def test_glob_specific_dirs():
    """Test glob with specific directory patterns."""
    print("=" * 60)
    print("TEST: Glob - Specific Directory Pattern")
    print("=" * 60)
    
    pattern = "songbird/**/*.py"
    
    start_time = time.time()
    result = await glob_pattern(pattern, directory=".", max_results=25)
    end_time = time.time()
    
    print(f"Glob pattern: '{pattern}'")
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    
    if result['success']:
        files = result.get('files', [])
        print(f"Found {len(files)} files in songbird/")
        
        # Group by subdirectory
        subdirs = {}
        for file_path in files:
            parts = Path(file_path).parts
            if len(parts) > 1:
                subdir = parts[1]
                subdirs[subdir] = subdirs.get(subdir, 0) + 1
        
        print("Files by subdirectory:")
        for subdir, count in sorted(subdirs.items()):
            print(f"  {subdir}/: {count} files")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    print()


async def test_glob_with_exclusions():
    """Test glob with hidden files excluded."""
    print("=" * 60)
    print("TEST: Glob - Exclude Hidden Files")
    print("=" * 60)
    
    pattern = "**/*"
    
    start_time = time.time()
    result = await glob_pattern(pattern, directory=".", include_hidden=False, max_results=30)
    end_time = time.time()
    
    print(f"Glob pattern: '{pattern}' (excluding hidden)")
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    
    if result['success']:
        files = result.get('files', [])
        print(f"Found {len(files)} non-hidden files")
        
        # Check file types
        extensions = {}
        for file_path in files:
            ext = Path(file_path).suffix or '(no extension)'
            extensions[ext] = extensions.get(ext, 0) + 1
        
        print("Files by extension:")
        for ext, count in sorted(extensions.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  {ext}: {count} files")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    print()


async def test_grep_basic():
    """Test basic grep functionality."""
    print("=" * 60)
    print("TEST: Grep - Basic Pattern Search")
    print("=" * 60)
    
    pattern = "class"
    
    start_time = time.time()
    result = await grep_search(pattern, directory=".", file_pattern="*.py", max_results=15)
    end_time = time.time()
    
    print(f"Grep pattern: '{pattern}' in Python files")
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    
    if result['success']:
        matches = result.get('matches', [])
        print(f"Found {len(matches)} matches")
        
        # Show first few matches with context
        for i, match in enumerate(matches[:5]):
            file_path = match.get('file', 'unknown')
            line_num = match.get('line', 0)
            line_content = match.get('line_content', '')
            print(f"  {i+1}. {file_path}:{line_num}")
            print(f"     {line_content.strip()}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    print()


async def test_grep_regex():
    """Test grep with regex patterns."""
    print("=" * 60)
    print("TEST: Grep - Regex Pattern")
    print("=" * 60)
    
    pattern = r"async def \w+"
    
    start_time = time.time()
    result = await grep_search(pattern, directory=".", file_pattern="*.py", regex=True, max_results=10)
    end_time = time.time()
    
    print(f"Grep regex: '{pattern}' in Python files")
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    
    if result['success']:
        matches = result.get('matches', [])
        print(f"Found {len(matches)} async function definitions")
        
        # Show matches
        for i, match in enumerate(matches[:8]):
            file_path = match.get('file', 'unknown')
            line_num = match.get('line', 0)
            line_content = match.get('line_content', '')
            print(f"  {i+1}. {file_path}:{line_num}")
            print(f"     {line_content.strip()}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    print()


async def test_grep_with_context():
    """Test grep with context lines."""
    print("=" * 60)
    print("TEST: Grep - With Context Lines")
    print("=" * 60)
    
    pattern = "TODO"
    
    start_time = time.time()
    result = await grep_search(pattern, directory=".", file_pattern="*.py", context_lines=2, max_results=5)
    end_time = time.time()
    
    print(f"Grep pattern: '{pattern}' with 2 context lines")
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    
    if result['success']:
        matches = result.get('matches', [])
        print(f"Found {len(matches)} TODO comments")
        
        # Show matches with context
        for i, match in enumerate(matches[:3]):
            file_path = match.get('file', 'unknown')
            line_num = match.get('line', 0)
            print(f"  {i+1}. {file_path}:{line_num}")
            
            # Show context if available
            context = match.get('context', {})
            before = context.get('before', [])
            after = context.get('after', [])
            line_content = match.get('line_content', '')
            
            for before_line in before:
                print(f"     {before_line}")
            print(f"  -> {line_content}")
            for after_line in after:
                print(f"     {after_line}")
            print()
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    print()


async def test_search_case_sensitivity():
    """Test case sensitivity in searches."""
    print("=" * 60)
    print("TEST: Search Tools - Case Sensitivity")
    print("=" * 60)
    
    pattern = "Class"  # Capital C
    
    print("Case-sensitive search:")
    start_time = time.time()
    result_sensitive = await grep_search(pattern, directory=".", file_pattern="*.py", case_sensitive=True, max_results=5)
    end_time = time.time()
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    
    if result_sensitive['success']:
        matches_sensitive = result_sensitive.get('matches', [])
        print(f"Found {len(matches_sensitive)} case-sensitive matches")
    
    print("\nCase-insensitive search:")
    start_time = time.time()
    result_insensitive = await grep_search(pattern, directory=".", file_pattern="*.py", case_sensitive=False, max_results=5)
    end_time = time.time()
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    
    if result_insensitive['success']:
        matches_insensitive = result_insensitive.get('matches', [])
        print(f"Found {len(matches_insensitive)} case-insensitive matches")
    
    print()


async def main():
    """Run all search tool tests."""
    print("SEARCH TOOLS TEST SUITE")
    print("=" * 60)
    print(f"Running tests at: {Path.cwd()}")
    print(f"Test time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # File search tests
    await test_file_search_content()
    await test_file_search_glob()
    
    # Glob tests
    await test_glob_basic()
    await test_glob_specific_dirs()
    await test_glob_with_exclusions()
    
    # Grep tests
    await test_grep_basic()
    await test_grep_regex()
    await test_grep_with_context()
    await test_search_case_sensitivity()
    
    print("=" * 60)
    print("ALL SEARCH TOOL TESTS COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())