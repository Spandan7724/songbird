# songbird/conversation.py
"""
Conversation orchestrator that handles LLM interactions with tool calling.
"""
import json
from typing import List, Dict, Any, Optional
from rich.prompt import Confirm
from .llm.providers import BaseProvider
from .tools.executor import ToolExecutor
from .tools.registry import get_tool_schemas
from .tools.file_operations import display_diff_preview, apply_file_edit


class ConversationOrchestrator:
    """Orchestrates conversations between user, LLM, and tools."""
    
    def __init__(self, provider: BaseProvider, working_directory: str = "."):
        self.provider = provider
        self.tool_executor = ToolExecutor(working_directory)
        self.conversation_history: List[Dict[str, Any]] = []
    
    async def chat(self, message: str) -> str:
        """
        Send a message and handle any tool calls.
        
        Args:
            message: User message
            
        Returns:
            Final response content
        """
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": message
        })
        
        # Get available tools
        tools = self.tool_executor.get_available_tools()
        
        # Get LLM response
        response = self.provider.chat(message, tools=tools)
        
        # Handle tool calls if any
        if response.tool_calls:
            # Execute tool calls
            tool_results = []
            for tool_call in response.tool_calls:
                function_name = tool_call["function"]["name"]
                arguments = json.loads(tool_call["function"]["arguments"])
                
                # Special handling for file_edit - show diff and confirm
                if function_name == "file_edit":
                    result = await self._handle_file_edit(arguments)
                else:
                    result = await self.tool_executor.execute_tool(function_name, arguments)
                
                tool_results.append({
                    "tool_call_id": tool_call.get("id", ""),
                    "function_name": function_name,
                    "result": result
                })
            
            # Add assistant message with tool calls to history
            self.conversation_history.append({
                "role": "assistant", 
                "content": response.content,
                "tool_calls": response.tool_calls
            })
            
            # Add tool results to history
            for tool_result in tool_results:
                self.conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tool_result["tool_call_id"],
                    "content": json.dumps(tool_result["result"])
                })
            
            # Get final response from LLM after tool execution
            # TODO: Implement multi-turn conversation with full history
            # For now, just return the original response with tool info
            tool_info = f"\n\n[Used tools: {', '.join([r['function_name'] for r in tool_results])}]"
            return response.content + tool_info
        else:
            # No tool calls, just return the response
            self.conversation_history.append({
                "role": "assistant",
                "content": response.content
            })
            return response.content
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get the conversation history."""
        return self.conversation_history.copy()
    
    def clear_history(self):
        """Clear the conversation history."""
        self.conversation_history.clear()
    
    async def _handle_file_edit(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle file edit with diff preview and confirmation."""
        try:
            # First, prepare the edit to show diff preview
            result = await self.tool_executor.execute_tool("file_edit", arguments)
            
            if not result.get("success"):
                return result
            
            edit_result = result["result"]
            if not edit_result.get("changes_made"):
                return {
                    "success": True,
                    "message": "No changes needed - file content is already as requested"
                }
            
            # Display the diff preview
            display_diff_preview(edit_result["diff_preview"], edit_result["file_path"])
            
            # Ask for confirmation
            if Confirm.ask("\n🤔 Apply these changes?"):
                # Apply the edit
                apply_result = await apply_file_edit(
                    arguments["file_path"],
                    arguments["new_content"], 
                    arguments.get("create_backup", True)
                )
                
                if apply_result["success"]:
                    return {
                        "success": True,
                        "message": f"✅ {apply_result['message']}",
                        "file_path": apply_result["file_path"]
                    }
                else:
                    return apply_result
            else:
                return {
                    "success": False,
                    "message": "❌ Changes cancelled by user"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Error handling file edit: {e}"
            }