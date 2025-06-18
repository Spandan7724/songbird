# songbird/cli.py
from __future__ import annotations
import asyncio
import os
import signal
import sys
import time
from threading import Timer
from typing import Optional
from datetime import datetime
import json
import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.status import Status
from rich.live import Live
from rich.table import Table
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from . import __version__
from .llm.providers import get_provider, list_available_providers, get_default_provider
from .conversation import ConversationOrchestrator, safe_interactive_menu
from .memory.manager import SessionManager
from .memory.models import Session
from .commands import CommandSelector, get_command_registry, CommandInputHandler
from .memory.history_manager import MessageHistoryManager
from .commands.loader import load_all_commands, is_command_input, parse_command_input

app = typer.Typer(add_completion=False, rich_markup_mode="rich",
                  help="Songbird - Terminal-first AI coding companion", no_args_is_help=False)
console = Console()

# ------------------------------------------------------------------ #
#  Ctrl-C double-tap guard (global)
# ------------------------------------------------------------------ #
_GRACE = 2.0           # seconds between taps
_last = None           # time of previous SIGINT
_cleanup_timer = None  # track active cleanup timer for resource safety
_in_status = False     # track if we're in a status/thinking state

def _flash_notice():
    global _cleanup_timer
    # Cancel any existing cleanup timer to prevent accumulation
    if _cleanup_timer:
        _cleanup_timer.cancel()
    
    # If we're in status mode, use console.print instead of raw output
    if _in_status:
        # Don't try to manipulate cursor during status
        return
    
    # Normal mode - use ANSI escape sequences
    sys.stdout.write("\033[s")  # Save cursor position
    sys.stdout.write("\033[A")  # Move up one line
    sys.stdout.write("\r\033[2K")  # Clear that line
    sys.stdout.write("\033[90mPress Ctrl+C again to exit\033[0m")  # Gray notice
    sys.stdout.write("\033[u")  # Restore cursor position
    sys.stdout.flush()
    
    # Schedule cleanup: clear the notice line above
    def _clear():
        if not _in_status:
            sys.stdout.write("\033[s")  # Save cursor position
            sys.stdout.write("\033[A")  # Move up one line
            sys.stdout.write("\r\033[2K")  # Clear that line
            sys.stdout.write("\033[u")  # Restore cursor position
            sys.stdout.flush()
        
    _cleanup_timer = Timer(_GRACE, _clear)
    _cleanup_timer.start()

def _sigint(signum, frame):
    global _last, _cleanup_timer
    now = time.monotonic()

    if _last and (now - _last) < _GRACE:          # second tap → quit
        # Cancel any pending cleanup timer before exit
        if _cleanup_timer:
            _cleanup_timer.cancel()
        signal.signal(signal.SIGINT, signal.default_int_handler)
        
        if _in_status:
            # Force stop the status if active
            console.print("\n[red]Interrupted![/red]")
        else:
            # Clear the notice line if it exists
            sys.stdout.write("\033[A\r\033[2K\033[B")  # Up, clear, down
        
        print()  # Clean newline before exit
        raise KeyboardInterrupt

    # First tap handling
    if _in_status:
        # During status/thinking, just show a console message
        console.print("\n[dim]Press Ctrl+C again to exit[/dim]")
    else:
        # Normal input mode - erase ^C and show notice
        sys.stdout.write("\b\b  \b\b")  # Backspace over ^C
        sys.stdout.flush()
        _flash_notice()
    
    _last = now               # start grace window

# Register the signal handler
signal.signal(signal.SIGINT, _sigint)
# ------------------------------------------------------------------ #
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


def format_time_ago(dt: datetime) -> str:
    """Format a datetime as a human-readable time ago string."""
    now = datetime.now()
    diff = now - dt

    if diff.days > 7:
        return dt.strftime("%Y-%m-%d")
    elif diff.days > 0:
        return f"{diff.days}d ago"
    elif diff.seconds > 3600:
        return f"{diff.seconds // 3600}h ago"
    elif diff.seconds > 60:
        return f"{diff.seconds // 60}m ago"
    else:
        return "just now"


async def display_session_selector(sessions: list[Session]) -> Optional[Session]:
    """Display an interactive session selector with better terminal handling."""
    if not sessions:
        console.print("No previous sessions found.", style="yellow")
        return None

    # Sort sessions by updated_at descending
    sessions.sort(key=lambda s: s.updated_at, reverse=True)
    
    # Limit sessions to avoid terminal overflow
    max_sessions = min(30, console.height - 10 if console.height > 10 else 20)
    display_sessions = sessions[:max_sessions]
    
    # Prepare options
    options = []
    for session in display_sessions:
        created = format_time_ago(session.created_at)
        modified = format_time_ago(session.updated_at)
        msg_count = len(session.messages)
        summary = (session.summary or "Empty session")[:50]
        if len(session.summary or "") > 50:
            summary += "..."
        
        option = f"{modified} | {created} | {msg_count} msgs | {summary}"
        options.append(option)
    
    options.append("Start new session")
    
    if len(sessions) > max_sessions:
        console.print(f"[yellow]Showing {max_sessions} most recent sessions out of {len(sessions)} total[/yellow]\n")
    
    # Use interactive menu
    selected_idx = await safe_interactive_menu(
        "Select a session to resume:",
        options,
        default_index=0
    )
    
    if selected_idx is None:
        # User cancelled, return None to indicate cancellation
        return None
    
    if selected_idx == len(display_sessions):
        return None
        
    return display_sessions[selected_idx]


def replay_conversation(session: Session):
    """Replay the conversation history to show it as the user saw it."""
    # Import here to avoid circular dependency
    from .tools.file_operations import display_diff_preview
    from rich.panel import Panel
    from rich.syntax import Syntax

    # Group messages with their tool calls and results
    i = 0
    while i < len(session.messages):
        msg = session.messages[i]

        if msg.role == "system":
            # Skip system messages in replay
            i += 1
            continue

        elif msg.role == "user":
            console.print(f"\n[bold cyan]You[/bold cyan]: {msg.content}")
            i += 1

        elif msg.role == "assistant":
            # Check if this is a tool-calling message
            if msg.tool_calls:
                # Show thinking message
                console.print(
                    f"\n[medium_spring_green]Songbird[/medium_spring_green] (thinking...)", style="dim")

                # Track tool index for matching with tool results
                tool_result_idx = i + 1

                # Process each tool call
                for tool_call in msg.tool_calls:
                    function_name = tool_call["function"]["name"]
                    arguments = tool_call["function"]["arguments"]

                    # Parse arguments if they're a string
                    if isinstance(arguments, str):
                        arguments = json.loads(arguments)

                    # Get the corresponding tool result
                    tool_result = None
                    if tool_result_idx < len(session.messages) and session.messages[tool_result_idx].role == "tool":
                        tool_result = json.loads(
                            session.messages[tool_result_idx].content)
                        tool_result_idx += 1

                    # Display tool execution based on type
                    if function_name == "file_create" and tool_result:
                        file_path = tool_result.get(
                            "file_path", arguments.get("file_path", "unknown"))
                        content = arguments.get("content", "")

                        console.print(f"\nCreating new file: {file_path}")
                        # Determine language from file extension
                        ext = file_path.split(
                            '.')[-1] if '.' in file_path else 'text'
                        # Create numbered lines manually to match original formatting
                        lines = content.split('\n')
                        numbered_lines = []
                        for idx, line in enumerate(lines, 1):
                            numbered_lines.append(f"  {idx:2d} {line}")
                        formatted_content = '\n'.join(numbered_lines)
                        console.print(
                            f"╭─ New file: {file_path} {'─' * (console.width - len(file_path) - 15)}╮")
                        console.print(formatted_content)
                        console.print(f"╰{'─' * (console.width - 2)}╯")

                    elif function_name == "file_edit" and tool_result:
                        file_path = tool_result.get(
                            "file_path", arguments.get("file_path", "unknown"))
                        if "diff_preview" in tool_result:
                            display_diff_preview(
                                tool_result["diff_preview"], file_path)
                            console.print("\nApply these changes?\n")
                            console.print("[green]▶ Yes[/green]")
                            console.print("  No")
                            console.print("\nSelected: Yes")

                    elif function_name == "shell_exec" and tool_result:
                        command = tool_result.get(
                            "command", arguments.get("command", ""))
                        cwd = tool_result.get("working_directory", "")

                        console.print(f"\nExecuting command: {command}")
                        if cwd:
                            console.print(f"Working directory: {cwd}")

                        # Match the exact shell panel style
                        console.print(
                            f"\n╭─ Shell {'─' * (console.width - 10)}╮")
                        console.print(
                            f"│ > {command}{' ' * (console.width - len(command) - 5)}│")
                        console.print(f"╰{'─' * (console.width - 2)}╯")

                        if "stdout" in tool_result and tool_result["stdout"]:
                            console.print("\nOutput:")
                            console.print("─" * console.width)
                            console.print(tool_result["stdout"].rstrip())
                            console.print("─" * console.width)

                        if "stderr" in tool_result and tool_result["stderr"]:
                            console.print("\nError output:", style="red")
                            console.print(
                                tool_result["stderr"].rstrip(), style="red")

                        exit_code = tool_result.get("exit_code", 0)
                        if exit_code == 0:
                            console.print(
                                f"✓ Command completed successfully (exit code: {exit_code})", style="green")
                        else:
                            console.print(
                                f"✗ Command failed (exit code: {exit_code})", style="red")

                    elif function_name == "file_search" and tool_result:
                        pattern = arguments.get("pattern", "")
                        console.print(f"\nSearching for: {pattern}")

                        # Display search results if available
                        if "matches" in tool_result and tool_result["matches"]:
                            from rich.table import Table
                            table = Table(
                                title=f"Search results for '{pattern}'")
                            table.add_column("File", style="cyan")
                            table.add_column("Line", style="yellow")
                            table.add_column("Content", style="white")

                            # Show first 10
                            for match in tool_result["matches"][:10]:
                                table.add_row(
                                    match.get("file", ""),
                                    str(match.get("line_number", "")),
                                    match.get("line_content", "").strip()
                                )
                            console.print(table)

                    elif function_name == "file_read" and tool_result:
                        file_path = arguments.get("file_path", "")
                        console.print(f"\nReading file: {file_path}")

                        if "content" in tool_result:
                            content = tool_result["content"]
                            # Show first 20 lines
                            lines = content.split('\n')[:20]
                            preview = '\n'.join(lines)
                            if len(content.split('\n')) > 20:
                                preview += "\n... (truncated)"

                            ext = file_path.split(
                                '.')[-1] if '.' in file_path else 'text'
                            syntax = Syntax(
                                preview, ext, theme="monokai", line_numbers=True)
                            console.print(
                                Panel(syntax, title=f"File: {file_path}", border_style="blue"))

                # Skip to after all tool results
                i = tool_result_idx

                # If there's content after tool calls, show it
                if msg.content:
                    console.print(
                        f"\n[medium_spring_green]Songbird[/medium_spring_green]: {msg.content}")

            else:
                # Regular assistant message
                if msg.content:
                    console.print(
                        f"\n[medium_spring_green]Songbird[/medium_spring_green]: {msg.content}")
                i += 1

        elif msg.role == "tool":
            # Tool results are handled inline above, skip
            i += 1
            continue
        else:
            i += 1


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    provider: Optional[str] = typer.Option(
        None, "--provider", "-p", help="LLM provider to use (gemini, ollama)"),
    list_providers: bool = typer.Option(
        False, "--list-providers", help="List available providers and exit"),
    continue_session: bool = typer.Option(
        False, "--continue", "-c", help="Continue the latest session"),
    resume_session: bool = typer.Option(
        False, "--resume", "-r", help="Resume a previous session from a list")
):
    """
    Songbird - Terminal-first AI coding companion
    
    Run 'songbird' to start an interactive chat session with AI and tools.
    Run 'songbird --continue' to continue your latest session.
    Run 'songbird --resume' to select and resume a previous session.
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
        chat(provider=provider,
             continue_session=continue_session, resume_session=resume_session)


@app.command(hidden=True)
def chat(
    provider: Optional[str] = None,
    continue_session: bool = False,
    resume_session: bool = False
) -> None:
    """Start an interactive Songbird session with AI and tools."""
    show_banner()

    # Initialize session manager
    session_manager = SessionManager(os.getcwd())
    session = None

    # Variables to track provider config
    restored_provider = None
    restored_model = None

    # Handle session continuation/resumption
    if continue_session:
        session = session_manager.get_latest_session()
        if session:
            # IMPORTANT: get_latest_session returns a session with None messages
            # We need to load the full session
            session = session_manager.load_session(session.id)
            
            console.print(
                f"\n[cornflower_blue]Continuing session from {format_time_ago(session.updated_at)}[/cornflower_blue]")
            console.print(f"Summary: {session.summary}", style="dim")

            # Restore provider configuration from session
            if session.provider_config:
                restored_provider = session.provider_config.get("provider")
                restored_model = session.provider_config.get("model")
                if restored_provider and restored_model:
                    console.print(
                        f"[dim]Restored: {restored_provider} - {restored_model}[/dim]")

            # Replay the conversation
            replay_conversation(session)
            console.print("\n[dim]--- Session resumed ---[/dim]\n")
        else:
            console.print(
                "\n[yellow]No previous session found. Starting new session.[/yellow]")

    elif resume_session:
        sessions = session_manager.list_sessions()
        if sessions:
            selected_session = asyncio.run(display_session_selector(sessions))
            if selected_session:
                session = session_manager.load_session(selected_session.id)
                if session:
                    console.print(
                        f"\n[cornflower_blue]Resuming session from {format_time_ago(session.updated_at)}[/cornflower_blue]")
                    console.print(f"Summary: {session.summary}", style="dim")

                    # Restore provider configuration from session
                    if session.provider_config:
                        restored_provider = session.provider_config.get(
                            "provider")
                        restored_model = session.provider_config.get("model")
                        if restored_provider and restored_model:
                            console.print(
                                f"[dim]Restored: {restored_provider} - {restored_model}[/dim]")

                    # Replay the conversation
                    replay_conversation(session)
                    console.print("\n[dim]--- Session resumed ---[/dim]\n")
            else:
                # User selected "Start new session"
                console.print(
                    "\n[cornflower_blue]Starting new session[/cornflower_blue]")
        else:
            console.print(
                "\n[cornflower_blue]No previous sessions found. Starting new session.[/cornflower_blue]")

    # Create new session if not continuing/resuming
    if not session:
        session = session_manager.create_session()
        console.print(
            "\nWelcome to Songbird - Your AI coding companion!", style="cornflower_blue")

    console.print(
        "Available tools: file_search, file_read, file_create, file_edit, shell_exec", style="dim")
    console.print(
        "I can search, read, edit files with diffs, and run shell commands.", style="dim")
    console.print(
        "Type [spring_green1]'/'[/spring_green1] for commands, or [spring_green1]'exit'[/spring_green1] to quit.\n", style="dim")

    # Load command system
    command_registry = load_all_commands()
    command_selector = CommandSelector(command_registry, console)
    
    # Create session manager for history
    session_manager = SessionManager(os.getcwd())
    
    # Create history manager (will be passed to input handler after orchestrator is created)
    history_manager = MessageHistoryManager(session_manager)
    
    # Create input handler with history support
    command_input_handler = CommandInputHandler(command_registry, console, history_manager)

    # Determine provider and model
    # Use restored values if available, otherwise use defaults
    provider_name = restored_provider or provider or get_default_provider()

    # Set default models based on provider
    default_models = {
        "gemini": "gemini-2.0-flash-exp",
        "ollama": "qwen2.5-coder:7b"
    }
    model_name = restored_model or default_models.get(
        provider_name, "qwen2.5-coder:7b")

    # Save initial provider config to session (if we have a session)
    if session:
        session.update_provider_config(provider_name, model_name)
        session_manager.save_session(session)

    console.print(
        f"Using provider: {provider_name}, model: {model_name}", style="dim")

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

        # Create orchestrator with session
        orchestrator = ConversationOrchestrator(
            provider_instance, os.getcwd(), session=session)

        # Start chat loop
        asyncio.run(_chat_loop(orchestrator, command_registry, command_input_handler,
                               provider_name, provider_instance))

    except Exception as e:
        console.print(f"Error starting Songbird: {e}", style="red")
        if provider_name == "gemini":
            console.print(
                "Make sure you have set GOOGLE_API_KEY environment variable", style="dim")
            console.print(
                "Get your API key from: https://aistudio.google.com/app/apikey", style="dim")
        elif provider_name == "ollama":
            console.print(
                "Make sure Ollama is running: ollama serve", style="dim")
            console.print(
                f"And the model is available: ollama pull {model_name}", style="dim")


# Updated _chat_loop function for cli.py

async def _chat_loop(orchestrator: ConversationOrchestrator, command_registry,
                     command_input_handler, provider_name: str, provider_instance):
    """Run the interactive chat loop with improved status handling."""
    
    while True:
        try:
            # Get user input
            user_input = command_input_handler.get_input_with_commands("You")
            
            if user_input.lower() in ["exit", "quit", "bye"]:
                console.print("\nGoodbye!", style="bold blue")
                break
                
            if not user_input.strip():
                continue
                
            # Handle commands
            if is_command_input(user_input):
                command_name, args = parse_command_input(user_input)
                command = command_registry.get_command(command_name)

                if command:
                    # Prepare command context with current model
                    context = {
                        "provider": provider_name,
                        "model": provider_instance.model,  # Always use current model
                        "provider_instance": provider_instance,
                        "orchestrator": orchestrator
                    }

                    # Execute command
                    result = await command.execute(args, context)

                    if result.message:
                        if result.success:
                            console.print(f"[green]{result.message}[/green]")
                        else:
                            console.print(f"[red]{result.message}[/red]")

                    # Handle special command results
                    if result.data:
                        if "action" in result.data and result.data["action"] == "clear_history":
                            # Clear conversation history
                            orchestrator.conversation_history = []
                            if orchestrator.session:
                                orchestrator.session.messages = []
                                orchestrator.session_manager.save_session(
                                    orchestrator.session)
                            # Invalidate history cache since we cleared messages
                            if command_input_handler.history_manager:
                                command_input_handler.history_manager.invalidate_cache()
                        
                        if result.data.get("new_model"):
                            # Model was changed, update display and save to session
                            new_model = result.data["new_model"]

                            # Update session with new provider config
                            if orchestrator.session:
                                orchestrator.session.update_provider_config(
                                    provider_name, new_model)
                                # Always save session when model changes
                                orchestrator.session_manager.save_session(
                                    orchestrator.session)

                            # Show the model change
                            console.print(
                                f"[dim]Now using: {provider_name} - {new_model}[/dim]")

                    continue
                else:
                    console.print(
                        f"[red]Unknown command: /{command_name}[/red]")
                    console.print(
                        "Type [green]/help[/green] to see available commands.")
                    continue
            
            # Process with LLM
            global _in_status
            _in_status = True
            
            # Create and manage status properly
            status = Status(
                "[dim]Songbird (thinking…)[/dim]",
                console=console,
                spinner="dots",
                spinner_style="cornflower_blue"
            )
            
            response = None
            try:
                status.start()
                response = await orchestrator.chat(user_input, status=status)
            finally:
                # Always stop status
                status.stop()
                _in_status = False
                # Small delay for clean output
                await asyncio.sleep(0.05)
            
            # Display response with proper spacing
            if response:
                console.print(f"[medium_spring_green]Songbird[/medium_spring_green]: {response}")
                
            # Invalidate history cache
            if command_input_handler.history_manager:
                command_input_handler.history_manager.invalidate_cache()
                
        except KeyboardInterrupt:
            console.print("\nGoodbye!", style="bold blue")
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
