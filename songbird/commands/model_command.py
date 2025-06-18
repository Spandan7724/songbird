# songbird/commands/model_command.py
"""
Simplified model switching command with clean display.
"""

from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from .base import BaseCommand, CommandResult


class ModelCommand(BaseCommand):
    """Command to switch LLM models."""

    def __init__(self):
        super().__init__(
            name="model",
            description="Switch the current LLM model",
            aliases=["m"]
        )

    async def execute(self, args: str, context: Dict[str, Any]) -> CommandResult:
        """Execute the model switching command."""
        provider_name = context.get("provider", "")
        current_model = context.get("model", "")
        provider_instance = context.get("provider_instance")

        if not provider_name:
            return CommandResult(
                success=False,
                message="No provider available in current context"
            )

        # Get available models
        models = self._get_available_models(provider_name)
        if not models:
            return CommandResult(
                success=False,
                message=f"No models available for provider: {provider_name}"
            )

        # If args provided, try to set model directly
        if args.strip():
            new_model = args.strip()
            if new_model in models:
                if provider_instance:
                    provider_instance.model = new_model
                return CommandResult(
                    success=True,
                    message=f"Switched to model: {new_model}",
                    data={"new_model": new_model}
                )
            else:
                return CommandResult(
                    success=False,
                    message=f"Model '{new_model}' not available. Use /model to see available models."
                )

        # Show model selection
        self.console.print(
            f"\n[bold]Current: {provider_name} - {current_model}[/bold]")
        self.console.print("\nAvailable models:")

        # Display models with numbers
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("", style="white")  # Number
        table.add_column("Model", style="spring_green1")
        table.add_column("", style="dim")  # Current indicator

        for i, model in enumerate(models, 1):
            current = "← current" if model == current_model else ""
            table.add_row(f"{i}.", model, current)

        self.console.print(table)

        # Get user choice
        choice = Prompt.ask(
            "\nSelect model number (or press Enter to cancel)",
            default="",
            show_default=False
        )

        if not choice:
            return CommandResult(
                success=True,
                message="[white dim]Model selection cancelled[/white dim]",
            )

        try:
            index = int(choice) - 1
            if 0 <= index < len(models):
                selected_model = models[index]

                if selected_model == current_model:
                    return CommandResult(
                        success=True,
                        message=f"Model unchanged: {selected_model}"
                    )

                # Update the model
                if provider_instance:
                    provider_instance.model = selected_model

                return CommandResult(
                    success=True,
                    message=f"Switched to model: {selected_model}",
                    data={"new_model": selected_model}
                )
            else:
                return CommandResult(
                    success=False,
                    message="Invalid selection. Please choose a valid number."
                )
        except ValueError:
            return CommandResult(
                success=False,
                message="Invalid input. Please enter a number."
            )

    def _get_available_models(self, provider_name: str) -> List[str]:
        """Get available models for a provider."""
        if provider_name == "ollama":
            return self._get_ollama_models()
        elif provider_name == "gemini":
            return [
                "gemini-2.0-flash-exp",
                "gemini-2.0-flash-001",
                "gemini-1.5-pro",
                "gemini-1.5-flash",
                "gemini-1.0-pro"
            ]
        else:
            return []

    def _get_ollama_models(self) -> List[str]:
        """Get available Ollama models."""
        try:
            import requests
            response = requests.get(
                "http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                models = response.json().get('models', [])
                return [model['name'] for model in models]
        except:
            pass

        # Fallback to common models
        return [
            "qwen2.5-coder:7b",
            "qwen2.5-coder:14b",
            "qwen2.5-coder:32b",
            "llama3.2:latest",
            "codellama:latest",
            "deepseek-coder:6.7b"
        ]

    def get_help(self) -> str:
        """Get detailed help for the model command."""
        return """
[bold]Usage:[/bold]
  /model              - Show available models and select interactively
  /model <name>       - Switch to specific model directly

[bold]Examples:[/bold]
  /model              - Opens model selection menu
  /model gemini-2.0-flash-exp     - Switch to Gemini 2.0 Flash
  /model qwen2.5-coder:7b         - Switch to Qwen 2.5 Coder

[bold]Shortcuts:[/bold]
  /m                  - Same as /model
"""
