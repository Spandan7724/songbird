#!/usr/bin/env python3
"""
Test script for the ls tool.
Tests various ls tool parameters and scenarios.
"""

import asyncio
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from songbird.tools.ls_tool import ls_directory


async def test_basic_ls():
    """Test basic ls functionality."""
    print("=" * 60)
    print("TEST: Basic LS (current directory)")
    print("=" * 60)
    
    start_time = time.time()
    result = await ls_directory(".")
    end_time = time.time()
    
    print(f"\nExecution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    print(f"Total items: {result.get('total_items', 0)}")
    print(f"Files: {result.get('file_count', 0)}, Directories: {result.get('dir_count', 0)}")
    print()


async def test_ls_long_format():
    """Test ls with detailed long format."""
    print("=" * 60)
    print("TEST: LS - Long Format (Detailed)")
    print("=" * 60)
    
    start_time = time.time()
    result = await ls_directory(".", long_format=True)
    end_time = time.time()
    
    print(f"\nExecution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    print(f"Total items: {result.get('total_items', 0)}")
    print()


async def test_ls_short_format():
    """Test ls with short format."""
    print("=" * 60)
    print("TEST: LS - Short Format")
    print("=" * 60)
    
    start_time = time.time()
    result = await ls_directory(".", long_format=False)
    end_time = time.time()
    
    print(f"\nExecution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    print(f"Total items: {result.get('total_items', 0)}")
    print()


async def test_ls_sort_by_size():
    """Test ls sorted by file size."""
    print("=" * 60)
    print("TEST: LS - Sort by Size")
    print("=" * 60)
    
    start_time = time.time()
    result = await ls_directory(".", sort_by="size", long_format=True)
    end_time = time.time()
    
    print(f"\nExecution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    print(f"Total items: {result.get('total_items', 0)}")
    print()


async def test_ls_sort_by_modified():
    """Test ls sorted by modification time."""
    print("=" * 60)
    print("TEST: LS - Sort by Modified Time")
    print("=" * 60)
    
    start_time = time.time()
    result = await ls_directory(".", sort_by="modified", long_format=True)
    end_time = time.time()
    
    print(f"\nExecution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    print(f"Total items: {result.get('total_items', 0)}")
    print()


async def test_ls_reverse_sort():
    """Test ls with reverse sorting."""
    print("=" * 60)
    print("TEST: LS - Reverse Sort by Size")
    print("=" * 60)
    
    start_time = time.time()
    result = await ls_directory(".", sort_by="size", reverse=True, long_format=True)
    end_time = time.time()
    
    print(f"\nExecution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    print(f"Total items: {result.get('total_items', 0)}")
    print()


async def test_ls_with_hidden():
    """Test ls showing hidden files."""
    print("=" * 60)
    print("TEST: LS - Including Hidden Files")
    print("=" * 60)
    
    start_time = time.time()
    result = await ls_directory(".", show_hidden=True, long_format=True)
    end_time = time.time()
    
    print(f"\nExecution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    print(f"Total items: {result.get('total_items', 0)}")
    print()


async def test_ls_files_only():
    """Test ls showing only files."""
    print("=" * 60)
    print("TEST: LS - Files Only")
    print("=" * 60)
    
    start_time = time.time()
    result = await ls_directory(".", file_type_filter="file", long_format=True)
    end_time = time.time()
    
    print(f"\nExecution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    print(f"Total items: {result.get('total_items', 0)}")
    print()


async def test_ls_dirs_only():
    """Test ls showing only directories."""
    print("=" * 60)
    print("TEST: LS - Directories Only")
    print("=" * 60)
    
    start_time = time.time()
    result = await ls_directory(".", file_type_filter="dir", long_format=True)
    end_time = time.time()
    
    print(f"\nExecution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    print(f"Total items: {result.get('total_items', 0)}")
    print()


async def test_ls_recursive():
    """Test ls with recursive listing."""
    print("=" * 60)
    print("TEST: LS - Recursive (Depth 2)")
    print("=" * 60)
    
    start_time = time.time()
    result = await ls_directory(".", recursive=True, max_depth=2, long_format=True)
    end_time = time.time()
    
    print(f"\nExecution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    print(f"Total items: {result.get('total_items', 0)}")
    print()


async def test_ls_specific_directory():
    """Test ls on a specific subdirectory."""
    print("=" * 60)
    print("TEST: LS - Specific Directory (songbird/tools)")
    print("=" * 60)
    
    start_time = time.time()
    result = await ls_directory("songbird/tools", long_format=True)
    end_time = time.time()
    
    print(f"\nExecution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    if result['success']:
        print(f"Total items: {result.get('total_items', 0)}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    print()


async def test_ls_nonexistent_path():
    """Test ls with non-existent path."""
    print("=" * 60)
    print("TEST: LS - Non-existent Path (Error Handling)")
    print("=" * 60)
    
    start_time = time.time()
    result = await ls_directory("/nonexistent/path")
    end_time = time.time()
    
    print(f"\nExecution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    print(f"Error: {result.get('error', 'None')}")
    print()


async def main():
    """Run all ls tool tests."""
    print("LS TOOL TEST SUITE")
    print("=" * 60)
    print(f"Running tests at: {Path.cwd()}")
    print(f"Test time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Run all tests
    await test_basic_ls()
    await test_ls_long_format()
    await test_ls_short_format()
    await test_ls_sort_by_size()
    await test_ls_sort_by_modified()
    await test_ls_reverse_sort()
    await test_ls_with_hidden()
    await test_ls_files_only()
    await test_ls_dirs_only()
    await test_ls_recursive()
    await test_ls_specific_directory()
    await test_ls_nonexistent_path()
    
    print("=" * 60)
    print("ALL LS TESTS COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())