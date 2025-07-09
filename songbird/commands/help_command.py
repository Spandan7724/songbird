from typing import Dict, Any
from rich.table import Table
from rich.panel import Panel
from .base import BaseCommand, CommandResult
from .registry import CommandRegistry


class HelpCommand(BaseCommand):
    
    def __init__(self, registry: CommandRegistry):
        super().__init__(
            name="help",
            description="Show available commands and usage information",
            aliases=["h", "?"]
        )
        self.registry = registry
    
    async def execute(self, args: str, context: Dict[str, Any]) -> CommandResult:
        if args.strip():
            return self._show_command_help(args.strip())
        else:
            # Show general help
            return self._show_general_help()
    
    def _show_general_help(self) -> CommandResult:
        commands = self.registry.get_all_commands()
        
        table = Table(title="Available Commands", show_header=True, header_style="bold blue")
        table.add_column("Command", style="cornflower_blue", width=15)
        table.add_column("Aliases", style="dim", width=10)
        table.add_column("Description", style="white")
        
        for command in sorted(commands, key=lambda c: c.name):
            aliases = ", ".join(f"/{alias}" for alias in command.aliases)
            table.add_row(
                f"/{command.name}",
                aliases or "-",
                command.description
            )
        
        usage_text = """
[bold]Usage:[/bold]
• Type [cornflower_blue]/[/cornflower_blue] to show commands
• Use [cornflower_blue]↑↓[/cornflower_blue] arrow keys to navigate
• Press [cornflower_blue]Enter[/cornflower_blue] to select a command
• Press [cornflower_blue]Esc[/cornflower_blue] to cancel

[bold]Examples:[/bold]
• [cornflower_blue]/model[/cornflower_blue] - Switch LLM model interactively
• [cornflower_blue]/model qwen2.5-coder:7b[/cornflower_blue] - Switch to specific model
• [cornflower_blue]/clear[/cornflower_blue] - Clear current conversation
• [cornflower_blue]/help model[/cornflower_blue] - Get help for specific command
"""
        
        self.console.print()
        self.console.print(table)
        self.console.print()
        self.console.print(Panel(usage_text, title="Command System Help", border_style="cornflower_blue"))
        
        return CommandResult(
            success=True,
            message=""
        )
    
    def _show_command_help(self, command_name: str) -> CommandResult:
        if command_name.startswith('/'):
            command_name = command_name[1:]
        
        command = self.registry.get_command(command_name)
        if not command:
            return CommandResult(
                success=False,
                message=f"Command '{command_name}' not found. Use '/help' to see all commands."
            )
        
        help_text = f"""
[bold]Command:[/bold] /{command.name}
[bold]Aliases:[/bold] {', '.join('/' + alias for alias in command.aliases) if command.aliases else 'None'}
[bold]Description:[/bold] {command.description}

{command.get_help()}
"""
        
        self.console.print()
        self.console.print(Panel(help_text, title=f"Help: /{command.name}", border_style="blue"))
        
        return CommandResult(
            success=True,
            message=f"Help for '{command.name}' displayed"
        )