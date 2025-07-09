from typing import Optional, Dict, Any
from rich.console import Console
from .registry import CommandRegistry
from .prompt_toolkit_input import PromptToolkitInputHandler
from ..memory.history_manager import MessageHistoryManager


class CommandInputHandler:

    def __init__(self, registry: CommandRegistry, console: Console, history_manager: Optional[MessageHistoryManager] = None):
        self.registry = registry
        self.console = console
        self.history_manager = history_manager
        self.show_model_in_prompt = False  # Can be toggled
        
        self._prompt_handler = PromptToolkitInputHandler(registry, console, history_manager)

    async def get_input_with_commands(self, prompt: str = "You", context: Optional[Dict[str, Any]] = None) -> str:
        """
        Get user input with command support and message history navigation.
        """
        self._prompt_handler.show_model_in_prompt = self.show_model_in_prompt
        
        return await self._prompt_handler.get_input_with_commands(prompt, context)

    def invalidate_history_cache(self):
        if self._prompt_handler:
            self._prompt_handler.invalidate_history_cache()

