#!/usr/bin/env python3
"""
Test script for the tree tool.
Tests various tree tool parameters and scenarios.
"""

import asyncio
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from songbird.tools.tree_tool import tree_display


async def test_basic_tree():
    """Test basic tree functionality."""
    print("=" * 60)
    print("TEST: Basic Tree (current directory)")
    print("=" * 60)
    
    start_time = time.time()
    result = await tree_display(".")
    end_time = time.time()
    
    print(f"\nExecution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    print(f"Total items: {result.get('total_items', 0)}")
    print(f"Files: {result.get('file_count', 0)}, Directories: {result.get('dir_count', 0)}")
    print()


async def test_tree_with_depth():
    """Test tree with different depth settings."""
    print("=" * 60)
    print("TEST: Tree with Different Depths")
    print("=" * 60)
    
    for depth in [1, 2, 3, 5]:
        print(f"\n--- Depth {depth} ---")
        start_time = time.time()
        result = await tree_display(".", max_depth=depth)
        end_time = time.time()
        
        print(f"Execution time: {end_time - start_time:.2f} seconds")
        print(f"Success: {result['success']}")
        print(f"Total items: {result.get('total_items', 0)}")
        print()


async def test_tree_dirs_only():
    """Test tree showing only directories."""
    print("=" * 60)
    print("TEST: Tree - Directories Only")
    print("=" * 60)
    
    start_time = time.time()
    result = await tree_display(".", dirs_only=True, max_depth=4)
    end_time = time.time()
    
    print(f"\nExecution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    print(f"Total items: {result.get('total_items', 0)}")
    print(f"Files: {result.get('file_count', 0)}, Directories: {result.get('dir_count', 0)}")
    print()


async def test_tree_files_only():
    """Test tree showing only files."""
    print("=" * 60)
    print("TEST: Tree - Files Only")
    print("=" * 60)
    
    start_time = time.time()
    result = await tree_display(".", files_only=True, max_depth=2)
    end_time = time.time()
    
    print(f"\nExecution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    print(f"Total items: {result.get('total_items', 0)}")
    print(f"Files: {result.get('file_count', 0)}, Directories: {result.get('dir_count', 0)}")
    print()


async def test_tree_with_hidden():
    """Test tree showing hidden files."""
    print("=" * 60)
    print("TEST: Tree - Including Hidden Files")
    print("=" * 60)
    
    start_time = time.time()
    result = await tree_display(".", show_hidden=True, max_depth=2)
    end_time = time.time()
    
    print(f"\nExecution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    print(f"Total items: {result.get('total_items', 0)}")
    print(f"Files: {result.get('file_count', 0)}, Directories: {result.get('dir_count', 0)}")
    print()


async def test_tree_no_sizes():
    """Test tree without showing file sizes."""
    print("=" * 60)
    print("TEST: Tree - No File Sizes")
    print("=" * 60)
    
    start_time = time.time()
    result = await tree_display(".", show_sizes=False, max_depth=2)
    end_time = time.time()
    
    print(f"\nExecution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    print(f"Total items: {result.get('total_items', 0)}")
    print()


async def test_tree_with_exclusions():
    """Test tree with custom exclusion patterns."""
    print("=" * 60)
    print("TEST: Tree - Custom Exclusions")
    print("=" * 60)
    
    # Exclude Python cache and test directories
    exclude_patterns = ["__pycache__", "*.pyc", "test*", ".pytest_cache"]
    
    start_time = time.time()
    result = await tree_display(".", exclude_patterns=exclude_patterns, max_depth=3)
    end_time = time.time()
    
    print(f"Excluded patterns: {exclude_patterns}")
    print(f"\nExecution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    print(f"Total items: {result.get('total_items', 0)}")
    print()


async def test_tree_include_only():
    """Test tree with include-only patterns."""
    print("=" * 60)
    print("TEST: Tree - Include Only Python Files")
    print("=" * 60)
    
    include_patterns = [".py"]
    
    start_time = time.time()
    result = await tree_display(".", include_only=include_patterns, max_depth=3)
    end_time = time.time()
    
    print(f"Include patterns: {include_patterns}")
    print(f"\nExecution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    print(f"Total items: {result.get('total_items', 0)}")
    print()


async def test_tree_nonexistent_path():
    """Test tree with non-existent path."""
    print("=" * 60)
    print("TEST: Tree - Non-existent Path (Error Handling)")
    print("=" * 60)
    
    start_time = time.time()
    result = await tree_display("/nonexistent/path")
    end_time = time.time()
    
    print(f"\nExecution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    print(f"Error: {result.get('error', 'None')}")
    print()


async def main():
    """Run all tree tool tests."""
    print("TREE TOOL TEST SUITE")
    print("=" * 60)
    print(f"Running tests at: {Path.cwd()}")
    print(f"Test time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Run all tests
    await test_basic_tree()
    await test_tree_with_depth()
    await test_tree_dirs_only()
    await test_tree_files_only()
    await test_tree_with_hidden()
    await test_tree_no_sizes()
    await test_tree_with_exclusions()
    await test_tree_include_only()
    await test_tree_nonexistent_path()
    
    print("=" * 60)
    print("ALL TREE TESTS COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())