# songbird/commands/loader.py
"""
Command loader for registering all available commands.
"""

from .registry import get_command_registry
from .model_command import ModelCommand
from .help_command import HelpCommand
from .clear_command import ClearCommand


def load_all_commands():
    """Load and register all available commands."""
    registry = get_command_registry()
    
    # Register built-in commands
    registry.register(ModelCommand())
    registry.register(ClearCommand())
    
    # Register help command (needs registry reference)
    registry.register(HelpCommand(registry))
    
    return registry


def is_command_input(text: str) -> bool:
    """Check if the input text is a command."""
    return text.strip().startswith('/')


def parse_command_input(text: str) -> tuple[str, str]:
    """Parse command input into command name and arguments."""
    if not text.startswith('/'):
        return "", ""
    
    # Remove leading slash and split into command and args
    command_part = text[1:].strip()
    if not command_part:
        return "", ""
    
    parts = command_part.split(' ', 1)
    command_name = parts[0]
    args = parts[1] if len(parts) > 1 else ""
    
    return command_name, args