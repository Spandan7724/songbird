#!/usr/bin/env python3
"""
Test script for shell execution tool.
Tests shell_exec functionality with safe commands.
"""

import asyncio
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from songbird.tools.shell_exec import shell_exec


async def test_simple_commands():
    """Test simple, safe shell commands."""
    print("=" * 60)
    print("TEST: Shell Exec - Simple Commands")
    print("=" * 60)
    
    commands = [
        "echo 'Hello from shell_exec'",
        "pwd",
        "whoami",
        "date",
        "echo 'Testing multiple words with spaces'"
    ]
    
    for cmd in commands:
        print(f"\nCommand: {cmd}")
        start_time = time.time()
        result = await shell_exec(cmd)
        end_time = time.time()
        
        print(f"Execution time: {end_time - start_time:.2f} seconds")
        print(f"Success: {result['success']}")
        print(f"Exit code: {result.get('exit_code', 'N/A')}")
        
        if result['success']:
            stdout = result.get('stdout', '').strip()
            if stdout:
                print(f"Output: {stdout}")
        else:
            stderr = result.get('stderr', '')
            print(f"Error: {stderr}")
    
    print()


async def test_directory_listing():
    """Test directory listing commands."""
    print("=" * 60)
    print("TEST: Shell Exec - Directory Listing")
    print("=" * 60)
    
    commands = [
        "ls -la",
        "ls -1 *.py 2>/dev/null || echo 'No Python files in current directory'",
        "find . -name '*.py' -type f | head -5"
    ]
    
    for cmd in commands:
        print(f"\nCommand: {cmd}")
        start_time = time.time()
        result = await shell_exec(cmd)
        end_time = time.time()
        
        print(f"Execution time: {end_time - start_time:.2f} seconds")
        print(f"Success: {result['success']}")
        print(f"Exit code: {result.get('exit_code', 'N/A')}")
        
        if result['success']:
            stdout = result.get('stdout', '').strip()
            if stdout:
                lines = stdout.split('\n')
                print(f"Output ({len(lines)} lines):")
                # Show first few lines
                for line in lines[:10]:
                    print(f"  {line}")
                if len(lines) > 10:
                    print(f"  ... and {len(lines) - 10} more lines")
        else:
            stderr = result.get('stderr', '')
            print(f"Error: {stderr}")
    
    print()


async def test_working_directory():
    """Test commands with different working directories."""
    print("=" * 60)
    print("TEST: Shell Exec - Working Directory")
    print("=" * 60)
    
    # Test in current directory
    print("Current directory:")
    start_time = time.time()
    result1 = await shell_exec("pwd", working_dir=".")
    end_time = time.time()
    
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result1['success']}")
    if result1['success']:
        print(f"PWD: {result1.get('stdout', '').strip()}")
    
    # Test in subdirectory if it exists
    print("\nSongbird directory (if exists):")
    start_time = time.time()
    result2 = await shell_exec("pwd && ls -la | head -3", working_dir="songbird")
    end_time = time.time()
    
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result2['success']}")
    if result2['success']:
        stdout = result2.get('stdout', '').strip()
        print(f"Output:\n{stdout}")
    else:
        print(f"Error: {result2.get('stderr', 'Directory not found')}")
    
    print()


async def test_command_timeout():
    """Test command timeout functionality."""
    print("=" * 60)
    print("TEST: Shell Exec - Timeout (Short)")
    print("=" * 60)
    
    # Test a command that should complete quickly
    cmd = "sleep 1 && echo 'Completed'"
    
    print(f"Command: {cmd} (2 second timeout)")
    start_time = time.time()
    result = await shell_exec(cmd, timeout=2)
    end_time = time.time()
    
    print(f"Execution time: {end_time - start_time:.2f} seconds")
    print(f"Success: {result['success']}")
    print(f"Exit code: {result.get('exit_code', 'N/A')}")
    
    if result['success']:
        stdout = result.get('stdout', '').strip()
        print(f"Output: {stdout}")
    else:
        print(f"Error: {result.get('stderr', 'Unknown error')}")
        if 'timeout' in result.get('error', '').lower():
            print("Command was terminated due to timeout")
    
    print()


async def test_command_with_pipes():
    """Test commands with pipes and redirections."""
    print("=" * 60)
    print("TEST: Shell Exec - Pipes and Redirections")
    print("=" * 60)
    
    commands = [
        "echo 'line1\\nline2\\nline3' | wc -l",
        "ls | head -5",
        "echo 'test' | tr 'a-z' 'A-Z'",
        "find . -name '*.py' 2>/dev/null | wc -l"
    ]
    
    for cmd in commands:
        print(f"\nCommand: {cmd}")
        start_time = time.time()
        result = await shell_exec(cmd)
        end_time = time.time()
        
        print(f"Execution time: {end_time - start_time:.2f} seconds")
        print(f"Success: {result['success']}")
        
        if result['success']:
            stdout = result.get('stdout', '').strip()
            print(f"Output: {stdout}")
        else:
            stderr = result.get('stderr', '')
            print(f"Error: {stderr}")
    
    print()


async def test_error_handling():
    """Test error handling with invalid commands."""
    print("=" * 60)
    print("TEST: Shell Exec - Error Handling")
    print("=" * 60)
    
    error_commands = [
        "nonexistent_command_12345",
        "ls /nonexistent/directory/path",
        "cat /nonexistent/file.txt",
        "python -c 'import nonexistent_module'"
    ]
    
    for cmd in error_commands:
        print(f"\nCommand: {cmd}")
        start_time = time.time()
        result = await shell_exec(cmd)
        end_time = time.time()
        
        print(f"Execution time: {end_time - start_time:.2f} seconds")
        print(f"Success: {result['success']}")
        print(f"Exit code: {result.get('exit_code', 'N/A')}")
        
        if not result['success']:
            stderr = result.get('stderr', '')
            print(f"Error (expected): {stderr[:100]}{'...' if len(stderr) > 100 else ''}")
        else:
            print("Unexpected success!")
    
    print()


async def test_python_execution():
    """Test Python command execution."""
    print("=" * 60)
    print("TEST: Shell Exec - Python Commands")
    print("=" * 60)
    
    python_commands = [
        "python3 --version",
        "python3 -c 'print(\"Hello from Python\")'",
        "python3 -c 'import sys; print(f\"Python path: {sys.executable}\")'",
        "python3 -c 'import json; print(json.dumps({\"test\": \"data\", \"number\": 42}))'"
    ]
    
    for cmd in python_commands:
        print(f"\nCommand: {cmd}")
        start_time = time.time()
        result = await shell_exec(cmd)
        end_time = time.time()
        
        print(f"Execution time: {end_time - start_time:.2f} seconds")
        print(f"Success: {result['success']}")
        
        if result['success']:
            stdout = result.get('stdout', '').strip()
            print(f"Output: {stdout}")
        else:
            stderr = result.get('stderr', '')
            print(f"Error: {stderr}")
    
    print()


async def main():
    """Run all shell execution tests."""
    print("SHELL EXECUTION TEST SUITE")
    print("=" * 60)
    print(f"Running tests at: {Path.cwd()}")
    print(f"Test time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    await test_simple_commands()
    await test_directory_listing()
    await test_working_directory()
    await test_command_timeout()
    await test_command_with_pipes()
    await test_error_handling()
    await test_python_execution()
    
    print("=" * 60)
    print("ALL SHELL EXECUTION TESTS COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())