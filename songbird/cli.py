# songbird/cli.py
from __future__ import annotations
import typer

app = typer.Typer(add_completion=False, rich_markup_mode="rich", help="Songbird - Terminal-first AI coding companion", no_args_is_help=True)

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
    typer.echo("Songbird – placeholder chat started.")

if __name__ == "__main__":
    # Running file directly: python -m songbird.cli
    app()
