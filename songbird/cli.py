# songbird/cli.py
from __future__ import annotations
import asyncio
import os
import typer
from rich.console import Console
from rich.prompt import Prompt
from . import __version__
from .llm.providers import OllamaProvider
from .conversation import ConversationOrchestrator

app = typer.Typer(add_completion=False, rich_markup_mode="rich", help="Songbird - Terminal-first AI coding companion", no_args_is_help=True)
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

@app.callback()
def main():
    """
    Songbird - Terminal-first AI coding companion
    
    A terminal-first AI coding companion that runs primarily on local LLMs
    and augments its reasoning with high-performance command-line tools.
    """
    pass

@app.command()
def chat() -> None:
    """Start an interactive Songbird session with AI and tools."""
    show_banner()
    console.print("\n🤖 Welcome to Songbird - Your AI coding companion!", style="bold green")
    console.print("🔧 Available tools: file_search, file_read, file_edit", style="dim")
    console.print("📝 I can search, read, and edit files with diff previews. Type 'exit' to quit.\n", style="dim")
    
    # Initialize LLM provider and conversation orchestrator
    try:
        provider = OllamaProvider(
            base_url="http://127.0.0.1:11434",
            model="qwen2.5-coder:7b"
        )
        orchestrator = ConversationOrchestrator(provider, os.getcwd())
        
        # Start chat loop
        asyncio.run(_chat_loop(orchestrator))
        
    except Exception as e:
        console.print(f"❌ Error starting Songbird: {e}", style="red")
        console.print("💡 Make sure Ollama is running: ollama serve", style="dim")
        console.print("💡 And the model is available: ollama pull qwen2.5-coder:7b", style="dim")


async def _chat_loop(orchestrator: ConversationOrchestrator):
    """Run the interactive chat loop."""
    while True:
        try:
            # Get user input
            user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")
            
            if user_input.lower() in ["exit", "quit", "bye"]:
                console.print("\n👋 Goodbye!", style="bold blue")
                break
                
            # Get AI response
            console.print("\n[bold yellow]Songbird[/bold yellow] (thinking...)", style="dim")
            response = await orchestrator.chat(user_input)
            
            # Display response
            console.print(f"\n[bold yellow]Songbird[/bold yellow]: {response}")
            
        except KeyboardInterrupt:
            console.print("\n\n👋 Goodbye!", style="bold blue")
            break
        except Exception as e:
            console.print(f"\n❌ Error: {e}", style="red")

@app.command()
def version() -> None:
    """Show Songbird version information."""
    show_banner()
    console.print(f"\n📦 Songbird v{__version__}", style="bold cyan")
    console.print("🚀 Terminal-first AI coding companion", style="dim")

if __name__ == "__main__":
    # Running file directly: python -m songbird.cli
    app()
