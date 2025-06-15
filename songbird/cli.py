# songbird/cli.py
from __future__ import annotations
import typer
from rich.console import Console
from . import __version__

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
    """Start an interactive Songbird session (placeholder)."""
    show_banner()
    console.print("\n🤖 Welcome to Songbird - Your AI coding companion!", style="bold green")
    console.print("💡 Placeholder chat session started. Full functionality coming soon!", style="dim")

@app.command()
def version() -> None:
    """Show Songbird version information."""
    show_banner()
    console.print(f"\n📦 Songbird v{__version__}", style="bold cyan")
    console.print("🚀 Terminal-first AI coding companion", style="dim")

if __name__ == "__main__":
    # Running file directly: python -m songbird.cli
    app()
