# Agent Core - handles planning, decision logic, and conversation flow.

import json
import logging
from typing import Any, Dict, List, Optional, Protocol
from datetime import datetime

from rich.text import Text

from ..llm.providers import BaseProvider
from ..ui.data_transfer import UIMessage, AgentOutput
from ..memory.models import Session, Message
from ..memory.optimized_manager import OptimizedSessionManager

from .planning import AgentPlan, PlanStatus
from .plan_manager import PlanManager
from ..config.config_manager import get_config
from .message_classifier import MessageClassifier
from .context_manager import FileContextManager

logger = logging.getLogger(__name__)


class ToolRunnerProtocol(Protocol):
    
    async def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        ...
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        ...


class AgentCore:
    """Core agent logic - planning, decision making, conversation orchestration."""
    
    def __init__(
        self, 
        provider: BaseProvider, 
        tool_runner: ToolRunnerProtocol,
        session: Optional[Session] = None,
        session_manager: Optional[OptimizedSessionManager] = None,
        quiet_mode: bool = False
    ):
        self.provider = provider
        self.tool_runner = tool_runner
        self.session = session
        self.session_manager = session_manager
        self.quiet_mode = quiet_mode
        self.conversation_history: List[Dict[str, Any]] = []
        self.current_plan: Optional[AgentPlan] = None
        self.plan_manager = PlanManager()
        self.message_classifier = MessageClassifier(self.provider)
        self.file_context_manager = FileContextManager()
        
        # Load system prompt from centralized prompts
        from ..prompts import get_core_system_prompt
        self.system_prompt = get_core_system_prompt()

    async def handle_message(self, user_message: str) -> AgentOutput:
        """Handle a user message and return appropriate output."""
        try:
            # Process file references first to enhance the message with file context
            enhanced_message, file_contexts = await self.file_context_manager.process_message_with_file_context(user_message)
            
            # Show file context summary if files were included (and not in quiet mode)
            if file_contexts and not self.quiet_mode:
                from rich.console import Console
                console = Console()
                summary = self.file_context_manager.get_file_summary(file_contexts)
                console.print(f"[dim]{summary}[/dim]")
            
            # Track referenced files in session
            if file_contexts and self.session:
                for ctx in file_contexts:
                    if not ctx.error:  # Only track successfully loaded files
                        self.session.add_referenced_file(
                            ctx.file_path, 
                            {
                                "relative_path": ctx.relative_path,
                                "line_count": ctx.line_count,
                                "size_bytes": ctx.size_bytes
                            }
                        )
            
            # Use enhanced message for processing
            processed_message = enhanced_message
            

            from ..tools.semantic_config import get_semantic_config
            config = get_semantic_config()
            

            # NOTE: Auto-completion now happens AFTER tool execution (better timing)
            if self.session:

                if config.enable_auto_todo_creation:
                    await self._auto_create_todos_if_needed(user_message)
            
            # Add enhanced message to history (this is what the LLM will see)
            self.conversation_history.append({
                "role": "user",
                "content": processed_message
            })
            
            # Add to session if available (store original user message for session history)
            if self.session:
                user_msg = Message(role="user", content=user_message)
                self.session.add_message(user_msg)
                if self.session_manager:
                    self.session_manager.save_session(self.session)
            
            # Generate plan if needed (for complex tasks - use original message)
            await self._generate_plan_if_needed(user_message)
            
            # Process the message through the agentic loop
            return await self._agentic_loop()
            
        except Exception as e:
            return AgentOutput.error_response(f"Error processing message: {str(e)}")
    
    async def _generate_plan_if_needed(self, user_message: str) -> None:
        """Generate execution plan for complex tasks."""
        try:
            # Check if we need to generate a plan
            plan_prompt = await self.plan_manager.generate_plan_prompt(
                user_message, 
                {"conversation_history": self.conversation_history}
            )
            
            if plan_prompt:  # Non-empty means planning is needed
                # Use LLM to generate plan
                messages = [{"role": "user", "content": plan_prompt}]
                response = await self.provider.chat_with_messages(messages)
                
                if response.content:

                    plan = await self.plan_manager.parse_plan_from_response(response.content)
                    if plan:
                        self.plan_manager.set_current_plan(plan)
                        self.current_plan = plan

                        await self._display_plan(plan)
                        
        except Exception:
            pass
    
    async def _display_plan(self, plan) -> None:
        if self.quiet_mode:
            return
            
        try:
            from rich.console import Console
            from rich.text import Text
            
            console = Console()

            plan_display = Text()
            plan_display.append(f"{plan.goal}\n\n", style="white")
            
            for i, step in enumerate(plan.steps, 1):
                if hasattr(step, 'action'):
                    action = step.action
                    args = step.args
                    description = step.description
                else:
                    action = step.get('action', 'unknown')
                    args = step.get('args', {})
                    description = step.get('description', '')
                

                plan_display.append(" • ", style="spring_green1")
                
                if action == 'file_create':
                    file_path = args.get('file_path', 'unknown')
                    plan_display.append("Create file ", style="white")
                    plan_display.append(f"{file_path}", style="cyan")
                elif action == 'file_edit':
                    file_path = args.get('file_path', 'unknown')
                    plan_display.append("Edit file ", style="white")
                    plan_display.append(f"{file_path}", style="cyan")
                elif action == 'file_read':
                    file_path = args.get('file_path', 'unknown')
                    plan_display.append("Read file ", style="white")
                    plan_display.append(f"{file_path}", style="cyan")
                elif action == 'shell_exec':
                    command = args.get('command', 'unknown')
                    plan_display.append("Execute ", style="white")
                    plan_display.append(f"{command}", style="green")
                elif action == 'ls':
                    path = args.get('path', 'current directory')
                    plan_display.append("List directory contents of ", style="white")
                    plan_display.append(f"{path}", style="cyan")
                else:
                    formatted_action = action.replace('_', ' ').title()
                    plan_display.append(f"{formatted_action}", style="white")
                    if description:
                        plan_display.append(f" - {description}", style="dim white")
                
                plan_display.append("\n")
            
            console.print("")
            console.print("Plan:", style="spring_green1")
            console.print("")
            console.print(plan_display)
            console.print("")
            
        except Exception:
            pass
    
    async def _agentic_loop(self) -> AgentOutput:
        config = get_config()
        max_iterations = config.agent.max_iterations
        iteration_count = 0
        consecutive_no_tools = 0
        total_tokens_used = 0
        max_tokens_budget = config.agent.token_budget  # Configurable token budget
        
        recent_failed_calls = []
        max_repeated_failures = 3
        
        loop_start_time = datetime.now()
        logger.info(f"Starting agentic loop with max_iterations={max_iterations}, token_budget={max_tokens_budget}")
        
        verbose_logging = config.ui.verbose_logging
        
        while iteration_count < max_iterations:
            iteration_count += 1
            iteration_start_time = datetime.now()
            
            if verbose_logging:
                logger.debug(f"Iteration {iteration_count}: Starting with {consecutive_no_tools} consecutive no-tool turns")
            
            tools = self.tool_runner.get_available_tools()
            
            messages = self._build_messages_for_llm()
            
            if verbose_logging:
                logger.debug(f"Iteration {iteration_count}: Requesting LLM response with {len(tools)} tools available")
            
            response = await self.provider.chat_with_messages(messages, tools=tools)
            
            if response.content:
                total_tokens_used += len(response.content.split()) * 1.3  # Rough approximation
            
            if response.tool_calls:
                consecutive_no_tools = 0
                
                if verbose_logging:
                    logger.debug(f"Iteration {iteration_count}: Executing {len(response.tool_calls)} tool calls")
                
                tool_results = await self._execute_tools(response.tool_calls)
                
                if self._detect_repeated_failures(tool_results, recent_failed_calls, max_repeated_failures):
                    logger.warning(f"Iteration {iteration_count}: Detected repeated failures - terminating loop")
                    await self._add_assistant_message_to_history(response, tool_results)
                    assistant_message = UIMessage.assistant(
                        "I've detected that I'm repeating the same failed operation. The task appears to be complete or I need different instructions to proceed."
                    )
                    return AgentOutput.completion(assistant_message)
                
                if self._detect_likely_completion(tool_results, iteration_count):
                    logger.info(f"Iteration {iteration_count}: Detected likely task completion - terminating loop")
                    await self._add_assistant_message_to_history(response, tool_results)
                    assistant_message = UIMessage.assistant(
                        "Task appears to be completed successfully based on the recent successful operations."
                    )
                    return AgentOutput.completion(assistant_message)
                
                # Add assistant message with tool calls to history
                await self._add_assistant_message_to_history(response, tool_results)
                
                # Check ONLY extreme termination criteria when tools are being used
                if total_tokens_used > max_tokens_budget:
                    logger.warning(f"Iteration {iteration_count}: Token budget exceeded ({total_tokens_used}/{max_tokens_budget}) - terminating")
                    assistant_message = UIMessage.assistant(
                        f"I've completed {iteration_count} steps and reached the token budget limit. Stopping here."
                    )
                    return AgentOutput.completion(assistant_message)
                elif iteration_count >= max_iterations - 1:  # Emergency brake
                    logger.warning(f"Iteration {iteration_count}: Maximum iterations reached - emergency termination")
                    assistant_message = UIMessage.assistant(
                        f"I've completed {iteration_count} steps (maximum reached). The task may require additional work."
                    )
                    return AgentOutput.completion(assistant_message)
                
                # Continue loop for next iteration
                continue
            else:
                # No tool calls - increment counter
                consecutive_no_tools += 1
                
                if verbose_logging:
                    logger.debug(f"Iteration {iteration_count}: No tool calls, consecutive count: {consecutive_no_tools}")
                
                # Check if we should terminate due to no tool usage
                if consecutive_no_tools >= 2:
                    logger.info(f"Iteration {iteration_count}: Two consecutive no-tool turns - terminating (task likely complete)")
                    # Two consecutive turns without tools - task likely complete
                    await self._add_final_assistant_message(response)
                    assistant_message = UIMessage.assistant(response.content or "")
                    return AgentOutput.completion(assistant_message)
                elif await self._should_terminate_loop(iteration_count, consecutive_no_tools, total_tokens_used, max_tokens_budget):
                    # Other termination criteria met
                    await self._add_final_assistant_message(response)
                    assistant_message = UIMessage.assistant(response.content or "")
                    return AgentOutput.completion(assistant_message)
                else:
                    # Add message and continue (might need clarification)
                    await self._add_final_assistant_message(response)
                    assistant_message = UIMessage.assistant(response.content or "")
                    return AgentOutput.completion(assistant_message)
        
        # Maximum iterations reached
        loop_duration = datetime.now() - loop_start_time
        logger.warning(f"Agentic loop terminated after {iteration_count} iterations in {loop_duration}")
        logger.info(f"Final stats: {total_tokens_used} tokens used, {consecutive_no_tools} consecutive no-tool turns")
        
        assistant_message = UIMessage.assistant(
            "I've reached the maximum number of steps for this task. The work may be incomplete."
        )
        return AgentOutput.completion(assistant_message)
    
    def _build_messages_for_llm(self) -> List[Dict[str, Any]]:
        """Build messages in the format expected by the LLM."""
        system_content = self.system_prompt
        
        # Add plan context if we have a current plan
        if self.current_plan:
            next_step = self.plan_manager.get_next_step()
            completed_steps = [step for step in self.current_plan.steps if step.status == PlanStatus.COMPLETED]
            
            plan_context = f"""

CURRENT EXECUTION PLAN:
Goal: {self.current_plan.goal}
Progress: {len(completed_steps)}/{len(self.current_plan.steps)} steps completed

NEXT STEP: {next_step.description if next_step else "Plan completed"}
{f"Tool: {next_step.action}" if next_step and next_step.action else ""}

Remember to follow the plan systematically. Complete the current step before moving to the next one."""
            
            system_content += plan_context
        
        messages = [{"role": "system", "content": system_content}]
        messages.extend(self.conversation_history)
        return messages
    
    async def _execute_tools(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute tool calls and return results."""
        tool_results = []
        
        for tool_call in tool_calls:
            try:
                # Parse tool call (handle different formats)
                function_name, arguments = self._parse_tool_call(tool_call)
                
                # Execute the tool
                result = await self.tool_runner.execute_tool(function_name, arguments)
                
                # Check if this tool completed any todos (real-time completion detection)
                if self.session and result.get("success"):
                    from ..tools.todo_tools import analyze_tool_completion
                    from ..tools.todo_manager import TodoManager
                    
                    todo_manager = TodoManager(session_id=self.session.id)
                    active_todos = [
                        t for t in todo_manager.get_current_session_todos() 
                        if t.status in ['pending', 'in_progress']
                    ]
                    
                    if active_todos:
                        completed_ids = await analyze_tool_completion(
                            function_name,
                            arguments,
                            active_todos,
                            self.provider
                        )
                        
                        # Mark todos as completed
                        for todo_id in completed_ids:
                            todo_manager.complete_todo(todo_id)
                        
                        # If any todos were completed, show updated todo list
                        if completed_ids:
                            from ..tools.todo_tools import todo_read
                            await todo_read(session_id=self.session.id, show_completed=True)
                
                # Update plan if we have one and this tool matches the next step
                if self.current_plan:
                    next_step = self.plan_manager.get_next_step()
                    if next_step and next_step.action == function_name:
                        # Interpret result with better logic for shell commands
                        is_success = self._interpret_tool_result(function_name, result)
                        if is_success:
                            self.plan_manager.mark_step_completed(next_step.step_id, result)
                        else:
                            self.plan_manager.mark_step_failed(next_step.step_id, result.get("error", "Tool execution failed"))
                
                # Format result
                tool_call_id = self._get_tool_call_id(tool_call)
                tool_results.append({
                    "tool_call_id": tool_call_id,
                    "function_name": function_name,
                    "result": result
                })
                
            except Exception as e:
                # Handle tool execution error
                tool_call_id = self._get_tool_call_id(tool_call)
                tool_results.append({
                    "tool_call_id": tool_call_id,
                    "function_name": function_name if 'function_name' in locals() else "unknown",
                    "result": {"success": False, "error": str(e)}
                })
        
        return tool_results
    
    def _parse_tool_call(self, tool_call: Any) -> tuple[str, Dict[str, Any]]:
        """Parse tool call from different provider formats."""
        if hasattr(tool_call, 'function'):
            # Ollama ToolCall objects
            function_name = tool_call.function.name
            arguments = tool_call.function.arguments
        elif isinstance(tool_call, dict) and "function" in tool_call:
            # Gemini/dict format
            function_name = tool_call["function"]["name"]
            arguments = tool_call["function"]["arguments"]
        else:
            raise ValueError(f"Unknown tool call format: {type(tool_call)}")
        
        # Ensure arguments is a dict
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                raise ValueError(f"Could not parse tool arguments: {arguments}")
        
        if not isinstance(arguments, dict):
            raise ValueError(f"Tool arguments must be a dict, got {type(arguments)}")
        
        return function_name, arguments
    
    def _get_tool_call_id(self, tool_call: Any) -> str:
        """Get tool call ID from different formats."""
        if hasattr(tool_call, 'id'):
            return tool_call.id or ""
        elif isinstance(tool_call, dict):
            return tool_call.get("id", "")
        else:
            return ""
    
    def _interpret_tool_result(self, function_name: str, result: Dict[str, Any]) -> bool:
        """Interpret tool results more intelligently, especially for shell commands."""
        # Default success check
        if result.get("success", True):
            return True
        
        # Special handling for shell commands
        if function_name == "shell_exec":
            stderr = result.get("stderr", "")
            command = result.get("command", "")
            
            # Handle "File exists" errors for mkdir as partial success
            if "mkdir" in command and "File exists" in stderr:
                return True  # Directory already exists - this is actually success
            
            # Handle other common "partial success" cases
            if "chmod" in command and "Operation not permitted" in stderr:
                return False  # This is a real failure
                
        # For other tools, trust the success flag
        return result.get("success", True)
    
    def _detect_repeated_failures(self, tool_results: List[Dict[str, Any]], 
                                 recent_failed_calls: List[str], 
                                 max_repeated_failures: int) -> bool:
        """Detect if we're repeating the same failed tool calls (infinite loop)."""
        for result in tool_results:
            function_name = result.get("function_name", "")
            tool_result = result.get("result", {})
            
            # Check if this is a failed call
            if not self._interpret_tool_result(function_name, tool_result):
                # Create a signature for this failed call
                command = tool_result.get("command", "")
                error = tool_result.get("stderr", "") or tool_result.get("error", "")
                failure_signature = f"{function_name}:{command}:{error}"
                
                # Add to recent failures (keep only recent ones)
                recent_failed_calls.append(failure_signature)
                if len(recent_failed_calls) > max_repeated_failures * 2:
                    recent_failed_calls.pop(0)
                
                # Check if we've seen this failure too many times recently
                recent_count = recent_failed_calls.count(failure_signature)
                if recent_count >= max_repeated_failures:
                    return True
        
        return False
    
    def _detect_likely_completion(self, tool_results: List[Dict[str, Any]], iteration_count: int) -> bool:
        """Detect if task is likely complete based on successful operations."""
        if iteration_count < 5: 
            return False
        
        config = get_config()
        if not config.agent.adaptive_termination:
            return False
        
        successful_file_ops = 0
        successful_shell_ops = 0
        failed_ops = 0
        
        for result in tool_results:
            function_name = result.get("function_name", "")
            tool_result = result.get("result", {})
            
            if self._interpret_tool_result(function_name, tool_result):
                if function_name in ["file_create", "file_edit", "file_read"]:
                    successful_file_ops += 1
                elif function_name == "shell_exec":
                    successful_shell_ops += 1
            else:
                failed_ops += 1
        
        if failed_ops > 0:
            return False
        
        # Only terminate if we have many iterations with successful operations,
        # indicating the task is truly complete
        
        # For file operations, require more iterations to avoid cutting off multi-file tasks
        if successful_file_ops > 0 and iteration_count >= 12:
            if self.current_plan and not self.plan_manager.is_plan_complete():
                return False
            return True
        
        if successful_shell_ops > 0 and iteration_count >= 15:
            # Additional check: only terminate if no plan is active or plan is complete
            if self.current_plan and not self.plan_manager.is_plan_complete():
                return False
            return True
            
        return False
    
    async def _add_assistant_message_to_history(self, response: Any, tool_results: List[Dict[str, Any]]) -> None:
        serializable_tool_calls = []
        if response.tool_calls:
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
        
        # Add assistant message
        self.conversation_history.append({
            "role": "assistant",
            "content": response.content or "",
            "tool_calls": serializable_tool_calls
        })
        
        for tool_result in tool_results:
            # Sanitize tool result before JSON serialization
            sanitized_result = self._sanitize_for_json(tool_result["result"])
            self.conversation_history.append({
                "role": "tool",
                "content": json.dumps(sanitized_result, indent=2),
                "tool_call_id": tool_result["tool_call_id"],
                "name": tool_result["function_name"]
            })
        
        # Add to session if available
        if self.session:
            assistant_msg = Message(
                role="assistant",
                content=response.content or "",
                tool_calls=serializable_tool_calls
            )
            self.session.add_message(assistant_msg)
            
            # Add tool results as separate messages
            for tool_result in tool_results:
                # Sanitize tool result before JSON serialization
                sanitized_result = self._sanitize_for_json(tool_result["result"])
                tool_msg = Message(
                    role="tool",
                    content=json.dumps(sanitized_result, indent=2),
                    tool_call_id=tool_result["tool_call_id"],
                    name=tool_result["function_name"]
                )
                self.session.add_message(tool_msg)
            
            # Note: Auto-completion now handled in real-time during tool execution (lines 356-382)
            
            # Force immediate flush of session after adding all messages
            if self.session_manager:
                await self.session_manager.flush_session(self.session)
    
    async def _add_final_assistant_message(self, response: Any) -> None:
        """Add final assistant message without tool calls."""
        self.conversation_history.append({
            "role": "assistant",
            "content": response.content or ""
        })
        
        # Add to session if available
        if self.session:
            assistant_msg = Message(
                role="assistant",
                content=response.content or ""
            )
            self.session.add_message(assistant_msg)
            
            # Force immediate flush of session
            if self.session_manager:
                await self.session_manager.flush_session(self.session)
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        return self.conversation_history.copy()
    
    def set_current_plan(self, plan: AgentPlan) -> None:
        self.current_plan = plan
    
    def get_current_plan(self) -> Optional[AgentPlan]:
        return self.current_plan
    
    async def _should_terminate_loop(self, iteration_count: int, consecutive_no_tools: int, 
                                   total_tokens_used: int, max_tokens_budget: int) -> bool:
        # Check if the agentic loop should terminate based on adaptive criteria.
        
        # 1. Token budget exceeded
        if total_tokens_used > max_tokens_budget:
            return True
        
        # 2. Too many consecutive turns without tools (task likely complete)
        if consecutive_no_tools >= 2:
            return True
        
        # 3. Plan is complete (if we have a plan)
        if self.plan_manager.is_plan_complete():
            return True
        
        # 4. Plan has failed (if we have a plan)
        if self.plan_manager.has_plan_failed():
            return True
        
        # 5. Iteration count is getting high (warning threshold)
        if iteration_count >= 10:
            # After 10 iterations, be more strict about termination
            if consecutive_no_tools >= 1:
                return True
        
        # Continue by default
        return False
    
    async def _auto_create_todos_if_needed(self, user_message: str) -> None:
        if not self.session:
            return
        
        # Check configuration
        from ..tools.semantic_config import get_semantic_config
        config = get_semantic_config()
        
        # Skip if disabled
        if not config.enable_auto_todo_creation:
            return
        
        # Quick check: skip very short messages
        if len(user_message.split()) < config.auto_todo_min_words:
            return
        
        # Use LLM-based classification to determine if auto-creation is appropriate
        try:
            # Get existing todos for context
            from ..tools.todo_manager import TodoManager
            todo_manager = TodoManager(session_id=self.session.id)
            existing_todos = todo_manager.get_current_session_todos()
            
            # Build context for classifier
            context = {
                'existing_todos_count': len(existing_todos),
                'recent_auto_creation': self._check_recent_auto_creation(),
                'conversation_length': len(self.conversation_history)
            }
            
            # Classify the message using LLM
            intent = await self.message_classifier.classify_message(user_message, context)
            
            # Auto-create todos based on LLM classification
            from ..tools.semantic_config import get_semantic_config
            config = get_semantic_config()
            if intent.should_auto_create_todos and intent.confidence > config.llm_confidence_threshold:
                # Use LLM to generate appropriate todos for this request
                todos = await self._generate_todos_for_request(user_message, existing_todos)
                
                if todos:
                    # Limit the number of todos created
                    limited_todos = todos[:config.auto_todo_max_per_message]
                    
                    from ..tools.todo_tools import todo_write
                    await todo_write(limited_todos, session_id=self.session.id, llm_provider=self.provider)
                    
                    # Show a subtle message that todos were created
                    from rich.console import Console
                    console = Console()
                    console.print(f"[dim]Created {len(limited_todos)} todos for this task[/dim]")
                
        except Exception:
            # Silently fail if todo generation doesn't work
            pass
    
    def _check_recent_auto_creation(self) -> bool:
        if not self.conversation_history:
            return False
        
        # Look at the last few messages to see if we recently created todos
        recent_messages = self.conversation_history[-6:]  # Last 3 turns (user + assistant)
        
        for message in recent_messages:
            if message.get('role') == 'assistant':
                content = message.get('content', '')
                # Check if this message indicates recent todo creation
                if 'Created' in content and 'todos' in content:
                    return True
        
        return False
    
    async def _generate_todos_for_request(self, user_message: str, existing_todos: List = None) -> List[Dict[str, Any]]:

        existing_todos = existing_todos or []
        
        # Build existing todos context
        existing_context = ""
        if existing_todos:
            existing_list = []
            for todo in existing_todos:
                existing_list.append(f'- {todo.content} (status: {todo.status})')
            existing_context = f"""

EXISTING TODOS IN THIS SESSION:
{chr(10).join(existing_list)}

IMPORTANT: Do NOT create todos that are similar to or duplicate the existing ones above. Focus on different aspects or complementary tasks."""
        

        prompt = f"""
Analyze this request and generate appropriate todos: "{user_message}"{existing_context}

CRITICAL RULES FOR TODO GENERATION:
1. Create todos at the RIGHT level of granularity
2. One todo per ACTUAL unit of work that would be done separately
3. If multiple things will be done in one action, make it ONE todo
4. Think like a developer - what are the logical chunks of work?

GOOD Examples:
- "Create a Python file with BFS implementation" → 1 todo: "implement-bfs-algorithm"
- "Build a REST API with auth" → 3-4 todos: "setup-api-structure", "implement-endpoints", "add-authentication", "add-tests"
- "Fix the login bug and update docs" → 2 todos: "fix-login-bug", "update-documentation"

BAD Examples (TOO GRANULAR):
- "Create a Python file with BFS" → 4 todos: "create-file", "write-algorithm", "add-inputs", "call-function"
- "Implement feature" → 6 todos: "create-file", "add-imports", "write-function", "add-variables", "call-function", "print-result"

Guidelines for Granularity:
- One file creation with implementation = ONE todo
- Each separate feature/component = ONE todo  
- Each major refactor = ONE todo
- Each distinct bug fix = ONE todo
- Don't break down actions that happen together in one file/command

Technical Rules:
1. Use semantic IDs in kebab-case (e.g., "implement-auth-service", "add-unit-tests")
2. Include appropriate priorities (high/medium/low)
3. Make each todo specific and actionable
4. Avoid duplicating existing todos
5. Generate 1-5 todos (not 3-7) - focus on quality over quantity

Return ONLY a JSON array in this format:
[
  {{"id": "implement-bfs-algorithm", "content": "Implement BFS algorithm in Python", "priority": "high"}},
  {{"id": "add-algorithm-tests", "content": "Add unit tests for the algorithm", "priority": "medium"}}
]
"""
        
        try:
            # Use the LLM to generate todos
            messages = [{"role": "user", "content": prompt}]
            response = await self.provider.chat_with_messages(messages)
            
            if response.content:
                # Extract JSON from response
                import json
                import re
                
                # Look for JSON array in the response
                json_match = re.search(r'\[.*?\]', response.content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    todos = json.loads(json_str)
                    
                    # Validate and return todos
                    if isinstance(todos, list) and all(
                        isinstance(todo, dict) and 
                        'id' in todo and 'content' in todo 
                        for todo in todos
                    ):
                        return todos
                        
        except Exception:
            pass
        
        return []  # Return empty list if generation fails
    

    
    def _describe_tool_accomplishment(self, tool_name: str, result: Dict[str, Any]) -> Optional[str]:
        """Convert a successful tool execution into a detailed, context-rich accomplishment description."""
        if not result.get("success"):
            return None
        
        if tool_name == "file_create":
            filename = result.get('filename', 'unknown file')
            content_info = ""
            
            # Extract content hints from the result
            if 'content' in result:
                content = str(result['content']).lower()  # Full content for analysis
                content_preview = content[:100]  # First 100 chars for display
                
                # Look for specific patterns
                patterns = []
                if 'def ' in content_preview or 'class ' in content_preview:
                    patterns.append("Python code")
                elif 'function' in content_preview or '=>' in content_preview:
                    patterns.append("JavaScript code")
                
                if 'algorithm' in content or 'bfs' in content:
                    patterns.append("algorithm implementation")
                
                if 'hardcoded' in content or ('graph = {' in content and 'start' in content):
                    patterns.append("hardcoded inputs")
                
                if 'import' in content or 'from ' in content:
                    patterns.append("Python imports")
                    
                if patterns:
                    content_info = f" containing {' and '.join(patterns)}"
                elif content.strip():
                    content_info = f" with content about {content_preview.split()[0] if content_preview.split() else 'code'}"
                else:
                    content_info = ""
            
            # Check filename for hints
            if filename.endswith('.py'):
                if 'bfs' in filename.lower():
                    content_info = content_info or " implementing BFS algorithm"
                elif 'test' in filename.lower():
                    content_info = content_info or " containing test code"
                else:
                    content_info = content_info or " containing Python code"
            elif filename.endswith('.js'):
                content_info = content_info or " containing JavaScript code"
            elif filename.endswith('.json'):
                content_info = content_info or " with configuration data"
            
            return f"Created file '{filename}'{content_info}"
            
        elif tool_name == "file_edit":
            filename = result.get('filename', 'unknown file')
            changes_info = ""
            if 'changes' in result or 'modified' in result:
                changes_info = " with code modifications"
            return f"Edited file '{filename}'{changes_info}"
            
        elif tool_name == "shell_exec":
            command = result.get("command", "")
            output = result.get("output", "")
            
            # Provide detailed context based on command and output
            if command.startswith("python"):
                script_name = command.split()[-1] if len(command.split()) > 1 else "script"
                output_info = ""
                
                if output:
                    output_preview = output[:200]  # First 200 chars of output
                    if 'BFS' in output and 'Order' in output:
                        output_info = f" producing BFS traversal results: {output_preview}"
                    elif 'Error' in output or 'error' in output.lower():
                        output_info = f" with error output: {output_preview}"
                    elif output.strip():
                        output_info = f" with output: {output_preview}"
                
                return f"Successfully executed Python script '{script_name}'{output_info}"
            elif "test" in command:
                return f"Ran tests with command: {command}"
            elif "install" in command:
                return f"Installed dependencies: {command}"
            else:
                output_info = f" (output: {output[:100]})" if output else ""
                return f"Executed command '{command}'{output_info}"
                
        elif tool_name == "file_search":
            pattern = result.get('pattern', 'unknown pattern')
            count = result.get('matches', 0) if 'matches' in result else "some"
            return f"Searched for files matching '{pattern}' and found {count} results"
            
        elif tool_name == "grep":
            pattern = result.get('pattern', 'unknown pattern') 
            count = result.get('matches', 0) if 'matches' in result else "some"
            return f"Searched file contents for '{pattern}' and found {count} matches"
            
        elif tool_name == "todo_write":
            created = result.get('created', 0)
            return f"Created {created} new todo items for task management"
            
        elif tool_name == "todo_read":
            count = result.get('count', 0) if 'count' in result else "current"
            return f"Reviewed {count} items in the todo list"
        else:
            # Generic accomplishment for other tools with more context
            success_msg = result.get('message', '') or result.get('output', '')
            context = f" - {success_msg[:50]}" if success_msg else ""
            return f"Successfully executed {tool_name}{context}"
    

    
    def _sanitize_for_json(self, obj: Any) -> Any:
        """Recursively sanitize objects to make them JSON-serializable."""
        if isinstance(obj, Text):
            # Convert Rich Text objects to plain strings
            return str(obj.plain)
        elif isinstance(obj, dict):
            return {key: self._sanitize_for_json(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._sanitize_for_json(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(self._sanitize_for_json(item) for item in obj)
        elif hasattr(obj, '__dict__'):
            # For objects with __dict__, try to convert to string
            return str(obj)
        else:
            return obj