#!/usr/bin/env python3
"""
Test script for file operation tools.
Tests file_read, file_create, and file_edit functionality.
"""

import asyncio
import sys
import time
import tempfile
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from songbird.tools.file_operations import file_read, file_create, file_edit


async def test_file_create():
    """Test file creation functionality."""
    print("=" * 60)
    print("TEST: File Create")
    print("=" * 60)
    
    # Create a temporary file
    temp_path = Path(tempfile.gettempdir()) / "songbird_test_file.txt"
    content = """Hello, World!
This is a test file created by the file_create tool.
It contains multiple lines to test the functionality.

Line 5 with some content.
Final line."""
    
    start_time = time.time()
    result = await file_create(str(temp_path), content)
    end_time = time.time()
    
    print(f"Created file: {temp_path}")
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    
    if result['success']:
        print(f"File size: {result.get('file_size', 0)} bytes")
        print(f"Lines: {result.get('lines_written', 0)}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    print()
    return temp_path


async def test_file_read_full(file_path):
    """Test reading a full file."""
    print("=" * 60)
    print("TEST: File Read - Full File")
    print("=" * 60)
    
    start_time = time.time()
    result = await file_read(str(file_path))
    end_time = time.time()
    
    print(f"Reading file: {file_path}")
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    
    if result['success']:
        content = result.get('content', '')
        print(f"Content length: {len(content)} characters")
        print(f"Lines read: {len(content.splitlines())}")
        print("\nFirst 200 characters:")
        print(f"'{content[:200]}{'...' if len(content) > 200 else ''}'")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    print()


async def test_file_read_partial(file_path):
    """Test reading part of a file."""
    print("=" * 60)
    print("TEST: File Read - Partial (3 lines)")
    print("=" * 60)
    
    start_time = time.time()
    result = await file_read(str(file_path), lines=3)
    end_time = time.time()
    
    print(f"Reading file: {file_path}")
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    
    if result['success']:
        content = result.get('content', '')
        print(f"Content length: {len(content)} characters")
        print(f"Lines read: {len(content.splitlines())}")
        print(f"Truncated: {result.get('truncated', False)}")
        print("\nContent:")
        print(f"'{content}'")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    print()


async def test_file_read_with_start(file_path):
    """Test reading from a specific line."""
    print("=" * 60)
    print("TEST: File Read - Start from line 2, read 3 lines")
    print("=" * 60)
    
    start_time = time.time()
    result = await file_read(str(file_path), lines=3, start_line=2)
    end_time = time.time()
    
    print(f"Reading file: {file_path}")
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    
    if result['success']:
        content = result.get('content', '')
        print(f"Content length: {len(content)} characters")
        print(f"Lines read: {len(content.splitlines())}")
        print(f"Start line: {result.get('start_line', 1)}")
        print("\nContent:")
        print(f"'{content}'")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    print()


async def test_file_edit(file_path):
    """Test file editing functionality."""
    print("=" * 60)
    print("TEST: File Edit")
    print("=" * 60)
    
    new_content = """Edited Content!
This file has been modified by the file_edit tool.
Original content was replaced.

New line 4.
Final edited line."""
    
    start_time = time.time()
    result = await file_edit(str(file_path), new_content, create_backup=True)
    end_time = time.time()
    
    print(f"Editing file: {file_path}")
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    
    if result['success']:
        print(f"New file size: {result.get('new_size', 0)} bytes")
        print(f"Old file size: {result.get('old_size', 0)} bytes")
        print(f"Backup created: {result.get('backup_created', False)}")
        if result.get('backup_path'):
            print(f"Backup path: {result['backup_path']}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    print()


async def test_file_read_nonexistent():
    """Test reading a non-existent file."""
    print("=" * 60)
    print("TEST: File Read - Non-existent File (Error Handling)")
    print("=" * 60)
    
    nonexistent_path = "/nonexistent/file.txt"
    
    start_time = time.time()
    result = await file_read(nonexistent_path)
    end_time = time.time()
    
    print(f"Reading file: {nonexistent_path}")
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    print(f"Error: {result.get('error', 'None')}")
    print()


async def test_file_create_existing(file_path):
    """Test creating a file that already exists."""
    print("=" * 60)
    print("TEST: File Create - Existing File (Should Overwrite)")
    print("=" * 60)
    
    new_content = "Overwritten content via file_create."
    
    start_time = time.time()
    result = await file_create(str(file_path), new_content)
    end_time = time.time()
    
    print(f"Creating file: {file_path}")
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    
    if result['success']:
        print(f"File size: {result.get('file_size', 0)} bytes")
        print(f"Overwritten: {result.get('overwritten', False)}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    print()


async def test_file_read_large_file():
    """Test reading a large file with line limits."""
    print("=" * 60)
    print("TEST: File Read - Large File Simulation")
    print("=" * 60)
    
    # Create a larger temporary file
    large_temp_path = Path(tempfile.gettempdir()) / "songbird_large_test.txt"
    large_content = "\n".join([f"Line {i+1}: This is a longer line with some content to test file reading capabilities." for i in range(100)])
    
    # Create the large file first
    create_result = await file_create(str(large_temp_path), large_content)
    
    if create_result['success']:
        start_time = time.time()
        result = await file_read(str(large_temp_path), lines=10)
        end_time = time.time()
        
        print(f"Reading large file: {large_temp_path}")
        print("Total file lines: 100")
        print(f"Execution time: {end_time - start_time:.2f} seconds")
        print(f"Success: {result['success']}")
        
        if result['success']:
            content = result.get('content', '')
            print(f"Content length: {len(content)} characters")
            print(f"Lines read: {len(content.splitlines())}")
            print(f"Truncated: {result.get('truncated', False)}")
        
        # Clean up
        try:
            os.unlink(large_temp_path)
        except:
            pass
    else:
        print(f"Failed to create large test file: {create_result.get('error')}")
    
    print()


async def cleanup_test_files(file_path):
    """Clean up test files."""
    print("=" * 60)
    print("CLEANUP: Removing Test Files")
    print("=" * 60)
    
    files_to_remove = [
        file_path,
        Path(str(file_path) + ".backup"),
    ]
    
    for file_path in files_to_remove:
        try:
            if file_path.exists():
                os.unlink(file_path)
                print(f"Removed: {file_path}")
        except Exception as e:
            print(f"Failed to remove {file_path}: {e}")
    
    print()


async def main():
    """Run all file operation tests."""
    print("FILE OPERATIONS TEST SUITE")
    print("=" * 60)
    print(f"Running tests at: {Path.cwd()}")
    print(f"Test time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Create a test file and run all operations
    temp_file_path = await test_file_create()
    
    try:
        await test_file_read_full(temp_file_path)
        await test_file_read_partial(temp_file_path)
        await test_file_read_with_start(temp_file_path)
        await test_file_edit(temp_file_path)
        await test_file_read_nonexistent()
        await test_file_create_existing(temp_file_path)
        await test_file_read_large_file()
    finally:
        await cleanup_test_files(temp_file_path)
    
    print("=" * 60)
    print("ALL FILE OPERATION TESTS COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())