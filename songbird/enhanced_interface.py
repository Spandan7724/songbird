# songbird/cli/enhanced_interface.py
"""Enhanced CLI interface with improved user experience."""

import asyncio
import sys
from typing import Optional, List
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.live import Live
import typer

from .llm.providers import get_default_provider, get_provider, list_available_providers
from .memory.optimized_manager import OptimizedSessionManager
from .memory.models import Session
from .performance import enable_profiling, get_profiler, OptimizationSuggestions


def create_banner() -> Panel:
    """Create the Songbird banner."""
    banner_text = """
    Songbird AI
    Terminal-First AI Coding Companion
    
    Multi-Provider • Agentic • Tool-Powered
    """
    
    return Panel(
        Text(banner_text, style="bold cyan", justify="center"),
        title="[bold blue]Welcome to Songbird[/bold blue]",
        border_style="blue",
        padding=(1, 2)
    )


def create_provider_status_table() -> Table:
    """Create a table showing provider availability with discovery status."""
    table = Table(title="[bold]Provider Status[/bold]", show_header=True, header_style="bold magenta")
    table.add_column("Provider", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Models Available", style="dim")
    table.add_column("Discovery", justify="center", style="dim")
    
    # Get provider information with discovery
    from .llm.providers import get_provider_info
    provider_info = get_provider_info(use_discovery=True)
    
    for name, info in provider_info.items():
        # Status and readiness
        if info["ready"]:
            status = "[green]✓ Ready[/green]"
        elif info["available"]:
            status = "[yellow]⚠ Setup Required[/yellow]"
        else:
            status = "[red]✗ Unavailable[/red]"
        
        # Models information
        if info["models"]:
            models = ", ".join(info["models"][:2])
            if len(info["models"]) > 2:
                models += f" (+{len(info['models']) - 2} more)"
        else:
            models = "[dim]None found[/dim]"
        
        # Discovery status
        if info.get("models_discovered", False):
            discovery_status = "[green]✓ Live[/green]"
        else:
            discovery_status = "[dim]Fallback[/dim]"
        
        table.add_row(name.title(), status, models, discovery_status)
    
    return table


def display_session_menu(sessions: List[Session], console: Console) -> Optional[Session]:
    """Display an interactive session selection menu."""
    if not sessions:
        console.print("[yellow]No previous sessions found.[/yellow]")
        return None
    
    console.print("\n[bold]Previous Sessions:[/bold]")
    
    # Create session table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="cyan", no_wrap=True, width=3)
    table.add_column("Created", style="green")
    table.add_column("Messages", justify="center", width=8)
    table.add_column("Summary", style="dim")
    
    for i, session in enumerate(sessions, 1):
        created = session.created_at.strftime("%m/%d %H:%M")
        message_count = str(len(session.messages))
        summary = session.summary or "[dim]No summary[/dim]"
        
        # Truncate long summaries
        if len(summary) > 60:
            summary = summary[:57] + "..."
        
        table.add_row(str(i), created, message_count, summary)
    
    console.print(table)
    
    # Get user selection
    try:
        while True:
            choice = Prompt.ask(
                "\nSelect a session number (or 'q' to quit)",
                choices=[str(i) for i in range(1, len(sessions) + 1)] + ["q"],
                default="q"
            )
            
            if choice == "q":
                return None
            
            try:
                index = int(choice) - 1
                return sessions[index]
            except (ValueError, IndexError):
                console.print("[red]Invalid selection. Please try again.[/red]")
    
    except KeyboardInterrupt:
        return None


def display_performance_summary(console: Console, show_details: bool = False):
    """Display performance profiling summary if available."""
    profiler = get_profiler()
    report = profiler.generate_report()
    
    if report.operations_count == 0:
        return
    
    # Quick summary
    summary_text = f"[dim]Performance: {report.operations_count} ops, "
    summary_text += f"{report.total_duration:.2f}s total, "
    summary_text += f"{report.avg_duration:.3f}s avg[/dim]"
    
    console.print(summary_text)
    
    if show_details:
        console.print("\n[bold]Performance Details:[/bold]")
        
        # Optimization suggestions
        suggestions = OptimizationSuggestions.analyze_report(report)
        for suggestion in suggestions[:3]:  # Show top 3 suggestions
            console.print(f"💡 {suggestion}")


class EnhancedCLI:
    """Enhanced CLI interface with improved user experience."""
    
    def __init__(self):
        self.console = Console()
        self.performance_enabled = False
    
    def display_startup_banner(self):
        """Display simplified system status."""
        # Show ready providers (with API keys configured)
        from .llm.providers import list_ready_providers
        ready = list_ready_providers()
        self.console.print(f"Ready providers: {', '.join(ready)}")
    
    def handle_session_selection(self, working_directory: str, continue_recent: bool = False) -> Optional[Session]:
        """Handle session selection logic."""
        session_manager = OptimizedSessionManager(working_directory=working_directory)
        
        if continue_recent:
            # Continue most recent session
            sessions = session_manager.list_sessions()
            if sessions:
                most_recent = sessions[0]  # Sessions are sorted by creation date
                self.console.print(f"[green]Continuing session from {most_recent.created_at.strftime('%m/%d %H:%M')}[/green]")
                return session_manager.load_session(most_recent.id)
            else:
                self.console.print("[yellow]No previous sessions found. Starting new session.[/yellow]")
                return None
        else:
            # Show session selection menu
            sessions = session_manager.list_sessions()
            return display_session_menu(sessions, self.console)
    
    def handle_provider_selection(self, provider_name: Optional[str]) -> Optional[object]:
        """Handle provider selection and initialization."""
        if provider_name:
            # Use specified provider
            try:
                provider_class = get_provider(provider_name)
                provider = provider_class()
                self.console.print(f"[green]Using {provider_name} provider[/green]")
                return provider
            except Exception as e:
                self.console.print(f"[red]Error initializing {provider_name}: {e}[/red]")
                return None
        else:
            # Auto-select best available provider
            default_provider = get_default_provider()
            try:
                provider_class = get_provider(default_provider)
                provider = provider_class()
                self.console.print(f"[green]Auto-selected {default_provider} provider[/green]")
                return provider
            except Exception as e:
                self.console.print(f"[red]Error with default provider {default_provider}: {e}[/red]")
                return None
    
    def enable_performance_monitoring(self, enable: bool = True):
        """Enable or disable performance monitoring."""
        if enable:
            enable_profiling()
            self.performance_enabled = True
            self.console.print("[dim]Performance monitoring enabled[/dim]")
        else:
            self.performance_enabled = False
    
    def display_startup_tips(self):
        """Display helpful startup tips."""
        tips = [
            "💡 Type '/help' during conversation for available commands",
            "💡 Use '/model' to switch between different AI models",
            "💡 Press Ctrl+C to exit gracefully at any time",
            "💡 Use '--continue' flag to resume your last session",
            "💡 Check available providers with '--list-providers'"
        ]
        
        # Show a random tip
        import random
        tip = random.choice(tips)
        self.console.print(f"\n{tip}\n", style="dim italic")
    
    def display_goodbye_message(self):
        """Display simplified goodbye message."""
        self.console.print("Goodbye", style="dim cornflower_blue")
    
    async def display_thinking_indicator(self, message: str = "Thinking..."):
        """Display an animated thinking indicator."""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True
        ) as progress:
            task = progress.add_task(message, total=None)
            # The progress spinner will animate automatically
            # This is meant to be used with context managers in actual implementation
    
    def confirm_dangerous_operation(self, operation: str, details: str = "") -> bool:
        """Confirm dangerous operations with clear warnings."""
        warning_text = f"[bold red]⚠️  WARNING: {operation}[/bold red]"
        if details:
            warning_text += f"\n{details}"
        
        panel = Panel(
            warning_text,
            title="[bold red]Confirmation Required[/bold red]",
            border_style="red"
        )
        
        self.console.print(panel)
        return Confirm.ask("Do you want to proceed?", default=False)
    
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
    
    def display_success_message(self, message: str, details: Optional[str] = None):
        """Display success messages with optional details."""
        success_text = f"[bold green]{message}[/bold green]"
        if details:
            success_text += f"\n{details}"
        
        panel = Panel(
            success_text,
            title="[bold green]Success[/bold green]",
            border_style="green"
        )
        
        self.console.print(panel)


def create_enhanced_help() -> str:
    """Create enhanced help text with formatting."""
    help_text = """
[bold cyan]Songbird AI - Terminal-First AI Coding Companion[/bold cyan]

[bold]Basic Usage:[/bold]
  songbird                    Start interactive chat session
  songbird --continue         Continue most recent session
  songbird --resume           Select from previous sessions
  songbird --provider <name>  Use specific provider

[bold]Available Providers:[/bold]
  openai      OpenAI GPT models (requires OPENAI_API_KEY)
  claude      Anthropic Claude (requires ANTHROPIC_API_KEY)
  gemini      Google Gemini (requires GOOGLE_API_KEY)
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

[bold]Environment Variables:[/bold]
  OPENAI_API_KEY      OpenAI API key
  ANTHROPIC_API_KEY   Anthropic Claude API key
  GOOGLE_API_KEY      Google Gemini API key
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


def create_version_info() -> str:
    """Create version information display."""
    from . import __version__
    
    version_text = f"""
[bold cyan]Songbird AI v{__version__}[/bold cyan]

[bold]Features:[/bold]
• Multi-provider LLM support (OpenAI, Claude, Gemini, Ollama, OpenRouter)
• Advanced tool arsenal (11 professional tools)
• Persistent session memory with project isolation
• Real-time model switching with in-chat commands
• Performance profiling and optimization
• Cross-platform compatibility

[bold]Architecture:[/bold]
• Clean separated layers (UI/Agent/Tools)
• Agentic intelligence with adaptive termination
• Centralized tool registry with provider-agnostic schemas
• Optimized session management with batch writes
• Graceful shutdown with signal handling

[bold]Author:[/bold] Spandan Chavan
[bold]Repository:[/bold] https://github.com/Spandan7724/songbird
[bold]License:[/bold] MIT
"""
    return version_text


def display_version_info(console: Console):
    """Display version information (simplified)."""
    from . import __version__
    console.print(__version__)


# Enhanced CLI instance for global use
enhanced_cli = EnhancedCLI()