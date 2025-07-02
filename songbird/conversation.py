# songbird/conversation.py
"""
Legacy conversation orchestrator that delegates to the new SongbirdOrchestrator.
This file maintains backwards compatibility while the new architecture is in use.
"""
import sys
from typing import Optional
from rich.console import Console
from InquirerPy import inquirer
from .llm.providers import BaseProvider
from .memory.models import Session


async def safe_interactive_menu(prompt: str, options: list[str], default_index: int = 0) -> int | None:
    """
    Async-safe interactive menu that handles all scenarios properly.
    Returns the selected index, or None if cancelled.
    """
    try:
        # Check if we're in an interactive terminal
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            # Non-interactive environment - auto-select default
            console = Console()
            console.print(f"\n{prompt}")
            for i, option in enumerate(options):
                marker = "▶ " if i == default_index else "  "
                console.print(f"{marker}{option}")
            console.print(f"[dim]Auto-selected: {options[default_index]}[/dim]")
            return default_index
        
        # Try the async InquirerPy API first
        return await async_interactive_menu(prompt, options, default_index)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        return None

async def async_interactive_menu(prompt: str, options: list[str], default_index: int = 0) -> int:
    """
    Async interactive menu using InquirerPy's execute_async() method.
    This is the CORRECT way to use InquirerPy within an existing event loop.
    """
    try:
        result = await inquirer.select(
            message=prompt,
            choices=options,
            default=options[default_index] if default_index < len(options) else options[0]
        ).execute_async()
        
        return options.index(result)
    except Exception:
        # Fall back to sync version if async fails
        return sync_interactive_menu(prompt, options, default_index)

def sync_interactive_menu(prompt: str, options: list[str], default_index: int = 0) -> int:
    """
    Synchronous fallback interactive menu.
    """
    try:
        result = inquirer.select(
            message=prompt,
            choices=options,
            default=options[default_index] if default_index < len(options) else options[0]
        ).execute()
        
        return options.index(result)
    except Exception:
        # Ultimate fallback to numbered menu
        return fallback_numbered_menu(prompt, options, default_index)

def fallback_numbered_menu(prompt: str, options: list[str], default_index: int = 0) -> int:
    """
    Fallback numbered menu for environments where InquirerPy doesn't work.
    """
    console = Console()
    
    # Show terminal compatibility message
    if not sys.stdin.isatty():
        console.print(f"\n{prompt}")
        for i, option in enumerate(options):
            style = "bold green" if i == default_index else "white"
            console.print(f"  {i + 1}. {option}", style=style)
        console.print(f"[dim]Auto-selected: {options[default_index]}[/dim]")
        return default_index
    
    try:
        console.print(f"\n{prompt}")
        for i, option in enumerate(options):
            style = "bold green" if i == default_index else "white"
            console.print(f"  {i + 1}. {option}", style=style)
        
        console.print(f"\n[dim]Enter number (1-{len(options)}) or press Enter for default [{default_index + 1}]:[/dim]")
        
        response = input().strip()
        
        if not response:
            return default_index
        
        choice = int(response) - 1
        if 0 <= choice < len(options):
            return choice
        else:
            console.print("[red]Invalid choice. Using default.[/red]")
            return default_index
    except (ValueError, KeyboardInterrupt):
        console.print("[red]Invalid input. Using default.[/red]")
        return default_index
    except Exception:
        # Fall back to numbered menu
        return fallback_numbered_menu(prompt, options, default_index)


def interactive_menu(prompt: str, options: list[str], default_index: int = 0) -> int:
    """
    Interactive menu function for backwards compatibility.
    Delegates to the safe async menu system.
    """
    # For backwards compatibility, use the sync version
    return sync_interactive_menu(prompt, options, default_index)


# Legacy ConversationOrchestrator - DEPRECATED: Use SongbirdOrchestrator instead
class ConversationOrchestrator:
    """DEPRECATED: Legacy orchestrator. Use SongbirdOrchestrator for new code."""

    def __init__(self, provider: BaseProvider, working_directory: str = ".", session: Optional[Session] = None):
        # Import here to avoid circular imports
        from .orchestrator import SongbirdOrchestrator
        
        # Delegate to new orchestrator
        self._orchestrator = SongbirdOrchestrator(provider, working_directory, session)
        
        # Create backwards compatibility interface
        self.provider = self._orchestrator.provider
        self.session = self._orchestrator.session
        self.session_manager = self._orchestrator.session_manager
        
    @property
    def conversation_history(self):
        """Delegate to new orchestrator."""
        return self._orchestrator.conversation_history
    
    @conversation_history.setter  
    def conversation_history(self, value):
        """Delegate to new orchestrator."""
        self._orchestrator.conversation_history = value
        
    async def chat(self, message: str, status=None) -> str:
        """Delegate to new orchestrator."""
        return await self._orchestrator.chat(message, status)