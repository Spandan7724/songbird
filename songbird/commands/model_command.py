# songbird/commands/model_command.py
"""
Model switching command for dynamically changing LLM models.
"""

import os
from typing import Dict, Any, List, Optional, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from .base import BaseCommand, CommandResult
from .input_handler import get_key, KeyCodes
from ..llm.providers import get_provider, list_available_providers


class ModelSelector:
    """Interactive model selector for a specific provider."""
    
    def __init__(self, console: Console):
        self.console = console
    
    def get_available_models(self, provider_name: str) -> List[str]:
        """Get available models for a provider."""
        if provider_name == "ollama":
            return self._get_ollama_models()
        elif provider_name == "gemini":
            return self._get_gemini_models()
        else:
            return []
    
    def _get_ollama_models(self) -> List[str]:
        """Get available Ollama models."""
        try:
            import ollama
            client = ollama.Client()
            models = client.list()
            return [model['name'] for model in models.get('models', [])]
        except Exception:
            # Fallback to some common models if we can't connect
            return [
                "devstral:latest",
                "qwen2.5-coder:7b", 
                "qwen2.5-coder:14b",
                "qwen2.5-coder:32b",
                "llama3.2:latest",
                "codellama:latest",
                "deepseek-coder:6.7b",
                "deepseek-coder:33b"
            ]
    
    def _get_gemini_models(self) -> List[str]:
        """Get available Gemini models."""
        return [
            "gemini-2.0-flash-001",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-1.0-pro"
        ]
    
    def select_model(self, provider_name: str, current_model: str = "") -> Optional[str]:
        """Interactive model selection."""
        models = self.get_available_models(provider_name)
        if not models:
            self.console.print(f"[red]No models available for provider: {provider_name}[/red]")
            return None
        
        # Find current model index
        selected_index = 0
        if current_model in models:
            selected_index = models.index(current_model)
        
        # Hide cursor
        self.console.print("\x1b[?25l", end="")
        
        try:
            while True:
                self._display_models(provider_name, models, selected_index, current_model)
                
                key = get_key()
                
                if key == KeyCodes.ENTER:  # Enter - select model
                    selected_model = models[selected_index]
                    self._clear_display()
                    return selected_model
                
                elif key == KeyCodes.ESCAPE:  # Escape - cancel
                    self._clear_display()
                    return None
                
                elif key == KeyCodes.UP:  # Up arrow
                    if selected_index > 0:
                        selected_index -= 1
                
                elif key == KeyCodes.DOWN:  # Down arrow
                    if selected_index < len(models) - 1:
                        selected_index += 1
                
                elif key == KeyCodes.CTRL_C:
                    self._clear_display()
                    raise KeyboardInterrupt()
        
        finally:
            # Show cursor
            self.console.print("\x1b[?25h", end="")
    
    def _display_models(self, provider_name: str, models: List[str], selected_index: int, current_model: str):
        """Display the model selection interface."""
        # Move cursor up to overwrite previous display
        if hasattr(self, '_last_display_lines'):
            self.console.print(f"\x1b[{self._last_display_lines}A", end="")
        
        lines = []
        
        # Header
        lines.append(f"[bold blue]Select {provider_name.title()} Model[/bold blue]")
        lines.append("Use ↑↓ arrows to navigate, Enter to select, Esc to cancel")
        lines.append("")
        
        # Models
        for i, model in enumerate(models):
            prefix = ">" if i == selected_index else " "
            
            # Styling based on selection and current model
            if i == selected_index:
                style = "bold green"
            elif model == current_model:
                style = "blue"
            else:
                style = "dim"
            
            # Add indicator for current model
            suffix = " (current)" if model == current_model else ""
            
            lines.append(f"[{style}]{prefix} {model}{suffix}[/{style}]")
        
        # Pad with empty lines
        while len(lines) < min(len(models) + 5, 15):
            lines.append("")
        
        # Display
        display_text = "\n".join(lines)
        self.console.print(display_text)
        
        self._last_display_lines = len(lines)
    
    def _clear_display(self):
        """Clear the model selection display."""
        if hasattr(self, '_last_display_lines'):
            # Move cursor up and clear lines
            self.console.print(f"\x1b[{self._last_display_lines}A", end="")
            for _ in range(self._last_display_lines):
                self.console.print("\x1b[2K")  # Clear line
            self.console.print(f"\x1b[{self._last_display_lines}A", end="")  # Move back up


class ModelCommand(BaseCommand):
    """Command to switch LLM models dynamically."""
    
    def __init__(self):
        super().__init__(
            name="model",
            description="Switch the current LLM model",
            aliases=["m"]
        )
        self.model_selector = ModelSelector(self.console)
    
    async def execute(self, args: str, context: Dict[str, Any]) -> CommandResult:
        """Execute the model switching command."""
        # Get current provider and model from context
        provider_name = context.get("provider", "")
        current_model = context.get("model", "")
        provider_instance = context.get("provider_instance")
        
        if not provider_name:
            return CommandResult(
                success=False,
                message="No provider available in current context"
            )
        
        # If args provided, try to set model directly
        if args.strip():
            new_model = args.strip()
            return self._set_model_directly(provider_name, new_model, provider_instance)
        
        # Show interactive model selector
        self.console.print(f"\n[bold]Current: {provider_name} - {current_model}[/bold]")
        selected_model = self.model_selector.select_model(provider_name, current_model)
        
        if selected_model is None:
            return CommandResult(
                success=True,
                message="Model selection cancelled"
            )
        
        if selected_model == current_model:
            return CommandResult(
                success=True,
                message=f"Model unchanged: {selected_model}"
            )
        
        # Update the provider instance with new model
        if provider_instance:
            provider_instance.model = selected_model
        
        return CommandResult(
            success=True,
            message=f"Switched to model: {selected_model}",
            data={"new_model": selected_model}
        )
    
    def _set_model_directly(self, provider_name: str, model_name: str, provider_instance) -> CommandResult:
        """Set model directly without interactive selection."""
        available_models = self.model_selector.get_available_models(provider_name)
        
        if model_name not in available_models:
            return CommandResult(
                success=False,
                message=f"Model '{model_name}' not available for {provider_name}. Available: {', '.join(available_models)}"
            )
        
        # Update the provider instance
        if provider_instance:
            provider_instance.model = model_name
        
        return CommandResult(
            success=True,
            message=f"Switched to model: {model_name}",
            data={"new_model": model_name}
        )
    
    def get_help(self) -> str:
        """Get detailed help for the model command."""
        return """
[bold]Usage:[/bold]
• [green]/model[/green] - Interactive model selector
• [green]/model <model_name>[/green] - Switch to specific model directly

[bold]Examples:[/bold]
• [green]/model[/green] - Opens model selection menu
• [green]/model qwen2.5-coder:7b[/green] - Switch to qwen2.5-coder:7b
• [green]/model gemini-2.0-flash-001[/green] - Switch to Gemini model

Available models depend on your current provider (Ollama or Gemini).
The interactive selector shows all available models for your provider.
"""