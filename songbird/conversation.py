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
        
        # Add system prompt to guide the LLM
        self.system_prompt = """You are Songbird, an AI coding assistant with access to powerful tools for interacting with the file system and terminal.

IMPORTANT: You have access to the following tools:
1. shell_exec - Execute ANY terminal/shell command (ls, dir, pwd, cd, python, git, pip, npm, etc.)
2. file_create - Create new files with content
3. file_edit - Edit existing files (shows diff before applying)
4. file_read - Read file contents
5. file_search - POWERFUL search tool that can find:
   - Files by name (e.g., "find test.py" or "find all Python files")
   - Functions by name (e.g., "find the calculate_total function")
   - Classes by name (e.g., "find the UserModel class")
   - Any text or code pattern in files
   - Variables and their definitions
   - The tool automatically detects what you're searching for!

When users ask you to:
- Find a file → Use file_search with the filename
- Find a function/class → Use file_search with the name
- Search for code → Use file_search with the pattern
- List files/folders → Use shell_exec with 'ls' or 'dir'
- Run Python scripts → Use shell_exec
- Work with a specific function → First use file_search to find it, then file_read or file_edit

ALWAYS use the appropriate tool when asked to perform file operations or terminal commands. Never say you cannot do something that these tools enable.

When users mention a file or function but don't provide the full path, use file_search to locate it first."""
        
        # Initialize conversation with system prompt
        self.conversation_history.append({
            "role": "system",
            "content": self.system_prompt
        })
    
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
                    # Unknown format, skip
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
                # The result from execute_tool is wrapped in {"success": bool, "result": actual_result}
                wrapped_result = tool_result["result"]
                actual_result = wrapped_result.get("result") if wrapped_result.get("success") else wrapped_result
                
                self.conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tool_result["tool_call_id"],
                    "content": json.dumps(actual_result)  # Store the actual result, not the wrapper
                })
            
            # Continue conversation with function results following official pattern
            if hasattr(self.provider, 'chat_with_messages'):
                messages = self._build_messages_with_function_results(tool_results)
                final_response = self.provider.chat_with_messages(messages, tools=None)
                
                # Add final response to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": final_response.content
                })
                
                return final_response.content
            else:
                # Fallback for providers that don't support chat_with_messages
                if len(tool_results) == 1:
                    result = tool_results[0]
                    function_name = result["function_name"]
                    success = result["result"].get("success", False)
                    
                    if success:
                        if function_name == "file_create":
                            file_path = result["result"].get("file_path", "unknown")
                            content = f"✅ Successfully created file: {file_path}"
                        elif function_name == "file_edit":
                            file_path = result["result"].get("file_path", "unknown")
                            content = f"✅ Successfully edited file: {file_path}"
                        else:
                            content = f"✅ Successfully executed {function_name}"
                    else:
                        error = result["result"].get("error", "Unknown error")
                        content = f"❌ {function_name} failed: {error}"
                else:
                    successful = sum(1 for r in tool_results if r["result"].get("success", False))
                    content = f"✅ Executed {successful}/{len(tool_results)} tools successfully"
                
                # Add final response to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": content
                })
                
                return content
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
            if msg["role"] == "system":
                # Always include system messages
                messages.append(msg)
            elif msg["role"] in ["user", "assistant"]:
                # For assistant messages, only include content, not tool_calls
                clean_msg = {
                    "role": msg["role"],
                    "content": msg["content"]
                }
                messages.append(clean_msg)
            elif msg["role"] == "tool":
                # Skip tool messages in conversation for now - let the final response handle acknowledgment
                continue
        return messages
    
    def _build_messages_with_function_results(self, tool_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Build messages including function call results following official Google GenAI pattern.
        
        IMPORTANT: We provide clear instructions to the LLM to not repeat the code content,
        since it was already shown in the tool execution output.
        """
        messages = []
        
        # Add system prompt first
        messages.append({
            "role": "system",
            "content": self.system_prompt
        })
        
        # Add all conversation history up to the latest assistant message with tool calls
        for msg in self.conversation_history:
            if msg["role"] == "system":
                continue  # Already added above
            elif msg["role"] in ["user", "assistant"]:
                clean_msg = {
                    "role": msg["role"],
                    "content": msg["content"]
                }
                # Include tool_calls if present (for the assistant message that triggered tools)
                if "tool_calls" in msg:
                    clean_msg["tool_calls"] = msg["tool_calls"]
                messages.append(clean_msg)
        
        # Add tool results as system/user messages describing what happened
        tool_summary = []
        for tool_result in tool_results:
            function_name = tool_result["function_name"]
            # The result from execute_tool is {"success": bool, "result": actual_result}
            wrapper_result = tool_result["result"]
            
            if wrapper_result.get("success", False):
                actual_result = wrapper_result["result"]
                
                if function_name == "file_create":
                    file_path = actual_result.get("file_path", "unknown file")
                    # Check if content was already shown
                    if actual_result.get("content_preview_shown", False):
                        content = f"Successfully created file: {file_path}\n(Content already displayed above - no need to show it again)"
                    else:
                        content = f"Successfully created file: {file_path}"
                elif function_name == "file_edit":
                    file_path = actual_result.get("file_path", "unknown file")
                    content = f"Successfully edited file: {file_path}\n(Diff already displayed above - no need to show the code again)"
                elif function_name == "shell_exec":
                    # Check if output was displayed live
                    if actual_result.get("output_displayed", True):  # Default to True for new shell_exec
                        # Output was already shown, just provide context
                        exit_code = actual_result.get("exit_code", 0)
                        command = actual_result.get("command", "unknown command")
                        
                        if exit_code == 0:
                            content = f"The command '{command}' executed successfully and the output was displayed above."
                        else:
                            content = f"The command '{command}' failed with exit code {exit_code}. See the output above for details."
                    else:
                        # Output wasn't displayed (shouldn't happen with current implementation)
                        stdout = actual_result.get("stdout", "").strip()
                        stderr = actual_result.get("stderr", "").strip()
                        exit_code = actual_result.get("exit_code", 0)
                        command = actual_result.get("command", "unknown command")
                        
                        content = f"Executed command: {command}\nExit code: {exit_code}"
                        
                        if stdout:
                            content += f"\n\nOutput:\n{stdout}"
                        if stderr:
                            content += f"\n\nError output:\n{stderr}"
                        if not stdout and not stderr:
                            content += "\n\n(No output produced)"
                        
                elif function_name == "file_search":
                    total_matches = actual_result.get("total_matches", 0)
                    search_type = actual_result.get("search_type", "text")
                    pattern = actual_result.get("pattern", "")
                    
                    if total_matches > 0:
                        content = f"Found {total_matches} {search_type} matches for '{pattern}'"
                        
                        # The search tool already displayed the results in a nice table,
                        # so just provide summary information
                        if actual_result.get("truncated"):
                            content += f" (showing first {len(actual_result.get('matches', []))} results)"
                        
                        # Add file summary if many matches
                        matches = actual_result.get("matches", [])
                        if matches:
                            files = list(set(m["file"] for m in matches))
                            if len(files) == 1:
                                content += f"\n\nAll matches are in: {files[0]}"
                            elif len(files) <= 3:
                                content += f"\n\nMatches found in: {', '.join(files)}"
                            else:
                                content += f"\n\nMatches found across {len(files)} files"
                    else:
                        content = f"No matches found for '{pattern}' ({search_type} search)"
                elif function_name == "file_read":
                    lines_returned = actual_result.get("lines_returned", 0)
                    file_content = actual_result.get("content", "")
                    content = f"File read successfully, {lines_returned} lines"
                    if file_content:
                        # Include a preview of the content
                        preview = file_content[:500] + "..." if len(file_content) > 500 else file_content
                        content += f"\n\nContent:\n{preview}"
                else:
                    content = f"Tool {function_name} executed successfully"
            else:
                # Tool execution failed
                error = wrapper_result.get("error", "Unknown error")
                content = f"Tool {function_name} failed: {error}"
            
            tool_summary.append(content)
        
        # Create a single message with all tool results
        combined_message = "Tool execution results:\n\n" + "\n\n---\n\n".join(tool_summary)
        
        # Add specific instructions based on what tools were used
        instructions = []
        
        if any("shell_exec" in r["function_name"] for r in tool_results):
            instructions.append("The shell command output has already been displayed to the user above. Please provide helpful context or summary, but do NOT repeat the raw output.")
        
        if any("file_create" in r["function_name"] or "file_edit" in r["function_name"] for r in tool_results):
            instructions.append("The file content/diff has already been displayed to the user. Do NOT repeat or show the code again.")
        
        if instructions:
            combined_message += "\n\nIMPORTANT INSTRUCTIONS:\n" + "\n".join(instructions)
        
        messages.append({
            "role": "user",
            "content": combined_message
        })
        
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
                        "file_path": apply_result["file_path"],
                        "diff_displayed": True  # Flag that diff was shown
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