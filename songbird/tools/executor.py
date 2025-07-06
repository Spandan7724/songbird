#Tool execution system for handling LLM function calls.

import asyncio
from typing import Dict, Any, List
from .tool_registry import get_tool_function, get_llm_tool_schemas, get_tool_registry
from ..config.config_manager import get_config


class ToolExecutor:
    def __init__(self, working_directory: str = ".", session_id: str = None):
        self.working_directory = working_directory
        self.session_id = session_id
        
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        # Execute a tool with given arguments.

        try:
            tool_function = get_tool_function(tool_name)
            if not tool_function:
                return {
                    "success": False,
                    "error": f"Unknown tool: {tool_name}"
                }
            
            config = get_config()
            
            if tool_name == "file_search" and "directory" not in arguments:
                arguments["directory"] = self.working_directory
            
            if tool_name in ["todo_read", "todo_write"] and "session_id" not in arguments:
                if self.session_id:
                    arguments["session_id"] = self.session_id
            
            if tool_name == "shell_exec" and "timeout" not in arguments:
                arguments["timeout"] = config.tools.shell_timeout
            
            result = await tool_function(**arguments)
            
            return {
                "success": True,
                "result": result
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def execute_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Execute multiple tool calls in parallel.

        tasks = []
        for tool_call in tool_calls:
            name = tool_call.get("name")
            arguments = tool_call.get("arguments", {})
            task = self.execute_tool(name, arguments)
            tasks.append(task)
            
        return await asyncio.gather(*tasks)
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        # Get list of available tool schemas for LLM (excluding task management tools).
        return get_llm_tool_schemas()
    
    def get_tool_statistics(self) -> Dict[str, Any]:
        # Get statistics about available tools.
        tool_registry = get_tool_registry()
        tool_info = tool_registry.get_tool_info()
        
        return {
            "total_tools": tool_info["total_tools"],
            "categories": tool_info["categories"],
            "parallel_safe": tool_info["parallel_safe"],
            "destructive": tool_info["destructive"]
        }
