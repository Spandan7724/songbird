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
            "description": "Search for text patterns in files using ripgrep. Returns structured results with file paths, line numbers, and matched content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Text pattern to search for (supports regex)"
                    },
                    "directory": {
                        "type": "string", 
                        "description": "Directory path to search in (defaults to current working directory)",
                        "default": "."
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
            "description": "Read file contents for analysis. Supports reading specific line ranges.",
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
            "description": "Edit a file with diff preview. Shows changes with + (additions) and - (deletions) before applying.",
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
            "description": "Execute shell commands safely with output capture. Useful for running tests, builds, git commands, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute"
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