from typing import Any, Dict, List, Optional
from .executor import ToolExecutor
from .tool_registry import get_tool_registry
from ..ui.data_transfer import ToolOutput, UIMessage


class ToolRunner:
    
    def __init__(self, working_directory: str = ".", session_id: Optional[str] = None, ui_layer=None):
        self.working_directory = working_directory
        self.session_id = session_id
        self.ui_layer = ui_layer
        self.tool_executor = ToolExecutor(working_directory, session_id)
    
    async def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            should_pause_thinking = self._should_pause_thinking_for_tool(tool_name)
            
            if should_pause_thinking and self.ui_layer:
                await self.ui_layer.pause_thinking()
            
            result = await self.tool_executor.execute_tool(tool_name, args)
            
            if should_pause_thinking and self.ui_layer:
                pass
            
            if not isinstance(result, dict):
                result = {"success": False, "error": "Invalid result format"}
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "tool_name": tool_name,
                "args": args
            }
    
    def _should_pause_thinking_for_tool(self, tool_name: str) -> bool:
        tool_registry = get_tool_registry()
        tool_def = tool_registry.get_tool(tool_name)
        return tool_def.produces_output if tool_def else False
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        return self.tool_executor.get_available_tools()
    
    async def execute_tools_parallel(self, tool_calls: List[Dict[str, Any]]) -> List[ToolOutput]:
        results = []
        
        for tool_call in tool_calls:
            try:
                if isinstance(tool_call, dict) and "function" in tool_call:
                    function_name = tool_call["function"]["name"]
                    arguments = tool_call["function"]["arguments"]
                elif hasattr(tool_call, 'function'):
                    function_name = tool_call.function.name
                    arguments = tool_call.function.arguments
                else:
                    results.append(ToolOutput.error(f"Invalid tool call format: {type(tool_call)}"))
                    continue
                
                result = await self.execute_tool(function_name, arguments)
                
                if result.get("success", True):
                    display_message = self._create_tool_display_message(function_name, result)
                    results.append(ToolOutput.success_result(result, display_message))
                else:
                    error_message = result.get("error", "Tool execution failed")
                    results.append(ToolOutput.error_result(error_message, result))
                    
            except Exception as e:
                results.append(ToolOutput.error_result(f"Error executing tool: {str(e)}"))
        
        return results
    
    def _create_tool_display_message(self, tool_name: str, result: Dict[str, Any]) -> UIMessage:
        if tool_name == "file_read":
            file_path = result.get("file_path", "unknown")
            content_length = len(result.get("content", ""))
            message_content = f"Read {file_path} ({content_length} characters)"
            
        elif tool_name == "file_create":
            file_path = result.get("file_path", "unknown")
            message_content = f"Created file: {file_path}"
            
        elif tool_name == "file_edit":
            file_path = result.get("file_path", "unknown")
            message_content = f"Edited file: {file_path}"
            
        elif tool_name == "shell_exec":
            command = result.get("command", "unknown")
            exit_code = result.get("exit_code", 0)
            if exit_code == 0:
                message_content = f"Executed: {command} (success)"
            else:
                message_content = f"Executed: {command} (exit code: {exit_code})"
                
        elif tool_name in ["ls", "glob", "grep"]:
            matches = result.get("matches", [])
            files = result.get("files", [])
            count = len(matches) + len(files)
            message_content = f"{tool_name.upper()}: Found {count} results"
            
        elif tool_name in ["todo_read", "todo_write"]:
            todos = result.get("todos", [])
            message_content = f"Todo management: {len(todos)} tasks"
            
        else:
            message_content = f"Executed {tool_name}"
        
        return UIMessage.tool_result(
            message_content,
            tool_name=tool_name,
            success=result.get("success", True)
        )
    
    def can_execute_in_parallel(self, tool_names: List[str]) -> bool:
        registry = get_tool_registry()
        
        for tool_name in tool_names:
            tool_def = registry.get_tool(tool_name)
            if not tool_def or not tool_def.parallel_safe:
                return False
        
        return True