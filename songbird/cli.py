# songbird/cli.py
from __future__ import annotations
import asyncio
import os
from typing import Optional
import typer
from rich.console import Console
from rich.prompt import Prompt
from . import __version__
from .llm.providers import get_provider, list_available_providers, get_default_provider
from .conversation import ConversationOrchestrator

app = typer.Typer(add_completion=False, rich_markup_mode="rich", help="Songbird - Terminal-first AI coding companion", no_args_is_help=False)
console = Console()

def show_banner():
    """Display the Songbird ASCII banner in blue."""
    banner = """
███████╗ ██████╗ ███╗   ██╗ ██████╗ ██████╗ ██╗██████╗ ██████╗ 
██╔════╝██╔═══██╗████╗  ██║██╔════╝ ██╔══██╗██║██╔══██╗██╔══██╗
███████╗██║   ██║██╔██╗ ██║██║  ███╗██████╔╝██║██████╔╝██║  ██║
╚════██║██║   ██║██║╚██╗██║██║   ██║██╔══██╗██║██╔══██╗██║  ██║
███████║╚██████╔╝██║ ╚████║╚██████╔╝██████╔╝██║██║  ██║██████╔╝
╚══════╝ ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝ ╚═════╝ ╚═╝╚═╝  ╚═╝╚═════╝
"""
    console.print(banner, style="bold blue")

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="LLM provider to use (gemini, ollama)"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
    list_providers: bool = typer.Option(False, "--list-providers", help="List available providers and exit")
):
    """
    Songbird - Terminal-first AI coding companion
    
    Run 'songbird' to start an interactive chat session with AI and tools.
    Run 'songbird version' to show version information.
    """
    if list_providers:
        available = list_available_providers()
        default = get_default_provider()
        console.print("Available providers:", style="bold")
        for p in available:
            status = " (default)" if p == default else ""
            console.print(f"  {p}{status}")
        return
    
    if ctx.invoked_subcommand is None:
        # No subcommand provided, start chat session
        chat(provider=provider, model=model)

@app.command(hidden=True)
def chat(provider: Optional[str] = None, model: Optional[str] = None) -> None:
    """Start an interactive Songbird session with AI and tools (same as running songbird without args)."""
    show_banner()
    console.print("\nWelcome to Songbird - Your AI coding companion!", style="bold green")
    console.print("Available tools: file_search, file_read, file_create, file_edit, shell_exec", style="dim")
    console.print("I can search, read, edit files with diffs, and run shell commands. Type 'exit' to quit.\n", style="dim")
    
    # Determine provider and model
    provider_name = provider or get_default_provider()
    
    # Set default models based on provider
    default_models = {
        "gemini": "gemini-2.0-flash-001",
        # "ollama": "qwen2.5-coder:7b"
        "ollama": "devstral:latest"
    }
    model_name = model or default_models.get(provider_name, "qwen2.5-coder:7b")
    
    console.print(f"Using provider: {provider_name}, model: {model_name}", style="dim")
    
    # Initialize LLM provider and conversation orchestrator
    try:
        provider_class = get_provider(provider_name)
        
        if provider_name == "gemini":
            provider_instance = provider_class(model=model_name)
        elif provider_name == "ollama":
            provider_instance = provider_class(
                base_url="http://127.0.0.1:11434",
                model=model_name
            )
        else:
            provider_instance = provider_class(model=model_name)
        
        orchestrator = ConversationOrchestrator(provider_instance, os.getcwd())
        
        # Start chat loop
        asyncio.run(_chat_loop(orchestrator))
        
    except Exception as e:
        console.print(f"Error starting Songbird: {e}", style="red")
        if provider_name == "gemini":
            console.print("Make sure you have set GOOGLE_API_KEY environment variable", style="dim")
            console.print("Get your API key from: https://aistudio.google.com/app/apikey", style="dim")
        elif provider_name == "ollama":
            console.print("Make sure Ollama is running: ollama serve", style="dim")
            console.print(f"And the model is available: ollama pull {model_name}", style="dim")


async def _chat_loop(orchestrator: ConversationOrchestrator):
    """Run the interactive chat loop."""
    while True:
        try:
            # Get user input
            user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")
            
            if user_input.lower() in ["exit", "quit", "bye"]:
                console.print("\nGoodbye!", style="bold blue")
                break
                
            # Get AI response
            console.print("\n[medium_spring_green]Songbird[/medium_spring_green] (thinking...)", style="dim")
            response = await orchestrator.chat(user_input)
            
            # Display response
            console.print(f"\n{response}")
            
        except KeyboardInterrupt:
            console.print("\n\nGoodbye!", style="bold blue")
            break
        except Exception as e:
            console.print(f"\nError: {e}", style="red")

@app.command()
def version() -> None:
    """Show Songbird version information."""
    show_banner()
    console.print(f"\nSongbird v{__version__}", style="bold cyan")
    console.print("Terminal-first AI coding companion", style="dim")

if __name__ == "__main__":
    # Running file directly: python -m songbird.cli
    app()
