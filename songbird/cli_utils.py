from typing import Optional, List
from rich.console import Console
from rich.panel import Panel


class EnhancedCLI:
    """Enhanced CLI interface with improved user experience."""
    
    def __init__(self):
        self.console = Console()
    
    def display_error_with_suggestions(self, error: Exception, suggestions: Optional[List[str]] = None):
        """Display errors with helpful suggestions."""
        error_text = f"[bold red]Error:[/bold red] {str(error)}"
        
        if suggestions:
            error_text += "\n\n[bold]Suggestions:[/bold]"
            for suggestion in suggestions:
                error_text += f"\n• {suggestion}"
        
        panel = Panel(
            error_text,
            title="[bold red]Error Occurred[/bold red]",
            border_style="red"
        )
        
        self.console.print(panel)


def create_enhanced_help() -> str:
    """Create enhanced help text with formatting."""
    help_text = """
[bold cyan]Songbird AI - Terminal-based AI Coding Companion[/bold cyan]

[bold]Basic Usage:[/bold]
  songbird                    Start interactive chat session
  songbird --continue         Continue most recent session
  songbird --resume           Select from previous sessions
  songbird --provider <name>  Use specific provider
  songbird -p "message"       Print mode: one-off commands (use quotes for multi-word messages)
  songbird -p "msg" --quiet   Ultra-quiet: only final answer, no tool output

[bold]Available Providers:[/bold]
  openai      OpenAI GPT models (requires OPENAI_API_KEY)
  claude      Anthropic Claude (requires ANTHROPIC_API_KEY)
  gemini      Google Gemini (requires GEMINI_API_KEY)
  ollama      Local Ollama models (no API key needed)
  openrouter  OpenRouter multi-provider (requires OPENROUTER_API_KEY)

[bold]In-Chat Commands:[/bold]
  /help, /h, /?        Show available commands
  /model, /m           Switch AI model interactively
  /clear, /cls, /c     Clear conversation history
  /exit, /quit         Exit the session

[bold]Examples:[/bold]
  songbird --provider gemini --continue
  songbird --resume
  songbird --list-providers
  songbird -p "What is 2+2?"
  songbird -p "List all Python files in this directory"
  songbird -p "Create hello.py" --quiet
  songbird -p "What's the current time?" --quiet

[bold]Environment Variables:[/bold]
  OPENAI_API_KEY      OpenAI API key
  ANTHROPIC_API_KEY   Anthropic Claude API key
  GEMINI_API_KEY      Google Gemini API key
  OPENROUTER_API_KEY  OpenRouter API key
  SONGBIRD_AUTO_APPLY Auto-apply file edits (y/n)

For detailed documentation, visit:
https://github.com/Spandan7724/songbird
"""
    return help_text


def display_enhanced_help(console: Console):
    """Display enhanced help information."""
    help_panel = Panel(
        create_enhanced_help(),
        title="[bold blue]Songbird Help[/bold blue]",
        border_style="blue",
        padding=(1, 2)
    )
    console.print(help_panel)


# Enhanced CLI instance for global use
enhanced_cli = EnhancedCLI()