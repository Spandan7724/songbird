# Tool Test Scripts

This directory contains individual test scripts for all Songbird tools. Each script can be run independently to test specific tool functionality and see their outputs.

## Available Test Scripts

- `test_tree.py` - Test tree tool with various parameters
- `test_ls.py` - Test ls tool with different options
- `test_file_operations.py` - Test file read/create/edit operations
- `test_search_tools.py` - Test file_search, glob, grep tools
- `test_shell_exec.py` - Test shell command execution
- `test_todo_tools.py` - Test todo management tools
- `run_all_tests.py` - Run all tests sequentially

## Usage

### Run Individual Tests
```bash
# From the project root
python -m tool_test.test_tree         # Test tree tool functionality
python -m tool_test.test_ls           # Test ls tool functionality  
python -m tool_test.test_file_operations  # Test file read/create/edit
python -m tool_test.test_search_tools     # Test file_search, glob, grep
python -m tool_test.test_shell_exec       # Test shell command execution
python -m tool_test.test_todo_tools       # Test todo management
```

### Run All Tests
```bash
python -m tool_test.run_all_tests     # Run complete test suite
```

### Quick Start
Try the tree tool test to see hierarchical project structure:
```bash
python -m tool_test.test_tree
```

## Test Structure

Each test script:
1. Imports the tool function directly from the tools module
2. Runs multiple test scenarios with different parameters
3. Displays formatted output showing tool behavior
4. Includes error handling for edge cases
5. Shows timing information where relevant

## Requirements

- Run from the project root directory
- Ensure all dependencies are installed (`uv sync`)
- Some tests may create temporary files (cleaned up automatically)