"""
Prompt-toolkit based input handler for Songbird commands with message history support.
Replaces the custom enhanced_input.py implementation.
"""

from typing import Optional, List, Dict, Any
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import History
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.filters import Condition
from prompt_toolkit.application import get_app
from prompt_toolkit.formatted_text import HTML
from rich.console import Console
from rich.table import Table

from .base import BaseCommand
from .registry import CommandRegistry
from ..memory.history_manager import MessageHistoryManager


class SongbirdHistory(History):
    """Custom history adapter that bridges prompt-toolkit with MessageHistoryManager."""
    
    def __init__(self, history_manager: MessageHistoryManager):
        super().__init__()
        self.history_manager = history_manager
        self._history_strings: Optional[List[str]] = None
        self._loaded = False
    
    def load_history_strings(self) -> List[str]:
        """Load history strings from the MessageHistoryManager."""
        if self._history_strings is None:
            # Force load from history manager
            self.history_manager._history_cache = None
            messages = self.history_manager._load_project_user_messages()
            self._history_strings = messages
            self._loaded = True
        return self._history_strings
    
    async def load(self):
        """Async generator to load history items (required by prompt-toolkit)."""
        if not self._loaded:
            self.load_history_strings()
        
        for item in self._history_strings or []:
            yield item
    
    def get_strings(self) -> List[str]:
        """Get all history strings."""
        return self.load_history_strings()
    
    def append_string(self, string: str) -> None:
        """Add a new string to history (prompt-toolkit calls this)."""
        # We don't need to implement this since history is managed by SessionManager
        # Just invalidate cache so next load gets fresh data
        self.history_manager.invalidate_cache()
        self._history_strings = None
        
    def store_string(self, string: str) -> None:
        """Store a string in history (required abstract method)."""
        # Delegate to append_string
        self.append_string(string)
    
    def __getitem__(self, index: int) -> str:
        """Get history item by index."""
        strings = self.load_history_strings()
        try:
            return strings[index]
        except IndexError:
            return ""
    
    def __len__(self) -> int:
        """Get number of history items."""
        return len(self.load_history_strings())


class CommandCompleter(Completer):
    """Completer for Songbird commands."""
    
    def __init__(self, registry: CommandRegistry):
        self.registry = registry
    
    def get_completions(self, document, complete_event):
        """Generate completions for commands."""
        text = document.text_before_cursor
        
        # Only complete if we're at the start of input and it starts with /
        if text.startswith('/') and ' ' not in text:
            command_part = text[1:].lower()  # Remove the /
            
            for command in self.registry.get_all_commands():
                # Check command name
                if command.name.lower().startswith(command_part):
                    yield Completion(
                        command.name,
                        start_position=-len(command_part),
                        display=f"/{command.name}",
                        display_meta=command.description
                    )
                
                # Check aliases
                for alias in command.aliases:
                    if alias.lower().startswith(command_part):
                        yield Completion(
                            alias,
                            start_position=-len(command_part),
                            display=f"/{alias}",
                            display_meta=f"{command.description} (alias for /{command.name})"
                        )


class PromptToolkitInputHandler:
    """Enhanced input handler using prompt-toolkit with message history support."""

    def __init__(self, registry: CommandRegistry, console: Console, history_manager: Optional[MessageHistoryManager] = None):
        self.registry = registry
        self.console = console
        self.history_manager = history_manager
        self.show_model_in_prompt = False  # Can be toggled
        self.session: PromptSession  # Type annotation for session
        
        # Create prompt-toolkit session
        self._create_session()
    
    def _create_session(self):
        """Create the prompt-toolkit session with all configurations."""
        # Set up history if available
        history = None
        if self.history_manager:
            history = SongbirdHistory(self.history_manager)
        
        # Set up command completer
        completer = CommandCompleter(self.registry)
        
        # Set up key bindings
        kb = self._create_key_bindings()
        
        # Create the session
        self.session = PromptSession(
            history=history,
            completer=completer,
            key_bindings=kb,
            complete_while_typing=False,  # Only complete on tab
            enable_history_search=True,   # Enable Ctrl+R search
            search_ignore_case=True,
        )
    
    def _create_key_bindings(self) -> KeyBindings:
        """Create custom key bindings for Songbird."""
        kb = KeyBindings()
        
        @kb.add('?', filter=Condition(lambda: self._should_show_help()))
        def show_help_on_question_mark(event):
            """Show help when user types '?' alone."""
            app = event.app
            buffer = app.current_buffer
            
            # Only show help if buffer only contains '?'
            if buffer.text == '?':
                buffer.delete_before_cursor(1)  # Remove the ?
                self._show_commands()
        
        return kb
    
    def _should_show_help(self) -> bool:
        """Check if we should show help on '?' press."""
        app = get_app()
        if app and app.current_buffer:
            return app.current_buffer.text == '?'
        return False

    async def get_input_with_commands(self, prompt: str = "You", context: Optional[Dict[str, Any]] = None) -> str:
        """
        Get user input with command support and message history navigation.
        Uses prompt-toolkit for robust input handling with history and completion.
        """
        # Build prompt with optional model info
        if self.show_model_in_prompt and context:
            model = context.get('model', '')
            if model:
                # Extract just the model name without version for brevity
                model_short = model.split(':')[0] if ':' in model else model
                prompt_text = f"{prompt} [{model_short}]"
            else:
                prompt_text = prompt
        else:
            prompt_text = prompt

        # Get input using prompt-toolkit session (async)
        try:
            # Create colored prompt using prompt-toolkit's HTML formatting
            colored_prompt = HTML(f'<b><ansicyan>{prompt_text}:</ansicyan></b> ')
            user_input = await self.session.prompt_async(colored_prompt)
        except KeyboardInterrupt:
            # Re-raise KeyboardInterrupt to be handled by caller
            raise
        except EOFError:
            # Handle Ctrl+D as exit
            return "exit"
        
        # Handle special cases
        if user_input == "/":
            # Show command help
            self._show_commands()
            # Get input again
            return await self.get_input_with_commands(prompt, context)

        elif user_input.startswith("/") and " " not in user_input:
            # Check if it's a valid command or alias
            cmd_name = user_input[1:].lower()
            command = self._find_command(cmd_name)

            if command:
                # Valid command, return it
                return f"/{command.name}"
            else:
                # Invalid command, show error and available commands
                self.console.print(f"[red]Unknown command: {user_input}[/red]")
                self.console.print("Available commands:")
                self._show_commands()
                # Get input again
                return await self.get_input_with_commands(prompt, context)

        # Regular input or command with args
        return user_input

    def _find_command(self, name: str) -> Optional[BaseCommand]:
        """Find command by name or alias."""
        for cmd in self.registry.get_all_commands():
            if cmd.name.lower() == name or name in [a.lower() for a in cmd.aliases]:
                return cmd
        return None

    def _show_commands(self):
        """Display available commands in a clean format."""
        commands = self.registry.get_all_commands()

        if not commands:
            self.console.print("[yellow]No commands available[/yellow]")
            return

        # Create a simple table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Command", style="cornflower_blue")
        table.add_column("Description", style="dim")

        for cmd in sorted(commands, key=lambda x: x.name):
            # Format command with aliases
            cmd_text = f"/{cmd.name}"
            if cmd.aliases:
                # Show first 2 aliases
                aliases = ", ".join(f"/{a}" for a in cmd.aliases[:2])
                cmd_text = f"{cmd_text} ({aliases})"

            table.add_row(cmd_text, cmd.description)

        self.console.print()
        self.console.print(table)
        self.console.print(
            "\n[dim]Type [spring_green1]/help[/spring_green1] for detailed command information[/dim]")

    def invalidate_history_cache(self):
        """Invalidate history cache - called when new messages are added."""
        if self.history_manager:
            self.history_manager.invalidate_cache()
            # Also invalidate the session history cache
            if hasattr(self.session, 'history') and isinstance(self.session.history, SongbirdHistory):
                self.session.history._history_strings = None
                self.session.history._loaded = False  # This is the missing piece!


# For backward compatibility with model_command.py and other existing code
class KeyCodes:
    """Key codes for compatibility."""
    UP = 'UP'
    DOWN = 'DOWN'
    ENTER = 'ENTER'
    ESCAPE = 'ESCAPE'
    CTRL_C = 'CTRL_C'


def show_status_line(console: Console, provider: str, model: str):
    """Show a status line with current provider and model."""
    # Extract model name for display
    model_display = model.split(':')[0] if ':' in model else model
    status = f"[dim][ {provider} | {model_display} ][/dim]"
    console.print(status, justify="right")