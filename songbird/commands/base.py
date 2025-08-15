"""
Base command class and result types for the command system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional, List
from rich.console import Console


@dataclass
class CommandResult:
    success: bool
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    should_continue_conversation: bool = True
    
    
class BaseCommand(ABC):
    
    def __init__(self, name: str, description: str, aliases: Optional[List[str]] = None):
        self.name = name
        self.description = description
        self.aliases = aliases or []
        self.console = Console()
    
    @abstractmethod
    async def execute(self, args: str, context: Dict[str, Any]) -> CommandResult:
        pass
    
    def matches(self, command_name: str) -> bool:
        return command_name == self.name or command_name in self.aliases
    
    def get_help(self) -> str:
        return self.description