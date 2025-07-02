#!/usr/bin/env python3
"""
Test runner utilities for tool testing.
Provides common functions and helpers for test scripts.
"""

import time
from typing import Dict, Any, List, Callable
from pathlib import Path


class TestRunner:
    """Helper class for running tool tests with timing and formatting."""
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.start_time = None
        self.results = []
    
    def start(self):
        """Start the test suite."""
        self.start_time = time.time()
        print(f"{self.test_name.upper()} TEST SUITE")
        print("=" * 60)
        print(f"Running tests at: {Path.cwd()}")
        print(f"Test time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
    
    async def run_test(self, test_func: Callable, test_description: str) -> Dict[str, Any]:
        """Run a single test function with timing and error handling."""
        print("=" * 60)
        print(f"TEST: {test_description}")
        print("=" * 60)
        
        start_time = time.time()
        success = True
        error = None
        result = None
        
        try:
            result = await test_func()
        except Exception as e:
            success = False
            error = str(e)
            print(f"ERROR: {error}")
        
        end_time = time.time()
        duration = end_time - start_time
        
        test_result = {
            "description": test_description,
            "success": success,
            "duration": duration,
            "error": error,
            "result": result
        }
        
        self.results.append(test_result)
        
        print(f"\nTest Duration: {duration:.2f} seconds")
        print(f"Status: {'✅ PASSED' if success else '❌ FAILED'}")
        print()
        
        return test_result
    
    def finish(self):
        """Complete the test suite and show summary."""
        if self.start_time is None:
            return
        
        total_time = time.time() - self.start_time
        passed = sum(1 for r in self.results if r['success'])
        failed = len(self.results) - passed
        
        print("=" * 60)
        print(f"{self.test_name.upper()} TESTS COMPLETED")
        print("=" * 60)
        print(f"Total tests: {len(self.results)}")
        print(f"Passed: {passed} ✅")
        print(f"Failed: {failed} ❌")
        print(f"Total time: {total_time:.2f} seconds")
        print(f"Success rate: {(passed/len(self.results))*100:.1f}%" if self.results else "N/A")
        print("=" * 60)


def format_tool_result(result: Dict[str, Any], show_details: bool = True) -> str:
    """Format a tool result for display."""
    if not isinstance(result, dict):
        return str(result)
    
    lines = []
    lines.append(f"Success: {result.get('success', 'unknown')}")
    
    if 'error' in result and result['error']:
        lines.append(f"Error: {result['error']}")
    
    if show_details and result.get('success', False):
        # Add specific details based on result type
        if 'total_items' in result:
            lines.append(f"Total items: {result['total_items']}")
        
        if 'file_count' in result and 'dir_count' in result:
            lines.append(f"Files: {result['file_count']}, Directories: {result['dir_count']}")
        
        if 'matches' in result:
            lines.append(f"Matches found: {len(result['matches'])}")
        
        if 'files' in result:
            lines.append(f"Files found: {len(result['files'])}")
        
        if 'todos' in result:
            lines.append(f"Todos: {len(result['todos'])}")
        
        if 'file_size' in result:
            lines.append(f"File size: {result['file_size']} bytes")
        
        if 'exit_code' in result:
            lines.append(f"Exit code: {result['exit_code']}")
    
    return "\n".join(lines)


def print_test_header(test_name: str, description: str = ""):
    """Print a formatted test header."""
    print("=" * 60)
    print(f"TEST: {test_name}")
    if description:
        print(f"Description: {description}")
    print("=" * 60)


def print_test_result(result: Dict[str, Any], execution_time: float):
    """Print formatted test result."""
    print(f"\nExecution time: {execution_time:.2f} seconds")
    print(format_tool_result(result, show_details=True))


async def run_tool_test(tool_func: Callable, test_name: str, *args, **kwargs) -> Dict[str, Any]:
    """Run a tool function with timing and error handling."""
    print_test_header(test_name)
    
    start_time = time.time()
    
    try:
        result = await tool_func(*args, **kwargs)
        end_time = time.time()
        
        print_test_result(result, end_time - start_time)
        return result
        
    except Exception as e:
        end_time = time.time()
        error_result = {
            "success": False,
            "error": str(e),
            "execution_time": end_time - start_time
        }
        
        print_test_result(error_result, end_time - start_time)
        return error_result


def compare_results(result1: Dict[str, Any], result2: Dict[str, Any], comparison_name: str):
    """Compare two tool results and print differences."""
    print("=" * 60)
    print(f"COMPARISON: {comparison_name}")
    print("=" * 60)
    
    # Compare success status
    if result1.get('success') != result2.get('success'):
        print(f"Success status differs: {result1.get('success')} vs {result2.get('success')}")
    
    # Compare counts if available
    for key in ['total_items', 'file_count', 'dir_count']:
        if key in result1 and key in result2:
            val1, val2 = result1[key], result2[key]
            if val1 != val2:
                print(f"{key} differs: {val1} vs {val2}")
            else:
                print(f"{key}: {val1} (same)")
    
    # Compare list lengths
    for key in ['matches', 'files', 'todos']:
        if key in result1 and key in result2:
            len1, len2 = len(result1[key]), len(result2[key])
            if len1 != len2:
                print(f"{key} count differs: {len1} vs {len2}")
            else:
                print(f"{key} count: {len1} (same)")
    
    print()


# Common test data generators
def generate_test_files_list() -> List[str]:
    """Generate a list of common test file patterns."""
    return [
        "*.py",
        "*.md", 
        "*.json",
        "*.txt",
        "*.toml",
        "*.yaml",
        "*.yml"
    ]


def generate_test_search_terms() -> List[str]:
    """Generate common search terms for testing."""
    return [
        "def",
        "class",
        "import",
        "async",
        "TODO",
        "FIXME",
        "print",
        "return"
    ]


# Export main utilities
__all__ = [
    'TestRunner',
    'format_tool_result',
    'print_test_header', 
    'print_test_result',
    'run_tool_test',
    'compare_results',
    'generate_test_files_list',
    'generate_test_search_terms'
]