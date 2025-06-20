# songbird/conversation.py
"""
Conversation orchestrator that handles LLM interactions with tool calling.
"""
import asyncio
import json
import os
import sys
from typing import List, Dict, Any, Optional
from rich.console import Console
from InquirerPy import inquirer
from .llm.providers import BaseProvider
from .tools.executor import ToolExecutor
from .tools.file_operations import display_diff_preview, apply_file_edit
from .memory.models import Session, Message
from .memory.manager import SessionManager


async def safe_interactive_menu(prompt: str, options: list[str], default_index: int = 0) -> int | None:
    """
    Async-safe interactive menu that handles all scenarios properly.
    Returns the selected index, or None if cancelled.
    """
    try:
        # Check if we're in an interactive terminal
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            # Non-interactive environment - auto-select default
            console = Console()
            console.print(f"\n{prompt}")
            for i, option in enumerate(options):
                marker = "▶ " if i == default_index else "  "
                console.print(f"{marker}{option}")
            console.print(f"[dim]Auto-selected: {options[default_index]}[/dim]")
            return default_index
        
        # Try the async InquirerPy API first
        return await async_interactive_menu(prompt, options, default_index)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        return None

async def async_interactive_menu(prompt: str, options: list[str], default_index: int = 0) -> int:
    """
    Async interactive menu using InquirerPy's execute_async() method.
    This is the CORRECT way to use InquirerPy within an existing event loop.
    """
    try:
        # Use InquirerPy's async API - this is the key fix!
        result = await inquirer.select(
            message=prompt,
            choices=options,
            default=options[default_index] if 0 <= default_index < len(options) else options[0]
        ).execute_async()
        return options.index(result)
    except Exception:
        # If async fails for any reason, fall back to synchronous
        print("Async menu failed, falling back to simple menu...")
        return fallback_numbered_menu(prompt, options, default_index)

def fallback_numbered_menu(prompt: str, options: list[str], default_index: int = 0) -> int:
    """Fallback numbered menu for when InquirerPy fails."""
    console = Console()
    
    # Check if we can actually read from stdin
    if not sys.stdin.isatty():
        console.print(f"\n{prompt}")
        for i, option in enumerate(options):
            style = "bold green" if i == default_index else "white"
            console.print(f"  {i + 1}. {option}", style=style)
        console.print(f"[dim]Auto-selected option {default_index + 1}: {options[default_index]}[/dim]")
        return default_index
    
    console.print(f"\n{prompt}")
    for i, option in enumerate(options):
        style = "bold green" if i == default_index else "white"
        console.print(f"  {i + 1}. {option}", style=style)
    
    while True:
        try:
            choice = input(f"\nSelect option (1-{len(options)}, default={default_index + 1}): ").strip()
            
            if not choice:
                return default_index
            
            choice_num = int(choice) - 1
            if 0 <= choice_num < len(options):
                return choice_num
            else:
                console.print(f"Invalid choice. Please select 1-{len(options)}", style="red")
        except ValueError:
            console.print("Invalid input. Please enter a number.", style="red")
        except (KeyboardInterrupt, EOFError):
            # Handle both Ctrl+C and EOF (no input available)
            return default_index

def interactive_menu(prompt: str, options: list[str], default_index: int = 0) -> int:
    """Synchronous compatibility function for CLI usage."""
    try:
        # Use InquirerPy's synchronous execute() method for CLI
        result = inquirer.select(
            message=prompt,
            choices=options,
            default=options[default_index] if 0 <= default_index < len(options) else options[0]
        ).execute()
        return options.index(result)
    except Exception:
        # Fall back to numbered menu
        return fallback_numbered_menu(prompt, options, default_index)

class ConversationOrchestrator:
    """Orchestrates conversations between user, LLM, and tools."""

    def __init__(self, provider: BaseProvider, working_directory: str = ".", session: Optional[Session] = None):
        self.provider = provider
        self.tool_executor = ToolExecutor(working_directory)
        self.conversation_history: List[Dict[str, Any]] = []
        self.session = session
        self.session_manager = SessionManager(working_directory)
        self._current_status = None  # Track current status object

        # Add system prompt to guide the LLM
        self.system_prompt = """You are Songbird, an AI coding assistant with access to powerful tools for interacting with the file system and terminal.

IMPORTANT: You have access to the following tools:
1. shell_exec - Execute ANY terminal/shell command (ls, dir, pwd, cd, python, git, pip, npm, etc.)
2. file_create - Create new files with content
3. file_edit - Edit existing files (shows diff before applying) - ALWAYS use this directly when asked to edit, don't show the code first
4. file_read - Read file contents
5. file_search - Fast search using ripgrep:
   - Find all Python files: Use "*.py"
   - Find specific file: Use exact name like "test.py" or glob like "*test*.py"
   - Search text in files: Use any text pattern
   - Filter by type: Use file_type parameter (py, js, md, etc.)

When users ask you to:
- Edit a file → Use file_edit IMMEDIATELY with the new content, don't show the code first
- Check if a file exists → Use file_search with the exact filename
- Find files → Use file_search with glob patterns
- Search for text/code → Use file_search with the text pattern
- List files/folders → Use shell_exec with 'ls' or 'dir' 
- Run scripts → Use shell_exec

CRITICAL FILE CREATION RULES:
- When creating files, ALWAYS generate appropriate filenames automatically based on the content/purpose
- NEVER ask the user "What should the file be named?" - infer logical names from context
- Use descriptive, conventional names: calculator.py, add_numbers.cpp, circle_area.py, etc.
- Match file extensions to the programming language/content type
- If the user specifies a filename, use it; otherwise generate one immediately

ALWAYS use the appropriate tool when asked to perform file operations or terminal commands. Never say you cannot do something that these tools enable.

When editing files, go straight to using file_edit - the tool will show the diff automatically.

RESPONSE FORMATTING GUIDELINES:
- When displaying code content, always wrap it in proper markdown code blocks with language specification
- Use clear, concise language in responses
- Structure information with headers, bullet points, and proper spacing
- When showing file contents, provide context about what the file does
- Keep responses focused and avoid unnecessary repetition
- Use appropriate technical terminology but explain complex concepts clearly"""

        # Initialize conversation history
        if self.session and self.session.messages:
            # Load existing conversation history from session
            self._load_history_from_session()
        else:
            # Initialize new conversation with system prompt
            self.conversation_history.append({
                "role": "system",
                "content": self.system_prompt
            })

            # Add system message to session if it's new
            if self.session:
                self.session.add_message(Message(
                    role="system",
                    content=self.system_prompt
                ))

    def _load_history_from_session(self):
        """Load conversation history from session messages."""
        self.conversation_history = []

        for msg in self.session.messages:
            hist_msg = {
                "role": msg.role,
                "content": msg.content
            }
            if msg.tool_calls:
                hist_msg["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                hist_msg["tool_call_id"] = msg.tool_call_id

            self.conversation_history.append(hist_msg)

    async def chat(self, message: str, status=None) -> str:
        """
        Send a message and handle any tool calls with multi-turn conversation.
        
        Args:
            message: User message
            status: Optional Rich Status object to stop before tool execution
            
        Returns:
            Final response content
        """
        # Store the status object
        self._current_status = status
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": message
        })

        # Add to session if we have one
        if self.session:
            user_msg = Message(role="user", content=message)
            self.session.add_message(user_msg)
            # Save after each user message
            self.session_manager.save_session(self.session)

        # Get available tools
        tools = self.tool_executor.get_available_tools()

        # Convert our conversation history to the format expected by the LLM
        messages = self._build_messages_for_llm()

        # Get LLM response
        response = self.provider.chat_with_messages(messages, tools=tools)

        # Handle tool calls if any
        if response.tool_calls:
            # CRITICAL: Stop status before any tool execution
            if self._current_status:
                self._current_status.stop()
                await asyncio.sleep(0.1)  # Ensure clean terminal state
            
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

                # Ensure result has the expected structure
                if not isinstance(result, dict):
                    result = {"success": False,
                              "error": "Invalid result format"}

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

            # Add to session
            if self.session:
                assistant_msg = Message(
                    role="assistant",
                    content=response.content or "",
                    tool_calls=serializable_tool_calls
                )
                self.session.add_message(assistant_msg)

            # Add tool results to history
            for tool_result in tool_results:
                # The result from execute_tool is wrapped in {"success": bool, "result": actual_result}
                wrapped_result = tool_result["result"]
                actual_result = wrapped_result.get(
                    "result") if wrapped_result.get("success") else wrapped_result

                self.conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tool_result["tool_call_id"],
                    # Store the actual result, not the wrapper
                    "content": json.dumps(actual_result)
                })

                # Add to session
                if self.session:
                    tool_msg = Message(
                        role="tool",
                        content=json.dumps(actual_result),
                        tool_call_id=tool_result["tool_call_id"]
                    )
                    self.session.add_message(tool_msg)

            # Continue conversation with function results following official pattern
            if hasattr(self.provider, 'chat_with_messages'):
                try:
                    messages = self._build_messages_with_function_results(
                        tool_results)
                    final_response = self.provider.chat_with_messages(
                        messages, tools=None)

                    # Add final response to history
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": final_response.content
                    })

                    # Add to session
                    if self.session:
                        final_msg = Message(
                            role="assistant", content=final_response.content)
                        self.session.add_message(final_msg)
                        # Update summary
                        self.session.summary = self.session.generate_summary()
                        self.session_manager.save_session(self.session)

                    return final_response.content
                except Exception as e:
                    # If there's an error, provide a simple status message
                    Console().print(
                        f"[dim]Debug: Error in final response: {e}[/dim]")

                    # Provide a simple status based on tool results
                    status_messages = []
                    for result in tool_results:
                        func_name = result["function_name"]
                        success = result["result"].get("success", False)

                        if success:
                            if func_name == "file_edit":
                                status_messages.append(
                                    "✓ File edited successfully")
                            elif func_name == "file_create":
                                status_messages.append(
                                    "✓ File created successfully")
                            else:
                                status_messages.append(
                                    f"✓ {func_name} completed")
                        else:
                            error = result["result"].get(
                                "error", "Unknown error")
                            status_messages.append(
                                f"✗ {func_name} failed: {error}")

                    status_content = "\n".join(
                        status_messages) if status_messages else "Operation completed"

                    # Add to session
                    if self.session:
                        status_msg = Message(
                            role="assistant", content=status_content)
                        self.session.add_message(status_msg)
                        self.session.summary = self.session.generate_summary()
                        self.session_manager.save_session(self.session)

                    return status_content
            else:
                # Fallback for providers that don't support chat_with_messages
                if len(tool_results) == 1:
                    result = tool_results[0]
                    function_name = result["function_name"]
                    success = result["result"].get("success", False)

                    if success:
                        if function_name == "file_create":
                            file_path = result["result"].get(
                                "file_path", "unknown")
                            content = f"✅ Successfully created file: {file_path}"
                        elif function_name == "file_edit":
                            file_path = result["result"].get(
                                "file_path", "unknown")
                            content = f"✅ Successfully edited file: {file_path}"
                        else:
                            content = f"✅ Successfully executed {function_name}"
                    else:
                        error = result["result"].get("error", "Unknown error")
                        content = f"❌ {function_name} failed: {error}"
                else:
                    successful = sum(
                        1 for r in tool_results if r["result"].get("success", False))
                    content = f"✅ Executed {successful}/{len(tool_results)} tools successfully"

                # Add final response to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": content
                })

                # Add to session
                if self.session:
                    final_msg = Message(role="assistant", content=content)
                    self.session.add_message(final_msg)
                    self.session.summary = self.session.generate_summary()
                    self.session_manager.save_session(self.session)

                return content
        else:
            # No tool calls, just return the response
            self.conversation_history.append({
                "role": "assistant",
                "content": response.content
            })

            # Add to session
            if self.session:
                assistant_msg = Message(
                    role="assistant", content=response.content)
                self.session.add_message(assistant_msg)
                self.session.summary = self.session.generate_summary()
                self.session_manager.save_session(self.session)

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
        Includes all messages to maintain context.
        """
        messages = []
        for msg in self.conversation_history:
            if msg["role"] == "system":
                messages.append(msg)
            elif msg["role"] == "user":
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            elif msg["role"] == "assistant":
                # Include assistant messages with their content
                clean_msg = {
                    "role": msg["role"],
                    "content": msg["content"]
                }
                # Include tool_calls if present
                if "tool_calls" in msg and msg["tool_calls"]:
                    clean_msg["tool_calls"] = msg["tool_calls"]
                messages.append(clean_msg)
            elif msg["role"] == "tool":
                # Include tool results in the conversation
                messages.append({
                    "role": "tool",
                    "content": msg["content"],
                    "tool_call_id": msg.get("tool_call_id", "")
                })
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
                    if actual_result.get("diff_displayed", False):
                        content = f"Successfully edited file: {file_path}\n(Diff already displayed above - no need to show the code again)"
                    else:
                        content = f"Successfully edited file: {file_path}"
                elif function_name == "shell_exec":
                    # Check if output was displayed live
                    # Default to True for new shell_exec
                    if actual_result.get("output_displayed", True):
                        # Output was already shown, just provide context
                        exit_code = actual_result.get("exit_code", 0)
                        command = actual_result.get(
                            "command", "unknown command")

                        if exit_code == 0:
                            content = f"The command '{command}' executed successfully and the output was displayed above."
                        else:
                            content = f"The command '{command}' failed with exit code {exit_code}. See the output above for details."
                    else:
                        # Output wasn't displayed (shouldn't happen with current implementation)
                        stdout = actual_result.get("stdout", "").strip()
                        stderr = actual_result.get("stderr", "").strip()
                        exit_code = actual_result.get("exit_code", 0)
                        command = actual_result.get(
                            "command", "unknown command")

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
                        preview = file_content[:500] + \
                            "..." if len(file_content) > 500 else file_content
                        content += f"\n\nContent:\n{preview}"
                else:
                    content = f"Tool {function_name} executed successfully"
            else:
                # Tool execution failed
                error = wrapper_result.get("error", "Unknown error")
                content = f"Tool {function_name} failed: {error}"

            tool_summary.append(content)

        # Create a single message with all tool results
        combined_message = "Tool execution results:\n\n" + \
            "\n\n---\n\n".join(tool_summary)

        # Add specific instructions based on what tools were used
        instructions = []

        if any("shell_exec" in r["function_name"] for r in tool_results):
            instructions.append(
                "The shell command output has already been displayed to the user above. Please provide helpful context or summary, but do NOT repeat the raw output.")

        if any("file_create" in r["function_name"] or "file_edit" in r["function_name"] for r in tool_results):
            instructions.append(
                "The file content/diff has already been displayed to the user. Do NOT repeat or show the code again.")

        if instructions:
            combined_message += "\n\nIMPORTANT INSTRUCTIONS:\n" + \
                "\n".join(instructions)

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
                    "result": {
                        "success": True,
                        "message": "No changes needed - file content is already as requested"
                    }
                }

            # Ensure status is stopped if it exists
            if hasattr(self, '_current_status') and self._current_status:
                self._current_status.stop()
                await asyncio.sleep(0.1)

            # Display the diff preview
            display_diff_preview(
                edit_result["diff_preview"], edit_result["file_path"])

            # Ask for confirmation with interactive menu
            if os.getenv("SONGBIRD_AUTO_APPLY") == "y":
                user_confirmed = True
            else:
                selected_index = await safe_interactive_menu(
                    "Apply these changes?",
                    ["Yes", "No"],
                    default_index=0
                )
                if selected_index is None:
                    # Handle cancellation 
                    return {
                        "success": False,
                        "result": {
                            "success": False,
                            "message": "Changes cancelled by user"
                        }
                    }
                user_confirmed = (selected_index == 0)

            if user_confirmed:
                # Apply the edit
                apply_result = await apply_file_edit(
                    arguments["file_path"],
                    arguments["new_content"]
                )

                if apply_result["success"]:
                    return {
                        "success": True,
                        "result": {
                            "success": True,
                            "message": apply_result["message"],
                            "file_path": apply_result["file_path"],
                            "diff_displayed": True
                        }
                    }
                else:
                    return {
                        "success": False,
                        "result": apply_result
                    }
            else:
                return {
                    "success": False,
                    "result": {
                        "success": False,
                        "message": "Changes cancelled by user"
                    }
                }

        except Exception as e:
            return {
                "success": False,
                "result": {
                    "success": False,
                    "error": f"Error handling file edit: {e}"
                }
            }
