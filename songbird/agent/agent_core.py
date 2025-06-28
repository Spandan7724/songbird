# songbird/agent/agent_core.py
"""Agent Core - handles planning, decision logic, and conversation flow."""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Protocol
from datetime import datetime

from ..llm.providers import BaseProvider
from ..ui.data_transfer import UIMessage, AgentOutput, MessageType
from ..memory.models import Session, Message
from ..memory.manager import SessionManager
from ..tools.todo_tools import auto_complete_todos_from_message
from .planning import AgentPlan, PlanStep, PlanStatus
from .plan_manager import PlanManager
from ..config.config_manager import get_config

# Configure logger for agent core
logger = logging.getLogger(__name__)


class ToolRunnerProtocol(Protocol):
    """Protocol for tool execution."""
    
    async def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool with given arguments."""
        ...
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools."""
        ...


class AgentCore:
    """Core agent logic - planning, decision making, conversation orchestration."""
    
    def __init__(
        self, 
        provider: BaseProvider, 
        tool_runner: ToolRunnerProtocol,
        session: Optional[Session] = None,
        session_manager: Optional[SessionManager] = None
    ):
        self.provider = provider
        self.tool_runner = tool_runner
        self.session = session
        self.session_manager = session_manager
        self.conversation_history: List[Dict[str, Any]] = []
        self.current_plan: Optional[AgentPlan] = None
        self.plan_manager = PlanManager()
        
        # Load system prompt from centralized prompts
        from ..prompts import get_core_system_prompt
        self.system_prompt = get_core_system_prompt()

    async def handle_message(self, user_message: str) -> AgentOutput:
        """Handle a user message and return appropriate output."""
        try:
            # Auto-complete todos if we have a session
            if self.session:
                completed_ids = await auto_complete_todos_from_message(
                    user_message, self.session.id, self.provider
                )
                if completed_ids:
                    # TODO: Handle auto-completed todos
                    pass
            
            # Add user message to history
            self.conversation_history.append({
                "role": "user",
                "content": user_message
            })
            
            # Add to session if available
            if self.session:
                user_msg = Message(role="user", content=user_message)
                self.session.add_message(user_msg)
                if self.session_manager:
                    self.session_manager.save_session(self.session)
            
            # Generate plan if needed (for complex tasks)
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
                    # Parse and store the plan
                    plan = await self.plan_manager.parse_plan_from_response(response.content)
                    if plan:
                        self.plan_manager.set_current_plan(plan)
                        self.current_plan = plan
                        
                        # Display the plan to the user
                        await self._display_plan(plan)
                        
        except Exception as e:
            # If planning fails, continue without a plan
            pass
    
    async def _display_plan(self, plan) -> None:

        try:
            from rich.console import Console
            from rich.panel import Panel
            from rich.text import Text
            
            console = Console()

            plan_display = Text()
            plan_display.append(f"{plan.goal}\n\n", style="white")
            
            for i, step in enumerate(plan.steps, 1):
                # Handle both dict and PlanStep object formats
                if hasattr(step, 'action'):  # PlanStep object
                    action = step.action
                    args = step.args
                    description = step.description
                else:  # Dict format
                    action = step.get('action', 'unknown')
                    args = step.get('args', {})
                    description = step.get('description', '')
                

                plan_display.append(" • ", style="blue")
                
                # Format step description based on action
                if action == 'file_create':
                    file_path = args.get('file_path', 'unknown')
                    plan_display.append(f"Create file ", style="white")
                    plan_display.append(f"{file_path}", style="cyan")
                elif action == 'file_edit':
                    file_path = args.get('file_path', 'unknown')
                    plan_display.append(f"Edit file ", style="white")
                    plan_display.append(f"{file_path}", style="cyan")
                elif action == 'file_read':
                    file_path = args.get('file_path', 'unknown')
                    plan_display.append(f"Read file ", style="white")
                    plan_display.append(f"{file_path}", style="cyan")
                elif action == 'shell_exec':
                    command = args.get('command', 'unknown')
                    plan_display.append(f"Execute ", style="white")
                    plan_display.append(f"{command}", style="green")
                elif action == 'ls':
                    path = args.get('path', 'current directory')
                    plan_display.append(f"List directory contents of ", style="white")
                    plan_display.append(f"{path}", style="cyan")
                else:
                    # Generic action display
                    formatted_action = action.replace('_', ' ').title()
                    plan_display.append(f"{formatted_action}", style="white")
                    if description:
                        plan_display.append(f" - {description}", style="dim white")
                
                plan_display.append("\n")
            
            # Display plan without panel - minimal style
            console.print("")
            console.print("Plan:", style="bold blue")
            console.print("")
            console.print(plan_display)
            console.print("")
            
        except Exception:
            # Don't fail if plan display has issues
            pass
    
    async def _agentic_loop(self) -> AgentOutput:
        """Main agentic loop for autonomous task execution with adaptive termination."""
        # Get configuration for termination criteria
        config = get_config()
        max_iterations = config.agent.max_iterations  # Configurable emergency brake
        iteration_count = 0
        consecutive_no_tools = 0
        total_tokens_used = 0
        max_tokens_budget = config.agent.token_budget  # Configurable token budget
        
        # Track repeated failed tool calls to detect infinite loops
        recent_failed_calls = []
        max_repeated_failures = 3
        
        # Logging for long-task diagnosis
        loop_start_time = datetime.now()
        logger.info(f"Starting agentic loop with max_iterations={max_iterations}, token_budget={max_tokens_budget}")
        
        # Enable verbose logging if configured
        verbose_logging = config.ui.verbose_logging
        
        while iteration_count < max_iterations:
            iteration_count += 1
            iteration_start_time = datetime.now()
            
            if verbose_logging:
                logger.debug(f"Iteration {iteration_count}: Starting with {consecutive_no_tools} consecutive no-tool turns")
            
            # Get available tools
            tools = self.tool_runner.get_available_tools()
            
            # Build messages for LLM
            messages = self._build_messages_for_llm()
            
            # Get LLM response
            if verbose_logging:
                logger.debug(f"Iteration {iteration_count}: Requesting LLM response with {len(tools)} tools available")
            
            response = await self.provider.chat_with_messages(messages, tools=tools)
            
            # Track token usage (approximate)
            if response.content:
                total_tokens_used += len(response.content.split()) * 1.3  # Rough approximation
            
            # Handle the response
            if response.tool_calls:
                # Reset consecutive no-tool counter
                consecutive_no_tools = 0
                
                if verbose_logging:
                    logger.debug(f"Iteration {iteration_count}: Executing {len(response.tool_calls)} tool calls")
                
                # Execute tools and continue loop
                tool_results = await self._execute_tools(response.tool_calls)
                
                # Check for repeated failed tool calls (infinite loop detection)
                if self._detect_repeated_failures(tool_results, recent_failed_calls, max_repeated_failures):
                    logger.warning(f"Iteration {iteration_count}: Detected repeated failures - terminating loop")
                    await self._add_assistant_message_to_history(response, tool_results)
                    assistant_message = UIMessage.assistant(
                        "I've detected that I'm repeating the same failed operation. The task appears to be complete or I need different instructions to proceed."
                    )
                    return AgentOutput.completion(assistant_message)
                
                # Check if recent successful operations suggest task completion
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
        if iteration_count < 5:  # Don't terminate too early - increased from 3
            return False
        
        # Get configuration to make completion detection configurable
        config = get_config()
        if not config.agent.adaptive_termination:
            return False  # Let user control termination if adaptive is disabled
        
        # Check if we just had successful file operations that likely fulfill the request
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
        
        # Don't terminate if there are recent failures - the task may need more work
        if failed_ops > 0:
            return False
        
        # More conservative completion detection to prevent premature termination
        # Only terminate if we have many iterations with successful operations,
        # indicating the task is truly complete
        
        # For file operations, require more iterations to avoid cutting off multi-file tasks
        if successful_file_ops > 0 and iteration_count >= 12:
            # Additional check: only terminate if no plan is active or plan is complete
            if self.current_plan and not self.plan_manager.is_plan_complete():
                return False
            return True
        
        # For shell operations, be even more conservative since they're often part of larger workflows
        if successful_shell_ops > 0 and iteration_count >= 15:
            # Additional check: only terminate if no plan is active or plan is complete
            if self.current_plan and not self.plan_manager.is_plan_complete():
                return False
            return True
            
        return False
    
    async def _add_assistant_message_to_history(self, response: Any, tool_results: List[Dict[str, Any]]) -> None:
        """Add assistant message with tool calls to conversation history."""
        # Convert tool calls to serializable format
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
        
        # Add tool results
        for tool_result in tool_results:
            self.conversation_history.append({
                "role": "tool",
                "content": json.dumps(tool_result["result"], indent=2),
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
                tool_msg = Message(
                    role="tool",
                    content=json.dumps(tool_result["result"], indent=2),
                    tool_call_id=tool_result["tool_call_id"],
                    name=tool_result["function_name"]
                )
                self.session.add_message(tool_msg)
            
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
        """Get the current conversation history."""
        return self.conversation_history.copy()
    
    def set_current_plan(self, plan: AgentPlan) -> None:
        """Set the current execution plan."""
        self.current_plan = plan
    
    def get_current_plan(self) -> Optional[AgentPlan]:
        """Get the current execution plan."""
        return self.current_plan
    
    async def _should_terminate_loop(self, iteration_count: int, consecutive_no_tools: int, 
                                   total_tokens_used: int, max_tokens_budget: int) -> bool:
        """Check if the agentic loop should terminate based on adaptive criteria."""
        
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