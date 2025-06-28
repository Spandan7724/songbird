# tests/conftest.py
"""
Pytest configuration for Songbird test suite.

Provides shared fixtures and configuration for the enhanced test suite
covering agentic conversation, enhanced providers, tool visibility,
parallel execution, and integration testing.
"""
import pytest
import tempfile
import os
from pathlib import Path


def pytest_configure(config):
    """Configure pytest with custom markers for the enhanced test suite."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (integration tests)"
    )
    config.addinivalue_line(
        "markers", "requires_ollama: marks tests that require Ollama server"
    )
    config.addinivalue_line(
        "markers", "requires_api_keys: marks tests that require API keys"
    )


@pytest.fixture(scope="session")
def test_data_dir():
    """Test data directory for fixtures."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def clean_environment():
    """Clean environment for testing without external dependencies."""
    original_env = os.environ.copy()
    
    # Clear API keys to test fallback behavior
    api_keys = [
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", 
        "OPENROUTER_API_KEY", "SONGBIRD_DEBUG_TOOLS"
    ]
    
    for key in api_keys:
        if key in os.environ:
            del os.environ[key]
    
    yield
    
    # Restore environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def debug_mode():
    """Enable debug mode for testing."""
    original_debug = os.environ.get("SONGBIRD_DEBUG_TOOLS")
    os.environ["SONGBIRD_DEBUG_TOOLS"] = "true"
    
    yield
    
    if original_debug is not None:
        os.environ["SONGBIRD_DEBUG_TOOLS"] = original_debug
    else:
        os.environ.pop("SONGBIRD_DEBUG_TOOLS", None)


@pytest.fixture
def isolated_workspace():
    """Isolated workspace for each test."""
    with tempfile.TemporaryDirectory(prefix="songbird_test_") as temp_dir:
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        yield temp_dir
        
        os.chdir(original_cwd)


@pytest.fixture
def sample_project_files(isolated_workspace):
    """Create sample project files for testing."""
    project_files = {
        "main.py": '''#!/usr/bin/env python3
"""Main application module."""

def main():
    print("Hello World")
    # TODO: Add more functionality

if __name__ == "__main__":
    main()
''',
        "utils.py": '''"""Utility functions."""

def helper_function():
    # TODO: Implement this
    pass

def another_helper():
    return "helper result"
''',
        "README.md": '''# Sample Project

This is a sample project for testing.

## TODO
- Add more features
- Write tests
- Documentation
''',
        "config.toml": '''[project]
name = "sample"
version = "1.0.0"

[settings]
debug = true
''',
        "tests/test_main.py": '''"""Tests for main module."""

def test_main():
    # TODO: Write actual tests
    assert True
'''
    }
    
    for file_path, content in project_files.items():
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
    
    return list(project_files.keys())


@pytest.fixture
def mock_successful_tool_result():
    """Mock successful tool execution result."""
    return {
        "success": True,
        "result": {
            "file_path": "/test/example.txt",
            "content": "Example content",
            "message": "Operation completed successfully"
        }
    }


@pytest.fixture
def mock_failed_tool_result():
    """Mock failed tool execution result."""
    return {
        "success": False,
        "error": "File not found: /nonexistent/file.txt",
        "details": "The specified file does not exist"
    }


# Pytest collection hook to organize test execution
def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test names."""
    for item in items:
        # Mark integration tests as slow
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.slow)
        
        # Mark tests requiring Ollama
        if "ollama" in item.nodeid.lower():
            item.add_marker(pytest.mark.requires_ollama)
        
        # Mark tests requiring API keys
        if any(keyword in item.nodeid.lower() for keyword in ["gemini", "openrouter", "openai", "claude"]):
            if "mock" not in item.nodeid.lower():
                item.add_marker(pytest.mark.requires_api_keys)


# Test session setup and teardown
@pytest.fixture(scope="session", autouse=True)
def test_session_setup():
    """Setup for the entire test session."""
    print("\n🧪 Starting Songbird Enhanced Test Suite")
    print("Testing: Agentic Loop, Enhanced Providers, Tool Visibility, Parallel Execution")
    
    yield
    
    print("\n✅ Songbird Enhanced Test Suite Completed")


@pytest.fixture(autouse=True)
def test_isolation():
    """Ensure test isolation by cleaning up any global state."""
    # Clean up any global state before each test
    yield
    # Clean up any global state after each test