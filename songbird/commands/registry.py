"""
Command registry for managing available commands.
"""

from typing import Dict, List, Optional
from .base import BaseCommand


class CommandRegistry:
    """Registry for managing available commands."""
    
    def __init__(self):
        self._commands: Dict[str, BaseCommand] = {}
    
    def register(self, command: BaseCommand) -> None:
        """Register a command."""
        self._commands[command.name] = command
        
        # Also register aliases
        for alias in command.aliases:
            self._commands[alias] = command
    
    def get_command(self, name: str) -> Optional[BaseCommand]:
        return self._commands.get(name)
    
    def get_all_commands(self) -> List[BaseCommand]:
        """Get all unique commands (excluding aliases)."""
        seen = set()
        commands = []
        for command in self._commands.values():
            if command.name not in seen:
                commands.append(command)
                seen.add(command.name)
        return commands
    
    def search_commands(self, query: str) -> List[BaseCommand]:
        query = query.lower()
        matches = []
        
        for command in self.get_all_commands():
            if (query in command.name.lower() or 
                query in command.description.lower() or
                any(query in alias.lower() for alias in command.aliases)):
                matches.append(command)
        
        return matches
    
    def is_command(self, text: str) -> bool:
        if not text.startswith('/'):
            return False
        
        # Extract command name (first word after /)
        parts = text[1:].split(' ', 1)
        command_name = parts[0]
        
        return command_name in self._commands


_registry = CommandRegistry()


def get_command_registry() -> CommandRegistry:
    return _registry