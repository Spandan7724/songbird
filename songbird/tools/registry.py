# songbird/tools/registry.py
"""
Tool registry for Songbird external tools.
Provides JSON schema definitions for tools that LLMs can invoke.
"""
from typing import Dict, Any, List
from .file_search import file_search
from .file_operations import file_read, file_edit, file_create
from .shell_exec import shell_exec
from .todo_tools import todo_read, todo_write
from .glob_tool import glob_pattern
from .grep_tool import grep_search
from .ls_tool import ls_directory
from .multiedit_tool import multi_edit


# Tool schema definitions for LLMs
TOOL_SCHEMAS = {
    "file_search": {
        "type": "function",
        "function": {
            "name": "file_search",
            "description": "Search for text patterns or files. Use glob patterns (*.py) to find files, or any text to search content. Powered by ripgrep for speed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Search pattern - use glob (*.py) for files, or any text/regex for content search"
                    },
                    "directory": {
                        "type": "string", 
                        "description": "Directory to search in (default: current directory)",
                        "default": "."
                    },
                    "file_type": {
                        "type": "string",
                        "description": "Filter by file type: py, js, md, txt, json, yaml, etc. (optional)"
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Whether search is case sensitive (default: false)",
                        "default": False
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results to return (default: 50)",
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
                        "description": "Whether to create a .bak backup file (default: false)",
                        "default": False
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
    },
    "todo_read": {
        "type": "function",
        "function": {
            "name": "todo_read",
            "description": "Read and display the current session's todo list. Use this to check current tasks and their status. Shows tasks in a formatted table with priority, status, and creation date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Optional session ID to filter todos (defaults to current session)"
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by task status: 'pending', 'in_progress', or 'completed'",
                        "enum": ["pending", "in_progress", "completed"]
                    },
                    "show_completed": {
                        "type": "boolean",
                        "description": "Whether to include completed tasks in the display (default: false)",
                        "default": False
                    }
                },
                "required": []
            }
        }
    },
    "todo_write": {
        "type": "function", 
        "function": {
            "name": "todo_write",
            "description": "Create, update, and manage todo items. Use this to add new tasks, update existing ones, mark tasks as completed, or change priority. To update existing todos, either provide the exact ID from todo_read, or use the exact task content - the system will automatically match by content if no ID is provided. Supports intelligent task management with automatic prioritization.",
            "parameters": {
                "type": "object",
                "properties": {
                    "todos": {
                        "type": "array",
                        "description": "List of todo items to create or update",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {
                                    "type": "string",
                                    "description": "Optional ID for existing todo to update. If not provided, the system will try to match by content. Use IDs from todo_read for guaranteed updates."
                                },
                                "content": {
                                    "type": "string",
                                    "description": "The task description or content"
                                },
                                "status": {
                                    "type": "string",
                                    "description": "Task status: pending, in_progress, or completed"
                                },
                                "priority": {
                                    "type": "string",
                                    "description": "Task priority: high, medium, or low. If not specified, will be automatically determined based on content."
                                }
                            },
                            "required": ["content"]
                        }
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Optional session ID for the todos (defaults to current session)"
                    }
                },
                "required": ["todos"]
            }
        }
    },
    "glob": {
        "type": "function",
        "function": {
            "name": "glob",
            "description": "Find files using glob patterns with enhanced functionality. Supports recursive searching and file filtering. Use patterns like '**/*.py', 'src/**/*.js', '*.md' to find files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to match files (e.g., '**/*.py', 'src/**/*.js', '*.md')"
                    },
                    "directory": {
                        "type": "string",
                        "description": "Directory to search in (default: current directory)",
                        "default": "."
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Whether to search recursively (default: True)",
                        "default": True
                    },
                    "include_hidden": {
                        "type": "boolean",
                        "description": "Whether to include hidden files/directories (default: False)",
                        "default": False
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 100)",
                        "default": 100
                    }
                },
                "required": ["pattern"]
            }
        }
    },
    "grep": {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search for patterns in file contents with advanced regex support. More powerful than file_search for complex pattern matching and content analysis. Supports context lines and various search options.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Text pattern or regex to search for in file contents"
                    },
                    "directory": {
                        "type": "string",
                        "description": "Directory to search in (default: current directory)",
                        "default": "."
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Glob pattern to filter files (e.g., '*.py', '*.{js,ts}')"
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Whether search is case sensitive (default: False)",
                        "default": False
                    },
                    "whole_word": {
                        "type": "boolean",
                        "description": "Whether to match whole words only (default: False)",
                        "default": False
                    },
                    "regex": {
                        "type": "boolean",
                        "description": "Whether pattern is a regular expression (default: False)",
                        "default": False
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "Number of context lines to show around matches (default: 0)",
                        "default": 0
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 100)",
                        "default": 100
                    }
                },
                "required": ["pattern"]
            }
        }
    },
    "ls": {
        "type": "function",
        "function": {
            "name": "ls",
            "description": "List directory contents with enhanced formatting and options. Provides detailed file information, sorting options, and beautiful Rich-formatted output. More advanced than basic shell ls command.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to list (default: current directory)",
                        "default": "."
                    },
                    "show_hidden": {
                        "type": "boolean",
                        "description": "Whether to show hidden files/directories (default: False)",
                        "default": False
                    },
                    "long_format": {
                        "type": "boolean",
                        "description": "Whether to show detailed information (default: False)",
                        "default": False
                    },
                    "sort_by": {
                        "type": "string",
                        "description": "Sort criteria: 'name', 'size', 'modified', 'type' (default: 'name')",
                        "enum": ["name", "size", "modified", "type"],
                        "default": "name"
                    },
                    "reverse": {
                        "type": "boolean",
                        "description": "Whether to reverse sort order (default: False)",
                        "default": False
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Whether to list subdirectories recursively (default: False)",
                        "default": False
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum depth for recursive listing (default: 3)",
                        "default": 3
                    },
                    "file_type_filter": {
                        "type": "string",
                        "description": "Filter by file type: 'files', 'dirs', or null for both",
                        "enum": ["files", "dirs"]
                    }
                },
                "required": []
            }
        }
    },
    "multi_edit": {
        "type": "function",
        "function": {
            "name": "multi_edit",
            "description": "Perform multiple file edits in a single atomic operation. Allows editing multiple files simultaneously with preview, backup, and rollback capabilities. Essential for large refactoring operations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "edits": {
                        "type": "array",
                        "description": "List of edit operations to perform",
                        "items": {
                            "type": "object",
                            "properties": {
                                "file_path": {
                                    "type": "string",
                                    "description": "Path to the file to edit/create/delete"
                                },
                                "new_content": {
                                    "type": "string",
                                    "description": "New content for the file (required for edit/create operations)"
                                },
                                "operation": {
                                    "type": "string",
                                    "description": "Type of operation: 'edit', 'create', or 'delete' (default: 'edit')"
                                },
                                "encoding": {
                                    "type": "string",
                                    "description": "File encoding (default: 'utf-8')"
                                }
                            },
                            "required": ["file_path"]
                        }
                    },
                    "create_backup": {
                        "type": "boolean",
                        "description": "Whether to create backup files (default: False)",
                        "default": False
                    },
                    "preview_only": {
                        "type": "boolean",
                        "description": "Whether to only show previews without applying (default: False)",
                        "default": False
                    },
                    "atomic": {
                        "type": "boolean",
                        "description": "Whether to apply all edits atomically (default: True)",
                        "default": True
                    }
                },
                "required": ["edits"]
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
    "shell_exec": shell_exec,
    "todo_read": todo_read,
    "todo_write": todo_write,
    "glob": glob_pattern,
    "grep": grep_search,
    "ls": ls_directory,
    "multi_edit": multi_edit
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