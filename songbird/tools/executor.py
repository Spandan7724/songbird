# songbird/tools/executor.py
"""
Tool execution system for handling LLM function calls.
"""
import asyncio
from typing import Dict, Any, List
from .registry import get_tool_function, get_tool_schemas


class ToolExecutor:
    """Executes tools called by LLMs."""
    
    def __init__(self, working_directory: str = ".", session_id: str = None):
        self.working_directory = working_directory
        self.session_id = session_id
        
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool with given arguments.
        
        Args:
            tool_name: Name of the tool to execute
            arguments: Arguments to pass to the tool
            
        Returns:
            Dictionary with result or error information
        """
        try:
            tool_function = get_tool_function(tool_name)
            if not tool_function:
                return {
                    "success": False,
                    "error": f"Unknown tool: {tool_name}"
                }
            
            # Add working directory to file search if not specified
            if tool_name == "file_search" and "directory" not in arguments:
                arguments["directory"] = self.working_directory
            
            # Add session_id to todo tools if not specified
            if tool_name in ["todo_read", "todo_write"] and "session_id" not in arguments:
                if self.session_id:
                    arguments["session_id"] = self.session_id
                
            # Execute the tool function
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
        """
        Execute multiple tool calls in parallel.
        
        Args:
            tool_calls: List of tool call dictionaries with 'name' and 'arguments'
            
        Returns:
            List of execution results
        """
        tasks = []
        for tool_call in tool_calls:
            name = tool_call.get("name")
            arguments = tool_call.get("arguments", {})
            task = self.execute_tool(name, arguments)
            tasks.append(task)
            
        return await asyncio.gather(*tasks)
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tool schemas for LLM."""
        return get_tool_schemas()