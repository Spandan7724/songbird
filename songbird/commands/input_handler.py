# songbird/commands/input_handler.py
"""
Enhanced input handler for Songbird commands with message history support.
"""

from typing import Optional, List
from rich.console import Console
from rich.table import Table
from .base import BaseCommand
from .registry import CommandRegistry
from .enhanced_input import get_input_with_history
from ..memory.history_manager import MessageHistoryManager


# Enhanced input handler that can show current model in prompt

class CommandInputHandler:
    """Enhanced input handler with model awareness and message history."""

    def __init__(self, registry: CommandRegistry, console: Console, history_manager: Optional[MessageHistoryManager] = None):
        self.registry = registry
        self.console = console
        self.history_manager = history_manager
        self.show_model_in_prompt = False  # Can be toggled

    def get_input_with_commands(self, prompt: str = "You", context: dict = None) -> str:
        """
        Get user input with command support and message history navigation.
        Shows help when user types just '/'.
        Can optionally show current model in prompt.
        Supports up/down arrow keys for message history (when available).
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

        # Get input with history support
        self.console.print("\n", end="")
        user_input = get_input_with_history(prompt_text, self.history_manager, self.console)

        # Handle special cases
        if user_input == "/":
            # Show command help
            self._show_commands()
            # Get input again
            return self.get_input_with_commands(prompt, context)

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
                return self.get_input_with_commands(prompt, context)

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
        table.add_column("Command", style="green")
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
            "\n[dim]Type /help for detailed command information[/dim]")


# Alternative: Status line approach
def show_status_line(console: Console, provider: str, model: str):
    """Show a status line with current provider and model."""
    # Extract model name for display
    model_display = model.split(':')[0] if ':' in model else model
    status = f"[dim][ {provider} | {model_display} ][/dim]"
    console.print(status, justify="right")

# For backward compatibility with model_command.py


class KeyCodes:
    """Key codes for compatibility."""
    UP = 'UP'
    DOWN = 'DOWN'
    ENTER = 'ENTER'
    ESCAPE = 'ESCAPE'
    CTRL_C = 'CTRL_C'


def get_key():
    """
    Simple key getter for model selector.
    Returns single characters or special key names.
    """
    import sys
    import os

    if os.name == 'nt':
        import msvcrt
        if msvcrt.kbhit():
            key = msvcrt.getch()
            if key in (b'\x00', b'\xe0'):  # Special key
                key2 = msvcrt.getch()
                if key2 == b'H':
                    return KeyCodes.UP
                elif key2 == b'P':
                    return KeyCodes.DOWN
            elif key == b'\r':
                return KeyCodes.ENTER
            elif key == b'\x1b':
                return KeyCodes.ESCAPE
            elif key == b'\x03':
                return KeyCodes.CTRL_C
            else:
                try:
                    return key.decode('utf-8', errors='ignore')
                except:
                    return ''
        return ''
    else:
        # Unix/Linux/macOS - simplified version
        import tty
        import termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            key = sys.stdin.read(1)

            # Handle special keys
            if key == '\x1b':  # ESC
                # Try to read more for arrow keys
                import select
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    key2 = sys.stdin.read(1)
                    if key2 == '[':
                        key3 = sys.stdin.read(1)
                        if key3 == 'A':
                            return KeyCodes.UP
                        elif key3 == 'B':
                            return KeyCodes.DOWN
                return KeyCodes.ESCAPE
            elif key == '\r' or key == '\n':
                return KeyCodes.ENTER
            elif key == '\x03':
                return KeyCodes.CTRL_C
            else:
                return key
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
