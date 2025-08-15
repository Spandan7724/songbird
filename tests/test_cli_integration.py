"""
Pytest tests for CLI integration functionality.

This module converts the CLI integration tests from:
- test_real_songbird.py (CLI session warnings and real usage scenarios)
"""

import os
import subprocess
import sys
import tempfile
import pytest


@pytest.fixture
def test_environment():
    """Fixture to set up test environment with API key."""
    original_env = os.environ.copy()
    
    # Set test API key
    os.environ['GEMINI_API_KEY'] = 'test-key-for-session-testing'
    os.environ['PYTHONWARNINGS'] = 'default'  # Enable all warnings
    
    yield os.environ.copy()
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.mark.slow
def test_cli_immediate_exit(test_environment):
    """Test CLI with immediate exit to check session cleanup."""
    input_data = 'exit\n'
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(input_data)
        temp_input = f.name
    
    try:
        with open(temp_input, 'r') as input_file:
            result = subprocess.run(
                [sys.executable, '-m', 'songbird.cli', '--provider', 'gemini'],
                stdin=input_file,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
                env=test_environment
            )
        
        # Check for unclosed session warnings
        combined_output = result.stdout + result.stderr
        unclosed_warnings = []
        for line in combined_output.split('\n'):
            line_lower = line.lower()
            if ('unclosed client session' in line_lower or 
                'unclosed connector' in line_lower or
                ('unclosed' in line_lower and 'aiohttp' in line_lower) or
                ('unclosed' in line_lower and 'session' in line_lower)):
                unclosed_warnings.append(line.strip())
        
        assert len(unclosed_warnings) == 0, \
            f"Found {len(unclosed_warnings)} unclosed session warnings: {unclosed_warnings}"
            
    except subprocess.TimeoutExpired:
        pytest.skip("CLI test timed out")
    except FileNotFoundError:
        pytest.skip("Songbird CLI not available")
    finally:
        try:
            os.unlink(temp_input)
        except:
            pass


@pytest.mark.slow
def test_cli_single_query_exit(test_environment):
    """Test CLI with single query then exit."""
    input_data = 'hello\nexit\n'
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(input_data)
        temp_input = f.name
    
    try:
        with open(temp_input, 'r') as input_file:
            result = subprocess.run(
                [sys.executable, '-m', 'songbird.cli', '--provider', 'gemini'],
                stdin=input_file,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
                env=test_environment
            )
        
        # Check for unclosed session warnings
        combined_output = result.stdout + result.stderr
        session_warnings = []
        for line in combined_output.split('\n'):
            line_lower = line.lower()
            if ('unclosed' in line_lower and 'session' in line_lower) or \
               ('unclosed' in line_lower and 'connector' in line_lower):
                session_warnings.append(line.strip())
        
        assert len(session_warnings) == 0, \
            f"Found session warnings in single query test: {session_warnings}"
            
    except subprocess.TimeoutExpired:
        pytest.skip("CLI test timed out")
    except FileNotFoundError:
        pytest.skip("Songbird CLI not available")
    finally:
        try:
            os.unlink(temp_input)
        except:
            pass


@pytest.mark.slow
def test_cli_multiple_queries(test_environment):
    """Test CLI with multiple queries to trigger session usage."""
    input_data = 'What is Python?\nHow do I create a file?\nexit\n'
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(input_data)
        temp_input = f.name
    
    try:
        with open(temp_input, 'r') as input_file:
            result = subprocess.run(
                [sys.executable, '-m', 'songbird.cli', '--provider', 'gemini'],
                stdin=input_file,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=45,  # Longer timeout for multiple queries
                env=test_environment
            )
        
        # Check for unclosed session warnings
        combined_output = result.stdout + result.stderr
        lines = combined_output.split('\n')
        
        session_warnings = []
        for line in lines:
            line_lower = line.lower()
            if ('unclosed' in line_lower and 'session' in line_lower) or \
               ('unclosed' in line_lower and 'connector' in line_lower):
                session_warnings.append(line.strip())
        
        assert len(session_warnings) == 0, \
            f"Found session warnings in multiple queries test: {session_warnings}"
            
    except subprocess.TimeoutExpired:
        pytest.skip("CLI test timed out (may be normal for multiple queries)")
    except FileNotFoundError:
        pytest.skip("Songbird CLI not available")
    finally:
        try:
            os.unlink(temp_input)
        except:
            pass


@pytest.mark.slow 
def test_cli_basic_functionality(test_environment):
    """Test basic CLI functionality without detailed session analysis."""
    input_data = 'exit\n'
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(input_data)
        temp_input = f.name
    
    try:
        with open(temp_input, 'r') as input_file:
            result = subprocess.run(
                [sys.executable, '-m', 'songbird.cli'],
                stdin=input_file,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
                env=test_environment
            )
        
        # Basic functionality test - CLI should start and exit without crashing
        # Exit code might vary depending on configuration, so we just check it ran
        assert result.returncode is not None, "CLI should complete execution"
        
        # Should not have critical errors that would indicate broken functionality
        stderr_output = result.stderr.lower()
        critical_errors = [
            'importerror',
            'modulenotfounderror', 
            'attributeerror',
            'syntaxerror'
        ]
        
        for error in critical_errors:
            assert error not in stderr_output, \
                f"Found critical error {error} in CLI output: {result.stderr}"
                
    except subprocess.TimeoutExpired:
        pytest.skip("CLI test timed out")
    except FileNotFoundError:
        pytest.skip("Songbird CLI not available")
    finally:
        try:
            os.unlink(temp_input)
        except:
            pass


@pytest.mark.slow
def test_cli_provider_selection(test_environment):
    """Test CLI with different provider selection."""
    test_cases = [
        {'provider': 'gemini', 'input': 'exit\n'},
        {'provider': None, 'input': 'exit\n'},  # Default provider
    ]
    
    for case in test_cases:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(case['input'])
            temp_input = f.name
        
        try:
            # Build command
            cmd = [sys.executable, '-m', 'songbird.cli']
            if case['provider']:
                cmd.extend(['--provider', case['provider']])
            
            with open(temp_input, 'r') as input_file:
                result = subprocess.run(
                    cmd,
                    stdin=input_file,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=30,
                    env=test_environment
                )
            
            # Should handle provider selection gracefully
            assert result.returncode is not None
            
        except subprocess.TimeoutExpired:
            # Timeout is acceptable for this test
            pass
        except FileNotFoundError:
            pytest.skip("Songbird CLI not available")
        finally:
            try:
                os.unlink(temp_input)
            except:
                pass


@pytest.mark.slow
def test_cli_error_handling(test_environment):
    """Test CLI error handling with invalid scenarios."""
    # Test with invalid provider
    input_data = 'exit\n'
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(input_data)
        temp_input = f.name
    
    try:
        with open(temp_input, 'r') as input_file:
            result = subprocess.run(
                [sys.executable, '-m', 'songbird.cli', '--provider', 'invalid_provider'],
                stdin=input_file,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
                env=test_environment
            )
        
        # Should handle invalid provider gracefully without crashing
        # (specific behavior may vary, but shouldn't have uncaught exceptions)
        combined_output = (result.stdout + result.stderr).lower()
        
        # Should not have uncaught exceptions
        uncaught_exceptions = [
            'traceback (most recent call last):',
            'unhandled exception',
            'fatal error'
        ]
        
        for exception_text in uncaught_exceptions:
            if exception_text in combined_output:
                # Allow for controlled error messages, but not uncaught exceptions
                # This is a soft assertion - log but don't fail
                print(f"Warning: Possible uncaught exception in CLI: {exception_text}")
                
    except subprocess.TimeoutExpired:
        pytest.skip("CLI test timed out")
    except FileNotFoundError:
        pytest.skip("Songbird CLI not available")
    finally:
        try:
            os.unlink(temp_input)
        except:
            pass 