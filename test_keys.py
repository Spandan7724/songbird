#!/usr/bin/env python3
"""
Test the smooth command input handler.
"""

from songbird.commands.base import BaseCommand
from songbird.commands import CommandRegistry
from rich.console import Console
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Create mock commands for testing

class ModelCommand(BaseCommand):
    name = "model"
    aliases = ["m"]
    description = "Switch the current LLM model"

    async def execute(self, args, context):
        return None


class ClearCommand(BaseCommand):
    name = "clear"
    aliases = ["cls", "c"]
    description = "Clear the current conversation history"

    async def execute(self, args, context):
        return None


class HelpCommand(BaseCommand):
    name = "help"
    aliases = ["h", "?"]
    description = "Show available commands and usage information"

    async def execute(self, args, context):
        return None


class ExitCommand(BaseCommand):
    name = "exit"
    aliases = ["quit", "q"]
    description = "Exit the application"

    async def execute(self, args, context):
        return None


class ConfigCommand(BaseCommand):
    name = "config"
    aliases = ["cfg"]
    description = "Configure application settings"

    async def execute(self, args, context):
        return None


class SearchCommand(BaseCommand):
    name = "search"
    aliases = ["s", "find"]
    description = "Search for files or content"

    async def execute(self, args, context):
        return None


class HistoryCommand(BaseCommand):
    name = "history"
    aliases = ["hist"]
    description = "Show command history"

    async def execute(self, args, context):
        return None


class SaveCommand(BaseCommand):
    name = "save"
    aliases = []
    description = "Save current session"

    async def execute(self, args, context):
        return None


class LoadCommand(BaseCommand):
    name = "load"
    aliases = []
    description = "Load a saved session"

    async def execute(self, args, context):
        return None


class SettingsCommand(BaseCommand):
    name = "settings"
    aliases = ["set"]
    description = "Manage application settings"

    async def execute(self, args, context):
        return None


def main():
    console = Console()

    # Create registry and add commands
    registry = CommandRegistry()
    commands = [
        ModelCommand(), ClearCommand(), HelpCommand(), ExitCommand(),
        ConfigCommand(), SearchCommand(), HistoryCommand(), SaveCommand(),
        LoadCommand(), SettingsCommand()
    ]

    for cmd in commands:
        registry.register(cmd)

    # Import the new input handler
    from songbird.commands.input_handler import CommandInputHandler

    handler = CommandInputHandler(registry, console)

    console.print("[bold green]Smooth Command Handler Test[/bold green]")
    console.print("Type '/' to see commands dropdown")
    console.print(
        "Use arrow keys to navigate, Enter to select, Escape to cancel")
    console.print("Type 'exit' to quit\n")

    while True:
        try:
            user_input = handler.get_input_with_commands("Test")

            if user_input.lower() in ["exit", "quit"]:
                console.print("\n[bold blue]Goodbye![/bold blue]")
                break

            console.print(f"You entered: [green]{user_input}[/green]")

        except KeyboardInterrupt:
            console.print("\n[bold blue]Interrupted![/bold blue]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
