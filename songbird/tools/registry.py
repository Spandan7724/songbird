# songbird/tools/registry.py
"""
Tool registry for Songbird external tools.
Provides JSON schema definitions for tools that LLMs can invoke.
"""
from typing import Dict, Any, List
from .file_search import file_search
from .file_operations import file_read, file_edit, file_create
from .shell_exec import shell_exec


# Tool schema definitions for LLMs
TOOL_SCHEMAS = {
    "file_search": {
        "type": "function",
        "function": {
            "name": "file_search",
            "description": "Search for files, text patterns, functions, classes, or variables. Can find: filenames (e.g., 'test.py'), functions (e.g., 'calculate_total'), classes, text in files, or any code pattern. Automatically detects what you're looking for.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "What to search for - can be filename, function name, class name, or any text/code pattern"
                    },
                    "directory": {
                        "type": "string", 
                        "description": "Directory path to search in (defaults to current working directory)",
                        "default": "."
                    },
                    "search_type": {
                        "type": "string",
                        "description": "Type of search: 'auto' (default), 'filename', 'text', 'function', 'class', 'variable'",
                        "enum": ["auto", "filename", "text", "function", "class", "variable"],
                        "default": "auto"
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Optional glob pattern to filter files (e.g., '*.py' for Python files only)"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 50)",
                        "default": 50
                    }
                },
                "required": ["pattern"]
            }
        }
    },
    "file_read": {
        "type": "function",
        "function": {
            "name": "file_read",
            "description": "Read file contents for analysis. Supports reading specific line ranges. Use this when you need to examine the contents of a specific file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to read"
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Number of lines to read (optional)"
                    },
                    "start_line": {
                        "type": "integer", 
                        "description": "Starting line number, 1-indexed (optional)"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    "file_create": {
        "type": "function",
        "function": {
            "name": "file_create",
            "description": "Create a new file with specified content. Always use this when the user asks to create, write, or make a new file. If file already exists, will return an error.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the new file to create"
                    },
                    "content": {
                        "type": "string",
                        "description": "Complete content for the new file"
                    }
                },
                "required": ["file_path", "content"]
            }
        }
    },
    "file_edit": {
        "type": "function",
        "function": {
            "name": "file_edit",
            "description": "Edit an existing file with diff preview. Shows changes with + (additions) and - (deletions) before applying. Use this to modify existing files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to edit"
                    },
                    "new_content": {
                        "type": "string",
                        "description": "Complete new content for the file"
                    },
                    "create_backup": {
                        "type": "boolean",
                        "description": "Whether to create a .bak backup file (default: true)",
                        "default": True
                    }
                },
                "required": ["file_path", "new_content"]
            }
        }
    },
    "shell_exec": {
        "type": "function",
        "function": {
            "name": "shell_exec",
            "description": "Execute ANY shell/terminal command. Use this for: listing files (ls, dir), running Python scripts, git commands, installing packages (pip, npm), checking system info, navigating directories (pwd, cd), and ANY other terminal command. This is your primary tool for interacting with the system.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Any shell command to execute (e.g., 'ls -la', 'dir', 'python script.py', 'git status', 'pip install package')"
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "Working directory for command execution (optional)"
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Timeout in seconds (default: 30)",
                        "default": 30.0
                    }
                },
                "required": ["command"]
            }
        }
    }
}

# Tool function mapping
TOOL_FUNCTIONS = {
    "file_search": file_search,
    "file_read": file_read,
    "file_create": file_create,
    "file_edit": file_edit,
    "shell_exec": shell_exec
}


def get_tool_schemas() -> List[Dict[str, Any]]:
    """Get all available tool schemas for LLM function calling."""
    return list(TOOL_SCHEMAS.values())


def get_tool_function(name: str):
    """Get tool function by name."""
    return TOOL_FUNCTIONS.get(name)


def list_available_tools() -> List[str]:
    """List names of all available tools."""
    return list(TOOL_SCHEMAS.keys())