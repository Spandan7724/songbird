# songbird/commands/input_handler.py
"""
Enhanced input handler for Songbird commands with message history support.
Uses prompt-toolkit for robust cross-platform input handling.
"""

from typing import Optional, Dict, Any
from rich.console import Console
from .registry import CommandRegistry
from .prompt_toolkit_input import PromptToolkitInputHandler
from ..memory.history_manager import MessageHistoryManager


class CommandInputHandler:
    """Enhanced input handler with model awareness and message history."""

    def __init__(self, registry: CommandRegistry, console: Console, history_manager: Optional[MessageHistoryManager] = None):
        self.registry = registry
        self.console = console
        self.history_manager = history_manager
        self.show_model_in_prompt = False  # Can be toggled
        
        # Create the prompt-toolkit handler
        self._prompt_handler = PromptToolkitInputHandler(registry, console, history_manager)

    async def get_input_with_commands(self, prompt: str = "You", context: Optional[Dict[str, Any]] = None) -> str:
        """
        Get user input with command support and message history navigation.
        Uses prompt-toolkit for robust input handling with history and completion.
        """
        # Sync model display setting
        self._prompt_handler.show_model_in_prompt = self.show_model_in_prompt
        
        # Delegate to prompt-toolkit handler
        return await self._prompt_handler.get_input_with_commands(prompt, context)

    def invalidate_history_cache(self):
        """Invalidate history cache - called when new messages are added."""
        if self._prompt_handler:
            self._prompt_handler.invalidate_history_cache()

