# songbird/cli.py
from __future__ import annotations
import asyncio
import os
from datetime import datetime, timezone
from typing import List, Optional
import typer
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich.syntax import Syntax
from rich.panel import Panel
from . import __version__
from .llm.providers import get_provider, list_available_providers, get_default_provider
from .conversation import ConversationOrchestrator
from .memory.manager import SessionManager
from .memory.models import Session, SessionStub, Message
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


def _render_msg(msg: "Message") -> None:
    if msg.role == "user":
        console.print(f"[bold cyan]You:[/bold cyan] {msg.content}")
    elif msg.role == "assistant":
        console.print(
            f"[medium_spring_green]Songbird:[/medium_spring_green] {msg.content}"
        )
    elif msg.role == "tool":
        content = msg.content
        if content.startswith("{") and content.endswith("}"):
            # JSON result wrapper
            console.print(
                Panel.fit(content, title="tool result", border_style="dim")
            )
        elif content.lstrip().startswith("---"):
            # Diff text saved as JSON string
            syntax = Syntax(content, "diff", theme="ansi_dark", word_wrap=True)
            console.print(
                Panel(syntax, title="diff preview", border_style="blue")
            )
        else:
            console.print(
                Panel.fit(content, title="tool output", border_style="dim")
            )

    # DISPLAY (captured diff previews, shell output, etc.) ------------------ #
    elif msg.role == "display":
        txt = msg.content
        if txt.lstrip().startswith("---"):
            syntax = Syntax(txt, "diff", theme="ansi_dark", word_wrap=True)
            console.print(
                Panel(syntax, title="diff preview", border_style="blue")
            )
        else:
            console.print(Panel.fit(txt, border_style="dim", title="output"))
    else:
        console.print(f"[dim]{msg.role}: {msg.content}[/dim]")


def _replay_history(session: Session) -> None:
    """Print every stored message except system prompts."""
    console.rule("[dim]Previous conversation[/dim]")
    for msg in session.messages:
        if msg.role == "system":
            continue
        _render_msg(msg)
    console.rule("[dim]--- end of history ---[/dim]")


def format_time_ago(dt: datetime) -> str:
    """Return “3h ago”, “just now”, or YYYY-MM-DD if > 7 days."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    diff = now - dt

    if diff.days > 7:
        return dt.strftime("%Y-%m-%d")
    if diff.days:
        return f"{diff.days}d ago"
    hours = diff.seconds // 3600
    if hours:
        return f"{hours}h ago"
    minutes = diff.seconds // 60
    if minutes:
        return f"{minutes}m ago"
    return "just now"


def display_session_selector(sessions: List[Session]) -> Optional[Session]:
    """Render a Rich table, allow numeric pick, return selected Session."""
    if not sessions:
        console.print("No previous sessions found.", style="yellow")
        return None

    sessions = sorted(sessions, key=lambda s: s.updated_at, reverse=True)

    table = Table(title="Previous Sessions", show_lines=True)
    table.add_column("#", justify="right", style="bold cyan")
    table.add_column("Updated", style="green")
    table.add_column("Msgs", justify="right")
    table.add_column("Summary")

    for idx, s in enumerate(sessions, 1):
        updated = format_time_ago(s.updated_at)
        count = s.n_messages
        table.add_row(str(idx), updated, str(count), s.summary or "no summary")

    console.print(table)
    choice = Prompt.ask("\nSelect session (blank to cancel)", default="")

    if not choice.strip():
        return None
    try:
        sel = int(choice) - 1
        if 0 <= sel < len(sessions):
            return sessions[sel]
    except ValueError:
        pass

    console.print("Invalid selection.", style="red")
    return None


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p", help="LLM provider (gemini, ollama)"
    ),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model"),
    continue_: bool = typer.Option(
        False, "--continue", "-c", help="Continue latest session in project"
    ),
    resume: bool = typer.Option(
        False, "--resume", "-r", help="Choose from past sessions in project"
    ),
    list_providers: bool = typer.Option(
        False, "--list-providers", help="List available providers and exit"
    ),
) -> None:
    """Run **songbird** to chat.  Use -c/-r for session memory."""
    if list_providers:
        available = list_available_providers()
        default = get_default_provider()
        console.print("Available providers:", style="bold")
        for p in available:
            console.print(f"  {p}{' (default)' if p == default else ''}")
        return

    if ctx.invoked_subcommand is None:
        chat(provider, model, continue_, resume)


@app.command(hidden=True)
def chat(
    provider: Optional[str],
    model: Optional[str],
    continue_: bool,
    resume: bool,
) -> None:
    show_banner()
    console.print(
        "\nWelcome to Songbird - Your AI coding companion!", style="bold green")
    console.print(
        "Available tools: file_search, file_read, file_create, file_edit, shell_exec", style="dim")
    console.print(
        "I can search, read, edit files with diffs, and run shell commands. Type 'exit' to quit.\n", style="dim")




    # 1.  Resolve / create session ------------------------------------- #
    sess_mgr = SessionManager(os.getcwd())

    def hydrate(stub: SessionStub) -> Session:
        full = sess_mgr.load_session(stub.id)
        if full is None:
            console.print(
                f"[yellow]Warning:[/] session {stub.id} could not be loaded; "
                "starting a new one."
            )
            return sess_mgr.create_session()
        return full

    if continue_ and resume:
        console.print("Choose either --continue or --resume.", style="red")
        raise typer.Exit(1)

    if continue_:
        session = sess_mgr.get_latest_session() or sess_mgr.create_session()
        console.print("[dim]Continuing latest session.[/dim]")

    elif resume:
        stub = display_session_selector(sess_mgr.list_sessions())
        if stub is None:
            raise typer.Exit()
        session = hydrate(stub)

    else:
        session = sess_mgr.create_session()

    # ------------------------------------------------------------------ #
    # 2.  Replay previous conversation (if any)
    # ------------------------------------------------------------------ #
    if session.messages:                
        _replay_history(session)



    # 2.  Provider & orchestrator -------------------------------------- #
    provider_name = provider or get_default_provider()
    default_models = {
        "gemini": "gemini-2.0-flash-001",
        "ollama": "devstral:latest",
    }
    model_name = model or default_models.get(provider_name, "qwen2.5-coder:7b")
    console.print(
        f"Using provider: {provider_name}, model: {model_name}", style="dim"
    )

    try:
        provider_cls = get_provider(provider_name)
        if provider_name == "gemini":
            provider_inst = provider_cls(model=model_name)
        elif provider_name == "ollama":
            provider_inst = provider_cls(
                base_url="http://127.0.0.1:11434", model=model_name
            )
        else:
            provider_inst = provider_cls(model=model_name)

        orchestrator = ConversationOrchestrator(
            provider_inst, Path.cwd(), session=session
        )
        asyncio.run(_chat_loop(orchestrator, sess_mgr))
    except Exception as exc:
        console.print(f"Startup error: {exc}", style="red")
        if provider_name == "gemini":
            console.print("Set GOOGLE_API_KEY env var.", style="dim")
        elif provider_name == "ollama":
            console.print("Ensure `ollama serve` is running.", style="dim")
            console.print(f"And the model is available: ollama pull {model_name}", style="dim")


async def _chat_loop(
    orchestrator: ConversationOrchestrator, sess_mgr: SessionManager
) -> None:
    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")
            if user_input.lower() in {"exit", "quit", "bye"}:
                console.print("\nGoodbye!", style="bold blue")
                break

            console.print(
                "\n[medium_spring_green]Songbird[/medium_spring_green] (thinking…)",
                style="dim",
            )
            reply = await orchestrator.chat(user_input)
            console.print(f"\n{reply}")

        except KeyboardInterrupt:
            console.print("\n\nGoodbye!", style="bold blue")
            break
        except Exception as exc:
            console.print(f"\nError: {exc}", style="red")
        finally:
            # Persist after every turn
            if orchestrator.session:
                sess_mgr.save_session(orchestrator.session)

@app.command()
def version() -> None:
    """Show Songbird version information."""
    show_banner()
    console.print(f"\nSongbird v{__version__}", style="bold cyan")
    console.print("Terminal-first AI coding companion", style="dim")

if __name__ == "__main__":
    # Running file directly: python -m songbird.cli
    app()
