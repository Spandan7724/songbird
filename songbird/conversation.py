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
        Send a message and handle any tool calls with multi-turn conversation.
        
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
        
        # Convert our conversation history to the format expected by the LLM
        messages = self._build_messages_for_llm()
        
        # Get LLM response
        response = self.provider.chat_with_messages(messages, tools=tools)
        
        # Handle tool calls if any
        if response.tool_calls:
            # Execute tool calls
            tool_results = []
            for i, tool_call in enumerate(response.tool_calls):
                # Handle different tool call formats
                if hasattr(tool_call, 'function'):
                    # Ollama ToolCall objects
                    function_name = tool_call.function.name
                    arguments = tool_call.function.arguments
                elif isinstance(tool_call, dict) and "function" in tool_call:
                    # Gemini/dict format
                    function_name = tool_call["function"]["name"]
                    arguments = tool_call["function"]["arguments"]
                else:
                    # Unknown format
                    print(f"DEBUG: Unknown tool call format: {tool_call}")
                    continue
                
                # Handle both string and dict arguments
                if isinstance(arguments, str):
                    arguments = json.loads(arguments)
                
                # Special handling for file_edit - show diff and confirm
                if function_name == "file_edit":
                    result = await self._handle_file_edit(arguments)
                else:
                    result = await self.tool_executor.execute_tool(function_name, arguments)
                
                # Get tool call ID
                if hasattr(tool_call, 'function'):
                    tool_call_id = getattr(tool_call, 'id', "")
                elif isinstance(tool_call, dict):
                    tool_call_id = tool_call.get("id", "")
                else:
                    tool_call_id = ""
                
                tool_results.append({
                    "tool_call_id": tool_call_id,
                    "function_name": function_name,
                    "result": result
                })
            
            # Add assistant message with tool calls to history  
            # Convert tool calls to serializable format
            serializable_tool_calls = []
            for tool_call in response.tool_calls:
                if hasattr(tool_call, 'function'):
                    # Ollama format
                    serializable_tool_calls.append({
                        "id": getattr(tool_call, 'id', ""),
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments
                        }
                    })
                elif isinstance(tool_call, dict):
                    # Already serializable (Gemini format)
                    serializable_tool_calls.append(tool_call)
                else:
                    # Unknown format, try to convert
                    serializable_tool_calls.append(str(tool_call))
            
            self.conversation_history.append({
                "role": "assistant", 
                "content": response.content or "",
                "tool_calls": serializable_tool_calls
            })
            
            # Add tool results to history
            for tool_result in tool_results:
                self.conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tool_result["tool_call_id"],
                    "content": json.dumps(tool_result["result"])
                })
            
            # Get final response from LLM after tool execution (without tools to get natural response)
            messages = self._build_messages_for_llm()
            final_response = self.provider.chat_with_messages(messages, tools=None)
            
            # Add final response to history
            self.conversation_history.append({
                "role": "assistant",
                "content": final_response.content
            })
            
            return final_response.content
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
    
    def _build_messages_for_llm(self) -> List[Dict[str, Any]]:
        """
        Convert conversation history to format expected by LLM.
        Filters out tool-specific fields that the LLM doesn't need.
        """
        messages = []
        for msg in self.conversation_history:
            if msg["role"] in ["user", "assistant"]:
                # For assistant messages, only include content, not tool_calls
                clean_msg = {
                    "role": msg["role"],
                    "content": msg["content"]
                }
                messages.append(clean_msg)
            elif msg["role"] == "tool":
                # Convert tool results to user messages asking for interpretation
                import json
                try:
                    tool_result = json.loads(msg['content'])
                    if tool_result.get('result', {}).get('success'):
                        # Successful tool execution
                        stdout = tool_result.get('result', {}).get('stdout', '')
                        stderr = tool_result.get('result', {}).get('stderr', '')
                        if stdout:
                            tool_msg = {
                                "role": "user",
                                "content": f"The command executed successfully with output:\n{stdout}"
                            }
                        else:
                            tool_msg = {
                                "role": "user", 
                                "content": "The command executed successfully with no output."
                            }
                    else:
                        # Failed tool execution
                        error = tool_result.get('result', {}).get('error', 'Unknown error')
                        tool_msg = {
                            "role": "user",
                            "content": f"The command failed with error: {error}"
                        }
                except json.JSONDecodeError:
                    # Fallback for non-JSON results
                    tool_msg = {
                        "role": "user", 
                        "content": f"Tool result: {msg['content']}"
                    }
                messages.append(tool_msg)
        return messages
    
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
            if Confirm.ask("\nApply these changes?"):
                # Apply the edit
                apply_result = await apply_file_edit(
                    arguments["file_path"],
                    arguments["new_content"], 
                    arguments.get("create_backup", True)
                )
                
                if apply_result["success"]:
                    return {
                        "success": True,
                        "message": f"{apply_result['message']}",
                        "file_path": apply_result["file_path"]
                    }
                else:
                    return apply_result
            else:
                return {
                    "success": False,
                    "message": "Changes cancelled by user"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Error handling file edit: {e}"
            }