
"""
Clear command for clearing the current conversation history.
"""

from typing import Dict, Any
from rich.prompt import Confirm
from .base import BaseCommand, CommandResult


class ClearCommand(BaseCommand):
    
    def __init__(self):
        super().__init__(
            name="clear",
            description="Clear the current conversation history",
            aliases=["cls", "c"]
        )
    
    async def execute(self, args: str, context: Dict[str, Any]) -> CommandResult:
        force = args.strip().lower() in ['--force', '-f', 'force', 'f']
        
        if not force:
            confirm = Confirm.ask("\n[white]Clear current conversation history? [cyan]\\[y/n][/cyan][/white]", show_choices=False)
            if not confirm:
                return CommandResult(
                    success=True,
                    message="[cornflower_blue]Clear cancelled[/cornflower_blue]"
                )
        
        self.console.clear()
        
        self.console.print("[cornflower_blue]Conversation cleared![/cornflower_blue]")
        self.console.print("[dim]Starting fresh conversation...[dim]\n")
        
        return CommandResult(
            success=True,
            message="[dim][cornflower_blue]Conversation history cleared[/cornflower_blue][/dim]",
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