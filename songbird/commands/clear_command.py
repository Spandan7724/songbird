# songbird/commands/clear_command.py
"""
Clear command for clearing the current conversation history.
"""

from typing import Dict, Any
from rich.console import Console
from rich.prompt import Confirm
from .base import BaseCommand, CommandResult


class ClearCommand(BaseCommand):
    """Command to clear the current conversation history."""
    
    def __init__(self):
        super().__init__(
            name="clear",
            description="Clear the current conversation history",
            aliases=["cls", "c"]
        )
    
    async def execute(self, args: str, context: Dict[str, Any]) -> CommandResult:
        """Execute the clear command."""
        # Check if we should skip confirmation (for args like --force or -f)
        force = args.strip().lower() in ['--force', '-f', 'force', 'f']
        
        if not force:
            # Ask for confirmation
            confirm = Confirm.ask("\n[yellow]Clear current conversation history?[/yellow]")
            if not confirm:
                return CommandResult(
                    success=True,
                    message="Clear cancelled"
                )
        
        # Clear the screen
        self.console.clear()
        
        # Show a fresh banner or indication
        self.console.print("[bold green]Conversation cleared![/bold green]")
        self.console.print("[dim]Starting fresh conversation...[/dim]\n")
        
        return CommandResult(
            success=True,
            message="Conversation history cleared",
            data={"action": "clear_history"},
            should_continue_conversation=False  # Signal to restart conversation
        )
    
    def get_help(self) -> str:
        """Get detailed help for the clear command."""
        return """
[bold]Usage:[/bold]
• [green]/clear[/green] - Clear conversation with confirmation
• [green]/clear --force[/green] or [green]/clear -f[/green] - Clear without confirmation

This command clears the current conversation history and starts fresh.
The conversation will continue with the same model and provider settings.
"""