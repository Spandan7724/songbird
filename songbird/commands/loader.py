"""
Command loader for registering all available commands.
"""

from .registry import get_command_registry
from .model_command import ModelCommand
from .help_command import HelpCommand
from .clear_command import ClearCommand


def load_all_commands():
    registry = get_command_registry()
    
    registry.register(ModelCommand())
    registry.register(ClearCommand())
    
    registry.register(HelpCommand(registry))
    
    return registry


def is_command_input(text: str) -> bool:
    return text.strip().startswith('/')


def parse_command_input(text: str) -> tuple[str, str]:
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


def is_bash_mode_input(text: str) -> bool:
    """Check if the input text is bash mode (starts with !)."""
    return text.strip().startswith('!')


def parse_bash_input(text: str) -> str:
    """Parse bash input and return the command to execute."""
    if not text.startswith('!'):
        return ""
    
    return text[1:].strip()