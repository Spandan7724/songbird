#!/usr/bin/env python3
"""
Run all tool tests sequentially.
This script executes all individual test scripts and provides a summary.
"""

import asyncio
import subprocess
import sys
import time
from pathlib import Path

# Test scripts to run (in order)
TEST_SCRIPTS = [
    "test_tree.py",
    "test_ls.py", 
    "test_file_operations.py",
    "test_search_tools.py",
    "test_shell_exec.py",
    "test_todo_tools.py"
]


async def run_test_script(script_name):
    """Run a single test script and capture its output."""
    print(f"{'='*80}")
    print(f"RUNNING: {script_name}")
    print(f"{'='*80}")
    
    start_time = time.time()
    
    try:
        # Run the test script as a subprocess
        result = subprocess.run(
            [sys.executable, "-m", f"tool_test.{script_name[:-3]}"],  # Remove .py extension
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout per test
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"Exit code: {result.returncode}")
        print(f"Duration: {duration:.2f} seconds")
        
        if result.returncode == 0:
            print("STATUS: ✅ PASSED")
        else:
            print("STATUS: ❌ FAILED")
        
        # Always show some output
        if result.stdout:
            print("\nSTDOUT:")
            print(result.stdout)
        
        if result.stderr:
            print("\nSTDERR:")
            print(result.stderr)
        
        return {
            "script": script_name,
            "success": result.returncode == 0,
            "duration": duration,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
        
    except subprocess.TimeoutExpired:
        end_time = time.time()
        duration = end_time - start_time
        print(f"STATUS: ⏰ TIMEOUT after {duration:.2f} seconds")
        
        return {
            "script": script_name,
            "success": False,
            "duration": duration,
            "stdout": "",
            "stderr": "Test timed out after 5 minutes"
        }
        
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        print(f"STATUS: 💥 ERROR - {str(e)}")
        
        return {
            "script": script_name,
            "success": False,
            "duration": duration,
            "stdout": "",
            "stderr": str(e)
        }


def print_summary(results):
    """Print a summary of all test results."""
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}")
    
    total_tests = len(results)
    passed_tests = sum(1 for r in results if r['success'])
    failed_tests = total_tests - passed_tests
    total_duration = sum(r['duration'] for r in results)
    
    print(f"Total tests: {total_tests}")
    print(f"Passed: {passed_tests} ✅")
    print(f"Failed: {failed_tests} ❌")
    print(f"Total duration: {total_duration:.2f} seconds")
    print(f"Success rate: {(passed_tests/total_tests)*100:.1f}%")
    
    print(f"\n{'='*80}")
    print("INDIVIDUAL RESULTS")
    print(f"{'='*80}")
    
    for result in results:
        status_icon = "✅" if result['success'] else "❌"
        print(f"{status_icon} {result['script']:<25} {result['duration']:>8.2f}s")
        
        if not result['success'] and result['stderr']:
            print(f"   Error: {result['stderr'][:100]}{'...' if len(result['stderr']) > 100 else ''}")
    
    print(f"\n{'='*80}")
    if failed_tests == 0:
        print("🎉 ALL TESTS PASSED!")
    else:
        print(f"⚠️  {failed_tests} TEST(S) FAILED")
    print(f"{'='*80}")


async def main():
    """Run all test scripts and provide summary."""
    print("SONGBIRD TOOL TEST SUITE")
    print(f"{'='*80}")
    print("Running all tool tests")
    print(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Working directory: {Path.cwd()}")
    print(f"Python executable: {sys.executable}")
    print(f"Scripts to run: {len(TEST_SCRIPTS)}")
    print(f"{'='*80}")
    
    overall_start_time = time.time()
    results = []
    
    # Run each test script
    for script in TEST_SCRIPTS:
        try:
            result = await run_test_script(script)
            results.append(result)
            
            # Small delay between tests
            await asyncio.sleep(1)
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Test run interrupted by user")
            break
        except Exception as e:
            print(f"\n\n💥 Unexpected error running {script}: {e}")
            results.append({
                "script": script,
                "success": False,
                "duration": 0,
                "stdout": "",
                "stderr": str(e)
            })
    
    overall_end_time = time.time()
    overall_duration = overall_end_time - overall_start_time
    
    # Print summary
    print_summary(results)
    
    print(f"\nOverall test run duration: {overall_duration:.2f} seconds")
    print(f"Completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Exit with appropriate code
    failed_count = sum(1 for r in results if not r['success'])
    sys.exit(0 if failed_count == 0 else 1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test suite interrupted by user")
        sys.exit(130)  # Standard exit code for Ctrl+C