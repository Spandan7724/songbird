# songbird/ui/ui_layer.py
"""UI Layer - handles all user interface concerns for Songbird."""

import sys
from typing import Optional, Protocol
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from InquirerPy import inquirer

from .data_transfer import (
    UIMessage, UIResponse, UIChoice, UIChoiceType, 
    MessageType
)


class UIProtocol(Protocol):
    """Protocol for UI implementations."""
    
    async def display_message(self, message: UIMessage) -> None:
        """Display a message to the user."""
        ...
    
    async def get_user_input(self, prompt: str = "You") -> UIResponse:
        """Get text input from the user."""
        ...
    
    async def present_choice(self, choice: UIChoice) -> UIResponse:
        """Present a choice menu to the user."""
        ...
    
    async def show_thinking(self, message: str) -> None:
        """Show that the system is thinking/processing."""
        ...
    
    async def hide_thinking(self) -> None:
        """Hide the thinking indicator."""
        ...


class UILayer:
    """Rich-based UI layer for terminal interaction."""
    
    def __init__(self, console: Optional[Console] = None, quiet_mode: bool = False):
        self.console = console or Console()
        self.quiet_mode = quiet_mode
        self._thinking_status = None
        
    async def display_message(self, message: UIMessage) -> None:
        """Display a message with appropriate styling."""
        # In quiet mode, only show final assistant responses
        if self.quiet_mode:
            if message.message_type == MessageType.ASSISTANT:
                # Show only the content without any formatting in quiet mode
                print(message.content)
            elif message.message_type == MessageType.ERROR:
                self._display_error_message(message)
            return
            
        # Normal mode - show all messages
        if message.message_type == MessageType.USER:
            self._display_user_message(message)
        elif message.message_type == MessageType.ASSISTANT:
            self._display_assistant_message(message)
        elif message.message_type == MessageType.SYSTEM:
            self._display_system_message(message)
        elif message.message_type == MessageType.TOOL_RESULT:
            self._display_tool_result(message)
        elif message.message_type == MessageType.ERROR:
            self._display_error_message(message)
    
    def _display_user_message(self, message: UIMessage) -> None:
        """Display user message."""
        self.console.print(f"\n[bold cornflower_blue]You:[/bold cornflower_blue] {message.content}")
    
    def _display_assistant_message(self, message: UIMessage) -> None:
        """Display assistant response with Rich formatting."""
        if message.content:
            # Check if this is code content
            if message.metadata and message.metadata.get("is_code"):
                language = message.metadata.get("language", "text")
                syntax = Syntax(message.content, language, theme="monokai", line_numbers=False)
                panel = Panel(syntax, title="Code", border_style="blue")
                self.console.print(panel)
            else:
                self.console.print(f"\n[medium_spring_green]Songbird:[/medium_spring_green] {message.content}")
    
    def _display_system_message(self, message: UIMessage) -> None:
        """Display system message."""
        style = "dim"
        if message.metadata and "style" in message.metadata:
            style = message.metadata["style"]
        self.console.print(f"[{style}]{message.content}[/{style}]")
    
    def _display_tool_result(self, message: UIMessage) -> None:
        """Display tool execution result."""
        if message.metadata:
            tool_name = message.metadata.get("tool_name", "Tool")
            if message.metadata.get("success", True):
                self.console.print(f"[green]✓ {tool_name}:[/green] {message.content}")
            else:
                self.console.print(f"[red]✗ {tool_name}:[/red] {message.content}")
        else:
            self.console.print(f"[blue]Tool Result:[/blue] {message.content}")
    
    def _display_error_message(self, message: UIMessage) -> None:
        """Display error message."""
        self.console.print(f"[red]Error:[/red] {message.content}")
        
        # Display suggestions if available
        if message.metadata and "suggestions" in message.metadata:
            suggestions = message.metadata["suggestions"]
            if suggestions:
                self.console.print("\n[bold]Suggestions:[/bold]")
                for suggestion in suggestions:
                    self.console.print(f"• {suggestion}", style="dim")
    
    async def get_user_input(self, prompt: str = "You") -> UIResponse:
        """Get user input with async support."""
        try:
            # For now, we'll use a simple input until we implement full async prompt-toolkit
            user_input = input(f"\n{prompt}: ").strip()
            return UIResponse(content=user_input)
        except (KeyboardInterrupt, EOFError):
            return UIResponse(content="", metadata={"cancelled": True})
    
    async def present_choice(self, choice: UIChoice) -> UIResponse:
        """Present a choice menu to the user."""
        if choice.choice_type == UIChoiceType.SINGLE_SELECT:
            return await self._single_select_menu(choice)
        elif choice.choice_type == UIChoiceType.CONFIRM:
            return await self._confirm_dialog(choice)
        elif choice.choice_type == UIChoiceType.TEXT_INPUT:
            return await self._text_input_dialog(choice)
        else:
            raise NotImplementedError(f"Choice type {choice.choice_type} not implemented")
    
    async def _single_select_menu(self, choice: UIChoice) -> UIResponse:
        """Handle single selection menu."""
        try:
            # Try InquirerPy first
            if sys.stdin.isatty():
                result = inquirer.select(
                    message=choice.prompt,
                    choices=choice.options,
                    default=choice.options[choice.default_index] if choice.options else None
                ).execute()
                selected_index = choice.options.index(result)
                return UIResponse(
                    content=result,
                    metadata={"selected_index": selected_index}
                )
        except Exception:
            pass
        
        # Fallback to numbered menu
        return await self._fallback_numbered_menu(choice)
    
    async def _fallback_numbered_menu(self, choice: UIChoice) -> UIResponse:
        """Fallback numbered menu for non-interactive environments."""
        # Auto-select default in non-TTY environments
        if not sys.stdin.isatty():
            default_option = choice.options[choice.default_index]
            self.console.print(f"\n{choice.prompt}")
            for i, option in enumerate(choice.options):
                style = "bold green" if i == choice.default_index else "white"
                self.console.print(f"  {i + 1}. {option}", style=style)
            self.console.print(f"[dim]Auto-selected option {choice.default_index + 1}: {default_option}[/dim]")
            return UIResponse(
                content=default_option,
                metadata={"selected_index": choice.default_index, "auto_selected": True}
            )
        
        # Interactive numbered menu
        self.console.print(f"\n{choice.prompt}")
        for i, option in enumerate(choice.options):
            style = "bold green" if i == choice.default_index else "white"
            self.console.print(f"  {i + 1}. {option}", style=style)
        
        while True:
            try:
                user_choice = input(f"\nSelect option (1-{len(choice.options)}, default={choice.default_index + 1}): ").strip()
                
                if not user_choice:
                    selected_index = choice.default_index
                    break
                
                choice_num = int(user_choice) - 1
                if 0 <= choice_num < len(choice.options):
                    selected_index = choice_num
                    break
                else:
                    self.console.print(f"Invalid choice. Please select 1-{len(choice.options)}", style="red")
            except ValueError:
                self.console.print("Invalid input. Please enter a number.", style="red")
            except (KeyboardInterrupt, EOFError):
                if choice.allow_cancel:
                    return UIResponse(content="", metadata={"cancelled": True})
                else:
                    selected_index = choice.default_index
                    break
        
        return UIResponse(
            content=choice.options[selected_index],
            metadata={"selected_index": selected_index}
        )
    
    async def _confirm_dialog(self, choice: UIChoice) -> UIResponse:
        """Handle confirmation dialog."""
        try:
            result = inquirer.confirm(
                message=choice.prompt,
                default=choice.default_index == 0  # 0 = Yes, 1 = No
            ).execute()
            return UIResponse(
                content="yes" if result else "no",
                metadata={"confirmed": result}
            )
        except Exception:
            # Fallback to text input
            response = input(f"{choice.prompt} (y/n): ").strip().lower()
            confirmed = response in ['y', 'yes', 'true', '1']
            return UIResponse(
                content="yes" if confirmed else "no",
                metadata={"confirmed": confirmed}
            )
    
    async def _text_input_dialog(self, choice: UIChoice) -> UIResponse:
        """Handle text input dialog."""
        try:
            result = input(f"{choice.prompt}: ").strip()
            return UIResponse(content=result)
        except (KeyboardInterrupt, EOFError):
            return UIResponse(content="", metadata={"cancelled": True})
    
    async def show_thinking(self, message: str) -> None:
        """Show thinking indicator."""
        # Suppress thinking indicators in quiet mode
        if self.quiet_mode:
            return
            
        self._thinking_message = message  # Store the message for resuming
        if not self._thinking_status:
            self._thinking_status = self.console.status(message)
            self._thinking_status.start()
    
    async def hide_thinking(self) -> None:
        """Hide thinking indicator."""
        # No-op in quiet mode since we don't start thinking indicators
        if self.quiet_mode:
            return
            
        if self._thinking_status:
            self._thinking_status.stop()
            self._thinking_status = None
    
    async def pause_thinking(self) -> None:
        """Temporarily pause thinking indicator for tool output."""
        if self._thinking_status:
            self._thinking_status.stop()
            # Keep reference to resume later but mark as paused
            if not hasattr(self, '_thinking_message'):
                self._thinking_message = "Processing..."
    
    async def resume_thinking(self, message: str = None) -> None:
        """Resume thinking indicator after tool output."""
        # Only resume if we had a thinking status before pausing
        if hasattr(self, '_thinking_message') or self._thinking_status:
            resume_message = message or getattr(self, '_thinking_message', "Processing...")
            if self._thinking_status:
                self._thinking_status.stop()
            
            self._thinking_status = self.console.status(resume_message)
            self._thinking_status.start()
    
    def is_thinking(self) -> bool:
        """Check if thinking indicator is currently active."""
        return self._thinking_status is not None and self._thinking_status._started
    
    def display_banner(self) -> None:
        """Display the Songbird banner."""
        banner = """███████╗ ██████╗ ███╗   ██╗ ██████╗ ██████╗ ██╗██████╗ ██████╗ 
                    ██╔════╝██╔═══██╗████╗  ██║██╔════╝ ██╔══██╗██║██╔══██╗██╔══██╗
                    ███████╗██║   ██║██╔██╗ ██║██║  ███╗██████╔╝██║██████╔╝██║  ██║
                    ╚════██║██║   ██║██║╚██╗██║██║   ██║██╔══██╗██║██╔══██╗██║  ██║
                    ███████║╚██████╔╝██║ ╚████║╚██████╔╝██████╔╝██║██║  ██║██████╔╝
                    ╚══════╝ ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚═╝╚═╝  ╚═╝╚═════╝"""
        self.console.print(banner, style="bold blue")
        self.console.print()
    
    def display_welcome(self, provider_name: str, model_name: str) -> None:
        """Display welcome message."""
        self.console.print("Welcome to Songbird - Your AI coding companion!", style="cornflower_blue")
        self.console.print(
            "Available tools: file_search, file_read, file_create, file_edit, shell_exec, todo_read, todo_write, glob, grep, ls, multi_edit",
            style="dim"
        )
        self.console.print(
            "I can search files, manage todos, run shell commands, and perform multi-file operations with full task management.",
            style="dim"
        )
        self.console.print(
            "Type [spring_green1]'/'[/spring_green1] for commands, or [spring_green1]'exit'[/spring_green1] to quit.\n",
            style="dim"
        )
        self.console.print(f"Using provider: {provider_name}, model: {model_name}", style="dim")
    
    def display_goodbye(self) -> None:
        """Display goodbye message."""
        self.console.print("Goodbye!", style="bold blue")