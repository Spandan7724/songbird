# Centralized tool registry for dynamic tool management and provider-agnostic schemas.

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from .file_search import file_search
from .file_operations import file_read, file_edit, file_create
from .shell_exec import shell_exec
from .todo_tools import todo_read, todo_write
from .glob_tool import glob_pattern
from .grep_tool import grep_search
from .ls_tool import ls_directory
from .multiedit_tool import multi_edit
from .tree_tool import tree_display


class ToolCategory(Enum):
    FILE_OPERATIONS = "file_operations"
    SEARCH = "search"
    SHELL = "shell"
    TASK_MANAGEMENT = "task_management"
    BULK_OPERATIONS = "bulk_operations"


@dataclass
class ToolDefinition:
    name: str
    function: Callable
    schema: Dict[str, Any]
    category: ToolCategory
    description: str
    examples: List[str] = field(default_factory=list)
    requires_confirmation: bool = False
    is_destructive: bool = False
    parallel_safe: bool = True
    produces_output: bool = False  # Whether tool produces immediate console output
    version: str = "1.0"
    
    def to_llm_schema(self, provider_format: str = "openai") -> Dict[str, Any]:
        if provider_format in ["openai", "anthropic", "openrouter"]:
            return {
                "type": "function",
                "function": self.schema
            }
        elif provider_format == "gemini":
            return {
                "name": self.schema["name"],
                "description": self.schema["description"],
                "parameters": self.schema["parameters"]
            }
        elif provider_format == "ollama":
            return {
                "type": "function",
                "function": self.schema
            }
        else:
            return {
                "type": "function", 
                "function": self.schema
            }


class ToolRegistry:
    
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._initialize_default_tools()
    
    def _initialize_default_tools(self):
        
        self.register_tool(ToolDefinition(
            name="file_read",
            function=file_read,
            category=ToolCategory.FILE_OPERATIONS,
            description="Read file contents with optional line range",
            schema={
                "name": "file_read",
                "description": "Read file contents with optional line range and metadata",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the file to read"
                        },
                        "lines": {
                            "type": "integer",
                            "description": "Number of lines to read (optional)",
                            "default": None
                        },
                        "start_line": {
                            "type": "integer", 
                            "description": "Starting line number (optional, 1-indexed)",
                            "default": 1
                        }
                    },
                    "required": ["file_path"]
                }
            },
            examples=["file_read('config.py')", "file_read('main.py', lines=50)"],
            parallel_safe=True,
            produces_output=False  # Silent tool - just returns data
        ))
        
        self.register_tool(ToolDefinition(
            name="file_create",
            function=file_create,
            category=ToolCategory.FILE_OPERATIONS,
            description="Create a new file with content",
            schema={
                "name": "file_create",
                "description": "Create a new file with specified content",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path where the file should be created"
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write to the file"
                        }
                    },
                    "required": ["file_path", "content"]
                }
            },
            examples=["file_create('main.py', 'print(\"Hello World\")')"],
            is_destructive=False,
            parallel_safe=False,  # File creation should be sequential
            produces_output=True  # Shows content preview
        ))
        
        self.register_tool(ToolDefinition(
            name="file_edit",
            function=file_edit,
            category=ToolCategory.FILE_OPERATIONS,
            description="Edit an existing file",
            schema={
                "name": "file_edit",
                "description": "Edit an existing file with new content",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the file to edit"
                        },
                        "new_content": {
                            "type": "string",
                            "description": "New content for the file"
                        },
                        "create_backup": {
                            "type": "boolean",
                            "description": "Whether to create a backup before editing",
                            "default": False
                        }
                    },
                    "required": ["file_path", "new_content"]
                }
            },
            examples=["file_edit('config.py', new_content)"],
            is_destructive=True,
            requires_confirmation=True,
            parallel_safe=False,
            produces_output=True  # Shows diff preview
        ))
        
        # Search Tools
        self.register_tool(ToolDefinition(
            name="file_search",
            function=file_search,
            category=ToolCategory.SEARCH,
            description="Search for files or content using patterns",
            schema={
                "name": "file_search",
                "description": "Search for text patterns or files. Use glob patterns (*.py) to find files, or any text to search content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Search pattern - use glob (*.py) for files, or any text/regex for content search"
                        },
                        "directory": {
                            "type": "string",
                            "description": "Directory to search in",
                            "default": "."
                        },
                        "file_type": {
                            "type": "string",
                            "description": "Filter by file type: py, js, md, txt, json, yaml, etc."
                        },
                        "case_sensitive": {
                            "type": "boolean",
                            "description": "Whether search is case sensitive",
                            "default": False
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum results to return",
                            "default": 50
                        }
                    },
                    "required": ["pattern"]
                }
            },
            examples=["file_search('*.py')", "file_search('TODO', file_type='py')"],
            parallel_safe=True,
            produces_output=True  # Shows search results table
        ))
        
        self.register_tool(ToolDefinition(
            name="glob",
            function=glob_pattern,
            category=ToolCategory.SEARCH,
            description="Find files using glob patterns",
            schema={
                "name": "glob",
                "description": "Find files and directories using glob patterns like **/*.py or src/**/*.js",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Glob pattern to match files (e.g., **/*.py, src/**/*.js)"
                        },
                        "directory": {
                            "type": "string",
                            "description": "Base directory to search from",
                            "default": "."
                        },
                        "recursive": {
                            "type": "boolean",
                            "description": "Whether to search recursively",
                            "default": True
                        },
                        "include_hidden": {
                            "type": "boolean",
                            "description": "Whether to include hidden files",
                            "default": False
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results",
                            "default": 100
                        }
                    },
                    "required": ["pattern"]
                }
            },
            examples=["glob('**/*.py')", "glob('src/**/*.js')"],
            parallel_safe=True,
            produces_output=True  # Shows file listing
        ))
        
        self.register_tool(ToolDefinition(
            name="grep",
            function=grep_search,
            category=ToolCategory.SEARCH,
            description="Search content with regex patterns",
            schema={
                "name": "grep",
                "description": "Search for text patterns in files using regex with context lines and filtering",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Regex pattern to search for"
                        },
                        "directory": {
                            "type": "string",
                            "description": "Directory to search in",
                            "default": "."
                        },
                        "file_pattern": {
                            "type": "string",
                            "description": "File pattern to search in (e.g., *.py)"
                        },
                        "case_sensitive": {
                            "type": "boolean",
                            "description": "Whether search is case sensitive",
                            "default": False
                        },
                        "whole_word": {
                            "type": "boolean",
                            "description": "Match whole words only",
                            "default": False
                        },
                        "regex": {
                            "type": "boolean",
                            "description": "Use regex pattern matching",
                            "default": True
                        },
                        "context_lines": {
                            "type": "integer",
                            "description": "Number of context lines around matches",
                            "default": 2
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results",
                            "default": 50
                        }
                    },
                    "required": ["pattern"]
                }
            },
            examples=["grep('function.*async')", "grep('TODO', file_pattern='*.py')"],
            parallel_safe=True,
            produces_output=True  # Shows search results with context
        ))
        
        self.register_tool(ToolDefinition(
            name="ls",
            function=ls_directory,
            category=ToolCategory.FILE_OPERATIONS,
            description="List directory contents with detailed file metadata, sorting, and filtering for file management tasks",
            schema={
                "name": "ls",
                "description": "List directory contents with detailed metadata including file sizes, permissions, modification dates. Ideal for file management, finding specific files, sorting by attributes, or when detailed file information is needed. Use when user asks 'what files are here', needs file sizes, wants to sort files, or requires file metadata.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path to list",
                            "default": "."
                        },
                        "show_hidden": {
                            "type": "boolean",
                            "description": "Include hidden files and directories",
                            "default": False
                        },
                        "long_format": {
                            "type": "boolean",
                            "description": "Show detailed file information",
                            "default": True
                        },
                        "sort_by": {
                            "type": "string",
                            "description": "Sort criteria: name, size, modified, type",
                            "default": "name"
                        },
                        "reverse": {
                            "type": "boolean",
                            "description": "Reverse sort order",
                            "default": False
                        },
                        "recursive": {
                            "type": "boolean",
                            "description": "List subdirectories recursively",
                            "default": False
                        },
                        "max_depth": {
                            "type": "integer",
                            "description": "Maximum recursion depth",
                            "default": 2
                        },
                        "file_type_filter": {
                            "type": "string",
                            "description": "Filter by type: file, dir, all",
                            "default": "all"
                        }
                    },
                    "required": ["path"]
                }
            },
            examples=["ls('.', long_format=True) # detailed file info", "ls('.', sort_by='size') # file management", "ls('.', recursive=True) # deep listing"],
            parallel_safe=True,
            produces_output=True  # Shows directory listing
        ))
        
        self.register_tool(ToolDefinition(
            name="tree",
            function=tree_display,
            category=ToolCategory.FILE_OPERATIONS,
            description="Display project structure and organization in hierarchical tree format for exploration and understanding",
            schema={
                "name": "tree",
                "description": "Display directory structure in hierarchical tree format. Ideal for project exploration, understanding codebase organization, explaining project structure, and getting architectural overviews. Use when user asks to 'explain project', 'show structure', 'understand organization', or needs a visual hierarchy of directories and files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path to display tree for",
                            "default": "."
                        },
                        "max_depth": {
                            "type": "integer",
                            "description": "Maximum depth to traverse",
                            "default": 3
                        },
                        "show_hidden": {
                            "type": "boolean",
                            "description": "Whether to show hidden files/directories",
                            "default": False
                        },
                        "show_sizes": {
                            "type": "boolean",
                            "description": "Whether to show file sizes",
                            "default": True
                        },
                        "exclude_patterns": {
                            "type": "array",
                            "description": "Additional patterns to exclude",
                            "items": {"type": "string"},
                            "default": None
                        },
                        "include_only": {
                            "type": "array",
                            "description": "Only include files/dirs matching these patterns",
                            "items": {"type": "string"},
                            "default": None
                        },
                        "dirs_only": {
                            "type": "boolean",
                            "description": "Show only directories",
                            "default": False
                        },
                        "files_only": {
                            "type": "boolean",
                            "description": "Show only files",
                            "default": False
                        }
                    },
                    "required": ["path"]
                }
            },
            examples=["tree('.') # project overview", "tree('.', max_depth=2) # high-level structure", "tree('.', dirs_only=True) # directory organization"],
            parallel_safe=True,
            produces_output=True  # Shows tree structure
        ))
        
        # Shell Operations
        self.register_tool(ToolDefinition(
            name="shell_exec",
            function=shell_exec,
            category=ToolCategory.SHELL,
            description="Execute shell commands",
            schema={
                "name": "shell_exec",
                "description": "Execute shell commands with live output streaming and error handling",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Shell command to execute"
                        },
                        "working_dir": {
                            "type": "string",
                            "description": "Working directory for command execution",
                            "default": "."
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Timeout in seconds",
                            "default": 120
                        }
                    },
                    "required": ["command"]
                }
            },
            examples=["shell_exec('ls -la')", "shell_exec('python test.py')"],
            is_destructive=True,
            parallel_safe=False,
            produces_output=True  # Shows command output with live streaming
        ))
        
        # Task Management
        self.register_tool(ToolDefinition(
            name="todo_read",
            function=todo_read,
            category=ToolCategory.TASK_MANAGEMENT,
            description="Read current tasks and todo items",
            schema={
                "name": "todo_read",
                "description": "Display current todo items with filtering and status information",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Session ID for task filtering"
                        },
                        "status": {
                            "type": "string",
                            "description": "Filter by status: pending, in_progress, completed"
                        },
                        "show_completed": {
                            "type": "boolean",
                            "description": "Include completed tasks in output",
                            "default": False
                        }
                    },
                    "required": []
                }
            },
            examples=["todo_read()", "todo_read(status='pending')"],
            parallel_safe=True,
            produces_output=True  # Shows todo table
        ))
        
        self.register_tool(ToolDefinition(
            name="todo_write",
            function=todo_write,
            category=ToolCategory.TASK_MANAGEMENT,
            description="Create and manage todo items",
            schema={
                "name": "todo_write",
                "description": "Create, update, or manage todo items with priority and status tracking",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "todos": {
                            "type": "array",
                            "description": "List of todo items to create or update",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "content": {"type": "string"},
                                    "status": {"type": "string"},
                                    "priority": {"type": "string"},
                                    "id": {"type": "string"}
                                },
                                "required": ["content", "status", "priority"]
                            }
                        },
                        "session_id": {
                            "type": "string",
                            "description": "Session ID for task organization"
                        }
                    },
                    "required": ["todos"]
                }
            },
            examples=["todo_write([{'content': 'Task', 'status': 'pending', 'priority': 'high'}])"],
            parallel_safe=False,
            produces_output=True  # Shows updated todo table
        ))
        
        # Bulk Operations
        self.register_tool(ToolDefinition(
            name="multi_edit",
            function=multi_edit,
            category=ToolCategory.BULK_OPERATIONS,
            description="Edit multiple files atomically",
            schema={
                "name": "multi_edit",
                "description": "Edit multiple files in a single atomic operation with rollback capability",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "edits": {
                            "type": "array",
                            "description": "List of file edits to perform",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "file_path": {"type": "string"},
                                    "new_content": {"type": "string"}
                                },
                                "required": ["file_path", "new_content"]
                            }
                        },
                        "create_backup": {
                            "type": "boolean",
                            "description": "Create backups before editing",
                            "default": False
                        },
                        "preview_only": {
                            "type": "boolean",
                            "description": "Only preview changes without applying",
                            "default": False
                        },
                        "atomic": {
                            "type": "boolean",
                            "description": "Ensure all edits succeed or none are applied",
                            "default": True
                        }
                    },
                    "required": ["edits"]
                }
            },
            examples=["multi_edit([{'file_path': 'a.py', 'new_content': '...'}])"],
            is_destructive=True,
            requires_confirmation=True,
            parallel_safe=False,
            produces_output=True  # Shows multi-file diff previews
        ))
    
    def register_tool(self, tool_def: ToolDefinition):
        self._tools[tool_def.name] = tool_def
    
    def unregister_tool(self, tool_name: str):
        if tool_name in self._tools:
            del self._tools[tool_name]
    
    def get_tool(self, tool_name: str) -> Optional[ToolDefinition]:
        return self._tools.get(tool_name)
    
    def get_tool_function(self, tool_name: str) -> Optional[Callable]:
        tool_def = self.get_tool(tool_name)
        return tool_def.function if tool_def else None
    
    def get_all_tools(self) -> Dict[str, ToolDefinition]:
        return self._tools.copy()
    
    def get_tools_by_category(self, category: ToolCategory) -> Dict[str, ToolDefinition]:
        return {
            name: tool_def for name, tool_def in self._tools.items()
            if tool_def.category == category
        }
    
    def get_llm_schemas(self, provider_format: str = "openai") -> List[Dict[str, Any]]:
        return [
            tool_def.to_llm_schema(provider_format)
            for tool_def in self._tools.values()
        ]
    
    def get_parallel_safe_tools(self) -> List[str]:
        return [
            name for name, tool_def in self._tools.items()
            if tool_def.parallel_safe
        ]
    
    def get_destructive_tools(self) -> List[str]:
        return [
            name for name, tool_def in self._tools.items()
            if tool_def.is_destructive
        ]
    
    def validate_tool_arguments(self, tool_name: str, arguments: Dict[str, Any]) -> bool:
        tool_def = self.get_tool(tool_name)
        if not tool_def:
            return False
        
        # Basic validation - could be enhanced with jsonschema
        required = tool_def.schema["parameters"].get("required", [])
        return all(arg in arguments for arg in required)
    
    def get_tool_info(self) -> Dict[str, Any]:
        return {
            "total_tools": len(self._tools),
            "categories": {
                category.value: len(self.get_tools_by_category(category))
                for category in ToolCategory
            },
            "parallel_safe": len(self.get_parallel_safe_tools()),
            "destructive": len(self.get_destructive_tools()),
            "tools": {
                name: {
                    "category": tool_def.category.value,
                    "description": tool_def.description,
                    "version": tool_def.version,
                    "parallel_safe": tool_def.parallel_safe,
                    "is_destructive": tool_def.is_destructive,
                    "requires_confirmation": tool_def.requires_confirmation
                }
                for name, tool_def in self._tools.items()
            }
        }


# Global registry instance
_tool_registry = ToolRegistry()


def get_tool_registry() -> ToolRegistry:
    return _tool_registry


def get_tool_function(tool_name: str) -> Optional[Callable]:
    return _tool_registry.get_tool_function(tool_name)


def get_tool_schemas(provider_format: str = "openai") -> List[Dict[str, Any]]:
    return _tool_registry.get_llm_schemas(provider_format)


def get_filtered_tool_schemas(provider_format: str = "openai", exclude_categories: List[ToolCategory] = None) -> List[Dict[str, Any]]:
    exclude_categories = exclude_categories or []
    
    filtered_tools = {
        name: tool_def for name, tool_def in _tool_registry._tools.items()
        if tool_def.category not in exclude_categories
    }
    
    return [
        tool_def.to_llm_schema(provider_format)
        for tool_def in filtered_tools.values()
    ]


def get_llm_tool_schemas(provider_format: str = "openai") -> List[Dict[str, Any]]:
    blocked_tools = {'todo_write'}
    
    filtered_tools = {
        name: tool_def for name, tool_def in _tool_registry._tools.items()
        if name not in blocked_tools
    }
    
    return [
        tool_def.to_llm_schema(provider_format)
        for tool_def in filtered_tools.values()
    ]