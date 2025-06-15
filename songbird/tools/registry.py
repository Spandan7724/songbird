# songbird/tools/registry.py
"""
Tool registry for Songbird external tools.
Provides JSON schema definitions for tools that LLMs can invoke.
"""
from typing import Dict, Any, List
from .file_search import file_search
from .file_operations import file_read, file_edit


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
    }
}

# Tool function mapping
TOOL_FUNCTIONS = {
    "file_search": file_search,
    "file_read": file_read,
    "file_edit": file_edit
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